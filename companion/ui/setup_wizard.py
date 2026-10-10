"""First-run setup wizard with hardware detection, cloud API, and model downloads."""

from __future__ import annotations

import yaml
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QSpinBox,
)

from ui.theme import (
    C_ACCENT, C_ACCENT2, C_BG, C_BG2, C_BORDER, C_BORDER2,
    C_GREEN, C_PANEL, C_RED, C_TEXT, C_TEXT_DIM, C_TEXT_MID,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_EXAMPLE = CONFIG_DIR / "config.example.yaml"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETUP_MARKER = DATA_DIR / ".setup_complete"
CATALOG_PATH = CONFIG_DIR / "model_catalog.yaml"

# ── Styles ──────────────────────────────────────────────────────────────────

_WIZARD_BG = "#0e1117"
_CARD_BG = "#161b22"
_CARD_HOVER = "#1c2129"
_CARD_SELECTED = "#1a2332"
_CARD_BORDER = "#30363d"
_CARD_BORDER_SEL = "#4d8fea"
_TEXT = "#e6edf3"
_TEXT_DIM = "#7d8590"
_TEXT_MID = "#8b949e"
_ACCENT = "#4d8fea"
_ACCENT2 = "#1f6feb"
_GREEN = "#2ea043"
_BTN_BG = "#21262d"
_BTN_HOVER = "#30363d"

_CARD_STYLE = f"""
    background: {_CARD_BG}; border: 2px solid {_CARD_BORDER};
    border-radius: 12px; padding: 20px;
"""
_CARD_HOVER_STYLE = f"""
    background: {_CARD_HOVER}; border: 2px solid {_CARD_BORDER};
    border-radius: 12px; padding: 20px;
"""
_CARD_SELECTED_STYLE = f"""
    background: {_CARD_SELECTED}; border: 2px solid {_CARD_BORDER_SEL};
    border-radius: 12px; padding: 20px;
"""
_INPUT_STYLE = f"""
    background: {_CARD_BG}; color: {_TEXT};
    border: 1px solid {_CARD_BORDER}; border-radius: 8px;
    padding: 8px 12px; font-family: 'Segoe UI', Consolas; font-size: 13px;
    selection-background-color: {_ACCENT};
"""
_INPUT_FOCUS_STYLE = f"""
    QLineEdit:focus {{ border-color: {_ACCENT}; }}
"""
_BTN_PRIMARY = f"""
    QPushButton {{
        background: {_ACCENT2}; color: #fff; border: none;
        border-radius: 8px; padding: 10px 28px;
        font-family: 'Segoe UI', Consolas; font-size: 13px; font-weight: bold;
    }}
    QPushButton:hover {{ background: {_ACCENT}; }}
    QPushButton:disabled {{ background: {_CARD_BORDER}; color: {_TEXT_DIM}; }}
"""
_BTN_SECONDARY = f"""
    QPushButton {{
        background: {_BTN_BG}; color: {_TEXT}; border: 1px solid {_CARD_BORDER};
        border-radius: 8px; padding: 10px 28px;
        font-family: 'Segoe UI', Consolas; font-size: 13px;
    }}
    QPushButton:hover {{ background: {_BTN_HOVER}; }}
"""
_COMBO_STYLE = f"""
    QComboBox {{
        background: {_CARD_BG}; color: {_TEXT};
        border: 1px solid {_CARD_BORDER}; border-radius: 8px;
        padding: 8px 12px; font-family: 'Segoe UI', Consolas; font-size: 13px;
        min-height: 20px;
    }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox::down-arrow {{ image: none; border-left: 5px solid transparent;
        border-right: 5px solid transparent; border-top: 6px solid {_TEXT_DIM}; }}
    QComboBox QAbstractItemView {{
        background: {_CARD_BG}; color: {_TEXT};
        border: 1px solid {_CARD_BORDER}; border-radius: 8px;
        selection-background-color: {_ACCENT2};
    }}
"""
_PROGRESS_STYLE = f"""
    QProgressBar {{
        background: {_CARD_BG}; border: 1px solid {_CARD_BORDER};
        border-radius: 6px; height: 8px; text-align: center;
    }}
    QProgressBar::chunk {{
        background: {_ACCENT2}; border-radius: 6px;
    }}
"""


def _load_catalog() -> dict:
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _page_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color: {_TEXT}; background: transparent;")
    return lbl


def _page_subtitle(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 11))
    lbl.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
    lbl.setWordWrap(True)
    return lbl


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color: {_TEXT_MID}; background: transparent;")
    return lbl


