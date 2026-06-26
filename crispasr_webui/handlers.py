"""HTTP request handlers for CrispASR TTS Web UI."""

import hmac
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, unquote, urlparse

from . import auth
from . import config
from . import crispasr_mgmt
from . import database
from . import status
from . import task_queue
from . import templates
from . import text_split
from . import audio_utils


# ─── HTTP Handler ───────────────────────────────────────

class TTSHandler(BaseHTTPRequestHandler):
    api_base = "http://localhost:8080"
    password = ""

    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_binary(self, code, data, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            length = 0
        if length > config.MAX_BODY:
            raise ValueError("Request body too large")
        return self.rfile.read(length) if length else b""

    def _check_auth(self) -> dict | None:
        hdr = self.headers.get("Authorization", "")
        if hdr.startswith("Bearer "):
            return auth.jwt_decode(hdr[7:])
        return None

    # ─── GET ─────────────────────────
    def do_GET(self):
        path = self.path.split("?")[0]  # strip query params for routing

        if path == "/" or path == "/index.html":
            body = templates.HTML_PAGE.encode("utf-8")
            self._send_binary(200, body, "text/html; charset=utf-8")

        elif path == "/api/check":
            if self._check_auth():
                self._send_json(200, {"ok": True})
            else:
                self._send_json(401, {"error": "未登录"})

        elif path == "/api/model":
            self._get_model()

        elif path == "/api/models":
            self._list_models()

        elif path.startswith("/api/audio/"):
            self._serve_audio()

        elif path.startswith("/uploads/"):
            self._serve_upload()

        elif path == "/api/history":
            self._get_history()

        elif path.startswith("/api/task/"):
            self._get_task()

        elif path == "/api/voices":
            self._list_voices()

        elif path == "/api/crispasr/version":
            self._get_crispasr_version()

        elif path == "/api/crispasr/update-status":
            self._get_update_status()

        elif path == "/api/status":
            self._get_status()

        elif path == "/api/logs":
            self._get_logs()

        elif path == "/api/presets":
            self._list_presets()

        elif path == "/api/resumable":
            self._get_resumable()

        else:
            self.send_error(404)

    # ─── POST ────────────────────────
    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/api/login":
            self._do_login()
        elif path == "/api/generate":
            self._do_generate()
        elif path == "/api/split":
            self._do_split()
        elif path == "/api/audition":
            self._do_audition()
        elif path == "/api/voices":
            self._upload_voice()
        elif path == "/api/model/switch":
            self._switch_model()
        elif path == "/api/crispasr/update":
            self._do_crispasr_update()
        elif path == "/api/resume":
            self._do_resume()
        elif path == "/api/history/batch":
            self._batch_delete_history()
        elif path == "/api/presets" and self.command == "POST":
            self._save_preset()
        elif path == "/api/compare":
            self._compare_voices()
        elif path == "/api/batch":
            self._batch_synthesize()
        elif path.startswith("/v1/"):
            self._proxy_api()
        else:
            self.send_error(404)

    def do_DELETE(self):
        path = self.path.split("?")[0]
        if path == "/api/history":
            self._delete_history()
        elif path.startswith("/api/history/"):
            task_id = unquote(path.split("/")[-1])
            self._delete_history_item(task_id)
        elif path == "/api/history/batch":
            self._batch_delete_history()
        elif path.startswith("/api/presets/"):
            name = unquote(path.split("/")[-1])
            self._delete_preset(name)
        elif path.startswith("/api/voices/"):
            name = unquote(path.split("/")[-1])
            self._delete_voice(name)
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ─── Login ───────────────────────
    _login_attempts: dict[str, list] = {}
    _login_lock = threading.Lock()
    _login_last_cleanup: float = 0

    def _do_login(self):
        client_ip = self.client_address[0]
        with self._login_lock:
            now = time.time()
            # Periodic cleanup: remove IPs with no recent attempts
            if now - self._login_last_cleanup > 300:
                self._login_attempts = {
                    ip: ts for ip, ts in self._login_attempts.items()
                    if ts and now - ts[-1] < 300
                }
                self._login_last_cleanup = now
            attempts = self._login_attempts.get(client_ip, [])
            attempts = [t for t in attempts if now - t < 300]
            if len(attempts) >= 10:
                self._send_json(429, {"error": "尝试次数过多，请5分钟后再试"})
                return
            attempts.append(now)
            self._login_attempts[client_ip] = attempts

        try:
            data = json.loads(self._read_body())
            pwd = data.get("password", "")
            if hmac.compare_digest(pwd.encode(), self.password.encode()):
                token = auth.jwt_encode({"sub": "user", "exp": time.time() + config.JWT_EXPIRY})
                self._send_json(200, {"token": token})
            else:
                self._send_json(401, {"error": "密码错误"})
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    # ─── Split ───────────────────────
    def _do_split(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            chunks = text_split.split_text(data["text"])
            self._send_json(200, {"chunks": chunks, "count": len(chunks)})
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    # ─── Audition (single chunk) ─────
    def _do_audition(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            text = data["text"]
            voice = data.get("voice", "serena")
            instruct = data.get("instruct", "")
            speed = data.get("speed", 1.0)

            payload = json.dumps({
                "model": "tts-1",
                "input": text,
                "voice": voice,
                "speed": speed,
                "consent_attestation": "test",
                "spoken_disclaimer": False,
                **({"instruct": instruct} if instruct else {}),
            }, ensure_ascii=False).encode("utf-8")

            req = urllib.request.Request(
                f"{self.api_base}/v1/audio/speech",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                audio_data = resp.read()

            self._send_binary(200, audio_data, "audio/wav")
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Generate ────────────────────
    def _do_generate(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            text = data["text"]
            voice = data.get("voice", "serena")
            instruct = data.get("instruct", "")
            speed = data.get("speed", 1.0)
            fmt = data.get("fmt", "wav")
            chunks_config = data.get("chunks_config")

            # If client sent pre-split chunks, use them; otherwise split server-side
            if chunks_config and len(chunks_config) > 0:
                final_chunks = []
                for c in chunks_config:
                    final_chunks.append({
                        "text": c.get("text", ""),
                        "voice": c.get("voice", ""),
                        "instruct": c.get("instruct", ""),
                    })
            else:
                final_chunks = text_split.split_text(text)

            task_id = uuid.uuid4().hex[:12]

            # Write to DB
            conn = database.db_conn()
            conn.execute(
                "INSERT INTO history (id,text,voice,instruct,speed,fmt,status,chunks_config,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, text[:2000], voice, instruct, speed, fmt, "pending",
                 json.dumps(final_chunks, ensure_ascii=False), time.time()),
            )
            conn.commit()
            conn.close()

            # Initialize task and enqueue (thread-safe via task_queue)
            task_info = {
                "status": "pending", "progress": 0, "total": len(final_chunks),
                "current": 0, "audio_url": None, "error": None, "duration": 0,
                "chunks_config": final_chunks, "global_voice": voice,
                "global_instruct": instruct, "speed": speed, "fmt": fmt,
                "api_base": self.api_base, "queue_pos": 0,
            }
            queue_pos = task_queue.enqueue_task(task_id, task_info)

            self._send_json(200, {"task_id": task_id, "queue_pos": queue_pos})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Resume ──────────────────────
    def _get_resumable(self):
        """Check if there's a resumable failed task."""
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            conn = database.db_conn()
            row = conn.execute(
                "SELECT id, chunks_config FROM history WHERE status='error' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()

            if not row:
                self._send_json(200, {"task_id": None})
                return

            task_id = row["id"]
            try:
                chunks = json.loads(row["chunks_config"]) if row["chunks_config"] else []
                total = len(chunks) if chunks else 0
            except (json.JSONDecodeError, TypeError):
                total = 0

            # Count existing valid chunk files
            completed = 0
            for f in config.AUDIO_DIR.iterdir():
                if f.name.startswith(task_id + "_chunk_"):
                    if f.stat().st_size > 44:
                        completed += 1

            self._send_json(200, {
                "task_id": task_id,
                "completed": completed,
                "total": total,
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _do_resume(self):
        """Resume a failed task."""
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            conn = database.db_conn()
            row = conn.execute(
                "SELECT id, voice, instruct, speed, fmt, chunks_config FROM history WHERE status='error' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()

            if not row:
                self._send_json(404, {"error": "无可恢复任务"})
                return

            task_id = row["id"]
            chunks_config = json.loads(row["chunks_config"]) if row["chunks_config"] else []
            voice = row["voice"]
            instruct = row["instruct"]
            speed = row["speed"]
            fmt = row["fmt"]

            # Re-initialize task
            task_info = {
                "status": "pending", "progress": 0, "total": len(chunks_config),
                "current": 0, "audio_url": None, "error": None, "duration": 0,
                "chunks_config": chunks_config, "global_voice": voice,
                "global_instruct": instruct, "speed": speed, "fmt": fmt,
                "api_base": self.api_base, "queue_pos": 0,
            }

            # Update DB status
            conn = database.db_conn()
            conn.execute("UPDATE history SET status='pending' WHERE id=?", (task_id,))
            conn.commit()
            conn.close()

            # Enqueue (thread-safe via task_queue)
            queue_pos = task_queue.enqueue_task(task_id, task_info)

            self._send_json(200, {"task_id": task_id, "queue_pos": queue_pos})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Task Status ─────────────────
    def _get_task(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        task_queue.cleanup_tasks()
        task_id = self.path.split("/")[-1].split("?")[0]
        task = task_queue.get_task(task_id)
        self._send_json(200, task)

    # ─── Model Info ──────────────────
    def _get_model(self):
        """Get current active model info."""
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            conn = database.db_conn()
            row = conn.execute("SELECT value FROM settings WHERE key='current_model'").fetchone()
            conn.close()
            current_key = row["value"] if row else "qwen3-tts-customvoice-1.7b-f16"
        except Exception:
            current_key = "qwen3-tts-customvoice-1.7b-f16"

        info = config.MODEL_REGISTRY.get(current_key, {})
        self._send_json(200, {
            "key": current_key,
            **info,
        })

    def _list_models(self):
        """List all available models."""
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        models = [{"key": k, **v} for k, v in config.MODEL_REGISTRY.items()]
        self._send_json(200, models)

    def _switch_model(self):
        """Switch to a different model."""
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            model_key = data.get("model", "")
            result = crispasr_mgmt.switch_model(model_key)
            self._send_json(200 if result["success"] else 400, result)
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── CrispASR Update ─────────────
    def _get_crispasr_version(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        current = crispasr_mgmt.get_crispasr_version()
        latest, tag = crispasr_mgmt.get_latest_crispasr_version()
        self._send_json(200, {"current": current, "latest": latest, "tag": tag})

    def _get_update_status(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        self._send_json(200, crispasr_mgmt.get_update_status())

    def _do_crispasr_update(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        # H6: Set running=True atomically to prevent double-start
        started, message = crispasr_mgmt.start_update()
        if not started:
            self._send_json(409, {"error": message})
            return
        # Start update in background
        t = threading.Thread(target=crispasr_mgmt.update_crispasr, daemon=True)
        t.start()
        self._send_json(200, {"message": message})

    # ─── Server Status ────────────────
    def _get_status(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        queue_depth = task_queue.queue_depth()
        active_task = task_queue.has_active_task()
        self._send_json(200, status.get_status(queue_depth, active_task))

    # ─── Logs ─────────────────────────
    def _get_logs(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        qs = parse_qs(urlparse(self.path).query)
        lines = min(500, max(10, int(qs.get("lines", ["200"])[0])))
        q = qs.get("q", [""])[0].strip()
        try:
            cmd = ["journalctl", "-u", "crispasr", "-n", str(lines), "--no-pager", "--output=short-iso"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            output = result.stdout
            if q:
                output = "\n".join(line for line in output.splitlines() if q.lower() in line.lower())
            self._send_json(200, {"logs": output, "lines": lines})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Presets ───────────────────────
    def _list_presets(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        conn = database.db_conn()
        rows = conn.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'preset:%' ORDER BY key"
        ).fetchall()
        conn.close()
        presets = []
        for row in rows:
            name = row["key"].replace("preset:", "", 1)
            try:
                data = json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                data = {}
            presets.append({"name": name, **data})
        self._send_json(200, presets)

    def _save_preset(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            name = data.get("name", "").strip()
            if not name:
                self._send_json(400, {"error": "预设名称不能为空"}); return
            safe_name = re.sub(r'[^a-zA-Z0-9_\-\u4e00-\u9fff]', '_', name)[:64]
            preset_data = {
                "voice": data.get("voice", "serena"),
                "instruct": data.get("instruct", ""),
                "speed": data.get("speed", 1.0),
                "fmt": data.get("fmt", "wav"),
            }
            conn = database.db_conn()
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (f"preset:{safe_name}", json.dumps(preset_data, ensure_ascii=False)),
            )
            conn.commit()
            conn.close()
            self._send_json(200, {"name": safe_name, **preset_data})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _delete_preset(self, name: str):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        conn = database.db_conn()
        conn.execute("DELETE FROM settings WHERE key=?", (f"preset:{name}",))
        conn.commit()
        conn.close()
        self._send_json(200, {"ok": True})

    # ─── Voice Compare ────────────────
    def _compare_voices(self):
        """Submit two TTS tasks with different voices for A/B comparison."""
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            text = data.get("text", "").strip()
            voice_a = data.get("voice_a", "serena")
            voice_b = data.get("voice_b", "")
            if not text:
                self._send_json(400, {"error": "文本不能为空"}); return
            if not voice_b:
                self._send_json(400, {"error": "请选择两个音色"}); return
            speed = data.get("speed", 1.0)
            fmt = data.get("fmt", "wav")
            instruct = data.get("instruct", "")

            results = []
            for voice in (voice_a, voice_b):
                task_id = uuid.uuid4().hex[:12]
                final_chunks = [{"text": text, "voice": voice, "instruct": instruct}]
                # Write to DB
                conn = database.db_conn()
                conn.execute(
                    "INSERT INTO history (id,text,voice,instruct,speed,fmt,status,chunks_config,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (task_id, text[:2000], voice, instruct, speed, fmt, "pending",
                     json.dumps(final_chunks, ensure_ascii=False), time.time()),
                )
                conn.commit()
                conn.close()
                # Build complete task_info matching _do_generate structure
                task_info = {
                    "status": "pending", "progress": 0, "total": 1,
                    "current": 0, "audio_url": None, "error": None, "duration": 0,
                    "chunks_config": final_chunks, "global_voice": voice,
                    "global_instruct": instruct, "speed": speed, "fmt": fmt,
                    "api_base": self.api_base, "queue_pos": 0,
                }
                task_queue.enqueue_task(task_id, task_info)
                results.append(task_id)

            self._send_json(200, {"task_a": results[0], "task_b": results[1]})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Batch Synthesize ─────────────
    def _batch_synthesize(self):
        """Submit multiple TTS tasks at once."""
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            texts = data.get("texts", [])
            if not texts or not isinstance(texts, list):
                self._send_json(400, {"error": "texts必须是非空数组"}); return
            if len(texts) > 20:
                self._send_json(400, {"error": "单次最多20条"}); return
            voice = data.get("voice", "serena")
            speed = data.get("speed", 1.0)
            fmt = data.get("fmt", "wav")
            instruct = data.get("instruct", "")
            task_ids = []
            for text in texts:
                text = str(text).strip()
                if not text:
                    continue
                task_id = uuid.uuid4().hex[:12]
                final_chunks = [{"text": text, "voice": voice, "instruct": instruct}]
                # Write to DB
                conn = database.db_conn()
                conn.execute(
                    "INSERT INTO history (id,text,voice,instruct,speed,fmt,status,chunks_config,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (task_id, text[:2000], voice, instruct, speed, fmt, "pending",
                     json.dumps(final_chunks, ensure_ascii=False), time.time()),
                )
                conn.commit()
                conn.close()
                # Build complete task_info matching _do_generate structure
                task_info = {
                    "status": "pending", "progress": 0, "total": 1,
                    "current": 0, "audio_url": None, "error": None, "duration": 0,
                    "chunks_config": final_chunks, "global_voice": voice,
                    "global_instruct": instruct, "speed": speed, "fmt": fmt,
                    "api_base": self.api_base, "queue_pos": 0,
                }
                task_queue.enqueue_task(task_id, task_info)
                task_ids.append(task_id)
            self._send_json(200, {"task_ids": task_ids, "count": len(task_ids)})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── History ─────────────────────
    def _get_history(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        qs = parse_qs(urlparse(self.path).query)
        page = max(1, int(qs.get("page", ["1"])[0]))
        per_page = min(100, max(1, int(qs.get("per_page", ["20"])[0])))
        q = qs.get("q", [""])[0].strip()
        offset = (page - 1) * per_page

        conn = database.db_conn()
        where = ""
        params: list = []
        if q:
            where = "WHERE text LIKE ?"
            params.append(f"%{q}%")

        total = conn.execute(f"SELECT COUNT(*) FROM history {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT id,text,voice,instruct,speed,fmt,audio_file,duration,status,created_at "
            f"FROM history {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()
        conn.close()
        self._send_json(200, {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        })

    def _delete_history_item(self, task_id: str):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        conn = database.db_conn()
        row = conn.execute("SELECT audio_file FROM history WHERE id=?", (task_id,)).fetchone()
        if not row:
            conn.close()
            self._send_json(404, {"error": "记录不存在"})
            return
        if row["audio_file"]:
            f = config.AUDIO_DIR / row["audio_file"]
            if f.exists():
                try: f.unlink()
                except: pass
        conn.execute("DELETE FROM history WHERE id=?", (task_id,))
        conn.commit()
        conn.close()
        self._send_json(200, {"ok": True})

    def _batch_delete_history(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            data = json.loads(self._read_body())
            ids = data.get("ids", [])
            if not ids:
                self._send_json(400, {"error": "无指定ID"}); return
            conn = database.db_conn()
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT audio_file FROM history WHERE id IN ({placeholders})", ids
            ).fetchall()
            for row in rows:
                if row["audio_file"]:
                    f = config.AUDIO_DIR / row["audio_file"]
                    if f.exists():
                        try: f.unlink()
                        except: pass
            conn.execute(f"DELETE FROM history WHERE id IN ({placeholders})", ids)
            conn.commit()
            conn.close()
            self._send_json(200, {"ok": True, "deleted": len(ids)})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _delete_history(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        # M1: Only delete audio files referenced in history, not all files
        conn = database.db_conn()
        rows = conn.execute("SELECT audio_file FROM history WHERE audio_file IS NOT NULL").fetchall()
        for row in rows:
            f = config.AUDIO_DIR / row["audio_file"]
            if f.exists():
                try: f.unlink()
                except: pass
        conn.execute("DELETE FROM history")
        conn.commit()
        conn.close()
        self._send_json(200, {"ok": True})

    # ─── Audio File Serving ──────────
    def _serve_audio(self):
        authed = self._check_auth()
        if not authed:
            qs = parse_qs(urlparse(self.path).query)
            token = qs.get("token", [""])[0]
            if token and auth.jwt_decode(token):
                authed = True
        if not authed:
            self.send_error(401)
            return

        filename = self.path.split("/")[-1].split("?")[0]
        # Strict filename validation: no path separators, no dots prefix
        if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
            self.send_error(400)
            return
        filepath = config.AUDIO_DIR / filename
        # Resolve symlinks and verify it stays within AUDIO_DIR
        try:
            real_path = filepath.resolve(strict=True)
            real_dir = config.AUDIO_DIR.resolve()
            if not str(real_path).startswith(str(real_dir) + os.sep) and real_path != real_dir:
                self.send_error(403)
                return
        except (FileNotFoundError, RuntimeError):
            self.send_error(404)
            return

        if not real_path.exists():
            self.send_error(404)
            return

        # M2: Stream audio instead of reading entire file into memory
        file_size = real_path.stat().st_size
        ext = filepath.suffix.lower()
        ct = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", file_size)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        with open(real_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def _serve_upload(self):
        """Serve uploaded reference audio files (auth via header or ?token=)."""
        authed = self._check_auth()
        if not authed:
            qs = parse_qs(urlparse(self.path).query)
            token = qs.get("token", [""])[0]
            if token and auth.jwt_decode(token):
                authed = True
        if not authed:
            self.send_error(401); return
        filename = unquote(self.path.split("/")[-1].split("?")[0])
        if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
            self.send_error(400); return
        filepath = config.UPLOAD_DIR / filename
        try:
            real_path = filepath.resolve(strict=True)
            real_dir = config.UPLOAD_DIR.resolve()
            if not str(real_path).startswith(str(real_dir) + os.sep) and real_path != real_dir:
                self.send_error(403); return
        except (FileNotFoundError, RuntimeError):
            self.send_error(404); return
        if not real_path.exists():
            self.send_error(404); return
        file_size = real_path.stat().st_size
        ext = filepath.suffix.lower()
        ct = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".webm": "audio/webm"}.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", file_size)
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        with open(real_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    # ─── Voice Clone ─────────────────
    def _upload_voice(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return

        try:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._send_json(400, {"error": "需要multipart上传"}); return

            boundary = content_type.split("boundary=")[-1].encode()
            body = self._read_body()

            # C2: Limit upload size (10 MB)
            if len(body) > config.MAX_UPLOAD_SIZE:
                self._send_json(413, {"error": "文件过大，最大10MB"}); return

            parts = body.split(b"--" + boundary)
            audio_data = b""
            voice_name = ""

            for part in parts:
                if b"Content-Disposition" not in part:
                    continue
                header_end = part.find(b"\r\n\r\n")
                if header_end < 0:
                    continue
                header = part[:header_end].decode("utf-8", errors="ignore")
                part_data = part[header_end+4:]
                if part_data.endswith(b"\r\n"):
                    part_data = part_data[:-2]

                if 'name="audio"' in header:
                    audio_data = part_data
                elif 'name="name"' in header:
                    voice_name = part_data.decode("utf-8", errors="ignore").strip()

            if not audio_data:
                self._send_json(400, {"error": "未找到音频文件"}); return
            if not voice_name:
                voice_name = f"custom_{int(time.time())}"

            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', voice_name)[:64]
            upload_path = config.UPLOAD_DIR / f"{safe_name}.wav"
            with open(upload_path, "wb") as f:
                f.write(audio_data)

            # Copy to CrispASR voices directory
            crispasr_voices = config.CRISPASR_DIR / "voices"
            crispasr_voices.mkdir(parents=True, exist_ok=True)
            shutil.copy2(upload_path, crispasr_voices / f"{safe_name}.wav")

            conn = database.db_conn()
            conn.execute("INSERT OR REPLACE INTO voices (name, filename, created_at) VALUES (?,?,?)",
                         (safe_name, f"{safe_name}.wav", time.time()))
            conn.commit()
            conn.close()

            self._send_json(200, {"name": safe_name, "filename": f"{safe_name}.wav"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _list_voices(self):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        conn = database.db_conn()
        rows = conn.execute("SELECT name, filename, created_at FROM voices ORDER BY created_at DESC").fetchall()
        conn.close()
        items = []
        for row in rows:
            item = dict(row)
            # Add duration
            fpath = config.UPLOAD_DIR / row["filename"]
            if fpath.exists():
                try:
                    item["duration"] = round(audio_utils.wav_duration(str(fpath)), 1)
                except Exception:
                    item["duration"] = 0
            else:
                item["duration"] = 0
            items.append(item)
        self._send_json(200, items)

    def _delete_voice(self, name: str):
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        conn = database.db_conn()
        row = conn.execute("SELECT filename FROM voices WHERE name=?", (name,)).fetchone()
        if not row:
            conn.close()
            self._send_json(404, {"error": "参考音频不存在"})
            return
        filename = row["filename"]
        # Delete from uploads
        upload_path = config.UPLOAD_DIR / filename
        if upload_path.exists():
            try: upload_path.unlink()
            except: pass
        # Delete from CrispASR voices dir
        crispasr_voice = config.CRISPASR_DIR / "voices" / filename
        if crispasr_voice.exists():
            try: crispasr_voice.unlink()
            except: pass
        conn.execute("DELETE FROM voices WHERE name=?", (name,))
        conn.commit()
        conn.close()
        self._send_json(200, {"ok": True})

    # ─── API Proxy ───────────────────
    def _proxy_api(self):
        # C3: Require auth for API proxy
        if not self._check_auth():
            self._send_json(401, {"error": "未登录"}); return
        try:
            body = self._read_body()
            url = f"{self.api_base}{self.path}"
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
            )
            with urllib.request.urlopen(req, timeout=1800) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", resp.headers.get("Content-Type", "audio/wav"))
            self.send_header("Content-Length", len(data))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, fmt, *args):
        if "/api/" in str(args) or "/v1/" in str(args):
            super().log_message(fmt, *args)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
