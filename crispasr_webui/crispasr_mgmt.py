#!/usr/bin/env python3
"""
CrispASR TTS Web UI v0.9 — CrispASR Management
Version detection, update (download prebuilt binary), model switching.
Imports: config, database
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from . import config
from . import database

# ─── Platform detection ─────────────────────────────────────

def detect_crispasr_asset() -> str:
    """Return the CrispASR release asset name for the current platform.
    E.g. 'crispasr-linux-arm64.tar.gz', 'crispasr-linux-x86_64.tar.gz'
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize architecture
    if machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine in ("x86_64", "amd64"):
        arch = "x86_64"
    else:
        arch = machine

    # Check for CUDA (prefer if nvidia-smi works)
    gpu_suffix = ""
    if system == "linux" and arch == "x86_64":
        try:
            r = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
            if r.returncode == 0:
                gpu_suffix = "-cuda"
        except Exception:
            pass

    # Check for Vulkan on non-CUDA systems
    if not gpu_suffix and system == "linux" and arch == "x86_64":
        try:
            r = subprocess.run(["vulkaninfo"], capture_output=True, timeout=5)
            if r.returncode == 0:
                gpu_suffix = "-vulkan"
        except Exception:
            pass

    if system == "linux":
        return f"crispasr-linux-{arch}{gpu_suffix}.tar.gz"
    elif system == "darwin":
        return "crispasr-macos.tar.gz"
    elif system == "windows":
        return f"crispasr-windows-{arch}-cpu.zip"
    else:
        return f"crispasr-linux-{arch}.tar.gz"


def has_systemd() -> bool:
    """Check if systemd is available for service management."""
    try:
        return shutil.which("systemctl") is not None
    except Exception:
        return False


# ─── Version helpers ────────────────────────────────────────

def get_latest_tag(src_dir) -> str:
    """Get the latest git tag from a source directory (kept for backward compat)."""
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
    return "main"


def get_crispasr_version() -> str:
    """Get current CrispASR version by running the binary with --version."""
    try:
        binary = _find_crispasr_binary()
        if not binary:
            return "unknown"
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        for line in (result.stdout + result.stderr).splitlines():
            if "version" in line.lower():
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


def _find_crispasr_binary() -> Path | None:
    """Locate the crispasr binary: CRISPASR_DIR/bin/crispasr, CRISPASR_DIR/crispasr, or PATH."""
    # Check standard locations relative to CRISPASR_DIR
    for candidate in [
        config.CRISPASR_DIR / "bin" / "crispasr",
        config.CRISPASR_DIR / "crispasr",
    ]:
        if candidate.exists():
            return candidate
    # Check PATH
    found = shutil.which("crispasr")
    if found:
        return Path(found)
    return None


# ─── Update logic ───────────────────────────────────────────

_update_lock = threading.Lock()
_update_status: dict = {"running": False, "step": "", "log": ""}


def get_update_status() -> dict:
    """Get current update status (thread-safe copy)."""
    with _update_lock:
        return dict(_update_status)


def start_update() -> tuple[bool, str]:
    """Try to start an update. Returns (started, message)."""
    with _update_lock:
        if _update_status.get("running"):
            return False, "更新正在进行中"
        _update_status["running"] = True
    return True, "更新已启动"


def _restart_crispasr_service():
    """Restart CrispASR via systemd (if available) or signal-based restart."""
    if has_systemd():
        try:
            subprocess.run(["sudo", "systemctl", "restart", "crispasr"],
                           capture_output=True, timeout=30)
            return
        except Exception:
            pass
    # Fallback: try sending SIGHUP to crispasr process for graceful restart
    # This is a best-effort approach; users without systemd manage their own processes
    pass


