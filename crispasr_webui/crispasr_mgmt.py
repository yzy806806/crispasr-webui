#!/usr/bin/env python3
"""
CrispASR TTS Web UI v3 — CrispASR Management
Version detection, update from GitHub, model switching.
Imports: config, database
"""

import json
import re
import subprocess
import threading
import time
import urllib.request

from . import config
from . import database


def get_latest_tag(src_dir) -> str:
    """Get the latest git tag from the CrispASR source repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(src_dir), "tag", "--sort=-v:refname"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if line.startswith("v") and re.match(r'v\d+\.\d+\.\d+', line):
                return line.strip()
    except Exception:
        pass
    return "main"  # fallback


def get_crispasr_version() -> str:
    """Get current CrispASR version."""
    try:
        binary = config.CRISPASR_DIR / "bin" / "crispasr"
        if not binary.exists():
            binary = config.CRISPASR_DIR / "crispasr"
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        for line in (result.stdout + result.stderr).splitlines():
            if "version" in line.lower():
                # Extract version number
                m = re.search(r'(\d+\.\d+\.\d+)', line)
                if m:
                    return m.group(1)
        return "unknown"
    except Exception:
        return "unknown"


def get_latest_crispasr_version() -> tuple[str, str]:
    """Check GitHub for latest CrispASR release. Returns (version, tag_name)."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/CrispStrobe/CrispASR/releases/latest",
            headers={"User-Agent": "CrispASR-WebUI"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("tag_name", "").lstrip("v"), data.get("tag_name", "")
    except Exception:
        return "", ""


_update_lock = threading.Lock()
_update_status: dict = {"running": False, "step": "", "log": ""}


def get_update_status() -> dict:
    """Get current update status (thread-safe copy)."""
    with _update_lock:
        return dict(_update_status)


def start_update() -> tuple[bool, str]:
    """Try to start an update. Returns (started, message).
    Thread-safe: acquires _update_lock internally.
    """
    with _update_lock:
        if _update_status.get("running"):
            return False, "更新正在进行中"
        _update_status["running"] = True
    return True, "更新已启动"


def update_crispasr(task_callback=None) -> dict:
    """Pull latest CrispASR source and rebuild. Returns {success, message}.
    Note: _update_status["running"] is set by the caller (_do_crispasr_update)."""
    global _update_status
    # Don't re-check running here — caller already set it and checked for duplicates
    _update_status = {"running": True, "step": "starting", "log": ""}

    try:
        build_dir = config.CRISPASR_DIR
        # Git repo is at parent of build dir; prefer that for git operations
        src_dir = build_dir.parent if (build_dir.parent / ".git").exists() else build_dir

        steps = [
            ("Checking source", ["git", "-C", str(src_dir), "fetch", "--tags"]),
            ("Resetting local changes", ["git", "-C", str(src_dir), "checkout", "--", "."]),
            ("Checking out latest", ["git", "-C", str(src_dir), "checkout", get_latest_tag(src_dir)]),
            ("Configuring", ["cmake", "-B", str(build_dir), "-S", str(src_dir),
                             "-DCMAKE_BUILD_TYPE=Release",
                             "-DGGML_CPU_ARM_ARCH=armv8.2-a",
                             "-DCMAKE_C_FLAGS=-march=armv8.2-a+dotprod+fp16",
                             "-DCMAKE_CXX_FLAGS=-march=armv8.2-a+dotprod+fp16"]),
            ("Building", ["cmake", "--build", str(build_dir), "--config", "Release", "-j2"]),
        ]

        log_lines = []
        for step_name, cmd in steps:
            _update_status["step"] = step_name
            log_lines.append(f"=== {step_name} ===")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            log_lines.append(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            if result.returncode != 0:
                log_lines.append(f"ERROR: {result.stderr[-500:]}")
                _update_status["log"] = "\n".join(log_lines)
                _update_status["running"] = False
                return {"success": False, "message": f"Failed at: {step_name}", "log": "\n".join(log_lines)}

        # Restart CrispASR service
        _update_status["step"] = "Restarting service"
        subprocess.run(["sudo", "systemctl", "restart", "crispasr"], capture_output=True, timeout=30)
        # Wait for CrispASR to come back up before checking version
        for _ in range(10):
            time.sleep(2)
            try:
                test_req = urllib.request.Request("http://localhost:8080/v1/models", method="GET")
                with urllib.request.urlopen(test_req, timeout=3):
                    break
            except:
                continue

        new_ver = get_crispasr_version()
        log_lines.append(f"Updated to {new_ver}")
        _update_status["log"] = "\n".join(log_lines)
        _update_status["running"] = False
        return {"success": True, "message": f"Updated to {new_ver}", "log": "\n".join(log_lines)}

    except Exception as e:
        _update_status["running"] = False
        _update_status["log"] = str(e)
        return {"success": False, "message": str(e)}


def switch_model(model_key: str) -> dict:
    """Switch CrispASR to a different model by restarting with new args."""
    if model_key not in config.MODEL_REGISTRY:
        return {"success": False, "message": f"Unknown model: {model_key}"}

    model_info = config.MODEL_REGISTRY[model_key]

    # Build new crispasr.service ExecStart
    binary = config.CRISPASR_DIR / "bin" / "crispasr"
    if not binary.exists():
        binary = config.CRISPASR_DIR / "crispasr"

    cmd_parts = [
        str(binary),
        "--server",
        "--backend", model_info["backend"],
        "-m", model_info["model_flag"],
        "--voice-dir", str(config.CRISPASR_DIR / "voices"),
        "--port", "8080",
        "--host", "127.0.0.1",
    ]

    exec_start = " ".join(cmd_parts)

    # Update systemd service
    service_path = "/etc/systemd/system/crispasr.service"
    try:
        # M10: Read file directly instead of shelling out to cat
        with open(service_path) as f:
            service_content = f.read()

        # Replace ExecStart line
        new_content = re.sub(
            r'ExecStart=.*',
            f'ExecStart={exec_start}',
            service_content,
        )

        # Write updated service file
        subprocess.run(
            ["sudo", "tee", service_path],
            input=new_content, capture_output=True, text=True, timeout=5,
        )
        subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, timeout=10)
        subprocess.run(["sudo", "systemctl", "restart", "crispasr"], capture_output=True, timeout=30)

        # Wait for service to come back up
        time.sleep(3)

        # Save current model to settings
        conn = database.db_conn()
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                     ("current_model", model_key))
        conn.commit()
        conn.close()

        return {"success": True, "message": f"Switched to {model_info['description']}", "model": model_key}

    except Exception as e:
        return {"success": False, "message": str(e)}