class _ClickCard(QWidget):
    clicked = Signal()

    def __init__(self, title: str, subtitle: str, icon: str = "", parent=None):
        super().__init__(parent)
        self._selected = False
        self.setFixedSize(220, 140)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        if icon:
            ico = QLabel(icon)
            ico.setFont(QFont("Segoe UI Symbol", 22))
            ico.setStyleSheet(f"color: {_ACCENT}; background: transparent;")
            layout.addWidget(ico)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {_TEXT}; background: transparent;")
        layout.addWidget(t)

        s = QLabel(subtitle)
        s.setFont(QFont("Segoe UI", 9))
        s.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        s.setWordWrap(True)
        layout.addWidget(s)

        layout.addStretch()
        self.setStyleSheet(_CARD_STYLE)

    def enterEvent(self, event):
        if not self._selected:
            self.setStyleSheet(_CARD_HOVER_STYLE)

    def leaveEvent(self, event):
        if not self._selected:
            self.setStyleSheet(_CARD_STYLE)

    def mousePressEvent(self, event):
        self.clicked.emit()

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setStyleSheet(_CARD_SELECTED_STYLE if selected else _CARD_STYLE)


# ── Page: Welcome ───────────────────────────────────────────────────────────

class _WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(16)

        logo = QLabel("COMPUTER")
        logo.setFont(QFont("Consolas", 32, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {_ACCENT}; background: transparent;")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        sub = QLabel("Companion Setup")
        sub.setFont(QFont("Segoe UI", 14))
        sub.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(20)

        desc = QLabel(
            "Let's get your AI companion configured.\n"
            "This takes about 2 minutes."
        )
        desc.setFont(QFont("Segoe UI", 11))
        desc.setStyleSheet(f"color: {_TEXT_MID}; background: transparent;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()


# ── Page: Mode Selection ───────────────────────────────────────────────────

class _ModePage(QWidget):
    mode_selected = Signal(str)  # "local", "cloud", "both"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        layout.addWidget(_page_title("How should the AI run?"))
        layout.addWidget(_page_subtitle("Choose what works best for your setup."))
        layout.addSpacing(12)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)
        cards_layout.setAlignment(Qt.AlignCenter)

        self._cards: dict[str, _ClickCard] = {}

        local_card = _ClickCard("Local Models", "Runs on your hardware.\nPrivate, free, offline.", "\u2699")
        cloud_card = _ClickCard("Cloud API", "Powerful cloud models.\nNeeds API key, fast setup.", "\u2601")
        both_card = _ClickCard("Both", "Local primary.\nCloud as fallback.", "\u26A1")

        for card, mode in [(local_card, "local"), (cloud_card, "cloud"), (both_card, "both")]:
            card.clicked.connect(lambda m=mode: self._select(m))
            self._cards[m] = card
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)
        layout.addStretch()

    def _select(self, mode: str):
        for k, card in self._cards.items():
            card.set_selected(k == mode)
        self.mode_selected.emit(mode)


# ── Page: Hardware Scan ────────────────────────────────────────────────────

class _HardwarePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._catalog = _load_catalog()
        self._selected_model = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(10)

        layout.addWidget(_page_title("Your Hardware"))
        layout.addWidget(_page_subtitle("We detected the following system configuration."))
        layout.addSpacing(8)

        self._hw_info = QLabel("Scanning...")
        self._hw_info.setFont(QFont("Consolas", 11))
        self._hw_info.setStyleSheet(f"color: {_TEXT}; background: {_CARD_BG}; border: 1px solid {_CARD_BORDER}; border-radius: 8px; padding: 14px;")
        self._hw_info.setWordWrap(True)
        self._hw_info.setMinimumHeight(80)
        layout.addWidget(self._hw_info)

        layout.addSpacing(8)
        layout.addWidget(_section_label("Recommended Model"))
        self._model_info = QLabel("")
        self._model_info.setFont(QFont("Segoe UI", 11))
        self._model_info.setStyleSheet(f"color: {_TEXT}; background: transparent;")
        self._model_info.setWordWrap(True)
        layout.addWidget(self._model_info)

        layout.addSpacing(4)
        self._model_combo = QComboBox()
        self._model_combo.setStyleSheet(_COMBO_STYLE)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        layout.addWidget(self._model_combo)

        layout.addStretch()

    def load_hardware(self, profile):
        lines = [
            f"GPU:   {profile.gpu_name} ({profile.gpu_vram_mb} MB VRAM)",
            f"RAM:   {profile.ram_gb} GB",
            f"CPU:   {profile.cpu_cores} cores",
            f"CUDA:  {'Yes' if profile.has_cuda else 'No'}",
        ]
        self._hw_info.setText("\n".join(lines))

        models = self._catalog.get("local_models", [])
        compatible = [
            m for m in models
            if profile.gpu_vram_mb >= m["min_vram_mb"] or profile.ram_gb >= m["min_ram_gb"]
        ]
        if not compatible:
            compatible = models[:1]

        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        for m in compatible:
            vision_tag = " + Vision" if m.get("supports_vision") else ""
            self._model_combo.addItem(f"{m['name']}{vision_tag}", m["name"])
        self._model_combo.blockSignals(False)

        if compatible:
            self._select_model(compatible[0])

    def _on_model_changed(self, idx):
        name = self._model_combo.currentData()
        models = self._catalog.get("local_models", [])
        for m in models:
            if m["name"] == name:
                self._select_model(m)
                break

    def _select_model(self, model: dict):
        self._selected_model = model
        vram_req = model["min_vram_mb"]
        vision = "Yes" if model.get("supports_vision") else "No"
        self._model_info.setText(
            f"Download size: ~2-5 GB | VRAM needed: {vram_req} MB | Vision: {vision}"
        )

    def selected_model(self) -> dict | None:
        return self._selected_model


# ── Page: Model Download ──────────────────────────────────────────────────

class _DownloadPage(QWidget):
    download_complete = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)

        layout.addWidget(_page_title("Downloading Model"))
        layout.addWidget(_page_subtitle("This may take a few minutes depending on your connection."))
        layout.addSpacing(12)

        self._status = QLabel("Ready to download")
        self._status.setFont(QFont("Segoe UI", 11))
        self._status.setStyleSheet(f"color: {_TEXT}; background: transparent;")
        layout.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(8)
        self._progress.setStyleSheet(_PROGRESS_STYLE)
        layout.addWidget(self._progress)

        self._detail = QLabel("")
        self._detail.setFont(QFont("Consolas", 9))
        self._detail.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        layout.addWidget(self._detail)

        layout.addStretch()
        self._worker = None

    def start_download(self, model: dict):
        from adapters.model_downloader import DownloadWorker

        dest = DATA_DIR / "models" / model["file"]
        url = model["huggingface_url"]

        self._status.setText(f"Downloading {model['name']}...")
        self._progress.setValue(0)

        self._worker = DownloadWorker(url, dest)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, downloaded, total):
        if total > 0:
            pct = int(downloaded * 100 / total)
            self._progress.setValue(pct)
            mb_dl = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self._detail.setText(f"{mb_dl:.1f} / {mb_total:.1f} MB")

    def _on_finished(self, path):
        self._progress.setValue(100)
        self._status.setText("Download complete!")
        self._status.setStyleSheet(f"color: {_GREEN}; background: transparent;")
        self.download_complete.emit()

    def _on_error(self, msg):
        self._status.setText(f"Download failed: {msg}")
        self._status.setStyleSheet(f"color: {C_RED}; background: transparent;")


