"""
tools/timer.py — Set, cancel, and list timers with desktop notification.
"""

from __future__ import annotations

import ctypes
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class TimerEntry:
    timer_id: int
    label: str
    duration: float
    created_at: float
    thread: threading.Thread
    cancelled: bool = False


_timers: dict[int, TimerEntry] = {}
_counter = 0
_lock = threading.Lock()
_on_expired_callback: Callable[[int, str], None] | None = None


def _next_id() -> int:
    global _counter
    with _lock:
        _counter += 1
        return _counter


def set_on_expired(callback: Callable[[int, str], None] | None):
    global _on_expired_callback
    _on_expired_callback = callback


def set_timer(duration: float, label: str = "Timer") -> int:
    timer_id = _next_id()
    entry = TimerEntry(
        timer_id=timer_id,
        label=label,
        duration=duration,
        created_at=time.time(),
        thread=threading.Thread(
            target=_timer_worker,
            args=(timer_id, duration, label),
            daemon=True,
        ),
    )
    with _lock:
        _timers[timer_id] = entry
    entry.thread.start()
    return timer_id


def cancel_timer(timer_id: int) -> bool:
    with _lock:
        entry = _timers.get(timer_id)
        if entry is None:
            return False
        entry.cancelled = True
        del _timers[timer_id]
    return True


def list_timers() -> list[dict]:
    now = time.time()
    result = []
    with _lock:
        for tid, entry in list(_timers.items()):
            if entry.cancelled:
                continue
            remaining = max(0.0, entry.duration - (now - entry.created_at))
            result.append({
                "id": tid,
                "label": entry.label,
                "duration": entry.duration,
                "remaining": round(remaining, 1),
            })
    return result


def _timer_worker(timer_id: int, duration: float, label: str):
    time.sleep(duration)
    with _lock:
        entry = _timers.get(timer_id)
        if entry is None or entry.cancelled:
            return
        _timers.pop(timer_id, None)

    print(f"[TIMER] '{label}' expired ({timer_id})")

    from contextlib import suppress
    if _on_expired_callback:
        with suppress(Exception):
            _on_expired_callback(timer_id, label)

    with suppress(Exception):
        ctypes.windll.user32.MessageBoxW(0, f"Timer expired: {label}", "COMPUTER", 0)


def cleanup():
    with _lock:
        for tid in list(_timers.keys()):
            cancel_timer(tid)
