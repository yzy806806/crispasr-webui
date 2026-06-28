#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# CrispASR TTS Web UI — One-click installer
# https://github.com/yzy806806/crispasr-webui
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | bash
#   or:  bash install.sh
# ──────────────────────────────────────────────────────────
set -euo pipefail

# ─── Configurable defaults ────────────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/opt/crispasr}"
DATA_DIR="${DATA_DIR:-/var/lib/crispasr-webui}"
WEBUI_PORT="${WEBUI_PORT:-8888}"
CRISPASR_PORT="${CRISPASR_PORT:-8080}"
WEBUI_USER="${WEBUI_USER:-crispasr}"
MODEL="${MODEL:-qwen3-tts-customvoice-1.7b-f16}"
GPU_BACKEND="${GPU_BACKEND:-auto}"  # auto | cpu | cuda | vulkan

# ─── Colors ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Pre-flight checks ────────────────────────────────────
info "CrispASR TTS Web UI Installer"
echo ""

# Must run as root (systemd + /etc write + /usr/local install)
if [ "$(id -u)" -ne 0 ]; then
    err "This script must be run as root. Use: sudo bash install.sh"
fi

command -v curl >/dev/null 2>&1 || err "curl is required but not found"
command -v git >/dev/null 2>&1 || err "git is required but not found"

# ─── Detect platform ──────────────────────────────────────
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
    x86_64|amd64)  ARCH_TAG="x86_64" ;;
    aarch64|arm64) ARCH_TAG="arm64" ;;
    *)             err "Unsupported architecture: $ARCH" ;;
esac

# Determine GPU variant
if [ "$GPU_BACKEND" = "auto" ]; then
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
        GPU_BACKEND="cuda"
    elif command -v vulkaninfo >/dev/null 2>&1 && vulkaninfo >/dev/null 2>&1; then
        GPU_BACKEND="vulkan"
    else
        GPU_BACKEND="cpu"
    fi
fi

# Build asset name
if [ "$OS" = "linux" ]; then
    case "$GPU_BACKEND" in
        cuda)   ASSET="crispasr-linux-${ARCH_TAG}-cuda.tar.gz" ;;
        vulkan) ASSET="crispasr-linux-${ARCH_TAG}-vulkan.tar.gz" ;;
        *)      ASSET="crispasr-linux-${ARCH_TAG}.tar.gz" ;;
    esac
elif [ "$OS" = "darwin" ]; then
    ASSET="crispasr-macos.tar.gz"
else
    err "Unsupported OS: $OS (Linux and macOS supported)"
fi

info "Platform: ${OS}/${ARCH_TAG}, GPU: ${GPU_BACKEND}"
info "Asset: ${ASSET}"

# ─── Get latest CrispASR version ──────────────────────────
info "Fetching latest CrispASR release..."
LATEST_TAG="$(curl -sfL 'https://api.github.com/repos/CrispStrobe/CrispASR/releases/latest' \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["tag_name"])' 2>/dev/null || true)"

if [ -z "$LATEST_TAG" ]; then
    err "Cannot fetch CrispASR release info. Check network connectivity."
fi
LATEST_VER="${LATEST_TAG#v}"
info "Latest CrispASR: ${LATEST_VER}"

# ─── Download CrispASR ────────────────────────────────────
DOWNLOAD_URL="https://github.com/CrispStrobe/CrispASR/releases/download/${LATEST_TAG}/${ASSET}"
BINARY_DIR="${INSTALL_DIR}/bin"

if [ -f "${BINARY_DIR}/crispasr" ]; then
    CURRENT_VER="$("${BINARY_DIR}/crispasr" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo 'unknown')"
    if [ "$CURRENT_VER" = "$LATEST_VER" ]; then
        ok "CrispASR ${CURRENT_VER} already installed, skipping download"
    else
        info "Updating CrispASR ${CURRENT_VER} → ${LATEST_VER}"
        _do_download=1
    fi
else
    _do_download=1
fi

