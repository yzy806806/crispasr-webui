# Changelog

## v1.3.0 (2026-06-29)

### 🏗️ Architecture: WebUI / CrispASR Separation

The biggest change in this release: **WebUI is now a pure frontend + model downloader**, completely decoupled from CrispASR installation.

- **install.sh** no longer installs, compiles, or manages CrispASR. It only installs the WebUI (~180 lines, down from ~430).
- **CrispASR** is installed by the user independently. WebUI detects it via a configurable path.
- **Settings panel** (`/api/settings`) lets you configure CrispASR binary path and port from the WebUI.
- **Model switching** now auto-creates the `crispasr.service` systemd unit on first use, then updates `ExecStart` and restarts.

### ✨ New Features

- **Model quantization selector** — When switching models, if multiple quantization options are available (f16, q8_0, q4_k_m), a dialog lets you choose.
- **Settings API** — `GET/POST /api/settings` to persist `crispasr_path` and `crispasr_port` in the database.
- **Auto service creation** — `handleSwitchModel` creates `/etc/systemd/system/crispasr.service` on first model switch. No manual systemd setup needed.
- **CrispASR version check** — Replaced the old install/update flow with a lightweight version detection endpoint.

### 🔧 Changes

- **Root execution** — WebUI now runs as root. All `sudo` calls removed. No dedicated system user, no sudoers file.
- **Password in SQLite only** — Password is stored exclusively in the database (`history.db`), never in environment files. Default: `12345678`.
- **install.sh streamlined** — Removed: CrispASR download/compile, GPU detection, model argument parsing, user creation, sudoers, CrispASR systemd service.
- **All architectures use prebuilt binaries** — Source compilation removed from install.sh. If the prebuilt binary doesn't work on your hardware, see the README FAQ for manual build instructions.

### 🐛 Fixes

- Fixed `_mktemp` subshell trap race condition that deleted temp directories before the caller could use them.
- Fixed cmake missing `-S` flag when building from source.
- Fixed missing `.so` library copying after aarch64 source builds.
- Fixed service file permissions and ownership for root execution.

### 📦 Upgrade Notes

If upgrading from v1.0.0:
1. Stop the old services: `systemctl stop crispasr-webui crispasr`
2. Run the new `install.sh` — it will reinstall the WebUI only.
3. Open the WebUI → Settings → configure your CrispASR binary path.
4. Switch to a model — the service will be auto-created and started.
