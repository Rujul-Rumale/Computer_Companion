"""
audio/tts.py - Local TTS engines with sentence-level streaming.
"""
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from config import get_config

_tts_lock = threading.Lock()
_SENTENCE_BOUNDARIES = ".!?\n"
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "\U0001F900-\U0001F9FF"
    "]+",
    flags=re.UNICODE,
)
_EMOJI_MODIFIER_RE = re.compile("[\ufe0f\u200d]")
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MARKDOWN_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_MARKDOWN_RE = re.compile(r"[*_`~#>]+")
_BRACKETED_RE = re.compile(r"\[(?:TOOL|executed):.*?\]")


def strip_for_speech(text: str) -> str:
    """Remove text that should be shown but not spoken."""
    text = _MARKDOWN_RE.sub(" ", text or "")
    text = _BRACKETED_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _INLINE_MARKDOWN_RE.sub(" ", text)
    text = _EMOJI_RE.sub("", text)
    text = _EMOJI_MODIFIER_RE.sub("", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _pop_complete_sentence(buffer: str) -> tuple[str | None, str]:
    """Return the first completed sentence and remaining buffer."""
    for i, ch in enumerate(buffer):
        if ch not in _SENTENCE_BOUNDARIES:
            continue
        # Skip periods in decimal numbers (e.g., 3.14, 0.5)
        if ch == '.' and i > 0 and buffer[i-1].isdigit() and i + 1 < len(buffer) and buffer[i+1].isdigit():
            continue

        end = i + 1
        while end < len(buffer) and buffer[end] in "\"')]} ":
            end += 1

        sentence = strip_for_speech(buffer[:end])
        rest = buffer[end:]
        return (sentence if sentence else None), rest

    return None, buffer


def _split_into_chunks(text: str, words_per_chunk: int) -> list[str]:
    """Split text into speakable chunks at sentence/clause boundaries."""
    # Split on sentence endings first
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = []
    word_count = 0
    for sent in sentences:
        words = sent.split()
        if word_count + len(words) > words_per_chunk and current:
            chunks.append(" ".join(current))
            current = words
            word_count = len(words)
        else:
            current.extend(words)
            word_count += len(words)
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if c.strip()]


