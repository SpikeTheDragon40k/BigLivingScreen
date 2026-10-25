"""Launch desktop entries through Gio, never through a shell.

Gio expands Exec field codes, applies quoting, handles DBusActivatable and
Flatpak entries, and passes the activation token from the launch context so
the new app may take focus on Wayland.
"""

from __future__ import annotations

import logging
from typing import Callable

from gi.repository import Gio, GLib

from living_room.applications.catalog import AppEntry

log = logging.getLogger(__name__)


class Launcher:
    def __init__(self, context_factory: Callable[[], Gio.AppLaunchContext | None]):
        self._context_factory = context_factory
        self.running: dict[int, str] = {}  # pid -> app name
        self.on_exit: Callable[[str], None] | None = None

    def launch(self, entry: AppEntry, action: str | None = None) -> tuple[bool, str]:
        """Returns (ok, message). Failures are logged and reported, never raised."""
        ctx = self._context_factory()
        try:
            if action:
                entry.info.launch_action(action, ctx)
            else:
                flags = GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD
                entry.info.launch_uris_as_manager([], ctx, flags, None, None, self._on_pid, entry.name)
        except GLib.Error as exc:
            log.error("Failed to launch %s: %s", entry.id, exc.message)
            return False, f"Could not start {entry.name}: {exc.message}"
        except Exception as exc:
            log.exception("Failed to launch %s", entry.id)
            return False, f"Could not start {entry.name}: {exc}"
        log.info("Launched %s%s", entry.id, f" (action {action})" if action else "")
        return True, f"Starting {entry.name}…"

    def _on_pid(self, _info, pid: int, name: str) -> None:
        if pid <= 0:
            return
        self.running[pid] = name
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, pid, self._on_child_exit, name)

    def _on_child_exit(self, pid: int, status: int, name: str) -> None:
        self.running.pop(pid, None)
        GLib.spawn_close_pid(pid)
        log.info("%s exited (status %s)", name, status)
        if self.on_exit:
            self.on_exit(name)
