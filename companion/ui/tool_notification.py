from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from ui.theme import C_BG2, C_BORDER, C_GREEN, C_ORANGE


class ToolToast(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._opacity = 1.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel()
        self._label.setStyleSheet(f"""
            QLabel {{
                background: {C_BG2};
                color: {C_GREEN};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 8px 16px;
                font-family: Consolas;
                font-size: 12px;
                font-weight: bold;
            }}
        """)
        self._label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(400)
        self._fade_anim.finished.connect(self.hide)

    def show_toast(self, text: str, success: bool = True, duration_ms: int = 2500):
        self._label.setText(f"{'✓' if success else '✗'} {text}")
        color = C_GREEN if success else C_ORANGE
        self._label.setStyleSheet(f"""
            QLabel {{
                background: {C_BG2};
                color: {color};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 8px 16px;
                font-family: Consolas;
                font-size: 12px;
                font-weight: bold;
            }}
        """)
        self.adjustSize()
        parent = self.parent()
        if parent and parent.isVisible():
            bottom_right = parent.mapToGlobal(parent.rect().bottomRight())
            x = bottom_right.x() - self.width() - 20
            y = bottom_right.y() - self.height() - 60
        else:
            geo = QApplication.primaryScreen().availableGeometry()
            x = geo.right() - self.width() - 20
            y = geo.bottom() - self.height() - 60
        self.move(x, y)
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        self._fade_anim.stop()
        self._timer.stop()
        self._timer.start(duration_ms)

    def _fade_out(self):
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()
