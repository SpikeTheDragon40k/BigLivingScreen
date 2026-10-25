"""Persistent user preferences stored as JSON with atomic writes."""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from living_room.config import paths

log = logging.getLogger(__name__)

CONFIG_VERSION = 1

# Desktop IDs offered as favorites on first run, if installed.
SEED_FAVORITES = [
    "kodi.desktop",
    "net.retrodeck.retrodeck.desktop",
    "streaming-netflix.desktop",
    "streaming-prime.desktop",
    "streaming-disney.desktop",
]

# SDL controller button name -> action name. D-pad and left stick always navigate.
DEFAULT_BINDINGS = {
    "a": "activate",
    "b": "back",
    "x": "options",
    "y": "favorite",
    "leftshoulder": "prev_section",
    "rightshoulder": "next_section",
    "start": "settings",
    "guide": "home",
    "back": "search",
}

DEFAULT_SETTINGS = {
    "fullscreen": True,
    "animations": True,
    "show_clock": True,
    "scale": 1.0,
    "background": "aurora",
    "guide_returns": True,
    "stick_deadzone": 0.5,
    "repeat_delay_ms": 400,
    "repeat_interval_ms": 130,
}

SCALE_STEPS = [0.75, 0.85, 1.0, 1.15, 1.3, 1.5]


def default_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "favorites": [],
        "favorites_initialized": False,
        "hidden": [],
        "settings": dict(DEFAULT_SETTINGS),
        "bindings": dict(DEFAULT_BINDINGS),
    }


def atomic_write_json(path: Path, data: Any) -> None:
    """Write JSON so that readers see either the old or the new file, never a partial one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    try:
        dir_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def _merge(data: Any) -> dict[str, Any]:
    """Merge loaded data over defaults, dropping anything malformed."""
    cfg = default_config()
    if not isinstance(data, dict):
        return cfg
    for key in ("favorites", "hidden"):
        value = data.get(key)
        if isinstance(value, list):
            seen: list[str] = []
            for item in value:
                if isinstance(item, str) and item and item not in seen:
                    seen.append(item)
            cfg[key] = seen
    cfg["favorites_initialized"] = bool(data.get("favorites_initialized", False))
    settings = data.get("settings")
    if isinstance(settings, dict):
        for key, default in DEFAULT_SETTINGS.items():
            value = settings.get(key, default)
            if isinstance(default, bool):
                ok = isinstance(value, bool)
            elif isinstance(default, (int, float)):
                ok = isinstance(value, (int, float)) and not isinstance(value, bool)
            else:
                ok = isinstance(value, type(default))
            cfg["settings"][key] = value if ok else default
    bindings = data.get("bindings")
    if isinstance(bindings, dict) and bindings:
        cfg["bindings"] = {
            str(k): str(v) for k, v in bindings.items() if isinstance(k, str) and isinstance(v, str)
        }
    return cfg


class Config:
    """In-memory config with change notification and atomic persistence."""

    def __init__(self, path: Path | None = None):
        self.path = path or paths.config_file()
        self.data = default_config()
        self._listeners: list[Callable[[str], None]] = []

    # -- persistence -------------------------------------------------------
    def load(self) -> "Config":
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return self
        except OSError as exc:
            log.warning("Cannot read config %s: %s", self.path, exc)
            return self
        try:
            self.data = _merge(json.loads(raw))
        except (ValueError, TypeError) as exc:
            backup = self.path.with_name(f"{self.path.name}.corrupt-{int(time.time())}")
            log.warning("Config is corrupt (%s); moved to %s and using defaults", exc, backup)
            try:
                os.replace(self.path, backup)
            except OSError:
                pass
            self.data = default_config()
        return self

    def save(self) -> None:
        try:
            atomic_write_json(self.path, self.data)
        except OSError as exc:
            log.error("Failed to save config: %s", exc)

    # -- notifications -----------------------------------------------------
    def connect(self, callback: Callable[[str], None]) -> None:
        self._listeners.append(callback)

    def _changed(self, what: str) -> None:
        self.save()
        for cb in list(self._listeners):
            try:
                cb(what)
            except Exception:  # a broken listener must not break saving
                log.exception("Config listener failed")

    # -- settings ----------------------------------------------------------
    def get(self, key: str) -> Any:
        return self.data["settings"].get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any) -> None:
        if self.data["settings"].get(key) == value:
            return
        self.data["settings"][key] = value
        self._changed(f"settings.{key}")

    # -- favorites ---------------------------------------------------------
    @property
    def favorites(self) -> list[str]:
        return list(self.data["favorites"])

    def is_favorite(self, app_id: str) -> bool:
        return app_id in self.data["favorites"]

    def seed_favorites(self, installed_ids: set[str]) -> None:
        """On first run, pre-populate favorites with known media apps that exist."""
        if self.data["favorites_initialized"]:
            return
        self.data["favorites"] = [i for i in SEED_FAVORITES if i in installed_ids]
        self.data["favorites_initialized"] = True
        self._changed("favorites")

    def add_favorite(self, app_id: str) -> None:
        if app_id not in self.data["favorites"]:
            self.data["favorites"].append(app_id)
            self.data["favorites_initialized"] = True
            self._changed("favorites")

    def remove_favorite(self, app_id: str) -> None:
        if app_id in self.data["favorites"]:
            self.data["favorites"].remove(app_id)
            self._changed("favorites")

    def toggle_favorite(self, app_id: str) -> bool:
        if self.is_favorite(app_id):
            self.remove_favorite(app_id)
            return False
        self.add_favorite(app_id)
        return True

    def move_favorite(self, app_id: str, delta: int) -> bool:
        favs = self.data["favorites"]
        if app_id not in favs:
            return False
        i = favs.index(app_id)
        j = max(0, min(len(favs) - 1, i + delta))
        if i == j:
            return False
        favs.insert(j, favs.pop(i))
        self._changed("favorites")
        return True

    # -- hidden apps -------------------------------------------------------
    @property
    def hidden(self) -> list[str]:
        return list(self.data["hidden"])

    def is_hidden(self, app_id: str) -> bool:
        return app_id in self.data["hidden"]

    def hide(self, app_id: str) -> None:
        if app_id not in self.data["hidden"]:
            self.data["hidden"].append(app_id)
            self._changed("hidden")

    def unhide(self, app_id: str) -> None:
        if app_id in self.data["hidden"]:
            self.data["hidden"].remove(app_id)
            self._changed("hidden")

    # -- bindings ----------------------------------------------------------
    @property
    def bindings(self) -> dict[str, str]:
        return dict(self.data["bindings"])

    def buttons_for(self, action: str) -> list[str]:
        return [b for b, a in self.data["bindings"].items() if a == action]

    def bind(self, button: str, action: str) -> str | None:
        """Bind button to action (one button per action). Returns an error message or None."""
        bindings = self.data["bindings"]
        previous = bindings.get(button)
        if previous in ("activate", "back") and previous != action and self.buttons_for(previous) == [button]:
            return f"'{button}' is the only button for {previous}; bind {previous} elsewhere first."
        for b in self.buttons_for(action):
            del bindings[b]
        bindings[button] = action
        self._changed("bindings")
        return None

    def reset_bindings(self) -> None:
        self.data["bindings"] = dict(DEFAULT_BINDINGS)
        self._changed("bindings")

    def reset(self) -> None:
        """Reset all preferences, keeping favorites seeding available again."""
        self.data = default_config()
        self._changed("all")

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.data)
