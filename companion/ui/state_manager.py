import re
from pathlib import Path

import yaml
from PySide6.QtCore import QObject

from ui.signals import get_signals

_MODES_YAML = Path(__file__).resolve().parent.parent / "modes.yaml"

_MODE_CHANGE_RE = re.compile(
    r"(?i)\b(?:switch\s+to|change\s+to|go\s+to|enter|use|enable|set\s+to|let.s\s+|"
    r"we\s+should\s+|start\s+)(?:(\w+)\s+)?mode\b"
)
_MODE_KEYWORD_RE = re.compile(
    r"(?i)\b(?:think|think\s+about|think\s+through|analyze|debug|reason|"
    r"brainstorm|brainstorming|creative|idea|ideas|could\s+we|what\s+if)\b"
)


def load_modes() -> dict:
    with open(_MODES_YAML) as f:
        return yaml.safe_load(f)


class AssistantStateManager(QObject):
    def __init__(self):
        super().__init__()
        self._modes = load_modes()
        self._mode = "default"
        self._state = "READY"
        self._connection = "CONNECTING"
        self._tts_enabled = True
        self._mic_muted = False
        self._metrics = {}
        self._signals = get_signals()

    # -- State --
    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str):
        state = (state or "READY").upper()
        if state == "IDLE":
            state = "READY"
        if state == "ACTING":
            state = "TOOL_USE"
        if state != self._state:
            self._state = state
            self._signals.state_changed.emit(state)

    # -- Connection --
    @property
    def connection(self) -> str:
        return self._connection

    def set_connection(self, status: str):
        status = (status or "CONNECTING").upper()
        if status != self._connection:
            self._connection = status
            self._signals.connection_changed.emit(status)

    # -- Mode --
    @property
    def mode(self) -> str:
        return self._mode

    @property
    def mode_config(self) -> dict:
        return self._modes.get(self._mode, self._modes["default"])

    def set_mode(self, mode: str):
        mode = (mode or "default").lower().strip()
        if mode not in self._modes:
            valid = list(self._modes.keys())
            for m in valid:
                if mode.startswith(m) or m.startswith(mode):
                    mode = m
                    break
            else:
                return
        if mode != self._mode:
            self._mode = mode
            self._signals.mode_changed.emit(mode)

    def cycle_mode(self):
        modes = list(self._modes.keys())
        idx = modes.index(self._mode)
        self.set_mode(modes[(idx + 1) % len(modes)])

    def detect_mode_command(self, text: str) -> str:
        text = (text or "").strip().lower()
        if not text:
            return ""
        m = _MODE_CHANGE_RE.search(text)
        if m:
            mode_word = m.group(1)
            if mode_word:
                for key in self._modes:
                    if mode_word.startswith(key) or key.startswith(mode_word):
                        return key
        if re.search(r"(?i)\bnormal\s+mode\b|\bdefault\s+mode\b|\bback\b", text):
            return "default"
        if re.search(r"(?i)\b(?:think|analyze|debug|reason|deep)\b", text):
            return "think"
        if re.search(r"(?i)\b(?:brainstorm|creative|idea|imagine|invent)\b", text):
            return "brainstorm"
        return ""

    # -- TTS / Mic --
    @property
    def tts_enabled(self) -> bool:
        return self._tts_enabled

    def set_tts_enabled(self, enabled: bool):
        self._tts_enabled = enabled

    @property
    def mic_muted(self) -> bool:
        return self._mic_muted

    def set_mic_muted(self, muted: bool):
        if muted != self._mic_muted:
            self._mic_muted = muted
            self._signals.mic_muted_changed.emit(muted)

    # -- Metrics --
    @property
    def metrics(self) -> dict:
        return self._metrics

    def update_metrics(self, **kwargs):
        self._metrics.update(**kwargs)
        self._signals.metrics_updated.emit(dict(self._metrics))

    # -- Mode instructions for system prompt injection --
    def mode_instructions_block(self) -> str:
        cfg = self.mode_config
        instructions = cfg.get("instructions", [])
        if not instructions:
            return ""
        lines = "\n".join(f"- {i}" for i in instructions)
        return f"\nCurrent mode ({cfg.get('indicator', self._mode).upper()}):\n{lines}"


_state_manager_instance = None


def get_state_manager() -> AssistantStateManager:
    global _state_manager_instance
    if _state_manager_instance is None:
        _state_manager_instance = AssistantStateManager()
    return _state_manager_instance
