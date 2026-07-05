"""OpenAI-compatible local model provider adapters."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from openai import OpenAI

from config import get_config


@dataclass(frozen=True)
class ModelProvider:
    backend: str
    base_url: str

    def normalized_base_url(self) -> str:
        url = self.base_url.rstrip("/")
        if self.backend.lower() == "ollama" and not url.endswith("/v1"):
            url = f"{url}/v1"
        return url

    def client(self) -> OpenAI:
        return OpenAI(base_url=self.normalized_base_url(), api_key="not-needed")


_PROVIDER: ModelProvider | None = None
_provider_lock = threading.Lock()


def get_model_provider() -> ModelProvider:
    global _PROVIDER
    if _PROVIDER is None:
        with _provider_lock:
            if _PROVIDER is None:
                _PROVIDER = _create_provider()
    return _PROVIDER


def _create_provider() -> ModelProvider:
    cfg = get_config()
    if cfg.llm_backend.lower() == "llama":
        from adapters.llama_backend import start_llama_server
        base_url = start_llama_server()
    else:
        base_url = cfg.llm_base_url
    return ModelProvider(
        backend=cfg.llm_backend,
        base_url=base_url,
    )


def reset_provider():
    """Invalidate the cached provider. Next get_model_provider() call recreates it."""
    global _PROVIDER
    _PROVIDER = None
