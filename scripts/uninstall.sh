#!/usr/bin/env bash
#
# voicemeet — clean uninstaller
# Removes LaunchAgent, stops daemon. Keeps session data.
#
# Usage:  ./scripts/uninstall.sh
#         ./scripts/uninstall.sh --purge  (also deletes session data)
#
set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
DIM="\033[2m"
RESET="\033[0m"

info()  { printf "${BOLD}${GREEN}✓${RESET} %s\n" "$1"; }
warn()  { printf "${BOLD}${YELLOW}!${RESET} %s\n" "$1"; }
step()  { printf "\n${BOLD}→ %s${RESET}\n" "$1"; }

LAUNCH_AGENT="$HOME/Library/LaunchAgents/com.voicemeet.pro.plist"
PURGE="${1:-}"

# ── 1. Stop daemon ────────────────────────────────────────
step "Stopping background daemon"

if launchctl list | grep -q "com.voicemeet.pro" 2>/dev/null; then
    launchctl unload "$LAUNCH_AGENT" 2>/dev/null || true
    info "Daemon stopped"
else
    info "Daemon was not running"
fi

# ── 2. Remove LaunchAgent ─────────────────────────────────
step "Removing LaunchAgent"

if [ -f "$LAUNCH_AGENT" ]; then
    rm "$LAUNCH_AGENT"
    info "LaunchAgent removed"
else
    info "No LaunchAgent found"
fi

# ── 3. Uninstall Python package ───────────────────────────
step "Uninstalling Python package"

if command -v pip3 &>/dev/null; then
    pip3 uninstall voicemeet -y --quiet 2>/dev/null && info "Package uninstalled" || info "Package not installed"
fi

# ── 4. Optionally purge data ──────────────────────────────
if [ "$PURGE" = "--purge" ]; then
    step "Purging session data"
    if [ -d "$HOME/.voicemeet" ]; then
        rm -rf "$HOME/.voicemeet"
        info "Session data deleted (~/.voicemeet/)"
    fi
else
    echo ""
    echo "  ${DIM}Session data preserved at ~/.voicemeet/${RESET}"
    echo "  ${DIM}To delete everything: ./scripts/uninstall.sh --purge${RESET}"
fi

echo ""
echo "${BOLD}${GREEN}voicemeet uninstalled.${RESET}"
