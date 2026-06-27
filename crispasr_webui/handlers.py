"""HTTP request handlers for CrispASR TTS Web UI.

Routes are declared in the ROUTES table at the bottom of this file.
Each route maps (method, path_pattern) → handler method.
Path patterns ending with '*' match prefixes; others match exactly.
Routes with auth=True automatically reject unauthenticated requests.
"""

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

# MIME type map for static file serving
_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
}

# ─── WAV header minimum size ──────────────────────────────
_WAV_HEADER_MIN = 44


# ─── HTTP Handler ───────────────────────────────────────

class TTSHandler(BaseHTTPRequestHandler):
    api_base = "http://localhost:8080"
    password = ""

    # ─── Response helpers ──────────────
    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_binary(self, code, data, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
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

    def _require_auth(self) -> dict | None:
        """Check auth; if failed, send 401 and return None."""
        claims = self._check_auth()
        if not claims:
            self._send_json(401, {"error": "未登录"})
        return claims

    # ─── Dispatch ──────────────────────
    def _dispatch(self):
        """Route a request via the ROUTES table."""
        method = self.command
        path = self.path.split("?")[0]

        # Static files — no auth needed
        if path.startswith("/static/"):
            self._serve_static(path)
            return

        # Root page — special case (fast path)
        if path == "/" or path == "/index.html":
            self._send_binary(200, templates.HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return

        # Search route table
        for route_method, route_pattern, handler, auth_required in ROUTES:
            if route_method != method:
                continue

            if route_pattern.endswith("*"):
                # Prefix match
                prefix = route_pattern[:-1]
                if not path.startswith(prefix):
                    continue
                # Extract path parameter (everything after prefix, before query)
                param = path[len(prefix):]
                if auth_required and not self._require_auth():
                    return
                handler(self, param)
                return
            else:
                # Exact match
                if path != route_pattern:
                    continue
                if auth_required and not self._require_auth():
                    return
                handler(self)
                return

        self.send_error(404)

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def do_DELETE(self):
        self._dispatch()

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

    # ─── Auth Check ──────────────────
    def _api_check(self):
        if self._check_auth():
            self._send_json(200, {"ok": True})
        else:
            self._send_json(401, {"error": "未登录"})

    # ─── Split ───────────────────────
    def _do_split(self):
        try:
            data = json.loads(self._read_body())
            chunks = text_split.split_text(data["text"])
            self._send_json(200, {"chunks": chunks, "count": len(chunks)})
        except Exception as e:
            self._send_json(400, {"error": str(e)})

    # ─── Audition (single chunk) ─────
    def _do_audition(self):
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
        try:
            data = json.loads(self._read_body())
            text = data["text"]
            voice = data.get("voice", "serena")
            instruct = data.get("instruct", "")
            speed = data.get("speed", 1.0)
            fmt = data.get("fmt", "wav")
            chunks_config = data.get("chunks_config")

            if chunks_config and len(chunks_config) > 0:
                final_chunks = [
                    {"text": c.get("text", ""), "voice": c.get("voice", ""),
                     "instruct": c.get("instruct", "")}
                    for c in chunks_config
                ]
            else:
                final_chunks = text_split.split_text(text)

            task_id, queue_pos = _create_task(
                text, voice, instruct, speed, fmt, final_chunks, self.api_base
            )
            self._send_json(200, {"task_id": task_id, "queue_pos": queue_pos})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Resume ──────────────────────
    def _get_resumable(self):
        """Check if there's a resumable failed task."""
        try:
            with database.DBCtx() as conn:
                row = conn.execute(
                    "SELECT id, chunks_config FROM history WHERE status='error' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()

                if not row:
                    self._send_json(200, {"task_id": None})
                    return

                task_id = row["id"]
                try:
                    chunks = json.loads(row["chunks_config"]) if row["chunks_config"] else []
                    total = len(chunks) if chunks else 0
                except (json.JSONDecodeError, TypeError):
                    total = 0

                completed = 0
                for f in config.AUDIO_DIR.iterdir():
                    if f.name.startswith(task_id + "_chunk_"):
                        if f.stat().st_size > _WAV_HEADER_MIN:
                            completed += 1

                self._send_json(200, {"task_id": task_id, "completed": completed, "total": total})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _do_resume(self):
        """Resume a failed task."""
        try:
            with database.DBCtx() as conn:
                row = conn.execute(
                    "SELECT id, voice, instruct, speed, fmt, chunks_config FROM history WHERE status='error' ORDER BY created_at DESC LIMIT 1"
                ).fetchone()

                if not row:
                    self._send_json(404, {"error": "无可恢复任务"})
                    return

                task_id = row["id"]
                chunks_config = json.loads(row["chunks_config"]) if row["chunks_config"] else []
                voice = row["voice"]
                instruct = row["instruct"]
                speed = row["speed"]
                fmt = row["fmt"]

                conn.execute("UPDATE history SET status='pending' WHERE id=?", (task_id,))
                conn.commit()

            task_info = _build_task_info(chunks_config, voice, instruct, speed, fmt, self.api_base)
            queue_pos = task_queue.enqueue_task(task_id, task_info)
            self._send_json(200, {"task_id": task_id, "queue_pos": queue_pos})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Task Status ─────────────────
    def _get_task(self, task_id: str):
        task_queue.cleanup_tasks()
        task = task_queue.get_task(task_id)
        if not task or not task.get("status"):
            self._send_json(404, {"error": "任务不存在"})
            return
        self._send_json(200, task)

    # ─── Model Info ──────────────────
    def _get_model(self):
        """Get current active model info."""
        try:
            with database.DBCtx() as conn:
                row = conn.execute("SELECT value FROM settings WHERE key='current_model'").fetchone()
            current_key = row["value"] if row else "qwen3-tts-customvoice-1.7b-f16"
        except Exception:
            current_key = "qwen3-tts-customvoice-1.7b-f16"

        info = config.MODEL_REGISTRY.get(current_key, {})
        self._send_json(200, {"key": current_key, **info})

    def _list_models(self):
        """List all available models."""
        models = [{"key": k, **v} for k, v in config.MODEL_REGISTRY.items()]
        self._send_json(200, models)

    def _switch_model(self):
        """Switch to a different model."""
        try:
            data = json.loads(self._read_body())
            model_key = data.get("model", "")
            result = crispasr_mgmt.switch_model(model_key)
            self._send_json(200 if result["success"] else 400, result)
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── CrispASR Update ─────────────
    def _get_crispasr_version(self):
        current = crispasr_mgmt.get_crispasr_version()
        latest, tag = crispasr_mgmt.get_latest_crispasr_version()
        self._send_json(200, {"current": current, "latest": latest, "tag": tag})

    def _get_update_status(self):
        self._send_json(200, crispasr_mgmt.get_update_status())

    def _do_crispasr_update(self):
        # H6: Set running=True atomically to prevent double-start
        started, message = crispasr_mgmt.start_update()
        if not started:
            self._send_json(409, {"error": message})
            return
        t = threading.Thread(target=crispasr_mgmt.update_crispasr, daemon=True)
        t.start()
        self._send_json(200, {"message": message})

    # ─── Server Status ────────────────
    def _get_status(self):
        queue_depth = task_queue.queue_depth()
        active_task = task_queue.has_active_task()
        self._send_json(200, status.get_status(queue_depth, active_task))

    # ─── Logs ─────────────────────────
    def _get_logs(self):
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
        with database.DBCtx() as conn:
            rows = conn.execute(
                "SELECT key, value FROM settings WHERE key LIKE 'preset:%' ORDER BY key"
            ).fetchall()
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
        try:
            data = json.loads(self._read_body())
            name = data.get("name", "").strip()
            if not name:
                self._send_json(400, {"error": "预设名称不能为空"})
                return
            safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', name)[:64]
            preset_data = {
                "voice": data.get("voice", "serena"),
                "instruct": data.get("instruct", ""),
                "speed": data.get("speed", 1.0),
                "fmt": data.get("fmt", "wav"),
            }
            with database.DBCtx() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (f"preset:{safe_name}", json.dumps(preset_data, ensure_ascii=False)),
                )
                conn.commit()
            self._send_json(200, {"name": safe_name, **preset_data})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _delete_preset(self, name: str):
        with database.DBCtx() as conn:
            conn.execute("DELETE FROM settings WHERE key=?", (f"preset:{name}",))
            conn.commit()
        self._send_json(200, {"ok": True})

    # ─── Voice Compare ────────────────
    def _compare_voices(self):
        """Submit two TTS tasks with different voices for A/B comparison."""
        try:
            data = json.loads(self._read_body())
            text = data.get("text", "").strip()
            voice_a = data.get("voice_a", "serena")
            voice_b = data.get("voice_b", "")
            if not text:
                self._send_json(400, {"error": "文本不能为空"})
                return
            if not voice_b:
                self._send_json(400, {"error": "请选择两个音色"})
                return
            speed = data.get("speed", 1.0)
            fmt = data.get("fmt", "wav")
            instruct = data.get("instruct", "")

            results = []
            for voice in (voice_a, voice_b):
                chunks = [{"text": text, "voice": voice, "instruct": instruct}]
                task_id, _ = _create_task(text, voice, instruct, speed, fmt, chunks, self.api_base)
                results.append(task_id)

            self._send_json(200, {"task_a": results[0], "task_b": results[1]})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── Batch Synthesize ─────────────
    def _batch_synthesize(self):
        """Submit multiple TTS tasks at once."""
        try:
            data = json.loads(self._read_body())
            texts = data.get("texts", [])
            if not texts or not isinstance(texts, list):
                self._send_json(400, {"error": "texts必须是非空数组"})
                return
            if len(texts) > 20:
                self._send_json(400, {"error": "单次最多20条"})
                return
            voice = data.get("voice", "serena")
            speed = data.get("speed", 1.0)
            fmt = data.get("fmt", "wav")
            instruct = data.get("instruct", "")
            task_ids = []
            for t in texts:
                t = str(t).strip()
                if not t:
                    continue
                chunks = [{"text": t, "voice": voice, "instruct": instruct}]
                task_id, _ = _create_task(t, voice, instruct, speed, fmt, chunks, self.api_base)
                task_ids.append(task_id)
            self._send_json(200, {"task_ids": task_ids, "count": len(task_ids)})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    # ─── History ─────────────────────
    def _get_history(self):
        qs = parse_qs(urlparse(self.path).query)
        page = max(1, int(qs.get("page", ["1"])[0]))
        per_page = min(100, max(1, int(qs.get("per_page", ["20"])[0])))
        q = qs.get("q", [""])[0].strip()
        offset = (page - 1) * per_page

        with database.DBCtx() as conn:
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
        self._send_json(200, {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        })

    def _get_history_item(self, task_id: str):
        """Get a single history item by ID."""
        with database.DBCtx() as conn:
            row = conn.execute(
                "SELECT id,text,voice,instruct,speed,fmt,audio_file,duration,status,created_at FROM history WHERE id=?",
                (task_id,),
            ).fetchone()
        if not row:
            self._send_json(404, {"error": "记录不存在"})
            return
        self._send_json(200, dict(row))

    def _delete_history_item(self, task_id: str):
        with database.DBCtx() as conn:
            row = conn.execute("SELECT audio_file FROM history WHERE id=?", (task_id,)).fetchone()
            if not row:
                self._send_json(404, {"error": "记录不存在"})
                return
            if row["audio_file"]:
                _safe_unlink(config.AUDIO_DIR / row["audio_file"])
            conn.execute("DELETE FROM history WHERE id=?", (task_id,))
            conn.commit()
        self._send_json(200, {"ok": True})

    def _batch_delete_history(self):
        try:
            data = json.loads(self._read_body())
            ids = data.get("ids", [])
            if not ids:
                self._send_json(400, {"error": "无指定ID"})
                return
            with database.DBCtx() as conn:
                placeholders = ",".join("?" * len(ids))
                rows = conn.execute(
                    f"SELECT audio_file FROM history WHERE id IN ({placeholders})", ids
                ).fetchall()
                for row in rows:
                    if row["audio_file"]:
                        _safe_unlink(config.AUDIO_DIR / row["audio_file"])
                conn.execute(f"DELETE FROM history WHERE id IN ({placeholders})", ids)
                conn.commit()
            self._send_json(200, {"ok": True, "deleted": len(ids)})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _delete_history(self):
        with database.DBCtx() as conn:
            rows = conn.execute("SELECT audio_file FROM history WHERE audio_file IS NOT NULL").fetchall()
            for row in rows:
                _safe_unlink(config.AUDIO_DIR / row["audio_file"])
            conn.execute("DELETE FROM history")
            conn.commit()
        self._send_json(200, {"ok": True})

    # ─── Audio / Upload File Serving ──
    def _serve_audio(self, filename: str):
        self._serve_file(config.AUDIO_DIR, filename)

    def _serve_upload(self, filename: str):
        """Serve uploaded reference audio files (auth via header or ?token=)."""
        self._serve_file(config.UPLOAD_DIR, filename)

    def _serve_file(self, base_dir: Path, filename: str):
        """Serve a file from base_dir with auth check, path traversal protection, and Range support."""
        # Auth: header or ?token= query param
        authed = self._check_auth()
        if not authed:
            qs = parse_qs(urlparse(self.path).query)
            token = qs.get("token", [""])[0]
            if token and auth.jwt_decode(token):
                authed = True
        if not authed:
            self.send_error(401)
            return

        filename = unquote(filename)
        if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
            self.send_error(400)
            return
        filepath = base_dir / filename

        try:
            real_path = filepath.resolve(strict=True)
            real_dir = base_dir.resolve()
            if not str(real_path).startswith(str(real_dir) + os.sep) and real_path != real_dir:
                self.send_error(403)
                return
        except (FileNotFoundError, RuntimeError):
            self.send_error(404)
            return
        if not real_path.exists():
            self.send_error(404)
            return

        file_size = real_path.stat().st_size
        ext = filepath.suffix.lower()
        ct = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".webm": "audio/webm"}.get(ext, "application/octet-stream")

        # Range request support for audio seeking
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            try:
                range_spec = range_header[6:]
                if range_spec.startswith("-"):
                    suffix_len = int(range_spec[1:])
                    start = max(0, file_size - suffix_len)
                    end = file_size - 1
                else:
                    parts = range_spec.split("-")
                    start = int(parts[0]) if parts[0] else 0
                    end = int(parts[1]) if parts[1] else file_size - 1
                start = max(0, min(start, file_size - 1))
                end = max(start, min(end, file_size - 1))
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                with open(real_path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
            except (ValueError, OSError):
                pass

        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        with open(real_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    # ─── Static File Serving ──────────
    def _serve_static(self, url_path: str):
        """Serve a static file from templates.STATIC_DIR with caching."""
        rel = url_path[len("/static/"):]
        if not rel or "/" in rel or "\\" in rel or rel.startswith("."):
            self.send_error(400)
            return
        filepath = templates.STATIC_DIR / rel
        if not filepath.exists():
            self.send_error(404)
            return
        try:
            real = filepath.resolve(strict=True)
            base = templates.STATIC_DIR.resolve()
            if not str(real).startswith(str(base) + os.sep) and real != base:
                self.send_error(403)
                return
        except (FileNotFoundError, RuntimeError):
            self.send_error(404)
            return

        ext = filepath.suffix.lower()
        ct = _MIME_TYPES.get(ext, "application/octet-stream")
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    # ─── Voice Clone ─────────────────
    def _upload_voice(self):
        try:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._send_json(400, {"error": "需要multipart上传"})
                return

            boundary = content_type.split("boundary=")[-1].encode()
            body = self._read_body()

            if len(body) > config.MAX_UPLOAD_SIZE:
                self._send_json(413, {"error": "文件过大，最大10MB"})
                return

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
                self._send_json(400, {"error": "未找到音频文件"})
                return
            if not voice_name:
                voice_name = f"custom_{int(time.time())}"

            safe_name = re.sub(r'[^\w-]', '_', voice_name)[:64]
            upload_path = config.UPLOAD_DIR / f"{safe_name}.wav"
            with open(upload_path, "wb") as f:
                f.write(audio_data)

            # Copy to CrispASR voices directory
            crispasr_voices = config.CRISPASR_DIR / "voices"
            crispasr_voices.mkdir(parents=True, exist_ok=True)
            shutil.copy2(upload_path, crispasr_voices / f"{safe_name}.wav")

            with database.DBCtx() as conn:
                conn.execute("INSERT OR REPLACE INTO voices (name, filename, created_at) VALUES (?,?,?)",
                             (safe_name, f"{safe_name}.wav", time.time()))
                conn.commit()

            self._send_json(200, {"name": safe_name, "filename": f"{safe_name}.wav"})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _list_voices(self):
        with database.DBCtx() as conn:
            rows = conn.execute("SELECT name, filename, created_at FROM voices ORDER BY created_at DESC").fetchall()
        items = []
        for row in rows:
            item = dict(row)
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
        with database.DBCtx() as conn:
            row = conn.execute("SELECT filename FROM voices WHERE name=?", (name,)).fetchone()
            if not row:
                self._send_json(404, {"error": "参考音频不存在"})
                return
            filename = row["filename"]
            _safe_unlink(config.UPLOAD_DIR / filename)
            _safe_unlink(config.CRISPASR_DIR / "voices" / filename)
            conn.execute("DELETE FROM voices WHERE name=?", (name,))
            conn.commit()
        self._send_json(200, {"ok": True})

    # ─── API Proxy ───────────────────
    def _proxy_api(self, sub_path: str):
        try:
            body = self._read_body()
            url = f"{self.api_base}/v1/{sub_path}"
            req = urllib.request.Request(
                url, data=body, method="POST",
                headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
            )
            with urllib.request.urlopen(req, timeout=1800) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", resp.headers.get("Content-Type", "audio/wav"))
            self.send_header("Content-Length", str(len(data)))
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
        # Only log API requests (check self.path, not args)
        if "/api/" in self.path or "/v1/" in self.path:
            super().log_message(fmt, *args)


# ─── Helper functions (outside class) ──────────────────

def _safe_unlink(filepath: Path):
    """Delete a file, silently ignoring errors."""
    try:
        filepath.unlink()
    except OSError:
        pass


def _create_task(text, voice, instruct, speed, fmt, chunks, api_base):
    """Create a TTS task: insert into DB, enqueue, return (task_id, queue_pos)."""
    task_id = uuid.uuid4().hex[:12]

    with database.DBCtx() as conn:
        conn.execute(
            "INSERT INTO history (id,text,voice,instruct,speed,fmt,status,chunks_config,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (task_id, text[:2000], voice, instruct, speed, fmt, "pending",
             json.dumps(chunks, ensure_ascii=False), time.time()),
        )
        conn.commit()

    task_info = _build_task_info(chunks, voice, instruct, speed, fmt, api_base)
    queue_pos = task_queue.enqueue_task(task_id, task_info)
    return task_id, queue_pos


def _build_task_info(chunks, voice, instruct, speed, fmt, api_base):
    """Build the task_info dict for task_queue."""
    return {
        "status": "pending", "progress": 0, "total": len(chunks),
        "current": 0, "audio_url": None, "error": None, "duration": 0,
        "chunks_config": chunks, "global_voice": voice,
        "global_instruct": instruct, "speed": speed, "fmt": fmt,
        "api_base": api_base, "queue_pos": 0,
    }


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ─── Route Table ────────────────────────────────────────
# Format: (method, path_pattern, handler, auth_required)
# Pattern ending with '*' → prefix match; param = rest of path after prefix
# Other patterns → exact match
ROUTES = [
    # ─── Public (no auth) ────────────
    ("GET",    "/api/check",             TTSHandler._api_check,         False),
    ("POST",   "/api/login",             TTSHandler._do_login,         False),

    # ─── Auth-protected API ──────────
    ("GET",    "/api/model",             TTSHandler._get_model,        True),
    ("GET",    "/api/models",            TTSHandler._list_models,      True),
    ("GET",    "/api/status",            TTSHandler._get_status,       True),
    ("GET",    "/api/logs",              TTSHandler._get_logs,         True),
    ("GET",    "/api/presets",           TTSHandler._list_presets,     True),
    ("GET",    "/api/resumable",         TTSHandler._get_resumable,    True),
    ("GET",    "/api/voices",            TTSHandler._list_voices,      True),
    ("GET",    "/api/crispasr/version",  TTSHandler._get_crispasr_version, True),
    ("GET",    "/api/crispasr/update-status", TTSHandler._get_update_status, True),
    ("GET",    "/api/history",           TTSHandler._get_history,      True),
    ("GET",    "/api/task/*",            TTSHandler._get_task,         True),   # param = task_id
    ("GET",    "/api/history/*",         TTSHandler._get_history_item, True),   # param = task_id

    # Audio serving (auth via header or ?token=)
    ("GET",    "/api/audio/*",           TTSHandler._serve_audio,      False),  # auth handled internally
    ("GET",    "/uploads/*",             TTSHandler._serve_upload,     False),  # auth handled internally

    ("POST",   "/api/generate",          TTSHandler._do_generate,      True),
    ("POST",   "/api/split",             TTSHandler._do_split,         True),
    ("POST",   "/api/audition",          TTSHandler._do_audition,      True),
    ("POST",   "/api/voices",            TTSHandler._upload_voice,     True),
    ("POST",   "/api/model/switch",      TTSHandler._switch_model,     True),
    ("POST",   "/api/crispasr/update",   TTSHandler._do_crispasr_update, True),
    ("POST",   "/api/resume",            TTSHandler._do_resume,        True),
    ("POST",   "/api/history/batch",     TTSHandler._batch_delete_history, True),
    ("POST",   "/api/presets",           TTSHandler._save_preset,      True),
    ("POST",   "/api/compare",           TTSHandler._compare_voices,   True),
    ("POST",   "/api/batch",             TTSHandler._batch_synthesize, True),
    ("POST",   "/v1/*",                  TTSHandler._proxy_api,        True),   # param = sub_path

    ("DELETE", "/api/history",           TTSHandler._delete_history,   True),
    ("DELETE", "/api/history/batch",     TTSHandler._batch_delete_history, True),
    ("DELETE", "/api/history/*",         TTSHandler._delete_history_item, True),  # param = task_id
    ("DELETE", "/api/presets/*",         TTSHandler._delete_preset,    True),  # param = name
    ("DELETE", "/api/voices/*",          TTSHandler._delete_voice,     True),  # param = name
]
