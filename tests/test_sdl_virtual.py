"""End-to-end test of the SDL backend using SDL's virtual game controller."""

import time

import pytest

sdl2 = pytest.importorskip("sdl2")

from gi.repository import GLib  # noqa: E402

from living_room.config.store import DEFAULT_BINDINGS  # noqa: E402
from living_room.controllers.sdl_backend import SDLInput  # noqa: E402


def spin(seconds):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ctx.iteration(False)
        time.sleep(0.004)


@pytest.fixture
def backend():
    if not hasattr(sdl2, "SDL_JoystickAttachVirtual"):
        pytest.skip("SDL too old for virtual joysticks")
    inp = SDLInput(lambda: DEFAULT_BINDINGS, repeat_delay=0.3, repeat_interval=0.1)
    if not inp.start():
        pytest.skip(f"SDL unavailable: {inp.error}")
    events = []
    inp.on_action = lambda action, info: events.append(action.value)
    yield inp, events
    inp.stop()


def attach(inp):
    index = sdl2.SDL_JoystickAttachVirtual(sdl2.SDL_JOYSTICK_TYPE_GAMECONTROLLER, 6, 15, 0)
    assert index >= 0
    spin(0.15)
    instance = next(iter(inp.controllers))
    return index, sdl2.SDL_JoystickFromInstanceID(instance)


def press(joy, button, hold=0.05):
    sdl2.SDL_JoystickSetVirtualButton(joy, button, 1)
    spin(hold)
    sdl2.SDL_JoystickSetVirtualButton(joy, button, 0)
    spin(0.05)


def test_hotplug_buttons_repeat_and_unplug(backend):
    inp, events = backend
    index, joy = attach(inp)
    assert len(inp.controllers) == 1
    press(joy, sdl2.SDL_CONTROLLER_BUTTON_A)
    press(joy, sdl2.SDL_CONTROLLER_BUTTON_B)
    press(joy, sdl2.SDL_CONTROLLER_BUTTON_Y)
    assert events == ["activate", "back", "favorite"]
    events.clear()
    press(joy, sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN, hold=0.65)
    # 1 initial + repeats every 0.1 s after 0.3 s
    assert events[0] == "down" and 3 <= len(events) <= 6 and set(events) == {"down"}
    events.clear()
    for value in (-30000, -25000, -18000, 0):  # one flick of the stick
        sdl2.SDL_JoystickSetVirtualAxis(joy, sdl2.SDL_CONTROLLER_AXIS_LEFTX, value)
        spin(0.03)
    assert events == ["left"]
    sdl2.SDL_JoystickDetachVirtual(index)
    spin(0.15)
    assert inp.controllers == {}


def test_capture_next_button_for_remapping(backend):
    inp, events = backend
    index, joy = attach(inp)
    captured = []
    inp.capture_next_button(captured.append)
    press(joy, sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP)   # d-pad is not capturable
    press(joy, sdl2.SDL_CONTROLLER_BUTTON_X)
    assert captured == ["x"]
    assert events == ["up"]
    sdl2.SDL_JoystickDetachVirtual(index)
    spin(0.1)
