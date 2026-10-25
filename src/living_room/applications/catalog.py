"""Application discovery through Gio's XDG desktop-entry implementation.

Gio.AppInfo.get_all() already scans every XDG data dir (including
~/.local/share/applications, /var/lib/flatpak/exports/share and
/var/lib/snapd/desktop when they are on XDG_DATA_DIRS), resolves duplicate
desktop IDs by precedence, drops Hidden=true entries and entries whose
TryExec is missing. should_show() then applies NoDisplay, OnlyShowIn and
NotShowIn for the current desktop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from living_room import APP_ID  # noqa: E402

log = logging.getLogger(__name__)

FALLBACK_ICON = "application-x-executable"


@dataclass
class AppEntry:
    id: str
    name: str
    info: Gio.DesktopAppInfo = field(repr=False)
    description: str = ""
    keywords: list[str] = field(default_factory=list)

    @property
    def icon(self) -> Gio.Icon | None:
        return self.info.get_icon()

    @property
    def is_flatpak(self) -> bool:
        return bool(self.info.get_string("X-Flatpak"))

    def actions(self) -> list[tuple[str, str]]:
        result = []
        for action in self.info.list_actions() or []:
            try:
                result.append((action, self.info.get_action_name(action) or action))
            except Exception:
                continue
        return result

    def matches(self, query: str) -> bool:
        q = query.casefold().strip()
        if not q:
            return True
        haystack = " ".join([self.name, self.id, self.description, *self.keywords]).casefold()
        return all(part in haystack for part in q.split())


def _entry_from_info(info: Gio.AppInfo) -> AppEntry | None:
    try:
        if not isinstance(info, Gio.DesktopAppInfo):
            return None
        app_id = info.get_id()
        if not app_id or app_id.startswith(APP_ID):
            return None
        if not info.should_show():
            return None
        # An entry must be launchable: either a command line or D-Bus activation.
        if not info.get_commandline() and not info.get_boolean("DBusActivatable"):
            return None
        name = info.get_name() or info.get_display_name()
        if not name:
            return None
        return AppEntry(
            id=app_id,
            name=name,
            info=info,
            description=info.get_description() or "",
            keywords=list(info.get_keywords() or []),
        )
    except Exception as exc:  # malformed entries must never break discovery
        log.warning("Skipping invalid desktop entry: %s", exc)
        return None


def discover() -> list[AppEntry]:
    entries: dict[str, AppEntry] = {}
    for info in Gio.AppInfo.get_all():
        entry = _entry_from_info(info)
        if entry and entry.id not in entries:
            entries[entry.id] = entry
    return sorted(entries.values(), key=lambda e: (e.name.casefold(), e.id))


def lookup(app_id: str) -> AppEntry | None:
    """Look up an entry even if it is NoDisplay (used for favorites)."""
    try:
        info = Gio.DesktopAppInfo.new(app_id)
    except (TypeError, GLib.Error):
        info = None
    if info is None:
        return None
    return AppEntry(id=app_id, name=info.get_name() or app_id, info=info,
                    description=info.get_description() or "")


class Catalog:
    """Keeps the application list current using Gio.AppInfoMonitor."""

    def __init__(self) -> None:
        self.apps: list[AppEntry] = []
        self._by_id: dict[str, AppEntry] = {}
        self._listeners: list[Callable[[], None]] = []
        self._monitor = Gio.AppInfoMonitor.get()
        self._monitor.connect("changed", self._on_changed)
        self._pending = 0
        self.refresh()

    def connect(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def refresh(self) -> None:
        self.apps = discover()
        self._by_id = {a.id: a for a in self.apps}
        log.info("Discovered %d applications", len(self.apps))

    def get(self, app_id: str) -> AppEntry | None:
        entry = self._by_id.get(app_id)
        return entry if entry is not None else lookup(app_id)

    def ids(self) -> set[str]:
        return set(self._by_id)

    def _on_changed(self, _monitor) -> None:
        # Package managers touch many files at once; debounce.
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(800, self._apply_change)

    def _apply_change(self) -> bool:
        self._pending = 0
        self.refresh()
        for cb in list(self._listeners):
            cb()
        return GLib.SOURCE_REMOVE
