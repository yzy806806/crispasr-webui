#!/usr/bin/env python3
"""
CrispASR TTS Web UI — Server Status
Reads system metrics: CPU, memory, disk, CrispASR process, queue depth.
No imports from other project modules except config (for paths).
"""

import os
import subprocess
import time

from . import config


def get_status(queue_depth: int = 0, active_task: bool = False) -> dict:
    """Collect system status metrics."""
    return {
        "crispasr": _crispasr_status(),
        "cpu": _cpu_usage(),
        "memory": _memory_usage(),
        "disk": _disk_usage(),
        "queue": {
            "depth": queue_depth,
            "active": active_task,
        },
        "timestamp": time.time(),
    }


def _crispasr_status() -> dict:
    """Check CrispASR service status."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "crispasr"],
            capture_output=True, text=True, timeout=5,
        )
        active = result.stdout.strip() == "active"
    except Exception:
        active = False

    # Try to get PID and uptime
    pid = None
    uptime = None
    try:
        result = subprocess.run(
            ["systemctl", "show", "crispasr", "--property=MainPID,ActiveEnterTimestamp"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            if line.startswith("MainPID="):
                pid_val = int(line.split("=", 1)[1])
                if pid_val > 0:
                    pid = pid_val
            elif line.startswith("ActiveEnterTimestamp="):
                ts_str = line.split("=", 1)[1]
                if ts_str:
                    # systemd timestamp format, just store as string
                    uptime = ts_str
    except Exception:
        pass

    return {
        "active": active,
        "pid": pid,
        "uptime": uptime,
    }


# ─── CPU usage (two /proc/stat samples) ─────────────────
_cpu_prev: tuple | None = None
_cpu_prev_time: float = 0

def _cpu_usage() -> dict:
    """Calculate CPU usage from /proc/stat delta."""
    global _cpu_prev, _cpu_prev_time
    try:
        vals = _read_proc_stat()
        now = time.monotonic()
        if _cpu_prev is None:
            # First call: store baseline, return 0 to avoid blocking
            _cpu_prev = vals
            _cpu_prev_time = now
            return {"percent": 0}

        d_idle = vals[0] - _cpu_prev[0]
        d_total = vals[1] - _cpu_prev[1]
        _cpu_prev = vals
        _cpu_prev_time = now

        pct = (1 - d_idle / d_total) * 100 if d_total > 0 else 0
        return {"percent": round(pct, 1)}
    except Exception:
        return {"percent": 0}


def _read_proc_stat() -> tuple:
    """Read idle and total from /proc/stat line 1."""
    with open("/proc/stat") as f:
        parts = f.readline().split()
    # user nice system idle iowait irq softirq steal guest guest_nice
    idle = int(parts[4]) + int(parts[5])  # idle + iowait
    total = sum(int(p) for p in parts[1:])
    return (idle, total)


def _memory_usage() -> dict:
    """Read memory info from /proc/meminfo."""
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(":")
                val = int(parts[1])  # in kB
                info[key] = val
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        used = total - available
        pct = (used / total * 100) if total > 0 else 0
        return {
            "total_mb": round(total / 1024),
            "used_mb": round(used / 1024),
            "available_mb": round(available / 1024),
            "percent": round(pct, 1),
        }
    except Exception:
        return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}


def _disk_usage() -> dict:
    """Get disk usage for audio directory."""
    try:
        # Audio dir size
        audio_size = 0
        audio_count = 0
        if config.AUDIO_DIR.exists():
            for f in config.AUDIO_DIR.iterdir():
                if f.is_file():
                    audio_size += f.stat().st_size
                    audio_count += 1

        # Partition usage for data dir
        stat = os.statvfs(config.DATA_DIR)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        pct = (used / total * 100) if total > 0 else 0

        return {
            "audio_files": audio_count,
            "audio_size_mb": round(audio_size / 1048576, 1),
            "disk_total_gb": round(total / 1073741824, 1),
            "disk_used_gb": round(used / 1073741824, 1),
            "disk_free_gb": round(free / 1073741824, 1),
            "disk_percent": round(pct, 1),
        }
    except Exception:
        return {"audio_files": 0, "audio_size_mb": 0, "disk_total_gb": 0, "disk_used_gb": 0, "disk_free_gb": 0, "disk_percent": 0}
