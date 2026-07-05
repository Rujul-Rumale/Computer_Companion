"""
tools/executor.py - Tool definitions and executor
All tool calls require explicit user intent (intent parsed from LLM response or direct command).
"""
import os
import re
import subprocess
import webbrowser
from pathlib import Path

from config import get_config

# ── Tool Registry ──────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    "open_app": {
        "description": "Launch an application by name",
        "params": ["app_name"],
    },
    "open_url": {
        "description": "Open a URL in Chrome",
        "params": ["url"],
    },
    "web_search": {
        "description": "Search the web",
        "params": ["query"],
    },
    "open_folder": {
        "description": "Open a folder in Explorer",
        "params": ["path"],
    },
    "set_volume": {
        "description": "Set system volume (0-100)",
        "params": ["level"],
    },
    "volume_up": {"description": "Increase volume", "params": []},
    "volume_down": {"description": "Decrease volume", "params": []},
    "mute": {"description": "Toggle mute", "params": []},
    "open_task_manager": {"description": "Open Task Manager", "params": []},
    "open_settings": {"description": "Open Windows Settings", "params": []},
    "take_screenshot": {"description": "Capture and analyze a screenshot", "params": []},
}

# App name → executable mapping
APP_MAP = {
    "vscode": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vs code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "fusion 360": r"C:\Users\%USERNAME%\AppData\Local\Autodesk\webdeploy\production\fusion360.exe",
    "fusion": r"C:\Users\%USERNAME%\AppData\Local\Autodesk\webdeploy\production\fusion360.exe",
    "kicad": r"C:\Program Files\KiCad\8.0\bin\kicad.exe",
    "sdrpp": r"C:\Program Files\SDR++\sdrpp.exe",
    "sdr++": r"C:\Program Files\SDR++\sdrpp.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "arduino": r"C:\Program Files\Arduino IDE\Arduino IDE.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "powershell": "powershell.exe",
}

SEARCH_PREFIXES = {
    "google": "https://www.google.com/search?q=",
    "youtube": "https://www.youtube.com/results?search_query=",
    "github": "https://github.com/search?q=",
    "stackoverflow": "https://stackoverflow.com/search?q=",
    "datasheet": "https://www.google.com/search?q=datasheet+",
    "ieee": "https://ieeexplore.ieee.org/search/searchresult.jsp?newsearch=true&queryText=",
}


class ToolResult:
    def __init__(self, success: bool, message: str, data: dict | None = None):
        self.success = success
        self.message = message
        self.data = data or {}

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"[{status}] {self.message}"


def execute_tool(tool_name: str, params: dict) -> ToolResult:
    """Execute a tool by name with params dict. Returns ToolResult."""
    handlers = {
        "open_app": _open_app,
        "open_url": _open_url,
        "web_search": _web_search,
        "open_folder": _open_folder,
        "set_volume": _set_volume,
        "volume_up": lambda p: _adjust_volume("up"),
        "volume_down": lambda p: _adjust_volume("down"),
        "mute": lambda p: _toggle_mute(),
        "open_task_manager": lambda p: _run("taskmgr.exe"),
        "open_settings": lambda p: _run("ms-settings:"),
        "take_screenshot": lambda p: _screenshot(),
    }
    handler = handlers.get(tool_name)
    if not handler:
        return ToolResult(False, f"Unknown tool: {tool_name}")
    try:
        return handler(params)
    except Exception as e:
        return ToolResult(False, f"Tool '{tool_name}' error: {e}")


def parse_tool_from_text(text: str) -> tuple[str, dict] | None:
    """
    Detect if LLM response contains a tool invocation.
    Format: [TOOL: tool_name param1=val1 param2=val2]
    Returns (tool_name, params) or None.
    """
    match = re.search(r'\[TOOL:\s*(\w+)(.*?)\]', text, re.IGNORECASE)
    if not match:
        return None
    tool_name = match.group(1).lower()
    param_str = match.group(2).strip()
    params = {}
    for kv in re.finditer(r'(\w+)=(["\']?)([^"\']+)\2', param_str):
        params[kv.group(1)] = kv.group(3)
    return tool_name, params


# ── Handlers ──────────────────────────────────────────────────────────────────

