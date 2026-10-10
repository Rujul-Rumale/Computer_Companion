"""Dictation manager — types cleaned speech into the active window via Win32 SendInput."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import re
import time
from typing import ClassVar

import keyboard


class DictationManager:
    """Injects text into the foreground window using Win32 ``SendInput``.

    Also handles voice commands (newline, backspace, etc.).
    """

    # Maps spoken commands to their key action
    VOICE_COMMANDS: ClassVar[dict[str, str | None]] = {
        "new line": "\n",
        "newline": "\n",
        "new paragraph": "\n\n",
        "tab": "\t",
        "period": ".",
        "comma": ",",
        "question mark": "?",
        "exclamation mark": "!",
        "exclamation point": "!",
        "colon": ":",
        "semicolon": ";",
        "dash": "-",
        "hyphen": "-",
    }

    # Commands that map to key presses rather than text
    KEY_COMMANDS: ClassVar[dict[str, str]] = {
        "backspace": "backspace",
        "delete that": "backspace",
        "delete last word": "ctrl+backspace",
        "enter": "enter",
        "undo": "ctrl+z",
        "redo": "ctrl+y",
        "select all": "ctrl+a",
        "copy that": "ctrl+c",
        "cut that": "ctrl+x",
        "paste that": "ctrl+v",
        "save": "ctrl+s",
    }

    def __init__(self):
        self._user32 = ctypes.windll.user32

    def type_text(self, text: str):
        """Inject *text* at the cursor in the foreground window."""
        for char in text:
            if char == "\n":
                keyboard.press_and_release("enter")
                continue
            self._type_char(char)
            time.sleep(0.005)  # small delay between chars for reliability

    def execute_command(self, command: str) -> bool:
        """Handle a voice command, returning True if recognised."""
        cmd = command.strip().lower()

        # Text commands (insert characters)
        if cmd in self.VOICE_COMMANDS:
            char = self.VOICE_COMMANDS[cmd]
            if char:
                self.type_text(char)
            return True

        # Key commands (press hotkey)
        if cmd in self.KEY_COMMANDS:
            keyboard.press_and_release(self.KEY_COMMANDS[cmd])
            return True

        return False

    def process_text(self, cleaned: str):
        """Type *cleaned* text, expanding any inline voice commands."""
        # Inline command expansion: "(command)" or "/command" patterns
        expanded = self._expand_inline_commands(cleaned)
        self.type_text(expanded)

    def _expand_inline_commands(self, text: str) -> str:
        """Replace inline voice commands like ``(newline)`` with actual chars."""
        result = text
        for cmd, char in self.VOICE_COMMANDS.items():
            # Match (cmd) patterns
            result = re.sub(
                re.escape(f"({cmd})"), char or "", result, flags=re.IGNORECASE
            )
        return result

    # ── Win32 SendInput ───────────────────────────────────────────────

    def _type_char(self, char: str):
        """Send a single Unicode character to the foreground window."""
        # Set up a KEYBDINPUT structure for Unicode
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.wintypes.WORD),
                ("wScan", ctypes.wintypes.WORD),
                ("dwFlags", ctypes.wintypes.DWORD),
                ("time", ctypes.wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.wintypes.DWORD),
                ("ki", KEYBDINPUT),
            ]

        # KEYEVENTF_UNICODE = 0x0004
        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        # Key down
        ki_down = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE, 0, None)
        inp_down = INPUT(INPUT_KEYBOARD, ki_down)
        self._user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))

        # Key up
        ki_up = KEYBDINPUT(0, ord(char), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)
        inp_up = INPUT(INPUT_KEYBOARD, ki_up)
        self._user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
