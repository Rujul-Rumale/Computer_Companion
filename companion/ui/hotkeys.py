import keyboard
from PySide6.QtCore import QObject, Signal


class GlobalHotkeyManager(QObject):
    voice_down = Signal()
    voice_up = Signal()
    overlay_toggle = Signal()
    screenshot = Signal()
    dev_panel_toggle = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctrl_down = False
        self._shift_down = False
        self._space_was_voice = False
        keyboard.hook(self._on_event)

    def _on_event(self, event):
        name = event.name.lower() if event.name else ''
        down = event.event_type == 'down'

        if name in ('ctrl', 'left ctrl', 'right ctrl'):
            self._ctrl_down = down
            return
        if name in ('shift', 'left shift', 'right shift'):
            self._shift_down = down
            return

        if name == 'space' and down and self._ctrl_down and not self._shift_down:
            self._space_was_voice = True
            self.voice_down.emit()
            return
        if name == 'space' and not down and self._space_was_voice:
            self._space_was_voice = False
            self.voice_up.emit()
            return

        if name == 'space' and down and self._ctrl_down and self._shift_down:
            self.overlay_toggle.emit()
            return
        if name == 'j' and down and self._ctrl_down and self._shift_down:
            self.screenshot.emit()
            return
        if name == 'd' and down and self._ctrl_down and self._shift_down:
            self.dev_panel_toggle.emit()
            return
        if name == 'q' and down and self._ctrl_down and self._shift_down:
            self.quit_requested.emit()
            return

    def stop(self):
        from contextlib import suppress
        with suppress(Exception):
            keyboard.unhook_all()
