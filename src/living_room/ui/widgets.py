"""Reusable TV-sized widgets. Every focusable widget carries the CSS class
`lr-focusable`, which is what spatial navigation looks for."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from gi.repository import Gdk, Gio, Gtk, Pango

from living_room.applications.catalog import FALLBACK_ICON, AppEntry

FOCUSABLE = "lr-focusable"


def safe_gicon(icon: Gio.Icon | None) -> Gio.Icon:
    """Return an icon that will actually render, falling back gracefully."""
    fallback = Gio.ThemedIcon.new(FALLBACK_ICON)
    if icon is None:
        return fallback
    if isinstance(icon, Gio.FileIcon):
        path = icon.get_file().get_path()
        return icon if path and Path(path).is_file() else fallback
    display = Gdk.Display.get_default()
    if display is not None and isinstance(icon, Gio.ThemedIcon):
        theme = Gtk.IconTheme.get_for_display(display)
        names = icon.get_names() or []
        # Desktop files sometimes put an absolute path in Icon= that Gio
        # turns into a ThemedIcon on older versions; handle that too.
        for name in names:
            if name.startswith("/") and Path(name).is_file():
                return Gio.FileIcon.new(Gio.File.new_for_path(name))
        if not theme.has_gicon(icon):
            return fallback
    return icon


def make_focusable(widget: Gtk.Widget) -> Gtk.Widget:
    widget.add_css_class(FOCUSABLE)
    widget.set_focusable(True)
    widget.set_focus_on_click(True)
    return widget


class AppCard(Gtk.Button):
    def __init__(self, entry: AppEntry | None, app_id: str, big: bool, scale: float,
                 favorite: bool = False):
        super().__init__()
        self.app_id = app_id
        self.entry = entry
        self.favorite = favorite
        make_focusable(self)
        self.add_css_class("card")
        self.add_css_class("big" if big else "small")
        icon_px = int((128 if big else 88) * scale)

        overlay = Gtk.Overlay()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=int(14 * scale))
        box.set_valign(Gtk.Align.CENTER)
        image = Gtk.Image.new_from_gicon(safe_gicon(entry.icon if entry else None))
        image.set_pixel_size(icon_px)
        box.append(image)
        label = Gtk.Label(label=entry.name if entry else _pretty_id(app_id))
        label.add_css_class("card-name")
        label.set_wrap(True)
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_lines(2)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_max_width_chars(14)
        box.append(label)
        if entry is None:
            sub = Gtk.Label(label="Not installed")
            sub.add_css_class("tile-desc")
            box.append(sub)
            self.add_css_class("missing")
        overlay.set_child(box)
        if favorite:
            star = Gtk.Label(label="★")
            star.add_css_class("card-star")
            star.set_halign(Gtk.Align.END)
            star.set_valign(Gtk.Align.START)
            overlay.add_overlay(star)
        self.set_child(overlay)
        self.set_tooltip_text(entry.description if entry and entry.description else None)
        self.connect("clicked", self._on_clicked)

    def _on_clicked(self, *_):
        root = self.get_root()
        if hasattr(root, "launch"):
            if self.entry is None:
                root.open_options(self.app_id)
            else:
                root.launch(self.app_id)


def _pretty_id(app_id: str) -> str:
    return app_id.removesuffix(".desktop").split(".")[-1].replace("-", " ").title()


def tile(label: str, on_activate: Callable[[], None] | None = None, value: str | None = None,
         description: str | None = None, destructive: bool = False) -> Gtk.Button:
    """A large full-width button used for menus and settings."""
    button = Gtk.Button()
    make_focusable(button)
    button.add_css_class("tile")
    if destructive:
        button.add_css_class("destructive")
    box = Gtk.Box(spacing=16)
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
    title = Gtk.Label(label=label, xalign=0)
    title.add_css_class("tile-label")
    text.append(title)
    if description:
        desc = Gtk.Label(label=description, xalign=0, wrap=True)
        desc.add_css_class("tile-desc")
        text.append(desc)
    box.append(text)
    value_label = Gtk.Label(label=value or "", xalign=1)
    value_label.add_css_class("tile-value")
    box.append(value_label)
    button.set_child(box)
    button.value_label = value_label
    button.title_label = title
    if on_activate:
        button.connect("clicked", lambda *_: on_activate())
    return button


def section_label(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text.upper(), xalign=0)
    label.add_css_class("lr-section")
    return label


def clear_box(container: Gtk.Widget) -> None:
    # Drop focus ourselves first; otherwise GTK picks a fallback widget when
    # the focused child is destroyed, racing with our own refocusing.
    root = container.get_root()
    focus = root.get_focus() if root is not None else None
    if focus is not None and focus.is_ancestor(container):
        root.set_focus(None)
    child = container.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        container.remove(child)
        child = nxt


def flowbox(min_per_line: int = 1, max_per_line: int = 12) -> Gtk.FlowBox:
    fb = Gtk.FlowBox()
    fb.set_selection_mode(Gtk.SelectionMode.NONE)
    fb.set_homogeneous(True)
    fb.set_min_children_per_line(min_per_line)
    fb.set_max_children_per_line(max_per_line)
    fb.set_column_spacing(24)
    fb.set_row_spacing(24)
    fb.set_valign(Gtk.Align.START)
    fb.set_halign(Gtk.Align.START)
    fb.set_focusable(False)
    return fb


def flow_append(fb: Gtk.FlowBox, widget: Gtk.Widget) -> None:
    fb.append(widget)
    child = widget.get_parent()
    if isinstance(child, Gtk.FlowBoxChild):
        child.set_focusable(False)
