"""Isolate every test run from the real user session.

Gio caches XDG directories on first use, so the environment must be set
before anything imports gi.repository.Gio.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="living-room-tests-"))
HOME = ROOT / "home"
DATA_HOME = HOME / ".local/share"
SYSTEM = ROOT / "system"
FLATPAK = ROOT / "flatpak/exports/share"

os.environ.update({
    "HOME": str(HOME),
    "XDG_CONFIG_HOME": str(HOME / ".config"),
    "XDG_STATE_HOME": str(HOME / ".local/state"),
    "XDG_DATA_HOME": str(DATA_HOME),
    "XDG_DATA_DIRS": f"{FLATPAK}:{SYSTEM}",
    "XDG_CURRENT_DESKTOP": "GNOME",
})
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# A tiny valid PNG (1x1) for absolute-path icon tests.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def _desktop(directory: Path, name: str, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("[Desktop Entry]\nType=Application\n" + body, encoding="utf-8")


def _build_fixture() -> None:
    icons = DATA_HOME / "icons/streaming"
    icons.mkdir(parents=True, exist_ok=True)
    for icon in ("netflix", "amazon", "dinsey"):
        (icons / f"{icon}.png").write_bytes(PNG)
    user_apps = DATA_HOME / "applications"
    for app_id, name, icon in (("netflix", "Netflix", "netflix"), ("prime", "Prime Video", "amazon"),
                               ("disney", "Disney+", "dinsey")):
        _desktop(user_apps, f"streaming-{app_id}.desktop",
                 f"Name={name}\nExec=/bin/true {app_id}\nIcon={icons / icon}.png\n")
    sys_apps = SYSTEM / "applications"
    _desktop(sys_apps, "kodi.desktop", "Name=Kodi\nExec=/bin/true\nIcon=kodi\n"
             "Actions=fullscreen;\n\n[Desktop Action fullscreen]\nName=Kodi Fullscreen\nExec=/bin/true -fs\n")
    _desktop(sys_apps, "nodisplay.desktop", "Name=Hidden Helper\nExec=/bin/true\nNoDisplay=true\n")
    _desktop(sys_apps, "hidden.desktop", "Name=Deleted\nExec=/bin/true\nHidden=true\n")
    _desktop(sys_apps, "kdeonly.desktop", "Name=KDE Thing\nExec=/bin/true\nOnlyShowIn=KDE;\n")
    _desktop(sys_apps, "notgnome.desktop", "Name=Not GNOME\nExec=/bin/true\nNotShowIn=GNOME;\n")
    _desktop(sys_apps, "tryexec.desktop", "Name=Missing Binary\nExec=/bin/true\n"
             "TryExec=/nonexistent/binary-xyz\n")
    _desktop(sys_apps, "broken.desktop", "Name=Broken\n")  # no Exec: invalid
    (sys_apps / "garbage.desktop").write_text("this is not a desktop file\x00\x01", encoding="latin-1")
    # Duplicate ID: the user's copy must win over the system one.
    _desktop(sys_apps, "dup.desktop", "Name=Duplicate System\nExec=/bin/true\n")
    _desktop(user_apps, "dup.desktop", "Name=Duplicate User\nExec=/bin/true\n")
    _desktop(FLATPAK / "applications", "net.retrodeck.retrodeck.desktop",
             "Name=RetroDECK\nExec=/bin/true run net.retrodeck.retrodeck\n"
             "Icon=net.retrodeck.retrodeck\nX-Flatpak=net.retrodeck.retrodeck\n")


_build_fixture()
