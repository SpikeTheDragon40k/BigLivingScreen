#!/usr/bin/env bash
# Remove Living Room from the current user's account.
#
#   scripts/uninstall.sh          remove the app, keep your preferences
#   scripts/uninstall.sh --purge  also delete ~/.config/living-room and logs
#
# Your own .desktop shortcuts, scripts and icons are never touched.
set -euo pipefail

APP_ID="io.github.spikethedragon40k.LivingRoom"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1

pkill -f "python3 -m living_room" 2>/dev/null || true

remove() {
  if [[ -e "$1" ]]; then rm -rf -- "$1"; echo "removed $1"; fi
}

remove "$CONFIG_HOME/autostart/living-room.desktop"
remove "$DATA_HOME/applications/$APP_ID.desktop"
remove "$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"
remove "$HOME/.local/bin/living-room"
remove "$DATA_HOME/living-room"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$DATA_HOME/applications" || true

if [[ $PURGE -eq 1 ]]; then
  remove "$CONFIG_HOME/living-room"
  remove "$STATE_HOME/living-room"
else
  echo "Kept preferences in $CONFIG_HOME/living-room (use --purge to delete them)."
fi
echo "Living Room uninstalled. System packages were left installed."
