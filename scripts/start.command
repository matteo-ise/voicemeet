#!/usr/bin/env bash
#
# voicemeet-pro — double-clickable start script
# Starts the menubar daemon without installing a LaunchAgent.
#
# Usage: Double-click this file in Finder, or run: ./scripts/start.command
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# If voicemeet is installed, just run it
if command -v voicemeet &>/dev/null; then
    exec python3 -m voicemeet.menubar
fi

# Otherwise, run from project dir
cd "$PROJECT_DIR"
if [ ! -d "src/voicemeet" ]; then
    echo "voicemeet-pro not found. Run ./scripts/install.sh first."
    read -p "Press Enter to close..."
    exit 1
fi

# Ensure deps installed
python3 -m pip install -e ".[all]" --quiet 2>/dev/null || true

# Start menubar daemon
exec python3 -m voicemeet.menubar
