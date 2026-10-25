"""Toolkit-independent input logic: actions, dead zones and repeat timing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    ACTIVATE = "activate"
    BACK = "back"
    FAVORITE = "favorite"
    OPTIONS = "options"
    PREV_SECTION = "prev_section"
    NEXT_SECTION = "next_section"
    SETTINGS = "settings"
    HOME = "home"
    SEARCH = "search"


DIRECTIONS = (Action.UP, Action.DOWN, Action.LEFT, Action.RIGHT)

BINDABLE_ACTIONS = [
    (Action.ACTIVATE, "Select / Launch"),
    (Action.BACK, "Back"),
    (Action.FAVORITE, "Add / remove favorite"),
    (Action.OPTIONS, "Application options"),
    (Action.PREV_SECTION, "Previous section"),
    (Action.NEXT_SECTION, "Next section"),
    (Action.SETTINGS, "Settings"),
    (Action.HOME, "Home / return to launcher"),
    (Action.SEARCH, "Search"),
]

DPAD_BUTTONS = {
    "dpup": Action.UP,
    "dpdown": Action.DOWN,
    "dpleft": Action.LEFT,
    "dpright": Action.RIGHT,
}

# Physical labels per controller family, keyed by SDL's normalized button names.
# SDL names buttons by position ("a" = bottom face button) for Xbox/PlayStation.
BUTTON_LABELS = {
    "xbox": {"a": "A", "b": "B", "x": "X", "y": "Y", "back": "View", "start": "Menu",
             "guide": "Xbox", "leftshoulder": "LB", "rightshoulder": "RB",
             "leftstick": "LS", "rightstick": "RS", "misc1": "Share"},
    "playstation": {"a": "✕", "b": "○", "x": "□", "y": "△", "back": "Share", "start": "Options",
                    "guide": "PS", "leftshoulder": "L1", "rightshoulder": "R1",
                    "leftstick": "L3", "rightstick": "R3", "touchpad": "Touchpad", "misc1": "Mic"},
    "nintendo": {"a": "A", "b": "B", "x": "X", "y": "Y", "back": "−", "start": "+",
                 "guide": "Home", "leftshoulder": "L", "rightshoulder": "R",
                 "leftstick": "LS", "rightstick": "RS", "misc1": "Capture"},
}
KEYBOARD_LABELS = {
    Action.ACTIVATE: "Enter", Action.BACK: "Esc", Action.FAVORITE: "F", Action.OPTIONS: "O",
    Action.PREV_SECTION: "PgUp", Action.NEXT_SECTION: "PgDn", Action.SETTINGS: "F1",
    Action.HOME: "Home", Action.SEARCH: "/",
}


def button_label(family: str, button: str) -> str:
    labels = BUTTON_LABELS.get(family, BUTTON_LABELS["xbox"])
    return labels.get(button, button.upper() if len(button) <= 2 else button.capitalize())


@dataclass
class _Held:
    direction: Action
    since: float
    last: float
    repeating: bool = False


class Repeater:
    """Turns held directions into navigation events with initial delay + repeat.

    Each physical source (e.g. "ctrl:3:dpad", "ctrl:3:stick") is tracked
    separately so one input never produces two events.
    """

    def __init__(self, delay: float = 0.4, interval: float = 0.13):
        self.delay = delay
        self.interval = interval
        self._held: dict[str, _Held] = {}

    def press(self, source: str, direction: Action, now: float) -> list[Action]:
        held = self._held.get(source)
        if held and held.direction == direction:
            return []
        self._held[source] = _Held(direction, now, now)
        return [direction]

    def release(self, source: str) -> None:
        self._held.pop(source, None)

    def release_prefix(self, prefix: str) -> None:
        for key in [k for k in self._held if k.startswith(prefix)]:
            del self._held[key]

    def clear(self) -> None:
        self._held.clear()

    def tick(self, now: float) -> list[Action]:
        out = []
        for held in self._held.values():
            if not held.repeating:
                if now - held.since >= self.delay:
                    held.repeating = True
                    held.last = now
                    out.append(held.direction)
            elif now - held.last >= self.interval:
                held.last = now
                out.append(held.direction)
        return out

    @property
    def active(self) -> bool:
        return bool(self._held)


class StickTracker:
    """Maps analog stick position to a single direction with hysteresis."""

    def __init__(self, deadzone: float = 0.5):
        self.deadzone = deadzone
        self.release_zone = deadzone * 0.7
        self.x = 0.0
        self.y = 0.0
        self.direction: Action | None = None

    def update(self, axis: str, raw: int) -> Action | None:
        value = max(-1.0, min(1.0, raw / 32767.0))
        if axis == "x":
            self.x = value
        else:
            self.y = value
        ax, ay = abs(self.x), abs(self.y)
        magnitude = max(ax, ay)
        threshold = self.release_zone if self.direction else self.deadzone
        if magnitude < threshold:
            self.direction = None
        elif ax >= ay:
            self.direction = Action.RIGHT if self.x > 0 else Action.LEFT
        else:
            self.direction = Action.DOWN if self.y > 0 else Action.UP
        return self.direction


def resolve_action(bindings: dict[str, str], button: str) -> Action | None:
    if button in DPAD_BUTTONS:
        return DPAD_BUTTONS[button]
    name = bindings.get(button)
    if not name:
        return None
    try:
        return Action(name)
    except ValueError:
        return None
