"""CrispASR TTS Web UI v0.9 — Configuration.

Bottom-level module; no imports from other project modules.

Usage:
    - Before starting the server, call ``config.init(data_dir, crispasr_dir, jwt_secret)``
      to build the frozen AppConfig.
    - Access settings via ``config.cfg.<attr>`` (e.g. ``config.cfg.DATA_DIR``).
    - For backward compatibility, module-level attributes are also updated at init time.
"""

import os
from dataclasses import dataclass, field
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

    # ─── Backward-compatible module-level attributes ────
    # Code that does ``from config import DATA_DIR`` will still work
    # because we re-assign the module globals after init().
    import sys
    mod = sys.modules[__name__]
    mod.DATA_DIR = cfg.DATA_DIR
    mod.DB_PATH = cfg.DB_PATH
    mod.AUDIO_DIR = cfg.AUDIO_DIR
    mod.UPLOAD_DIR = cfg.UPLOAD_DIR
    mod.CRISPASR_DIR = cfg.CRISPASR_DIR
    mod.JWT_SECRET = cfg.JWT_SECRET
    mod.JWT_EXPIRY = cfg.JWT_EXPIRY
    mod.MAX_BODY = cfg.MAX_BODY
    mod.MAX_UPLOAD_SIZE = cfg.MAX_UPLOAD_SIZE

    return cfg


# ─── Default module-level values (used before init) ───────

DATA_DIR: Path = Path(os.environ.get("CRISPASR_DATA_DIR", "")) or Path(__file__).parent.parent / "tts_data"
DB_PATH: Path = DATA_DIR / "history.db"
AUDIO_DIR: Path = DATA_DIR / "audio"
UPLOAD_DIR: Path = DATA_DIR / "uploads"
CRISPASR_DIR: Path = Path(os.environ.get("CRISPASR_DIR", str(Path(__file__).parent.parent)))
JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
JWT_EXPIRY: int = 86400 * 7
MAX_BODY: int = 10 * 1024 * 1024
MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024


# ─── Backward-compatible setters (call init internally) ───

def set_data_dir(data_dir: str | Path) -> None:
    """Re-assign data paths. Calls init() to rebuild frozen config."""
    current = cfg or AppConfig(
        DATA_DIR=DATA_DIR, DB_PATH=DB_PATH, AUDIO_DIR=AUDIO_DIR,
        UPLOAD_DIR=UPLOAD_DIR, CRISPASR_DIR=CRISPASR_DIR, JWT_SECRET=JWT_SECRET,
    )
    init(data_dir=data_dir, crispasr_dir=current.CRISPASR_DIR, jwt_secret=current.JWT_SECRET)


def set_crispasr_dir(crispasr_dir: str | Path) -> None:
    """Set CrispASR directory. Calls init() to rebuild frozen config."""
    current = cfg or AppConfig(
        DATA_DIR=DATA_DIR, DB_PATH=DB_PATH, AUDIO_DIR=AUDIO_DIR,
        UPLOAD_DIR=UPLOAD_DIR, CRISPASR_DIR=CRISPASR_DIR, JWT_SECRET=JWT_SECRET,
    )
    init(data_dir=current.DATA_DIR, crispasr_dir=crispasr_dir, jwt_secret=current.JWT_SECRET)


def set_jwt_secret(secret: str) -> None:
    """Set JWT secret. Calls init() to rebuild frozen config."""
    current = cfg or AppConfig(
        DATA_DIR=DATA_DIR, DB_PATH=DB_PATH, AUDIO_DIR=AUDIO_DIR,
        UPLOAD_DIR=UPLOAD_DIR, CRISPASR_DIR=CRISPASR_DIR, JWT_SECRET=JWT_SECRET,
    )
    init(data_dir=current.DATA_DIR, crispasr_dir=current.CRISPASR_DIR, jwt_secret=secret)


# ─── Model Registry ──────────────────────────────────────
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
