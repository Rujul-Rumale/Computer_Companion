"""Compact chat dock — typing, attachments, modes, mic, stop."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from adapters import AttachmentSummary, get_attachment_processor
from config import get_config
from ui.mode_selector import ModeSelector
from ui.signals import get_signals
from ui.state_manager import get_state_manager
from ui.theme import (
    C_ACCENT,
    C_ACCENT2,
    C_BG,
    C_BG2,
    C_BORDER,
    C_GREEN,
    C_RED,
    C_TEXT,
    C_TEXT_DIM,
    state_display,
)

DOCK_W = 400
DOCK_H = 480


class AttachmentChip(QFrame):
    def __init__(self, summary: AttachmentSummary, on_remove: Callable[[], None], parent=None):
        super().__init__(parent)
        self.summary = summary
        self.setStyleSheet(f"""
            QFrame {{
                background: {C_BG2}; border: 1px solid {C_BORDER};
                border-radius: 4px; padding: 2px;
            }}
        """)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 4, 2)
        label = QLabel(f"{summary.display_name} ({summary.kind})")
        label.setStyleSheet(f"color: {C_TEXT}; font-family: Consolas; font-size: 9px;")
        row.addWidget(label)
        btn = QPushButton("x")
        btn.setFixedSize(18, 18)
        btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C_TEXT_DIM}; border: none; }}
            QPushButton:hover {{ color: {C_RED}; }}
        """)
        btn.clicked.connect(on_remove)
        row.addWidget(btn)


