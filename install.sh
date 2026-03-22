#!/usr/bin/env bash

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "  ${CYAN}[*]${RESET} $*"; }
success() { echo -e "  ${GREEN}[+]${RESET} $*"; }
warn()    { echo -e "  ${YELLOW}[!]${RESET} $*"; }
error()   { echo -e "  ${RED}[-]${RESET} $*"; exit 1; }
section() { echo -e "\n${BOLD}${CYAN}── $* ──${RESET}"; }

echo -e "${RED}${BOLD}"
cat << 'EOF'
  ██████╗ ███████╗██╗  ██╗     ██████╗ ███████╗██╗███╗   ██╗████████╗
  ██╔══██╗██╔════╝╚██╗██╔╝    ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝
  ██████╔╝███████╗ ╚███╔╝     ██║   ██║███████╗██║██╔██╗ ██║   ██║
  ██╔══██╗╚════██║ ██╔██╗     ██║   ██║╚════██║██║██║╚██╗██║   ██║
  ██║  ██║███████║██╔╝ ██╗    ╚██████╔╝███████║██║██║ ╚████║   ██║
  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝    ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝
EOF
echo -e "${RESET}${CYAN}  Advanced Breach & Dark Web Intelligence Framework${RESET}"
echo -e "${RESET}${BOLD}  Installer v2.0${RESET}\n"

if [[ "$EUID" -eq 0 ]]; then
    warn "Running as root — pip packages will install system-wide."
fi

section "Detecting environment"
OS="unknown"
if   [[ -f /etc/os-release ]]; then source /etc/os-release; OS="${ID:-unknown}"; fi
ARCH=$(uname -m)
info "OS: ${OS}  |  Arch: ${ARCH}  |  Kernel: $(uname -r)"

section "Checking Python"
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))')
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [[ "$MAJOR" -ge 3 && "$MINOR" -ge 10 ]]; then
            PYTHON="$cmd"
            success "Found $cmd ($VER)"
            break
        else
            warn "$cmd is $VER — need 3.10+"
        fi
    fi
done
[[ -z "$PYTHON" ]] && error "Python 3.10+ not found. Install it first:\n  sudo apt install python3 python3-pip"

section "Checking pip"
if ! "$PYTHON" -m pip --version &>/dev/null; then
    warn "pip not found — attempting install..."
    case "$OS" in
        kali|debian|ubuntu|linuxmint|parrot)
            sudo apt-get install -y python3-pip ;;
        arch|manjaro)
            sudo pacman -S --noconfirm python-pip ;;
        fedora|rhel|centos)
            sudo dnf install -y python3-pip ;;
        *)
            "$PYTHON" -m ensurepip --upgrade || error "Could not install pip" ;;
    esac
fi
success "pip: $("$PYTHON" -m pip --version | awk '{print $1,$2}')"

section "Installing system packages"
install_sys_pkg() {
    case "$OS" in
        kali|debian|ubuntu|linuxmint|parrot)
            sudo apt-get install -y "$@" ;;
        arch|manjaro)
            sudo pacman -S --noconfirm "$@" ;;
        fedora|rhel|centos)
            sudo dnf install -y "$@" ;;
        *)
            warn "Unknown OS — skipping system package install for: $*" ;;
    esac
}

if command -v tor &>/dev/null; then
    success "Tor already installed: $(tor --version 2>&1 | head -1)"
else
    info "Installing Tor..."
    install_sys_pkg tor
    success "Tor installed"
fi

info "Installing build essentials..."
case "$OS" in
    kali|debian|ubuntu|linuxmint|parrot)
        sudo apt-get install -y build-essential libssl-dev libffi-dev \
             python3-dev curl wget git 2>/dev/null || true ;;
    arch|manjaro)
        sudo pacman -S --noconfirm base-devel openssl 2>/dev/null || true ;;
    fedora|rhel|centos)
        sudo dnf install -y gcc openssl-devel python3-devel 2>/dev/null || true ;;
esac
success "System packages done"

section "Setting up Python virtual environment"
VENV_DIR="$(pwd)/venv"

if [[ -d "$VENV_DIR" ]]; then
    warn "venv already exists at $VENV_DIR — skipping creation"
else
    "$PYTHON" -m venv "$VENV_DIR"
    success "Created venv at $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python3"
success "venv activated — using $PYTHON_VENV"

"$PIP" install --upgrade pip setuptools wheel -q
success "pip upgraded inside venv"

