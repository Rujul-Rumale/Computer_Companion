"""
tools/active_window_tracker.py - Background daemon that tracks the active foreground window.
Provides synchronous snapshot + async polling with Qt signals.
"""

from __future__ import annotations

import time

import psutil
import win32gui
import win32process
from PySide6.QtCore import QObject, QTimer, Signal

_OWN_TITLES = {"computer", "ai companion", "companion"}


def get_process_name(hwnd: int) -> str:
    """Return the executable name for the window's process, or 'unknown'."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        return proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        return "unknown"


def get_active_window_info() -> dict:
    """Return info about the currently focused foreground window.

    Returns a dict with keys:
        title, class_name, process_name, executable, hwnd, timestamp
    or all-empty fields if no valid foreground window is detected.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return _empty_info()
        title = win32gui.GetWindowText(hwnd) or ""
        class_name = win32gui.GetClassName(hwnd) or ""
        process_name = get_process_name(hwnd)
        executable = process_name  # psutil.name() is the exe name
        return {
            "title": title,
            "class_name": class_name,
            "process_name": process_name,
            "executable": executable,
            "hwnd": hwnd,
            "timestamp": time.time(),
        }
    except Exception:
        return _empty_info()


def _empty_info() -> dict:
    return {
        "title": "",
        "class_name": "",
        "process_name": "",
        "executable": "",
        "hwnd": 0,
        "timestamp": 0.0,
    }


def _is_own_window(info: dict) -> bool:
    title = (info.get("title") or "").lower()
    proc = (info.get("process_name") or "").lower()
    return any(keyword in title or keyword in proc for keyword in _OWN_TITLES)


class ActiveWindowTracker(QObject):
    """Periodically polls the foreground window and emits signals on change.

    Signals:
        window_changed(dict) — emitted when the active window title/process changes.
        window_updated(dict) — emitted on every poll tick (for UI refresh).
    """

    window_changed = Signal(dict)
    window_updated = Signal(dict)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._current: dict = _empty_info()
        self._timer: QTimer | None = None
        self._running = False
        self._enabled = True

    @property
    def current(self) -> dict:
        return dict(self._current)

    @property
    def current_title(self) -> str:
        return self._current.get("title", "")

    @property
    def current_process(self) -> str:
        return self._current.get("process_name", "")

    @property
    def is_tracking(self) -> bool:
        return self._running

    def start(self, interval_ms: int = 1000):
        if self._running:
            return
        self._running = True
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.stop()
            self._timer = None

    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def _poll(self):
        if not self._enabled:
            return
        info = get_active_window_info()
        if _is_own_window(info):
            return
        self.window_updated.emit(dict(info))
        changed = (
            info["title"] != self._current["title"]
            or info["process_name"] != self._current["process_name"]
        )
        if changed:
            self._current = info
            self.window_changed.emit(dict(info))
