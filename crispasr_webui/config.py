#!/usr/bin/env python3
"""
CrispASR TTS Web UI v3 — Configuration
Bottom-level module; no imports from other project modules.
"""

import os
from pathlib import Path

# ─── Paths ──────────────────────────────────────────────
# Default values; may be overridden at runtime via set_data_dir() / set_crispasr_dir()
# When installed via install.sh, CRISPASR_DIR defaults to /opt/crispasr
# and DATA_DIR defaults to /var/lib/crispasr-webui

_CRISPASR_DIR_DEFAULT = os.environ.get(
    "CRISPASR_DIR",
    str(Path(__file__).parent.parent),  # fallback: parent of package dir
)
DATA_DIR: Path = Path(os.environ.get("CRISPASR_DATA_DIR", "")) or Path(__file__).parent.parent / "tts_data"
DB_PATH: Path = DATA_DIR / "history.db"
AUDIO_DIR: Path = DATA_DIR / "audio"
UPLOAD_DIR: Path = DATA_DIR / "uploads"
CRISPASR_DIR: Path = Path(_CRISPASR_DIR_DEFAULT)

# ─── Auth ───────────────────────────────────────────────
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
JWT_EXPIRY: int = 86400 * 7  # 7 days

# ─── Server limits ──────────────────────────────────────
MAX_BODY: int = 10 * 1024 * 1024       # 10 MB request body
MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024 # 10 MB voice upload


def set_data_dir(data_dir: str | Path) -> None:
    """Re-assign data path globals at runtime (called from main())."""
    global DATA_DIR, DB_PATH, AUDIO_DIR, UPLOAD_DIR
    DATA_DIR = Path(data_dir)
    DB_PATH = DATA_DIR / "history.db"
    AUDIO_DIR = DATA_DIR / "audio"
    UPLOAD_DIR = DATA_DIR / "uploads"


def set_crispasr_dir(crispasr_dir: str | Path) -> None:
    """Set CrispASR installation directory at runtime."""
    global CRISPASR_DIR
    CRISPASR_DIR = Path(crispasr_dir)


def set_jwt_secret(secret: str) -> None:
    global JWT_SECRET
    JWT_SECRET = secret


# ─── Model Registry ────────────────────────────────────
# Models that CrispASR supports for TTS
# Each model defines: backend, gguf patterns, built-in voices, capabilities
MODEL_REGISTRY: dict[str, dict] = {
    "qwen3-tts-customvoice-1.7b-f16": {
        "backend": "qwen3-tts-customvoice",
        "model_flag": "qwen3-tts-1.7b-customvoice",
        "voices": ["serena", "vivian", "sohee", "ono_anna", "aiden", "dylan", "eric", "ryan", "uncle_fu"],
        "has_instruct": True,
        "has_clone": True,
        "has_streaming": False,
        "description": "1.7B CustomVoice — 9 premium speakers + style control + voice cloning",
        "auto_dl": True,
    },
    "qwen3-tts-customvoice-0.6b-q8": {
        "backend": "qwen3-tts-customvoice",
        "model_flag": "qwen3-tts-0.6b-customvoice",
        "voices": ["serena", "vivian", "sohee", "ono_anna", "aiden", "dylan", "eric", "ryan", "uncle_fu"],
        "has_instruct": True,
        "has_clone": True,
        "has_streaming": False,
        "description": "0.6B CustomVoice Q8 — lighter, same 9 speakers",
        "auto_dl": True,
    },
    "qwen3-tts-base-1.7b": {
        "backend": "qwen3-tts",
        "model_flag": "qwen3-tts-1.7b-base",
        "voices": [],  # base uses WAV ref or baked default
        "has_instruct": False,
        "has_clone": True,
        "has_streaming": True,
        "description": "1.7B Base — streaming output, WAV clone",
        "auto_dl": True,
    },
    "qwen3-tts-voicedesign-1.7b": {
        "backend": "qwen3-tts-customvoice",
        "model_flag": "qwen3-tts-1.7b-voicedesign",
        "voices": [],
        "has_instruct": True,
        "has_clone": False,
        "has_streaming": False,
        "description": "1.7B VoiceDesign — describe voice in natural language via instruct",
        "auto_dl": True,
    },
    "kokoro": {
        "backend": "kokoro",
        "model_flag": "kokoro",
        "voices": ["af_bella", "af_nicole", "af_sarah", "af_sky", "am_adam", "am_michael"],
        "has_instruct": False,
        "has_clone": False,
        "has_streaming": False,
        "description": "Kokoro 82M — lightweight multilingual, style presets",
        "auto_dl": True,
    },
    "cosyvoice3-tts": {
        "backend": "cosyvoice3-tts",
        "model_flag": "cosyvoice3-tts",
        "voices": ["zero_shot", "fleurs-en", "fleurs-de", "fleurs-zh", "fleurs-ja", "fleurs-fr", "fleurs-es", "fleurs-ko"],
        "has_instruct": False,
        "has_clone": True,
        "has_streaming": False,
        "description": "CosyVoice3 0.5B — 9 languages + 18 Chinese dialects + WAV clone",
        "auto_dl": True,
    },
    "chatterbox": {
        "backend": "chatterbox",
        "model_flag": "chatterbox",
        "voices": ["default"],
        "has_instruct": False,
        "has_clone": True,
        "has_streaming": False,
        "description": "Chatterbox — 23 languages, emotion tags",
        "auto_dl": True,
    },
}
