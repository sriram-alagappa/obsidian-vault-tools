#!/bin/bash
# install-agent.sh — install (or remove) the launchd agent that keeps _OCR/ current.
#
#   OBSIDIAN_VAULT="/path/to/My Vault" ./scripts/install-agent.sh
#   ./scripts/install-agent.sh --uninstall
#
# The agent runs build_ocr.py every INTERVAL seconds. An uneventful pass costs
# ~0.2s and logs nothing, so the log only ever records real work.
set -euo pipefail

LABEL="com.user.obsidian-ocr"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/obsidian-ocr.log"
INTERVAL="${INTERVAL:-30}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

unload() { launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true; }

if [ "${1:-}" = "--uninstall" ]; then
  unload; rm -f "$PLIST"
  echo "  removed $LABEL"; exit 0
fi

VAULT="${OBSIDIAN_VAULT:-}"
[ -n "$VAULT" ]            || { echo "  set OBSIDIAN_VAULT to the vault path"; exit 1; }
[ -d "$VAULT/.obsidian" ]  || { echo "  $VAULT has no .obsidian/ — point at the vault itself"; exit 1; }
[ -x "$REPO/bin/ocrshot" ] || { echo "  missing $REPO/bin/ocrshot — run ./build.sh first"; exit 1; }

# Pre-flight: launchd inherits no Full Disk Access. If we cannot list the vault
# now, the agent will not be able to either — fail loudly rather than silently.
if ! ls "$VAULT" >/dev/null 2>&1; then
  echo "  cannot read $VAULT"
  echo "  Grant Full Disk Access to /usr/bin/python3 and $REPO/bin/ocrshot"
  echo "  (System Settings > Privacy & Security > Full Disk Access; use Cmd-Shift-G to type a path)"
  exit 1
fi

mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$REPO/scripts/build_ocr.py</string>
    <string>$VAULT</string>
    <string>--quiet</string>
  </array>
  <key>StartInterval</key><integer>$INTERVAL</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>ProcessType</key><string>Background</string>
  <key>LowPriorityIO</key><true/>
</dict>
</plist>
PLIST_EOF

plutil -lint "$PLIST" >/dev/null
unload
launchctl bootstrap "gui/$UID" "$PLIST" 2>/dev/null || launchctl load "$PLIST"

echo "  installed $LABEL"
echo "    vault    $VAULT"
echo "    every    ${INTERVAL}s"
echo "    log      $LOG"
echo "    status   launchctl print gui/$UID/$LABEL | head -20"
echo "    remove   ./scripts/install-agent.sh --uninstall"
