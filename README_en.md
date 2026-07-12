# CrispASR TTS Web UI

A lightweight web UI for [CrispASR](https://github.com/CrispStrobe/CrispASR) TTS — written in Go.

**Single binary, zero dependencies** (except a CrispASR backend).

[中文文档](./README.md)

## Features

- 🔊 Text-to-speech with voice selection & style control
- 🎤 Voice cloning (upload or record reference audio)
- 📊 Batch synthesis & voice comparison
- 🎵 MP3/WAV output with incremental ffmpeg transcoding
- 📦 Incremental audio write — peak memory ~11MB for 25k-char tasks
- 📜 History with search, pagination, batch delete
- 🧠 Model switching with quantization level selection, auto-download
- 📈 System status monitoring (CPU / memory / disk / queue)
- 🔐 Password authentication with JWT + bcrypt
- ⚡ CrispASR auto start/stop — starts on demand, stops when idle to save memory
- ⚙️ Settings panel — configure CrispASR path & port from WebUI
- 📦 Single static binary — no Python, no pip, no venv

## Quick Start

### One-click Install (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```

> ⚠️ **Must run as root** (needs to write systemd units, install to /opt, write /etc config).

The installer will:
1. Detect CPU architecture
2. Build the WebUI Go binary (requires Go 1.22+, auto-installed)
3. Configure systemd service, enabled on boot
4. Start WebUI (default password `12345678`)

> 📌 **CrispASR is NOT included in the installer.** Install [CrispASR](https://github.com/CrispStrobe/CrispASR) separately, then configure the binary path in WebUI → ⚙️ Settings.

### Install CrispASR

CrispASR provides pre-built binaries:

| Platform | Filename |
|----------|----------|
| Linux x86_64 | `crispasr-linux-x86_64.tar.gz` |
| Linux x86_64 + CUDA | `crispasr-linux-x86_64-cuda.tar.gz` |
| Linux x86_64 + Vulkan | `crispasr-linux-x86_64-vulkan.tar.gz` |
| Linux ARM64 | `crispasr-linux-arm64.tar.gz` |
| macOS | `crispasr-macos.tar.gz` |

```bash
# Download and extract
curl -fsSL -o /tmp/crispasr.tar.gz \
  https://github.com/CrispStrobe/CrispASR/releases/latest/download/crispasr-linux-x86_64.tar.gz
sudo mkdir -p /opt/crispasr/bin /opt/crispasr/lib
sudo tar xzf /tmp/crispasr.tar.gz -C /tmp/
sudo cp $(find /tmp -name crispasr -type f | head -1) /opt/crispasr/bin/crispasr
sudo find /tmp -name '*.so*' -type f -exec cp {} /opt/crispasr/lib/ \;
```

Then go to WebUI → ⚙️ Settings → set path to `/opt/crispasr/bin/crispasr`.

### Password

**Default password: `12345678`**, automatically written to the SQLite database on first startup.

Change password: click 🔑 Change Password in the sidebar. Forgot password:

```bash
sudo systemctl stop crispasr-webui
sqlite3 /var/lib/crispasr-webui/history.db "DELETE FROM settings WHERE key='password';"
sudo systemctl start crispasr-webui
```

### Custom Install Options

```bash
sudo INSTALL_DIR=/opt/my-tts DATA_DIR=/data/tts WEBUI_PORT=9999 bash install.sh
```

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTALL_DIR` | `/opt/crispasr` | Install directory |
| `DATA_DIR` | `/var/lib/crispasr-webui` | Data directory (history, audio) |
| `WEBUI_PORT` | `8888` | WebUI listen port |
| `CRISPASR_PORT` | `8080` | CrispASR service port |

### Manual Install

```bash
# Build
go build -o crispasr-webui .

# Run CrispASR server (install separately)
/opt/crispasr/bin/crispasr --server --backend qwen3-tts-customvoice \
  -m qwen3-tts-1.7b-customvoice --voice-dir /opt/crispasr/voices --port 8080 &

# Run WebUI
CRISPASR_DIR=/opt/crispasr ./crispasr-webui
```

Open http://localhost:8888

## Performance

| Metric | Python (v0.9.3) | Go (v1.4.0) |
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

## Compatibility

| OS | Support | Notes |
|----|---------|-------|
| Ubuntu 20.04+ | ✅ | Fully supported |
| Debian 11+ | ✅ | Fully supported |
| CentOS / RHEL 8+ | ⚠️ | Needs manual curl/git install |
| macOS | ⚠️ | Manual start (no systemd) |
| Other Linux | ⚠️ | Needs systemd + curl + git + bash |

## FAQ

<details>
<summary><strong>Forgot password?</strong></summary>

```bash
sudo systemctl stop crispasr-webui
sqlite3 /var/lib/crispasr-webui/history.db "DELETE FROM settings WHERE key='password';"
sudo systemctl start crispasr-webui
```

Resets to default `12345678`.
</details>

<details>
<summary><strong>How to uninstall?</strong></summary>

```bash
sudo systemctl stop crispasr-webui
sudo systemctl disable crispasr-webui
sudo rm /etc/systemd/system/crispasr-webui.service
sudo rm /etc/tts-webui.env
sudo rm -rf /opt/crispasr /var/lib/crispasr-webui
sudo systemctl daemon-reload
```
</details>

<details>
<summary><strong>How to view logs?</strong></summary>

```bash
journalctl -u crispasr-webui -f
```
</details>

<details>
<summary><strong>How to update WebUI?</strong></summary>

Re-run the installer:

```bash
curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
```
</details>

<details>
<summary><strong>How to update CrispASR?</strong></summary>

CrispASR must be updated manually. Download the new pre-built package, replace `/opt/crispasr/bin/crispasr`, then restart:

```bash
sudo systemctl restart crispasr
```

The WebUI Settings page shows current and latest versions.
</details>

<details>
<summary><strong>Auto start/stop — how does it work?</strong></summary>

Enabled by default (`CRISPASR_AUTOSTART=1`):

1. **On task submit** — auto `systemctl start crispasr`, wait for health check
2. **After tasks complete** — idle for 5 minutes, then auto `systemctl stop crispasr`
3. **New task during idle countdown** — auto-cancel the timer

Disable: set `CRISPASR_AUTOSTART=0` in `/etc/tts-webui.env`, restart WebUI.
</details>

<details>
<summary><strong>Pre-built binary crashes (Illegal instruction)?</strong></summary>

Some CPUs (e.g. Neoverse-N1, older x86_64) may not support instruction set extensions (SVE, AVX2) used in pre-built binaries.

Build CrispASR from source:

```bash
git clone --depth 1 --branch v0.8.5 https://github.com/CrispStrobe/CrispASR
cd CrispASR
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
sudo cp build/bin/crispasr /opt/crispasr/bin/crispasr
sudo find build -name '*.so*' -exec cp {} /opt/crispasr/lib/ \;
```
</details>

## License

MIT
