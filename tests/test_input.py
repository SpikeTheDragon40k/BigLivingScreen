from living_room.config.store import DEFAULT_BINDINGS
from living_room.controllers.input import (
    Action, Repeater, StickTracker, button_label, resolve_action,
)


def test_press_emits_once_then_repeats_after_delay():
    r = Repeater(delay=0.4, interval=0.1)
    assert r.press("pad", Action.DOWN, 0.0) == [Action.DOWN]
    assert r.press("pad", Action.DOWN, 0.05) == []  # duplicate event: no double navigation
    assert r.tick(0.2) == []
    assert r.tick(0.41) == [Action.DOWN]
    assert r.tick(0.45) == []
    assert r.tick(0.52) == [Action.DOWN]
    r.release("pad")
    assert r.tick(2.0) == []


def test_direction_change_emits_immediately():
    r = Repeater()
    r.press("pad", Action.LEFT, 0.0)
    assert r.press("pad", Action.UP, 0.1) == [Action.UP]


def test_sources_are_independent_and_release_prefix():
    r = Repeater(delay=0.1, interval=0.1)
    r.press("ctrl:1:stick", Action.LEFT, 0.0)
    r.press("ctrl:2:stick", Action.RIGHT, 0.0)
    assert sorted(r.tick(0.11)) == sorted([Action.LEFT, Action.RIGHT])
    r.release_prefix("ctrl:1:")  # controller 1 unplugged mid-hold
    assert r.tick(0.25) == [Action.RIGHT]


def test_stick_deadzone_and_hysteresis():
    s = StickTracker(deadzone=0.5)
    assert s.update("x", 10000) is None           # ~0.3: inside dead zone
    assert s.update("x", 20000) == Action.RIGHT   # ~0.61: past threshold
    assert s.update("x", 13000) == Action.RIGHT   # ~0.40: still held (hysteresis)
    assert s.update("x", 9000) is None            # ~0.27: released
    assert s.update("y", -30000) == Action.UP
    s.update("y", 0)
    s.update("x", 25000)
    assert s.update("y", 26000) == Action.DOWN    # dominant axis wins on diagonals


def test_stick_noise_does_not_flap():
    s = StickTracker(deadzone=0.5)
    states = [s.update("x", v) for v in (17000, 16000, 17500, 15000, 16500)]
    assert states == [Action.RIGHT] * 5


def test_resolve_action_uses_bindings_and_fixed_dpad():
    assert resolve_action(DEFAULT_BINDINGS, "a") == Action.ACTIVATE
    assert resolve_action(DEFAULT_BINDINGS, "dpup") == Action.UP
    assert resolve_action(DEFAULT_BINDINGS, "paddle1") is None
    assert resolve_action({"a": "bogus"}, "a") is None
    assert resolve_action({"x": "activate"}, "x") == Action.ACTIVATE


def test_button_labels_per_family():
    assert button_label("playstation", "a") == "✕"
    assert button_label("xbox", "leftshoulder") == "LB"
    assert button_label("unknown", "b") == "B"
    assert button_label("xbox", "paddle1") == "Paddle1"