if [ "${_do_download:-0}" = "1" ]; then
    info "Downloading ${ASSET}..."
    TMPDIR="$(mktemp -d)"
    trap 'rm -rf "$TMPDIR"' EXIT

    curl -fSL --progress-bar -o "${TMPDIR}/${ASSET}" "${DOWNLOAD_URL}" \
        || err "Download failed: ${DOWNLOAD_URL}"

    info "Extracting..."
    mkdir -p "${BINARY_DIR}"
    tar xzf "${TMPDIR}/${ASSET}" -C "${TMPDIR}"

    # Find and install binary
    BINARY_SRC="$(find "${TMPDIR}" -name crispasr -type f 2>/dev/null | head -1)"
    [ -n "$BINARY_SRC" ] || err "Cannot find crispasr binary in archive"

    cp "$BINARY_SRC" "${BINARY_DIR}/crispasr"
    chmod +x "${BINARY_DIR}/crispasr"

    # Copy auxiliary binaries (crispasr-quantize, etc.)
    find "$(dirname "$BINARY_SRC")" -name 'crispasr*' -type f 2>/dev/null | while read -r f; do
        [ "$f" != "$BINARY_SRC" ] && cp "$f" "${BINARY_DIR}/" && chmod +x "${BINARY_DIR}/$(basename "$f")"
    done

    ok "CrispASR ${LATEST_VER} installed to ${BINARY_DIR}"
fi

# ─── Build WebUI from source ──────────────────────────────
info "Building CrispASR TTS Web UI (Go)..."

WEBUI_SRC="${INSTALL_DIR}/crispasr-webui-src"
WEBUI_BIN="${INSTALL_DIR}/bin/crispasr-webui"

# Check Go
if ! command -v go >/dev/null 2>&1; then
    info "Go not found, installing Go 1.24..."
    GO_TMP="$(mktemp -d)"
    curl -fSL "https://go.dev/dl/go1.24.4.${OS}-${ARCH_TAG}.tar.gz" | tar -C /usr/local -xzf -
    export PATH="$PATH:/usr/local/go/bin"
    rm -rf "$GO_TMP"
    ok "Go 1.24.4 installed"
fi

# Clone or update
if [ -d "${WEBUI_SRC}/.git" ]; then
    info "Updating WebUI source..."
    git -C "${WEBUI_SRC}" pull --ff-only 2>/dev/null || warn "Git pull failed, using existing version"
else
    info "Cloning WebUI source..."
    rm -rf "${WEBUI_SRC}"
    git clone --depth 1 https://github.com/yzy806806/crispasr-webui.git "${WEBUI_SRC}" 2>/dev/null \
        || err "Git clone failed"
fi

# Build
info "Compiling..."
cd "${WEBUI_SRC}"
go build -o "${WEBUI_BIN}" . 2>&1 || err "Build failed"
chmod +x "${WEBUI_BIN}"

# Copy static files next to binary (Go reads ./static/)
cp -r "${WEBUI_SRC}/static" "${INSTALL_DIR}/static"

ok "WebUI built: ${WEBUI_BIN} ($(du -h "${WEBUI_BIN}" | cut -f1))"

# ─── Create data directory ────────────────────────────────
mkdir -p "${DATA_DIR}/audio" "${DATA_DIR}/uploads" "${INSTALL_DIR}/voices"

# ─── Create system user (Linux only) ──────────────────────
if [ "$OS" = "linux" ] && command -v useradd >/dev/null 2>&1; then
    if ! id "$WEBUI_USER" >/dev/null 2>&1; then
        info "Creating system user: ${WEBUI_USER}"
        useradd --system --no-create-home --shell /usr/sbin/nologin "$WEBUI_USER" 2>/dev/null || true
    fi
    chown -R "$WEBUI_USER":"$WEBUI_USER" "${DATA_DIR}" "${INSTALL_DIR}/voices" "${INSTALL_DIR}/static" 2>/dev/null || true
fi

# ─── Write config file ────────────────────────────────────
ENV_FILE="/etc/tts-webui.env"
if [ "$OS" = "linux" ]; then
    cat > "$ENV_FILE" << ENVEOF
CRISPASR_DIR=${INSTALL_DIR}
CRISPASR_DATA_DIR=${DATA_DIR}
CRISPASR_PORT=${CRISPASR_PORT}
CRISPASR_AUTOSTART=1
CRISPASR_IDLE_TIMEOUT=300
ENVEOF
    chmod 644 "$ENV_FILE"
    ok "Config saved to ${ENV_FILE} (password stored in DB, default: 12345678)"
else
    warn "Save these env vars for manual startup:"
    echo "  export CRISPASR_DIR='${INSTALL_DIR}'"
    echo "  export CRISPASR_DATA_DIR='${DATA_DIR}'"
    echo "  export CRISPASR_AUTOSTART=1"
