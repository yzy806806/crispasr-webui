"""CrispASR TTS Web UI v0.9 — Configuration.

Bottom-level module; no imports from other project modules.

Usage:
    Call ``config.init(data_dir, crispasr_dir, jwt_secret)`` at startup.
    Access settings via ``config.cfg.<attr>`` (e.g. ``config.cfg.DATA_DIR``).
"""

import os
from dataclasses import dataclass
from pathlib import Path


# ─── Immutable Configuration ─────────────────────────────

@dataclass(frozen=True)
class AppConfig:
    """Frozen configuration — built once at startup, never mutated."""
    DATA_DIR: Path
    DB_PATH: Path
    AUDIO_DIR: Path
    UPLOAD_DIR: Path
    CRISPASR_DIR: Path
    JWT_SECRET: str
    JWT_EXPIRY: int = 86400 * 7          # 7 days
    MAX_BODY: int = 10 * 1024 * 1024     # 10 MB request body
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB voice upload


# ─── Singleton ────────────────────────────────────────────

cfg: AppConfig | None = None


def init(data_dir: str | Path = "",
         crispasr_dir: str | Path = "",
         jwt_secret: str = "") -> AppConfig:
    """Build and store the frozen config. Call once at startup."""
    global cfg

    _crispasr_default = os.environ.get(
        "CRISPASR_DIR",
        str(Path(__file__).parent.parent),
    )
    _data_dir = Path(data_dir) if data_dir else (
        Path(os.environ.get("CRISPASR_DATA_DIR", ""))
        or Path(__file__).parent.parent / "tts_data"
    )
    _crispasr_dir = Path(crispasr_dir) if crispasr_dir else Path(_crispasr_default)
    _jwt_secret = jwt_secret or os.environ.get("JWT_SECRET", "")

    cfg = AppConfig(
        DATA_DIR=_data_dir,
        DB_PATH=_data_dir / "history.db",
        AUDIO_DIR=_data_dir / "audio",
        UPLOAD_DIR=_data_dir / "uploads",
        CRISPASR_DIR=_crispasr_dir,
        JWT_SECRET=_jwt_secret,
    )
    return cfg


# ─── Convenience accessors (used by server.py) ────────────
# These forward to cfg so server.py can call set_data_dir() etc.
# without knowing about init()'s full signature.

def set_data_dir(data_dir: str | Path) -> None:
    init(data_dir=data_dir,
         crispasr_dir=cfg.CRISPASR_DIR if cfg else "",
         jwt_secret=cfg.JWT_SECRET if cfg else "")

def set_crispasr_dir(crispasr_dir: str | Path) -> None:
    init(data_dir=cfg.DATA_DIR if cfg else "",
         crispasr_dir=crispasr_dir,
         jwt_secret=cfg.JWT_SECRET if cfg else "")

def set_jwt_secret(secret: str) -> None:
    init(data_dir=cfg.DATA_DIR if cfg else "",
         crispasr_dir=cfg.CRISPASR_DIR if cfg else "",
         jwt_secret=secret)


# ─── Module-level property access (config.DATA_DIR → cfg.DATA_DIR) ─

def __getattr__(name: str):
    """Transparently forward attribute access to the frozen config."""
    if cfg is not None and name in cfg.__dataclass_fields__:
        return getattr(cfg, name)
    raise AttributeError(f"module 'config' has no attribute {name!r}")


# ─── Model Registry ──────────────────────────────────────

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
        "voices": [],
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
