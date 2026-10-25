"""SDL2 GameController backend polled from the GLib main loop.

SDL is initialised with only the game-controller subsystem (no SDL window,
no video), so it reads devices through udev/evdev/hidraw and supports USB
and Bluetooth hot-plug. On Ubuntu releases where libSDL2 is provided by
sdl2-compat (SDL3 underneath) the same API applies.

SDL_PollEvent never blocks, so polling with GLib.timeout_add keeps every
SDL call on the main thread and needs no locking.
"""

from __future__ import annotations

import ctypes
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from gi.repository import GLib

from living_room.controllers.input import (
    DPAD_BUTTONS, Action, Repeater, StickTracker, resolve_action,
)

log = logging.getLogger(__name__)

try:
    import sdl2
    HAVE_SDL = True
except Exception as exc:  # ImportError, or the shared library missing
    sdl2 = None
    HAVE_SDL = False
    _IMPORT_ERROR = str(exc)


def _family(controller_type: int) -> str:
    if not HAVE_SDL:
        return "xbox"
    ps = {getattr(sdl2, n, -1) for n in ("SDL_CONTROLLER_TYPE_PS3", "SDL_CONTROLLER_TYPE_PS4",
                                         "SDL_CONTROLLER_TYPE_PS5")}
    nin = {getattr(sdl2, n, -1) for n in (
        "SDL_CONTROLLER_TYPE_NINTENDO_SWITCH_PRO", "SDL_CONTROLLER_TYPE_NINTENDO_SWITCH_JOYCON_LEFT",
        "SDL_CONTROLLER_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT",
        "SDL_CONTROLLER_TYPE_NINTENDO_SWITCH_JOYCON_PAIR")}
    if controller_type in ps:
        return "playstation"
    if controller_type in nin:
        return "nintendo"
    return "xbox"


@dataclass
class ControllerInfo:
    instance_id: int
    name: str
    family: str
    guid: str
    handle: object = field(repr=False, default=None)
    stick: StickTracker = field(default_factory=StickTracker)
    pressed: set[str] = field(default_factory=set)
    axes: dict[str, int] = field(default_factory=dict)


