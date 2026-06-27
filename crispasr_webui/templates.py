"""HTML templates for CrispASR TTS Web UI.

Frontend assets are served as independent static files from the static/ directory:
  static/index.html  — page structure
  static/style.css   — styles
  static/app.js      — application logic

This module holds STATIC_DIR for the handler to serve static files,
and the HTML_PAGE content loaded lazily from index.html.
"""

from pathlib import Path

# Static files directory (sibling of this package's .py files)
STATIC_DIR: Path = Path(__file__).parent / "static"

# Pre-loaded HTML page content (populated on first access)
_CACHED_HTML: str | None = None


def _load_html() -> str:
    """Load and cache the index.html page."""
    global _CACHED_HTML
    if _CACHED_HTML is None:
        _CACHED_HTML = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return _CACHED_HTML


def reload_html() -> None:
    """Force reload HTML from disk (useful after updates)."""
    global _CACHED_HTML
    _CACHED_HTML = None


# Backward-compatible: handlers.py does `templates.HTML_PAGE`
# Use __getattr__ for module-level lazy attribute
def __getattr__(name: str):
    if name == "HTML_PAGE":
        return _load_html()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
