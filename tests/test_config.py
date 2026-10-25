import json

from living_room.config.store import DEFAULT_BINDINGS, Config, atomic_write_json


def make(tmp_path):
    return Config(tmp_path / "living-room" / "config.json").load()


def test_defaults_when_missing(tmp_path):
    cfg = make(tmp_path)
    assert cfg.favorites == []
    assert cfg.get("fullscreen") is True
    assert cfg.bindings == DEFAULT_BINDINGS


def test_favorites_persist_in_order(tmp_path):
    cfg = make(tmp_path)
    for app in ("kodi.desktop", "streaming-netflix.desktop", "streaming-prime.desktop"):
        cfg.add_favorite(app)
    cfg.move_favorite("streaming-prime.desktop", -2)
    again = make(tmp_path)
    assert again.favorites == ["streaming-prime.desktop", "kodi.desktop", "streaming-netflix.desktop"]


def test_toggle_and_remove(tmp_path):
    cfg = make(tmp_path)
    assert cfg.toggle_favorite("a.desktop") is True
    assert cfg.toggle_favorite("a.desktop") is False
    assert make(tmp_path).favorites == []


def test_move_clamps_at_edges(tmp_path):
    cfg = make(tmp_path)
    cfg.add_favorite("a")
    cfg.add_favorite("b")
    assert cfg.move_favorite("a", -1) is False
    assert cfg.move_favorite("b", 5) is False
    assert cfg.move_favorite("a", 1) is True
    assert cfg.favorites == ["b", "a"]


def test_seed_only_installed_and_only_once(tmp_path):
    cfg = make(tmp_path)
    cfg.seed_favorites({"kodi.desktop", "streaming-disney.desktop", "firefox.desktop"})
    assert cfg.favorites == ["kodi.desktop", "streaming-disney.desktop"]
    cfg.remove_favorite("kodi.desktop")
    cfg.seed_favorites({"kodi.desktop"})
    assert cfg.favorites == ["streaming-disney.desktop"]


def test_missing_favorites_are_kept(tmp_path):
    cfg = make(tmp_path)
    cfg.add_favorite("uninstalled.desktop")
    assert make(tmp_path).favorites == ["uninstalled.desktop"]


def test_hidden(tmp_path):
    cfg = make(tmp_path)
    cfg.hide("x.desktop")
    assert make(tmp_path).is_hidden("x.desktop")
    cfg.unhide("x.desktop")
    assert not make(tmp_path).is_hidden("x.desktop")


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "living-room" / "config.json"
    path.parent.mkdir(parents=True)
    path.write_text("{ not json")
    cfg = Config(path).load()
    assert cfg.favorites == []
    assert list(path.parent.glob("config.json.corrupt-*"))


def test_malformed_values_fall_back(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"favorites": ["a", 3, "a", None, "b"], "settings": {
        "fullscreen": "yes", "scale": 1.3, "animations": False}, "bindings": {}}))
    cfg = Config(path).load()
    assert cfg.favorites == ["a", "b"]
    assert cfg.get("fullscreen") is True
    assert cfg.get("scale") == 1.3
    assert cfg.get("animations") is False
    assert cfg.bindings == DEFAULT_BINDINGS


def test_atomic_write_leaves_no_temp_files(tmp_path):
    path = tmp_path / "x.json"
    atomic_write_json(path, {"a": 1})
    atomic_write_json(path, {"a": 2})
    assert json.loads(path.read_text()) == {"a": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]


def test_bindings_one_button_per_action(tmp_path):
    cfg = make(tmp_path)
    assert cfg.bind("x", "favorite") is None
    assert cfg.buttons_for("favorite") == ["x"]
    assert "y" not in cfg.bindings
    assert make(tmp_path).bindings["x"] == "favorite"


def test_cannot_unbind_last_activate_or_back(tmp_path):
    cfg = make(tmp_path)
    assert cfg.bind("a", "favorite") is not None
    assert cfg.bindings["a"] == "activate"
    assert cfg.bind("b", "search") is not None
    # Moving activate to another button first makes it allowed.
    assert cfg.bind("x", "activate") is None
    assert cfg.bind("a", "favorite") is None


def test_reset(tmp_path):
    cfg = make(tmp_path)
    cfg.add_favorite("a")
    cfg.set("scale", 1.5)
    cfg.reset()
    again = make(tmp_path)
    assert again.favorites == []
    assert again.get("scale") == 1.0


def test_listener_called(tmp_path):
    cfg = make(tmp_path)
    seen = []
    cfg.connect(seen.append)
    cfg.set("animations", False)
    cfg.add_favorite("a")
    assert seen == ["settings.animations", "favorites"]
