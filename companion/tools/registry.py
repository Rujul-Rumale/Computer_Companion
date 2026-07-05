"""
tools/registry.py - Central computer control tool registry.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from tools.base import ToolResult
from tools.base import tool_spec as _tool_spec

# Import utility tool handlers
from tools.system_tools import battery_status, system_processes
from tools.utility_tools import (
    calculate,
    currency_convert,
    dictionary_lookup,
    generate_uuid,
    get_weather,
    network_info,
    news_headlines,
    notes_create,
    notes_delete,
    notes_list,
    notes_read,
    time_in,
    wikipedia_search,
)

APP_ALIASES: dict[str, list[str]] = {
    "chrome": ["chrome", "browser", "google"],
    "vscode": ["vscode", "vs code", "code", "editor"],
    "notepad": ["notepad"],
    "calculator": ["calculator", "calc"],
    "explorer": ["file explorer", "explorer"],
    "task manager": ["task manager", "taskmgr"],
    "settings": ["settings", "windows settings"],
}

APP_MAP = {
    "vscode": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vs code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "powershell": "powershell.exe",
}

_WEB_APPS: dict[str, dict] = {}
_WEB_APP_ALIASES: dict[str, str] = {}


def _load_web_apps() -> dict[str, dict]:
    global _WEB_APPS, _WEB_APP_ALIASES
    if _WEB_APPS:
        return _WEB_APPS
    path = Path(__file__).resolve().parent.parent / "config" / "web_apps.yaml"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        apps = data.get("web_apps", {})
        _WEB_APPS = apps
        for key, val in apps.items():
            for alias in val.get("aliases", []):
                _WEB_APP_ALIASES[alias] = key
        return apps
    except Exception:
        return {}


def resolve_web_app(name: str) -> str:
    """Resolve a web app name to its URL. Checks aliases and direct names."""
    key = name.strip().lower()
    apps = _load_web_apps()
    if key in apps:
        return apps[key]["url"]
    if key in _WEB_APP_ALIASES:
        return apps[_WEB_APP_ALIASES[key]]["url"]
    for canonical, val in apps.items():
        if key in canonical or canonical in key:
            return val["url"]
    return ""


def _guess_web_url(name: str) -> str:
    """Guess a plausible URL for a multi-word service name not in the registry."""
    raw = name.strip()
    if " " not in raw:
        return ""
    domain = raw.lower().replace(" ", "")
    domain = re.sub(r"[^a-z0-9.-]", "", domain)
    if not domain or len(domain) < 3:
        return ""
    return f"https://{domain}.com"


def _expand(path: str) -> str:
    return os.path.expandvars(path)


def _pyautogui():
    import pyautogui

    return pyautogui


def _normalize_app_name(name: str) -> str:
    return " ".join((name or "").lower().split())


def _resolve_app_path(app_name: str) -> tuple[str, str]:
    """Resolve an app name to (canonical, path). Checks aliases, hardcoded map, then scanned apps with fuzzy matching."""
    app_key = _normalize_app_name(app_name)
    if not app_key:
        return "", ""

    # 1. Check hardcoded aliases
    for canonical, aliases in APP_ALIASES.items():
        if app_key == canonical or app_key in aliases or any(alias in app_key for alias in aliases):
            candidate = APP_MAP.get(canonical) or APP_MAP.get(app_key) or canonical
            return canonical, _expand(candidate)

    # 2. Check hardcoded app map
    for canonical, path in APP_MAP.items():
        if app_key == _normalize_app_name(canonical):
            return canonical, _expand(path)

    # 3. Check scanned apps cache (exact + alias + fuzzy)
    from tools.app_scanner import load_cache
    apps = load_cache()
    if apps:
        # Exact match
        if app_key in apps:
            return app_key, apps[app_key]["path"]
        # Alias or substring match (works without rapidfuzz)
        best_name = ""
        for name, info in apps.items():
            if app_key in name or any(app_key in alias for alias in info.get("aliases", [])):
                best_name = name
                break
        if not best_name:
            # Fuzzy match via rapidfuzz (installed)
            from tools.app_search import fuzzy_find_app
            found_name, found_info = fuzzy_find_app(app_name)
            if found_name:
                return found_name, found_info["path"]
        else:
            return best_name, apps[best_name]["path"]

    return "", ""


def open_app(params: dict[str, Any]) -> ToolResult:
    app_name = str(params.get("name") or params.get("app_name") or "").strip()
    if not app_name:
        return ToolResult(False, "No app name given")

    canonical, resolved = _resolve_app_path(app_name)
    if not canonical:
        return ToolResult(False, f"Unknown app: {app_name}. Try open_web_app for online services.")
    try:
        if os.path.exists(resolved):
            os.startfile(resolved)
            return ToolResult(True, f"Opening {canonical or app_name}.", {"path": resolved})

        if resolved.lower().endswith((".exe", ".bat", ".cmd")) or resolved in {"wt.exe", "explorer.exe", "notepad.exe", "calc.exe", "powershell.exe"}:
            subprocess.Popen([resolved])
            return ToolResult(True, f"Opening {canonical or app_name}.", {"command": resolved})

        if canonical == "chrome":
            chrome_path = _expand(APP_MAP.get("chrome", "chrome.exe"))
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path])
                return ToolResult(True, f"Opening {canonical}.", {"path": chrome_path})

        return ToolResult(False, f"Could not open {canonical}: not found at {resolved}")
    except Exception as exc:
        return ToolResult(False, f"Could not open {app_name}: {exc}")


def open_url(params: dict[str, Any]) -> ToolResult:
    url = str(params.get("url") or "").strip()
    if not url:
        return ToolResult(False, "No URL provided")
    if not url.startswith("http"):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return ToolResult(True, f"Opened {url}.")
    except Exception as exc:
        return ToolResult(False, f"Could not open URL: {exc}")


def open_web_app(params: dict[str, Any]) -> ToolResult:
    name = str(params.get("name") or params.get("app") or "").strip()
    if not name:
        return ToolResult(False, "No web app name given")
    url = resolve_web_app(name)
    if not url:
        url = _guess_web_url(name)
    if not url:
        return ToolResult(False, f"Unknown web app: {name}")
    return open_url({"url": url})


def search_web(params: dict[str, Any]) -> ToolResult:
    """Open a search URL in the browser. For fetching results, use web_search_results."""
    from tools.web_search import build_search_url
    platform = str(params.get("platform") or params.get("site") or "").strip()
    query = str(params.get("query") or "").strip()
    if not platform:
        return ToolResult(False, "No platform specified for search")
    if not query:
        return ToolResult(False, "No search query provided")
    url = build_search_url(platform, query)
    if not url:
        return ToolResult(False, f"Unknown search platform: {platform}")
    return open_url({"url": url})


def refresh_apps(params: dict[str, Any]) -> ToolResult:
    from tools.app_scanner import refresh_cache
    try:
        count = len(refresh_cache())
        return ToolResult(True, f"Refreshed {count} installed applications.")
    except Exception as exc:
        return ToolResult(False, f"App scan failed: {exc}")


def clipboard_get(params: dict[str, Any]) -> ToolResult:
    from tools.clipboard import _get_manager
    text = _get_manager().get()
    return ToolResult(True, text if text else "Clipboard is empty", {"text": text})


def clipboard_set(params: dict[str, Any]) -> ToolResult:
    from tools.clipboard import _get_manager
    text = str(params.get("text") or "").strip()
    if not text:
        return ToolResult(False, "No text provided")
    ok = _get_manager().set(text)
    return ToolResult(ok, "Clipboard set" if ok else "Failed to set clipboard")


def clipboard_history(params: dict[str, Any]) -> ToolResult:
    from tools.clipboard import _get_manager
    limit = int(params.get("limit", 10))
    items = _get_manager().history(limit)
    if not items:
        return ToolResult(True, "Clipboard history is empty", {"items": []})
    return ToolResult(True, f"Clipboard history ({len(items)} items)", {"items": items})


def get_system_status(params: dict[str, Any]) -> ToolResult:
    from tools.system_tools import format_status, system_status
    status = system_status()
    summary = format_status(status)
    return ToolResult(True, summary, status)


def list_windows(params: dict[str, Any]) -> ToolResult:
    from tools.window_tools import window_list
    windows = window_list()
    if not windows:
        return ToolResult(True, "No visible windows found", {"windows": []})
    titles = "\n".join(f"{w['title']} ({w['width']}x{w['height']})" for w in windows[:20])
    return ToolResult(True, f"Windows ({len(windows)}):\n{titles}", {"windows": windows})


def focus_window_tool(params: dict[str, Any]) -> ToolResult:
    from tools.window_tools import focus_window
    identifier = str(params.get("title") or params.get("name") or "").strip()
    if not identifier:
        return ToolResult(False, "No window title provided")
    ok, msg = focus_window(identifier)
    return ToolResult(ok, f"Focused: {msg}" if ok else msg)


def set_timer_tool(params: dict[str, Any]) -> ToolResult:
    from tools.timer import set_timer
    duration = float(params.get("duration", params.get("seconds", 60)))
    label = str(params.get("label", "Timer"))
    if duration <= 0:
        return ToolResult(False, "Duration must be positive")
    tid = set_timer(duration, label)
    return ToolResult(True, f"Timer #{tid} set for {duration}s: {label}", {"id": tid, "duration": duration, "label": label})


def cancel_timer_tool(params: dict[str, Any]) -> ToolResult:
    from tools.timer import cancel_timer
    tid = int(params.get("id", 0))
    ok = cancel_timer(tid)
    return ToolResult(ok, f"Timer #{tid} cancelled" if ok else f"Timer #{tid} not found")


def list_timers_tool(params: dict[str, Any]) -> ToolResult:
    from tools.timer import list_timers
    timers = list_timers()
    if not timers:
        return ToolResult(True, "No active timers", {"timers": []})
    lines = [f"#{t['id']} {t['label']} ({t['remaining']}s remaining)" for t in timers]
    return ToolResult(True, "\n".join(lines), {"timers": timers})


def read_file(params: dict[str, Any]) -> ToolResult:
    """Read a file and return its text content. Supports .txt, .docx, .pdf, code, config, etc."""
    path = str(params.get("path") or "").strip()
    if not path:
        return ToolResult(False, "No file path provided")
    resolved = Path(path)
    if not resolved.exists():
        return ToolResult(False, f"File not found: {path}")
    if not resolved.is_file():
        return ToolResult(False, f"Not a file: {path}")

    ext = resolved.suffix.lower()
    try:
        if ext == ".docx":
            from docx import Document as DocxDocument
            doc = DocxDocument(str(resolved))
            text = "\n".join(p.text for p in doc.paragraphs)
        elif ext == ".pdf":
            import fitz
            doc = fitz.open(str(resolved))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
        else:
            text = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return ToolResult(False, f"Failed to read {path}: {exc}")

    max_chars = 16000
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"
    return ToolResult(True, text, {"path": path, "size": len(text)})


def search_files_tool(params: dict[str, Any]) -> ToolResult:
    from tools.file_search import search_files
    query = str(params.get("query") or "").strip()
    directory = str(params.get("directory") or "").strip()
    search_type = str(params.get("type", "name")).strip()
    max_results = int(params.get("max_results", 20))
    days = int(params.get("days", 7))

    if search_type not in ("name", "content", "date"):
        return ToolResult(False, "Search type must be name, content, or date")

    if search_type in ("name", "content") and not query:
        return ToolResult(False, "Query required for name/content search")

    results = search_files(query, directory, search_type, max_results, days)
    if not results:
        return ToolResult(True, f"No files found ({search_type})", {"files": []})

    lines = []
    for r in results[:20]:
        if "line" in r:
            lines.append(f"{r['path']}:{r['line']}  {r['snippet']}")
        else:
            lines.append(f"{r['path']}")
    return ToolResult(
        True,
        f"Found {len(results)} files:\n" + "\n".join(lines),
        {"files": results},
    )


def get_active_window(params: dict[str, Any]) -> ToolResult:
    from tools.active_window_tracker import get_active_window_info
    info = get_active_window_info()
    title = info.get("title", "")
    proc = info.get("process_name", "")
    if title:
        return ToolResult(True, f"Active window: {title} ({proc})", data=info)
    return ToolResult(False, "No active window detected", data=info)


def minimize_window(params: dict[str, Any]) -> ToolResult:
    try:
        _pyautogui().hotkey("win", "down")
        return ToolResult(True, "Minimized the active window.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def maximize_window(params: dict[str, Any]) -> ToolResult:
    try:
        _pyautogui().hotkey("win", "up")
        return ToolResult(True, "Maximized the active window.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def close_window(params: dict[str, Any]) -> ToolResult:
    try:
        _pyautogui().hotkey("alt", "f4")
        return ToolResult(True, "Closed the active window.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def set_speech_speed_tool(params: dict[str, Any]) -> ToolResult:
    rate = float(params.get("rate", 1.0))
    if rate < 0.25 or rate > 4.0:
        return ToolResult(False, "Speed must be between 0.25 and 4.0")
    if _TTS_SPEED_CALLBACK:
        _TTS_SPEED_CALLBACK(rate)
        return ToolResult(True, f"Speech speed set to {rate}x")
    return ToolResult(False, "TTS manager not available")


def switch_window(params: dict[str, Any]) -> ToolResult:
    direction = str(params.get("direction", "next")).lower()
    count = int(params.get("count", 1) or 1)
    count = max(1, min(count, 10))
    try:
        pyautogui = _pyautogui()
        for _ in range(count):
            if direction == "prev":
                pyautogui.hotkey("alt", "shift", "tab")
            else:
                pyautogui.keyDown("alt")
                pyautogui.press("tab")
                pyautogui.keyUp("alt")
        return ToolResult(True, f"Switched window ({direction}).")
    except Exception as exc:
        return ToolResult(False, str(exc))


def show_desktop(params: dict[str, Any]) -> ToolResult:
    try:
        _pyautogui().hotkey("win", "d")
        return ToolResult(True, "Showed desktop.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def press_key(params: dict[str, Any]) -> ToolResult:
    key = str(params.get("key", "")).strip()
    if not key:
        return ToolResult(False, "No key provided")
    try:
        _pyautogui().press(key)
        return ToolResult(True, f"Pressed {key}.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def hotkey(params: dict[str, Any]) -> ToolResult:
    raw_keys = params.get("keys") or params.get("key") or []
    if isinstance(raw_keys, str):
        keys = [part.strip() for part in raw_keys.replace("+", ",").split(",") if part.strip()]
    else:
        keys = [str(part).strip() for part in raw_keys if str(part).strip()]
    if not keys:
        return ToolResult(False, "No keys provided")
    try:
        _pyautogui().hotkey(*keys)
        return ToolResult(True, f"Pressed hotkey {'+'.join(keys)}.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def type_text(params: dict[str, Any]) -> ToolResult:
    text = str(params.get("text", ""))
    if not text:
        return ToolResult(False, "No text provided")
    try:
        _pyautogui().write(text, interval=0.01)
        return ToolResult(True, "Typed text into the active app.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def move_mouse(params: dict[str, Any]) -> ToolResult:
    try:
        x = int(params.get("x"))
        y = int(params.get("y"))
        _pyautogui().moveTo(x, y)
        return ToolResult(True, f"Moved mouse to {x}, {y}.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def click(params: dict[str, Any]) -> ToolResult:
    try:
        x = int(params.get("x"))
        y = int(params.get("y"))
        button = str(params.get("button", "left"))
        clicks = int(params.get("clicks", 1) or 1)
        _pyautogui().click(x=x, y=y, button=button, clicks=clicks)
        return ToolResult(True, f"Clicked at {x}, {y}.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def scroll(params: dict[str, Any]) -> ToolResult:
    try:
        amount = int(params.get("amount", 0) or 0)
        _pyautogui().scroll(amount)
        return ToolResult(True, f"Scrolled {amount}.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def set_volume(params: dict[str, Any]) -> ToolResult:
    try:
        level = int(params.get("level", 50) or 50)
        level = max(0, min(100, level))
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return ToolResult(True, f"Volume set to {level}%.")
        except Exception:
            pyautogui = _pyautogui()
            for _ in range(20):
                pyautogui.press("volumedown")
            steps = max(1, level // 5)
            for _ in range(steps):
                pyautogui.press("volumeup")
            return ToolResult(True, f"Volume adjusted to about {level}%.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def volume_up(params: dict[str, Any]) -> ToolResult:
    try:
        _pyautogui().press("volumeup")
        return ToolResult(True, "Volume increased.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def volume_down(params: dict[str, Any]) -> ToolResult:
    try:
        _pyautogui().press("volumedown")
        return ToolResult(True, "Volume decreased.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def mute(params: dict[str, Any]) -> ToolResult:
    try:
        _pyautogui().press("volumemute")
        return ToolResult(True, "Muted audio.")
    except Exception as exc:
        return ToolResult(False, str(exc))


def open_folder(params: dict[str, Any]) -> ToolResult:
    path = str(params.get("path") or Path.home()).strip()
    expanded = _expand(path)
    try:
        os.startfile(expanded)
        return ToolResult(True, f"Opened folder: {expanded}")
    except Exception as exc:
        return ToolResult(False, str(exc))


def open_settings(params: dict[str, Any]) -> ToolResult:
    try:
        os.startfile("ms-settings:")
        return ToolResult(True, "Opened Settings.")
    except Exception:
        try:
            subprocess.Popen(["powershell", "-Command", "Start-Process ms-settings:"])
            return ToolResult(True, "Opened Settings.")
        except Exception as exc:
            return ToolResult(False, str(exc))


def open_task_manager(params: dict[str, Any]) -> ToolResult:
    try:
        os.startfile("taskmgr.exe")
        return ToolResult(True, "Opened Task Manager.")
    except Exception:
        try:
            subprocess.Popen(["taskmgr.exe"])
            return ToolResult(True, "Opened Task Manager.")
        except Exception as exc:
            return ToolResult(False, str(exc))


def take_screenshot(params: dict[str, Any]) -> ToolResult:
    try:
        from PIL import Image as _PILImage

        from config import get_config

        cfg = get_config()
        path = cfg.screenshot_path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img = _pyautogui().screenshot()
        # Downscale to 720p max dimension for faster LLM processing
        _max_wh = 720
        w, h = img.size
        if w > _max_wh or h > _max_wh:
            scale = min(_max_wh / w, _max_wh / h)
            img = img.resize((int(w * scale), int(h * scale)), _PILImage.Resampling.LANCZOS)
        img.save(path)
        return ToolResult(True, f"Screenshot saved: {path}", {"path": path})
    except Exception as exc:
        return ToolResult(False, f"Screenshot failed: {exc}")


TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "open_app": _tool_spec(
        name="open_app",
        description="Open an installed desktop program. NOT for websites or online services.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "App name or alias (e.g. chrome, vscode, notepad)"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        handler=open_app,
        aliases=["launch_app", "open_application"],
    ),
    "open_url": _tool_spec(
        name="open_url",
        description="Open any URL or website in the default browser.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The URL or website name to open (e.g. https://example.com)"}},
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=open_url,
        aliases=["open_website", "navigate", "go_to"],
    ),
    "open_web_app": _tool_spec(
        name="open_web_app",
        description="Open any website or online service by name (YouTube, Prime Video, Netflix, Gmail, etc.). Not for installed programs.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Service or website name (e.g. youtube, prime video, netflix, gmail)"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        handler=open_web_app,
        aliases=["open_online_service", "open_website"],
    ),
    "get_active_window": _tool_spec(
        name="get_active_window",
        description="Get the title and process name of the focused window.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=get_active_window,
    ),
    "minimize_window": _tool_spec(
        name="minimize_window",
        description="Minimize the active window.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=minimize_window,
    ),
    "maximize_window": _tool_spec(
        name="maximize_window",
        description="Maximize the active window.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=maximize_window,
    ),
    "close_window": _tool_spec(
        name="close_window",
        description="Close the active window.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=close_window,
    ),
    "switch_window": _tool_spec(
        name="switch_window",
        description="Switch to the next or previous window.",
        parameters={
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["next", "prev"], "default": "next"},
                "count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1},
            },
            "additionalProperties": False,
        },
        handler=switch_window,
    ),
    "show_desktop": _tool_spec(
        name="show_desktop",
        description="Show the desktop.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=show_desktop,
    ),
    "press_key": _tool_spec(
        name="press_key",
        description="Press a single key.",
        parameters={
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
            "additionalProperties": False,
        },
        handler=press_key,
    ),
    "hotkey": _tool_spec(
        name="hotkey",
        description="Press a key combination such as ctrl+s.",
        parameters={
            "type": "object",
            "properties": {
                "keys": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        {"type": "string"},
                    ]
                }
            },
            "required": ["keys"],
            "additionalProperties": False,
        },
        handler=hotkey,
    ),
    "type_text": _tool_spec(
        name="type_text",
        description="Type text into the active application. For web searches use search_web.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        handler=type_text,
    ),
    "move_mouse": _tool_spec(
        name="move_mouse",
        description="Move the mouse cursor to screen coordinates.",
        parameters={
            "type": "object",
            "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            "required": ["x", "y"],
            "additionalProperties": False,
        },
        handler=move_mouse,
    ),
    "click": _tool_spec(
        name="click",
        description="Click at screen coordinates.",
        parameters={
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "clicks": {"type": "integer", "minimum": 1, "maximum": 5, "default": 1},
            },
            "required": ["x", "y"],
            "additionalProperties": False,
        },
        handler=click,
    ),
    "scroll": _tool_spec(
        name="scroll",
        description="Scroll the active window.",
        parameters={
            "type": "object",
            "properties": {"amount": {"type": "integer"}},
            "required": ["amount"],
            "additionalProperties": False,
        },
        handler=scroll,
    ),
    "set_volume": _tool_spec(
        name="set_volume",
        description="Set system volume from 0 to 100.",
        parameters={
            "type": "object",
            "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}},
            "required": ["level"],
            "additionalProperties": False,
        },
        handler=set_volume,
    ),
    "volume_up": _tool_spec(
        name="volume_up",
        description="Increase system volume.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=volume_up,
    ),
    "volume_down": _tool_spec(
        name="volume_down",
        description="Decrease system volume.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=volume_down,
    ),
    "mute": _tool_spec(
        name="mute",
        description="Mute system audio.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=mute,
    ),
    "open_folder": _tool_spec(
        name="open_folder",
        description="Open a folder in File Explorer.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=open_folder,
    ),
    "open_settings": _tool_spec(
        name="open_settings",
        description="Open Windows Settings.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=open_settings,
    ),
    "open_task_manager": _tool_spec(
        name="open_task_manager",
        description="Open Windows Task Manager.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=open_task_manager,
    ),
    "take_screenshot": _tool_spec(
        name="take_screenshot",
        description="",  # hidden from LLM — auto-capture handles this
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=take_screenshot,
        hidden=True,
    ),
    "search_web": _tool_spec(
        name="search_web",
        description="Search YouTube, Google, Amazon, GitHub, Maps, etc. and open results in browser.",
        parameters={
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["youtube", "google", "amazon", "github", "maps", "reddit", "scholar", "stackoverflow", "bing", "duckduckgo"],
                    "description": "Platform to search (youtube, google, amazon, github, maps, etc.)",
                },
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["platform", "query"],
            "additionalProperties": False,
        },
        handler=search_web,
    ),
    "refresh_apps": _tool_spec(
        name="refresh_apps",
        description="Rescan Start Menu for newly installed apps.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=refresh_apps,
    ),
    "clipboard_get": _tool_spec(
        name="clipboard_get",
        description="Read the current text from the system clipboard.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=clipboard_get,
        aliases=["read_clipboard", "get_clipboard"],
    ),
    "clipboard_set": _tool_spec(
        name="clipboard_set",
        description="Set the system clipboard to the given text.",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to copy to clipboard"}},
            "required": ["text"],
            "additionalProperties": False,
        },
        handler=clipboard_set,
        aliases=["write_clipboard", "copy_to_clipboard"],
    ),
    "clipboard_history": _tool_spec(
        name="clipboard_history",
        description="Show recent clipboard history.",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Number of recent entries to return", "default": 10}},
            "additionalProperties": False,
        },
        handler=clipboard_history,
    ),
    "system_status": _tool_spec(
        name="system_status",
        description="Get CPU, RAM, disk, battery, and uptime.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=get_system_status,
        aliases=["status", "sysinfo", "system_info"],
    ),
    "window_list": _tool_spec(
        name="window_list",
        description="List all visible open windows.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=list_windows,
        aliases=["list_windows", "enum_windows"],
    ),
    "focus_window": _tool_spec(
        name="focus_window",
        description="Bring a window to the foreground by title (exact or fuzzy match).",
        parameters={
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Window title to search for"}},
            "required": ["title"],
            "additionalProperties": False,
        },
        handler=focus_window_tool,
        aliases=["switch_to", "bring_to_front", "activate_window"],
    ),
    "set_timer": _tool_spec(
        name="set_timer",
        description="Set a timer that will notify when expired.",
        parameters={
            "type": "object",
            "properties": {
                "duration": {"type": "number", "description": "Duration in seconds"},
                "label": {"type": "string", "description": "Label for the timer (default: Timer)"},
            },
            "required": ["duration"],
            "additionalProperties": False,
        },
        handler=set_timer_tool,
        aliases=["start_timer", "timer"],
    ),
    "cancel_timer": _tool_spec(
        name="cancel_timer",
        description="Cancel an active timer by ID.",
        parameters={
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "Timer ID to cancel"}},
            "required": ["id"],
            "additionalProperties": False,
        },
        handler=cancel_timer_tool,
    ),
    "list_timers": _tool_spec(
        name="list_timers",
        description="List all active timers and their remaining time.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=list_timers_tool,
        aliases=["active_timers", "timer_list"],
    ),
    "file_search": _tool_spec(
        name="file_search",
        description="Search files by name, content, or modification date. Can search a specific directory or the current directory.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (required for name/content search)"},
                "directory": {"type": "string", "description": "Directory to search (default: current directory)"},
                "type": {"type": "string", "enum": ["name", "content", "date"], "description": "Search type: name (filename match), content (text search), date (recently modified)", "default": "name"},
                "max_results": {"type": "integer", "description": "Maximum results (max 30)", "default": 20},
                "days": {"type": "integer", "description": "Days back for date search (default: 7)", "default": 7},
            },
            "additionalProperties": False,
        },
        handler=search_files_tool,
        aliases=["find_file", "search_file", "find"],
    ),
    "read_file": _tool_spec(
        name="read_file",
        description="Read a file and return its text content. Supports .txt, .py, .md, .json, .csv, .docx, .pdf, and many other formats. Use this to proofread, summarize, or check file contents.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        handler=read_file,
        aliases=["view_file", "open_file", "cat"],
    ),
    "web_search_results": _tool_spec(
        name="web_search_results",
        description="Search the web and return titles, URLs, and snippets. Use for answering questions about current events, comparing things, or verifying facts.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {"type": "integer", "description": "Number of results (max 10)", "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=lambda p: _web_search_results(p),
        aliases=["web_search", "search_results"],
    ),
    "web_read_page": _tool_spec(
        name="web_read_page",
        description="Fetch a web page and extract readable article text.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Page URL to read"},
                "max_chars": {"type": "integer", "description": "Max characters to return", "default": 8000},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        handler=lambda p: _web_read_page(p),
        aliases=["read_page", "fetch_page"],
    ),
    "web_search_deep": _tool_spec(
        name="web_search_deep",
        description="Search the web AND read the top result in one call. Best for getting detailed info about a topic.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=lambda p: _web_search_deep(p),
    ),
    "set_speech_speed": _tool_spec(
        name="set_speech_speed",
        description="Set TTS speech rate (0.25-4.0, default 1.0).",
        parameters={
            "type": "object",
            "properties": {
                "rate": {"type": "number", "description": "Speech speed multiplier (0.25 - 4.0)", "default": 1.0},
            },
            "required": ["rate"],
            "additionalProperties": False,
        },
        handler=set_speech_speed_tool,
        aliases=["tts_speed", "speech_rate", "set_tts_speed"],
    ),
    "get_weather": _tool_spec(
        name="get_weather",
        description="Get current weather conditions for a city — temperature, humidity, wind.",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name (e.g. Hyderabad, London)"}},
            "required": ["city"],
            "additionalProperties": False,
        },
        handler=get_weather,
        aliases=["weather", "weather_forecast"],
    ),
    "calculate": _tool_spec(
        name="calculate",
        description="Evaluate a mathematical expression. Supports arithmetic, trig, logs, constants (pi, e). Examples: 2+2, sin(pi/4), sqrt(144), log10(100).",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Math expression to evaluate"}},
            "required": ["expression"],
            "additionalProperties": False,
        },
        handler=calculate,
        aliases=["math", "calc", "evaluate"],
    ),
    "wikipedia": _tool_spec(
        name="wikipedia",
        description="Search Wikipedia and return a summary of the article.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Topic to search for on Wikipedia"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=wikipedia_search,
        aliases=["wiki", "wikipedia_summary"],
    ),
    "battery_status": _tool_spec(
        name="battery_status",
        description="Check laptop battery level, charging status, and estimated time remaining.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=battery_status,
        aliases=["battery", "battery_check", "power_status"],
    ),
    "system_processes": _tool_spec(
        name="system_processes",
        description="List top running processes by CPU or memory usage.",
        parameters={
            "type": "object",
            "properties": {
                "sort_by": {"type": "string", "enum": ["cpu", "memory"], "default": "cpu", "description": "Sort by cpu or memory usage"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "additionalProperties": False,
        },
        handler=system_processes,
        aliases=["processes", "top", "ps"],
    ),
    "network_info": _tool_spec(
        name="network_info",
        description="Get public IP, local IP, ping latency, and active network interfaces.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=network_info,
        aliases=["network", "net_info", "ip_info"],
    ),
    "news_headlines": _tool_spec(
        name="news_headlines",
        description="Get latest news headlines and snippets via web search.",
        parameters={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "News topic or query (default: latest news India today)", "default": "latest news India today"},
                "count": {"type": "integer", "description": "Number of headlines", "default": 5},
            },
            "additionalProperties": False,
        },
        handler=news_headlines,
        aliases=["news", "headlines", "top_news"],
    ),
    "dictionary": _tool_spec(
        name="dictionary",
        description="Look up a word — get definition, phonetic, and example sentence.",
        parameters={
            "type": "object",
            "properties": {"word": {"type": "string", "description": "Word to define"}},
            "required": ["word"],
            "additionalProperties": False,
        },
        handler=dictionary_lookup,
        aliases=["define", "definition", "dict"],
    ),
    "currency_convert": _tool_spec(
        name="currency_convert",
        description="Convert an amount between currencies (e.g. USD to INR, EUR to USD).",
        parameters={
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "Amount to convert", "default": 1},
                "from": {"type": "string", "description": "Source currency code (e.g. USD, EUR, INR)"},
                "to": {"type": "string", "description": "Target currency code (e.g. INR, EUR, GBP)"},
            },
            "required": ["from", "to"],
            "additionalProperties": False,
        },
        handler=currency_convert,
        aliases=["convert_currency", "currency", "exchange_rate"],
    ),
    "notes": _tool_spec(
        name="notes",
        description="Manage persistent notes. Sub-actions: create (title+content), list (no args), read (id), delete (id). Default: list all notes.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "list", "read", "delete"], "default": "list"},
                "title": {"type": "string", "description": "Note title (for create)"},
                "content": {"type": "string", "description": "Note content (for create)"},
                "id": {"type": "string", "description": "Note ID (for read/delete)"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        handler=lambda p: {
            "create": notes_create,
            "list": notes_list,
            "read": notes_read,
            "delete": notes_delete,
        }.get(p.get("action", "list"), notes_list)(p),
        aliases=["note", "memo", "save_note", "my_notes"],
    ),
    "time_in": _tool_spec(
        name="time_in",
        description="Get the current time in any timezone. Supports common abbreviations (IST, PST, GMT, UTC, CET, etc.) and IANA names (Asia/Kolkata, US/Eastern).",
        parameters={
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "Timezone name or abbreviation (e.g. IST, PST, Asia/Kolkata, US/Eastern)"},
            },
            "required": ["timezone"],
            "additionalProperties": False,
        },
        handler=time_in,
        aliases=["current_time", "what_time", "convert_time"],
    ),
    "uuid": _tool_spec(
        name="uuid",
        description="Generate a random UUID (version 4 by default).",
        parameters={
            "type": "object",
            "properties": {
                "version": {"type": "integer", "enum": [1, 4, 7], "default": 4},
            },
            "additionalProperties": False,
        },
        handler=generate_uuid,
        aliases=["generate_uuid", "gen_uuid"],
    ),
}

def _web_search_results(params: dict[str, Any]) -> ToolResult:
    from tools.web_research import web_search_results
    return web_search_results(params)


def _web_read_page(params: dict[str, Any]) -> ToolResult:
    from tools.web_research import web_read_page
    return web_read_page(params)


def _web_search_deep(params: dict[str, Any]) -> ToolResult:
    from tools.web_research import web_search_deep
    return web_search_deep(params)


_TOOL_ALIASES = {
    alias: canonical
    for canonical, spec in TOOL_REGISTRY.items()
    for alias in spec.get("aliases", [])
}

_TTS_SPEED_CALLBACK: Callable[[float], None] | None = None


def set_tts_speed_callback(cb: Callable[[float], None]):
    global _TTS_SPEED_CALLBACK
    _TTS_SPEED_CALLBACK = cb


def normalize_tool_name(name: str) -> str:
    tool_name = " ".join((name or "").lower().split())
    return _TOOL_ALIASES.get(tool_name, tool_name)




def tool_prompt_block() -> str:
    return (
        "Tools:\n"
        "- Apps: open_app (installed), open_web_app (YouTube/GitHub/etc), open_url.\n"
        "- Search: search_web (YouTube/Google/Amazon/GitHub/Maps). Not type_text.\n"
        "- Desktop: window_list, focus_window, minimize/maximize/close window, show_desktop.\n"
        "- Mouse & KB: move_mouse, click, scroll, type_text, hotkey, press_key.\n"
        "- Clipboard: clipboard_get/set/history.\n"
        "- Audio: set_volume, volume_up/down, mute, set_speech_speed.\n"
        "- System: system_status, battery_status, system_processes, network_info, open_folder/settings/task_manager.\n"
        "- Timers: set_timer, cancel_timer, list_timers.\n"
        "- Files: file_search (find files), read_file (read .txt/.docx/.pdf/code and return content).\n"
        "- Web: web_search_results (search web, get text results back), web_search_deep (search + read top result), web_read_page (extract full article text from URL).\n"
        "- Info: wikipedia (article summary), dictionary (definition), calculate (math), currency_convert.\n"
        "- Data: notes (persistent create/list/read/delete), news_headlines, get_weather, time_in, uuid.\n"
        "- Other: get_active_window, refresh_apps.\n"
        "Priority: search_web > open_web_app > open_url > open_app. "
        "Never use type_text for searches."
    )


def execute_tool(tool_name: str, params: dict[str, Any] | None = None, *, require_confirmation: bool = False) -> ToolResult:
    tool_name = normalize_tool_name(tool_name)
    spec = TOOL_REGISTRY.get(tool_name)
    if not spec:
        return ToolResult(False, f"Unknown tool: {tool_name}")
    if spec.get("requires_confirmation") and not require_confirmation:
        return ToolResult(False, f"Confirmation required for {tool_name}")
    try:
        _log_tool(tool_name, params or {})
        return spec["handler"](params or {})
    except Exception as exc:
        return ToolResult(False, f"Tool '{tool_name}' error: {exc}")


def _log_tool(tool_name: str, params: dict[str, Any]):
    print("---[TOOL]-----------------------------------------------------")
    print(f"  TOOL:   {tool_name}")
    print(f"  PARAMS: {json.dumps(params)}")
    print("--------------------------------------------------------------")


def get_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        }
        for spec in TOOL_REGISTRY.values()
        if not spec.get("hidden")
    ]