class SDLInput:
    """Emits Actions from all connected controllers."""

    def __init__(self, bindings: Callable[[], dict[str, str]], deadzone: float = 0.5,
                 repeat_delay: float = 0.4, repeat_interval: float = 0.13):
        self._bindings = bindings
        self.deadzone = deadzone
        self.repeater = Repeater(repeat_delay, repeat_interval)
        self.controllers: dict[int, ControllerInfo] = {}
        self.on_action: Callable[[Action, ControllerInfo | None], None] | None = None
        self.on_devices_changed: Callable[[], None] | None = None
        self.raw_listeners: list[Callable[[str], None]] = []
        self._capture: Callable[[str], None] | None = None
        self._source = 0
        self.available = False
        self.error = ""
        self.last_family = "xbox"
        self.fast = True

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> bool:
        if not HAVE_SDL:
            self.error = f"PySDL2 unavailable: {_IMPORT_ERROR}"
            log.warning(self.error)
            return False
        sdl2.SDL_SetHint(b"SDL_NO_SIGNAL_HANDLERS", b"1")
        # Without an SDL window there is no focus concept; we gate events
        # ourselves based on the GTK window's focus state.
        sdl2.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
        if sdl2.SDL_Init(sdl2.SDL_INIT_GAMECONTROLLER) != 0:
            self.error = sdl2.SDL_GetError().decode(errors="replace")
            log.error("SDL_Init failed: %s", self.error)
            return False
        self._load_user_mappings()
        self.available = True
        self._schedule()
        log.info("SDL game controller support initialised")
        return True

    def stop(self) -> None:
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0
        if self.available:
            for info in self.controllers.values():
                sdl2.SDL_GameControllerClose(info.handle)
            self.controllers.clear()
            sdl2.SDL_Quit()
            self.available = False

    def set_active(self, active: bool) -> None:
        """Poll quickly while the launcher is focused, slowly otherwise."""
        if active != self.fast:
            self.fast = active
            self.repeater.clear()
            if self.available:
                self._schedule()

    def _schedule(self) -> None:
        if self._source:
            GLib.source_remove(self._source)
        self._source = GLib.timeout_add(16 if self.fast else 60, self._poll)

    def _load_user_mappings(self) -> None:
        from living_room.config import paths
        db = paths.config_dir() / "gamecontrollerdb.txt"
        if db.exists():
            try:
                n = sdl2.SDL_GameControllerAddMappingsFromFile(str(db).encode())
                log.info("Loaded %s controller mappings from %s", n, db)
            except Exception as exc:
                log.warning("Could not load %s: %s", db, exc)

    def capture_next_button(self, callback: Callable[[str], None] | None) -> None:
        self._capture = callback

    # -- polling -----------------------------------------------------------
    def _poll(self) -> bool:
        event = sdl2.SDL_Event()
        try:
            while sdl2.SDL_PollEvent(ctypes.byref(event)):
                self._handle(event)
        except Exception:
            log.exception("Error while processing controller events")
        for direction in self.repeater.tick(time.monotonic()):
            self._emit(direction, None)
        return GLib.SOURCE_CONTINUE

    def _emit(self, action: Action, info: ControllerInfo | None) -> None:
        if self.on_action:
            self.on_action(action, info)

    def _raw(self, text: str) -> None:
        for cb in list(self.raw_listeners):
            cb(text)

    def _handle(self, event) -> None:
        t = event.type
        if t == sdl2.SDL_CONTROLLERDEVICEADDED:
            self._open(event.cdevice.which)
        elif t == sdl2.SDL_CONTROLLERDEVICEREMOVED:
            self._close(event.cdevice.which)
        elif t in (sdl2.SDL_CONTROLLERBUTTONDOWN, sdl2.SDL_CONTROLLERBUTTONUP):
            info = self.controllers.get(event.cbutton.which)
            if info is None:
                return
            name = sdl2.SDL_GameControllerGetStringForButton(event.cbutton.button)
            name = name.decode() if name else f"button{event.cbutton.button}"
            down = t == sdl2.SDL_CONTROLLERBUTTONDOWN
            self._button(info, name, down)
        elif t == sdl2.SDL_CONTROLLERAXISMOTION:
            info = self.controllers.get(event.caxis.which)
            if info is None:
                return
            name = sdl2.SDL_GameControllerGetStringForAxis(event.caxis.axis)
            name = name.decode() if name else f"axis{event.caxis.axis}"
            self._axis(info, name, event.caxis.value)
        elif t in (sdl2.SDL_JOYDEVICEADDED, sdl2.SDL_JOYDEVICEREMOVED):
            if self.on_devices_changed:
                self.on_devices_changed()

    def _button(self, info: ControllerInfo, name: str, down: bool) -> None:
        self.last_family = info.family
        if down:
            info.pressed.add(name)
        else:
            info.pressed.discard(name)
        self._raw(f"{info.name}: {name} {'pressed' if down else 'released'}")
        source = f"ctrl:{info.instance_id}:dpad:{name}"
        if not down:
            self.repeater.release(source)
            return
        if self._capture and name not in DPAD_BUTTONS:
            cb, self._capture = self._capture, None
            cb(name)
            return
        action = resolve_action(self._bindings(), name)
        if action is None:
            return
        if action in DPAD_BUTTONS.values():
            for d in self.repeater.press(source, action, time.monotonic()):
                self._emit(d, info)
        else:
            self._emit(action, info)

    def _axis(self, info: ControllerInfo, name: str, value: int) -> None:
        info.axes[name] = value
        if name not in ("leftx", "lefty"):
            return
        info.stick.deadzone = self.deadzone
        info.stick.release_zone = self.deadzone * 0.7
        before = info.stick.direction
        direction = info.stick.update("x" if name == "leftx" else "y", value)
        if direction == before:
            return
        source = f"ctrl:{info.instance_id}:stick"
        if direction is None:
            self.repeater.release(source)
        else:
            self.last_family = info.family
            for d in self.repeater.press(source, direction, time.monotonic()):
                self._emit(d, info)

    # -- devices -----------------------------------------------------------
    def _open(self, device_index: int) -> None:
        handle = sdl2.SDL_GameControllerOpen(device_index)
        if not handle:
            log.warning("Could not open controller %d: %s", device_index,
                        sdl2.SDL_GetError().decode(errors="replace"))
            return
        joystick = sdl2.SDL_GameControllerGetJoystick(handle)
        instance = sdl2.SDL_JoystickInstanceID(joystick)
        if instance in self.controllers:
            sdl2.SDL_GameControllerClose(handle)
            return
        name = (sdl2.SDL_GameControllerName(handle) or b"Controller").decode(errors="replace")
        guid_buf = ctypes.create_string_buffer(64)
        sdl2.SDL_JoystickGetGUIDString(sdl2.SDL_JoystickGetGUID(joystick), guid_buf, 64)
        try:
            ctype = sdl2.SDL_GameControllerGetType(handle)
        except Exception:
            ctype = 0
        info = ControllerInfo(instance, name, _family(ctype), guid_buf.value.decode(), handle,
                              StickTracker(self.deadzone))
        self.controllers[instance] = info
        self.last_family = info.family
        log.info("Controller connected: %s (%s)", name, info.family)
        self._raw(f"Connected: {name}")
        if self.on_devices_changed:
            self.on_devices_changed()

    def _close(self, instance: int) -> None:
        info = self.controllers.pop(instance, None)
        if info is None:
            return
        self.repeater.release_prefix(f"ctrl:{instance}:")
        sdl2.SDL_GameControllerClose(info.handle)
        log.info("Controller disconnected: %s", info.name)
        self._raw(f"Disconnected: {info.name}")
        if self.on_devices_changed:
            self.on_devices_changed()

    def unmapped_joysticks(self) -> list[str]:
        """Joysticks SDL sees but has no game-controller mapping for."""
        if not self.available:
            return []
        out = []
        for i in range(sdl2.SDL_NumJoysticks()):
            if not sdl2.SDL_IsGameController(i):
                out.append((sdl2.SDL_JoystickNameForIndex(i) or b"Unknown").decode(errors="replace"))
        return out


def user_mapping_path() -> Path:
    from living_room.config import paths
    return paths.config_dir() / "gamecontrollerdb.txt"
