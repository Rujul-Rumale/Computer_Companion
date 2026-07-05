"""
tools/window_tools.py — Window enumeration and focusing via win32gui.
"""

from __future__ import annotations

import win32con
import win32gui


def _enum_windows() -> list[dict]:
    """Enumerate all visible top-level windows with titles."""
    windows = []

    def callback(hwnd, _data):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        rect = win32gui.GetWindowRect(hwnd)
        windows.append({
            "hwnd": hwnd,
            "title": title,
            "left": rect[0],
            "top": rect[1],
            "right": rect[2],
            "bottom": rect[3],
            "width": rect[2] - rect[0],
            "height": rect[3] - rect[1],
        })
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def _fuzzy_match(query: str, title: str) -> bool:
    query = query.lower()
    title = title.lower()
    return query in title or title in query


def window_list() -> list[dict]:
    return _enum_windows()


def focus_window(identifier: str) -> tuple[bool, str]:
    """Bring a window to the foreground by title match.
    Returns (success, message_or_title).
    """
    windows = _enum_windows()

    # Exact match first
    for w in windows:
        if w["title"].lower() == identifier.lower():
            try:
                win32gui.ShowWindow(w["hwnd"], win32con.SW_SHOW)
                win32gui.SetForegroundWindow(w["hwnd"])
                return True, w["title"]
            except Exception as exc:
                return False, str(exc)

    # Fuzzy match
    for w in windows:
        if _fuzzy_match(identifier, w["title"]):
            try:
                win32gui.ShowWindow(w["hwnd"], win32con.SW_SHOW)
                win32gui.SetForegroundWindow(w["hwnd"])
                return True, w["title"]
            except Exception as exc:
                return False, str(exc)

    return False, f"No window matching '{identifier}' found"
