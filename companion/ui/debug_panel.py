from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTabWidget, QVBoxLayout, QWidget

from ui.signals import get_signals
from ui.state_manager import get_state_manager
from ui.theme import C_ACCENT, C_BG, C_BG2, C_BORDER, C_TEXT, C_TEXT_MID


class DebugPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._sm = get_state_manager()
        self._signals = get_signals()
        self._setup_ui()
        self._signals.metrics_updated.connect(self._on_metrics)
        self._signals.state_changed.connect(self._on_state)

    def _setup_ui(self):
        self.setWindowTitle("Developer Panel")
        self.setStyleSheet(f"""
            QWidget {{ background: {C_BG}; color: {C_TEXT}; }}
            QPlainTextEdit {{
                background: {C_BG2}; color: {C_TEXT};
                border: 1px solid {C_BORDER};
                font-family: Consolas; font-size: 10px;
            }}
            QTabWidget::pane {{ border: 1px solid {C_BORDER}; }}
            QTabBar::tab {{
                background: {C_BG2}; color: {C_TEXT_MID};
                padding: 3px 10px; font-family: Consolas; font-size: 10px;
                border: 1px solid {C_BORDER};
            }}
            QTabBar::tab:selected {{ color: {C_ACCENT}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("// DEVELOPER PANEL")
        title.setStyleSheet(f"color: {C_ACCENT}; font-family: Consolas; font-size: 12px; font-weight: bold;")
        layout.addWidget(title)

        tabs = QTabWidget()

        # Logs
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(500)
        tabs.addTab(self._log, "LOGS")

        # Metrics
        self._metrics_widget = QWidget()
        metrics_layout = QVBoxLayout(self._metrics_widget)
        self._metrics_label = QLabel("TTFT: —\nResponse: —\nTTS latency: —\nMode: —\nMemory tokens: —")
        self._metrics_label.setStyleSheet(f"color: {C_TEXT}; font-family: Consolas; font-size: 11px;")
        metrics_layout.addWidget(self._metrics_label)
        metrics_layout.addStretch()
        tabs.addTab(self._metrics_widget, "METRICS")

        # Raw prompts
        self._prompt_log = QPlainTextEdit()
        self._prompt_log.setReadOnly(True)
        self._prompt_log.setMaximumBlockCount(100)
        tabs.addTab(self._prompt_log, "PROMPTS")

        layout.addWidget(tabs)

    def log(self, text: str):
        self._log.appendPlainText(text)

    def log_prompt(self, text: str):
        self._prompt_log.appendPlainText(text)

    def _on_metrics(self, metrics: dict):
        lines = []
        lines.append(f"TTFT: {metrics.get('ttft', '—')}ms")
        lines.append(f"Response time: {metrics.get('response_time', '—')}ms")
        lines.append(f"TTS latency: {metrics.get('tts_latency', '—')}ms")
        lines.append(f"Mode: {metrics.get('mode', '—')}")
        lines.append(f"Memory injected tokens: {metrics.get('memory_tokens', '—')}")
        self._metrics_label.setText("\n".join(lines))

    def _on_state(self, state: str):
        pass

    def append_system(self, text: str):
        self._log.appendPlainText(f"[SYS] {text}")
