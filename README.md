# pi-computer-use-linux

Token-efficient Linux/X11 computer-use tools for [Pi](https://github.com/mariozechner/pi-coding-agent) — a Linux port of [`@injaneity/pi-computer-use`](https://github.com/injaneity/pi-computer-use) using AT-SPI + xdotool instead of macOS AX/ScreenCaptureKit.

## Install

```bash
# system deps
sudo apt-get install -y python3 python3-gi gir1.2-atspi-2.0 xdotool wmctrl scrot
gsettings set org.gnome.desktop.interface toolkit-accessibility true   # enable AT-SPI

# pi extension
pi install git:github.com/tak-uukti/pi-computer-use-linux@v0.1.0
```

The postinstall step writes a small bash wrapper to `~/.pi/agent/helpers/pi-computer-use-linux/bridge` that execs `python3 bridge/bridge.py`. No build step, no codesign.

## Tools (8)

| name | description |
|---|---|
| `list_windows` | enumerate X11 windows (`@wN`, title, pid, geometry, focus) |
| `screenshot` | focus a window, capture PNG, return AT-SPI `@eN` targets |
| `click` | click ref or coordinates; supports button + clickCount |
| `type_text` | type literal text into focused control |
| `set_text` | replace value of `@eN` text/entry (AT-SPI; falls back to ctrl-a + type) |
| `keypress` | press keys/chords (`Enter`, `["Ctrl","A"]`, `["ctrl+l","Return"]`) |
| `scroll` | scroll at ref/coords by pixel delta |
| `computer_actions` | batch up to 20 actions in one call |

## Architecture

- `extensions/computer-use.ts` — registers the 8 tools with Pi.
- `src/bridge.ts` — manages a long-lived helper subprocess, newline-delimited JSON.
- `bridge/bridge.py` — Python 3 helper using AT-SPI (`gi.repository.Atspi`), `wmctrl`, `xdotool`, `scrot`.
- `scripts/setup-helper.mjs` — postinstall: writes the bash wrapper.

The AT-SPI walk is depth-capped (12) and element-capped (200) to keep prompts lean.

## Limitations (v0.1)

- **X11 only.** Wayland sessions cannot capture other-app windows or synthesize input via `xdotool`. Run a GNOME-on-Xorg, KDE-on-X11, or XFCE session.
- Apps must export AT-SPI (most GTK/Qt apps do; Electron requires `--force-renderer-accessibility`).
- Mouse cursor physically moves — no stealth pointer.
- No drag, no double_click tool, no arrange_window, no navigate_browser, no list_apps. Use `keypress({keys:["ctrl+l"]})` + `type_text` + `keypress({keys:["Return"]})` for browser nav.

## Development

```bash
npm run typecheck
python3 -c "import ast; ast.parse(open('bridge/bridge.py').read())"
echo '{"id":"1","cmd":"list_windows"}' | python3 bridge/bridge.py
```

## License

MIT © 2026 Tak1tak