class ChatDock(QWidget):
    """Docked chat panel opened from the pet or tray."""

    def __init__(self):
        super().__init__()
        self.cfg = get_config()
        self._signals = get_signals()
        self._sm = get_state_manager()
        self._attachments: list[AttachmentSummary] = []
        self._on_send: Callable[[str, list[AttachmentSummary]], None] | None = None
        self._anchor_pet: Callable[[], QPoint] | None = None
        self._streaming = False
        self._assistant_start: int | None = None
        self._last_user_line = ""

        self._setup_window()
        self._setup_ui()
        self._setup_signals()

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(DOCK_W, DOCK_H)
        self.setAcceptDrops(True)

    def _setup_ui(self):
        self._container = QFrame(self)
        self._container.setObjectName("chatDock")
        self._container.setGeometry(0, 0, DOCK_W, DOCK_H)
        self._container.setStyleSheet(f"""
            QFrame#chatDock {{
                background: rgba(13, 15, 18, 248);
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self._container)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 8, 10, 8)

        header = QHBoxLayout()
        title = QLabel(self.cfg.persona_name.upper())
        title.setStyleSheet(f"color: {C_ACCENT}; font-family: Consolas; font-size: 11px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self._state_label = QLabel("Ready")
        self._state_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px;")
        header.addWidget(self._state_label)
        close_btn = QPushButton("x")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C_TEXT_DIM}; border: none; font-size: 14px; }}
            QPushButton:hover {{ color: {C_RED}; }}
        """)
        close_btn.setToolTip("Close chat (Esc)")
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self._mode_selector = ModeSelector()
        layout.addWidget(self._mode_selector)

        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setFont(QFont("Consolas", 10))
        self._transcript.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG}; color: {C_TEXT};
                border: 1px solid {C_BORDER}; border-radius: 6px; padding: 6px;
            }}
        """)
        self._transcript.setPlaceholderText("Conversation appears here…")
        layout.addWidget(self._transcript, stretch=1)

        self._chip_area = QWidget()
        self._chip_layout = QHBoxLayout(self._chip_area)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(4)
        self._chip_area.hide()
        layout.addWidget(self._chip_area)

        drop_hint = QLabel("Drop files here to attach")
        drop_hint.setAlignment(Qt.AlignCenter)
        drop_hint.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px;")
        layout.addWidget(drop_hint)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Message…")
        self._input.setFixedHeight(32)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BG2}; color: {C_TEXT};
                border: 1px solid {C_BORDER}; border-radius: 6px;
                padding: 0 10px; font-family: Consolas; font-size: 11px;
            }}
            QLineEdit:focus {{ border-color: {C_ACCENT2}; }}
        """)
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, stretch=1)

        self._mic_btn = QPushButton("MIC")
        self._mic_btn.setFixedSize(40, 32)
        self._mic_btn.setCheckable(True)
        self._mic_btn.setToolTip("Mute microphone")
        self._mic_btn.clicked.connect(self._toggle_mic)
        self._style_mic_btn()
        input_row.addWidget(self._mic_btn)

        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setFixedSize(48, 32)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_RED};
                border: 1px solid {C_RED}; border-radius: 6px;
                font-family: Consolas; font-size: 9px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {C_RED}; color: #fff; }}
        """)
        self._stop_btn.clicked.connect(lambda: self._signals.stop_requested.emit())
        input_row.addWidget(self._stop_btn)

        send_btn = QPushButton("SEND")
        send_btn.setFixedSize(52, 32)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_ACCENT2}; color: #fff;
                border: none; border-radius: 6px;
                font-family: Consolas; font-size: 9px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {C_ACCENT}; }}
        """)
        send_btn.clicked.connect(self._send)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

    def _setup_signals(self):
        self._signals.state_changed.connect(self._on_state)
        self._signals.assistant_token.connect(self._on_token)
        self._signals.user_message_sent.connect(self._on_user)
        self._signals.assistant_done.connect(self._on_done)
        self._signals.error_occurred.connect(self._on_error)

    def set_send_callback(self, cb: Callable[[str, list[AttachmentSummary]], None]):
        self._on_send = cb

    def set_anchor_provider(self, cb: Callable[[], QPoint]):
        self._anchor_pet = cb

    def position_near_pet(self):
        if not self._anchor_pet:
            return
        center = self._anchor_pet()
        screen = QApplication.primaryScreen().availableGeometry()
        pet_offset = 30
        x = center.x() - DOCK_W // 2
        y = center.y() - pet_offset - DOCK_H
        x = max(screen.left() + 8, min(x, screen.right() - DOCK_W - 8))
        y = max(screen.top() + 8, min(y, screen.bottom() - DOCK_H - 8))
        self.move(x, y)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.position_near_pet()
            self.show()
            self.raise_()
            self._input.setFocus()

    def _on_state(self, state: str):
        self._state_label.setText(state_display(state))

    def _on_user(self, text: str):
        line = f"You: {text}"
        if line == self._last_user_line:
            return
        self._last_user_line = line
        self._streaming = False
        self._assistant_start = None
        self._append_line(line, C_GREEN)

    def _on_token(self, token: str):
        if not self._streaming:
            self._streaming = True
            self._begin_assistant_line()
        self._append_assistant_token(token)

    def _on_done(self, full_text: str):
        if self._streaming and self._assistant_start is not None:
            self._replace_assistant_text(full_text[:2000])
        elif full_text.strip():
            self._append_line(f"Assistant: {full_text[:2000]}", C_ACCENT)
        self._streaming = False
        self._assistant_start = None

    def _on_error(self, err: str):
        self._streaming = False
        self._assistant_start = None
        self._append_line(f"Error: {err}", C_RED)

    def _append_line(self, text: str, color: str):
        cursor = self._transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        if self._transcript.document().characterCount() > 1:
            cursor.insertText("\n")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self._transcript.setTextCursor(cursor)
        self._transcript.ensureCursorVisible()

    def _begin_assistant_line(self):
        cursor = self._transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        if self._transcript.document().characterCount() > 1:
            cursor.insertText("\n")
        prefix = QTextCharFormat()
        prefix.setForeground(QColor(C_ACCENT))
        cursor.insertText("Assistant: ", prefix)
        self._assistant_start = cursor.position()
        self._transcript.setTextCursor(cursor)

    def _append_assistant_token(self, token: str):
        if self._assistant_start is None:
            self._begin_assistant_line()
        cursor = self._transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(C_TEXT))
        cursor.insertText(token, fmt)
        self._transcript.setTextCursor(cursor)
        self._transcript.ensureCursorVisible()

    def _replace_assistant_text(self, text: str):
        if self._assistant_start is None:
            return
        cursor = self._transcript.textCursor()
        cursor.setPosition(self._assistant_start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(C_TEXT))
        cursor.insertText(text, fmt)
        self._transcript.setTextCursor(cursor)

    def _send(self):
        text = self._input.text().strip()
        if not text and not self._attachments:
            return
        self._input.clear()
        attachments = list(self._attachments)
        self._clear_attachments()
        display = text or "Review the attached files."
        self._last_user_line = f"You: {display}"
        self._streaming = False
        self._assistant_start = None
        self._append_line(self._last_user_line, C_GREEN)
        if self._on_send:
            self._on_send(display, attachments)

    def _toggle_mic(self):
        muted = not self._sm.mic_muted
        self._sm.set_mic_muted(muted)
        self._style_mic_btn()

    def _style_mic_btn(self):
        muted = self._sm.mic_muted
        color = C_RED if muted else C_GREEN
        self._mic_btn.setChecked(muted)
        self._mic_btn.setText("MUTED" if muted else "MIC")
        self._mic_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {color};
                border: 1px solid {color}; border-radius: 6px;
                font-family: Consolas; font-size: 8px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.05); }}
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self._add_paths(paths)
        event.acceptProposedAction()

    def _add_paths(self, paths: list[str]):
        processor = get_attachment_processor()
        for path in paths:
            if not path or not Path(path).exists():
                continue
            summary = processor.summarize_path(path)
            self._attachments.append(summary)
            chip = AttachmentChip(summary, lambda s=summary: self._remove_attachment(s))
            self._chip_layout.addWidget(chip)
        self._chip_area.setVisible(bool(self._attachments))

    def _remove_attachment(self, summary: AttachmentSummary):
        self._attachments = [a for a in self._attachments if a.path != summary.path]
        self._rebuild_chips()

    def _clear_attachments(self):
        self._attachments.clear()
        self._rebuild_chips()

    def _rebuild_chips(self):
        while self._chip_layout.count():
            item = self._chip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for summary in self._attachments:
            chip = AttachmentChip(summary, lambda s=summary: self._remove_attachment(s))
            self._chip_layout.addWidget(chip)
        self._chip_area.setVisible(bool(self._attachments))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)