section "Installing Python dependencies"
if [[ ! -f "requirements.txt" ]]; then
    error "requirements.txt not found — are you running this from the rsx-osint directory?"
fi

info "Installing from requirements.txt..."
"$PIP" install -r requirements.txt
success "All Python packages installed"

section "Playwright (optional — for JS-heavy pages)"
PLAYWRIGHT_ENABLED=$(python3 -c "
import yaml
try:
    cfg = yaml.safe_load(open('config/settings.yaml'))
    print(str(cfg.get('use_playwright', False)).lower())
except:
    print('false')
" 2>/dev/null || echo "false")

if [[ "$PLAYWRIGHT_ENABLED" == "true" ]]; then
    info "use_playwright is enabled — installing browser..."
    "$VENV_DIR/bin/playwright" install firefox
    success "Playwright Firefox installed"
else
    info "use_playwright is false in settings.yaml — skipping browser install"
    info "To enable later: set use_playwright: true then run:  playwright install firefox"
fi

section "Creating output directories"
mkdir -p output/results
success "output/results/ ready"

section "Tor service"
TOR_RUNNING=false
if systemctl is-active --quiet tor 2>/dev/null; then
    success "Tor service is already running"
    TOR_RUNNING=true
else
    info "Tor is not running — attempting to start..."
    if sudo systemctl start tor 2>/dev/null; then
        sleep 2
        if systemctl is-active --quiet tor 2>/dev/null; then
            success "Tor service started"
            TOR_RUNNING=true
        fi
    fi
fi

if [[ "$TOR_RUNNING" == "false" ]]; then
    warn "Could not start Tor automatically."
    warn "Start it manually before using dark web mode:"
    warn "  sudo systemctl start tor"
    warn "  OR: tor &"
fi

if [[ "$TOR_RUNNING" == "true" ]]; then
    section "Verifying Tor connectivity"
    info "Testing SOCKS5 on 127.0.0.1:9050..."
    TOR_CHECK=$("$PYTHON_VENV" -c "
import socket
try:
    s = socket.create_connection(('127.0.0.1', 9050), timeout=5)
    s.close()
    print('ok')
except:
    print('fail')
" 2>/dev/null)
    if [[ "$TOR_CHECK" == "ok" ]]; then
        success "Tor SOCKS5 is reachable on 127.0.0.1:9050"
    else
        warn "Tor SOCKS5 not reachable on port 9050 — check your Tor config"
    fi
fi

section "Verifying installation"
VERIFY=$("$PYTHON_VENV" -c "
mods = [
    'aiohttp','bs4','rich','yaml','requests',
    'modules.utils.config','modules.utils.tui','modules.utils.dedup',
    'modules.dorking.engines','modules.darkweb.engines','modules.darkweb.crawler',
    'modules.scraper.breach','modules.scraper.paste',
]
ok, fail = [], []
for m in mods:
    try: __import__(m); ok.append(m)
    except Exception as e: fail.append((m, str(e)))
print(f'PASS:{len(ok)} FAIL:{len(fail)}')
for m,e in fail: print(f'  FAIL {m}: {e}')
" 2>&1)

if echo "$VERIFY" | grep -q "FAIL:0"; then
    success "All modules import successfully"
else
    warn "Some modules had import errors:"
    echo "$VERIFY" | grep FAIL
fi

section "Creating launcher"
cat > run.sh << 'RUNEOF'
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/venv/bin/activate"
python3 "$DIR/main.py" "$@"
RUNEOF
chmod +x run.sh
success "Created run.sh launcher"

echo ""
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}${BOLD}  Installation complete!${RESET}"
echo ""
echo -e "  ${BOLD}Run interactive TUI:${RESET}"
echo -e "    ${CYAN}./run.sh${RESET}"
echo ""
echo -e "  ${BOLD}Or with flags:${RESET}"
echo -e "    ${CYAN}./run.sh -q user@example.com -t email --clearnet${RESET}"
echo -e "    ${CYAN}./run.sh -q targetuser -t username --both --tor 127.0.0.1:9050${RESET}"
echo ""
echo -e "  ${BOLD}Optional — add API keys in:${RESET}"
echo -e "    ${CYAN}config/settings.yaml${RESET}  (api_keys section)"
echo ""
echo -e "  ${BOLD}Optional — add proxies for dork rotation:${RESET}"
echo -e "    ${CYAN}config/proxies.txt${RESET}  (one per line)"
echo ""
echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
