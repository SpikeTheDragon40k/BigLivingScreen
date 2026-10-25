"""Main window: page stack, dialogs, spatial navigation, hints, clock, toasts."""

from __future__ import annotations

import logging
import time

from gi.repository import Adw, Gdk, GLib, Gtk

from living_room import APP_NAME
from living_room.controllers.input import DIRECTIONS, KEYBOARD_LABELS, Action, button_label
from living_room.ui import spatial, style
from living_room.ui.pages import (
    HomePage, OptionsDialog, Page, SearchPage, SettingsPage, first_focusable,
)
from living_room.ui.widgets import FOCUSABLE, AppCard, clear_box, make_focusable

log = logging.getLogger(__name__)

KEYMAP = {
    "Up": Action.UP, "Down": Action.DOWN, "Left": Action.LEFT, "Right": Action.RIGHT,
    "KP_Up": Action.UP, "KP_Down": Action.DOWN, "KP_Left": Action.LEFT, "KP_Right": Action.RIGHT,
    "Return": Action.ACTIVATE, "KP_Enter": Action.ACTIVATE, "space": Action.ACTIVATE,
    "Escape": Action.BACK, "BackSpace": Action.BACK,
    "f": Action.FAVORITE, "o": Action.OPTIONS, "Menu": Action.OPTIONS,
    "Page_Up": Action.PREV_SECTION, "Page_Down": Action.NEXT_SECTION,
    "F1": Action.SETTINGS, "Home": Action.HOME, "slash": Action.SEARCH,
}
# Keys that still navigate while typing in the search field.
ENTRY_KEYS = {"Up", "Down", "Escape", "Return", "KP_Enter", "Page_Up", "Page_Down", "F1"}


