"""
config/loader.py - Unified config + personality loader
"""
import threading
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent
CONFIG_PATH = CONFIG_DIR / "config.yaml"
CONFIG_EXAMPLE = CONFIG_DIR / "config.example.yaml"
BASE_DIR = Path(__file__).parent.parent


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else BASE_DIR / p


def load_raw() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE
    with open(path) as f:
        return yaml.safe_load(f)


def load_personality(config: dict) -> dict:
    pf = _resolve(config.get("personality_file", "config/personality.yaml"))
    with open(pf) as f:
        return yaml.safe_load(f)


class Config:
    """Flat config accessor with dot notation."""
    def __init__(self):
        self._raw = load_raw()
        self._personality = load_personality(self._raw)
        self._resolve_paths()

    def _resolve_paths(self):
        self._raw["memory"]["db_path"] = str(_resolve(self._raw["memory"]["db_path"]))
        self._raw["tools"]["screenshot_temp_path"] = str(
            _resolve(self._raw["tools"]["screenshot_temp_path"])
        )
        browser = self._raw.get("browser", {})
        if browser.get("screenshot_path"):
            browser["screenshot_path"] = str(_resolve(browser["screenshot_path"]))

    # --- LLM ---
    @property
    def llm_backend(self) -> str:
        return self._raw["llm"]["backend"]

    @property
    def llm_base_url(self) -> str:
        if self._raw["llm"]["backend"] == "lmstudio":
            return self._raw["llm"]["lmstudio_base_url"]
        return self._raw["llm"]["ollama_base_url"]

    @property
    def llm_model(self) -> str:
        return self._raw["llm"]["model"]

    @property
    def llm_temperature(self) -> float:
        return self._raw["llm"]["temperature"]

    @property
    def llm_max_tokens(self) -> int:
        return self._raw["llm"]["max_tokens"]

    @property
    def llm_max_tokens_brainstorm(self) -> int:
        return int(self._raw["llm"].get("max_tokens_brainstorm", self._raw["llm"]["max_tokens"]))

    @property
    def llm_stream(self) -> bool:
        return self._raw["llm"]["stream"]

    @property
    def llm_context_window(self) -> int:
        return self._raw["llm"]["context_window"]

    # --- llama.cpp ---
    @property
    def llama_model_path(self) -> str:
        return self._raw["llm"].get("llama_model_path", "")

    @property
    def llama_n_gpu_layers(self) -> int:
        return int(self._raw["llm"].get("llama_n_gpu_layers", -1))

    @property
    def llama_port(self) -> int:
        return int(self._raw["llm"].get("llama_port", 8012))

    @property
    def llama_host(self) -> str:
        return self._raw["llm"].get("llama_host", "127.0.0.1")

    @property
    def llama_chat_format(self) -> str:
        return self._raw["llm"].get("llama_chat_format", "")

    @property
    def llama_ctx_size(self) -> int:
        return int(self._raw["llm"].get("llama_ctx_size", 4096))

    @property
    def llama_startup_timeout(self) -> int:
        return int(self._raw["llm"].get("llama_startup_timeout", 120))

    @property
    def llama_mmproj_auto(self) -> bool:
        return bool(self._raw["llm"].get("llama_mmproj_auto", True))

    @property
    def llama_image_max_tokens(self) -> int:
        return int(self._raw["llm"].get("llama_image_max_tokens", 2048))

    # --- Speech ---
    @property
    def whisper_model(self) -> str:
        return self._raw["speech"]["whisper_model"]

    @property
    def whisper_device(self) -> str:
        return self._raw["speech"]["whisper_device"]

    @property
    def whisper_compute_type(self) -> str:
        return self._raw["speech"]["whisper_compute_type"]

    @property
    def sample_rate(self) -> int:
        return self._raw["speech"]["sample_rate"]

    @property
    def push_to_talk_key(self) -> str:
        return self._raw["speech"]["push_to_talk_key"]

    @property
    def silence_threshold(self) -> float:
        return self._raw["speech"]["silence_threshold"]

    @property
    def silence_duration(self) -> float:
        return self._raw["speech"]["silence_duration"]

    # --- TTS ---
    @property
    def tts_engine(self) -> str:
        return self._raw["tts"]["engine"]

    @property
    def chatterbox_python(self) -> str:
        value = self._raw["tts"].get("chatterbox_python", "")
        return str(_resolve(value)) if value else ""

    @property
    def chatterbox_model(self) -> str:
        return self._raw["tts"].get("chatterbox_model", "turbo")

    @property
    def chatterbox_device(self) -> str:
        return self._raw["tts"].get("chatterbox_device", "auto")

    @property
    def chatterbox_voice_prompt(self) -> str:
        value = self._raw["tts"].get("chatterbox_voice_prompt", "")
        return str(_resolve(value)) if value else ""

    @property
    def chatterbox_exaggeration(self) -> float:
        return float(self._raw["tts"].get("chatterbox_exaggeration", 0.15))

    @property
    def chatterbox_cfg_weight(self) -> float:
        return float(self._raw["tts"].get("chatterbox_cfg_weight", 0.0))

    @property
    def chatterbox_temperature(self) -> float:
        return float(self._raw["tts"].get("chatterbox_temperature", 0.8))

    @property
    def min_sentence_chars(self) -> int:
        return int(self._raw["tts"].get("min_sentence_chars", 1))

    @property
    def piper_exe(self) -> str:
        value = self._raw["tts"].get("piper_exe", "")
        return str(_resolve(value)) if value else ""

    @property
    def piper_model(self) -> str:
        value = self._raw["tts"].get("piper_model", "")
        return str(_resolve(value)) if value else ""

    @property
    def piper_config(self) -> str:
        value = self._raw["tts"].get("piper_config", "")
        return str(_resolve(value)) if value else ""

    @property
    def piper_speaker(self):
        return self._raw["tts"].get("piper_speaker")

    @property
    def piper_length_scale(self) -> float:
        return float(self._raw["tts"].get("piper_length_scale", 1.0))

    @property
    def kokoro_voice(self) -> str:
        return self._raw["tts"]["kokoro_voice"]

    @property
    def kokoro_speed(self) -> float:
        return self._raw["tts"]["kokoro_speed"]

    @property
    def tts_stream_chunk(self) -> int:
        return self._raw["tts"]["stream_chunk_size"]

    # --- Memory ---
    @property
    def db_path(self) -> str:
        return self._raw["memory"]["db_path"]

    @property
    def max_context_memories(self) -> int:
        return self._raw["memory"]["max_context_memories"]

    @property
    def summary_threshold(self) -> int:
        return self._raw["memory"]["summary_threshold"]

    @property
    def session_persistence(self) -> bool:
        return self._raw["memory"].get("session_persistence", True)

    # --- Context ---
    @property
    def track_active_window(self) -> bool:
        return self._raw.get("context", {}).get("track_active_window", True)

    @property
    def window_poll_interval_ms(self) -> int:
        return int(self._raw.get("context", {}).get("window_poll_interval_ms", 1000))

    @property
    def show_in_prompt(self) -> bool:
        return self._raw.get("context", {}).get("show_in_prompt", True)

    @property
    def persist_window_context(self) -> bool:
        return self._raw.get("context", {}).get("persist_window_context", True)

    # --- Tools ---
    @property
    def require_confirmation(self) -> bool:
        return self._raw["tools"]["require_confirmation"]

    @property
    def screenshot_hotkey(self) -> str:
        return self._raw["tools"]["screenshot_hotkey"]

    @property
    def screenshot_path(self) -> str:
        return self._raw["tools"]["screenshot_temp_path"]

    # --- Search ---
    @property
    def search_searxng_url(self) -> str:
        return self._raw.get("search", {}).get("searxng_url", "")

    # --- Browser ---
    @property
    def browser_enabled(self) -> bool:
        return bool(self._raw.get("browser", {}).get("enabled", False))

    @property
    def browser_headless(self) -> bool:
        return bool(self._raw.get("browser", {}).get("headless", True))

    @property
    def browser_screenshot_path(self) -> str:
        return self._raw.get("browser", {}).get("screenshot_path", "data/browser_screenshot.png")

    # --- UI ---
    @property
    def window_title(self) -> str:
        return self._raw["ui"]["window_title"]

    @property
    def window_size(self) -> tuple:
        return self._raw["ui"]["window_width"], self._raw["ui"]["window_height"]

    @property
    def font_family(self) -> str:
        return self._raw["ui"]["font_family"]

    @property
    def font_size(self) -> int:
        return self._raw["ui"]["font_size"]

    @property
    def max_history_display(self) -> int:
        return self._raw["ui"]["max_history_display"]

    @property
    def pet_enabled(self) -> bool:
        return bool(self._raw.get("ui", {}).get("pet_enabled", True))

    # --- Personality ---
    @property
    def persona_name(self) -> str:
        return self._personality["name"]

    @property
    def system_prompt(self) -> str:
        return self._personality["system_prompt"]

    @property
    def personality(self) -> dict:
        return self._personality

    @property
    def user_context(self) -> dict:
        return self._raw.get("user", {})

    def reload(self):
        self._raw = load_raw()
        self._personality = load_personality(self._raw)
        self._resolve_paths()


# Singleton
_cfg: Config | None = None
_cfg_lock = threading.Lock()

def get_config() -> Config:
    global _cfg
    if _cfg is None:
        with _cfg_lock:
            if _cfg is None:
                _cfg = Config()
    return _cfg
