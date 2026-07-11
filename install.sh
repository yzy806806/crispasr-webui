#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# CrispASR TTS Web UI — One-click installer (webui only)
# https://github.com/yzy806806/crispasr-webui
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/yzy806806/crispasr-webui/main/install.sh | sudo bash
#
# CrispASR must be installed separately.
# Use the webui to configure the path and manage models.
# ──────────────────────────────────────────────────────────
set -euo pipefail

# ─── Configurable defaults ────────────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/opt/crispasr}"
DATA_DIR="${DATA_DIR:-/var/lib/crispasr-webui}"
WEBUI_PORT="${WEBUI_PORT:-8888}"
CRISPASR_PORT="${CRISPASR_PORT:-8080}"

# ─── Colors ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()   { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

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

# ─── Pre-flight ────────────────────────────────────────────
echo ""
info "CrispASR TTS Web UI Installer"
echo ""

if [ "$(id -u)" -ne 0 ]; then
    die "This script must be run as root. Use: sudo bash install.sh"
fi

_detect_pkg_mgr
_ensure_cmd curl
_ensure_cmd git

# ─── Detect platform (for Go download) ────────────────────
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64)  ARCH_TAG="amd64" ;;
    aarch64|arm64) ARCH_TAG="arm64" ;;
    *)             die "Unsupported architecture: $ARCH" ;;
esac

info "Platform: ${OS}/${ARCH_TAG}"

# ─── Build WebUI from source ──────────────────────────────
info "Building CrispASR TTS Web UI (Go)..."

WEBUI_SRC="${INSTALL_DIR}/crispasr-webui-src"
WEBUI_BIN="${INSTALL_DIR}/bin/crispasr-webui"

# Install Go if missing
if ! command -v go >/dev/null 2>&1; then
    info "Go not found, installing Go 1.24..."
    GO_TMP="$(mktemp -d)"
    trap "rm -rf '$GO_TMP'" RETURN
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

# Copy static files
cp -r "${WEBUI_SRC}/static" "${INSTALL_DIR}/static"

ok "WebUI built: ${WEBUI_BIN} ($(du -h "${WEBUI_BIN}" | cut -f1))"

# ─── Create directories ───────────────────────────────────
mkdir -p "${DATA_DIR}/audio" "${DATA_DIR}/uploads" "${INSTALL_DIR}/voices"

# ─── Write config ─────────────────────────────────────────
ENV_FILE="/etc/tts-webui.env"
cat > "$ENV_FILE" << ENVEOF
CRISPASR_DIR=${INSTALL_DIR}
CRISPASR_DATA_DIR=${DATA_DIR}
CRISPASR_PORT=${CRISPASR_PORT}
CRISPASR_AUTOSTART=1
CRISPASR_IDLE_TIMEOUT=300
ENVEOF
chmod 644 "$ENV_FILE"
ok "Config saved to ${ENV_FILE} (password stored in DB, default: 12345678)"

# ─── Systemd service (webui only) ─────────────────────────
if [ "$OS" = "linux" ] && command -v systemctl >/dev/null 2>&1; then
    info "Configuring systemd service..."

    cat > /etc/systemd/system/crispasr-webui.service << EOF
[Unit]
Description=CrispASR TTS Web UI (Go)
After=network.target

[Service]
Type=simple
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

    systemctl daemon-reload
    systemctl enable crispasr-webui
    systemctl start crispasr-webui

    # ─── Done ──────────────────────────────────────────
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🎙️  CrispASR TTS Web UI is ready!${NC}"
    echo ""
    echo -e "  URL:      ${GREEN}http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${WEBUI_PORT}${NC}"
    echo -e "  Password: 12345678 (default, change in Settings)"
    echo ""
    echo -e "  ${YELLOW}📌 CrispASR not included.${NC} Install it separately, then configure the"
    echo -e "     path in WebUI → ⚙️ Settings, then pick a model in 🧠 Model."
    echo ""
    echo -e "  Service:  ${CYAN}systemctl status crispasr-webui${NC}"
    echo -e "  Logs:     ${CYAN}journalctl -u crispasr-webui -f${NC}"
    echo -e "  Uninstall: ${CYAN}systemctl stop crispasr-webui && rm -rf ${INSTALL_DIR} ${DATA_DIR}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

else
    # Manual start (macOS / non-systemd)
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🎙️  CrispASR TTS Web UI — Manual Start${NC}"
    echo ""
    echo "  Start WebUI:"
    echo "    CRISPASR_DIR='${INSTALL_DIR}' CRISPASR_DATA_DIR='${DATA_DIR}' ${WEBUI_BIN}"
    echo ""
    echo -e "  Then open: ${GREEN}http://localhost:${WEBUI_PORT}${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
fi
