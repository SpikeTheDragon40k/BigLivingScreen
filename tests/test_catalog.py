from gi.repository import Gio

from living_room.applications import catalog
from living_room.applications.launcher import Launcher


def ids():
    return {a.id for a in catalog.discover()}


def test_discovers_user_streaming_shortcuts():
    found = ids()
    for app_id in ("streaming-netflix.desktop", "streaming-prime.desktop", "streaming-disney.desktop"):
        assert app_id in found


def test_discovers_system_and_flatpak_entries():
    found = ids()
    assert "kodi.desktop" in found
    assert "net.retrodeck.retrodeck.desktop" in found
    retro = next(a for a in catalog.discover() if a.id == "net.retrodeck.retrodeck.desktop")
    assert retro.is_flatpak


def test_filters_invisible_and_invalid_entries():
    found = ids()
    for app_id in ("nodisplay.desktop", "hidden.desktop", "kdeonly.desktop", "notgnome.desktop",
                   "tryexec.desktop", "broken.desktop", "garbage.desktop"):
        assert app_id not in found, app_id


def test_duplicate_ids_resolve_to_user_entry_once():
    apps = [a for a in catalog.discover() if a.id == "dup.desktop"]
    assert len(apps) == 1
    assert apps[0].name == "Duplicate User"


def test_absolute_png_icon_is_file_icon():
    netflix = next(a for a in catalog.discover() if a.id == "streaming-netflix.desktop")
    icon = netflix.icon
    assert isinstance(icon, Gio.FileIcon)
    assert icon.get_file().get_path().endswith("streaming/netflix.png")
    disney = next(a for a in catalog.discover() if a.id == "streaming-disney.desktop")
    assert disney.icon.get_file().get_path().endswith("dinsey.png")


def test_desktop_actions_listed():
    kodi = next(a for a in catalog.discover() if a.id == "kodi.desktop")
    assert kodi.actions() == [("fullscreen", "Kodi Fullscreen")]


def test_sorted_by_name():
    names = [a.name.casefold() for a in catalog.discover()]
    assert names == sorted(names)


def test_lookup_missing_returns_none():
    assert catalog.lookup("does-not-exist.desktop") is None
    assert catalog.lookup("kodi.desktop").name == "Kodi"


def test_search_matching():
    netflix = next(a for a in catalog.discover() if a.id == "streaming-netflix.desktop")
    assert netflix.matches("net")
    assert netflix.matches("NETFLIX")
    assert netflix.matches("")
    assert not netflix.matches("disney")


def test_launch_failure_is_reported_not_raised(tmp_path):
    # The program exists at discovery time but is removed before launch.
    script = tmp_path / "vanishing-app"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    entry = catalog.AppEntry("x.desktop", "Broken", Gio.DesktopAppInfo.new_from_keyfile(_keyfile(
        f"Exec={script}\n")))
    script.unlink()
    ok, message = Launcher(lambda: None).launch(entry)
    assert not ok
    assert "Broken" in message


def test_launch_success_uses_gio_without_shell(tmp_path):
    marker = tmp_path / "ran"
    # Field codes and quoting are handled by Gio; a shell metacharacter in an
    # argument must arrive literally, not be interpreted.
    entry = catalog.AppEntry("t.desktop", "Toucher", Gio.DesktopAppInfo.new_from_keyfile(_keyfile(
        f'Exec=/usr/bin/touch "{marker};rm"\n')))
    launcher = Launcher(lambda: None)
    ok, _ = launcher.launch(entry)
    assert ok
    import time
    for _ in range(50):
        if (tmp_path / "ran;rm").exists():
            break
        time.sleep(0.05)
    assert (tmp_path / "ran;rm").exists()
    assert not marker.exists()


def _keyfile(extra: str):
    from gi.repository import GLib
    kf = GLib.KeyFile()
    data = "[Desktop Entry]\nType=Application\nName=T\n" + extra
    kf.load_from_data(data, len(data.encode()), GLib.KeyFileFlags.NONE)
    return kf
