"""XDG base directory helpers (resolved at call time so tests can override)."""

import os
from pathlib import Path


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var, "")
    # The spec says relative paths must be ignored.
    if value and os.path.isabs(value):
        return Path(value)
    return Path.home() / fallback


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "living-room"


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / "living-room"


def autostart_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / "autostart"


def config_file() -> Path:
    return config_dir() / "config.json"
