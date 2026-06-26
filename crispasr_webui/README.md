# CrispASR WebUI

A modern, self-contained web interface for [CrispASR](https://github.com/CrispStrobe/CrispASR) TTS engine.

**Single-file deployment, zero external dependencies** — just Python 3.10+ and a running CrispASR server.

## Features

- 🔐 **Password-protected access** — JWT authentication with rate limiting
- 📝 **Long text auto-split** — automatic sentence segmentation for batch generation
- 🎭 **Per-sentence voice & style control** — inline markup syntax `[voice]{instruct}text`
- 📋 **Task queue** — submit multiple tasks, processed sequentially with position tracking
- ⏩ **Resume interrupted generation** — detects existing chunk files, skips completed segments
- 🔄 **Model switching** — switch between CrispASR models (restart required, ~10-20s)
- 🔄 **One-click CrispASR update** — pull latest source, build, and restart from the UI
- 🎤 **Voice cloning** — upload reference audio for custom voice
- 📊 **Generation history** — SQLite-backed with playback and download
- 🎵 **Audio format selection** — WAV (lossless), MP3, or OGG
- 🎧 **Single-chunk audition** — preview any sentence before full generation
- 📱 **Responsive design** — works on desktop and mobile

## Quick Start

### Prerequisites

- Python 3.10+
- [CrispASR](https://github.com/CrispStrobe/CrispASR) server running
- FFmpeg (optional, for MP3/OGG conversion)

### Install & Run

```bash
# Download
wget https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/tts_webui.py

# Run with password
python3 tts_webui.py --port 8888 --api http://localhost:8080 --password YOUR_PASSWORD

# Or use environment variable
TTS_PASSWORD=YOUR_PASSWORD python3 tts_webui.py --port 8888 --api http://localhost:8080
```

Open `http://localhost:8888` in your browser.

### Systemd Service (Recommended)

Create `/etc/tts-webui.env`:
```ini
TTS_PASSWORD=your_secure_password
```

Create `/etc/systemd/system/tts-webui.service`:
```ini
[Unit]
Description=CrispASR TTS Web UI
After=network.target crispasr.service
Requires=crispasr.service

[Service]
Type=simple
User=ubuntu
EnvironmentFile=/etc/tts-webui.env
ExecStart=/usr/bin/python3 /path/to/tts_webui.py --port 8888 --api http://localhost:8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tts-webui
```

## Usage

### Inline Markup Syntax

Control voice and style per-sentence directly in the text:

| Syntax | Effect |
|--------|--------|
| `[vivian]{温柔}你好啊` | Use voice "vivian" with instruct "温柔" |
| `[ryan]好的` | Change voice only, inherit global instruct |
| `{激动}太棒了！` | Change instruct only, inherit global voice |
| `普通文本` | Use global voice and instruct |

Priority: **Inline markup > Per-chunk UI config > Global config**

### Per-Chunk Configuration

1. Click **预览分句** to split text into chunks
2. Click ⚙️ on any chunk to expand per-chunk settings
3. Set voice and instruct for individual chunks
4. Click **▶ 试听** to audition a single chunk

### Task Queue

- Multiple generation requests are queued automatically
- Queue position is shown in the UI
- Tasks are processed sequentially (CrispASR handles one request at a time)

### Resume Generation

- If generation is interrupted, existing chunk files are preserved
- Click **恢复生成** to continue from where it left off

### Model Switching

1. Open **模型** panel
2. Click a model card to switch
3. CrispASR will restart (~10-20s)
4. Voice list updates automatically

### CrispASR Update

1. Open **更新** panel
2. Click **检查更新** to compare versions
3. Click **更新并编译** to pull latest source and rebuild

## Command Line Options

```
usage: tts_webui.py [-h] [--listen ADDR] [--port PORT] [--api URL] [--password PWD] [--data-dir DIR]

options:
  --listen ADDR    Listen address (default: 0.0.0.0)
  --port PORT      Listen port (default: 8888)
  --api URL        CrispASR API base URL (default: http://localhost:8080)
  --password PWD   Login password (or set TTS_PASSWORD env var)
  --data-dir DIR   Data directory for history, audio, uploads
```

## Architecture

```
tts_webui.py          # Single-file application (~2200 lines)
├── JWT Auth          # Hand-rolled HS256 (zero deps)
├── Text Splitting    # Sentence segmentation + inline markup parser
├── Task Queue        # In-memory queue with threading
├── CrispASR Client   # HTTP proxy to CrispASR /v1/audio/speech
├── Model Registry    # Static model config table
├── DB Layer          # SQLite for history, voices, settings
└── HTTP Server       # ThreadingMixIn + BaseHTTPRequestHandler
```

Data is stored in `./tts_data/`:
```
tts_data/
├── history.db    # SQLite database
├── audio/        # Generated audio files
└── uploads/      # Uploaded reference audio
```

## Supported Models

| Model | Voices | Instruct | Clone | Streaming |
|-------|--------|----------|-------|-----------|
| qwen3-tts-customvoice-1.7b-f16 | 9 | ✓ | ✓ | ✗ |
| qwen3-tts-customvoice-0.6b-q8 | 9 | ✓ | ✓ | ✗ |
| qwen3-tts-base-1.7b | — | ✗ | ✓ | ✓ |
| qwen3-tts-voicedesign-1.7b | — | ✓ | ✗ | ✗ |
| kokoro | 6 | ✗ | ✗ | ✗ |
| cosyvoice3-tts | 8 | ✗ | ✓ | ✗ |
| chatterbox | 1 | ✗ | ✓ | ✗ |

## License

MIT License — see [LICENSE](LICENSE)

## Author

Built by [Hermes](https://github.com/yzy806806) — an AI agent by Nous Research.
