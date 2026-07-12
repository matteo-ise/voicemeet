#!/usr/bin/env bash
#
# voicemeet — BlackHole setup helper
# Installs BlackHole 2ch and provides setup instructions.
#
# Usage:  ./scripts/setup_blackhole.sh
#
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

info()  { printf "${BOLD}${GREEN}✓${RESET} %s\n" "$1"; }
warn()  { printf "${BOLD}${YELLOW}!${RESET} %s\n" "$1"; }
step()  { printf "\n${BOLD}→ %s${RESET}\n" "$1"; }

echo "${BOLD}BlackHole Setup — for system audio capture${RESET}"
echo ""
echo "BlackHole is a virtual audio driver that lets voicemeet"
echo "capture system audio (Zoom, Meet, Teams, browser calls)."
echo ""

# ── 1. Install BlackHole ──────────────────────────────────
step "Installing BlackHole 2ch"

if ! command -v brew &>/dev/null; then
    warn "Homebrew not found. Install from https://brew.sh"
    echo "  Then run: brew install blackhole-2ch"
    exit 1
fi

if brew list blackhole-2ch &>/dev/null 2>&1; then
    info "BlackHole 2ch already installed"
else
    brew install blackhole-2ch
    info "BlackHole 2ch installed"
fi

# ── 2. Setup instructions ─────────────────────────────────
step "Multi-Output Device setup (required)"

echo "  To capture BOTH speakers + system audio:"
echo ""
echo "  1. Open ${BOLD}Audio MIDI Setup${RESET} (Spotlight → 'Audio MIDI Setup')"
echo "  2. Click ${BOLD}+${RESET} (bottom left) → ${BOLD}Create Multi-Output Device${RESET}"
echo "  3. Check both:"
echo "     • ${BOLD}BlackHole 2ch${RESET}"
echo "     • ${BOLD}Your speakers/headphones${RESET}"
echo "  4. Set Master Device to your speakers"
echo "  5. Set system output to this Multi-Output Device"
echo "     (System Settings → Sound → Output → Multi-Output Device)"
echo ""
echo "  ${BOLD}Now voicemeet can capture system audio via BlackHole.${RESET}"
echo ""

# ── 3. Verify ─────────────────────────────────────────────
step "Verifying"

if python3 -c "
import sounddevice as sd
devs = sd.query_devices()
found = any('BlackHole' in d.get('name','') for d in devs)
exit(0 if found else 1)
" 2>/dev/null; then
    info "BlackHole detected by sounddevice"
else
    warn "BlackHole not detected yet — restart audio apps or reboot"
fi

echo ""
echo "${BOLD}${GREEN}Done!${RESET} Use voicemeet record --mode online to capture system audio."
