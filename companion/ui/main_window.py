import queue
import threading
import time
from datetime import datetime

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from adapters import AttachmentSummary, get_attachment_processor, get_tool_runner
from ai import ConversationManager
from audio import PushToTalkRecorder, TTSManager, load_whisper
from config import get_config
from memory import init_db
from memory.store import get_recent_turns
from tools.system_tools import get_system_volume, set_system_volume
from tools import execute_tool
from tools.active_window_tracker import ActiveWindowTracker
from ui.animation import AssistantOrb
from ui.debug_panel import DebugPanel
from ui.markdown import md_to_html
from ui.memory_panel import MemoryDrawer
from ui.mode_selector import ModeSelector
from ui.signals import get_signals
from ui.state_manager import get_state_manager
from ui.theme import (
    C_ACCENT,
    C_ACCENT2,
    C_BG,
    C_BG2,
    C_BORDER,
    C_BORDER2,
    C_GREEN,
    C_ORANGE,
    C_RED,
    C_TEXT,
    C_TEXT_DIM,
    C_YELLOW,
    MODE_COLORS,
    state_display,
)
from ui.tool_notification import ToolToast


class LLMWorkerSignals(QObject):
    token = Signal(str)
    finished = Signal(str)
    error = Signal(str)
    state_change = Signal(str)
    tool_executed = Signal(str)


class LLMWorker(QRunnable):
    def __init__(
        self,
        manager: ConversationManager,
        user_msg: str,
        mode_config: dict | None = None,
        image_path: str | None = None,
        active_window_info: dict | None = None,
        attachments: list[AttachmentSummary] | None = None,
    ):
        super().__init__()
        self.signals = LLMWorkerSignals()
        self._manager = manager
        self._msg = user_msg
        self._image_path = image_path
        self._mode_config = mode_config
        self._active_window_info = active_window_info
        self._attachments = attachments or []

    def run(self):
        try:
            for _token in self._manager.chat_stream(
                self._msg,
                self._image_path,
                on_token=self.signals.token.emit,
                on_tool=lambda result: self.signals.tool_executed.emit(str(result)),
                on_state=self.signals.state_change.emit,
                mode_config=self._mode_config,
                active_window_info=self._active_window_info,
                attachments=self._attachments,
            ):
                pass
            self.signals.finished.emit("done")
        except Exception as e:
            self.signals.error.emit(str(e))
            self.signals.state_change.emit("IDLE")