# ── Page: Cloud Setup ─────────────────────────────────────────────────────

class _CloudPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._catalog = _load_catalog()
        self._selected_preset = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(10)

        layout.addWidget(_page_title("Cloud API Setup"))
        layout.addWidget(_page_subtitle("Choose a provider and enter your API key."))
        layout.addSpacing(8)

        layout.addWidget(_section_label("Provider"))
        self._provider_combo = QComboBox()
        self._provider_combo.setStyleSheet(_COMBO_STYLE)
        presets = self._catalog.get("cloud_presets", [])
        for p in presets:
            self._provider_combo.addItem(p["name"], p["name"])
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        layout.addWidget(self._provider_combo)

        layout.addSpacing(4)
        layout.addWidget(_section_label("API Key"))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("Enter your API key...")
        self._key_input.setStyleSheet(_INPUT_STYLE)
        layout.addWidget(self._key_input)

        layout.addSpacing(4)
        layout.addWidget(_section_label("Model"))
        self._model_combo = QComboBox()
        self._model_combo.setStyleSheet(_COMBO_STYLE)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        layout.addWidget(self._model_combo)

        layout.addSpacing(4)
        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("Base URL (auto-filled for known providers)")
        self._base_url_input.setStyleSheet(_INPUT_STYLE)
        layout.addWidget(self._base_url_input)

        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setStyleSheet(_BTN_SECONDARY)
        self._test_btn.setFixedWidth(160)
        self._test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self._test_btn)

        self._test_result = QLabel("")
        self._test_result.setFont(QFont("Segoe UI", 10))
        self._test_result.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        self._test_result.setWordWrap(True)
        layout.addWidget(self._test_result)

        layout.addStretch()

        if presets:
            self._on_provider_changed(0)

    def _on_provider_changed(self, idx):
        name = self._provider_combo.currentData()
        presets = self._catalog.get("cloud_presets", [])
        for p in presets:
            if p["name"] == name:
                self._selected_preset = p
                self._base_url_input.setText(p.get("base_url", ""))
                self._model_combo.clear()
                for m in p.get("models", []):
                    vision_tag = " (Vision)" if m.get("supports_vision") else ""
                    self._model_combo.addItem(f"{m['name']}{vision_tag}", m["model_id"])
                if not p.get("models"):
                    self._model_combo.addItem("Custom model...", "")
                break

    def _on_model_changed(self, idx):
        pass

    def _test_connection(self):
        self._test_result.setText("Testing...")
        self._test_result.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        self._test_btn.setEnabled(False)
        QTimer.singleShot(100, self._do_test)

    def _do_test(self):
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=self._base_url_input.text().rstrip("/") + "/v1",
                api_key=self._key_input.text() or "none",
            )
            models = client.models.list()
            ids = [m.id for m in models.data][:5]
            self._test_result.setText(f"Connected! Models: {', '.join(ids)}")
            self._test_result.setStyleSheet(f"color: {_GREEN}; background: transparent;")
        except Exception as e:
            self._test_result.setText(f"Failed: {e}")
            self._test_result.setStyleSheet(f"color: {C_RED}; background: transparent;")
        finally:
            self._test_btn.setEnabled(True)

    def selected_config(self) -> dict:
        preset = self._selected_preset or {}
        model_id = self._model_combo.currentData() or ""
        return {
            "provider": preset.get("name", "Custom"),
            "base_url": self._base_url_input.text(),
            "api_key_ref": preset.get("keyring_ref", ""),
            "api_key": self._key_input.text(),
            "model": model_id,
        }


