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
    api_key: str = "not-needed"

    def normalized_base_url(self) -> str:
        url = self.base_url.rstrip("/")
        if self.backend.lower() == "ollama" and not url.endswith("/v1"):
            url = f"{url}/v1"
        return url

    def client(self) -> OpenAI:
        return OpenAI(base_url=self.normalized_base_url(), api_key=self.api_key)


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
    backend = cfg.llm_backend.lower()

    if backend == "llama":
        from adapters.llama_backend import start_llama_server
        base_url = start_llama_server()
        return ModelProvider(backend=cfg.llm_backend, base_url=base_url)

    if backend == "cloud":
        from security.keyring_store import load_key
        base_url = cfg.llm_cloud_base_url
        api_key_ref = cfg.llm_cloud_api_key_ref
        api_key = load_key(api_key_ref) if api_key_ref else ""
        if not api_key:
            print(f"[WARN] No API key found for cloud provider '{cfg.llm_cloud_provider}'. "
                  "Set it up in Settings > Cloud.")
        return ModelProvider(
            backend=cfg.llm_backend,
            base_url=base_url,
            api_key=api_key or "not-needed",
        )

    return ModelProvider(
        backend=cfg.llm_backend,
        base_url=cfg.llm_base_url,
    )


def reset_provider():
    """Invalidate the cached provider. Next get_model_provider() call recreates it."""
    global _PROVIDER
    _PROVIDER = None
