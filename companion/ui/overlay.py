from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.animation import AssistantOrb
from ui.signals import get_signals
from ui.state_manager import get_state_manager
from ui.theme import (
    C_ACCENT,
    C_ACCENT2,
    C_BG2,
    C_BORDER,
    C_GREEN,
    C_TEXT,
    C_TEXT_DIM,
    C_TEXT_MID,
    C_YELLOW,
    MODE_COLORS,
    state_display,
)

_COMPACT_W = 240
_COMPACT_H = 50
_EXPANDED_W = 480
_EXPANDED_H = 220


class AudioLevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0.0
        self.setFixedSize(4, 24)

    def set_level(self, level: float):
        self._level = min(1.0, level * 5)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        fill_h = int(h * self._level)
        bg = QColor(C_BG2)
        painter.fillRect(0, h - fill_h, self.width(), fill_h, QColor(C_GREEN))
        painter.fillRect(0, 0, self.width(), h - fill_h, bg)
        painter.end()


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._signals = get_signals()
        self._sm = get_state_manager()
        self._waiting_for_response = False
        self._message_callback = None
        self._compact = True
        self._manual_expanded = False  # User pinned (clicked)
        self._auto_expanded = False      # System auto-expanded (future-proof)
        self._response_complete = False
        self._speaking = False
        self._pending_collapse = False
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._try_auto_collapse)
        self._stay_top_timer = QTimer(self)
        self._stay_top_timer.setInterval(1000)
        self._stay_top_timer.timeout.connect(lambda: self.raise_())
        self._setup_window()
        self._setup_ui()
        self._setup_signals()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(_COMPACT_W, _COMPACT_H)
        self._dragging = False
        self._drag_pos = None

    def _setup_ui(self):
        self._container = QFrame(self)
        self._container.setObjectName("overlayContainer")
        self._container.setStyleSheet(f"""
            QFrame#overlayContainer {{
                background: rgba(26, 29, 35, 230);
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)

        self._layout = QVBoxLayout(self._container)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(10, 6, 10, 6)

        # ── Top bar ───────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(6)
        self._orb = AssistantOrb()
        self._orb.setFixedSize(36, 36)
        top.addWidget(self._orb)

        self._level_meter = AudioLevelMeter()
        self._level_meter.hide()
        top.addWidget(self._level_meter)

        labels = QVBoxLayout()
        labels.setSpacing(0)
        self._state_label = QLabel("Ready")
        self._state_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 11px; font-weight: bold; background: transparent;")
        labels.addWidget(self._state_label)
        self._mode_label = QLabel("CHAT")
        self._mode_label.setStyleSheet(f"color: {MODE_COLORS['default']}; font-family: Consolas; font-size: 9px; background: transparent;")
        labels.addWidget(self._mode_label)
        top.addLayout(labels)

        top.addStretch()

        self._context_label = QLabel()
        self._context_label.setStyleSheet(f"color: {C_YELLOW}; font-family: Consolas; font-size: 9px; background: transparent; padding-right: 4px;")
        self._context_label.hide()
        top.addWidget(self._context_label)

        self._connection_label = QLabel()
        self._connection_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px; background: transparent; padding-right: 4px;")
        top.addWidget(self._connection_label)

        self._shrink_btn = QPushButton("\u2500")
        self._shrink_btn.setFixedSize(20, 20)
        self._shrink_btn.setToolTip("Collapse to compact")
        self._shrink_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_TEXT_DIM};
                border: none; border-radius: 10px;
                font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.1); color: {C_TEXT}; }}
        """)
        self._shrink_btn.clicked.connect(self._collapse)
        self._shrink_btn.hide()
        top.addWidget(self._shrink_btn)

        self._hide_btn = QPushButton("\u2212")
        self._hide_btn.setFixedSize(20, 20)
        self._hide_btn.setToolTip("Hide overlay")
        self._hide_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_TEXT_DIM};
                border: none; border-radius: 10px;
                font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.1); color: {C_TEXT}; }}
        """)
        self._hide_btn.clicked.connect(self._hide_window)
        self._hide_btn.hide()
        top.addWidget(self._hide_btn)

        self._stop_btn = QPushButton("\u25A0")
        self._stop_btn.setFixedSize(20, 20)
        self._stop_btn.setToolTip("Stop response")
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ff5050;
                border: none; border-radius: 10px;
                font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(255,80,80,0.3); }
        """)
        self._stop_btn.clicked.connect(lambda: self._signals.stop_requested.emit())
        self._stop_btn.hide()
        top.addWidget(self._stop_btn)

        self._close_btn = QPushButton("\u00D7")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setToolTip("Exit")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_TEXT_DIM};
                border: none; border-radius: 10px;
                font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(255,80,80,0.3); color: #ff5050; }}
        """)
        self._close_btn.clicked.connect(self._exit_app)
        self._close_btn.hide()
        top.addWidget(self._close_btn)

        self._layout.addLayout(top)

        # ── Separator ─────────────────────────────────────────────────
        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.HLine)
        self._separator.setStyleSheet(f"background: {C_BORDER}; max-height: 1px;")
        self._separator.hide()
        self._layout.addWidget(self._separator)

        # ── History ───────────────────────────────────────────────────
        self._history_label = QLabel("Hi, I'm COMPUTER. How can I help?")
        self._history_label.setStyleSheet(f"color: {C_TEXT_MID}; font-family: Consolas; font-size: 11px; background: transparent; padding: 6px 0;")
        self._history_label.setWordWrap(True)
        self._history_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._history_label.hide()
        self._layout.addWidget(self._history_label, stretch=1)

        # ── Input row ─────────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        input_row.setContentsMargins(0, 4, 0, 0)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Message COMPUTER...")
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BG2}; color: {C_TEXT};
                border: 1px solid {C_BORDER}; border-radius: 5px;
                padding: 0 8px; font-family: Consolas; font-size: 11px;
            }}
            QLineEdit:focus {{ border-color: {C_ACCENT2}; }}
        """)
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input)

        self._send_btn = QPushButton("\u2192")
        self._send_btn.setFixedSize(30, 30)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_ACCENT2}; color: #fff;
                border: none; border-radius: 5px;
                font-size: 14px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {C_ACCENT}; }}
        """)
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)
        self._layout.addLayout(input_row)

        self._input.hide()
        self._send_btn.hide()

    def _resize_container(self):
        w = _EXPANDED_W if not self._compact else _COMPACT_W
        h = _EXPANDED_H if not self._compact else _COMPACT_H
        self._container.setGeometry(0, 0, w, h)
        self.setFixedSize(w, h)

    def _expand(self, auto=False, show_input=False):
        if not self._compact:
            return
        self._compact = False
        self._manual_expanded = not auto
        self._auto_expanded = auto
        self._separator.show()
        self._history_label.show()
        self._input.show()
        self._send_btn.show()
        self._shrink_btn.show()
        self._hide_btn.show()
        self._stop_btn.show()
        self._close_btn.show()
        self._resize_container()
        if show_input:
            self._input.setFocus()

    def _collapse(self):
        if self._compact:
            self._resize_container()
            return
        self._compact = True
        self._manual_expanded = False
        self._auto_expanded = False
        self._input.clear()
        self._input.clearFocus()
        self._separator.hide()
        self._history_label.hide()
        self._input.hide()
        self._send_btn.hide()
        self._shrink_btn.hide()
        self._hide_btn.hide()
        self._stop_btn.hide()
        self._close_btn.hide()
        self._resize_container()

    def set_message_callback(self, cb):
        self._message_callback = cb

    def _setup_signals(self):
        self._signals.state_changed.connect(self._on_state)
        self._signals.mode_changed.connect(self._on_mode)
        self._signals.connection_changed.connect(self._on_connection)
        self._signals.assistant_token.connect(self._on_token)
        self._signals.user_message_sent.connect(self._on_user_message)
        self._signals.assistant_done.connect(self._on_done)
        self._signals.speaking_changed.connect(self._on_speaking)
        self._signals.audio_level.connect(self._on_audio_level)
        self._signals.window_context_changed.connect(self._on_window_context)

    def _on_state(self, state: str):
        self._orb.set_state(state)
        self._state_label.setText(state_display(state))
        self._level_meter.setVisible(state == "LISTENING")
        self._stop_btn.setVisible(state in ("THINKING", "TOOL_USE", "SPEAKING"))
        if self._pending_collapse:
            self._collapse_timer.stop()
            self._pending_collapse = False

    def _on_mode(self, mode: str):
        cfg = self._sm._modes.get(mode, {})
        indicator = cfg.get("indicator", mode.upper())
        color = MODE_COLORS.get(mode, C_TEXT_DIM)
        self._mode_label.setText(indicator)
        self._mode_label.setStyleSheet(f"color: {color}; font-family: Consolas; font-size: 9px; background: transparent;")

    def _on_connection(self, status: str):
        self._connection_label.setText(status)

    def _on_token(self, token: str):
        current = self._history_label.text()
        if current == "Hi, I'm COMPUTER. How can I help?" or self._waiting_for_response:
            self._history_label.setText(token)
            self._waiting_for_response = False
        else:
            if len(current) > 300:
                current = current[-300:]
            self._history_label.setText(current + token)

    def _on_user_message(self, text: str):
        self._history_label.setText(f"YOU: {text}")
        self._waiting_for_response = True

    def _on_done(self, full_text: str):
        self._history_label.setText(full_text[:300])
        self._response_complete = True
        if not self._speaking:
            self._schedule_auto_collapse()

    def _on_speaking(self, speaking: bool):
        self._speaking = speaking
        if not speaking and self._response_complete:
            self._schedule_auto_collapse()

    def _schedule_auto_collapse(self):
        """Start the auto-collapse grace-timer (only for auto-expanded, not manual)."""
        if self._manual_expanded:
            return  # Never auto-collapse if user expanded the overlay
        if self._compact:
            return  # Already collapsed
        if self._input.hasFocus() or self._input.text():
            return  # User is interacting with the input
        self._pending_collapse = True
        self._collapse_timer.start(4000)  # 4-second grace period

    def _try_auto_collapse(self):
        self._pending_collapse = False
        if self._manual_expanded:
            return
        if self._compact:
            return
        if self._input.hasFocus() or self._input.text():
            self._schedule_auto_collapse()
            return
        self._collapse()

    def _on_audio_level(self, level: float):
        self._level_meter.set_level(level)

    def _on_window_context(self, info: dict):
        title = (info.get("title") or "").strip()
        proc = (info.get("process_name") or "").strip()
        if title or proc:
            text = proc or title.split(" - ")[0] if title else proc
            self._context_label.setText(f"[{text[:30]}]")
            self._context_label.show()
        else:
            self._context_label.hide()

    def _exit_app(self):
        QApplication.quit()
        import os
        os._exit(0)

    def _hide_window(self):
        self.hide()

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        if self._message_callback:
            self._message_callback(text)

    def show_overlay(self):
        self._collapse()
        self.show()
        self.raise_()
        self._stay_top_timer.start()

    def hide_overlay(self):
        self.hide()
        self._stay_top_timer.stop()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier:
            event.ignore()
            return
        if event.key() == Qt.Key_Escape and not self._compact:
            self._collapse()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._compact:
                self._expand(show_input=True)
                self._manual_expanded = True
            elif self._auto_expanded:
                # Pin the auto-expanded overlay (user clicked → convert to manual)
                self._auto_expanded = False
                self._manual_expanded = True
                self._input.show()
                self._send_btn.show()
                self._input.setFocus()
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() == Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()
