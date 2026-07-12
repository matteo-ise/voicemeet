#!/usr/bin/env bash
#
# Demo script — showcases voicemeet features with realistic timing.
# Record with: asciinema rec --overwrite --command ./scripts/demo.sh assets/demo.cast
# Convert:     agg assets/demo.cast assets/demo.gif --font-size 18 --theme monokai
#
set -uo pipefail  # no -e — some commands exit non-zero by design (setup exits 1 if optional deps missing)

export TERM=xterm-256color

# Helper: print command, sleep, execute, sleep
run() {
    echo ""
    printf "\033[1;36m\$ %s\033[0m\n" "$1"
    sleep 0.8
    bash -c "$1" 2>&1 || true
    sleep 1.5
}

clear
sleep 0.5

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║          voicemeet  —  Demo Walkthrough          ║"
echo "  ║    Premium local meeting notes, 100% private     ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""
sleep 2

# ── 1. Version ─────────────────────────────────────────
run "voicemeet --version"

# ── 2. Setup check ─────────────────────────────────────
run "voicemeet setup"

# ── 3. Record (dry-run — shows full pipeline) ──────────
run "voicemeet record --dry-run --title 'Q3 Product Sync'"

# ── 4. List sessions ───────────────────────────────────
run "voicemeet list --limit 5"

# ── 5. Show latest ─────────────────────────────────────
SID=$(
    python3 -c "
import os, sqlite3
db = os.path.expanduser('~/.voicemeet/voicemeet.db')
conn = sqlite3.connect(db)
row = conn.execute(\"SELECT id FROM sessions ORDER BY started_at DESC LIMIT 1\").fetchone()
print(row[0][:8] if row else '')
" 2>/dev/null
)
if [ -n "$SID" ]; then
    run "voicemeet show $SID"
fi

# ── 6. Export ──────────────────────────────────────────
if [ -n "$SID" ]; then
    run "voicemeet export $SID --format md --output /tmp/voicemeet-demo.md"
fi

# ── 7. Search ──────────────────────────────────────────
run "voicemeet search Q3"

echo ""
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║  ⭐ Star us: github.com/matteo-ise/voicemeet     ║"
echo "  ║  Install:  git clone ... && ./scripts/install.sh ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo ""
sleep 3