class MainWindow(QMainWindow):
    _transcribed_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.cfg = get_config()
        self.conv = ConversationManager()
        self.recorder = PushToTalkRecorder()
        self.tts = TTSManager()
        self._signals = get_signals()
        self._sm = get_state_manager()
        self._assistant_responding = False
        self._saved_volume = None
        self._streaming_buffer = ""
        self._tts_token_queue: queue.Queue | None = None
        self._pending_image: str | None = None
        self._thread_pool = QThreadPool.globalInstance()
        self._start_time = 0.0
        self._assistant_start_cursor: QTextCursor | None = None
        self._last_assistant_pos: int = 0
        self._active_window_tracker: ActiveWindowTracker | None = None

        init_db()
        self._setup_ui()
        self._setup_connections()
        self._setup_app_shortcuts()
        self._start_backend()

    def _setup_ui(self):
        self.setWindowTitle(self.cfg.window_title)
        w, h = self.cfg.window_size
        self.resize(w, h)
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background-color: {C_BG}; color: {C_TEXT}; }}
            QSplitter::handle {{ background: {C_BORDER}; }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._make_header())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setSpacing(0)
        body_layout.setContentsMargins(0, 0, 0, 0)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(0)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._orb_bar = self._make_orb_bar()
        left_layout.addWidget(self._orb_bar)

        self._chat_display = self._make_chat_display()
        left_layout.addWidget(self._chat_display, stretch=1)

        self._input_bar = self._make_input_bar()
        left_layout.addWidget(self._input_bar)

        body_layout.addWidget(left, stretch=1)

        self.memory_drawer = MemoryDrawer()
        body_layout.addWidget(self.memory_drawer)

        root.addWidget(body, stretch=1)

        self._status_bar = QLabel(f"  {self.cfg.persona_name.upper()}  |  {self.cfg.llm_backend.upper()}")
        self._status_bar.setStyleSheet(f"""
            QLabel {{
                background: {C_BG2}; color: {C_TEXT_DIM};
                font-family: Consolas; font-size: 10px;
                padding: 2px 8px; border-top: 1px solid {C_BORDER};
            }}
        """)
        root.addWidget(self._status_bar)

        self._toast = ToolToast(self)

        self.debug_panel = DebugPanel()
        self.debug_panel.setWindowFlags(Qt.Window)

    def _make_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_BORDER};")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 0, 12, 0)

        title = QLabel(f"◈ {self.cfg.window_title}")
        title.setStyleSheet(f"color: {C_ACCENT}; font-family: Consolas; font-size: 13px; font-weight: bold; background: transparent;")
        layout.addWidget(title)

        layout.addStretch()

        self._mode_selector = ModeSelector()
        layout.addWidget(self._mode_selector)

        self._connection_indicator = QLabel("CONNECTING")
        self._connection_indicator.setStyleSheet(f"color: {C_YELLOW}; font-family: Consolas; font-size: 10px; font-weight: bold; background: transparent;")
        layout.addWidget(self._connection_indicator)

        return header

    def _make_orb_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 4, 12, 4)

        self._orb = AssistantOrb()
        self._orb.setFixedSize(40, 40)
        layout.addWidget(self._orb)

        self._state_label = QLabel("Ready")
        self._state_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 14px; font-weight: bold; background: transparent;")
        layout.addWidget(self._state_label)

        self._mode_indicator = QLabel("")
        self._mode_indicator.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px; background: transparent; padding-left: 8px;")
        layout.addWidget(self._mode_indicator)

        layout.addStretch()

        self._metrics_bar = QLabel("")
        self._metrics_bar.setStyleSheet(f"color: {C_TEXT_DIM}; font-family: Consolas; font-size: 9px; background: transparent;")
        layout.addWidget(self._metrics_bar)

        return bar

    def _make_chat_display(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(0)
        layout.setContentsMargins(8, 8, 8, 4)

        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setFont(QFont("Consolas", 12))
        self._chat.setLineWrapMode(QTextEdit.WidgetWidth)
        self._chat.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._chat.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                padding: 8px;
                selection-background-color: {C_ACCENT2};
            }}
            QScrollBar:vertical {{
                background: {C_BG2}; width: 8px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER2}; border-radius: 4px;
            }}
        """)
        layout.addWidget(self._chat)

        return container

    def _make_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(6)

        self._ptt_btn = QPushButton("◎")
        self._ptt_btn.setFixedSize(42, 36)
        self._ptt_btn.setCheckable(True)
        self._ptt_btn.setToolTip("Hold to talk (Ctrl+Space)")
        self._ptt_btn.setStyleSheet(self._ptt_style(False))
        self._ptt_btn.pressed.connect(self._ptt_start)
        self._ptt_btn.released.connect(self._ptt_stop)

        self._input = QLineEdit()
        self._input.setPlaceholderText(f"Message {self.cfg.persona_name}...")
        self._input.setFixedHeight(36)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BG2}; color: {C_TEXT};
                border: 1px solid {C_BORDER}; border-radius: 6px;
                padding: 0 12px; font-family: Consolas; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {C_ACCENT2}; }}
        """)
        self._input.returnPressed.connect(self._send_text)
        layout.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("SEND")
        self._send_btn.setFixedSize(64, 36)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_BORDER2}; color: {C_ACCENT};
                border: 1px solid {C_ACCENT2}; border-radius: 6px;
                font-family: Consolas; font-size: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {C_ACCENT2}; color: #fff; }}
            QPushButton:disabled {{ color: {C_TEXT_DIM}; border-color: {C_BORDER}; }}
        """)
        self._send_btn.clicked.connect(self._send_text)
        layout.addWidget(self._send_btn)

        self._stop_btn = QPushButton("■")
        self._stop_btn.setFixedSize(42, 36)
        self._stop_btn.setToolTip("Stop")
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_RED};
                border: 1px solid {C_RED}; border-radius: 6px;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: {C_RED}; color: #fff; }}
        """)
        self._stop_btn.clicked.connect(self._interrupt)
        layout.addWidget(self._stop_btn)

        return bar

    def _ptt_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {C_GREEN}; color: #000;
                    border: 1px solid {C_GREEN}; border-radius: 6px;
                    font-size: 16px;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent; color: {C_GREEN};
                border: 1px solid {C_GREEN}; border-radius: 6px;
                font-size: 16px;
            }}
            QPushButton:hover {{ background: rgba(0,255,157,0.1); }}
        """

    def _setup_connections(self):
        self._signals.state_changed.connect(self._on_state)
        self._signals.mode_changed.connect(self._on_mode)
        self._signals.connection_changed.connect(self._on_connection)
        self._signals.assistant_token.connect(self._on_token)
        self._signals.assistant_done.connect(self._on_done)
        self._signals.tool_executed.connect(self._on_tool_result)
        self._signals.error_occurred.connect(self._on_error_signal)

        self._transcribed_signal.connect(self._on_transcribed)
        self.recorder.on_transcribed = self._transcribed_signal.emit
        self.recorder.on_status = self._on_recorder_status
        self.recorder.on_level = self._signals.audio_level.emit
        self.tts.set_speaking_callback(self._on_speaking)
        self._signals.stop_requested.connect(self._interrupt)
        from tools.registry import set_tts_speed_callback
        set_tts_speed_callback(self.tts.set_speed)

    def _setup_app_shortcuts(self):
        sc_ss = QShortcut(QKeySequence("Ctrl+Shift+J"), self)
        sc_ss.activated.connect(self._take_screenshot)

    # ── State updates ────────────────────────────────────────────────────

    def _on_state(self, state: str):
        self._orb.set_state(state)
        self._state_label.setText(state_display(state))

    def _on_mode(self, mode: str):
        cfg = self._sm._modes.get(mode, {})
        indicator = cfg.get("indicator", mode.upper())
        color = MODE_COLORS.get(mode, C_TEXT_DIM)
        self._mode_indicator.setText(f"[{indicator}]")
        self._mode_indicator.setStyleSheet(f"color: {color}; font-family: Consolas; font-size: 9px; background: transparent; padding-left: 8px;")

        tts_speed = cfg.get("tts_speed")
        if tts_speed is not None:
            self.tts.set_speed(tts_speed)

    def _on_connection(self, status: str):
        color_map = {"CONNECTING": C_YELLOW, "READY": C_GREEN, "OFFLINE": C_RED}
        color = color_map.get(status, C_YELLOW)
        self._connection_indicator.setText(status)
        self._connection_indicator.setStyleSheet(f"color: {color}; font-family: Consolas; font-size: 10px; font-weight: bold; background: transparent;")

    # ── Message send / receive ───────────────────────────────────────────

    def _send_text(self):
        text = self._input.text().strip()
        if not text:
            return
        if self._assistant_responding:
            self._interrupt()
        self._input.clear()
        self.dispatch_message(text)

    def dispatch_message(
        self,
        text: str,
        image_path: str | None = None,
        attachment_paths: list[str] | None = None,
    ):
        attachments: list[AttachmentSummary] = []
        if attachment_paths:
            attachments = get_attachment_processor().summarize_many(attachment_paths)
        self._dispatch_message(text, image_path=image_path, attachments=attachments)

    def ptt_start(self):
        self._ptt_start()

    def ptt_stop(self):
        self._ptt_stop()

    def take_screenshot(self):
        self._take_screenshot()

    def _dispatch_message(
        self,
        text: str,
        image_path: str | None = None,
        attachments: list[AttachmentSummary] | None = None,
    ):
        if self._assistant_responding:
            return

        mode_cmd = self._sm.detect_mode_command(text)
        if mode_cmd:
            self._sm.set_mode(mode_cmd)
            self._append_system(f"Mode: {mode_cmd}")
            return

        attachments = attachments or []
        if image_path is None:
            for att in attachments:
                if att.kind == "image" and att.path:
                    image_path = att.path
                    break

        if image_path is None and self._should_capture_screen(text):
            result = get_tool_runner().run("take_screenshot", {}, require_confirmation=False)
            if result.success:
                image_path = result.data.get("path")
            else:
                self._append_error(result.message)

        active_window_info = None
        if self._active_window_tracker and self.cfg.track_active_window:
            active_window_info = self._active_window_tracker.current

        self._assistant_responding = True
        self._streaming_buffer = ""
        self._send_btn.setEnabled(False)
        self._start_time = time.time()

        self._append_user(text)
        self._append_assistant_start()
        self._signals.user_message_sent.emit(text)

        if self._sm.tts_enabled:
            self._tts_token_queue = queue.Queue()
            self.tts.speak_streaming(self._tts_token_queue)
        else:
            self._tts_token_queue = None

        mode_config = self._sm.mode_config

        worker = LLMWorker(self.conv, text, mode_config, image_path, active_window_info, attachments)
        worker.signals.token.connect(self._on_token_worker)
        worker.signals.finished.connect(self._on_finished_worker)
        worker.signals.error.connect(self._on_error_worker)
        worker.signals.state_change.connect(self._on_worker_state)
        worker.signals.tool_executed.connect(self._on_tool_worker)
        self._thread_pool.start(worker)

    def _on_token_worker(self, token: str):
        self._streaming_buffer += token
        self._append_token(token)
        self._signals.assistant_token.emit(token)
        if self._tts_token_queue is not None:
            self._tts_token_queue.put(token)

    def _on_finished_worker(self, _):
        self._assistant_responding = False
        self._send_btn.setEnabled(True)
        self._pending_image = None

        self._render_markdown_response()

        if self._tts_token_queue is not None:
            self._tts_token_queue.put(None)
            self._tts_token_queue = None
        else:
            self._sm.set_state("READY")

        elapsed = (time.time() - self._start_time) * 1000
        self._sm.update_metrics(response_time=int(elapsed))

        self._signals.assistant_done.emit(self._streaming_buffer)

    def _render_markdown_response(self):
        if self._streaming_buffer and self._assistant_start_cursor is not None:
            cursor = QTextCursor(self._chat.document())
            cursor.setPosition(self._last_assistant_pos)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            html = md_to_html(self._streaming_buffer)
            cursor.insertHtml(html)
        self._assistant_start_cursor = None

    def _on_error_worker(self, err: str):
        self._assistant_responding = False
        self._send_btn.setEnabled(True)
        if self._tts_token_queue is not None:
            self._tts_token_queue.put(None)
            self._tts_token_queue = None
        self._append_error(err)
        self._sm.set_state("ERROR")
        self._signals.error_occurred.emit(err)

    def _on_tool_worker(self, result: str):
        self._append_tool(result)
        self._signals.tool_executed.emit(result, True)
        self.memory_drawer._refresh()

    def _on_token(self, token: str):
        pass  # Handled via _on_token_worker -> signal bridge

    def _on_done(self, full_text: str):
        pass

    def _on_tool_result(self, result: str, success: bool):
        self._toast.show_toast(result, success)

    _STATE_TRANSITIONS = {
        "READY": {"THINKING", "ACTING", "SPEAKING"},
        "THINKING": {"ACTING", "SPEAKING", "READY", "THINKING"},
        "ACTING": {"THINKING", "SPEAKING", "READY", "ACTING"},
        "SPEAKING": {"READY"},
    }

    def _on_worker_state(self, state: str):
        state = (state or "").upper()
        if state == "IDLE":
            state = "READY"
        current = self._sm.state
        allowed = self._STATE_TRANSITIONS.get(current, {"THINKING", "ACTING", "SPEAKING", "READY"})
        if state not in allowed:
            return
        if state in ("THINKING", "ACTING"):
            if current == "SPEAKING":
                return
            self._sm.set_state(state)
        elif state in ("SPEAKING", "READY"):
            if current == "SPEAKING" and state != "READY":
                return
            self._sm.set_state(state)

    def _on_error_signal(self, err: str):
        pass

    # ── PTT / Voice ──────────────────────────────────────────────────────

    def _ptt_start(self):
        if self._sm.mic_muted:
            return
        # Always interrupt any in-flight TTS to ensure clean barge-in
        if self._assistant_responding:
            self._interrupt()
        elif self.tts and self.tts.is_speaking():
            self.tts.interrupt()
            self._assistant_responding = False
        # Save and duck system volume
        saved = get_system_volume()
        if saved is not None:
            self._saved_volume = saved
            set_system_volume(0.15)
        self._ptt_btn.setStyleSheet(self._ptt_style(True))
        self.recorder.start_recording()

    def _ptt_stop(self):
        if self._saved_volume is not None:
            set_system_volume(self._saved_volume)
            self._saved_volume = None
        self._ptt_btn.setStyleSheet(self._ptt_style(False))
        # Build whisper prompt from recent conversation
        whisper_prompt = None
        try:
            recent = get_recent_turns(self.conv.session_id, limit=3)
            if recent:
                parts = []
                for r in reversed(recent):
                    role = r.get("role", "")
                    content = r.get("content", "").strip()
                    if content and role in ("user", "assistant"):
                        parts.append(f"{role}: {content[:120]}")
                if parts:
                    whisper_prompt = " | ".join(parts)
        except Exception:
            pass
        self.recorder.stop_and_transcribe(initial_prompt=whisper_prompt)

    def toggle_ptt(self):
        if not self._ptt_btn.isChecked():
            self._ptt_start()
            self._ptt_btn.setChecked(True)
        else:
            self._ptt_stop()
            self._ptt_btn.setChecked(False)

    def _on_transcribed(self, text: str):
        self._input.setText(text)
        self._dispatch_message(text)

    def _on_recorder_status(self, status: str):
        self._sm.set_state(status)

    def _on_speaking(self, is_speaking: bool):
        if not is_speaking and self._sm.state == "LISTENING":
            return
        self._sm.set_state("SPEAKING" if is_speaking else "READY")
        self._signals.speaking_changed.emit(is_speaking)

    # ── Interrupt ────────────────────────────────────────────────────────

    def _interrupt(self):
        self.conv.interrupt()
        if self._tts_token_queue is not None:
            self._tts_token_queue.put(None)
            self._tts_token_queue = None
        self.tts.interrupt()
        self._assistant_responding = False
        self._streaming_buffer = ""
        self._assistant_start_cursor = None
        self._send_btn.setEnabled(True)
        self._sm.set_state("READY")
        self._append_system("Interrupted.")
        self._signals.interruption_requested.emit()

    # ── Screenshot ───────────────────────────────────────────────────────

    def _take_screenshot(self):
        result = execute_tool("take_screenshot", {})
        if result.success:
            path = result.data.get("path")
            self._dispatch_message("What do you see on my screen?", image_path=path)
        else:
            self._append_error(result.message)

    def _should_capture_screen(self, text: str) -> bool:
        query = (text or "").lower().strip()
        triggers = [
            "what is on my screen", "what's on my screen", "what do you see",
            "look at my screen", "analyze my screen", "analyze this screen",
            "read my screen", "screenshot", "screen",
        ]
        return any(t in query for t in triggers)

    # ── Chat display helpers ─────────────────────────────────────────────

    def _append_user(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_colored(f"\n[{ts}] YOU › {text}", C_GREEN)

    def _append_assistant_start(self):
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_colored(f"\n[{ts}] {self.cfg.persona_name.upper()} › ", C_ACCENT, newline=False)
        self._assistant_start_cursor = self._chat.textCursor()
        self._assistant_start_cursor.movePosition(QTextCursor.End)
        self._last_assistant_pos = self._assistant_start_cursor.position()

    def _append_token(self, token: str):
        cursor = self._chat.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(C_TEXT))
        cursor.insertText(token, fmt)
        self._chat.setTextCursor(cursor)
        self._chat.ensureCursorVisible()

    def _append_tool(self, text: str):
        self._append_colored(f"\n  ⚙ {text}", C_ORANGE)

    def _append_error(self, text: str):
        self._append_colored(f"\n[ERR] {text}", C_RED)

    def _append_system(self, text: str):
        self._append_colored(f"\n[SYS] {text}", C_TEXT_DIM)

    def _append_colored(self, text: str, color_hex: str, newline: bool = True):
        cursor = self._chat.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        if newline:
            text = "\n" + text
        cursor.insertText(text, fmt)
        self._chat.setTextCursor(cursor)
        self._chat.ensureCursorVisible()

    # ── Backend startup ─────────────────────────────────────────────────

    def _start_backend(self):
        self._sm.set_connection("CONNECTING")
        self.debug_panel.append_system(f"Initializing {self.cfg.window_title}...")
        self.debug_panel.append_system(f"Backend: {self.cfg.llm_backend.upper()} @ {self.cfg.llm_base_url}")
        self.debug_panel.append_system(f"Model: {self.cfg.llm_model}")

        if self.cfg.track_active_window:
            self._start_window_tracker()

        def _check():
            ok, msg = self.conv.test_connection()
            def _update():
                if ok:
                    self._sm.set_connection("READY")
                    self.debug_panel.append_system(msg)
                else:
                    self._sm.set_connection("OFFLINE")
                    self.debug_panel.append_system(f"[ERROR] {msg}")
            QTimer.singleShot(0, _update)
        threading.Thread(target=_check, daemon=True).start()

        def _load_stt():
            try:
                load_whisper()
                QTimer.singleShot(0, lambda: self.debug_panel.append_system("Whisper STT ready."))
            except Exception:
                QTimer.singleShot(0, lambda: self.debug_panel.append_system("Whisper unavailable"))
        threading.Thread(target=_load_stt, daemon=True).start()

        self._backend_timer = QTimer(self)
        self._backend_timer.timeout.connect(self._refresh_backend)
        self._backend_timer.start(30000)

    def _start_window_tracker(self):
        self._active_window_tracker = ActiveWindowTracker(self)
        self._active_window_tracker.window_changed.connect(self._on_window_changed)
        self._active_window_tracker.start(self.cfg.window_poll_interval_ms)
        self.debug_panel.append_system(f"Active window tracker started ({self.cfg.window_poll_interval_ms}ms interval)")

    def _on_window_changed(self, info: dict):
        title = info.get("title", "")
        proc = info.get("process_name", "")
        if title:
            self.debug_panel.append_system(f"Focus: {proc} · {title[:60]}")
        self._signals.window_context_changed.emit(info)

    def _refresh_backend(self):
        def _check():
            ok, _ = self.conv.test_connection()
            def _update():
                self._sm.set_connection("READY" if ok else "OFFLINE")
            QTimer.singleShot(0, _update)
        threading.Thread(target=_check, daemon=True).start()

    def closeEvent(self, event):
        self._signals.quit_requested.emit()
        event.accept()
