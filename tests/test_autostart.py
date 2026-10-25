from living_room.config import autostart


def test_enable_disable_roundtrip():
    autostart.set_enabled(False)
    assert not autostart.is_enabled()
    autostart.set_enabled(True)
    path = autostart.autostart_file()
    assert path.name == "living-room.desktop"
    assert path.parent.name == "autostart"
    text = path.read_text()
    exec_line = next(l for l in text.splitlines() if l.startswith("Exec="))
    assert exec_line.endswith(" --autostart") and exec_line[5] == "/"
    assert "Name=Living Room" in text
    assert autostart.is_enabled()
    autostart.set_enabled(False)
    assert not path.exists()
    autostart.set_enabled(False)  # idempotent


def test_user_disabled_entry_is_respected():
    autostart.set_enabled(True)
    path = autostart.autostart_file()
    path.write_text(path.read_text().replace("enabled=true", "enabled=false"))
    assert not autostart.is_enabled()
    autostart.set_enabled(False)


def test_crash_loop_detection():
    autostart.record_clean_exit()
    assert autostart.record_start(now=1000) == 0
    assert not autostart.crash_loop_detected(now=1001)
    autostart.record_start(now=1010)  # previous run never exited cleanly
    autostart.record_start(now=1020)
    assert autostart.crash_loop_detected(now=1030)
    autostart.record_clean_exit()
    assert not autostart.crash_loop_detected(now=1040)


def test_old_crashes_expire():
    autostart.record_clean_exit()
    autostart.record_start(now=0)
    autostart.record_start(now=10)
    autostart.record_start(now=20)
    assert not autostart.crash_loop_detected(now=10_000)