fi

# ─── Configure systemd services (Linux only) ──────────────
if [ "$OS" = "linux" ] && command -v systemctl >/dev/null 2>&1; then
    info "Configuring systemd services..."

    # GPU flags
    GPU_FLAGS=""
    if [ "$GPU_BACKEND" = "cuda" ]; then
        GPU_FLAGS="--gpu-backend cuda"
    elif [ "$GPU_BACKEND" = "vulkan" ]; then
        GPU_FLAGS="--gpu-backend vulkan"
    fi

    # Thread count: use half of available cores
    THREADS="$(nproc 2>/dev/null || echo 2)"
    [ "$THREADS" -gt 2 ] && THREADS=$((THREADS / 2))
    [ "$THREADS" -lt 1 ] && THREADS=1

    # Model config (from Go registry via the binary itself)
    MODEL_FLAG="qwen3-tts-1.7b-customvoice"
    BACKEND="qwen3-tts-customvoice"

    # --- CrispASR service ---
    cat > /etc/systemd/system/crispasr.service << EOF
[Unit]
Description=CrispASR TTS Server (${MODEL})
After=network.target

[Service]
Type=simple
User=${WEBUI_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${BINARY_DIR}/crispasr --server --backend ${BACKEND} -m ${MODEL_FLAG} --auto-download --voice-dir ${INSTALL_DIR}/voices --host 127.0.0.1 --port ${CRISPASR_PORT} -t ${THREADS} ${GPU_FLAGS}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # --- WebUI service (Go binary) ---
    # Note: no Requires=crispasr.service — WebUI auto-starts/stops CrispASR on demand
    cat > /etc/systemd/system/crispasr-webui.service << EOF
[Unit]
Description=CrispASR TTS Web UI (Go)
After=network.target crispasr.service

[Service]
Type=simple
User=${WEBUI_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${WEBUI_BIN}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # --- Sudoers for auto start/stop ---
    SUDOERS_FILE="/etc/sudoers.d/crispasr-autostart"
    cat > "$SUDOERS_FILE" << EOF
${WEBUI_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl start crispasr, /usr/bin/systemctl stop crispasr, /usr/bin/systemctl restart crispasr
EOF
    chmod 440 "$SUDOERS_FILE"

    systemctl daemon-reload
    systemctl enable crispasr crispasr-webui
    systemctl restart crispasr

    info "Waiting for CrispASR to start..."
    for i in $(seq 1 30); do
        if curl -sf "http://localhost:${CRISPASR_PORT}/v1/models" >/dev/null 2>&1; then
            break
        fi
        sleep 2
    done

    systemctl restart crispasr-webui

    ok "Services configured and started!"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🎙️  CrispASR TTS Web UI is ready!${NC}"
    echo ""
    echo -e "  URL:      ${GREEN}http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${WEBUI_PORT}${NC}"
    echo -e "  Password: 12345678 (default, change in Settings)"
    echo ""
    echo -e "  ${YELLOW}⚡ Auto start/stop enabled${NC} — CrispASR stops after 5 min idle, starts on demand"
    echo ""
    echo -e "  Services:  ${CYAN}systemctl status crispasr crispasr-webui${NC}"
    echo -e "  Logs:      ${CYAN}journalctl -u crispasr-webui -f${NC}"
    echo -e "  Uninstall: ${CYAN}systemctl stop crispasr crispasr-webui && rm -rf ${INSTALL_DIR} ${DATA_DIR}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

else
    # ─── Manual start instructions (macOS / non-systemd) ──
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🎙️  CrispASR TTS Web UI — Manual Start${NC}"
    echo ""
    echo "  1. Start CrispASR server:"
    echo "     ${BINARY_DIR}/crispasr --server --backend qwen3-tts-customvoice -m qwen3-tts-1.7b-customvoice --voice-dir ${INSTALL_DIR}/voices --port ${CRISPASR_PORT} &"
    echo ""
    echo "  2. Start WebUI:"
    echo "     CRISPASR_DIR='${INSTALL_DIR}' CRISPASR_DATA_DIR='${DATA_DIR}' \\\\"
    echo "       ${WEBUI_BIN}"
    echo ""
    echo -e "  Then open: ${GREEN}http://localhost:${WEBUI_PORT}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi
