#!/usr/bin/env bash
# Install (or remove) the daily discovery job for the current macOS user.
#   scripts/install-daily-discovery.sh 07:30     # run every day at 07:30
#   scripts/install-daily-discovery.sh --uninstall
# The Mac must be awake at that time (launchd runs a missed job once after wake).
set -euo pipefail

LABEL=dk.roleradar.discovery
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$TARGET"
  echo "Removed $LABEL"
  exit 0
fi

if ! [[ "${1:-}" =~ ^([01]?[0-9]|2[0-3]):([0-5][0-9])$ ]]; then
  echo "usage: $0 HH:MM | --uninstall" >&2
  exit 2
fi
hour=$((10#${BASH_REMATCH[1]}))
minute=$((10#${BASH_REMATCH[2]}))

mkdir -p "$(dirname "$TARGET")"
sed -e "s|__REPO__|$REPO|" -e "s|__HOUR__|$hour|" -e "s|__MINUTE__|$minute|" \
  "$REPO/scripts/launchd/$LABEL.plist" >"$TARGET"
plutil -lint "$TARGET" >/dev/null
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$TARGET"
printf 'Installed %s: every day at %02d:%02d (log: ~/Library/Logs/roleradar-discovery.log)\n' \
  "$LABEL" "$hour" "$minute"