class KokoroTTS:
    def __init__(self):
        self._pipeline = None
        self._stop_event = threading.Event()
        self._speak_thread: threading.Thread | None = None
        self.on_speaking: Callable[[bool], None] | None = None
        self._loaded = False
        self._speed_override: float | None = None
        self._speaking_fired = False

    def set_speed(self, rate: float):
        self._speed_override = max(0.25, min(4.0, rate))

    def load(self) -> bool:
        try:
            from kokoro import KPipeline
            self._pipeline = KPipeline(lang_code="a")
            self._loaded = True
            print("[TTS] Kokoro loaded.")
            return True
        except ImportError:
            print("[TTS] Kokoro not found.")
            return False
        except Exception as e:
            print(f"[TTS] Kokoro init failed: {e}")
            return False

    def interrupt(self):
        self._stop_event.set()

    def speak(self, text: str):
        """Speak text. Interrupts any ongoing speech."""
        self.interrupt()
        self._stop_event = threading.Event()
        self._speak_thread = threading.Thread(
            target=self._speak_worker, args=(text,), daemon=True
        )
        self._speak_thread.start()

    def speak_streaming(self, token_queue: "queue.Queue[str | None]"):
        """
        Consumes tokens from a queue (None = done), speaks in chunks.
        token_queue: put tokens as they arrive, put None when finished.
        """
        self.interrupt()
        self._stop_event = threading.Event()
        self._speak_thread = threading.Thread(
            target=self._stream_worker, args=(token_queue,), daemon=True
        )
        self._speak_thread.start()

    def _stream_worker(self, token_queue: "queue.Queue[str | None]"):
        cfg = get_config()
        self._speaking_fired = False
        speech_queue: queue.Queue[str | None] = queue.Queue()

        def _speaker():
            while not self._stop_event.is_set():
                try:
                    sentence = speech_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if sentence is None:
                    break
                self._speak_chunk(sentence)

        speaker_thread = threading.Thread(target=_speaker, daemon=True)
        speaker_thread.start()
        buffer = ""
        pending_sentence = ""
        try:
            while not self._stop_event.is_set():
                try:
                    token = token_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if token is None:
                    break
                buffer += token
                while True:
                    sentence, buffer = _pop_complete_sentence(buffer)
                    if not sentence:
                        break
                    pending_sentence = f"{pending_sentence} {sentence}" if pending_sentence else sentence
                    if len(pending_sentence) >= cfg.min_sentence_chars:
                        speech_queue.put(pending_sentence)
                        pending_sentence = ""

                words = buffer.split()
                if len(words) >= cfg.tts_stream_chunk:
                    chunk = strip_for_speech(buffer)
                    if chunk:
                        if pending_sentence:
                            chunk = f"{pending_sentence} {chunk}"
                            pending_sentence = ""
                        speech_queue.put(chunk)
                    buffer = ""
            # Speak remainder
            if pending_sentence and not self._stop_event.is_set():
                speech_queue.put(pending_sentence)
            if buffer.strip() and not self._stop_event.is_set():
                remainder = strip_for_speech(buffer)
                if remainder:
                    speech_queue.put(remainder)
        finally:
            speech_queue.put(None)
            speaker_thread.join(timeout=300.0)
            if self.on_speaking:
                self.on_speaking(False)

    def _speak_worker(self, text: str):
        cfg = get_config()
        self._speaking_fired = False
        try:
            chunks = _split_into_chunks(strip_for_speech(text), cfg.tts_stream_chunk)
            for chunk in chunks:
                if self._stop_event.is_set():
                    break
                self._speak_chunk(chunk)
        finally:
            if self.on_speaking:
                self.on_speaking(False)

    def _speak_chunk(self, text: str):
        text = strip_for_speech(text)
        if not text or self._stop_event.is_set():
            return
        cfg = get_config()
        try:
            if self._loaded and self._pipeline:
                import sounddevice as sd
                generator = self._pipeline(
                    text,
                    voice=cfg.kokoro_voice,
                    speed=self._speed_override if self._speed_override is not None else cfg.kokoro_speed,
                    split_pattern=None,
                )
                for _, _, audio in generator:
                    if self._stop_event.is_set():
                        break
                    if audio is not None and len(audio) > 0:
                        if self.on_speaking and not self._speaking_fired:
                            self._speaking_fired = True
                            self.on_speaking(True)
                        sd.play(audio, samplerate=24000, blocking=False)
                        # Wait for audio to finish, checking for interrupt
                        duration = len(audio) / 24000
                        steps = int(duration / 0.05) + 1
                        for _ in range(steps):
                            if self._stop_event.is_set():
                                sd.stop()
                                return
                            time.sleep(0.05)
                        sd.wait()
            else:
                self._silent_fallback(text)
        except Exception as e:
            print(f"[TTS] Chunk error: {e}")
            from contextlib import suppress
            with suppress(Exception):
                self._silent_fallback(text)

    def _silent_fallback(self, text: str):
        if text:
            print(f"[TTS] No local speech engine available for: {text[:80]}")

    def is_speaking(self) -> bool:
        return self._speak_thread is not None and self._speak_thread.is_alive()