def _wait_for_crispasr(port: int = 8080, timeout: int = 30):
    """Wait for CrispASR HTTP server to become ready."""
    for _ in range(timeout // 2):
        time.sleep(2)
        try:
            req = urllib.request.Request(f"http://localhost:{port}/v1/models", method="GET")
            with urllib.request.urlopen(req, timeout=3):
                return True
        except Exception:
            continue
    return False


def update_crispasr(task_callback=None) -> dict:
    """Download latest CrispASR prebuilt binary and install it.
    Returns {success, message, log}.
    """
    global _update_status
    _update_status = {"running": True, "step": "starting", "log": ""}
    log_lines = []

    try:
        # 1. Get latest version info
        _update_status["step"] = "Checking latest version"
        latest_ver, latest_tag = get_latest_crispasr_version()
        if not latest_ver:
            _update_status["running"] = False
            return {"success": False, "message": "Cannot fetch latest version from GitHub"}

        log_lines.append(f"Latest CrispASR: {latest_ver} ({latest_tag})")

        # 2. Determine the right asset for this platform
        asset_name = detect_crispasr_asset()
        download_url = (
            f"https://github.com/CrispStrobe/CrispASR/releases/download/"
            f"{latest_tag}/{asset_name}"
        )
        log_lines.append(f"Platform: {asset_name}")

        # 3. Download
        _update_status["step"] = f"Downloading {asset_name}"
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = Path(tmpdir) / asset_name
            try:
                urllib.request.urlretrieve(download_url, archive_path)
            except Exception as e:
                _update_status["running"] = False
                _update_status["log"] = "\n".join(log_lines + [f"Download failed: {e}"])
                return {"success": False, "message": f"Download failed: {e}"}

            archive_size = archive_path.stat().st_size
            log_lines.append(f"Downloaded {archive_size / 1e6:.1f} MB")

            # 4. Extract
            _update_status["step"] = "Extracting"
            extract_dir = Path(tmpdir) / "extract"
            extract_dir.mkdir()

            if asset_name.endswith(".tar.gz"):
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(extract_dir)
            elif asset_name.endswith(".zip"):
                import zipfile
                with zipfile.ZipFile(archive_path) as zf:
                    zf.extractall(extract_dir)

            # 5. Find the binary in the extracted directory
            new_binary = None
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    if f == "crispasr" or f == "crispasr.exe":
                        new_binary = Path(root) / f
                        break
                if new_binary:
                    break

            if not new_binary:
                _update_status["running"] = False
                return {"success": False, "message": "Cannot find crispasr binary in archive"}

            # 6. Install: copy to CRISPASR_DIR/bin/
            _update_status["step"] = "Installing"
            install_dir = config.CRISPASR_DIR / "bin"
            install_dir.mkdir(parents=True, exist_ok=True)
            dest = install_dir / "crispasr"

            # Backup old binary
            if dest.exists():
                backup = dest.with_name("crispasr.bak")
                shutil.copy2(dest, backup)

            shutil.copy2(new_binary, dest)
            dest.chmod(0o755)
            log_lines.append(f"Installed to {dest}")

            # Also copy crispasr-quantize if present
            for sibling in new_binary.parent.iterdir():
                if sibling.name.startswith("crispasr") and sibling != new_binary:
                    shutil.copy2(sibling, install_dir / sibling.name)
                    (install_dir / sibling.name).chmod(0o755)

        # 7. Restart CrispASR service
        _update_status["step"] = "Restarting service"
        _restart_crispasr_service()

        # 8. Wait for CrispASR to come back up
        _wait_for_crispasr()

        new_ver = get_crispasr_version()
        log_lines.append(f"Updated to {new_ver}")
        _update_status["log"] = "\n".join(log_lines)
        _update_status["running"] = False
        return {"success": True, "message": f"Updated to {new_ver}", "log": "\n".join(log_lines)}

    except Exception as e:
        _update_status["running"] = False
        _update_status["log"] = "\n".join(log_lines + [str(e)])
        return {"success": False, "message": str(e)}


# ─── Model switching ────────────────────────────────────────

def switch_model(model_key: str) -> dict:
    """Switch CrispASR to a different model by restarting with new args."""
    if model_key not in config.MODEL_REGISTRY:
        return {"success": False, "message": f"Unknown model: {model_key}"}

    model_info = config.MODEL_REGISTRY[model_key]

    binary = _find_crispasr_binary()
    if not binary:
        return {"success": False, "message": "CrispASR binary not found"}

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

    if has_systemd():
        service_path = "/etc/systemd/system/crispasr.service"
        try:
            with open(service_path) as f:
                service_content = f.read()

            new_content = re.sub(
                r'ExecStart=.*',
                f'ExecStart={exec_start}',
                service_content,
            )

            subprocess.run(
                ["sudo", "tee", service_path],
                input=new_content, capture_output=True, text=True, timeout=5,
            )
            subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, timeout=10)
            subprocess.run(["sudo", "systemctl", "restart", "crispasr"], capture_output=True, timeout=30)

            time.sleep(3)

            conn = database.db_conn()
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                         ("current_model", model_key))
            conn.commit()
            conn.close()

            return {"success": True, "message": f"Switched to {model_info['description']}", "model": model_key}
        except Exception as e:
            return {"success": False, "message": str(e)}
    else:
        return {"success": False, "message": "Model switching requires systemd. Please restart CrispASR manually with: " + exec_start}
