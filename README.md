# CrispASR TTS Web UI

A lightweight web UI for CrispASR TTS — written in Go.

**Single binary, zero dependencies** (except ffmpeg and a CrispASR backend).

## Features

- 🔊 Text-to-speech with voice selection & style control
- 🎤 Voice cloning (upload or record reference audio)
- 📊 Batch synthesis & voice comparison
- 📜 History with search, pagination, batch delete
- 🔄 Model switching (7 backends: Qwen3-TTS, Kokoro, CosyVoice3, Chatterbox)
- 📈 System status monitoring (CPU / memory / disk / queue)
- 🔐 Password authentication with JWT
- 📦 Single static binary — no Python, no pip, no venv

## Quick Start

```bash
# Build
go build -o crispasr-webui .

# Run
export TTS_PASSWORD=your_password
export CRISPASR_DIR=/path/to/crispasr
./crispasr-webui
```

Open http://localhost:8888

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_PASSWORD` | *(required)* | Login password |
| `CRISPASR_DIR` | `.` | CrispASR installation directory |
| `CRISPASR_DATA_DIR` | `./tts_data` | Data directory (DB, audio, uploads) |
| `TTS_PORT` | `8888` | HTTP port |
| `JWT_SECRET` | *(auto-generated)* | JWT signing key |

## Architecture

```
main.go (1087 lines) — everything in one file:
  ├── Config & Model Registry
  ├── JWT Auth & Rate Limiting
  ├── SQLite Database
  ├── Task Queue (goroutine + sync.Cond)
  ├── API Handlers (20 endpoints)
  ├── Text Splitter
  └── WAV Concatenation
```

**Compare with Python version (v0.9.3):**

| Metric | Python | Go |
|--------|--------|----|
| Total lines | 3,895 | 1,087 |
| Backend files | 12 `.py` | 1 `.go` |
| Dependencies | Python 3.10+ | None (static binary) |
| Multipart upload | 57 lines hand-rolled | 3 lines stdlib |
| Range request | 81 lines manual | 0 lines (http.FileServer) |
| Route dispatch | 40 lines custom | 0 lines (http.ServeMux) |
| Task queue | threading.Lock + dict | goroutine + Cond |
| Binary size | N/A (needs Python) | ~14 MB |

## License

MIT
