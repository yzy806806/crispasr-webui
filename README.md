# CrispASR TTS Web UI

Web UI for [CrispASR](https://github.com/CrispStrobe/CrispASR) TTS server — voice cloning, multi-voice generation, text splitting, and one-click updates.

**Zero external dependencies** — Python 3.10+ stdlib only. No pip, no npm, no Docker required.

## Features

- 🎙️ **Multi-voice TTS** — 9 built-in voices + custom voice cloning
- 📝 **Text splitting** — Auto-split long text into sentences with inline voice/markup support
- 🔄 **Resume** — Failed generation can be resumed without re-doing completed chunks
- 🔄 **One-click update** — Download latest CrispASR binary from GitHub, auto-detect platform
- 🧪 **Audition** — Preview single chunks before full generation
- 🌐 **OpenAI-compatible proxy** — `/v1/audio/speech` endpoint for external tools
- 🔒 **Password auth** — JWT-based with rate limiting
- 📱 **Responsive UI** — Dark theme, mobile-friendly

## Quick Start

### One-click install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | bash
```

This will:
1. Detect your CPU architecture and GPU (CUDA/Vulkan/CPU)
2. Download the latest CrispASR binary
3. Install the WebUI from GitHub
4. Configure systemd services (CrispASR + WebUI)
5. Ask you to set a login password
6. Start everything up

### Custom install options

```bash
# Install to custom directory, use CUDA, select model
INSTALL_DIR=/opt/my-tts GPU_BACKEND=cuda MODEL=qwen3-tts-customvoice-0.6b-q8 bash install.sh

# Or set password via env (non-interactive)
TTS_PASSWORD=mypassword bash install.sh
```

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTALL_DIR` | `/opt/crispasr` | Installation directory |
| `DATA_DIR` | `/var/lib/crispasr-webui` | Data directory (history, audio) |
| `WEBUI_PORT` | `8888` | WebUI listen port |
| `CRISPASR_PORT` | `8080` | CrispASR server port |
| `GPU_BACKEND` | `auto` | GPU: `auto`, `cpu`, `cuda`, `vulkan` |
| `MODEL` | `qwen3-tts-customvoice-1.7b-f16` | Default TTS model |
| `TTS_PASSWORD` | *(interactive)* | Login password |

### Manual install (macOS / non-systemd Linux)

```bash
# 1. Download CrispASR for your platform
#    See: https://github.com/CrispStrobe/CrispASR/releases
curl -L -o crispasr.tar.gz https://github.com/CrispStrobe/CrispASR/releases/latest/download/crispasr-macos.tar.gz
mkdir -p /opt/crispasr/bin && tar xzf crispasr.tar.gz -C /opt/crispasr/bin --strip-components=1

# 2. Clone WebUI
git clone https://github.com/yzy806806/crispasr-webui.git /opt/crispasr/crispasr_webui

# 3. Start CrispASR server
/opt/crispasr/bin/crispasr --server --backend qwen3-tts-customvoice \
  -m qwen3-tts-1.7b-customvoice --voice-dir /opt/crispasr/voices \
  --port 8080 &

# 4. Start WebUI
TTS_PASSWORD=mypassword CRISPASR_DIR=/opt/crispasr \
  python3 -m crispasr_webui --port 8888 --api http://localhost:8080
```

## Supported Platforms

CrispASR provides prebuilt binaries for:

| Platform | Asset | Notes |
|----------|-------|-------|
| Linux ARM64 | `crispasr-linux-arm64.tar.gz` | Raspberry Pi 4/5, Oracle Cloud Ampere |
| Linux x86_64 | `crispasr-linux-x86_64.tar.gz` | Generic CPU (AVX2) |
| Linux x86_64 + CUDA | `crispasr-linux-x86_64-cuda.tar.gz` | NVIDIA GPU |
| Linux x86_64 + Vulkan | `crispasr-linux-x86_64-vulkan.tar.gz` | AMD/Intel GPU |
| macOS | `crispasr-macos.tar.gz` | Apple Silicon + Intel |
| Windows x86_64 | `crispasr-windows-x86_64-cpu.zip` | CPU only |

The WebUI is pure Python and runs on any platform with Python 3.10+.

## CLI Options

```
python3 -m crispasr_webui [OPTIONS]

  --listen ADDR       Listen address (default: 0.0.0.0)
  --port PORT         Listen port (default: 8888)
  --api URL           CrispASR API URL (default: http://localhost:8080)
  --password PASS     Login password (or set TTS_PASSWORD env)
  --data-dir PATH     Data directory (history, audio, uploads)
  --crispasr-dir PATH CrispASR installation directory
```

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

## Service Management

```bash
# Check status
systemctl status crispasr crispasr-webui

# View logs
journalctl -u crispasr-webui -f

# Restart
sudo systemctl restart crispasr-webui

# Stop
sudo systemctl stop crispasr crispasr-webui

# Uninstall
sudo systemctl stop crispasr crispasr-webui
sudo systemctl disable crispasr crispasr-webui
sudo rm -rf /opt/crispasr /var/lib/crispasr-webui /etc/crispasr-webui.env
sudo rm /etc/systemd/system/crispasr.service /etc/systemd/system/crispasr-webui.service
sudo systemctl daemon-reload
```

## License

MIT

---

**[中文文档](README_zh.md)**
