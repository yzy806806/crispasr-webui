# CrispASR TTS Web UI

A lightweight web UI for [CrispASR](https://github.com/CrispStrobe/CrispASR) TTS — written in Go.

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
- 🔄 Resumable tasks & one-click CrispASR updates

## Quick Start

### One-click Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | bash
```

The installer will:
1. Detect CPU arch & GPU (CUDA / Vulkan / CPU)
2. Download the latest CrispASR binary
3. Build the WebUI Go binary (requires Go 1.22+)
4. Configure systemd services (CrispASR + WebUI)
5. Interactively set a login password
6. Start all services

### Manual Install

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
| `JWT_SECRET` | *(auto-generated & persisted)* | JWT signing key |

## Performance

| Metric | Python (v0.9.3) | Go (v1.1.0) |
|--------|-----------------|-------------|
| Total lines | 3,895 | 1,486 |
| Backend files | 12 `.py` | 1 `.go` |
| Dependencies | Python 3.10+ | None (static binary) |
| Binary size | N/A (needs Python) | ~13 MB |
| Runtime memory | ~60 MB | **~10 MB** |
| Startup time | ~2s | **<100ms** |

## Architecture

```
main.go — everything in one file:
  ├── Config & Model Registry (7 backends)
  ├── JWT Auth (HMAC-SHA256, auto-persisted key)
  ├── SQLite Database + Task Queue (goroutine + sync.Cond)
  ├── API Handlers (27 endpoints)
  ├── Text Splitter (rune-safe, sentence-boundary)
  └── WAV Concatenation
```

## License

MIT
