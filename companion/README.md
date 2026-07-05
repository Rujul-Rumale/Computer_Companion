# AI Companion — Local Engineering AI Teammate

Terminal-style desktop AI companion. Dark industrial UI. Runs fully local on RTX 3050 / 16GB RAM.

---

## Stack

| Component | Technology |
|-----------|-----------|
| LLM | LM Studio (OpenAI-compatible API) |
| STT | Faster-Whisper (small, CUDA) |
| TTS | Piper TTS (local, auto-provisioned) |
| UI | PySide6 |
| Memory | SQLite |
| Backend | Python 3.11+ |

---

## Requirements

- Windows 11
- Python 3.11+
- NVIDIA GPU with CUDA 11.8+ (for Whisper CUDA)
- LM Studio installed with a model loaded
- ~4GB VRAM free for Whisper small + model inference

---

## Install

```bat
setup.bat
```

Or manually:

```bat
pip install -r requirements.txt
python seed_memory.py
```

---

## Start

### One-click launcher
Double-click:

```bat
launch_companion.bat
```

It will:
- create or reuse `.venv`
- install Python dependencies
- seed the memory database if needed
- start LM Studio if it can find it in common install paths
- wait for the local LM Studio API
- download a local Piper binary and voice model if they are missing
- start the app

### Manual first run
1. Open LM Studio → load your model → start local server (port 1234)
2. Verify model name in `config/config.yaml` under `llm.model` matches exactly what LM Studio shows
3. Run:

```bat
python main.py
```

or double-click `run.bat`

---

## Model Name

LM Studio shows model names like `gemma-3-4b-it` in the server tab. Copy it exactly into `config/config.yaml`:

```yaml
llm:
  model: "gemma-3-4b-it"   # must match LM Studio exactly
```

---

## Hotkeys

| Key | Action |
|-----|--------|
| `Ctrl+Space` | Push-to-talk (hold to record, release to transcribe) |
| `Ctrl+Shift+J` | Screenshot + send to LLM for analysis |
| `Enter` | Send text message |
| `■ STOP` button | Interrupt LLM generation + TTS |

---

## Configuration

### `config/config.yaml`
Main config: LLM backend, model, Whisper settings, TTS, memory, hotkeys, UI.

### `config/personality.yaml`
Editable personality: name, role, traits, rules, system prompt. Edit freely — changes take effect on next startup (or call `get_config().reload()`).

---

## Memory System

SQLite at `data/memory.db`. Four tables:

- **projects** — active/inactive projects with notes
- **people** — contacts with relationship and notes  
- **facts** — key-value store (preferences, goals, hardware info)
- **conversation_summaries** — auto-generated session summaries

Memory context is scoped per turn. Long-term memory is only injected when it is relevant to the current message or the current session state. Session memory starts empty and tracks the current project, task, and topic only after the user activates them.

Manage via the MEMORY tab in the UI or edit `seed_memory.py` and re-run it.

---

## Computer Control

The LLM can emit `[TOOL: tool_name param=value]` in responses to trigger actions.

Available tools:
- `open_app` — launch VS Code, KiCad, Fusion 360, SDR++, etc.
- `open_url` — open URLs in Chrome
- `web_search` — search Google/YouTube/GitHub/IEEE/StackOverflow
- `open_folder` — open Windows Explorer at path
- `set_volume` / `volume_up` / `volume_down` / `mute`
- `open_task_manager` / `open_settings`
- `take_screenshot` — capture + analyze

App paths are in `tools/executor.py` → `APP_MAP`. Update for your install paths.

---

## Whisper on CPU (if no CUDA)

Change in `config/config.yaml`:
```yaml
speech:
  whisper_device: "cpu"
  whisper_compute_type: "int8"
```

Significantly slower but functional.

---

## Piper TTS

Piper is downloaded into `data/piper/` and the default voice is downloaded into `data/voices/` on first launch.

The default voice is:
- `en_US-lessac-medium`

If the launcher cannot reach GitHub or Hugging Face, the app still starts, but voice output will stay unavailable until those files are present.

---

## Project Structure

```
companion/
├── main.py                  # entry point
├── run.bat                  # launcher
├── setup.bat                # installer
├── seed_memory.py           # memory seeder
├── requirements.txt
├── config/
│   ├── config.yaml          # main config
│   ├── personality.yaml     # personality + system prompt
│   └── loader.py            # config accessor
├── ai/
│   └── llm_client.py        # LM Studio streaming client
├── audio/
│   ├── stt.py               # Faster-Whisper STT
│   └── tts.py               # Kokoro TTS
├── memory/
│   └── store.py             # SQLite memory
├── tools/
│   └── executor.py          # tool registry + handlers
├── ui/
│   └── main_window.py       # PySide6 terminal UI
└── data/
    └── memory.db            # auto-created
```

---

## State Visualizer

The orb bar shows current AI state:

| State | Color | Meaning |
|-------|-------|---------|
| IDLE | Gray | Waiting for input |
| LISTENING | Green | Recording voice |
| TRANSCRIBING | Yellow | Running Whisper |
| THINKING | Cyan | LLM generating |
| ACTING | Orange | Executing tool |
| SPEAKING | Purple | TTS playing |

---

## Troubleshooting

**LLM won't connect**
- LM Studio server must be running before launching the app
- Check model name in config matches LM Studio exactly (case-sensitive)
- Default port is 1234

**Whisper fails on CUDA**
- Run `nvidia-smi` to confirm GPU visible
- Try `whisper_device: cpu` + `whisper_compute_type: int8`

**Kokoro not found**
- `pip install kokoro` — requires espeak-ng on Windows: https://github.com/espeak-ng/espeak-ng/releases
- App falls back to pyttsx3 automatically if Kokoro fails

**No audio input**
- Check `sounddevice` can see your mic: `python -c "import sounddevice as sd; print(sd.query_devices())"`


## Launcher Logs

- `logs/startup.log`
- `logs/error.log`
