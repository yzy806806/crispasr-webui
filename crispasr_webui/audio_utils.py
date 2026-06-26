#!/usr/bin/env python3
"""
CrispASR TTS Web UI v0.9 — Audio Utilities
WAV duration, format conversion.
Imports: stdlib + config
"""

import subprocess
import wave

from . import config


def wav_duration(path: str) -> float:
    try:
        with wave.open(path, "r") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 0.0


def convert_audio(src_path: str, fmt: str) -> str | None:
    # L6: Validate fmt parameter
    if fmt not in ("wav", "mp3", "ogg"):
        return None
    if fmt == "wav":
        return src_path
    out_path = src_path.rsplit(".", 1)[0] + f".{fmt}"
    codec_map = {"mp3": "libmp3lame", "ogg": "libopus"}
    codec = codec_map.get(fmt, "copy")
    bitrate = "128k" if fmt == "mp3" else "64k"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-c:a", codec, "-b:a", bitrate, out_path],
            capture_output=True, timeout=60, check=True,
        )
        return out_path
    except Exception:
        return None
