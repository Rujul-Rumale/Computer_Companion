from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ui.signals import get_signals
from ui.state_manager import get_state_manager
from ui.theme import C_BORDER, C_BORDER2, C_TEXT_DIM, MODE_COLORS


class ModeSelector(QWidget):
    mode_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sm = get_state_manager()
        self._signals = get_signals()
        self._setup_ui()
        self._signals.mode_changed.connect(self._on_mode_changed)
        self._refresh()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("MODE")
        label.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px; font-weight: bold; padding-right: 4px;")
        layout.addWidget(label)

        self._buttons = {}
        for mode_key in self._sm._modes:
            cfg = self._sm._modes[mode_key]
            label_text = cfg.get("label", mode_key.capitalize())
            btn = QPushButton(label_text.upper())
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, m=mode_key: self._select(m))
            layout.addWidget(btn)
            self._buttons[mode_key] = btn

        layout.addStretch()

    def _select(self, mode: str):
        self._sm.set_mode(mode)
        self.mode_selected.emit(mode)

    def _on_mode_changed(self, mode: str):
        self._refresh()

    def _refresh(self):
        current = self._sm.mode
        for key, btn in self._buttons.items():
            selected = key == current
            btn.setChecked(selected)
            color = MODE_COLORS.get(key, C_TEXT_DIM)
            if selected:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {color}; color: #000;
                        border: 1px solid {color}; border-radius: 2px;
                        font-family: Consolas; font-size: 9px; font-weight: bold;
                        padding: 0 8px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {color};
                        border: 1px solid {C_BORDER}; border-radius: 2px;
                        font-family: Consolas; font-size: 9px;
                        padding: 0 8px;
                    }}
                    QPushButton:hover {{ background: {C_BORDER2}; }}
                """)