def _run(cmd: str, shell: bool = False) -> ToolResult:
    try:
        cmd_expanded = os.path.expandvars(cmd)
        if shell:
            subprocess.Popen(cmd_expanded, shell=True)
        else:
            subprocess.Popen(cmd_expanded)
        return ToolResult(True, f"Launched: {cmd}")
    except FileNotFoundError:
        return ToolResult(False, f"Executable not found: {cmd}")
    except Exception as e:
        return ToolResult(False, str(e))


def _open_app(params: dict) -> ToolResult:
    app_name = params.get("app_name", "").lower().strip()
    if not app_name:
        return ToolResult(False, "No app name given")

    # Check registry
    for key, path in APP_MAP.items():
        if key in app_name or app_name in key:
            expanded = os.path.expandvars(path)
            if os.path.exists(expanded):
                return _run(expanded)
            else:
                # Try running by name as fallback
                return _run(key.replace(" ", "") + ".exe")

    # Fallback: try running directly
    return _run(app_name + ".exe")


def _open_url(params: dict) -> ToolResult:
    url = params.get("url", "").strip()
    if not url:
        return ToolResult(False, "No URL given")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    chrome = os.path.expandvars(APP_MAP.get("chrome", "chrome.exe"))
    try:
        if os.path.exists(chrome):
            subprocess.Popen([chrome, url])
        else:
            webbrowser.open(url)
        return ToolResult(True, f"Opened: {url}")
    except Exception as e:
        return ToolResult(False, str(e))


def _web_search(params: dict) -> ToolResult:
    query = params.get("query", "").strip()
    engine = params.get("engine", "google").lower()
    if not query:
        return ToolResult(False, "No query given")
    prefix = SEARCH_PREFIXES.get(engine, SEARCH_PREFIXES["google"])
    import urllib.parse
    url = prefix + urllib.parse.quote_plus(query)
    return _open_url({"url": url})


def _open_folder(params: dict) -> ToolResult:
    path = params.get("path", "").strip()
    if not path:
        path = str(Path.home())
    expanded = os.path.expandvars(path)
    try:
        subprocess.Popen(["explorer.exe", expanded])
        return ToolResult(True, f"Opened folder: {expanded}")
    except Exception as e:
        return ToolResult(False, str(e))


def _set_volume(params: dict) -> ToolResult:
    level = params.get("level", 50)
    try:
        level = int(level)
        level = max(0, min(100, level))
        # Use nircmd if available, else PowerShell workaround
        nircmd = r"C:\Program Files\NirSoft\nircmd.exe"
        if os.path.exists(nircmd):
            subprocess.run([nircmd, "setsysvolume", str(int(level / 100 * 65535))])
        else:
            # PowerShell via COM
            subprocess.run(["powershell", "-Command",
                f"Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class Vol {{ [DllImport(\"winmm.dll\")] public static extern int waveOutSetVolume(IntPtr h, uint v); }}'; [Vol]::waveOutSetVolume([IntPtr]::Zero, {int((level/100)*0xFFFF) | (int((level/100)*0xFFFF) << 16)})"],
                capture_output=True)
        return ToolResult(True, f"Volume set to {level}%")
    except Exception as e:
        return ToolResult(False, f"Volume error: {e}")


def _adjust_volume(direction: str) -> ToolResult:
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        current = volume.GetMasterVolumeLevelScalar()
        delta = 0.1 if direction == "up" else -0.1
        new_vol = max(0.0, min(1.0, current + delta))
        volume.SetMasterVolumeLevelScalar(new_vol, None)
        return ToolResult(True, f"Volume {'increased' if direction == 'up' else 'decreased'} to {int(new_vol*100)}%")
    except Exception:
        # Fallback to keyboard simulation
        try:
            import pyautogui
            key = "volumeup" if direction == "up" else "volumedown"
            for _ in range(3):
                pyautogui.press(key)
            return ToolResult(True, f"Volume {direction}")
        except Exception as e:
            return ToolResult(False, str(e))


def _toggle_mute() -> ToolResult:
    try:
        import pyautogui
        pyautogui.press("volumemute")
        return ToolResult(True, "Toggled mute")
    except Exception as e:
        return ToolResult(False, str(e))


def _screenshot() -> ToolResult:
    cfg = get_config()
    path = cfg.screenshot_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        import pyautogui
        img = pyautogui.screenshot()
        img.save(path)
        return ToolResult(True, f"Screenshot saved: {path}", {"path": path})
    except Exception as e:
        return ToolResult(False, f"Screenshot failed: {e}")