class LivingRoomWindow(Adw.ApplicationWindow):
    def __init__(self, app, config, catalog, launcher, input_backend, windowed: bool = False):
        super().__init__(application=app, title=APP_NAME)
        self.config = config
        self.catalog = catalog
        self.launcher = launcher
        self.input = input_backend
        self.add_css_class("living-room")
        self.set_default_size(1280, 720)
        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.scale = self._compute_scale()
        self._activated_at = 0.0
        self._nav_serial = 0  # bumped on every user navigation
        self._scroll_anim = None
        self._toast_timer = 0
        self.history: list[Page] = []
        self.dialog: Page | None = None
        self._forced_windowed = windowed

        root = Gtk.Overlay()
        root.add_css_class("lr-background")
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main.append(self._build_header())
        self.stack = Gtk.Stack(vexpand=True, hexpand=True)
        self.stack.set_transition_duration(220)
        main.append(self.stack)
        self.hints_box = Gtk.Box()
        self.hints_box.add_css_class("lr-hints")
        main.append(self.hints_box)
        root.set_child(main)

        self.scrim = Gtk.Box(hexpand=True, vexpand=True)
        self.scrim.add_css_class("lr-scrim")
        self.scrim.set_visible(False)
        root.add_overlay(self.scrim)
        self.dialog_slot = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.dialog_slot.set_visible(False)
        root.add_overlay(self.dialog_slot)
        self.toast_revealer = Gtk.Revealer(halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
        self.toast_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.toast_revealer.set_can_target(False)
        self.toast_label = Gtk.Label(wrap=True)
        self.toast_label.add_css_class("lr-toast")
        self.toast_revealer.set_child(self.toast_label)
        root.add_overlay(self.toast_revealer)
        self.set_content(root)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.connect("notify::is-active", self._on_active_changed)
        self.connect("close-request", self._on_close_request)

        self.apply_style()
        self.home = HomePage(self)
        self.search = SearchPage(self)
        self._show_page(self.home, initial=True)
        self.apply_window_mode()
        self._tick_clock()
        GLib.timeout_add_seconds(1, self._tick_clock)
        config.connect(self._on_config_changed)
        catalog.connect(self.on_catalog_changed)

    # -- construction ------------------------------------------------------
    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(spacing=24)
        header.add_css_class("lr-header")
        title = Gtk.Label(label=APP_NAME.upper(), xalign=0, hexpand=True, valign=Gtk.Align.CENTER)
        title.add_css_class("lr-title")
        header.append(title)
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.clock = Gtk.Label(xalign=1)
        self.clock.add_css_class("lr-clock")
        self.date = Gtk.Label(xalign=1)
        self.date.add_css_class("lr-date")
        clock_box.append(self.clock)
        clock_box.append(self.date)
        self.clock_box = clock_box
        header.append(clock_box)
        for icon, tip, cb in (("system-search-symbolic", "Search", lambda: self.open_search()),
                              ("emblem-system-symbolic", "Settings", lambda: self.open_settings())):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip, valign=Gtk.Align.CENTER)
            b.add_css_class("tile")
            b.add_css_class("round")
            make_focusable(b)
            b.connect("clicked", lambda _b, cb=cb: cb())
            header.append(b)
        self.header = header
        return header

    def _compute_scale(self) -> float:
        height = 1080
        display = Gdk.Display.get_default()
        monitor = None
        surface = self.get_surface()
        if surface is not None:
            monitor = display.get_monitor_at_surface(surface)
        if monitor is None:
            monitors = display.get_monitors()
            monitor = monitors.get_item(0) if monitors.get_n_items() else None
        if monitor is not None:
            height = monitor.get_geometry().height or 1080
        return max(0.5, min(2.5, height / 1080.0 * float(self.config.get("scale"))))

    def apply_style(self) -> None:
        css = style.build_css(self.scale, self.config.get("background"), self.config.get("animations"))
        if hasattr(self._css, "load_from_string"):
            self._css.load_from_string(css)
        else:
            self._css.load_from_data(css, -1)
        anim = self.config.get("animations")
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE if anim
                                       else Gtk.StackTransitionType.NONE)
        self.toast_revealer.set_transition_duration(200 if anim else 0)
        self.clock_box.set_visible(bool(self.config.get("show_clock")))

    def apply_window_mode(self) -> None:
        if self.config.get("fullscreen") and not self._forced_windowed:
            self.fullscreen()
        else:
            self.unfullscreen()

    # -- clock -------------------------------------------------------------
    def _tick_clock(self) -> bool:
        now = GLib.DateTime.new_now_local()
        self.clock.set_label(now.format("%H:%M") or "")
        self.date.set_label(now.format("%A %-d %B") or "")
        return GLib.SOURCE_CONTINUE

    # -- pages and dialogs -------------------------------------------------
    @property
    def current(self) -> Page:
        return self.history[-1]

    def _show_page(self, page: Page, initial: bool = False) -> None:
        if page.get_parent() is None:
            self.stack.add_child(page)
        if not initial and self.history:
            self.current.on_hidden()
        if initial:
            self.history = [page]
        self.stack.set_visible_child(page)
        page.on_shown()
        self.update_hints()
        GLib.idle_add(self._restore_focus, page, self._nav_serial)

    def push(self, page: Page) -> None:
        self._remember_focus()
        self.current.on_hidden()
        self.history.append(page)
        if page.get_parent() is None:
            self.stack.add_child(page)
        self.stack.set_visible_child(page)
        page.on_shown()
        self.update_hints()
        GLib.idle_add(self._restore_focus, page, self._nav_serial)

    def pop(self) -> None:
        if len(self.history) <= 1:
            return
        page = self.history.pop()
        page.on_hidden()
        self.stack.set_visible_child(self.current)
        self.current.on_shown()
        if page not in (self.home, self.search) and not isinstance(page, SettingsPage):
            GLib.timeout_add(400, self._remove_page, page)
        self.update_hints()
        GLib.idle_add(self._restore_focus, self.current, self._nav_serial)

    def _remove_page(self, page: Page) -> bool:
        if page.get_parent() is self.stack and page not in self.history:
            self.stack.remove(page)
        return GLib.SOURCE_REMOVE

    def go_home(self) -> None:
        self.close_dialog()
        while len(self.history) > 1:
            self.pop()

    def open_settings(self) -> None:
        self.close_dialog()
        if isinstance(self.current, SettingsPage):
            return
        page = next((c for c in self._stack_children() if isinstance(c, SettingsPage)), None)
        if page is None:
            page = SettingsPage(self)
        else:
            page.build()
        self.push(page)

    def open_search(self) -> None:
        self.close_dialog()
        if self.current is self.search:
            self.search.handle_action(Action.SEARCH)
            return
        if self.search in self.history:
            while self.current is not self.search:
                self.pop()
            return
        self.push(self.search)

    def _stack_children(self):
        child = self.stack.get_first_child()
        while child is not None:
            yield child
            child = child.get_next_sibling()

    def open_dialog(self, dialog: Page) -> None:
        self._remember_focus()
        self.close_dialog(restore=False)
        self.dialog = dialog
        self.dialog_slot.append(dialog)
        self.scrim.set_visible(True)
        self.dialog_slot.set_visible(True)
        self.update_hints()
        GLib.idle_add(self._restore_focus, dialog, self._nav_serial)

    def close_dialog(self, restore: bool = True) -> None:
        if self.dialog is None:
            return
        self.dialog.on_hidden()
        self.dialog_slot.remove(self.dialog)
        self.dialog = None
        self.scrim.set_visible(False)
        self.dialog_slot.set_visible(False)
        self.update_hints()
        if restore:
            GLib.idle_add(self._restore_focus, self.current, self._nav_serial)

    def _remember_focus(self) -> None:
        target = self.dialog or (self.history[-1] if self.history else None)
        focus = self._focusable_ancestor(self.get_focus())
        if target is not None and focus is not None:
            target.last_focus = focus

    def _restore_focus(self, page: Page, serial: int | None = None) -> bool:
        if page is not (self.dialog or self.current):
            return GLib.SOURCE_REMOVE
        if serial is not None and serial != self._nav_serial:
            return GLib.SOURCE_REMOVE  # the user already navigated since this was scheduled
        w = page.last_focus
        if w is None or not self._in_scope(w):
            w = page.default_focus()
        if w is not None:
            self.focus_widget(w)
        else:
            self.set_focus(None)
        return GLib.SOURCE_REMOVE

    # -- focus & navigation -----------------------------------------------
    def _scopes(self) -> list[Gtk.Widget]:
        if self.dialog is not None:
            return [self.dialog]
        return [self.header, self.current]

    def _candidates(self) -> list[Gtk.Widget]:
        out = []
        for scope in self._scopes():
            stack = [scope]
            while stack:
                w = stack.pop()
                if not w.get_visible() or not w.get_child_visible():
                    continue
                if w.has_css_class(FOCUSABLE) and w.is_sensitive() and w.get_mapped():
                    out.append(w)
                    continue
                child = w.get_first_child()
                while child is not None:
                    stack.append(child)
                    child = child.get_next_sibling()
        return out

    def _focusable_ancestor(self, w: Gtk.Widget | None) -> Gtk.Widget | None:
        while w is not None and not w.has_css_class(FOCUSABLE):
            w = w.get_parent()
        return w

    def _in_scope(self, w: Gtk.Widget) -> bool:
        return w.get_mapped() and any(w is s or w.is_ancestor(s) for s in self._scopes())

    def _bounds(self, w: Gtk.Widget) -> spatial.Rect | None:
        ok, r = w.compute_bounds(self)
        if not ok:
            return None
        return spatial.Rect(r.origin.x, r.origin.y, r.size.width, r.size.height)

    def focused_card(self) -> AppCard | None:
        w = self._focusable_ancestor(self.get_focus())
        return w if isinstance(w, AppCard) else None

    def focus_widget(self, w: Gtk.Widget | None) -> bool:
        if w is None:
            return GLib.SOURCE_REMOVE
        w.grab_focus()
        self.set_focus_visible(True)
        if not self._scroll_into_view(w):
            # Freshly built widgets have no allocation yet; retry after layout.
            w.add_tick_callback(lambda widget, _clock: self._scroll_into_view(widget) and False)
        return GLib.SOURCE_REMOVE

    def navigate(self, direction: Action) -> None:
        current = self._focusable_ancestor(self.get_focus())
        candidates = self._candidates()
        if current is None or current not in candidates:
            page = self.dialog or self.current
            target = page.last_focus if page.last_focus in candidates else page.default_focus()
            self.focus_widget(target or (candidates[0] if candidates else None))
            return
        cur = self._bounds(current)
        if cur is None:
            return
        rects = [(i, b) for i, w in enumerate(candidates) if w is not current and (b := self._bounds(w))]
        key = spatial.find_next(cur, rects, direction.value)
        if key is not None:
            self.focus_widget(candidates[key])

    def jump_section(self, delta: int) -> None:
        sections = [s for s in (self.dialog or self.current).sections()
                    if s.get_visible() and first_focusable(s) is not None]
        if not sections:
            return
        focus = self.get_focus()
        index = next((i for i, s in enumerate(sections) if focus is not None and focus.is_ancestor(s)), -1)
        target = sections[(index + delta) % len(sections)] if index >= 0 else sections[0]
        self.focus_widget(first_focusable(target))

    def _scroll_into_view(self, w: Gtk.Widget) -> bool:
        """Returns False if the widget has no layout yet."""
        sw = w.get_ancestor(Gtk.ScrolledWindow)
        if sw is None:
            return True
        content = sw.get_child()
        ok, r = w.compute_bounds(content)
        if not ok or (r.size.width == 0 and r.size.height == 0):
            return False
        adj = sw.get_vadjustment()
        margin = 60 * self.scale
        value, page = adj.get_value(), adj.get_page_size()
        top, bottom = r.origin.y - margin, r.origin.y + r.size.height + margin
        if top < value:
            target = max(adj.get_lower(), top)
        elif bottom > value + page:
            target = min(adj.get_upper() - page, bottom - page)
        else:
            return True
        if self._scroll_anim is not None:
            self._scroll_anim.skip()
        if not self.config.get("animations"):
            adj.set_value(target)
            return True
        anim_target = Adw.CallbackAnimationTarget.new(lambda v: adj.set_value(v))
        self._scroll_anim = Adw.TimedAnimation.new(sw, value, target, 220, anim_target)
        self._scroll_anim.set_easing(Adw.Easing.EASE_OUT_CUBIC)
        self._scroll_anim.play()
        return True

    # -- input dispatch ----------------------------------------------------
    def handle_action(self, action: Action, source=None) -> None:
        if not self.is_active():
            if action == Action.HOME and self.config.get("guide_returns"):
                log.info("Guide pressed while in background; requesting focus")
                self.present()
            return
        if time.monotonic() - self._activated_at < 0.35:
            return  # ignore the tail of a press that switched focus back to us
        if source is not None and getattr(source, "family", None):
            self._update_family(source.family)
        page = self.dialog or self.current
        if page.handle_action(action):
            return
        if action in DIRECTIONS or action in (Action.PREV_SECTION, Action.NEXT_SECTION):
            self._nav_serial += 1
        if action in DIRECTIONS:
            self.navigate(action)
        elif action == Action.ACTIVATE:
            focus = self._focusable_ancestor(self.get_focus())
            if focus is not None:
                focus.activate()
            else:
                self.navigate(Action.DOWN)
        elif action == Action.BACK:
            if self.dialog is not None:
                self.close_dialog()
            else:
                self.pop()
        elif action == Action.SETTINGS:
            self.open_settings()
        elif action == Action.SEARCH:
            self.open_search()
        elif action == Action.HOME:
            self.go_home()
            GLib.idle_add(lambda: self.home.handle_action(Action.HOME) and False)
        elif action in (Action.PREV_SECTION, Action.NEXT_SECTION):
            self.jump_section(-1 if action == Action.PREV_SECTION else 1)
        elif action == Action.FAVORITE:
            card = self.focused_card()
            if card is not None:
                self.toggle_favorite(card.app_id)
        elif action == Action.OPTIONS:
            card = self.focused_card()
            if card is not None:
                self.open_dialog(OptionsDialog(self, card.app_id))

    def _on_key(self, _ctrl, keyval, _keycode, state) -> bool:
        name = Gdk.keyval_name(keyval) or ""
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            if name in ("f", "F") and state & Gdk.ModifierType.CONTROL_MASK:
                self.open_search()
                return True
            return False
        if name == "F11":
            self.config.set("fullscreen", not self.config.get("fullscreen"))
            return True
        focus = self.get_focus()
        typing = isinstance(focus, Gtk.Text) or isinstance(focus, Gtk.Editable)
        if typing and name not in ENTRY_KEYS:
            return False
        if typing and name in ("Return", "KP_Enter"):
            self.jump_section(1)
            return True
        char = chr(Gdk.keyval_to_unicode(keyval) or 0)
        if char.isprintable() and char.strip() and name != "slash" and (
                self.current is self.search or (name not in KEYMAP and self.dialog is None)):
            # Typing anywhere starts or continues a search.
            if self.current is not self.search:
                self.open_search()
            self.search._type(char)
            return True
        action = KEYMAP.get(name)
        if action is None:
            return False
        self._update_family("keyboard")
        self.handle_action(action)
        return True

    def _on_active_changed(self, *_):
        active = self.is_active()
        if active:
            self._activated_at = time.monotonic()
        if self.input is not None:
            self.input.set_active(active)

    def _on_close_request(self, *_):
        return False

    # -- hints -------------------------------------------------------------
    _family = None

    def _update_family(self, family: str) -> None:
        if family != self._family:
            self._family = family
            self.update_hints()

    def button_label(self, button: str, family: str | None = None) -> str:
        fam = family or (self.input.last_family if self.input is not None else "xbox")
        return button_label(fam, button)

    def action_label(self, action: Action) -> str:
        if action in DIRECTIONS:
            return "Arrows" if self._family == "keyboard" else "D-Pad"
        if self._family == "keyboard" or self.input is None or not self.input.controllers:
            return KEYBOARD_LABELS.get(action, action.value)
        buttons = self.config.buttons_for(action.value)
        return self.button_label(buttons[0]) if buttons else "—"

    def update_hints(self) -> bool:
        clear_box(self.hints_box)
        page = self.dialog or (self.history[-1] if self.history else None)
        if page is None:
            return False
        hints = [(Action.UP, "Navigate")] + [h for h in page.hints() if h[0] != Action.UP]
        if page.hints() and page.hints()[0][0] == Action.UP:
            hints = page.hints()
        for action, text in hints:
            box = Gtk.Box()
            key = Gtk.Label(label=self.action_label(action))
            key.add_css_class("hint-key")
            box.append(key)
            label = Gtk.Label(label=text)
            label.add_css_class("hint")
            box.append(label)
            self.hints_box.append(box)
        return False

    # -- toasts ------------------------------------------------------------
    def toast(self, text: str, error: bool = False, seconds: int = 3) -> None:
        self.toast_label.set_label(text)
        (self.toast_label.add_css_class if error else self.toast_label.remove_css_class)("error")
        self.toast_revealer.set_reveal_child(True)
        if self._toast_timer:
            GLib.source_remove(self._toast_timer)
        self._toast_timer = GLib.timeout_add_seconds(seconds, self._hide_toast)

    def _hide_toast(self) -> bool:
        self._toast_timer = 0
        self.toast_revealer.set_reveal_child(False)
        return GLib.SOURCE_REMOVE

    # -- app operations ----------------------------------------------------
    def launch(self, app_id: str, action: str | None = None) -> None:
        entry = self.catalog.get(app_id)
        if entry is None:
            self.toast("This application is not installed.", error=True)
            return
        ok, message = self.launcher.launch(entry, action)
        self.toast(message, error=not ok, seconds=4 if ok else 6)

    def open_options(self, app_id: str) -> None:
        self.open_dialog(OptionsDialog(self, app_id))

    def toggle_favorite(self, app_id: str) -> None:
        added = self.config.toggle_favorite(app_id)
        entry = self.catalog.get(app_id)
        name = entry.name if entry else app_id
        self.toast(f"{name} added to favorites" if added else f"{name} removed from favorites")

    def move_favorite(self, app_id: str, delta: int) -> None:
        if self.config.move_favorite(app_id, delta):
            self.toast("Moved earlier" if delta < 0 else "Moved later")

    def reset_preferences(self) -> None:
        self.config.reset()
        self.config.seed_favorites(self.catalog.ids())
        self.toast("Preferences reset")

    def on_app_exited(self, name: str) -> None:
        if not self.is_active():
            self.present()

    # -- change handling ---------------------------------------------------
    def _on_config_changed(self, what: str) -> None:
        if what == "favorites":
            focus_card = self.focused_card()
            self.home.rebuild_favorites(refocus=self.current is self.home)
            for app_id, card in list(self.home.all_cards.items()):
                if card.favorite != self.config.is_favorite(app_id):
                    self.home.update_star(app_id)
            if self.current is self.search:
                self.search.update()
                if focus_card is not None:
                    GLib.idle_add(self.focus_widget, first_focusable(self.search.results))
        elif what == "hidden":
            self.home.rebuild()
        elif what in ("settings.scale", "settings.background", "settings.animations",
                      "settings.show_clock", "all"):
            old_scale = self.scale
            self.scale = self._compute_scale()
            self.apply_style()
            if what == "all" or abs(old_scale - self.scale) > 1e-6:
                self._rebuild_pages()
            if what == "all":
                self.apply_window_mode()
        elif what == "settings.fullscreen":
            self.apply_window_mode()
        elif what == "bindings":
            self.update_hints()
        if what.startswith("settings.") and self.input is not None:
            self.input.deadzone = float(self.config.get("stick_deadzone"))

    def _rebuild_pages(self) -> None:
        """Recreate all pages so sizes follow the new scale."""
        self.close_dialog(restore=False)
        was_settings = isinstance(self.current, SettingsPage)
        focused = self._focusable_ancestor(self.get_focus())
        focused_title = focused.title_label.get_label() if hasattr(focused, "title_label") else None
        for child in list(self._stack_children()):
            child.on_hidden()
            self.stack.remove(child)
        self.home = HomePage(self)
        self.search = SearchPage(self)
        self._show_page(self.home, initial=True)
        if was_settings:
            settings = SettingsPage(self)
            settings.last_focus = settings.find_tile(focused_title)
            self.push(settings)

    def on_catalog_changed(self) -> None:
        self.home.rebuild()
        if self.current is self.search:
            self.search.update()
