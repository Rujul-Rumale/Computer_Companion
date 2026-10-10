# Companion: Fixes + Skills Implementation Plan

## Current State
- 12 utility skills already implemented in `tools/utility_tools.py` and `tools/system_tools.py`
- All registered in `TOOL_REGISTRY` in `tools/registry.py`
- Prompt block already updated
- User context section already in `config.yaml`
- User context injection already in `ai/llm_client.py`

## 3 Remaining Fixes

### Fix 1: Screenshot Not Triggering (take_screenshot not in TOOL_REGISTRY)

**Root cause:** `take_screenshot` function exists but is NOT in `TOOL_REGISTRY`. Both `_dispatch_message` (auto-capture) and `_take_screenshot` (hotkey) call `execute_tool("take_screenshot")` which only resolves tools through `TOOL_REGISTRY` — returns "Unknown tool".

**Changes needed:**

1. **`tools/base.py`** — Add `hidden: bool = False` parameter to `tool_spec()` function, include `"hidden": hidden` in returned dict.

2. **`tools/registry.py:839-842`** — Replace the comment with actual tool registration:
   ```python
   "take_screenshot": _tool_spec(
       name="take_screenshot",
       description="",
       parameters={"type": "object", "properties": {}, "additionalProperties": False},
       handler=take_screenshot,
       hidden=True,
   ),
   ```

3. **`tools/registry.py:get_tool_schemas()`** — Filter out hidden tools:
   ```python
   def get_tool_schemas() -> list[dict[str, Any]]:
       return [
           {
               "type": "function",
               "function": {
                   "name": spec["name"],
                   "description": spec["description"],
                   "parameters": spec["parameters"],
               },
           }
           for spec in TOOL_REGISTRY.values()
           if not spec.get("hidden")
       ]
   ```

### Fix 2: Auto-Mute (Audio Ducking) on PTT

**Root cause:** Not implemented. `_ptt_start` hard-interrupts TTS but never adjusts system volume.

**Changes needed:**

1. **`ui/main_window.py`** — In `_ptt_start()`:
   ```python
   # At top of file, add import:
   # from tools.system_tools import _get_pycaw_volume
   
   def _ptt_start(self):
       if self._sm.mic_muted:
           return
       if self._assistant_responding:
           self._interrupt()
       # Save and lower volume (ducking)
       self._saved_volume = _get_system_volume()
       _set_system_volume(0.15)  # 15%
       ...
   
   def _ptt_stop(self):
       # Restore volume
       if hasattr(self, '_saved_volume') and self._saved_volume is not None:
           _set_system_volume(self._saved_volume)
           self._saved_volume = None
       ...
   ```

2. **`tools/system_tools.py`** — Add helper functions using pycaw:
   ```python
   def _get_pycaw():
       from ctypes import cast, POINTER
       from comtypes import CLSCTX_ALL
       from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
       devices = AudioUtilities.GetSpeakers()
       interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
       return cast(interface, POINTER(IAudioEndpointVolume))

   def _get_system_volume() -> float:
       try:
           return _get_pycaw().GetMasterVolumeLevelScalar()
       except Exception:
           return None

   def _set_system_volume(level: float):
       try:
           _get_pycaw().SetMasterVolumeLevelScalar(level, None)
       except Exception:
           pass
   ```

3. **`config.yaml`** — Add duck volume config:
   ```yaml
   audio:
     duck_volume: 0.15
   ```

### Fix 3: Search Tool Doesn't Go Deep

**Root cause:** LLM calls `web_search_results` (gets snippets) but rarely calls `web_read_page` (reads full article). No combined tool exists. Descriptions don't guide chaining.

**Changes needed:**

1. **`tools/web_research.py`** — Add `web_search_deep()`:
   ```python
   def web_search_deep(params: dict[str, Any]) -> ToolResult:
       """Search + auto-read the top result in one call."""
       query = str(params.get("query", "")).strip()
       if not query:
           return ToolResult(False, "query is required")
       
       # First, search
       search_result = web_search_results({"query": query, "count": 1})
       if not search_result.success:
           return search_result
       
       # Extract first result URL
       results = search_result.data.get("results", [])
       if not results:
           return ToolResult(False, f"No results for '{query}'")
       
       top_url = results[0].get("url", "")
       if not top_url:
           return search_result
       
       # Read the page
       page_result = web_read_page({"url": top_url, "max_chars": 6000})
       if not page_result.success:
           return search_result  # fallback: return search results if page read fails
       
       combined = f"Search: {query}\n\nTop result: {results[0].get('title')}\n{top_url}\n\n{page_result.message}"
       return ToolResult(True, combined, {
           "query": query,
           "source_url": top_url,
           "source_title": results[0].get("title"),
           "search_snippet": results[0].get("snippet"),
           "page_content": page_result.message,
       })
   ```

2. **`tools/registry.py`** — Register `web_search_deep` in TOOL_REGISTRY and add to prompt block:
   ```
   "- Web: web_search_results (get snippets first), web_search_deep (search + read top result), web_read_page (read full article from URL).\n"
   ```

## Files to Modify
| File | Changes |
|------|---------|
| `tools/base.py` | Add `hidden` param to `tool_spec()` |
| `tools/registry.py` | Register take_screenshot (hidden), add web_search_deep, update get_tool_schemas(), update prompt block |
| `tools/web_research.py` | Add `web_search_deep()` function |
| `tools/system_tools.py` | Add `_get_system_volume()`, `_set_system_volume()` helpers |
| `ui/main_window.py` | Add volume ducking to `_ptt_start()` / `_ptt_stop()` |
| `config/config.yaml` | Add `audio.duck_volume` config |

## Test
- Run `test_launcher.py` — expects 70+ passing
