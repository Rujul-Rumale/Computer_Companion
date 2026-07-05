"""llama.cpp standalone server subprocess manager (using llama-server.exe)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
LLAMA_BIN_DIR = BASE_DIR / "data" / "llama_bin"
SERVER_EXE = LLAMA_BIN_DIR / "llama-server.exe"


class LlamaServer:
    """Manages a llama.cpp server subprocess lifecycle."""

    def __init__(
        self,
        model_path: str,
        *,
        n_gpu_layers: int = -1,
        port: int = 8012,
        host: str = "127.0.0.1",
        chat_format: str | None = None,
        ctx_size: int = 8192,
        mmproj_auto: bool = True,
        image_max_tokens: int = 2048,
    ):
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self.port = port
        self.host = host
        self.chat_format = chat_format
        self.ctx_size = ctx_size
        self.mmproj_auto = mmproj_auto
        self.image_max_tokens = image_max_tokens
        self._proc: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, timeout: float = 60.0) -> str:
        if self.is_running:
            return self.base_url

        if not SERVER_EXE.exists():
            raise RuntimeError(
                f"llama-server.exe not found at {SERVER_EXE}. "
                "Download from https://github.com/ggml-org/llama.cpp/releases"
            )

        cmd = [
            str(SERVER_EXE),
            "--model", self.model_path,
            "--host", self.host,
            "--port", str(self.port),
            "--n-gpu-layers", str(self.n_gpu_layers),
            "--ctx-size", str(self.ctx_size),
        ]
        if self.mmproj_auto:
            cmd += ["--mmproj-auto"]
            cmd += ["--image-max-tokens", str(self.image_max_tokens)]
        if self.chat_format:
            cmd += ["--chat-template", self.chat_format]

        log_path = BASE_DIR / "data" / "llama_server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "w", encoding="utf-8") as log_file:
            self._proc = subprocess.Popen(
                cmd,
                cwd=str(LLAMA_BIN_DIR),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
            )

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(f"http://{self.host}:{self.port}/v1/models", timeout=2)
                if resp.status_code == 200:
                    return self.base_url
            except requests.RequestException:
                pass
            if self._proc.poll() is not None:
                log_text = log_path.read_text(encoding="utf-8")[-2000:]
                raise RuntimeError(
                    f"llama server exited early (code {self._proc.returncode}). "
                    f"Log tail:\n{log_text}"
                )
            time.sleep(0.5)

        self.stop()
        raise TimeoutError(
            f"llama server did not become ready within {timeout}s. "
            f"Check {log_path} for details."
        )

    def stop(self):
        if self._proc and self._proc.poll() is None:
            try:
                if sys.platform == "win32":
                    self._proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self._proc.terminate()
                try:
                    self._proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait()
            except KeyboardInterrupt:
                self._proc.kill()
                self._proc.wait()
        self._proc = None

    def restart(self, timeout: float = 60.0) -> str:
        self.stop()
        return self.start(timeout=timeout)


# Singleton
_server: LlamaServer | None = None
_server_lock = threading.Lock()


def get_llama_server() -> LlamaServer | None:
    global _server
    return _server


def start_llama_server() -> str:
    global _server
    with _server_lock:
        if _server and _server.is_running:
            return _server.base_url

        # Clean up dead server before starting new one
        if _server:
            _server.stop()

        from config import get_config
        cfg = get_config()

        model_path = cfg.llama_model_path
        if not model_path or not os.path.exists(model_path):
            raise RuntimeError(
                f"llama model not found at '{model_path}'. "
                "Set llm.llama_model_path in config.yaml or download a GGUF model."
            )

        _server = LlamaServer(
            model_path=model_path,
            n_gpu_layers=cfg.llama_n_gpu_layers,
            port=cfg.llama_port,
            host=cfg.llama_host,
            chat_format=cfg.llama_chat_format or None,
            ctx_size=cfg.llama_ctx_size,
            mmproj_auto=cfg.llama_mmproj_auto,
            image_max_tokens=cfg.llama_image_max_tokens,
        )
        return _server.start(timeout=cfg.llama_startup_timeout)


def stop_llama_server():
    global _server
    with _server_lock:
        if _server:
            _server.stop()
            _server = None
