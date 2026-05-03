---
name: computer-use
description: Linux/X11 desktop control for Pi via AT-SPI + xdotool. Use to inspect, click, type into visible windows.
---

# computer-use (Linux/X11)

## Quick Start

```
list_windows                          # find @wN
screenshot {window:"@w2"}             # focus + capture; returns @eN AX targets + PNG
click {ref:"@e3"}                     # click an element
type_text {text:"hello"}              # type into focused control
keypress {keys:["Return"]}            # submit
```

## Tools

| name | use |
|---|---|
| list_windows | enumerate visible windows |
| screenshot | focus a window, capture PNG, return AX targets `@eN` |
| click | click `@eN`/`@wN` or `x,y`; supports `button`, `clickCount` |
| type_text | type literal text at cursor |
| set_text | replace value of an `@eN` text/entry field |
| keypress | press keys/chords (`Enter`, `["Ctrl","A"]`, `["ctrl+l","Return"]`) |
| scroll | scroll at ref/coords by `scrollY`/`scrollX` pixels |
| computer_actions | run a small sequence in one tool call |

## Pitfalls

- X11 only — Wayland sessions are not supported in v0.1.
- Enable AT-SPI: `gsettings set org.gnome.desktop.interface toolkit-accessibility true`.
- Keystrokes go to whatever has focus — call `screenshot {window}` first.
- Mouse cursor physically moves (no stealth pointer on X11).
- `screenshot` of `@wN` crops the full screen to that window's geometry.
- AX walk is capped at depth 12 / 200 elements per app to stay token-light.
