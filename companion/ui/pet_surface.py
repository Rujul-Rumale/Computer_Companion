"""Transparent always-on-top 5x5 dot-matrix companion surface."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QWidget

from ui.dot_matrix import DotMatrixWidget
from ui.signals import get_signals
from ui.state_manager import get_state_manager

SURFACE_SIZE = 40
CLICK_DRAG_THRESHOLD = 5

_STATE_TO_VISUAL = {
    "READY": "idle",
    "LISTENING": "listening",
    "TRANSCRIBING": "listening",
    "THINKING": "thinking",
    "TOOL_USE": "acting",
    "SPEAKING": "speaking",
    "ERROR": "error",
}


class PetSurface(QWidget):
    """Draggable ambient dot-matrix tile. Click toggles the chat dock."""

    clicked = Signal()
    moved = Signal(QPoint)

    def __init__(self):
        super().__init__()
        self._signals = get_signals()
        self._sm = get_state_manager()
        self._dragging = False
        self._drag_origin = QPoint()
        self._did_drag = False

        self._setup_window()
        self._setup_ui()
        self._setup_signals()

        self._stay_top = QTimer(self)
        self._stay_top.setInterval(8000)
        self._stay_top.timeout.connect(self.raise_)

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(SURFACE_SIZE, SURFACE_SIZE)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - SURFACE_SIZE - 40, screen.bottom() - SURFACE_SIZE - 80)

    def _setup_ui(self):
        self._matrix = DotMatrixWidget(self)
        self._matrix.setGeometry(0, 0, SURFACE_SIZE, SURFACE_SIZE)
        self._matrix.set_visual_state("idle")

        self._bubble = QLabel(self)
        self._bubble.setWordWrap(True)
        self._bubble.setMaximumWidth(180)
        self._bubble.hide()
        self._bubble.setStyleSheet("""
            QLabel {
                background: rgba(13, 15, 18, 235);
                color: #c9d1d9;
                border: 1px solid #232830;
                border-radius: 6px;
                padding: 4px 8px;
                font-family: Segoe UI, Consolas;
                font-size: 10px;
            }
        """)

    def _setup_signals(self):
        self._signals.state_changed.connect(self._on_state)
        self._signals.connection_changed.connect(self._on_connection)
        self._signals.mic_muted_changed.connect(self._apply_visual)

    def _resolve_visual_state(self) -> str:
        if self._sm.mic_muted:
            return "muted"
        return _STATE_TO_VISUAL.get(self._sm.state, "idle")

    def _on_state(self, _state: str):
        self._apply_visual()
        self.raise_()
        self._stay_top.start()

    def _apply_visual(self):
        self._matrix.set_visual_state(self._resolve_visual_state())

    def _on_connection(self, status: str):
        if status == "OFFLINE":
            self.show_bubble("Offline", 2500)
        elif status == "READY":
            self.show_bubble("Online", 1000)

    def show_bubble(self, text: str, duration_ms: int = 1800):
        self._bubble.setText(text)
        self._bubble.adjustSize()
        bx = (SURFACE_SIZE - self._bubble.width()) // 2
        self._bubble.move(bx, -self._bubble.height() - 4)
        self._bubble.show()
        self._bubble.raise_()
        QTimer.singleShot(duration_ms, self._bubble.hide)

    def show_pet(self):
        self._apply_visual()
        self.show()
        self.raise_()
        self._stay_top.start()

    def hide_pet(self):
        self.hide()
        self._stay_top.stop()

    def global_anchor(self) -> QPoint:
        return self.frameGeometry().center()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._did_drag = False
            self._drag_origin = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_origin
            if delta.manhattanLength() > CLICK_DRAG_THRESHOLD:
                self._did_drag = True
            self.move(self.pos() + delta)
            self._drag_origin = event.globalPosition().toPoint()
            self.moved.emit(self.pos())
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            if not self._did_drag:
                self.clicked.emit()
            event.accept()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #12151a; color: #c9d1d9;
                border: 1px solid #232830;
                font-family: Consolas; font-size: 11px;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background: #232830; color: #4d8fea; }
        """)
        menu.addAction("Open Chat", self.clicked.emit)
        menu.addAction("Open Control Panel", self._signals.show_control_panel_requested.emit)
        menu.addAction("Hide Companion", self.hide)
        menu.addSeparator()
        quit_action = menu.addAction("Exit COMPUTER")
        quit_action.triggered.connect(self._signals.quit_requested.emit)
        menu.exec(event.globalPos())
        event.accept()

    def resizeEvent(self, event):
        self._matrix.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)
