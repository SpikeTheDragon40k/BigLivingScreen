"""Entry point: single-instance Adw.Application wiring config, apps and input."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib  # noqa: E402

from living_room import APP_ID, APP_NAME, __version__  # noqa: E402
from living_room.config import autostart, paths  # noqa: E402

log = logging.getLogger("living_room")


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug or os.environ.get("LIVING_ROOM_DEBUG") else logging.INFO
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    stderr = logging.StreamHandler()
    stderr.setFormatter(fmt)
    root.addHandler(stderr)
    try:
        paths.state_dir().mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            paths.state_dir() / "living-room.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:
        pass


class LivingRoomApp(Adw.Application):
    def __init__(self):
        flags = getattr(Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE)
        super().__init__(application_id=APP_ID, flags=flags)
        GLib.set_application_name(APP_NAME)
        self.window = None
        self.windowed = False
        self.config = None
        self.catalog = None
        self.input = None
        self.launcher = None
        self.add_main_option("windowed", ord("w"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Start in a window instead of fullscreen", None)
        self.add_main_option("autostart", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Started by GNOME autostart (enables crash-loop protection)", None)
        self.add_main_option("disable-autostart", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Remove the autostart entry and exit", None)
        self.add_main_option("version", ord("v"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Print version and exit", None)
        self.connect("handle-local-options", self._on_local_options)

    def _on_local_options(self, _app, options: GLib.VariantDict) -> int:
        if options.contains("version"):
            print(f"{APP_NAME} {__version__}")
            return 0
        if options.contains("disable-autostart"):
            autostart.set_enabled(False)
            print("Autostart disabled.")
            return 0
        if options.contains("autostart") and autostart.crash_loop_detected():
            log.error("Living Room crashed repeatedly; skipping autostart launch. "
                      "Start it manually to reset, or run: living-room --disable-autostart")
            autostart.record_clean_exit()  # the next manual start begins fresh
            return 1
        self.windowed = options.contains("windowed")
        return -1

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        from living_room.applications.catalog import Catalog
        from living_room.applications.launcher import Launcher
        from living_room.config.store import Config
        from living_room.controllers.sdl_backend import SDLInput

        autostart.record_start()
        self.config = Config().load()
        self.catalog = Catalog()
        self.config.seed_favorites(self.catalog.ids())
        self.launcher = Launcher(lambda: Gdk.Display.get_default().get_app_launch_context())
        cfg = self.config
        self.input = SDLInput(lambda: cfg.bindings, float(cfg.get("stick_deadzone")),
                              cfg.get("repeat_delay_ms") / 1000.0, cfg.get("repeat_interval_ms") / 1000.0)
        self.input.start()
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def do_activate(self):
        # A second `living-room` invocation lands here: bring the launcher back.
        if self.window is None:
            from living_room.ui.window import LivingRoomWindow
            self.window = LivingRoomWindow(self, self.config, self.catalog, self.launcher,
                                           self.input, windowed=self.windowed)
            self.input.on_action = self.window.handle_action
            self.input.on_devices_changed = self.window.update_hints
            self.launcher.on_exit = self.window.on_app_exited
        self.window.present()

    def do_shutdown(self):
        if self.input is not None:
            self.input.stop()
        autostart.record_clean_exit()
        log.info("Living Room exited cleanly")
        Adw.Application.do_shutdown(self)


def main(argv: list[str] | None = None) -> int:
    setup_logging("--debug" in (argv or sys.argv))
    args = [a for a in (argv or sys.argv) if a != "--debug"]
    app = LivingRoomApp()
    try:
        return app.run(args)
    except KeyboardInterrupt:
        app.quit()
        return 0


if __name__ == "__main__":
    sys.exit(main())
