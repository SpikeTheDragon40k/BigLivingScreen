"""Pages and dialogs. Each page receives Actions via handle_action() before the
window's generic handling (spatial navigation, activate, back...)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from gi.repository import GLib, Gtk

from living_room import __version__
from living_room.config import autostart, paths
from living_room.config.store import SCALE_STEPS
from living_room.controllers.input import BINDABLE_ACTIONS, DIRECTIONS, Action
from living_room.ui import style
from living_room.ui.widgets import (
    FOCUSABLE, AppCard, clear_box, flow_append, flowbox, make_focusable, section_label, tile,
)

if TYPE_CHECKING:
    from living_room.ui.window import LivingRoomWindow


def scrolled(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    sw = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.set_child(child)
    viewport = sw.get_child()
    if hasattr(viewport, "set_scroll_to_focus"):
        viewport.set_scroll_to_focus(False)  # the window scrolls smoothly itself
    return sw


def first_focusable(root: Gtk.Widget) -> Gtk.Widget | None:
    stack = [root]
    while stack:
        w = stack.pop(0)
        if w.has_css_class(FOCUSABLE) and w.get_visible() and w.is_sensitive():
            return w
        child = w.get_first_child()
        kids = []
        while child is not None:
            kids.append(child)
            child = child.get_next_sibling()
        stack[0:0] = kids
    return None


class Page(Gtk.Box):
    title = ""
    is_dialog = False

    def __init__(self, win: "LivingRoomWindow"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.last_focus: Gtk.Widget | None = None

    def default_focus(self) -> Gtk.Widget | None:
        return first_focusable(self)

    def sections(self) -> list[Gtk.Widget]:
        return []

    def handle_action(self, action: Action) -> bool:
        return False

    def hints(self) -> list[tuple[Action, str]]:
        return [(Action.ACTIVATE, "Select"), (Action.BACK, "Back")]

    def on_shown(self) -> None:
        pass

    def on_hidden(self) -> None:
        pass


# -- Home -------------------------------------------------------------------
class HomePage(Page):
    title = ""

    def __init__(self, win):
        super().__init__(win)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.add_css_class("lr-content")
        content.append(section_label("Favorites"))
        self.fav_flow = flowbox(2, 7)
        self.fav_empty = Gtk.Label(label="No favorites yet — highlight any application and press "
                                         "Favorite to pin it here.", xalign=0, wrap=True)
        self.fav_empty.add_css_class("lr-empty")
        content.append(self.fav_flow)
        content.append(self.fav_empty)
        content.append(section_label("All Applications"))
        self.all_flow = flowbox(3, 10)
        self.all_empty = Gtk.Label(label="No applications found.", xalign=0)
        self.all_empty.add_css_class("lr-empty")
        content.append(self.all_flow)
        content.append(self.all_empty)
        self.scroller = scrolled(content)
        self.append(self.scroller)
        self.all_cards: dict[str, AppCard] = {}
        self.rebuild()

    def sections(self):
        return [self.fav_flow, self.all_flow]

    def hints(self):
        return [(Action.ACTIVATE, "Launch"), (Action.FAVORITE, "Favorite"), (Action.OPTIONS, "Options"),
                (Action.SEARCH, "Search"), (Action.SETTINGS, "Settings")]

    def _focused_app(self) -> tuple[str | None, Gtk.Widget | None]:
        focus = self.win.focused_card()
        if focus is None:
            return None, None
        return focus.app_id, focus.get_ancestor(Gtk.FlowBox)

    def rebuild(self) -> None:
        app_id, flow = self._focused_app()
        self.rebuild_favorites(refocus=False)
        cfg, catalog, scale = self.win.config, self.win.catalog, self.win.scale
        clear_box(self.all_flow)
        self.all_cards.clear()
        apps = [a for a in catalog.apps if not cfg.is_hidden(a.id)]
        for entry in apps:
            card = AppCard(entry, entry.id, False, scale, cfg.is_favorite(entry.id))
            self.all_cards[entry.id] = card
            flow_append(self.all_flow, card)
        self.all_empty.set_visible(not apps)
        if app_id:
            self._refocus(app_id, flow)

    def rebuild_favorites(self, refocus: bool = True) -> None:
        app_id, flow = self._focused_app() if refocus else (None, None)
        clear_box(self.fav_flow)
        cfg, catalog, scale = self.win.config, self.win.catalog, self.win.scale
        favs = cfg.favorites
        for fid in favs:
            flow_append(self.fav_flow, AppCard(catalog.get(fid), fid, True, scale))
        self.fav_empty.set_visible(not favs)
        self.fav_flow.set_visible(bool(favs))
        if app_id:
            self._refocus(app_id, flow)

    def update_star(self, app_id: str) -> None:
        old = self.all_cards.get(app_id)
        if old is None:
            return
        child = old.get_parent()
        index = child.get_index() if isinstance(child, Gtk.FlowBoxChild) else -1
        had_focus = self.win.focused_card() is old
        card = AppCard(old.entry, app_id, False, self.win.scale, self.win.config.is_favorite(app_id))
        self.all_flow.remove(child)
        self.all_flow.insert(card, index)
        card.get_parent().set_focusable(False)
        self.all_cards[app_id] = card
        if had_focus:
            self.win.focus_widget(card)

    def _refocus(self, app_id: str, flow: Gtk.Widget | None) -> None:
        targets = [flow] if flow is not None else []
        targets += [self.fav_flow, self.all_flow]
        for fb in targets:
            child = fb.get_first_child() if fb else None
            while child is not None:
                card = child.get_child()
                if isinstance(card, AppCard) and card.app_id == app_id:
                    GLib.idle_add(self.win.focus_widget, card)
                    return
                child = child.get_next_sibling()

    def handle_action(self, action):
        if action == Action.HOME:
            self.scroller.get_vadjustment().set_value(0)
            target = first_focusable(self.fav_flow) if self.fav_flow.get_visible() else None
            target = target or first_focusable(self.all_flow)
            if target:
                self.win.focus_widget(target)
            return True
        return False


# -- Search -----------------------------------------------------------------
KEY_ROWS = ["ABCDEFG", "HIJKLMN", "OPQRSTU", "VWXYZ-+", "1234567", "890.&'!"]


class SearchPage(Page):
    title = "Search"

    def __init__(self, win):
        super().__init__(win)
        outer = Gtk.Box(spacing=48)
        outer.add_css_class("lr-content")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.entry = Gtk.SearchEntry(placeholder_text="Type to search…")
        self.entry.add_css_class("lr-search")
        make_focusable(self.entry)
        self.entry.connect("search-changed", lambda *_: self.update())
        left.append(self.entry)
        self.keyboard = Gtk.Grid(row_spacing=10, column_spacing=10)
        for r, row in enumerate(KEY_ROWS):
            for c, ch in enumerate(row):
                self.keyboard.attach(self._key(ch, lambda ch=ch: self._type(ch)), c, r, 1, 1)
        r = len(KEY_ROWS)
        self.keyboard.attach(self._key("Space", lambda: self._type(" ")), 0, r, 3, 1)
        self.keyboard.attach(self._key("⌫", self._backspace), 3, r, 2, 1)
        self.keyboard.attach(self._key("Clear", lambda: self.entry.set_text("")), 5, r, 2, 1)
        left.append(self.keyboard)
        outer.append(left)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        right.append(section_label("Results"))
        self.results = flowbox(2, 6)
        self.empty = Gtk.Label(label="No matching applications.", xalign=0)
        self.empty.add_css_class("lr-empty")
        right.append(self.results)
        right.append(self.empty)
        outer.append(right)
        self.scroller = scrolled(outer)
        self.append(self.scroller)
        self.update()

    def _key(self, label: str, cb: Callable[[], None]) -> Gtk.Button:
        b = Gtk.Button(label=label)
        make_focusable(b)
        b.add_css_class("tile")
        b.add_css_class("key")
        b.connect("clicked", lambda *_: cb())
        return b

    def _type(self, ch: str) -> None:
        self.entry.set_text(self.entry.get_text() + ch.lower())
        self.entry.set_position(-1)

    def _backspace(self) -> None:
        self.entry.set_text(self.entry.get_text()[:-1])

    def default_focus(self):
        return first_focusable(self.keyboard)

    def sections(self):
        return [self.keyboard, self.results]

    def hints(self):
        return [(Action.ACTIVATE, "Select"), (Action.BACK, "Back"), (Action.FAVORITE, "Favorite"),
                (Action.OPTIONS, "Options"), (Action.NEXT_SECTION, "Results")]

    def on_shown(self):
        self.update()

    def update(self) -> None:
        clear_box(self.results)
        query = self.entry.get_text()
        cfg = self.win.config
        matches = [a for a in self.win.catalog.apps if a.matches(query)]
        if not query:
            matches = [a for a in matches if not cfg.is_hidden(a.id)]
        for entry in matches[:48]:
            flow_append(self.results, AppCard(entry, entry.id, False, self.win.scale,
                                              cfg.is_favorite(entry.id)))
        self.empty.set_visible(not matches)

    def handle_action(self, action):
        if action == Action.SEARCH:
            self.win.focus_widget(self.entry)
            return True
        return False


# -- Dialog base ------------------------------------------------------------
class Dialog(Page):
    is_dialog = True

    def __init__(self, win, title: str, subtitle: str = ""):
        super().__init__(win)
        self.add_css_class("lr-dialog")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_size_request(int(720 * win.scale), -1)
        self.set_spacing(14)
        heading = Gtk.Label(label=title, xalign=0, wrap=True)
        heading.add_css_class("lr-page-title")
        super().append(heading)
        if subtitle:
            sub = Gtk.Label(label=subtitle, xalign=0, wrap=True)
            sub.add_css_class("lr-subtitle")
            super().append(sub)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        sw = scrolled(self.body)
        sw.set_propagate_natural_height(True)
        sw.set_max_content_height(int(640 * win.scale))
        super().append(sw)

    def append(self, child):
        self.body.append(child)

    def hints(self):
        return [(Action.ACTIVATE, "Select"), (Action.BACK, "Close")]


class OptionsDialog(Dialog):
    def __init__(self, win, app_id: str):
        entry = win.catalog.get(app_id)
        super().__init__(win, entry.name if entry else app_id,
                         (entry.description if entry else "This application is not installed."))
        self.app_id = app_id
        cfg = win.config
        if entry:
            self.append(tile("Launch", lambda: (win.close_dialog(), win.launch(app_id))))
            for action_id, label in entry.actions():
                self.append(tile(label, lambda a=action_id: (win.close_dialog(), win.launch(app_id, a))))
        fav = cfg.is_favorite(app_id)
        self.append(tile("Remove from favorites" if fav else "Add to favorites",
                         lambda: (win.close_dialog(), win.toggle_favorite(app_id))))
        if fav and len(cfg.favorites) > 1:
            self.append(tile("Move earlier", lambda: win.move_favorite(app_id, -1)))
            self.append(tile("Move later", lambda: win.move_favorite(app_id, 1)))
        if entry:
            if cfg.is_hidden(app_id):
                self.append(tile("Show in All Applications",
                                 lambda: (win.close_dialog(), cfg.unhide(app_id))))
            else:
                self.append(tile("Hide from All Applications",
                                 lambda: (win.close_dialog(), cfg.hide(app_id),
                                          win.toast("Hidden. Restore it in Settings → Hidden applications."))))
        self.append(tile("Close", win.close_dialog))


class ConfirmDialog(Dialog):
    def __init__(self, win, title: str, subtitle: str, confirm: str, on_yes: Callable[[], None]):
        super().__init__(win, title, subtitle)
        self.append(tile("Cancel", win.close_dialog))
        self.append(tile(confirm, lambda: (win.close_dialog(), on_yes()), destructive=True))


# -- Settings ---------------------------------------------------------------
class ListPage(Page):
    """A titled, scrollable, centred column of tiles."""

    def __init__(self, win, title: str, subtitle: str = ""):
        super().__init__(win)
        self.title = title
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        column.add_css_class("lr-content")
        column.set_halign(Gtk.Align.CENTER)
        column.set_size_request(int(1100 * win.scale), -1)
        heading = Gtk.Label(label=title, xalign=0)
        heading.add_css_class("lr-page-title")
        column.append(heading)
        if subtitle:
            sub = Gtk.Label(label=subtitle, xalign=0, wrap=True)
            sub.add_css_class("lr-subtitle")
            column.append(sub)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.body.set_margin_top(12)
        column.append(self.body)
        self.append(scrolled(column))


def on_off(value: bool) -> str:
    return "On" if value else "Off"


class SettingsPage(ListPage):
    def __init__(self, win):
        super().__init__(win, "Settings")
        self.build()

    def build(self):
        win, cfg = self.win, self.win.config
        clear_box(self.body)
        add = self.body.append
        add(section_label("Applications"))
        add(tile("Manage favorites", lambda: win.push(FavoritesPage(win)),
                 value=str(len(cfg.favorites)), description="Reorder or remove favorites"))
        add(tile("Hidden applications", lambda: win.push(HiddenPage(win)), value=str(len(cfg.hidden))))
        add(tile("Refresh application list", self._refresh))
        add(section_label("Controller"))
        add(tile("Controller mappings", lambda: win.push(BindingsPage(win)),
                 description="Choose which button performs each action"))
        add(tile("Controller test", lambda: win.push(DiagnosticsPage(win)),
                 description="Detected controllers and live button presses"))
        add(self._toggle("Guide button brings back Living Room", "guide_returns",
                         "Best effort: GNOME may show a notification instead of switching"))
        add(self._cycle("Analog stick dead zone", "stick_deadzone", [0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
                        lambda v: f"{round(v * 100)}%"))
        add(section_label("Display"))
        add(self._toggle("Fullscreen", "fullscreen"))
        add(self._cycle("Background", "background", list(style.BACKGROUNDS),
                        lambda v: style.BACKGROUNDS.get(v, ("?",))[0]))
        # Changing the scale makes the window rebuild every page (including this one).
        add(self._cycle("Interface scale", "scale", SCALE_STEPS, lambda v: f"{round(v * 100)}%"))
        add(self._toggle("Animations", "animations"))
        add(self._toggle("Show clock", "show_clock"))
        add(section_label("System"))
        auto = tile("Start automatically after login", value=on_off(autostart.is_enabled()),
                    description=str(autostart.autostart_file()))
        auto.connect("clicked", lambda *_: self._toggle_autostart(auto))
        add(auto)
        add(tile("Reset preferences", lambda: win.open_dialog(ConfirmDialog(
            win, "Reset preferences?", "Favorites, hidden apps, mappings and settings return to defaults.",
            "Reset", win.reset_preferences)), destructive=True))
        add(tile("Quit Living Room", lambda: win.open_dialog(ConfirmDialog(
            win, "Quit Living Room?", "GNOME keeps running normally.", "Quit", win.get_application().quit)),
            destructive=True))
        about = Gtk.Label(label=f"Living Room {__version__} · config: {paths.config_file()}", xalign=0, wrap=True)
        about.add_css_class("tile-desc")
        add(about)

    def find_tile(self, title):
        for child in _children(self.body):
            if title and hasattr(child, "title_label") and child.title_label.get_label() == title:
                return child
        return None

    def _toggle(self, label, key, description=None):
        cfg = self.win.config
        t = tile(label, value=on_off(cfg.get(key)), description=description)

        def flip(*_):
            cfg.set(key, not cfg.get(key))
            t.value_label.set_label(on_off(cfg.get(key)))
        t.connect("clicked", flip)
        return t

    def _cycle(self, label, key, values, fmt):
        """A tile that steps through `values` (nearest current value + 1) on each press."""
        cfg = self.win.config
        t = tile(label, value=fmt(cfg.get(key)))

        def step(*_):
            cur = cfg.get(key)
            if cur in values:
                i = values.index(cur)
            else:
                i = min(range(len(values)), key=lambda j: abs(values[j] - cur)) \
                    if isinstance(cur, (int, float)) else -1
            cfg.set(key, values[(i + 1) % len(values)])
            t.value_label.set_label(fmt(cfg.get(key)))
        t.connect("clicked", step)
        return t

    def _toggle_autostart(self, t):
        try:
            autostart.set_enabled(not autostart.is_enabled())
        except OSError as exc:
            self.win.toast(f"Could not change autostart: {exc}", error=True)
        t.value_label.set_label(on_off(autostart.is_enabled()))

    def _refresh(self):
        self.win.catalog.refresh()
        self.win.on_catalog_changed()
        self.win.toast(f"Found {len(self.win.catalog.apps)} applications")


def _children(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        child = child.get_next_sibling()


class FavoritesPage(ListPage):
    def __init__(self, win):
        super().__init__(win, "Manage favorites",
                         "Select a favorite to pick it up, move it with Up/Down, select again to drop it.")
        self.moving: str | None = None
        self.build()

    def build(self):
        clear_box(self.body)
        favs = self.win.config.favorites
        if not favs:
            empty = Gtk.Label(label="No favorites yet.", xalign=0)
            empty.add_css_class("lr-empty")
            self.body.append(empty)
        for fid in favs:
            entry = self.win.catalog.get(fid)
            t = tile(entry.name if entry else f"{fid} (not installed)", lambda f=fid: self._pick(f),
                     value="Moving" if self.moving == fid else "")
            t.app_id = fid
            if self.moving == fid:
                t.add_css_class("moving")
            self.body.append(t)

    def _row(self, fid):
        for child in _children(self.body):
            if getattr(child, "app_id", None) == fid:
                return child
        return None

    def _pick(self, fid):
        self.moving = None if self.moving == fid else fid
        self._rebuild(fid)

    def _rebuild(self, fid):
        self.build()
        row = self._row(fid) or first_focusable(self.body)
        if row:
            GLib.idle_add(self.win.focus_widget, row)

    def _focused_id(self):
        focus = self.win.get_focus()
        for child in _children(self.body):
            if focus is not None and (focus == child or focus.is_ancestor(child)):
                return getattr(child, "app_id", None)
        return None

    def hints(self):
        if self.moving:
            return [(Action.UP, "Move"), (Action.ACTIVATE, "Drop"), (Action.BACK, "Drop")]
        return [(Action.ACTIVATE, "Pick up"), (Action.FAVORITE, "Remove"), (Action.BACK, "Back")]

    def handle_action(self, action):
        if self.moving:
            if action in (Action.UP, Action.DOWN):
                self.win.config.move_favorite(self.moving, -1 if action == Action.UP else 1)
                self._rebuild(self.moving)
                return True
            if action == Action.BACK:
                fid, self.moving = self.moving, None
                self._rebuild(fid)
                self.win.update_hints()
                return True
            if action in (Action.LEFT, Action.RIGHT):
                return True
        if action == Action.FAVORITE:
            fid = self._focused_id()
            if fid:
                self.win.config.remove_favorite(fid)
                self.build()
                row = first_focusable(self.body)
                if row:
                    GLib.idle_add(self.win.focus_widget, row)
                self.win.toast("Removed from favorites")
            return True
        if action == Action.ACTIVATE:
            GLib.idle_add(self.win.update_hints)
        return False


class HiddenPage(ListPage):
    def __init__(self, win):
        super().__init__(win, "Hidden applications", "Select an application to show it again.")
        self.build()

    def build(self):
        clear_box(self.body)
        hidden = self.win.config.hidden
        if not hidden:
            empty = Gtk.Label(label="Nothing is hidden.", xalign=0)
            empty.add_css_class("lr-empty")
            self.body.append(empty)
        for hid in hidden:
            entry = self.win.catalog.get(hid)
            self.body.append(tile(entry.name if entry else hid, lambda h=hid: self._unhide(h), value="Show"))

    def _unhide(self, hid):
        self.win.config.unhide(hid)
        self.build()
        row = first_focusable(self.body)
        GLib.idle_add(self.win.focus_widget, row) if row else None
        self.win.toast("Shown in All Applications")


class BindingsPage(ListPage):
    def __init__(self, win):
        super().__init__(win, "Controller mappings",
                         "Select an action, then press the controller button you want for it. "
                         "D-pad and left stick always navigate; the keyboard always works too.")
        self.capturing: str | None = None
        self._timeout = 0
        self.build()

    def build(self):
        clear_box(self.body)
        cfg, inp = self.win.config, self.win.input
        for action, label in BINDABLE_ACTIONS:
            buttons = cfg.buttons_for(action.value)
            value = "Press a button…" if self.capturing == action.value else \
                ", ".join(self.win.button_label(b) for b in buttons) or "Unassigned"
            t = tile(label, lambda a=action.value: self._capture(a), value=value)
            t.action_name = action.value
            if self.capturing == action.value:
                t.add_css_class("moving")
            self.body.append(t)
        self.body.append(tile("Reset to defaults", self._reset, destructive=True))
        if inp is None or not inp.available:
            note = Gtk.Label(label="No controller support available — see Controller test.", xalign=0)
            note.add_css_class("tile-desc")
            self.body.append(note)

    def _focus_action(self, name):
        for child in _children(self.body):
            if getattr(child, "action_name", None) == name:
                GLib.idle_add(self.win.focus_widget, child)

    def _capture(self, action_name):
        inp = self.win.input
        if inp is None or not inp.available or not inp.controllers:
            self.win.toast("Connect a controller first", error=True)
            return
        self.capturing = action_name
        inp.capture_next_button(self._captured)
        self._timeout = GLib.timeout_add_seconds(6, self._cancel)
        self.build()
        self._focus_action(action_name)

    def _captured(self, button):
        action_name, self.capturing = self.capturing, None
        if self._timeout:
            GLib.source_remove(self._timeout)
            self._timeout = 0
        if action_name:
            error = self.win.config.bind(button, action_name)
            if error:
                self.win.toast(error, error=True)
            else:
                self.win.toast(f"{self.win.button_label(button)} → {action_name.replace('_', ' ')}")
        self.build()
        self._focus_action(action_name)

    def _cancel(self):
        self._timeout = 0
        if self.capturing:
            name, self.capturing = self.capturing, None
            self.win.input.capture_next_button(None)
            self.build()
            self._focus_action(name)
        return GLib.SOURCE_REMOVE

    def _reset(self):
        self.win.config.reset_bindings()
        self.build()
        self.win.toast("Controller mappings reset")

    def on_hidden(self):
        if self.capturing:
            self._cancel()


DIAG_BUTTONS = ["a", "b", "x", "y", "back", "guide", "start", "leftstick", "rightstick",
                "leftshoulder", "rightshoulder", "dpup", "dpdown", "dpleft", "dpright",
                "misc1", "touchpad"]
DIAG_AXES = ["leftx", "lefty", "rightx", "righty", "lefttrigger", "righttrigger"]


class DiagnosticsPage(Page):
    title = "Controller test"

    def __init__(self, win):
        super().__init__(win)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("lr-content")
        heading = Gtk.Label(label="Controller test", xalign=0)
        heading.add_css_class("lr-page-title")
        box.append(heading)
        sub = Gtk.Label(label="Press buttons and move sticks. Press Back (B / ○) or Esc to leave.",
                        xalign=0, wrap=True)
        sub.add_css_class("lr-subtitle")
        box.append(sub)
        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.add_css_class("tile-label")
        box.append(self.status)
        self.button_flow = flowbox(4, 9)
        self.button_labels: dict[str, Gtk.Label] = {}
        for name in DIAG_BUTTONS:
            lbl = Gtk.Label(label=name)
            lbl.add_css_class("diag-btn")
            self.button_labels[name] = lbl
            self.button_flow.append(lbl)
        box.append(section_label("Buttons"))
        box.append(self.button_flow)
        box.append(section_label("Axes"))
        axes = Gtk.Grid(column_spacing=16, row_spacing=8)
        self.levels: dict[str, Gtk.LevelBar] = {}
        for i, name in enumerate(DIAG_AXES):
            axes.attach(Gtk.Label(label=name, xalign=0), (i % 2) * 2, i // 2, 1, 1)
            lb = Gtk.LevelBar(min_value=0, max_value=1, hexpand=True)
            lb.set_size_request(int(300 * win.scale), -1)
            self.levels[name] = lb
            axes.attach(lb, (i % 2) * 2 + 1, i // 2, 1, 1)
        box.append(axes)
        box.append(section_label("Events"))
        self.log = Gtk.Label(xalign=0, yalign=0)
        self.log.add_css_class("diag-log")
        box.append(self.log)
        self.lines: list[str] = []
        self.append(scrolled(box))
        self._timer = 0

    def hints(self):
        return [(Action.BACK, "Back")]

    def default_focus(self):
        return None

    def on_shown(self):
        inp = self.win.input
        if inp is not None:
            inp.raw_listeners.append(self._event)
        self._timer = GLib.timeout_add(50, self._refresh)
        self._refresh()

    def on_hidden(self):
        inp = self.win.input
        if inp is not None and self._event in inp.raw_listeners:
            inp.raw_listeners.remove(self._event)
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _event(self, text):
        self.lines = (self.lines + [text])[-10:]
        self.log.set_label("\n".join(self.lines))

    def _refresh(self):
        inp = self.win.input
        if inp is None or not inp.available:
            err = inp.error if inp is not None else "not started"
            self.status.set_label(f"Controller support unavailable: {err}\n"
                                  "Install python3-sdl2 (see README). Keyboard navigation still works.")
            return GLib.SOURCE_CONTINUE
        ctrls = list(inp.controllers.values())
        lines = [f"{len(ctrls)} controller(s) connected"] + \
                [f"• {c.name}  [{c.family}]  {c.guid}" for c in ctrls]
        unmapped = inp.unmapped_joysticks()
        if unmapped:
            lines.append("Detected without a mapping (add one to "
                         f"{paths.config_dir() / 'gamecontrollerdb.txt'}): " + ", ".join(unmapped))
        self.status.set_label("\n".join(lines))
        pressed = set().union(*(c.pressed for c in ctrls)) if ctrls else set()
        for name, lbl in self.button_labels.items():
            fam = ctrls[0].family if ctrls else "xbox"
            lbl.set_label(self.win.button_label(name, fam))
            (lbl.add_css_class if name in pressed else lbl.remove_css_class)("on")
        for name, lb in self.levels.items():
            values = [c.axes.get(name, 0) for c in ctrls] or [0]
            v = max(values, key=abs)
            lb.set_value((v / 32767.0) if "trigger" in name else (v + 32768) / 65535.0)
        return GLib.SOURCE_CONTINUE

    def handle_action(self, action):
        # Swallow everything except Back so buttons can be tested freely.
        return action != Action.BACK


__all__ = ["HomePage", "SearchPage", "SettingsPage", "OptionsDialog", "ConfirmDialog", "Page",
           "DIRECTIONS"]
