"""GNOME autostart entry and crash-loop protection.

Autostart uses the XDG autostart spec (~/.config/autostart), which GNOME
honours after graphical login on both Wayland and X11. Nothing outside the
user's home directory is touched.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path

from living_room import APP_NAME
from living_room.config import paths
from living_room.config.store import atomic_write_json

log = logging.getLogger(__name__)

AUTOSTART_NAME = "living-room.desktop"
CRASH_LIMIT = 3          # consecutive unclean exits ...
CRASH_WINDOW_S = 300     # ... within this many seconds disable autostart launches

AUTOSTART_TEMPLATE = """[Desktop Entry]
Type=Application
Name={name}
Comment=Controller-first TV launcher
Exec={exec} --autostart
Icon=io.github.spikethedragon40k.LivingRoom
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=2
"""


def exec_path() -> str:
    """Absolute path of the launcher command; ~/.local/bin may not be on PATH yet at login."""
    found = os.environ.get("LIVING_ROOM_EXEC") or shutil.which("living-room")
    return found or str(Path.home() / ".local/bin/living-room")


def autostart_file() -> Path:
    return paths.autostart_dir() / AUTOSTART_NAME


def is_enabled() -> bool:
    path = autostart_file()
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "X-GNOME-Autostart-enabled=false" not in text and "Hidden=true" not in text


def set_enabled(enabled: bool) -> None:
    path = autostart_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        content = AUTOSTART_TEMPLATE.format(name=APP_NAME, exec=exec_path())
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        log.info("Autostart enabled: %s", path)
    else:
        try:
            path.unlink()
            log.info("Autostart disabled: removed %s", path)
        except FileNotFoundError:
            pass


# -- crash-loop guard ------------------------------------------------------
def _session_file() -> Path:
    return paths.state_dir() / "session.json"


def _read_session() -> dict:
    try:
        data = json.loads(_session_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_start(now: float | None = None) -> int:
    """Mark a session as running. Returns the number of recent unclean exits."""
    now = time.time() if now is None else now
    data = _read_session()
    crashes = [t for t in data.get("crashes", []) if isinstance(t, (int, float)) and now - t < CRASH_WINDOW_S]
    if data.get("running"):
        crashes.append(data.get("started", now))
    try:
        atomic_write_json(_session_file(), {"running": True, "started": now, "crashes": crashes})
    except OSError as exc:
        log.warning("Cannot write session state: %s", exc)
    return len(crashes)


def record_clean_exit() -> None:
    try:
        atomic_write_json(_session_file(), {"running": False, "crashes": []})
    except OSError as exc:
        log.warning("Cannot write session state: %s", exc)


def crash_loop_detected(now: float | None = None) -> bool:
    now = time.time() if now is None else now
    data = _read_session()
    crashes = [t for t in data.get("crashes", []) if isinstance(t, (int, float)) and now - t < CRASH_WINDOW_S]
    if data.get("running"):
        crashes.append(data.get("started", now))
    return len(crashes) >= CRASH_LIMIT
