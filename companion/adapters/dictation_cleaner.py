"""Dictation cleanup subprocess — runs Qwen2.5-0.5B GGUF on CPU via llama-cpp-python.

Communicates with the main process via JSON-lines over stdin/stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

WORKER_SCRIPT = r'''
import json
import sys

from llama_cpp import Llama


def main():
    model_path = None
    llm = None

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        cmd = msg.get("cmd")

        if cmd == "load":
            model_path = msg["model"]
            llm = Llama(
                model_path=model_path,
                n_ctx=512,
                n_gpu_layers=0,       # CPU only — no VRAM contention
                verbose=False,
            )
            sys.stdout.write(json.dumps({"ok": True}) + "\n")
            sys.stdout.flush()

        elif cmd == "cleanup":
            if llm is None:
                sys.stdout.write(
                    json.dumps({"text": msg.get("text", "")}) + "\n"
                )
                sys.stdout.flush()
                continue

            text = msg.get("text", "")
            prompt = (
                "Clean up the following speech transcription. "
                "Remove filler words (um, uh, like, you know, actually, basically, literally). "
                "Fix stutters and repetitions. "
                "Add proper punctuation and capitalization. "
                "Output ONLY the cleaned text with no explanations.\n\n"
                f"{text}"
            )
            try:
                result = llm(
                    prompt,
                    max_tokens=256,
                    temperature=0.0,
                    stop=["\n\n"],
                )
                cleaned = result["choices"][0]["text"].strip()
            except Exception:
                cleaned = text

            if not cleaned:
                cleaned = text

            sys.stdout.write(json.dumps({"text": cleaned}) + "\n")
            sys.stdout.flush()

        elif cmd == "shutdown":
            sys.exit(0)


if __name__ == "__main__":
    main()
'''


class DictationCleaner:
    """Manages a long-lived subprocess running the tiny cleanup model on CPU.

    Usage::

        cleaner = DictationCleaner("data/models/qwen-0.5b-q4.gguf")
        cleaner.start()
        cleaned = cleaner.cleanup("um hi how uh are you")
        cleaner.shutdown()
    """

    def __init__(self, model_path: str, python_path: str | None = None):
        self._model_path = model_path
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._ready = threading.Event()

        if python_path is None:
            # Try to find the llama venv Python first
            candidates = [
                Path(__file__).resolve().parent.parent
                / ".venv_llama311" / "Scripts" / "python.exe",
                Path(__file__).resolve().parent.parent
                / ".venv" / "Scripts" / "python.exe",
            ]
            python_path = None
            for c in candidates:
                if c.exists():
                    python_path = str(c)
                    break
            if python_path is None:
                python_path = sys.executable

        self._python_path = python_path

    def start(self, timeout: float = 120.0):
        """Launch the worker subprocess and wait for it to load the model."""
        if self._proc is not None:
            return

        self._proc = subprocess.Popen(
            [self._python_path, "-c", WORKER_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # Tell worker to load the model
        self._send({"cmd": "load", "model": self._model_path})
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("Dictation cleaner worker exited early")
            try:
                resp = json.loads(line)
                if resp.get("ok"):
                    self._ready.set()
                    return
            except json.JSONDecodeError:
                continue

        self.shutdown()
        raise TimeoutError("Dictation cleaner model load timed out")

    def cleanup(self, text: str) -> str:
        """Send *text* to the worker and return the cleaned version."""
        if not self._ready.is_set() or self._proc is None:
            return text  # fallback: return raw text if cleaner not ready

        with self._lock:
            self._send({"cmd": "cleanup", "text": text})
            line = self._proc.stdout.readline()
            if not line:
                return text
            try:
                resp = json.loads(line)
                return resp.get("text", text)
            except json.JSONDecodeError:
                return text

    def shutdown(self):
        """Stop the worker subprocess."""
        if self._proc and self._proc.poll() is None:
            try:
                self._send({"cmd": "shutdown"})
                self._proc.wait(timeout=10)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None
        self._ready.clear()

    def _send(self, msg: dict):
        if self._proc and self._proc.stdin:
            self._proc.stdin.write(json.dumps(msg) + "\n")
            self._proc.stdin.flush()
