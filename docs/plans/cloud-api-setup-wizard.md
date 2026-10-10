# Plan: Cloud API Backend + First-Run Setup Wizard

**Status:** Parked — ready for implementation when desired  
**Created:** 2026-07-17  

---

## Overview

Add a generic OpenAI-compatible cloud backend to the existing architecture, and replace the current "copy config.example.yaml" first-run behavior with a professional, multi-page setup wizard that detects hardware, recommends models, supports cloud API keys (stored securely via OS keyring), and includes model auto-download from HuggingFace.

### Key Decisions

| Decision | Choice |
|----------|--------|
| Cloud scope | Any OpenAI-compatible API (NIMs, OpenAI, Together, Groq, custom) |
| Cloud vs local | Additional option alongside existing local backends |
| API key storage | OS keyring (`keyring` library / Windows Credential Locker), fallback to encrypted file |
| First-run detection | `data/.setup_complete` marker file |
| Cloud failure behavior | Error + suggest local fallback |
| Model downloads | Auto-download from HuggingFace with progress bar during setup |
| Wizard aesthetic | Lighter/modern feel within PySide6 (card-based, more whitespace, softer colors) |

---

## Step 1: Hardware Detection Module

**New file:** `companion/adapters/hardware.py`

- Detect GPU via `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader` (subprocess parse)
- Detect RAM via `psutil.virtual_memory().total`
- Detect CPU cores via `psutil.cpu_count(logical=False)`
- Return a `HardwareProfile` dataclass: `gpu_name`, `gpu_vram_mb`, `ram_gb`, `cpu_cores`, `has_cuda`
- Cache result (hardware doesn't change between sessions)

---

## Step 2: Model Catalog

**New file:** `companion/config/model_catalog.yaml`

Curated list of models with hardware requirements, GGUF download URLs (HuggingFace), and vision capability flags:

```yaml
local_models:
  - name: "Gemma 4 E4B"
    file: gemma-4-E4B-it-Q4_K_M.gguf
    huggingface_url: "https://huggingface.co/..."
    min_vram_mb: 3000
    min_ram_gb: 6
    supports_vision: true
    mmproj_url: "https://huggingface.co/..."
  - name: "Phi-4 Mini"
    ...
  - name: "Qwen2.5 7B"
    ...

cloud_presets:
  - name: "NVIDIA NIMs (Free)"
    base_url: "https://integrate.api.nvidia.com/v1"
    models:
      - name: "Llama 3.1 90B"
        model_id: "meta/llama-3.1-90b-instruct"
        supports_vision: false
      - name: "LLaVA 34B"
        model_id: "yehia/llava-34b-v2"
        supports_vision: true
  - name: "OpenAI"
    base_url: "https://api.openai.com/v1"
    models: [...]
  - name: "Custom (OpenAI-compatible)"
    base_url: ""
    models: []
```

---

## Step 3: Secure Key Storage

**New file:** `companion/security/keyring_store.py`

- `store_key(name: str, key: str)` — saves via `keyring.set_password("companion", name, key)`
- `load_key(name: str) -> str | None` — loads via `keyring.get_password("companion", name)`
- `delete_key(name: str)` — removes
- `is_available() -> bool` — checks if keyring backend works
- Fallback if keyring unavailable: AES-encrypted file using machine-specific key derivation (SHA-256 of machine SID + hostname)
- Add `keyring` to `requirements.txt`

---

## Step 4: Config Schema Updates

**Modified files:**
- `companion/config/config.yaml`
- `companion/config/config.example.yaml`
- `companion/config/loader.py`

New config fields:

```yaml
llm:
  backend: cloud            # llama | lmstudio | ollama | cloud
  cloud:
    provider: nvidia        # nvidia | openai | together | groq | custom
    base_url: "https://integrate.api.nvidia.com/v1"
    api_key_ref: "nvidia_nim"  # keyring reference name
    model: "meta/llama-3.1-90b-instruct"
```

Add properties to `Config` class in `loader.py`:
- `llm_cloud_provider`, `llm_cloud_base_url`, `llm_cloud_api_key_ref`, `llm_cloud_model`

---

## Step 5: Model Provider Update

**Modified file:** `companion/adapters/model_provider.py`

- In `_create_provider()`, when `backend == "cloud"`:
  - Read `cloud_base_url` from config
  - Load API key from keyring via `keyring_store.load_key(cloud_api_key_ref)`
  - Return `ModelProvider` with the real API key
- Modify `ModelProvider` dataclass to accept optional `api_key` field
- In `client()`, use `api_key` if provided, else `"not-needed"`

---

## Step 6: Setup Wizard UI

**New file:** `companion/ui/setup_wizard.py`

A `QDialog` subclass with a `QStackedWidget` for page navigation. Lighter, modern aesthetic (softer dark theme with more whitespace, card-based layout, smooth page transitions) while staying within PySide6.

### Pages

1. **Welcome** — App logo, brief tagline, "Get Started" button
2. **Mode Selection** — Three large clickable cards:
   - "Local Models" (runs on your hardware, private, free)
   - "Cloud API" (powerful models, needs API key, faster setup)
   - "Both" (local primary, cloud as fallback)
3. **Hardware Scan** (if local selected) — Shows detected GPU/RAM/CPU, recommends models from catalog, user can pick or change
4. **Model Download** (if local) — Downloads selected GGUF + mmproj via HuggingFace with progress bar (reuse/extend `_resolve_mmproj` pattern with proper QThread + progress signal)
5. **Cloud Setup** (if cloud selected) — Provider dropdown, API key input (password field), model dropdown populated from catalog, "Test Connection" button that sends a simple prompt
6. **Voice** — Whisper model, TTS engine selection
7. **About You** — City, timezone, language, interests
8. **Summary** — Overview of choices, "Launch COMPUTER" button

On finish: writes `config.yaml`, stores API key in keyring, creates `data/.setup_complete` marker file.

---

## Step 7: First-Run Detection

**Modified file:** `companion/main.py`

- Before creating `MainWindow`, check if `data/.setup_complete` exists
- If not: show `SetupWizard`, block until completed
- If user closes wizard without finishing: show warning, exit or offer to skip

---

## Step 8: Settings Dialog Update

**Modified file:** `companion/ui/settings_dialog.py`

- Add "Cloud" tab to the tab widget:
  - Provider dropdown (NVIDIA NIMs, OpenAI, Together, Groq, Custom)
  - Base URL field (auto-filled from provider, editable for "Custom")
  - API key field (password field with show/hide toggle, saves to keyring)
  - Model field (text input or dropdown if provider has known models)
  - "Test Connection" button
- Add backend dropdown options: add "cloud" to the existing `["llama", "lmstudio", "ollama"]` list

---

## Step 9: Cloud Fallback in LLM Client

**Modified file:** `companion/ai/llm_client.py`

- Add error handling around the streaming call (line 309):
  - Catch `openai.APIConnectionError`, `openai.AuthenticationError`, `openai.RateLimitError`
  - If cloud backend and error occurs, emit a signal suggesting local fallback
  - Show toast notification: "Cloud API unavailable — switch to local model in Settings"

---

## Step 10: Model Download Manager

**New file:** `companion/adapters/model_downloader.py`

- `download_model(url: str, dest: Path, progress_callback: Callable)` — streaming download with chunk progress
- Uses `requests` (already in requirements) with streaming
- Validates download (file size check, optional SHA-256)
- Shows progress via Qt signals for wizard integration
- Threaded via `QThread` to avoid UI freeze

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `adapters/hardware.py` | **New** | GPU/RAM/CPU detection |
| `config/model_catalog.yaml` | **New** | Curated model list + cloud presets |
| `security/keyring_store.py` | **New** | Secure API key storage |
| `ui/setup_wizard.py` | **New** | First-run setup wizard |
| `adapters/model_downloader.py` | **New** | HuggingFace model download with progress |
| `config/config.yaml` | **Modify** | Add `cloud` section under `llm` |
| `config/config.example.yaml` | **Modify** | Add `cloud` section, document new backend |
| `config/loader.py` | **Modify** | Add cloud config properties |
| `adapters/model_provider.py` | **Modify** | Support cloud backend + real API keys |
| `ui/settings_dialog.py` | **Modify** | Add "Cloud" tab, add "cloud" to backend list |
| `main.py` | **Modify** | Add first-run detection + wizard launch |
| `ai/llm_client.py` | **Modify** | Add cloud error handling + fallback suggestion |
| `requirements.txt` | **Modify** | Add `keyring` |

---

## Execution Order

1. **Hardware detection** (`hardware.py`) — no dependencies
2. **Keyring store** (`keyring_store.py`) — no dependencies
3. **Model catalog** (`model_catalog.yaml`) — no dependencies
4. **Model downloader** (`model_downloader.py`) — no dependencies
5. **Config updates** (`loader.py`, `config.yaml`) — depends on catalog structure
6. **Model provider** (`model_provider.py`) — depends on keyring + config
7. **Setup wizard** (`setup_wizard.py`) — depends on hardware, catalog, downloader, keyring
8. **First-run detection** (`main.py`) — depends on wizard
9. **Settings dialog** (`settings_dialog.py`) — depends on config + keyring
10. **LLM client** (`llm_client.py`) — cloud error handling

---

## Architecture Notes

### Why this works cleanly

The existing codebase already uses the **OpenAI Python SDK** as a generic HTTP client (`model_provider.py:25`). NVIDIA NIMs, OpenAI, Together, and Groq all expose OpenAI-compatible APIs. So the core change is just: pass a real API key instead of `"not-needed"`, and set the correct `base_url`. No new HTTP libraries needed.

### Image handling with cloud APIs

The codebase already sends images in OpenAI-compatible multimodal format (`llm_client.py:265`):
```python
{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
```
Cloud providers that support vision (NIMs LLaVA, OpenAI GPT-4V, etc.) accept this exact format. The only requirement is selecting a vision-capable model from the catalog.

### Keyring security model

- API keys never touch `config.yaml` (only a reference name is stored there)
- Windows Credential Locker is the primary backend (encrypted by the OS, tied to user account)
- Fallback: AES-256 encryption with machine-derived key for systems without keyring
- Keys loaded at runtime only, never logged or written to disk in plaintext
