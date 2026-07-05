import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from ui.signals import get_signals
from ui.state_manager import get_state_manager
from ui.theme import C_ACCENT, C_BORDER, C_PANEL, C_TEXT, C_TEXT_DIM


class SystemTrayIcon(QSystemTrayIcon):
    show_window_requested = Signal()
    show_dock_requested = Signal()
    show_dev_panel_requested = Signal()
    mode_changed = Signal(str)
    mic_toggled = Signal()
    exit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sm = get_state_manager()
        self._signals = get_signals()
        self._window_context: dict = {}
        self.setToolTip("COMPUTER")

        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "app_icon.png")
        icon = QIcon(icon_path) if os.path.isfile(icon_path) else QIcon()
        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setIcon(icon)

        self._menu = QMenu()
        self._menu.setStyleSheet(f"""
            QMenu {{
                background: {C_PANEL}; color: {C_TEXT};
                border: 1px solid {C_BORDER};
                font-family: Consolas; font-size: 11px;
            }}
            QMenu::item {{ padding: 6px 24px; }}
            QMenu::item:selected {{ background: {C_BORDER}; color: {C_ACCENT}; }}
            QMenu::item:disabled {{ color: {C_TEXT_DIM}; }}
            QMenu::separator {{ background: {C_BORDER}; height: 1px; margin: 4px 8px; }}
            QMenu::indicator {{ width: 0; height: 0; }}
        """)

        self._status_mode = self._menu.addAction("Mode: CHAT")
        self._status_mode.setEnabled(False)
        self._status_state = self._menu.addAction("State: READY")
        self._status_state.setEnabled(False)
        self._status_conn = self._menu.addAction("Connection: ...")
        self._status_conn.setEnabled(False)
        self._menu.addSeparator()

        open_action = QAction("Open COMPUTER")
        open_action.triggered.connect(self.show_window_requested.emit)
        self._menu.addAction(open_action)

        dock_action = QAction("Open Chat Dock")
        dock_action.setShortcut("Ctrl+Shift+Space")
        dock_action.triggered.connect(self.show_dock_requested.emit)
        self._menu.addAction(dock_action)

        self._menu.addSeparator()

        mode_menu = self._menu.addMenu("Change Mode")
        mode_menu.setStyleSheet(self._menu.styleSheet())
        self._mode_actions = {}
        for mode_key in self._sm._modes:
            cfg = self._sm._modes[mode_key]
            label = cfg.get("label", mode_key.capitalize())
            action = QAction(label)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, m=mode_key: self._set_mode_from_tray(m))
            mode_menu.addAction(action)
            self._mode_actions[mode_key] = action

        self._signals.mode_changed.connect(self._on_mode)
        self._on_mode(self._sm.mode)

        self._menu.addSeparator()

        self._mic_action = QAction("Mute Mic")
        self._mic_action.triggered.connect(self._toggle_mic)
        self._menu.addAction(self._mic_action)

        dev_panel_action = QAction("Dev Panel")
        dev_panel_action.triggered.connect(self.show_dev_panel_requested.emit)
        self._menu.addAction(dev_panel_action)

        self._menu.addSeparator()

        exit_action = QAction("Exit COMPUTER")
        exit_action.setShortcut("Ctrl+Shift+Q")
        exit_action.triggered.connect(self._exit_app)
        self._menu.addAction(exit_action)

        self.setContextMenu(self._menu)

        self._signals.state_changed.connect(self._on_state)
        self._signals.connection_changed.connect(self._on_connection)
        self._signals.speaking_changed.connect(self._on_speaking)

    def _on_mode(self, mode: str):
        cfg = self._sm._modes.get(mode, {})
        indicator = cfg.get("indicator", mode.upper())
        self._status_mode.setText(f"Mode: {indicator}")
        for key, action in self._mode_actions.items():
            action.setChecked(key == mode)

    def _on_state(self, state: str):
        from ui.theme import state_display
        self._status_state.setText(f"State: {state_display(state)}")
        self._update_tooltip()

    def _on_connection(self, status: str):
        self._status_conn.setText(f"Connection: {status}")
        self._update_tooltip()

    def _on_speaking(self, speaking: bool):
        self._update_tooltip()

    def update_window_context(self, info: dict):
        self._window_context = info
        self._update_tooltip()

    def _update_tooltip(self):
        s = self._sm.state
        c = self._sm.connection
        from ui.theme import state_display
        tip = f"COMPUTER\nState: {state_display(s)}\nConnection: {c}"
        win = getattr(self, '_window_context', None)
        if win:
            title = (win.get("title") or "").strip()
            proc = (win.get("process_name") or "").strip()
            if title:
                tip += f"\nWindow: {title[:80]}"
            if proc:
                tip += f"\nApp: {proc}"
        self.setToolTip(tip)

    def _set_mode_from_tray(self, mode: str):
        self._sm.set_mode(mode)
        self.mode_changed.emit(mode)

    def _toggle_mic(self):
        muted = not self._sm.mic_muted
        self._sm.set_mic_muted(muted)
        self._mic_action.setText("Unmute Mic" if muted else "Mute Mic")
        self.mic_toggled.emit()

    def _exit_app(self):
        get_signals().quit_requested.emit()
