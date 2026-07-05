"""
main.py - Entry point for AI Companion (tray-first, ambient pet)
"""
import os
import sys
from contextlib import suppress

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import QApplication

from config import get_config
from memory import init_db
from ui.hotkeys import GlobalHotkeyManager
from ui.signals import get_signals

_window = None
_pet = None
_dock = None
_tray = None
_hotkeys = None
_shutting_down = False


def _handle_dock_message(text: str, attachments):
    if _window:
        paths = [a.path for a in attachments]
        _window.dispatch_message(text, attachment_paths=paths)


def _shutdown_app():
    global _shutting_down, _hotkeys, _pet, _dock, _tray, _window
    if _shutting_down:
        return
    _shutting_down = True

    if _hotkeys:
        _hotkeys.stop()
        _hotkeys = None
    if _dock:
        _dock.hide()
    if _pet:
        _pet.hide_pet()
    if _window:
        _window.hide()
    if _tray:
        _tray.hide()

    from config import get_config
    if get_config().llm_backend.lower() == "llama":
        from adapters.llama_backend import stop_llama_server
        with suppress(KeyboardInterrupt):
            stop_llama_server()

    app = QApplication.instance()
    if app:
        app.quit()
    QTimer.singleShot(400, lambda: os._exit(0))


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("COMPUTER")
    app.setOrganizationName("AICompanion")
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "app_icon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0d0f12"))
    palette.setColor(QPalette.WindowText, QColor("#c9d1d9"))
    palette.setColor(QPalette.Base, QColor("#12151a"))
    palette.setColor(QPalette.AlternateBase, QColor("#161a21"))
    palette.setColor(QPalette.Text, QColor("#c9d1d9"))
    palette.setColor(QPalette.Button, QColor("#161a21"))
    palette.setColor(QPalette.ButtonText, QColor("#c9d1d9"))
    palette.setColor(QPalette.Highlight, QColor("#4d8fea"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    init_db()
    cfg = get_config()
    signals = get_signals()
    signals.quit_requested.connect(_shutdown_app)

    global _window, _pet, _dock, _tray, _hotkeys

    def _show_control_panel():
        if _window:
            _window.show()
            _window.raise_()
            _window.activateWindow()

    from ui.main_window import MainWindow
    _window = MainWindow()
    signals.show_control_panel_requested.connect(_show_control_panel)

    from ui.tray import SystemTrayIcon
    _tray = SystemTrayIcon()
    _tray.show_window_requested.connect(_window.show)
    _tray.show_window_requested.connect(_window.raise_)
    _tray.show_dock_requested.connect(_toggle_dock)
    _tray.show_dev_panel_requested.connect(_toggle_dev_panel)
    _tray.mic_toggled.connect(_sync_mic_state)
    _tray.show()
    signals.window_context_changed.connect(_tray.update_window_context)

    if cfg.pet_enabled:
        from ui.chat_dock import ChatDock
        from ui.pet_surface import PetSurface

        _pet = PetSurface()
        _dock = ChatDock()
        _dock.set_send_callback(_handle_dock_message)
        _dock.set_anchor_provider(_pet.global_anchor)
        _pet.clicked.connect(_toggle_dock)
        _pet.moved.connect(lambda _: _reposition_dock())
        signals.dock_toggle_requested.connect(_toggle_dock)

        quit_sc_dock = QShortcut(QKeySequence("Ctrl+Shift+Q"), _dock)
        quit_sc_dock.activated.connect(_shutdown_app)

    _hotkeys = GlobalHotkeyManager()
    _hotkeys.voice_down.connect(_window.ptt_start, Qt.QueuedConnection)
    _hotkeys.voice_up.connect(_window.ptt_stop, Qt.QueuedConnection)
    _hotkeys.overlay_toggle.connect(_toggle_dock, Qt.QueuedConnection)
    _hotkeys.screenshot.connect(_take_screenshot_global, Qt.QueuedConnection)
    _hotkeys.dev_panel_toggle.connect(_toggle_dev_panel, Qt.QueuedConnection)
    _hotkeys.quit_requested.connect(_shutdown_app, Qt.QueuedConnection)

    quit_sc = QShortcut(QKeySequence("Ctrl+Q"), _window)
    quit_sc.activated.connect(_shutdown_app)
    quit_sc_dock = QShortcut(QKeySequence("Ctrl+Shift+Q"), _window)
    quit_sc_dock.activated.connect(_shutdown_app)

    QTimer.singleShot(500, _startup_ready)
    if _pet:
        QTimer.singleShot(800, _pet.show_pet)

    sys.exit(app.exec())


def _toggle_dock():
    if _dock:
        _dock.toggle_visibility()
        if _dock.isVisible():
            _dock.position_near_pet()


def _reposition_dock():
    if _dock and _dock.isVisible():
        _dock.position_near_pet()


def _sync_mic_state():
    if _dock:
        _dock._style_mic_btn()


def _take_screenshot_global():
    if _window:
        _window.take_screenshot()


def _toggle_dev_panel():
    if _window and _window.debug_panel:
        dp = _window.debug_panel
        if dp.isVisible():
            dp.hide()
        else:
            dp.show()
            dp.raise_()


def _startup_ready():
    print("COMPUTER Ready — Ctrl+Shift+Q to exit")


if __name__ == "__main__":
    main()