class PiperTTS(KokoroTTS):
    def __init__(self):
        super().__init__()
        self._exe = ""
        self._model = ""
        self._config = ""

    def load(self) -> bool:
        cfg = get_config()
        local_exe = Path(__file__).resolve().parent.parent / "data" / "piper" / "piper.exe"
        exe = ""
        # 1) explicit config path
        if cfg.piper_exe:
            exe = cfg.piper_exe
        # 2) environment override from launcher
        if not exe:
            exe = os.environ.get("PIPER_EXE", "")
        # 3) on PATH
        if not exe:
            which_exe = shutil.which("piper") or shutil.which("piper.exe")
            exe = which_exe or ""
        # 4) direct local path
        if not exe and local_exe.exists():
            exe = str(local_exe)
        # 5) recursive search under data/piper (handles nested zip layout)
        if not exe:
            piper_dir = Path(__file__).resolve().parent.parent / "data" / "piper"
            if piper_dir.exists():
                found = list(piper_dir.rglob("piper.exe"))
                if found:
                    exe = str(found[0])
        model = cfg.piper_model
        model_path = Path(model) if model else None
        if not exe or not Path(exe).exists():
            print(f"[TTS] Piper not found (tried: {exe}).")
            return False
        if not model_path or not model_path.exists():
            print(f"[TTS] Piper voice model not found: {model}")
            print("[TTS] Set tts.piper_model in config.yaml.")
            return False

        config = cfg.piper_config
        if not config:
            inferred = model_path.with_suffix(model_path.suffix + ".json")
            config = str(inferred) if inferred.exists() else ""

        self._exe = exe
        self._model = str(model_path)
        self._config = config
        self._loaded = True
        print(f"[TTS] Piper loaded: {model_path.name}")
        return True

    def _speak_chunk(self, text: str):
        text = strip_for_speech(text)
        if not text or self._stop_event.is_set():
            return
        if not self._loaded:
            self._silent_fallback(text)
            return

        if self.on_speaking and not self._speaking_fired:
            self._speaking_fired = True
            self.on_speaking(True)

        try:
            self._piper_speak(text)
        except Exception as e:
            print(f"[TTS/Piper] {e}")
            self._silent_fallback(text)

    def _piper_speak(self, text: str):
        cfg = get_config()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name

        cmd = [
            self._exe,
            "--model", self._model,
            "--output_file", wav_path,
        ]
        if self._config:
            cmd.extend(["--config", self._config])
        if cfg.piper_speaker is not None:
            cmd.extend(["--speaker", str(cfg.piper_speaker)])
        if cfg.piper_length_scale != 1.0:
            cmd.extend(["--length_scale", str(cfg.piper_length_scale)])
        elif self._speed_override is not None:
            length_scale = 1.0 / self._speed_override
            cmd.extend(["--length_scale", f"{length_scale:.2f}"])

        try:
            proc = subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
                timeout=45,
            )
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(detail or f"piper exited with {proc.returncode}")
            self._play_wav(wav_path)
        finally:
            from contextlib import suppress
            with suppress(OSError):
                os.remove(wav_path)

    def _play_wav(self, path: str):
        import sounddevice as sd
        import soundfile as sf

        audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)

        sd.play(audio, samplerate=sample_rate, blocking=False)
        duration = len(audio) / sample_rate
        steps = int(duration / 0.05) + 1
        for _ in range(steps):
            if self._stop_event.is_set():
                sd.stop()
                return
            time.sleep(0.05)
        sd.wait()


