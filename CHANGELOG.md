# Changelog

## v1.4.0 (2026-07-12)

### 🔒 Security

- **Password bcrypt hashing** — Passwords are now stored as bcrypt hashes in the database instead of plaintext. Login and change-password both use `bcrypt.CompareHashAndPassword`. Existing plaintext passwords are automatically migrated to bcrypt on first startup.

### ✨ New Features

- **Settings panel** — New ⚙️ Settings nav item with UI to configure CrispASR binary path and port directly from the WebUI. Previously only accessible via API.
- **MP3 output** — Users can now select MP3 format for audio output. Each chunk is converted via ffmpeg and appended incrementally to the output file. Previously only WAV was supported regardless of the format selector.
- **Incremental audio write** — `processTask` no longer accumulates all chunk audio in memory. Each chunk is written to the output file immediately after CrispASR returns. Peak memory drops from ~360MB to ~11MB for a 25k-character, 33-chunk task.

### 🐛 Fixes

- **Version check hint corrected** — The "new version available" hint now shows `cmake -B build && cmake --build build` instead of `cargo build --release` (CrispASR is a C++ project, not Rust).
- **install.sh cleanup** — Removed unused `WEBUI_USER` variable left over from the v3 root-execution refactor.
- **README consistency** — Fixed `tts.db` → `history.db` in all password reset examples (both Chinese and English READMEs). Added Settings panel to feature list.
- **Auto-stop for externally-started CrispASR** — When the WebUI starts and detects CrispASR already running (e.g. started manually via `systemctl start crispasr`), it now schedules the idle auto-stop timer. Previously, only CrispASR instances started by the WebUI's own auto-start mechanism would be auto-stopped.
- **HTTP client timeout** — Increased from 30min to 2h. ARM CPU RTF~11x means a single 800-char chunk takes ~35min; the old 30min timeout caused `context deadline exceeded` errors.
- **Frontend poll timeout** — Extended from ~1h to ~20h with adaptive interval (2s → 5s → 30s) for ultra-long tasks.
- **processTask logging** — Added chunk-level logging (char count, audio bytes, duration) for debugging failed tasks.

### 📦 Upgrade Notes

- The `golang.org/x/crypto/bcrypt` dependency is now required. `go mod tidy` will pull it automatically.
- On first startup after upgrade, existing plaintext passwords are automatically hashed — no user action needed.
- MP3 output requires `ffmpeg` installed on the server.

## v1.3.1 (2026-06-29)

### 🔒 Security Fixes

- **CORS origin whitelist** — Only allow localhost and private IPs (10.x, 172.16-31.x, 192.168.x). Unknown origins get `Access-Control-Allow-Origin: null` instead of being reflected back. Prevents credential leakage if `Access-Control-Allow-Credentials` is ever added.
- **JWT input validation** — Verify all JWT parts are well-formed base64url before HMAC comparison. Rejects malformed tokens early.
- **Service file write mutex** — `handleSwitchModel` now serializes writes to `/etc/systemd/system/crispasr.service` with `svcWriteMu`, preventing concurrent model switches from corrupting the unit file.
- **Auto-stop TOCTOU** — `scheduleCrispASRStop` re-checks `crispASRState == "running"` inside the timer callback, closing a race window where a task could arrive between the queue check and the stop command.

### 🔧 Improvements

- **`dbExec` now returns `error`** — Callers can decide whether to handle or ignore. Previously errors were only logged.

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