# ── Page: Voice Setup ─────────────────────────────────────────────────────

class _VoicePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(10)

        layout.addWidget(_page_title("Voice Setup"))
        layout.addWidget(_page_subtitle("Configure speech recognition and text-to-speech."))
        layout.addSpacing(8)

        layout.addWidget(_section_label("Speech Recognition (Whisper)"))
        self._whisper_model = QComboBox()
        self._whisper_model.setStyleSheet(_COMBO_STYLE)
        self._whisper_model.addItems(["tiny", "base", "small", "medium", "large"])
        self._whisper_model.setCurrentText("medium")
        layout.addWidget(self._whisper_model)

        self._whisper_device = QComboBox()
        self._whisper_device.setStyleSheet(_COMBO_STYLE)
        self._whisper_device.addItems(["cuda", "cpu"])
        layout.addWidget(self._whisper_device)

        layout.addSpacing(8)
        layout.addWidget(_section_label("Text-to-Speech"))
        self._tts_engine = QComboBox()
        self._tts_engine.setStyleSheet(_COMBO_STYLE)
        self._tts_engine.addItems(["piper", "kokoro", "chatterbox", "pyttsx3"])
        layout.addWidget(self._tts_engine)

        layout.addStretch()

    def selected_config(self) -> dict:
        return {
            "whisper_model": self._whisper_model.currentText(),
            "whisper_device": self._whisper_device.currentText(),
            "tts_engine": self._tts_engine.currentText(),
        }


# ── Page: About You ──────────────────────────────────────────────────────

