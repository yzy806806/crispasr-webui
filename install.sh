#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# CrispASR TTS Web UI — One-click installer
# https://github.com/yzy806806/crispasr-webui
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
#
# Env overrides:
#   INSTALL_DIR=/opt/crispasr        DATA_DIR=/var/lib/crispasr-webui
#   WEBUI_PORT=8888                   CRISPASR_PORT=8080
#   MODEL=qwen3-tts-customvoice-1.7b-f16
#   MODEL_QUANT=f16                   GPU_BACKEND=auto
#   WEBUI_USER=crispasr
# ──────────────────────────────────────────────────────────
set -euo pipefail

# ─── Configurable defaults ────────────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/opt/crispasr}"
DATA_DIR="${DATA_DIR:-/var/lib/crispasr-webui}"
WEBUI_PORT="${WEBUI_PORT:-8888}"
CRISPASR_PORT="${CRISPASR_PORT:-8080}"
WEBUI_USER="${WEBUI_USER:-crispasr}"
MODEL="${MODEL:-qwen3-tts-customvoice-1.7b-f16}"
MODEL_QUANT="${MODEL_QUANT:-f16}"       # f16 | q8_0 | q4_k_m | q4_0
GPU_BACKEND="${GPU_BACKEND:-auto}"       # auto | cpu | cuda | vulkan

# ─── Colors ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()   { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ─── Global cleanup trap ──────────────────────────────────
_CLEANUP_DIRS=()
_cleanup() { local d; for d in "${_CLEANUP_DIRS[@]}"; do rm -rf "$d" 2>/dev/null; done; }
trap _cleanup EXIT

# _mktemp_value: populated by _mktemp, consumed immediately after call.
# Do NOT use in a subshell $() — EXIT trap would delete the dir before caller sees it.
_mktemp_value=""
_mktemp() {
    _mktemp_value="$(mktemp -d)" || die "Cannot create temp dir"
    _CLEANUP_DIRS+=("$_mktemp_value")
}

# ─── Package manager helpers ──────────────────────────────
_pkg_install=""
_pkg_update=""
_detect_pkg_mgr() {
    if command -v apt-get >/dev/null 2>&1; then
        _pkg_install="apt-get install -y -qq"
        _pkg_update="apt-get update -qq"
    elif command -v dnf >/dev/null 2>&1; then
        _pkg_install="dnf install -y -q"
        _pkg_update="dnf check-update -q || true"
    elif command -v yum >/dev/null 2>&1; then
        _pkg_install="yum install -y -q"
        _pkg_update="yum check-update -q || true"
    elif command -v apk >/dev/null 2>&1; then
        _pkg_install="apk add --no-cache"
        _pkg_update="apk update"
    elif command -v pacman >/dev/null 2>&1; then
        _pkg_install="pacman -S --noconfirm --needed"
        _pkg_update="pacman -Sy --noconfirm"
    elif command -v brew >/dev/null 2>&1; then
        _pkg_install="brew install"
        _pkg_update="brew update"
    else
        _pkg_install=""
        _pkg_update=""
    fi
}

# Ensure a command exists; try to install if missing
_ensure_cmd() {
    local bin="$1" pkg="${2:-$1}"
    command -v "$bin" >/dev/null 2>&1 && return 0
    if [ -n "$_pkg_install" ]; then
        warn "$bin not found, installing $pkg..."
        [ -n "$_pkg_update" ] && $_pkg_update 2>/dev/null || true
        $_pkg_install "$pkg" || die "Cannot install $pkg. Install manually: $pkg"
    else
        die "$bin is required but not found. Please install it manually."
    fi
}

# ─── Pre-flight checks ────────────────────────────────────
echo ""
info "CrispASR TTS Web UI Installer"
echo ""

# Must run as root (systemd + /etc write)
if [ "$(id -u)" -ne 0 ]; then
    die "This script must be run as root. Use: sudo bash install.sh"
fi

_detect_pkg_mgr
_ensure_cmd curl
_ensure_cmd git

# ─── Detect platform ──────────────────────────────────────
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
    x86_64|amd64)  ARCH_TAG="x86_64" ;;
    aarch64|arm64) ARCH_TAG="arm64" ;;
    *)             die "Unsupported architecture: $ARCH" ;;
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

# Build asset name (for prebuilt downloads on x86_64/macOS)
if [ "$OS" = "linux" ]; then
    case "$GPU_BACKEND" in
        cuda)   ASSET="crispasr-linux-${ARCH_TAG}-cuda.tar.gz" ;;
        vulkan) ASSET="crispasr-linux-${ARCH_TAG}-vulkan.tar.gz" ;;
        *)      ASSET="crispasr-linux-${ARCH_TAG}.tar.gz" ;;
    esac
elif [ "$OS" = "darwin" ]; then
    ASSET="crispasr-macos.tar.gz"
else
    die "Unsupported OS: $OS (Linux and macOS supported)"
fi

