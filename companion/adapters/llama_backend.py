"""llama.cpp standalone server subprocess manager (using llama-server.exe)."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
LLAMA_BIN_DIR = BASE_DIR / "data" / "llama_bin"
SERVER_EXE = LLAMA_BIN_DIR / "llama-server.exe"

# Known mmproj download URLs keyed by model filename substring
_MMPROJ_MAP: dict[str, tuple[str, str]] = {
    "gemma-4-e4b-it": (
        "https://huggingface.co/batiai/Gemma-4-E4B-it-GGUF/resolve/main/mmproj-BF16.gguf",
        "mmproj-BF16.gguf",
    ),
}


def _resolve_mmproj(model_path: str, mmproj_cfg: str = "") -> str | None:
    """Auto-detect or download the multimodal projector file.

    1. If ``mmproj_cfg`` is non-empty, use it directly.
    2. Scan the model's directory for ``*mmproj*.gguf`` files.
    3. If not found, attempt to download from a known Hugging Face URL
       based on the model filename.
    """
    # 1. Explicit config path
    if mmproj_cfg:
        p = Path(mmproj_cfg)
        if p.exists():
            return str(p)
        print(f"[mmproj] configured path not found: {mmproj_cfg}")

    model_dir = Path(model_path).parent

    # 2. Search for mmproj files next to the model
    candidates = sorted(model_dir.glob("*mmproj*.gguf"))
    if candidates:
        match = candidates[0]
        print(f"[mmproj] found: {match.name}")
        return str(match)

    # 3. Try to download for known model architectures
    model_name = Path(model_path).name.lower()
    for key, (url, fname) in _MMPROJ_MAP.items():
        if key in model_name:
            dest = model_dir / fname
            if dest.exists():
                print(f"[mmproj] found cached: {dest.name}")
                return str(dest)
            print(f"[mmproj] downloading {fname} from Hugging Face (~946 MB)...")
            try:
                r = requests.get(url, stream=True, timeout=30)
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded * 100 // total
                            print(f"[mmproj] download progress: {pct}%", end="\r")
                print(f"\n[mmproj] saved to {dest}")
                return str(dest)
            except Exception as e:
                print(f"[mmproj] download failed: {e}")
                return None

    return None


def _kill_all_llama_servers():
    """Kill ALL llama-server.exe processes on the system (orphan cleanup).

    Uses ``taskkill /F`` because ``CTRL_BREAK_EVENT`` is unreliable — orphaned
    servers accumulate on the same port and answer requests instead of the
    current server, breaking vision (mmproj) and other features.
    """
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "llama-server.exe"],
            capture_output=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def _wait_port_free(host: str, port: int, timeout: float = 10.0) -> bool:
    """Block until *port* on *host* is free (no process listening).

    Returns ``True`` if the port became free within *timeout*, ``False``
    otherwise.  Ensures the new server process can bind without conflict.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except (ConnectionRefusedError, OSError):
            return True
        time.sleep(0.5)
    return False


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
        mmproj_path: str | None = None,
        image_max_tokens: int = 2048,
    ):
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self.port = port
        self.host = host
        self.chat_format = chat_format
        self.ctx_size = ctx_size
        self.mmproj_path = mmproj_path
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
        if self.mmproj_path:
            cmd += ["--mmproj", self.mmproj_path]
            cmd += ["--image-max-tokens", str(self.image_max_tokens)]
        else:
            # No mmproj available — vision will fail with a clear error
            print("[llama] No multimodal projector found — vision disabled")
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
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return

        # 1. Graceful shutdown via API
        try:
            requests.post(f"http://{self.host}:{self.port}/shutdown", timeout=3)
            proc.wait(timeout=5)
            return
        except Exception:
            pass

        # 2. CTRL_BREAK_EVENT (only reaches our process group)
        try:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
            proc.wait(timeout=5)
            return
        except Exception:
            pass

        # 3. Hard kill
        try:
            proc.kill()
            proc.wait(timeout=3)
        except Exception:
            pass

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
        # If the server we know about is healthy, no need to restart
        if _server and _server.is_running:
            return _server.base_url

        # Nuke ALL orphaned llama-server processes — they accumulate on the
        # same port and steal requests meant for the current server.
        _kill_all_llama_servers()

        from config import get_config
        cfg = get_config()

        # Wait for port to be free before binding
        _wait_port_free(cfg.llama_host, cfg.llama_port, timeout=15)
        if _server:
            _server.stop()

        model_path = cfg.llama_model_path
        if not model_path or not os.path.exists(model_path):
            raise RuntimeError(
                f"llama model not found at '{model_path}'. "
                "Set llm.llama_model_path in config.yaml or download a GGUF model."
            )

        mmproj_path = _resolve_mmproj(model_path, cfg.llama_mmproj_path)

        _server = LlamaServer(
            model_path=model_path,
            n_gpu_layers=cfg.llama_n_gpu_layers,
            port=cfg.llama_port,
            host=cfg.llama_host,
            chat_format=cfg.llama_chat_format or None,
            ctx_size=cfg.llama_ctx_size,
            mmproj_path=mmproj_path,
            image_max_tokens=cfg.llama_image_max_tokens,
        )
        return _server.start(timeout=cfg.llama_startup_timeout)


def stop_llama_server():
    global _server
    with _server_lock:
        if _server:
            _server.stop()
            _server = None
