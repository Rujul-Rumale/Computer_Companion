"""
audio/stt.py - Faster-Whisper STT with push-to-talk
"""
import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from config import get_config

_whisper_model = None
_model_lock = threading.Lock()

# ── Audio pre-processing ─────────────────────────────────────────────────


def _highpass_filter(audio: np.ndarray, sr: int, cutoff: int = 80) -> np.ndarray:
    """Simple first-order high-pass filter to remove low-frequency rumble."""
    rc = 1.0 / (2.0 * np.pi * cutoff)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    filtered = np.zeros_like(audio)
    filtered[0] = audio[0]
    for i in range(1, len(audio)):
        filtered[i] = alpha * (filtered[i - 1] + audio[i] - audio[i - 1])
    return filtered


def _normalize_audio(audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
    """Peak-normalize audio so the loudest sample hits target_peak."""
    peak = np.max(np.abs(audio))
    if peak < 1e-10:
        return audio
    return audio * (target_peak / peak)


def _preprocess_audio(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Apply noise reduction, high-pass filter, and normalization."""
    try:
        import noisereduce as nr
        audio = nr.reduce_noise(y=audio, sr=sr, stationary=False, prop_decrease=0.85)
    except ImportError:
        pass
    audio = _highpass_filter(audio, sr, cutoff=80)
    audio = _normalize_audio(audio, target_peak=0.9)
    return audio


def _resolve_whisper_runtime(device: str, compute_type: str) -> tuple[str, str]:
    """Choose a supported faster-whisper runtime, preferring the configured one."""
    device = (device or "cpu").lower()
    compute_type = compute_type or "float32"

    try:
        import ctranslate2
        if device == "cuda" and ctranslate2.get_cuda_device_count() < 1:
            print("[STT] CUDA requested but no CUDA device was detected; falling back to CPU.")
            device = "cpu"

        supported = ctranslate2.get_supported_compute_types(device)
        if compute_type not in supported:
            fallback = "float32" if "float32" in supported else sorted(supported)[0]
            print(
                f"[STT] {device} does not support compute_type={compute_type}; "
                f"using {fallback}."
            )
            compute_type = fallback
    except Exception as e:
        print(f"[STT] Could not inspect CTranslate2 runtime support: {e}")
        if device == "cpu" and compute_type == "float16":
            compute_type = "float32"

    return device, compute_type


def load_whisper():
    """Lazy-load whisper. Call once at startup."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    cfg = get_config()
    with _model_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            device, compute_type = _resolve_whisper_runtime(
                cfg.whisper_device,
                cfg.whisper_compute_type,
            )
            print(f"[STT] Loading Whisper '{cfg.whisper_model}' on {device} ({compute_type})...")
            try:
                _whisper_model = WhisperModel(
                    cfg.whisper_model,
                    device=device,
                    compute_type=compute_type,
                )
            except Exception as e:
                if device != "cpu":
                    print(f"[STT] CUDA Whisper load failed: {e}")
                    if "cublas64_12.dll" in str(e):
                        print(
                            "[STT] Install CUDA Toolkit 12.x or add its bin directory "
                            "to PATH to enable GPU transcription."
                        )
                    print("[STT] Falling back to CPU (float32).")
                    _whisper_model = WhisperModel(
                        cfg.whisper_model,
                        device="cpu",
                        compute_type="float32",
                    )
                else:
                    raise
            print("[STT] Whisper ready.")
    return _whisper_model


def transcribe(
    audio_data: np.ndarray,
    sample_rate: int = 16000,
    initial_prompt: str | None = None,
) -> str:
    """Transcribe a numpy float32 array. Returns text."""
    try:
        audio_data = _preprocess_audio(audio_data, sample_rate)
    except Exception as exc:
        print(f"[STT] Preprocessing failed, using raw audio: {exc}")

    model = load_whisper()
    kwargs = dict(
        beam_size=5,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    if initial_prompt:
        kwargs["initial_prompt"] = initial_prompt

    try:
        segments, _ = model.transcribe(audio_data, **kwargs)
        return " ".join(s.text.strip() for s in segments).strip()
    except Exception as e:
        if "cublas64_12.dll" not in str(e):
            raise

        print(f"[STT] CUDA transcription failed: {e}")
        print(
            "[STT] Install CUDA Toolkit 12.x or add its bin directory to PATH "
            "to enable GPU transcription."
        )
        print("[STT] Retrying transcription on CPU (float32).")
        global _whisper_model
        with _model_lock:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                get_config().whisper_model,
                device="cpu",
                compute_type="float32",
            )
            model = _whisper_model
        segments, _ = model.transcribe(audio_data, **kwargs)
        return " ".join(s.text.strip() for s in segments).strip()


class PushToTalkRecorder:
    """
    Records audio while active (push-to-talk style).
    Call start_recording() / stop_and_transcribe() from UI.
    """

    def __init__(self):
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._level_lock = threading.Lock()
        self._last_level = 0.0
        self.on_transcribed: Callable[[str], None] | None = None
        self.on_status: Callable[[str], None] | None = None
        self.on_level: Callable[[float], None] | None = None

    def _audio_callback(self, indata, frames, time_info, status):
        if self._recording:
            with self._lock:
                self._frames.append(indata.copy())
            if self.on_level:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                self._last_level = rms
                self.on_level(rms)

    def start_recording(self, device_index: int | None = None):
        if self._recording:
            return
        cfg = get_config()
        self._frames = []
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=cfg.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
            device=device_index,
            blocksize=1024,
        )
        self._stream.start()
        print("[STT] Recording started")
        if self.on_status:
            self.on_status("LISTENING")

    def stop_and_transcribe(self, initial_prompt: str | None = None) -> str | None:
        """Stops recording, transcribes, calls on_transcribed. Returns text."""
        if not self._recording:
            return None
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if self.on_status:
            self.on_status("TRANSCRIBING")

        with self._lock:
            frames = list(self._frames)
            print(f"[STT] Collected frames: {len(frames)}")

        if not frames:
            if self.on_status:
                self.on_status("IDLE")
            return None

        audio = np.concatenate(frames, axis=0).flatten()
        print(f"[STT] Samples: {len(audio)}")
        print(f"[STT] Mean amplitude: {np.abs(audio).mean()}")

        # Noise floor check
        cfg = get_config()

        print(
        f"[STT] Silence check: "
        f"{np.abs(audio).mean()} vs {cfg.silence_threshold}"
        )

        if np.abs(audio).mean() < cfg.silence_threshold:
            if self.on_status:
                self.on_status("IDLE")
            return None

        def _transcribe_thread():
            try:
                text = transcribe(audio, initial_prompt=initial_prompt)
                if text and self.on_transcribed:
                    self.on_transcribed(text)
                    return
            except Exception as e:
                print(f"[STT] Transcription failed: {e}")
            if self.on_status:
                self.on_status("IDLE")

        threading.Thread(target=_transcribe_thread, daemon=True).start()
        return None  # result delivered via callback

    @staticmethod
    def list_devices() -> list[dict]:
        devices = sd.query_devices()
        result = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                result.append({"index": i, "name": d["name"]})
        return result