info "Platform: ${OS}/${ARCH_TAG}, GPU: ${GPU_BACKEND}"
info "Model: ${MODEL} (quant: ${MODEL_QUANT})"

# ─── Get latest CrispASR version ──────────────────────────
info "Fetching latest CrispASR release..."
LATEST_TAG="$(curl -sfL 'https://api.github.com/repos/CrispStrobe/CrispASR/releases/latest' \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["tag_name"])' 2>/dev/null || true)"

[ -n "$LATEST_TAG" ] || die "Cannot fetch CrispASR release info. Check network connectivity."
LATEST_VER="${LATEST_TAG#v}"
info "Latest CrispASR: ${LATEST_VER}"

# ─── Install CrispASR ──────────────────────────────────────
BINARY_DIR="${INSTALL_DIR}/bin"
_do_install=0

if [ -f "${BINARY_DIR}/crispasr" ]; then
    CURRENT_VER="$("${BINARY_DIR}/crispasr" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
    if [ "$CURRENT_VER" = "$LATEST_VER" ]; then
        ok "CrispASR ${CURRENT_VER} already installed, skipping"
    else
        info "Updating CrispASR ${CURRENT_VER:-unknown} → ${LATEST_VER}"
        _do_install=1
    fi
else
    _do_install=1
fi

if [ "$_do_install" = "1" ]; then
    mkdir -p "${BINARY_DIR}"

    # ── Use prebuilt binary for all platforms ──
    DOWNLOAD_URL="https://github.com/CrispStrobe/CrispASR/releases/download/${LATEST_TAG}/${ASSET}"
    info "Downloading ${ASSET}..."
    _mktemp && TMPDIR="$_mktemp_value"

    curl -fSL --progress-bar -o "${TMPDIR}/${ASSET}" "${DOWNLOAD_URL}" \
        || die "Download failed: ${DOWNLOAD_URL}"

    info "Extracting..."
    tar xzf "${TMPDIR}/${ASSET}" -C "${TMPDIR}"

    # Copy binaries
    BINARY_SRC="$(find "${TMPDIR}" -name crispasr -type f 2>/dev/null | head -1)"
    [ -n "$BINARY_SRC" ] || die "Cannot find crispasr binary in archive"
    BINARY_DIR_SRC="$(dirname "$BINARY_SRC")"

    cp "$BINARY_SRC" "${BINARY_DIR}/crispasr"
    chmod +x "${BINARY_DIR}/crispasr"

    # Copy auxiliary binaries (crispasr-quantize, etc.)
    find "$BINARY_DIR_SRC" -name 'crispasr*' -type f 2>/dev/null | while read -r f; do
        [ "$f" != "$BINARY_SRC" ] && cp "$f" "${BINARY_DIR}/" && chmod +x "${BINARY_DIR}/$(basename "$f")"
    done

    # Copy shared libraries if bundled in the archive
    mkdir -p "${BINARY_DIR}/../lib"
    find "${TMPDIR}" -name '*.so*' -type f 2>/dev/null | while read -r so; do
        cp "$so" "${BINARY_DIR}/../lib/" && chmod +x "${BINARY_DIR}/../lib/$(basename "$so")"
    done

    ok "CrispASR ${LATEST_VER} installed to ${BINARY_DIR}"
fi

# ─── Build WebUI from source ──────────────────────────────
info "Building CrispASR TTS Web UI (Go)..."

WEBUI_SRC="${INSTALL_DIR}/crispasr-webui-src"
WEBUI_BIN="${INSTALL_DIR}/bin/crispasr-webui"

# Install Go if missing
if ! command -v go >/dev/null 2>&1; then
    info "Go not found, installing Go 1.24..."
    _mktemp && GO_TMP="$_mktemp_value"
    curl -fSL "https://go.dev/dl/go1.24.4.${OS}-${ARCH_TAG}.tar.gz" | tar -C /usr/local -xzf -
    export PATH="$PATH:/usr/local/go/bin"
    ok "Go 1.24.4 installed"
fi

# Clone or update WebUI source
if [ -d "${WEBUI_SRC}/.git" ]; then
    info "Updating WebUI source..."
    git -C "${WEBUI_SRC}" pull --ff-only 2>/dev/null || warn "Git pull failed, using existing version"
else
    info "Cloning WebUI source..."
    rm -rf "${WEBUI_SRC}"
    git clone --depth 1 https://github.com/yzy806806/crispasr-webui.git "${WEBUI_SRC}" 2>/dev/null \
        || die "Git clone failed"
fi

# Build
info "Compiling..."
cd "${WEBUI_SRC}"
go build -o "${WEBUI_BIN}" . 2>&1 || die "Build failed"
chmod +x "${WEBUI_BIN}"

# Copy static files next to binary (Go reads ./static/ relative to CWD)
cp -r "${WEBUI_SRC}/static" "${INSTALL_DIR}/static"

ok "WebUI built: ${WEBUI_BIN} ($(du -h "${WEBUI_BIN}" | cut -f1))"

