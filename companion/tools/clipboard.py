"""
tools/clipboard.py — Clipboard read, write, append, and history tracking.
Uses win32clipboard (pywin32) for system clipboard access.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

# Lazily loaded to allow mocking in tests
_win32clipboard = None
_win32con = None

def _ensure_win32():
    global _win32clipboard, _win32con
    if _win32clipboard is None:
        import win32clipboard as wc
        import win32con as wcon
        _win32clipboard = wc
        _win32con = wcon
    return _win32clipboard, _win32con


@dataclass
class ClipboardEntry:
    text: str
    timestamp: float = field(default_factory=time.time)


class ClipboardManager:
    def __init__(self, max_history: int = 50):
        self._max_history = max_history
        self._history: deque[ClipboardEntry] = deque(maxlen=max_history)
        self._lock = threading.Lock()
        self._last_text: str = ""
        self._watcher_thread: threading.Thread | None = None
        self._watcher_running = False

    # ── System clipboard access ────────────────────────────────────────

    def _open_clipboard(self):
        return _ensure_win32()

    def get(self) -> str:
        try:
            win32clipboard, wcon = self._open_clipboard()
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(wcon.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(wcon.CF_UNICODETEXT) or ""
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            pass
        return ""

    def set(self, text: str) -> bool:
        if not text:
            return False
        try:
            win32clipboard, wcon = self._open_clipboard()
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, wcon.CF_UNICODETEXT)
                self._record(text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return False

    def append(self, text: str) -> bool:
        current = self.get()
        combined = (current + "\n" + text) if current else text
        return self.set(combined)

    # ── History ────────────────────────────────────────────────────────

    def _record(self, text: str):
        if not text or text == self._last_text:
            return
        self._last_text = text
        with self._lock:
            if not self._history or self._history[-1].text != text:
                self._history.append(ClipboardEntry(text=text))

    def history(self, limit: int = 10) -> list[dict]:
        with self._lock:
            items = list(self._history)
        return [
            {"text": e.text, "timestamp": e.timestamp}
            for e in items[-limit:]
        ]

    # ── Background watcher ─────────────────────────────────────────────

    def start_watcher(self):
        if self._watcher_thread and self._watcher_thread.is_alive():
            return
        self._watcher_running = True
        self._watcher_thread = threading.Thread(
            target=self._watcher_loop, daemon=True
        )
        self._watcher_thread.start()

    def stop_watcher(self):
        self._watcher_running = False

    def _watcher_loop(self):
        while self._watcher_running:
            try:
                text = self.get()
                if text and text != self._last_text:
                    self._record(text)
            except Exception:
                pass
            time.sleep(0.5)


_CLIPBOARD: ClipboardManager | None = None


def _get_manager() -> ClipboardManager:
    global _CLIPBOARD
    if _CLIPBOARD is None:
        _CLIPBOARD = ClipboardManager()
        _CLIPBOARD.start_watcher()
    return _CLIPBOARD
