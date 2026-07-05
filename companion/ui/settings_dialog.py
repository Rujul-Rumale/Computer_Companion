from __future__ import annotations

import os
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
from ui.theme import C_ACCENT, C_ACCENT2, C_BG, C_BG2, C_BORDER, C_TEXT, C_TEXT_DIM

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


def _save_config(raw: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    get_config().reload()


class _BrowseField(QHBoxLayout):
    def __init__(self, placeholder="", file_filter="*.*", parent=None):
        super().__init__(parent)
        self._filter = file_filter
        self.field = QLineEdit()
        self.field.setPlaceholderText(placeholder)
        self.field.setStyleSheet(f"""
            QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER};
                          border-radius: 4px; padding: 2px 6px; font-family: Consolas; font-size: 11px; }}
            QLineEdit:focus {{ border-color: {C_ACCENT2}; }}
        """)
        self.addWidget(self.field, stretch=1)
        btn = QPushButton("...")
        btn.setFixedSize(26, 24)
        btn.setStyleSheet(f"""
            QPushButton {{ background: {C_BG2}; color: {C_TEXT}; border: 1px solid {C_BORDER};
                          border-radius: 4px; font-size: 12px; }}
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
        self.setMinimumSize(520, 420)
        self.setStyleSheet(f"""
            QDialog {{ background: {C_BG}; color: {C_TEXT}; font-family: Consolas; font-size: 12px; }}
            QLabel {{ color: {C_TEXT}; }}
            QGroupBox {{ border: 1px solid {C_BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 16px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {C_TEXT_DIM}; }}
        """)
        self._setup_ui()
        self._load_values()

    def _make_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        scroll.setWidget(container)
        return scroll

    def _add_group(self, parent_layout: QVBoxLayout, title: str) -> QFormLayout:
        group = QGroupBox(title)
        flay = QFormLayout(group)
        flay.setSpacing(6)
        flay.setContentsMargins(10, 16, 10, 10)
        flay.setLabelAlignment(Qt.AlignRight)
        parent_layout.addWidget(group)
        return flay

    def _add_row(self, form: QFormLayout, label: str, widget: QWidget):
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px;")
        form.addRow(lbl, widget)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {C_BORDER}; border-radius: 4px; background: transparent; }}
            QTabBar::tab {{ background: {C_BG2}; color: {C_TEXT_DIM}; border: 1px solid {C_BORDER};
                           border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px;
                           padding: 6px 14px; font-family: Consolas; font-size: 11px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {C_BG}; color: {C_TEXT}; border-bottom: 1px solid {C_BG}; }}
            QTabBar::tab:hover {{ background: {C_ACCENT2}; color: #fff; }}
        """)

        tabs.addTab(self._build_llm_tab(), "LLM")
        tabs.addTab(self._build_voice_tab(), "Voice")
        tabs.addTab(self._build_keys_tab(), "Keys")
        tabs.addTab(self._build_ui_tab(), "UI")
        tabs.addTab(self._build_user_tab(), "User")
        layout.addWidget(tabs, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{ background: {C_ACCENT2}; color: #fff; border: none; border-radius: 4px;
                          padding: 6px 20px; font-family: Consolas; font-size: 12px; font-weight: bold; }}
            QPushButton:hover {{ background: {C_ACCENT}; }}
        """)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background: {C_BG2}; color: {C_TEXT}; border: 1px solid {C_BORDER};
                          border-radius: 4px; padding: 6px 20px; font-family: Consolas; font-size: 12px; }}
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

    def _build_llm_tab(self) -> QWidget:
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Backend")
        self._llm_backend = QComboBox()
        self._llm_backend.addItems(["llama", "lmstudio", "ollama"])
        self._llm_backend.setStyleSheet(f"QComboBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Backend", self._llm_backend)

        self._llm_model = QLineEdit()
        self._llm_model.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Model name", self._llm_model)

        self._llm_temp = QDoubleSpinBox()
        self._llm_temp.setRange(0.0, 2.0)
        self._llm_temp.setSingleStep(0.05)
        self._llm_temp.setDecimals(2)
        self._llm_temp.setStyleSheet(f"QDoubleSpinBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Temperature", self._llm_temp)

        self._llm_ctx = QSpinBox()
        self._llm_ctx.setRange(1024, 65536)
        self._llm_ctx.setSingleStep(1024)
        self._llm_ctx.setStyleSheet(f"QSpinBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Context size", self._llm_ctx)

        f2 = self._add_group(layout, "Model path (llama.cpp)")
        browse = _BrowseField(placeholder="Path to .gguf file", file_filter="GGUF files (*.gguf);;All files (*.*)")
        self._llm_path = browse.field
        self._llm_path.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; font-family: Consolas; font-size: 11px; }}")
        path_row = QHBoxLayout()
        path_row.addWidget(self._llm_path, stretch=1)
        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(f"QPushButton {{ background: {C_BG2}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 10px; }} QPushButton:hover {{ background: {C_ACCENT2}; color: #fff; }}")
        browse_btn.clicked.connect(self._browse_model)
        path_row.addWidget(browse_btn)
        f2.addRow(path_row)

        layout.addStretch()
        return scroll

    def _build_voice_tab(self) -> QWidget:
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "TTS Engine")
        self._tts_engine = QComboBox()
        self._tts_engine.addItems(["piper", "kokoro", "chatterbox", "pyttsx3"])
        self._tts_engine.setStyleSheet(f"QComboBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Engine", self._tts_engine)

        self._kokoro_voice = QLineEdit()
        self._kokoro_voice.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Kokoro voice", self._kokoro_voice)

        self._kokoro_speed = QDoubleSpinBox()
        self._kokoro_speed.setRange(0.5, 2.0)
        self._kokoro_speed.setSingleStep(0.05)
        self._kokoro_speed.setDecimals(2)
        self._kokoro_speed.setStyleSheet(f"QDoubleSpinBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Kokoro speed", self._kokoro_speed)

        self._piper_model = QLineEdit()
        self._piper_model.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Piper model path", self._piper_model)

        f2 = self._add_group(layout, "Whisper (STT)")
        self._whisper_model = QComboBox()
        self._whisper_model.addItems(["tiny", "base", "small", "medium", "large"])
        self._whisper_model.setStyleSheet(f"QComboBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f2, "Model", self._whisper_model)

        self._whisper_device = QComboBox()
        self._whisper_device.addItems(["cuda", "cpu"])
        self._whisper_device.setStyleSheet(f"QComboBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f2, "Device", self._whisper_device)

        layout.addStretch()
        return scroll

    def _build_keys_tab(self) -> QWidget:
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Hotkeys")
        self._ptt_key = QLineEdit()
        self._ptt_key.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Push-to-talk", self._ptt_key)

        self._screenshot_key = QLineEdit()
        self._screenshot_key.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Screenshot", self._screenshot_key)

        note = QLabel("Format: ctrl+space, ctrl+shift+j (lowercase, no spaces)")
        note.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 10px; padding: 4px 0;")
        layout.addWidget(note)
        layout.addStretch()
        return scroll

    def _build_ui_tab(self) -> QWidget:
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Appearance")
        self._font_family = QLineEdit()
        self._font_family.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Font", self._font_family)

        self._font_size = QSpinBox()
        self._font_size.setRange(8, 24)
        self._font_size.setStyleSheet(f"QSpinBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Font size", self._font_size)

        self._win_w = QSpinBox()
        self._win_w.setRange(400, 3840)
        self._win_w.setStyleSheet(f"QSpinBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Window width", self._win_w)

        self._win_h = QSpinBox()
        self._win_h.setRange(300, 2160)
        self._win_h.setStyleSheet(f"QSpinBox {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Window height", self._win_h)

        self._pet_enabled = QCheckBox("Show companion pet")
        self._pet_enabled.setStyleSheet(f"QCheckBox {{ color: {C_TEXT}; }} QCheckBox::indicator {{ width: 14px; height: 14px; }}")
        f.addRow(self._pet_enabled)

        layout.addStretch()
        return scroll

    def _build_user_tab(self) -> QWidget:
        scroll = self._make_tab()
        container = scroll.widget()
        layout = container.layout()

        f = self._add_group(layout, "Your Context")
        self._user_city = QLineEdit()
        self._user_city.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "City", self._user_city)

        self._user_country = QLineEdit()
        self._user_country.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Country", self._user_country)

        self._user_tz = QLineEdit()
        self._user_tz.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Timezone", self._user_tz)

        self._user_currency = QLineEdit()
        self._user_currency.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Currency", self._user_currency)

        self._user_language = QLineEdit()
        self._user_language.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Language", self._user_language)

        self._user_locale = QLineEdit()
        self._user_locale.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Locale", self._user_locale)

        self._user_work_hours = QLineEdit()
        self._user_work_hours.setStyleSheet(f"QLineEdit {{ background: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; border-radius: 4px; padding: 2px 6px; }}")
        self._add_row(f, "Work hours", self._user_work_hours)

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