# ─── Create directories ───────────────────────────────────
mkdir -p "${DATA_DIR}/audio" "${DATA_DIR}/uploads" "${INSTALL_DIR}/voices"

# ─── Create system user (Linux only) ──────────────────────
if [ "$OS" = "linux" ] && command -v useradd >/dev/null 2>&1; then
    if ! id "$WEBUI_USER" >/dev/null 2>&1; then
        info "Creating system user: ${WEBUI_USER}"
        useradd --system --create-home --home-dir "/home/${WEBUI_USER}" \
            --shell /usr/sbin/nologin "$WEBUI_USER" 2>/dev/null || true
    fi
    chown -R "${WEBUI_USER}:${WEBUI_USER}" "${DATA_DIR}" "${INSTALL_DIR}/voices" "${INSTALL_DIR}/static" 2>/dev/null || true
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

    # Thread count: use half of available cores (min 1, max 8)
    THREADS="$(nproc 2>/dev/null || echo 2)"
    [ "$THREADS" -gt 2 ] && THREADS=$((THREADS / 2))
    [ "$THREADS" -lt 1 ] && THREADS=1
    [ "$THREADS" -gt 8 ] && THREADS=8

    # Resolve model: MODEL env var is the registry key (e.g. "qwen3-tts-customvoice-1.7b-f16")
    # We derive backend + model_flag from it. If MODEL looks like a raw model name
    # (no hyphens matching our registry), treat it as a model_flag directly.
    case "$MODEL" in
        qwen3-tts-customvoice-1.7b-f16)
            BACKEND="qwen3-tts-customvoice"; MODEL_FLAG="qwen3-tts-1.7b-customvoice" ;;
        qwen3-tts-customvoice-0.6b-q8)
            BACKEND="qwen3-tts-customvoice"; MODEL_FLAG="qwen3-tts-0.6b-customvoice" ;;
        qwen3-tts-base-1.7b)
            BACKEND="qwen3-tts"; MODEL_FLAG="qwen3-tts-1.7b-base" ;;
        qwen3-tts-voicedesign-1.7b)
            BACKEND="qwen3-tts-customvoice"; MODEL_FLAG="qwen3-tts-1.7b-voicedesign" ;;
        kokoro)
            BACKEND="kokoro"; MODEL_FLAG="kokoro" ;;
        cosyvoice3-tts)
            BACKEND="cosyvoice3-tts"; MODEL_FLAG="cosyvoice3-tts" ;;
        chatterbox)
            BACKEND="chatterbox"; MODEL_FLAG="chatterbox" ;;
        *)
            # Unknown key — assume it's a raw model_flag, guess backend
            BACKEND="qwen3-tts-customvoice"; MODEL_FLAG="$MODEL" ;;
    esac

    # Build quant flag: only pass --model-quant if user explicitly set MODEL_QUANT
    QUANT_FLAG=""
    if [ -n "$MODEL_QUANT" ]; then
        QUANT_FLAG="--model-quant ${MODEL_QUANT}"
    fi

    # --- CrispASR service ---
    cat > /etc/systemd/system/crispasr.service << EOF
[Unit]
Description=CrispASR TTS Server (${MODEL})
After=network.target

[Service]
Type=simple
User=${WEBUI_USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${BINARY_DIR}/crispasr --server --backend ${BACKEND} -m ${MODEL_FLAG} ${QUANT_FLAG} --voice-dir ${INSTALL_DIR}/voices --host 127.0.0.1 --port ${CRISPASR_PORT} -t ${THREADS} ${GPU_FLAGS}
Environment=LD_LIBRARY_PATH=${INSTALL_DIR}/lib
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
${WEBUI_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl start crispasr, /usr/bin/systemctl stop crispasr, /usr/bin/systemctl restart crispasr, /usr/bin/systemctl daemon-reload
EOF
    chmod 440 "$SUDOERS_FILE"

    # Allow webui user to modify crispasr.service (for model switching)
    chown "${WEBUI_USER}:${WEBUI_USER}" /etc/systemd/system/crispasr.service
    chmod 664 /etc/systemd/system/crispasr.service

    systemctl daemon-reload
    systemctl enable crispasr crispasr-webui
    systemctl start crispasr-webui

    # ─── Done ──────────────────────────────────────────
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🎙️  CrispASR TTS Web UI is ready!${NC}"
    echo ""
    echo -e "  URL:      ${GREEN}http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${WEBUI_PORT}${NC}"
    echo -e "  Password: 12345678 (default, change in Settings)"
    echo ""
    echo -e "  ${YELLOW}📌 Next step:${NC} open WebUI → ${YELLOW}🧠 模型选择${NC} → 选模型和量化级别，CrispASR 会自动下载模型并启动"
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
    echo "     CRISPASR_DIR='${INSTALL_DIR}' CRISPASR_DATA_DIR='${DATA_DIR}' ${WEBUI_BIN}"
    echo ""
    echo -e "  Then open: ${GREEN}http://localhost:${WEBUI_PORT}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi
