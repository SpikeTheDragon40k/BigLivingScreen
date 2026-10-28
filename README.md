# Big Living Screen


[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20me-FF5E5B?logo=kofi&logoColor=white)](https://ko-fi.com/spikethedragon)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support%20me-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/spike_the_dragon)



A fullscreen, controller-first application launcher for **Ubuntu GNOME**, in the spirit of
Steam Big Picture, KDE Plasma Bigscreen and smart-TV home screens. Pick Kodi, RetroDECK,
Netflix, Prime Video, Disney+ or any other installed application with a game controller from
the couch.

Living Room is a **normal unprivileged GTK 4 / libadwaita application that runs inside your
existing GNOME session**. It does not install KDE, replace GNOME Shell, touch GDM, change
display/HDMI settings, GPU drivers or kernel parameters.

```
┌───────────────────────────────────────────────────────────────┐
│  LIVING ROOM                         20:45   🔍  ⚙             │
│                                    Saturday 24 October        │
│  FAVORITES                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │   Kodi   │ │ RetroDECK│ │ Netflix  │ │  Prime   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ALL APPLICATIONS                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │Disney+ │ │Firefox │ │ Files  │ │Settings│ │  …     │       │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │
│  D-Pad Navigate   A Launch   Y Favorite   X Options   ☰ Settings │
└───────────────────────────────────────────────────────────────┘
```

## Features

- Large, rounded application cards, smooth focus animation, clock and date, dark theme,
  selectable background (gradients or your GNOME wallpaper), interface scaling that follows the
  screen resolution (designed for 1920×1080 at 2–3 m).
- **Controller navigation everywhere** — home screen, search, dialogs, settings — using SDL's
  normalized game-controller mapping (Xbox, PlayStation DualShock/DualSense, 8BitDo, Switch Pro
  and other SDL-compatible pads), USB and Bluetooth, hot-plug, several controllers at once,
  analog-stick dead zone with hysteresis, initial-delay + repeat for held directions.
- Keyboard fallback for everything (and mouse/touch work too).
- Application discovery via `Gio.AppInfo` / `Gio.DesktopAppInfo` (all XDG data dirs, including
  `~/.local/share/applications`, Flatpak exports and Snap entries), live refresh when apps are
  installed or removed.
- Launching via Gio (`launch_uris_as_manager` / `launch_action`): field codes, quoting,
  DBus-activatable apps, Flatpak and desktop actions are handled by GLib. **No shell is ever used.**
- Favorites: add with the **+ Add favorite** card at the end of the Favorites row (or Settings →
  Manage favorites → + Add favorite), which opens a picker of every installed app; or highlight any
  app and press Y, or X for its menu (Launch / Add to favorites / Hide / desktop actions).
  Remove with Y or the same menu; reorder (Options → Move, or Settings → Manage favorites), hide
  unwanted apps, uninstalled favorites stay in place as dimmed cards until you remove them.
- On-screen keyboard search (or just start typing on a keyboard).
- Controller remapping, controller test screen, optional GNOME autostart with crash-loop
  protection.

## Install (Ubuntu 26.04 GNOME)

```bash
git clone https://github.com/SpikeTheDragon40k/BigLivingScreen.git
cd BigLivingScreen
scripts/install.sh            # add --autostart to start after login
```

The installer:

1. Checks that `/usr/bin/python3` can import GTK 4, libadwaita and PySDL2. If not, it shows the
   `apt` command and **asks before running `sudo`**. The packages are:

   ```bash
   sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-sdl2
   ```

   `python3-sdl2` loads `libSDL2-2.0.so.0`; on releases where SDL2 is provided by
   `sdl2-compat` (SDL3 underneath) that works unchanged. Without PySDL2 the launcher still runs
   with keyboard only.
2. Copies the app to `~/.local/share/living-room/lib`, creates `~/.local/bin/living-room`,
   a desktop entry `~/.local/share/applications/io.github.spikethedragon40k.LivingRoom.desktop`
   and an icon. Nothing outside your home directory is written.

Then open **Living Room** from the GNOME app grid, or run `living-room`
(`living-room --windowed` for a window, `living-room --debug` for verbose logs).

> The repository's `data/living-room.desktop` is installed under the application ID name
> (`io.github.spikethedragon40k.LivingRoom.desktop`) so GNOME Shell matches the window to its
> entry on Wayland.

### Uninstall

```bash
scripts/uninstall.sh          # keeps ~/.config/living-room
scripts/uninstall.sh --purge  # also removes preferences and logs
```

Your own shortcuts (`~/.local/bin/streaming-kiosk`, `streaming-*.desktop`, icons) are never
created, modified or removed by install or uninstall.

## Controls

| Controller (SDL name) | Xbox / PlayStation label | Keyboard | Action |
|---|---|---|---|
| D-pad, left stick | | Arrows | Navigate |
| `a` (bottom face) | A / ✕ | Enter, Space | Launch / select |
| `b` (right face) | B / ○ | Esc, Backspace | Back / close |
| `y` (top face) | Y / △ | F | Add / remove favorite |
| `x` (left face) | X / □ | O, Menu | Application options |
| `leftshoulder` / `rightshoulder` | LB RB / L1 R1 | PgUp / PgDn | Switch section |
| `start` | Menu / Options | F1 | Settings |
| `back` | View / Share | `/`, Ctrl+F, or just type | Search |
| `guide` | Xbox / PS | Home | Home (see below) |
| | | F11 | Toggle fullscreen |
| | | Ctrl+Q | Quit |

Buttons other than the D-pad can be reassigned in **Settings → Controller mappings**. The
on-screen hints show the labels of the controller you used last. Living Room refuses mappings
that would leave *Select* or *Back* without a button, and the keyboard always works.

Nintendo-layout controllers: SDL reports buttons by their printed label by default, so "A"
is the right-hand button. Remap if you prefer positional behaviour.

## Your existing streaming shortcuts

`streaming-netflix.desktop`, `streaming-prime.desktop` and `streaming-disney.desktop` in
`~/.local/share/applications` are discovered like any other app; their absolute-path PNG icons
(including `dinsey.png`) are loaded directly. On first start, Kodi (`kodi.desktop`), RetroDECK
(`net.retrodeck.retrodeck.desktop`, Flatpak) and the three streaming entries are pre-added to
favorites if installed — change that freely.

Controller navigation *inside* Netflix/Prime/Disney+ in Chrome is a separate matter: those
websites are not natively gamepad-friendly, and Living Room does not inject input into other
applications. Use a remote-friendly mapping tool (see below) if you want that.

## Returning to Living Room — GNOME Wayland limitations

Living Room keeps running while another application is open, and it reads controllers through
SDL even in the background (it **ignores** all input while it is not the focused window, so
pressing A in Kodi never launches something behind your back).

What works:

- **When the launched app exits**, the launcher becomes usable again: GNOME focuses the next
  window, which is the fullscreen Living Room. Living Room also watches the process it started and
  calls `present()` when it ends.
- **Running `living-room` again** (e.g. from the app grid or the dock) brings the existing instance
  to the front — it is a single-instance `GApplication`, and because the request comes from GNOME
  Shell it carries a valid activation token.

What is limited:

- GNOME Wayland does **not** let applications grab global input or steal focus. When you press
  **Guide/Home** while another app is focused, Living Room *requests* activation, but GNOME
  normally shows a "Living Room is ready" notification instead of switching windows. This is
  intentional compositor policy; Living Room does not bypass it. (Toggle the behaviour in
  Settings → "Guide button brings back Living Room".)
- The controller's Guide button may also be seen by the foreground app (Kodi, Steam, …).

Reliable alternatives:

1. **Quit the app with its own controller mapping** — Kodi: *Power → Exit*, RetroDECK/ES-DE:
   *Quit*, Chrome kiosk: map a button to `Alt+F4` (below).
2. **GNOME keyboard shortcut**: Settings → Keyboard → View and customise shortcuts → Custom
   Shortcuts → `+`, command `living-room`, e.g. `Super+Home`. GNOME Shell runs it with an
   activation token, so the launcher is raised. Then map a controller chord to that key:
   - **Steam Input** (if you use Steam): add Living Room or Chrome as a non-Steam game and use a
     chord/“Guide + button” binding to send `Super+Home` or `Alt+F4`.
   - **Input Remapper** (`sudo apt install input-remapper`) or **AntiMicroX**: map e.g.
     *Back + Start* to `Super+Home`. Note these create a virtual input device; keep the mapping to a
     combination you don't use in games.

## Autostart and recovery

Settings → *Start automatically after login* (or `install.sh --autostart`) writes
`~/.config/autostart/living-room.desktop`. It starts after GNOME login on Wayland and X11. GDM,
the display manager configuration and automatic login are **not** touched — if you want the PC
to boot straight to the TV screen, enable automatic login yourself in GNOME Settings → Users.

Safety nets:

- Living Room is just a window: if it crashes, GNOME keeps running normally.
- **Crash-loop protection**: if Living Room exits uncleanly 3 times within 5 minutes, the next
  autostart is skipped.
- Disable autostart from a terminal (Ctrl+Alt+T): `living-room --disable-autostart`, or delete
  `~/.config/autostart/living-room.desktop`, or turn it off in GNOME Tweaks → Startup
  Applications.
- Leave fullscreen with F11 / Settings; quit with Ctrl+Q or Settings → Quit; or press the Super key
  to reach the GNOME overview.

## Configuration

`~/.config/living-room/config.json` (written atomically: temp file + fsync + rename). A corrupt
file is moved to `config.json.corrupt-<timestamp>` and defaults are used. It stores favorites
(desktop IDs, in order), hidden apps, settings and button bindings. Logs:
`~/.local/state/living-room/living-room.log` (no environment or secrets are logged).

Custom SDL controller mappings: put lines in SDL `gamecontrollerdb.txt` format into
`~/.config/living-room/gamecontrollerdb.txt`.

## Troubleshooting

| Problem | What to do |
|---|---|
| "Controller support unavailable" | `sudo apt install python3-sdl2`; check `python3 -c "import sdl2"`. |
| Controller not detected | Settings → Controller test. For USB pads check `ls -l /dev/input/event*` shows your user has access (systemd's `uaccess` ACL is applied to the active seat). For Bluetooth, pair in GNOME Settings first. If Steam is running it may grab the controller — close Steam or disable its Steam Input for that controller. |
| Listed as "Detected without a mapping" | Add a mapping line (e.g. from SDL_GameControllerDB) to `~/.config/living-room/gamecontrollerdb.txt` and restart. |
| DualSense/DualShock behaves oddly over USB | SDL may use hidraw; installing `steam-devices` (`sudo apt install steam-devices`) adds udev rules granting access. That is a system package; install only if needed. |
| An app is missing | Check it is visible in the GNOME app grid. Entries with `NoDisplay=true`, `Hidden=true`, `OnlyShowIn`/`NotShowIn` excluding GNOME, missing `TryExec`/`Exec` binaries are skipped on purpose. Settings → Refresh application list, and Settings → Hidden applications. |
| Icon missing | A generic icon is shown when the theme lacks it or the file path doesn't exist. |
| Launch fails | A message appears and the launcher keeps working; details are in the log. |
| Text too big/small | Settings → Interface scale. |
| Window not fullscreen | Settings → Fullscreen, or F11. |

## What has been tested

Tested in a headless cloud container (Ubuntu 24.04, GTK 4.14, libadwaita 1.5, SDL 2.30,
PySDL2 0.9.16, Python 3.12) — **not on your Lenovo, not on Ubuntu 26.04, not with a physical
controller, TV or real GNOME session**:

- Automated tests (`pytest`): desktop-entry discovery (user, system and Flatpak-export dirs,
  NoDisplay/Hidden/OnlyShowIn/NotShowIn/TryExec, invalid and garbage files, duplicate IDs,
  absolute-path PNG icons including `dinsey.png`, desktop actions), launching through Gio without
  a shell and failure reporting, favorites/hidden/bindings persistence, atomic writes,
  corrupt-config recovery, autostart and crash-loop detection, dead zone/hysteresis/repeat logic,
  spatial navigation, and an **end-to-end SDL test with SDL's virtual game controller**
  (hot-plug, button → action mapping, held-direction repeat, stick, unplug, remap capture).
- Manual run under Xvfb/X11 with screenshots: home screen, keyboard navigation, launching the
  streaming shortcuts (fake `streaming-kiosk`), launch toast and child-exit detection, Options
  dialog, Settings, Search, persistence of favorites across restarts.
- The running app driven by an SDL virtual controller: D-pad navigation, A launching the Netflix
  shortcut, hints switching to controller button labels.
- `install.sh` / `uninstall.sh` as a non-root user: installs only into `$HOME`, autostart entry
  uses an absolute path, uninstall removes everything it created and leaves the streaming files
  untouched.

**Unverified** (please check on the real machine): GNOME Wayland fullscreen and focus behaviour,
returning focus after Kodi/RetroDECK exit, Guide-button behaviour, real Xbox/PlayStation/8BitDo
controllers over USB and Bluetooth, Ubuntu 26.04 package names/versions, GNOME X11 session, Snap
entries.

## Development

```bash
python3 -m pytest              # needs python3-pytest plus the runtime packages
PYTHONPATH=src python3 -m living_room --windowed
```

Layout:

```
src/living_room/
  main.py                 Adw.Application, CLI options, logging
  applications/catalog.py Gio-based discovery + AppInfoMonitor refresh
  applications/launcher.py Gio launching, child watch
  controllers/input.py    Actions, repeat timing, stick dead zone (toolkit-free)
  controllers/sdl_backend.py SDL2 GameController polling on the GLib main loop
  config/                 JSON store, XDG paths, autostart + crash guard
  ui/                     window, pages, widgets, spatial navigation, CSS
tests/                    pytest suite (isolated XDG dirs)
scripts/                  install.sh, uninstall.sh
```

Architecture notes: SDL is initialised with only the game-controller subsystem and polled with
`GLib.timeout_add` (16 ms when focused, 60 ms in the background), so every SDL and GTK call
happens on the main thread without locks. Navigation is spatial (nearest focusable widget in
the pressed direction), so it works the same in grids, lists and dialogs.

Releases: push a tag `vX.Y.Z`; the only GitHub Action builds a source archive and publishes a
GitHub release.

## License

MIT — see [LICENSE](LICENSE).
