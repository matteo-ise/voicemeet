#!/usr/bin/env bash
#
# voicemeet-pro — one-command installer
# Checks deps, installs everything, sets up background daemon.
#
# Usage:  ./scripts/install.sh
#
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
DIM="\033[2m"
RESET="\033[0m"

info()  { printf "${BOLD}${GREEN}✓${RESET} %s\n" "$1"; }
warn()  { printf "${BOLD}${YELLOW}!${RESET} %s\n" "$1"; }
fail()  { printf "${BOLD}${RED}✗${RESET} %s\n" "$1"; exit 1; }
step()  { printf "\n${BOLD}→ %s${RESET}\n" "$1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCH_AGENT="$HOME/Library/LaunchAgents/com.voicemeet.pro.plist"

echo "${BOLD}╔══════════════════════════════════════════════╗${RESET}"
echo "${BOLD}║  voicemeet-pro installer                      ║${RESET}"
echo "${BOLD}║  Premium local meeting notes — zero cost     ║${RESET}"
echo "${BOLD}╚══════════════════════════════════════════════╝${RESET}"

# ── 1. Python ─────────────────────────────────────────────
step "Checking Python"

if ! command -v python3 &>/dev/null; then
    fail "Python 3 not found. Install from https://python.org or use miniconda."
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    fail "Python 3.11+ required, found $PY_VERSION"
fi

PYTHON_PATH=$(python3 -c 'import sys; print(sys.executable)')
info "Python $PY_VERSION at $PYTHON_PATH"

# ── 2. Install voicemeet-pro ──────────────────────────────
step "Installing voicemeet-pro (with all features)"

cd "$PROJECT_DIR"
if python3 -m pip install -e ".[all]" --quiet 2>&1 | grep -v "already satisfied"; then
    info "voicemeet-pro installed"
else
    info "voicemeet-pro already up to date"
fi

# Verify
if ! python3 -c "import voicemeet" 2>/dev/null; then
    fail "Installation failed — import voicemeet not working"
fi
info "Import verified"

# ── 3. Ollama ─────────────────────────────────────────────
step "Checking Ollama (for AI summaries)"

if ! command -v ollama &>/dev/null; then
    warn "Ollama not installed."
    echo "  Install from: https://ollama.ai"
    echo "  Then re-run: ./scripts/install.sh"
    echo "  ${DIM}(Summaries will be skipped until Ollama is available)${RESET}"
else
    info "Ollama found: $(ollama --version 2>&1 | head -1)"

    # Check if ollama is running
    if ! ollama list &>/dev/null 2>&1; then
        warn "Ollama not running. Starting it..."
        open -a Ollama 2>/dev/null || ollama serve &
        sleep 3
    fi

    # Pull model if not present
    step "Ensuring llama3.2 model is available"
    if ollama list 2>/dev/null | grep -q "llama3.2"; then
        info "llama3.2 already pulled"
    else
        echo "  Pulling llama3.2 (one-time, ~3GB)..."
        ollama pull llama3.2
        info "llama3.2 pulled"
    fi
fi

# ── 4. Whisper model ──────────────────────────────────────
step "Checking Whisper model"

if python3 -c "from voicemeet.transcribe.engine import find_model; m=find_model(); print(m) if m else exit(1)" 2>/dev/null; then
    MODEL_PATH=$(python3 -c "from voicemeet.transcribe.engine import find_model; print(find_model())")
    info "Model found: $MODEL_PATH"
else
    warn "No whisper model found."
    echo "  Options:"
    echo "    a) If you have OpenSuperWhisper installed — models are auto-detected"
    echo "    b) Download a model:"
    echo "       curl -L -o ~/.voicemeet/models/ggml-large-v3-turbo-q5_0.bin \\"
    echo "         https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
    echo "    c) Set VOICEMEET_MODEL_PATH=/path/to/model.bin"
    echo "  ${DIM}Transcription will fail until a model is available${RESET}"
fi

# ── 5. BlackHole (optional, for system audio) ─────────────
step "Checking BlackHole (optional — for online meetings)"

if python3 -c "
import sounddevice as sd
devs = sd.query_devices()
found = any('BlackHole' in d.get('name','') for d in devs)
exit(0 if found else 1)
" 2>/dev/null; then
    info "BlackHole installed"
else
    warn "BlackHole not found (optional — needed for system audio capture)"
    echo "  Install: brew install blackhole-2ch"
    echo "  Then: Audio MIDI Setup → Create Multi-Output Device"
    echo "  ${DIM}Mic-only recording works without it${RESET}"
fi

# ── 6. LaunchAgent (auto-start on login) ──────────────────
step "Setting up background daemon (LaunchAgent)"

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$LAUNCH_AGENT" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voicemeet.pro</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>-m</string>
        <string>voicemeet.menubar</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>${HOME}/.voicemeet/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.voicemeet/daemon.err</string>
</dict>
</plist>
PLIST

info "LaunchAgent installed at $LAUNCH_AGENT"

# Unload if already loaded, then load fresh
launchctl unload "$LAUNCH_AGENT" 2>/dev/null || true
launchctl load "$LAUNCH_AGENT" 2>/dev/null

if launchctl list | grep -q "com.voicemeet.pro"; then
    info "Background daemon started — menubar icon should appear"
else
    warn "LaunchAgent loaded but not visible yet — try logging out and back in"
fi

# ── 7. Create data directories ────────────────────────────
mkdir -p "$HOME/.voicemeet/exports" "$HOME/.voicemeet/recordings" "$HOME/.voicemeet/models"

# ── Done ──────────────────────────────────────────────────
echo ""
echo "${BOLD}${GREEN}╔══════════════════════════════════════════════╗${RESET}"
echo "${BOLD}${GREEN}║  Installation complete!                       ║${RESET}"
echo "${BOLD}${GREEN}╚══════════════════════════════════════════════╝${RESET}"
echo ""
echo "  ${BOLD}What just happened:${RESET}"
echo "    • voicemeet-pro installed with all features"
echo "    • Background daemon started (menubar icon: VM)"
echo "    • Auto-starts on login"
echo ""
echo "  ${BOLD}How to use:${RESET}"
echo "    • Press ${BOLD}Cmd+Shift+M${RESET} anywhere to start/stop recording"
echo "    • Click ${BOLD}VM${RESET} in menubar for options"
echo "    • Or use CLI: ${BOLD}voicemeet record --title \"My Meeting\"${RESET}"
echo ""
echo "  ${BOLD}Sessions saved to:${RESET} ~/.voicemeet/"
echo "  ${BOLD}Logs:${RESET} ~/.voicemeet/daemon.log"
echo ""
echo "  ${DIM}Uninstall: ./scripts/uninstall.sh${RESET}"
