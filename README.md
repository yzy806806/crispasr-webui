# CrispASR TTS Web UI

Web UI for [CrispASR](https://github.com/CrispStrobe/CrispASR) TTS server — voice cloning, multi-voice generation, text splitting, and one-click updates.

## Features

- 🎙️ **Multi-voice TTS** — 9 built-in voices + custom voice cloning
- 📝 **Text splitting** — Auto-split long text into sentences with inline voice/markup support
- 🔄 **Resume** — Failed generation can be resumed without re-doing completed chunks
- 🔄 **One-click update** — Pull latest CrispASR from GitHub, rebuild, and restart
- 🧪 **Audition** — Preview single chunks before full generation
- 🌐 **OpenAI-compatible proxy** — `/v1/audio/speech` endpoint for external tools
- 🔒 **Password auth** — JWT-based with rate limiting
- 📱 **Responsive UI** — Dark theme, mobile-friendly

## Quick Start

```bash
# Run with password
python3 -m crispasr_webui --password your_password --port 8888

# Or via environment variable
TTS_PASSWORD=your_password python3 -m crispasr_webui
```

Requires a running CrispASR server (default: `http://localhost:8080`).

## Architecture

```
crispasr_webui/
├── __init__.py         # Package init
├── __main__.py         # python -m entry point
├── config.py           # Paths, constants, model registry
├── auth.py             # JWT encode/decode
├── database.py         # SQLite init & connections
├── text_split.py       # Sentence splitting & inline markup
├── audio_utils.py      # WAV duration, format conversion
├── task_queue.py       # Task queue, generation worker
├── crispasr_mgmt.py    # Version check, update, model switch
├── templates.py        # HTML/CSS/JS frontend
├── handlers.py         # HTTP request handler
└── server.py           # Entry point & CLI args
```

**Zero external dependencies** — Python 3.10+ stdlib only.

## License

MIT