class _UserPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(10)

        layout.addWidget(_page_title("About You"))
        layout.addWidget(_page_subtitle("Help the companion give you location-aware answers."))
        layout.addSpacing(8)

        self._fields: dict[str, QLineEdit] = {}
        fields = [
            ("City", "city", "Your city"),
            ("Country", "country", "Your country"),
            ("Timezone", "timezone", "e.g. America/New_York"),
            ("Language", "language", "English"),
            ("Currency", "currency", "USD"),
        ]
        for label, key, placeholder in fields:
            layout.addWidget(_section_label(label))
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setStyleSheet(_INPUT_STYLE)
            self._fields[key] = inp
            layout.addWidget(inp)

        layout.addStretch()

    def selected_config(self) -> dict:
        return {k: inp.text() for k, inp in self._fields.items()}


# ── Page: Summary ─────────────────────────────────────────────────────────

class _SummaryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(10)

        layout.addWidget(_page_title("Ready to Go"))
        layout.addWidget(_page_subtitle("Here's what we configured:"))
        layout.addSpacing(12)

        self._summary = QLabel("")
        self._summary.setFont(QFont("Consolas", 11))
        self._summary.setStyleSheet(f"color: {_TEXT}; background: {_CARD_BG}; border: 1px solid {_CARD_BORDER}; border-radius: 8px; padding: 14px;")
        self._summary.setWordWrap(True)
        self._summary.setMinimumHeight(120)
        layout.addWidget(self._summary)

        layout.addStretch()

    def set_summary(self, text: str):
        self._summary.setText(text)


# ── Main Wizard ──────────────────────────────────────────────────────────

class SetupWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("COMPUTER // Setup")
        self.setMinimumSize(700, 520)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{ background: {_WIZARD_BG}; color: {_TEXT};
                       font-family: 'Segoe UI', Consolas; font-size: 12px; }}
            QLabel {{ background: transparent; }}
            QScrollArea {{ border: none; background: transparent; }}
        """)

        self._mode = "local"
        self._hw = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # Build pages
        self._welcome = _WelcomePage()
        self._mode_page = _ModePage()
        self._hw_page = _HardwarePage()
        self._dl_page = _DownloadPage()
        self._cloud_page = _CloudPage()
        self._voice_page = _VoicePage()
        self._user_page = _UserPage()
        self._summary_page = _SummaryPage()

        self._stack.addWidget(self._welcome)
        self._stack.addWidget(self._mode_page)
        self._stack.addWidget(self._hw_page)
        self._stack.addWidget(self._dl_page)
        self._stack.addWidget(self._cloud_page)
        self._stack.addWidget(self._voice_page)
        self._stack.addWidget(self._user_page)
        self._stack.addWidget(self._summary_page)

        self._mode_page.mode_selected.connect(self._on_mode_selected)
        self._dl_page.download_complete.connect(self._on_download_done)

        # Navigation bar
        nav = QWidget()
        nav.setFixedHeight(60)
        nav.setStyleSheet(f"background: {_CARD_BG}; border-top: 1px solid {_CARD_BORDER};")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(24, 0, 24, 0)

        self._back_btn = QPushButton("Back")
        self._back_btn.setStyleSheet(_BTN_SECONDARY)
        self._back_btn.clicked.connect(self._go_back)
        self._back_btn.hide()

        self._next_btn = QPushButton("Get Started")
        self._next_btn.setStyleSheet(_BTN_PRIMARY)
        self._next_btn.clicked.connect(self._go_next)

        nav_layout.addWidget(self._back_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self._next_btn)
        root.addWidget(nav)

        self._page_index = 0
        self._page_order = [0, 1]  # welcome, mode; rest added dynamically

    def _on_mode_selected(self, mode: str):
        self._mode = mode

    def _go_next(self):
        idx = self._stack.currentIndex()

        if idx == 0:  # Welcome -> Mode
            self._stack.setCurrentIndex(1)

        elif idx == 1:  # Mode -> next page
            if self._mode in ("local", "both"):
                from adapters.hardware import detect_hardware
                self._hw = detect_hardware()
                self._hw_page.load_hardware(self._hw)
                self._stack.setCurrentIndex(2)
            elif self._mode == "cloud":
                self._stack.setCurrentIndex(4)

        elif idx == 2:  # Hardware -> Download
            model = self._hw_page.selected_model()
            if model:
                self._dl_page.start_download(model)
                self._stack.setCurrentIndex(3)
            else:
                self._stack.setCurrentIndex(3)

        elif idx == 3:  # Download done -> next
            if self._mode == "both":
                self._stack.setCurrentIndex(4)
            else:
                self._stack.setCurrentIndex(5)

        elif idx == 4:  # Cloud -> Voice
            self._stack.setCurrentIndex(5)

        elif idx == 5:  # Voice -> User
            self._stack.setCurrentIndex(6)

        elif idx == 6:  # User -> Summary
            self._update_summary()
            self._stack.setCurrentIndex(7)
            self._next_btn.setText("Launch COMPUTER")

        elif idx == 7:  # Summary -> Finish
            self._finish()

        self._update_nav()

    def _go_back(self):
        idx = self._stack.currentIndex()

        if idx == 1:
            self._stack.setCurrentIndex(0)
        elif idx == 2:
            self._stack.setCurrentIndex(1)
        elif idx == 3:
            self._stack.setCurrentIndex(2)
        elif idx == 4:
            if self._mode in ("local", "both"):
                self._stack.setCurrentIndex(2)
            else:
                self._stack.setCurrentIndex(1)
        elif idx == 5:
            if self._mode == "cloud":
                self._stack.setCurrentIndex(4)
            else:
                self._stack.setCurrentIndex(2)
        elif idx == 6:
            self._stack.setCurrentIndex(5)
        elif idx == 7:
            self._stack.setCurrentIndex(6)

        self._update_nav()

    def _update_nav(self):
        idx = self._stack.currentIndex()
        self._back_btn.setVisible(idx > 0)
        self._next_btn.setText(
            "Launch COMPUTER" if idx == 7 else
            "Get Started" if idx == 0 else
            "Next"
        )

    def _on_download_done(self):
        if self._mode == "both":
            self._stack.setCurrentIndex(4)
        else:
            self._stack.setCurrentIndex(5)
        self._update_nav()

    def _update_summary(self):
        lines = []
        if self._mode in ("local", "both"):
            hw = self._hw
            if hw:
                lines.append(f"Hardware: {hw.gpu_name}, {hw.ram_gb}GB RAM, {hw.cpu_cores} cores")
            model = self._hw_page.selected_model()
            if model:
                lines.append(f"Local model: {model['name']}")

        if self._mode in ("cloud", "both"):
            ccfg = self._cloud_page.selected_config()
            if ccfg.get("provider"):
                lines.append(f"Cloud: {ccfg['provider']} ({ccfg.get('model', 'N/A')})")

        voice = self._voice_page.selected_config()
        lines.append(f"Voice: {voice['tts_engine']} TTS, Whisper {voice['whisper_model']}")

        user = self._user_page.selected_config()
        loc = f"{user.get('city', '')}, {user.get('country', '')}".strip(", ")
        if loc:
            lines.append(f"Location: {loc}")

        self._summary_page.set_summary("\n".join(lines))

    def _finish(self):
        raw = yaml.safe_load(open(CONFIG_EXAMPLE, encoding="utf-8")) or {}
        llm = raw.setdefault("llm", {})

        if self._mode in ("local", "both"):
            llm["backend"] = "llama"
            model = self._hw_page.selected_model()
            if model:
                llm["model"] = model["file"]

        if self._mode in ("cloud", "both"):
            if self._mode == "cloud":
                llm["backend"] = "cloud"
            ccfg = self._cloud_page.selected_config()
            llm.setdefault("cloud", {})
            llm["cloud"]["provider"] = ccfg.get("provider", "custom")
            llm["cloud"]["base_url"] = ccfg.get("base_url", "")
            llm["cloud"]["api_key_ref"] = ccfg.get("api_key_ref", "")
            llm["cloud"]["model"] = ccfg.get("model", "")

            api_key = ccfg.get("api_key", "")
            key_ref = ccfg.get("api_key_ref", "")
            if api_key and key_ref:
                from security.keyring_store import store_key
                store_key(key_ref, api_key)

        voice = self._voice_page.selected_config()
        speech = raw.setdefault("speech", {})
        speech["whisper_model"] = voice["whisper_model"]
        speech["whisper_device"] = voice["whisper_device"]
        tts = raw.setdefault("tts", {})
        tts["engine"] = voice["tts_engine"]

        user = self._user_page.selected_config()
        raw["user"] = user

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(raw, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETUP_MARKER.write_text("done", encoding="utf-8")

        self.accept()
