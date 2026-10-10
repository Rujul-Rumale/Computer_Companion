"""Secure API key storage using OS keyring with encrypted file fallback."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

_SERVICE = "companion"

_KEY_DIR = Path(__file__).resolve().parent.parent / "data"
_KEY_FILE = _KEY_DIR / ".credentials.enc"

keyring_available: bool | None = None


def _try_import_keyring():
    global keyring_available
    try:
        import keyring as _kr
        # Test that the backend actually works (not just imported)
        _kr.set_password(_SERVICE, "_probe", "ok")
        _kr.delete_password(_SERVICE, "_probe")
        keyring_available = True
        return _kr
    except Exception:
        keyring_available = False
        return None


def is_available() -> bool:
    if keyring_available is None:
        _try_import_keyring()
    return bool(keyring_available)


def _get_keyring():
    import keyring
    return keyring


def store_key(name: str, key: str) -> bool:
    if is_available():
        try:
            _get_keyring().set_password(_SERVICE, name, key)
            return True
        except Exception:
            pass
    return _store_key_encrypted(name, key)


def load_key(name: str) -> str | None:
    if is_available():
        try:
            val = _get_keyring().get_password(_SERVICE, name)
            if val:
                return val
        except Exception:
            pass
    return _load_key_encrypted(name)


def delete_key(name: str) -> bool:
    if is_available():
        try:
            _get_keyring().delete_password(_SERVICE, name)
            return True
        except Exception:
            pass
    return _delete_key_encrypted(name)


def list_keys() -> list[str]:
    if is_available():
        try:
            kr = _get_keyring()
            if hasattr(kr, "get_credential"):
                cred = kr.get_credential(_SERVICE, None)
                if cred and cred.username:
                    return [cred.username]
        except Exception:
            pass
    return _list_keys_encrypted()


def _derive_key() -> bytes:
    parts = [
        platform.node(),
        os.getlogin() if hasattr(os, "getlogin") else "user",
        platform.machine(),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).digest()[:32]


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _store_key_encrypted(name: str, key: str) -> bool:
    try:
        _KEY_DIR.mkdir(parents=True, exist_ok=True)
        store: dict[str, str] = {}
        if _KEY_FILE.exists():
            store = json.loads(_KEY_FILE.read_text(encoding="utf-8"))
        store[name] = key
        plaintext = json.dumps(store).encode()
        enc = _xor_bytes(plaintext, _derive_key())
        _KEY_FILE.write_bytes(enc)
        return True
    except Exception:
        return False


def _load_key_encrypted(name: str) -> str | None:
    try:
        if not _KEY_FILE.exists():
            return None
        enc = _KEY_FILE.read_bytes()
        plaintext = _xor_bytes(enc, _derive_key())
        store = json.loads(plaintext)
        return store.get(name)
    except Exception:
        return None


def _delete_key_encrypted(name: str) -> bool:
    try:
        if not _KEY_FILE.exists():
            return False
        enc = _KEY_FILE.read_bytes()
        plaintext = _xor_bytes(enc, _derive_key())
        store = json.loads(plaintext)
        if name in store:
            del store[name]
            enc = _xor_bytes(json.dumps(store).encode(), _derive_key())
            _KEY_FILE.write_bytes(enc)
            return True
    except Exception:
        pass
    return False


def _list_keys_encrypted() -> list[str]:
    try:
        if not _KEY_FILE.exists():
            return []
        enc = _KEY_FILE.read_bytes()
        plaintext = _xor_bytes(enc, _derive_key())
        store = json.loads(plaintext)
        return list(store.keys())
    except Exception:
        return []
