#!/usr/bin/env bash
# Install Living Room for the current user only. Nothing outside $HOME is
# written, except system packages if you explicitly agree to install them.
#
#   scripts/install.sh            install (asks before using sudo apt)
#   scripts/install.sh --deps     also install missing Ubuntu packages without asking
#   scripts/install.sh --autostart  also start Living Room after GNOME login
set -euo pipefail

APP_ID="io.github.spikethedragon40k.LivingRoom"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
LIB_DIR="$DATA_HOME/living-room/lib"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/living-room"
DESKTOP="$DATA_HOME/applications/$APP_ID.desktop"
ICON="$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"
PYTHON="${LIVING_ROOM_PYTHON:-/usr/bin/python3}"
PACKAGES=(python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-sdl2)

AUTO_DEPS=0
AUTOSTART=0
for arg in "$@"; do
  case "$arg" in
    --deps) AUTO_DEPS=1 ;;
    --autostart) AUTOSTART=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ $EUID -eq 0 ]]; then
  echo "Run this as your normal user, not root. It only installs into your home directory." >&2
  exit 1
fi

check_deps() {
  "$PYTHON" - <<'EOF'
import sys
missing = []
try:
    import gi
    gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw  # noqa
except Exception as exc:
    missing.append(f"GTK4/libadwaita bindings ({exc})")
try:
    import sdl2  # noqa
except Exception as exc:
    missing.append(f"PySDL2 / SDL2 ({exc})")
for m in missing:
    print("  missing:", m)
sys.exit(1 if missing else 0)
EOF
}

echo "==> Checking dependencies"
if ! check_deps; then
  echo
  echo "Living Room needs these Ubuntu packages: ${PACKAGES[*]}"
  answer=n
  if [[ $AUTO_DEPS -eq 1 ]]; then
    answer=y
  elif [[ -t 0 ]]; then
    read -r -p "Install them now with 'sudo apt install'? [y/N] " answer
  fi
  if [[ $answer =~ ^[Yy]$ ]]; then
    sudo apt-get update
    sudo apt-get install -y "${PACKAGES[@]}"
    check_deps || { echo "Dependencies still missing; see README troubleshooting." >&2; exit 1; }
  else
    echo "Install them with: sudo apt install ${PACKAGES[*]}"
    if ! "$PYTHON" -c 'import gi; gi.require_version("Gtk","4.0"); gi.require_version("Adw","1")' 2>/dev/null; then
      exit 1
    fi
    echo "Continuing without controller support (keyboard still works)."
  fi
fi

echo "==> Installing application files to $LIB_DIR"
mkdir -p "$LIB_DIR" "$BIN_DIR" "$(dirname "$DESKTOP")" "$(dirname "$ICON")"
rm -rf "$LIB_DIR/living_room.new"
cp -r "$REPO_DIR/src/living_room" "$LIB_DIR/living_room.new"
find "$LIB_DIR/living_room.new" -name '__pycache__' -type d -prune -exec rm -rf {} +
rm -rf "$LIB_DIR/living_room"
mv "$LIB_DIR/living_room.new" "$LIB_DIR/living_room"

echo "==> Creating launcher command $BIN"
cat > "$BIN.tmp" <<EOF
#!/bin/sh
# Living Room launcher (installed by scripts/install.sh)
PYTHONPATH="$LIB_DIR\${PYTHONPATH:+:\$PYTHONPATH}" exec $PYTHON -m living_room "\$@"
EOF
chmod 755 "$BIN.tmp"
mv "$BIN.tmp" "$BIN"

echo "==> Installing desktop entry and icon"
sed "s|@EXEC@|$BIN|" "$REPO_DIR/data/living-room.desktop" > "$DESKTOP.tmp"
mv "$DESKTOP.tmp" "$DESKTOP"
cp "$REPO_DIR/src/living_room/assets/$APP_ID.svg" "$ICON"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$DATA_HOME/applications" || true

if [[ $AUTOSTART -eq 1 ]]; then
  echo "==> Enabling autostart"
  LIVING_ROOM_EXEC="$BIN" PYTHONPATH="$LIB_DIR" "$PYTHON" -c \
    'from living_room.config import autostart; autostart.set_enabled(True); print("   ", autostart.autostart_file())'
fi

echo
echo "Installed. Start it from the GNOME app grid ('Living Room') or run: $BIN"
echo "Windowed mode for testing: $BIN --windowed"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "Note: $BIN_DIR is not on PATH in this shell; log out and in, or use the full path.";; esac