class ChatterboxTTS(PiperTTS):
    def __init__(self):
        super().__init__()
        self._python = ""
        self._worker_script = ""
        self._worker: subprocess.Popen | None = None

    def load(self) -> bool:
        cfg = get_config()
        python_path = Path(cfg.chatterbox_python)
        worker_script = Path(__file__).with_name("chatterbox_worker.py")

        if not python_path.exists():
            print(f"[TTS] Chatterbox Python not found: {python_path}")
            print("[TTS] No speech engine available.")
            return False
        if not worker_script.exists():
            print(f"[TTS] Chatterbox worker not found: {worker_script}")
            print("[TTS] No speech engine available.")
            return False

        self._python = str(python_path)
        self._worker_script = str(worker_script)
        self._loaded = True
        print("[TTS] Chatterbox configured.")
        return True

    def interrupt(self):
        super().interrupt()
        self._stop_worker()

    def _speak_chunk(self, text: str):
        text = strip_for_speech(text)
        if not text or self._stop_event.is_set():
            return
        if not self._loaded:
            self._silent_fallback(text)
            return

        if self.on_speaking and not self._speaking_fired:
            self._speaking_fired = True
            self.on_speaking(True)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        try:
            self._chatterbox_speak(text, wav_path)
            self._play_wav(wav_path)
        except Exception as e:
            print(f"[TTS/Chatterbox] {e}")
            self._silent_fallback(text)
        finally:
            from contextlib import suppress
            with suppress(OSError):
                os.remove(wav_path)

    def _chatterbox_speak(self, text: str, wav_path: str):
        worker = self._ensure_worker()
        cfg = get_config()
        request = {
            "text": text,
            "output": wav_path,
            "voice_prompt": cfg.chatterbox_voice_prompt,
            "exaggeration": cfg.chatterbox_exaggeration,
            "cfg_weight": cfg.chatterbox_cfg_weight,
            "temperature": cfg.chatterbox_temperature,
        }
        assert worker.stdin is not None
        assert worker.stdout is not None
        worker.stdin.write(json.dumps(request) + "\n")
        worker.stdin.flush()
        response = worker.stdout.readline()
        if not response:
            self._stop_worker()
            raise RuntimeError("worker exited before returning audio")

        payload = json.loads(response)
        if not payload.get("ok"):
            raise RuntimeError(payload.get("error", "worker failed"))

    def _ensure_worker(self) -> subprocess.Popen:
        if self._worker and self._worker.poll() is None:
            return self._worker

        cfg = get_config()
        env = os.environ.copy()
        root = Path(__file__).resolve().parent.parent
        cache_dir = root / "data" / "hf_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        env["HF_HOME"] = str(cache_dir)
        env["TRANSFORMERS_CACHE"] = str(cache_dir / "transformers")
        env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        env["DISABLE_TQDM"] = "1"

        cmd = [
            self._python,
            self._worker_script,
            "--model", cfg.chatterbox_model,
            "--device", cfg.chatterbox_device,
            "--exaggeration", str(cfg.chatterbox_exaggeration),
            "--cfg-weight", str(cfg.chatterbox_cfg_weight),
            "--temperature", str(cfg.chatterbox_temperature),
        ]
        if cfg.chatterbox_voice_prompt:
            cmd.extend(["--voice-prompt", cfg.chatterbox_voice_prompt])

        self._worker = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        return self._worker

    def _stop_worker(self):
        worker = self._worker
        self._worker = None
        if not worker:
            return
        try:
            if worker.poll() is None and worker.stdin:
                worker.stdin.write(json.dumps({"command": "stop"}) + "\n")
                worker.stdin.flush()
                worker.wait(timeout=2.0)
        except Exception:
            from contextlib import suppress
            with suppress(Exception):
                worker.terminate()


class TTSManager:
    """Singleton TTS manager. Selects engine from config."""
    def __init__(self):
        cfg = get_config()
        engine_map = {
            "kokoro": KokoroTTS,
            "piper": PiperTTS,
            "chatterbox": ChatterboxTTS,
        }
        cls = engine_map.get(cfg.tts_engine, PiperTTS)
        self._engine = cls()
        self._loaded = False
        self._loaded = self._engine.load()
        self.on_speaking = None

    def set_speaking_callback(self, cb: Callable[[bool], None]):
        self._engine.on_speaking = cb

    def set_speed(self, rate: float):
        self._engine.set_speed(rate)

    def speak(self, text: str):
        self._engine.speak(text)

    def speak_streaming(self, token_queue: "queue.Queue[str | None]"):
        self._engine.speak_streaming(token_queue)

    def interrupt(self):
        self._engine.interrupt()

    def is_speaking(self) -> bool:
        return self._engine.is_speaking()
