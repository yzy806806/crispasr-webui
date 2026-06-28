# CrispASR TTS Web UI

A lightweight web UI for [CrispASR](https://github.com/CrispStrobe/CrispASR) TTS — written in Go.

**Single binary, zero dependencies** (except ffmpeg and a CrispASR backend).

[中文文档](./README.md)

## Features

- 🔊 Text-to-speech with voice selection & style control
- 🎤 Voice cloning (upload or record reference audio)
- 📊 Batch synthesis & voice comparison
- 📜 History with search, pagination, batch delete
- 🔄 Model switching (7 backends: Qwen3-TTS, Kokoro, CosyVoice3, Chatterbox)
- 📈 System status monitoring (CPU / memory / disk / queue)
- 🔐 Password authentication with JWT
- ⚡ CrispASR auto start/stop — starts on demand, stops when idle to save memory
- 📦 Single static binary — no Python, no pip, no venv
- 🔄 Resumable tasks & one-click CrispASR install & update

## Quick Start

### One-click Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```

> ⚠️ **Must run as root** (needs to write systemd units, install to /opt, write /etc config).

The installer will:
1. Detect CPU arch & GPU (CUDA / Vulkan / CPU)
2. Download the latest CrispASR binary
3. Build the WebUI Go binary (requires Go 1.22+, auto-installed)
4. Configure systemd services (CrispASR + WebUI), enabled on boot
5. Start all services (default password `12345678`, change in Web UI Settings)

### Password

**Default password: `12345678`**, automatically written to the SQLite database on first startup. The password is never stored in env files or systemd EnvironmentFile.

After installation, the terminal shows:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🎙️  CrispASR TTS Web UI is ready!

  URL:      http://10.0.0.25:8888
  Password: 12345678 (default, change in Settings)

  Services:  systemctl status crispasr crispasr-webui
  Logs:      journalctl -u crispasr-webui -f
  Uninstall: systemctl stop crispasr crispasr-webui && rm -rf /opt/crispasr /var/lib/crispasr-webui
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

The password is stored in the SQLite database (`/var/lib/crispasr-webui/tts.db`, `settings` table) as a bcrypt hash.

**Change password:** Click the user icon in the top-right corner → Change Password. Changes take effect immediately and persist across restarts.

**Forgot password?** Delete the password record from the database, then restart — it will reset to the default `12345678`:

```bash
sudo systemctl stop crispasr-webui
sqlite3 /var/lib/crispasr-webui/tts.db "DELETE FROM settings WHERE key='password';"
sudo systemctl start crispasr-webui
```

### Compatibility

| OS | Support | Notes |
|----|---------|-------|
| Ubuntu 20.04+ | ✅ | Fully supported |
| Debian 11+ | ✅ | Fully supported, zero Python dependency |
| CentOS / RHEL 8+ | ⚠️ | Needs manual curl/git install; systemd available |
| macOS | ⚠️ | Manual start (no systemd), script can compile |
| Other Linux | ⚠️ | Needs systemd + curl + git + bash |

> 💡 The installer uses only POSIX-standard tools (`grep -oE`, `od`, `sed`) — no Python needed. Debian minimal install works out of the box.

### Custom Install Options

```bash
# Custom install dir, CUDA, specific model
sudo INSTALL_DIR=/opt/my-tts GPU_BACKEND=cuda MODEL=qwen3-tts-customvoice-0.6b-q8 bash install.sh
```

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTALL_DIR` | `/opt/crispasr` | Install directory |
| `DATA_DIR` | `/var/lib/crispasr-webui` | Data directory (history, audio) |
| `WEBUI_PORT` | `8888` | WebUI listen port |
| `CRISPASR_PORT` | `8080` | CrispASR service port |
| `GPU_BACKEND` | `auto` | GPU mode: `auto`, `cpu`, `cuda`, `vulkan` |
| `MODEL` | `qwen3-tts-customvoice-1.7b-f16` | Default TTS model |

### Manual Install

```bash
# Build
go build -o crispasr-webui .

# Run CrispASR server
/opt/crispasr/bin/crispasr --server --backend qwen3-tts-customvoice \
  -m qwen3-tts-1.7b-customvoice --voice-dir /opt/crispasr/voices \
  --port 8080 &

# Run WebUI
CRISPASR_DIR=/opt/crispasr ./crispasr-webui
```

Open http://localhost:8888

## Performance

| Metric | Python (v0.9.3) | Go (v1.3.0) |
|--------|-----------------|-------------|
| Total lines | 3,895 | 1,486 |
| Backend files | 12 `.py` | 1 `.go` |
| Dependencies | Python 3.10+ | None (static binary) |
| Binary size | N/A (needs Python) | ~13 MB |
| Runtime memory | ~60 MB | **~10 MB** |
| Startup time | ~2s | **<100ms** |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CRISPASR_DIR` | `.` | CrispASR installation directory |
| `CRISPASR_DATA_DIR` | `./tts_data` | Data directory (DB, audio, uploads) |
| `TTS_PORT` | `8888` | HTTP port |
| `JWT_SECRET` | *(auto-generated & persisted)* | JWT signing key |
| `CRISPASR_AUTOSTART` | `1` | Auto start/stop CrispASR (`1`=on, `0`=off) |
| `CRISPASR_IDLE_TIMEOUT` | `300` | Seconds of idle before auto-stopping CrispASR (min 60) |
| `CRISPASR_PORT` | `8080` | CrispASR service port (for health checks) |

## Supported Platforms

CrispASR provides pre-built binaries for:

| Platform | Filename | Notes |
|----------|----------|-------|
| Linux x86_64 | `crispasr-linux-x86_64.tar.gz` | CPU only |
| Linux x86_64 + CUDA | `crispasr-linux-x86_64-cuda.tar.gz` | NVIDIA GPU |
| Linux x86_64 + Vulkan | `crispasr-linux-x86_64-vulkan.tar.gz` | AMD/Intel GPU |
| Linux ARM64 | `crispasr-linux-arm64.tar.gz` | Ampere Altra, Raspberry Pi 5 |
| macOS | `crispasr-macos.tar.gz` | Apple Silicon + Intel |

## FAQ

<details>
<summary><strong>Forgot password?</strong></summary>

Delete the password record from the database, then restart — it will reset to the default `12345678`:

```bash
sudo systemctl stop crispasr-webui
sqlite3 /var/lib/crispasr-webui/tts.db "DELETE FROM settings WHERE key='password';"
sudo systemctl start crispasr-webui
```
</details>

<details>
<summary><strong>How to uninstall?</strong></summary>

```bash
sudo systemctl stop crispasr crispasr-webui
sudo systemctl disable crispasr crispasr-webui
sudo rm /etc/systemd/system/crispasr.service /etc/systemd/system/crispasr-webui.service
sudo rm /etc/crispasr-webui.env
sudo rm -rf /opt/crispasr /var/lib/crispasr-webui
sudo systemctl daemon-reload
```
</details>

<details>
<summary><strong>How to view logs?</strong></summary>

```bash
# WebUI logs
journalctl -u crispasr-webui -f

# CrispASR service logs
journalctl -u crispasr -f
```
</details>

<details>
<summary><strong>Does it work on Debian?</strong></summary>

Yes. The installer has zero Python dependencies and uses only POSIX-standard tools. Debian 11+ minimal install works with just `curl` and `git`. If missing:

```bash
sudo apt update && sudo apt install -y curl git
```
</details>

<details>
<summary><strong>How to update?</strong></summary>

Re-run the installer — it automatically pulls the latest code and rebuilds:

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```

CrispASR engine install and updates are available via the "Install/Update" button in the Web UI. When not installed, the button shows "Install CrispASR x.x.x"; when installed, it shows "Update to x.x.x".
</details>

## License

MIT
