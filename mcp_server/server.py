"""MCP server wrapping the linux-computer-use bridge.

Exposes computer-use tools (list_windows, screenshot, click, type_text,
set_text, keypress, scroll, computer_actions, recording helpers) over MCP so any
MCP-aware agent (Claude Code, OpenCode, …) can drive Linux/X11 the same way
the Pi extension does.
"""
from __future__ import annotations

import base64
import itertools
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

# --- locate bridge ---------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_BRIDGE = _HERE.parent / "bridge" / "bridge.py"
if not _BRIDGE.exists():  # pragma: no cover
    raise RuntimeError(f"bridge.py not found at {_BRIDGE}")

# --- bridge process management --------------------------------------------

_procs: dict[str, subprocess.Popen] = {}
_recorders: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()
_id_seq = itertools.count(1)


def _python() -> str:
    # Prefer system python3 — bridge needs PyGObject (gi), which venvs lack.
    return "/usr/bin/python3" if Path("/usr/bin/python3").exists() else (shutil.which("python3") or "python3")


def _display_key(display: str = "") -> str:
    return display or os.environ.get("DISPLAY", "")


def _env_for_display(display: str = "") -> dict[str, str]:
    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    return env


def _display_size(display: str) -> str:
    xdpyinfo = shutil.which("xdpyinfo")
    if not xdpyinfo:
        return "1440x900"
    try:
        out = subprocess.run(
            [xdpyinfo, "-display", display],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            env=_env_for_display(display),
        ).stdout
    except Exception:
        return "1440x900"
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("dimensions:"):
            parts = line.split()
            if len(parts) >= 2 and "x" in parts[1]:
                return parts[1]
    return "1440x900"


def _spawn(display: str = "") -> subprocess.Popen:
    return subprocess.Popen(
        [_python(), str(_BRIDGE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=_env_for_display(display),
    )


def _bridge_call(cmd: str, args: dict[str, Any], display: str = "") -> Any:
    with _lock:
        key = _display_key(display)
        proc = _procs.get(key)
        if proc is None or proc.poll() is not None:
            proc = _spawn(display)
            _procs[key] = proc
        rid = str(next(_id_seq))
        req = {"id": rid, "cmd": cmd, **args}
        assert proc.stdin and proc.stdout
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        if not line:
            err = ""
            if proc.stderr:
                try:
                    err = proc.stderr.read() or ""
                except Exception:
                    pass
            raise RuntimeError(f"bridge died: {err.strip()}")
        resp = json.loads(line)
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error", "bridge error"))
        return resp.get("result")


# --- server ----------------------------------------------------------------

mcp = FastMCP("linux-computer-use")


@mcp.tool()
def list_windows(display: str = "") -> dict:
    """Enumerate visible X11 windows. Optional display targets another X display, e.g. ':99'."""
    return _bridge_call("list_windows", {}, display=display)


@mcp.tool()
def screenshot(window: str = "", display: str = "") -> list:
    """Capture window PNG + AT-SPI @eN targets. Optional display targets another X display."""
    res = _bridge_call("screenshot", {"window": window} if window else {}, display=display)
    png_b64 = res.pop("pngBase64", "")
    parts: list = [res]
    if png_b64:
        try:
            parts.append(Image(data=base64.b64decode(png_b64), format="png"))
        except Exception:
            # Fallback: write to /tmp and include path.
            path = f"/tmp/lcu-screenshot-{res.get('stateId','x')}.png"
            try:
                Path(path).write_bytes(base64.b64decode(png_b64))
                res["imagePath"] = path
            except Exception:
                pass
    return parts


@mcp.tool()
def click(ref: str = "", x: int = -1, y: int = -1, button: str = "left", click_count: int = 1, display: str = "") -> dict:
    """Click @eN, @wN, or absolute x,y. Optional display targets another X display."""
    args: dict[str, Any] = {"button": button, "clickCount": click_count}
    if ref:
        args["ref"] = ref
    if x >= 0:
        args["x"] = x
    if y >= 0:
        args["y"] = y
    return _bridge_call("click", args, display=display)


@mcp.tool()
def type_text(text: str, display: str = "") -> dict:
    """Type literal text at the current cursor. Optional display targets another X display."""
    return _bridge_call("type_text", {"text": text}, display=display)


@mcp.tool()
def set_text(ref: str, text: str, display: str = "") -> dict:
    """Replace value of an @eN text/entry via AT-SPI. Optional display targets another X display."""
    return _bridge_call("set_text", {"ref": ref, "text": text}, display=display)


@mcp.tool()
def keypress(keys: list[str], display: str = "") -> dict:
    """Press keys/chords: ['Enter'], ['ctrl','a'], ['ctrl+l','Return']. Optional display targets another X display."""
    return _bridge_call("keypress", {"keys": keys}, display=display)


@mcp.tool()
def scroll(ref: str = "", x: int = -1, y: int = -1, scroll_x: int = 0, scroll_y: int = 0, display: str = "") -> dict:
    """Scroll at ref/coords by pixel delta. Optional display targets another X display."""
    args: dict[str, Any] = {"scrollX": scroll_x, "scrollY": scroll_y}
    if ref:
        args["ref"] = ref
    if x >= 0:
        args["x"] = x
    if y >= 0:
        args["y"] = y
    return _bridge_call("scroll", args, display=display)


@mcp.tool()
def computer_actions(actions: list[dict], display: str = "") -> dict:
    """Batch multiple actions ({type:click|type_text|set_text|keypress|scroll, ...}). Optional display targets another X display."""
    return _bridge_call("computer_actions", {"actions": actions}, display=display)


@mcp.tool()
def start_recording(display: str = "", output_path: str = "", fps: int = 10) -> dict:
    """Record an X display to an mp4 with ffmpeg x11grab. Stop with stop_recording."""
    key = _display_key(display)
    if not key:
        raise RuntimeError("No DISPLAY set; pass display like ':0.0' or ':99'.")
    if key in _recorders and _recorders[key]["proc"].poll() is None:
        return {"display": key, "path": _recorders[key]["path"], "status": "already_recording"}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    if not output_path:
        out_dir = Path.home() / ".local" / "share" / "linux-computer-use" / "recordings"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_display = key.replace(":", "d").replace(".", "_")
        output_path = str(out_dir / f"computer-use-{safe_display}-{int(time.time())}.mp4")
    proc = subprocess.Popen(
        [
            ffmpeg,
            "-y",
            "-video_size",
            _display_size(key),
            "-framerate",
            str(fps),
            "-f",
            "x11grab",
            "-i",
            key,
            "-pix_fmt",
            "yuv420p",
            output_path,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=_env_for_display(display),
    )
    _recorders[key] = {"proc": proc, "path": output_path}
    return {"display": key, "path": output_path, "pid": proc.pid, "status": "recording"}


@mcp.tool()
def stop_recording(display: str = "") -> dict:
    """Stop an active X display recording and return the mp4 path."""
    key = _display_key(display)
    recorder = _recorders.get(key)
    if not recorder:
        return {"display": key, "status": "not_recording"}
    proc: subprocess.Popen = recorder["proc"]
    if proc.poll() is None:
        if proc.stdin:
            try:
                proc.stdin.write("q\n")
                proc.stdin.flush()
            except Exception:
                proc.terminate()
        else:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    _recorders.pop(key, None)
    return {"display": key, "path": recorder["path"], "returncode": proc.returncode, "status": "stopped"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
