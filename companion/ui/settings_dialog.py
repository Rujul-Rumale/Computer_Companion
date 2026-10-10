from __future__ import annotations

from pathlib import Path

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import get_config
from ui.theme import C_ACCENT, C_ACCENT2, C_BG, C_BG2, C_BORDER, C_BORDER2, C_GREEN, C_PANEL, C_RED, C_TEXT, C_TEXT_DIM, C_TEXT_MID

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

_WIDGET_STYLE = f"""
    background: {C_BG}; color: {C_TEXT};
    border: 1px solid {C_BORDER};
    border-radius: 6px; padding: 4px 8px;
    font-family: Consolas; font-size: 11px;
"""
_FOCUS_STYLE = f"QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {C_ACCENT}; }}"


def _save_config(raw: dict):
    CONFIG_DIR.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    get_config().reload()


class _BrowseField(QHBoxLayout):
    def __init__(self, placeholder="", file_filter="*.*", parent=None):
        super().__init__(parent)
        self._filter = file_filter
        self.field = QLineEdit()
        self.field.setPlaceholderText(placeholder)
        self.field.setStyleSheet(_WIDGET_STYLE + _FOCUS_STYLE)
        self.addWidget(self.field, stretch=1)
        btn = QPushButton("\u2026")
        btn.setFixedSize(28, 26)
        btn.setStyleSheet(f"""
            QPushButton {{ background: {C_BG2}; color: {C_TEXT_MID}; border: 1px solid {C_BORDER};
                          border-radius: 6px; font-size: 14px; }}
            QPushButton:hover {{ background: {C_ACCENT2}; color: #fff; }}
        """)
        btn.clicked.connect(self._browse)
        self.addWidget(btn)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self.parent(), "Select file", self.field.text(), self._filter)
        if path:
            self.field.setText(path)

    def text(self):
        return self.field.text()

    def setText(self, txt):
        self.field.setText(txt)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = get_config()
        self.setWindowTitle("Settings")
        self.setMinimumSize(540, 460)
        self.setStyleSheet(f"""
            QDialog {{ background: {C_BG}; color: {C_TEXT}; font-family: Consolas; font-size: 12px; }}
            QLabel {{ color: {C_TEXT}; }}
            QGroupBox {{
                border: 1px solid {C_BORDER}; border-radius: 8px;
                margin-top: 14px; padding-top: 18px;
                background: {C_PANEL};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 12px; padding: 0 6px;
                color: {C_TEXT_MID}; font-size: 11px;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 8px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER}; border-radius: 4px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {C_BORDER2}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._setup_ui()
        self._load_values()

    def _make_widget(self, w: QWidget) -> QWidget:
        """Apply base widget style to a form control."""
        w.setStyleSheet(_WIDGET_STYLE + _FOCUS_STYLE)
        return w

    def _make_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        scroll.setWidget(container)
        return scroll

    def _add_group(self, parent_layout: QVBoxLayout, title: str) -> QFormLayout:
        group = QGroupBox(title)
        flay = QFormLayout(group)
        flay.setSpacing(8)
        flay.setContentsMargins(12, 18, 12, 12)
        flay.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        parent_layout.addWidget(group)
        return flay

    def _add_row(self, form: QFormLayout, label: str, widget: QWidget):
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px; padding-top: 2px;")
        form.addRow(lbl, widget)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {C_BORDER};
                border-radius: 8px; background: transparent;
                top: -1px;
            }}
            QTabBar::tab {{
                background: {C_BG2}; color: {C_TEXT_DIM};
                border: 1px solid {C_BORDER};
                border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 7px 18px; font-family: Consolas; font-size: 11px; margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {C_PANEL}; color: {C_TEXT};
                border-color: {C_BORDER};
            }}
            QTabBar::tab:hover {{
                background: {C_ACCENT2}; color: #fff;
            }}
        """)

        tabs.addTab(self._build_llm_tab(), "LLM")
        tabs.addTab(self._build_cloud_tab(), "Cloud")
        tabs.addTab(self._build_voice_tab(), "Voice")
        tabs.addTab(self._build_keys_tab(), "Keys")
        tabs.addTab(self._build_ui_tab(), "UI")
        tabs.addTab(self._build_user_tab(), "User")
        layout.addWidget(tabs, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_ACCENT2}; color: #fff; border: none; border-radius: 6px;
                padding: 7px 24px; font-family: Consolas; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {C_ACCENT}; }}
        """)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_BG2}; color: {C_TEXT}; border: 1px solid {C_BORDER};
                border-radius: 6px; padding: 7px 24px; font-family: Consolas; font-size: 12px;
            }}
            QPushButton:hover {{ background: {C_BORDER}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select GGUF model", "", "GGUF files (*.gguf);;All files (*.*)")
        if path:
            self._llm_path.setText(path)

    def _build_llm_tab(self):
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Backend")
        self._llm_backend = QComboBox()
        self._llm_backend.addItems(["llama", "lmstudio", "ollama", "cloud"])
        self._make_widget(self._llm_backend)
        self._add_row(f, "Backend", self._llm_backend)

        self._llm_model = QLineEdit()
        self._make_widget(self._llm_model)
        self._add_row(f, "Model name", self._llm_model)

        self._llm_temp = QDoubleSpinBox()
        self._llm_temp.setRange(0.0, 2.0)
        self._llm_temp.setSingleStep(0.05)
        self._llm_temp.setDecimals(2)
        self._make_widget(self._llm_temp)
        self._add_row(f, "Temperature", self._llm_temp)

        self._llm_ctx = QSpinBox()
        self._llm_ctx.setRange(1024, 65536)
        self._llm_ctx.setSingleStep(1024)
        self._make_widget(self._llm_ctx)
        self._add_row(f, "Context size", self._llm_ctx)

        f2 = self._add_group(layout, "Model path (llama.cpp)")
        browse = _BrowseField(placeholder="Path to .gguf file", file_filter="GGUF files (*.gguf);;All files (*.*)")
        self._llm_path = browse.field
        path_row = QHBoxLayout()
        path_row.addWidget(self._llm_path, stretch=1)
        browse_btn = QPushButton("Browse\u2026")
        browse_btn.setStyleSheet(f"QPushButton {{ background: {C_BG2}; color: {C_TEXT_MID}; border: 1px solid {C_BORDER}; border-radius: 6px; padding: 4px 14px; }} QPushButton:hover {{ background: {C_ACCENT2}; color: #fff; }}")
        browse_btn.clicked.connect(self._browse_model)
        path_row.addWidget(browse_btn)
        f2.addRow(path_row)

        layout.addStretch()
        return scroll

    def _build_cloud_tab(self):
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Cloud Provider")
        self._cloud_provider = QComboBox()
        self._cloud_provider.addItems(["nvidia", "openai", "together", "groq", "custom"])
        self._make_widget(self._cloud_provider)
        self._add_row(f, "Provider", self._cloud_provider)

        self._cloud_base_url = QLineEdit()
        self._cloud_base_url.setPlaceholderText("https://integrate.api.nvidia.com/v1")
        self._make_widget(self._cloud_base_url)
        self._add_row(f, "Base URL", self._cloud_base_url)

        self._cloud_model = QLineEdit()
        self._cloud_model.setPlaceholderText("meta/llama-3.1-90b-instruct")
        self._make_widget(self._cloud_model)
        self._add_row(f, "Model", self._cloud_model)

        f2 = self._add_group(layout, "API Key")
        key_row = QHBoxLayout()
        self._cloud_api_key = QLineEdit()
        self._cloud_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._cloud_api_key.setPlaceholderText("Enter API key...")
        self._make_widget(self._cloud_api_key)
        key_row.addWidget(self._cloud_api_key, stretch=1)
        toggle_btn = QPushButton("\u25C9")
        toggle_btn.setFixedSize(28, 26)
        toggle_btn.setStyleSheet(f"QPushButton {{ background: {C_BG2}; color: {C_TEXT_MID}; border: 1px solid {C_BORDER}; border-radius: 6px; font-size: 12px; }} QPushButton:hover {{ background: {C_ACCENT2}; color: #fff; }}")
        toggle_btn.clicked.connect(lambda: self._cloud_api_key.setEchoMode(
            QLineEdit.EchoMode.Normal if self._cloud_api_key.echoMode() == QLineEdit.EchoMode.Password
            else QLineEdit.EchoMode.Password
        ))
        key_row.addWidget(toggle_btn)
        f2.addRow(key_row)

        note = QLabel("Key is stored securely via OS keyring, never saved to config file.")
        note.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 10px; padding: 4px 0 0 0;")
        layout.addWidget(note)

        test_btn = QPushButton("Test Connection")
        test_btn.setStyleSheet(f"QPushButton {{ background: {C_BG2}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 6px; padding: 6px 16px; }} QPushButton:hover {{ background: {C_ACCENT2}; color: #fff; }}")
        test_btn.clicked.connect(self._test_cloud_connection)
        layout.addWidget(test_btn)

        self._cloud_test_result = QLabel("")
        self._cloud_test_result.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 10px;")
        layout.addWidget(self._cloud_test_result)

        layout.addStretch()
        return scroll

    def _test_cloud_connection(self):
        self._cloud_test_result.setText("Testing...")
        self._cloud_test_result.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 10px;")
        try:
            from openai import OpenAI
            base = self._cloud_base_url.text().rstrip("/")
            if not base.endswith("/v1"):
                base += "/v1"
            client = OpenAI(base_url=base, api_key=self._cloud_api_key.text() or "none")
            models = client.models.list()
            ids = [m.id for m in models.data][:5]
            self._cloud_test_result.setText(f"OK: {', '.join(ids)}")
            self._cloud_test_result.setStyleSheet(f"color: {C_GREEN}; font-size: 10px;")
        except Exception as e:
            self._cloud_test_result.setText(f"Failed: {e}")
            self._cloud_test_result.setStyleSheet(f"color: {C_RED}; font-size: 10px;")

    def _build_voice_tab(self):
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "TTS Engine")
        self._tts_engine = QComboBox()
        self._tts_engine.addItems(["piper", "kokoro", "chatterbox", "pyttsx3"])
        self._make_widget(self._tts_engine)
        self._add_row(f, "Engine", self._tts_engine)

        self._kokoro_voice = QLineEdit()
        self._make_widget(self._kokoro_voice)
        self._add_row(f, "Kokoro voice", self._kokoro_voice)

        self._kokoro_speed = QDoubleSpinBox()
        self._kokoro_speed.setRange(0.5, 2.0)
        self._kokoro_speed.setSingleStep(0.05)
        self._kokoro_speed.setDecimals(2)
        self._make_widget(self._kokoro_speed)
        self._add_row(f, "Kokoro speed", self._kokoro_speed)

        self._piper_model = QLineEdit()
        self._make_widget(self._piper_model)
        self._add_row(f, "Piper model path", self._piper_model)

        f2 = self._add_group(layout, "Whisper (STT)")
        self._whisper_model = QComboBox()
        self._whisper_model.addItems(["tiny", "base", "small", "medium", "large"])
        self._make_widget(self._whisper_model)
        self._add_row(f2, "Model", self._whisper_model)

        self._whisper_device = QComboBox()
        self._whisper_device.addItems(["cuda", "cpu"])
        self._make_widget(self._whisper_device)
        self._add_row(f2, "Device", self._whisper_device)

        layout.addStretch()
        return scroll

    def _build_keys_tab(self):
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Hotkeys")
        self._ptt_key = QLineEdit()
        self._make_widget(self._ptt_key)
        self._add_row(f, "Push-to-talk", self._ptt_key)

        self._screenshot_key = QLineEdit()
        self._make_widget(self._screenshot_key)
        self._add_row(f, "Screenshot", self._screenshot_key)

        note = QLabel("Format: ctrl+space, ctrl+shift+j (lowercase, no spaces)")
        note.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 10px; padding: 6px 0 0 0;")
        layout.addWidget(note)
        layout.addStretch()
        return scroll

    def _build_ui_tab(self):
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Appearance")
        self._font_family = QLineEdit()
        self._make_widget(self._font_family)
        self._add_row(f, "Font", self._font_family)

        self._font_size = QSpinBox()
        self._font_size.setRange(8, 24)
        self._make_widget(self._font_size)
        self._add_row(f, "Font size", self._font_size)

        self._win_w = QSpinBox()
        self._win_w.setRange(400, 3840)
        self._make_widget(self._win_w)
        self._add_row(f, "Window width", self._win_w)

        self._win_h = QSpinBox()
        self._win_h.setRange(300, 2160)
        self._make_widget(self._win_h)
        self._add_row(f, "Window height", self._win_h)

        self._pet_enabled = QCheckBox("Show companion pet")
        self._pet_enabled.setStyleSheet(f"QCheckBox {{ color: {C_TEXT}; spacing: 6px; }} QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {C_BORDER}; border-radius: 3px; background: {C_BG2}; }} QCheckBox::indicator:checked {{ background: {C_ACCENT}; border-color: {C_ACCENT}; }}")
        f.addRow(self._pet_enabled)

        layout.addStretch()
        return scroll

    def _build_user_tab(self):
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Your Context")
        fields = [
            ("City", "_user_city"),
            ("Country", "_user_country"),
            ("Timezone", "_user_tz"),
            ("Currency", "_user_currency"),
            ("Language", "_user_language"),
            ("Locale", "_user_locale"),
            ("Work hours", "_user_work_hours"),
        ]
        for label, attr in fields:
            edit = QLineEdit()
            self._make_widget(edit)
            setattr(self, attr, edit)
            self._add_row(f, label, edit)

        layout.addStretch()
        return scroll

    def _load_values(self):
        r = self.cfg._raw
        llm = r.get("llm", {})
        self._llm_backend.setCurrentText(llm.get("backend", "llama"))
        self._llm_model.setText(llm.get("model", ""))
        self._llm_temp.setValue(float(llm.get("temperature", 0.35)))
        self._llm_ctx.setValue(int(llm.get("context_window", 4096)))
        self._llm_path.setText(llm.get("llama_model_path", ""))

        cloud = llm.get("cloud", {})
        self._cloud_provider.setCurrentText(cloud.get("provider", "nvidia"))
        self._cloud_base_url.setText(cloud.get("base_url", ""))
        self._cloud_model.setText(cloud.get("model", ""))
        api_key_ref = cloud.get("api_key_ref", "")
        if api_key_ref:
            from security.keyring_store import load_key
            saved_key = load_key(api_key_ref)
            if saved_key:
                self._cloud_api_key.setText(saved_key)

        speech = r.get("speech", {})
        self._whisper_model.setCurrentText(speech.get("whisper_model", "medium"))
        self._whisper_device.setCurrentText(speech.get("whisper_device", "cuda"))

        tts = r.get("tts", {})
        self._tts_engine.setCurrentText(tts.get("engine", "piper"))
        self._kokoro_voice.setText(tts.get("kokoro_voice", ""))
        self._kokoro_speed.setValue(float(tts.get("kokoro_speed", 1.0)))
        self._piper_model.setText(tts.get("piper_model", ""))

        tools_sec = r.get("tools", {})
        self._ptt_key.setText(speech.get("push_to_talk_key", "ctrl+space"))
        self._screenshot_key.setText(tools_sec.get("screenshot_hotkey", "ctrl+shift+j"))

        ui_sec = r.get("ui", {})
        self._font_family.setText(ui_sec.get("font_family", "Consolas"))
        self._font_size.setValue(int(ui_sec.get("font_size", 13)))
        self._win_w.setValue(int(ui_sec.get("window_width", 1100)))
        self._win_h.setValue(int(ui_sec.get("window_height", 750)))
        self._pet_enabled.setChecked(bool(ui_sec.get("pet_enabled", True)))

        user = r.get("user", {})
        self._user_city.setText(user.get("city", ""))
        self._user_country.setText(user.get("country", ""))
        self._user_tz.setText(user.get("timezone", ""))
        self._user_currency.setText(user.get("currency", ""))
        self._user_language.setText(user.get("language", ""))
        self._user_locale.setText(user.get("locale", ""))
        self._user_work_hours.setText(user.get("work_hours", ""))

    def _save(self):
        raw = self.cfg._raw.copy()
        raw.setdefault("llm", {})["backend"] = self._llm_backend.currentText()
        raw["llm"]["model"] = self._llm_model.text()
        raw["llm"]["temperature"] = self._llm_temp.value()
        raw["llm"]["context_window"] = self._llm_ctx.value()
        raw["llm"]["llama_model_path"] = self._llm_path.text()

        cloud = raw["llm"].setdefault("cloud", {})
        cloud["provider"] = self._cloud_provider.currentText()
        cloud["base_url"] = self._cloud_base_url.text()
        cloud["model"] = self._cloud_model.text()

        api_key = self._cloud_api_key.text().strip()
        key_ref = cloud.get("api_key_ref", self._cloud_provider.currentText())
        cloud["api_key_ref"] = key_ref
        if api_key:
            from security.keyring_store import store_key
            store_key(key_ref, api_key)

        raw.setdefault("speech", {})["whisper_model"] = self._whisper_model.currentText()
        raw["speech"]["whisper_device"] = self._whisper_device.currentText()
        raw["speech"]["push_to_talk_key"] = self._ptt_key.text()

        tts = raw.setdefault("tts", {})
        tts["engine"] = self._tts_engine.currentText()
        tts["kokoro_voice"] = self._kokoro_voice.text()
        tts["kokoro_speed"] = self._kokoro_speed.value()
        tts["piper_model"] = self._piper_model.text()

        raw.setdefault("tools", {})["screenshot_hotkey"] = self._screenshot_key.text()

        ui_sec = raw.setdefault("ui", {})
        ui_sec["font_family"] = self._font_family.text()
        ui_sec["font_size"] = self._font_size.value()
        ui_sec["window_width"] = self._win_w.value()
        ui_sec["window_height"] = self._win_h.value()
        ui_sec["pet_enabled"] = self._pet_enabled.isChecked()

        user = raw.setdefault("user", {})
        user["city"] = self._user_city.text()
        user["country"] = self._user_country.text()
        user["timezone"] = self._user_tz.text()
        user["currency"] = self._user_currency.text()
        user["language"] = self._user_language.text()
        user["locale"] = self._user_locale.text()
        user["work_hours"] = self._user_work_hours.text()

        _save_config(raw)
        self.accept()
