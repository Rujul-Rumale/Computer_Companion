"""
test_launcher.py - Tests for tool routing, web app resolution, web search, and URL opening.
Run: .venv/Scripts/python -m pytest tests/
"""
import os
import sys
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Mock webbrowser.open so tests don't hang
_browser_patch = unittest.mock.patch("tools.registry.webbrowser.open", return_value=True)
_browser_patch.start()

# Mock win32 clipboard at module level
_clipboard_fake = unittest.mock.MagicMock()
_clipboard_con_fake = unittest.mock.MagicMock()
import tools.clipboard

tools.clipboard._win32clipboard = _clipboard_fake
tools.clipboard._win32con = _clipboard_con_fake

# Mock win32gui so window tests don't fail without display
_win32gui_patch = unittest.mock.patch("tools.window_tools.win32gui")
_win32gui_patch.start()

# Redirect app cache to a temp file so tests don't pollute the real cache
import tools.app_scanner as _ascanner

_ascanner._CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "installed_apps_test.json"
_ascanner._CACHE_PATH.write_text("{}")

# Ensure clipboard watcher is started
from tools.clipboard import _get_manager
from tools.file_search import search_files
from tools.registry import (
    cancel_timer_tool,
    clipboard_get,
    clipboard_history,
    clipboard_set,
    execute_tool,
    focus_window_tool,
    get_system_status,
    list_timers_tool,
    list_windows,
    open_app,
    open_url,
    open_web_app,
    resolve_web_app,
    search_files_tool,
    search_web,
    set_timer_tool,
)
from tools.system_tools import format_status, system_status
from tools.web_search import build_search_url, resolve_platform

_get_manager().start_watcher()

passed = 0
failed = 0

def check(label, ok):
    global passed, failed
    if ok: passed += 1
    else: failed += 1; print(f"[FAIL] {label}", flush=True)

# ── resolve_web_app tests ──
print("=== resolve_web_app ===", flush=True)
check("youtube", resolve_web_app("youtube") == "https://youtube.com")
check("yt", resolve_web_app("yt") == "https://youtube.com")
check("gmail", resolve_web_app("gmail") == "https://mail.google.com")
check("email", resolve_web_app("email") == "https://mail.google.com")
check("amazon", resolve_web_app("amazon") == "https://amazon.com")
check("github", resolve_web_app("github") == "https://github.com")
check("unknown", resolve_web_app("unknown123") == "")
print("", flush=True)

# ── open_url tests ──
print("=== open_url ===", flush=True)
check("explicit", open_url({"url": "https://example.com"}).success)
check("auto-https", open_url({"url": "example.com"}).success)
check("no-url", not open_url({}).success)
print("", flush=True)

# ── open_web_app tests ──
print("=== open_web_app ===", flush=True)
check("youtube", open_web_app({"name": "youtube"}).success)
check("gmail", open_web_app({"name": "gmail"}).success)
check("unknown", not open_web_app({"name": "unknownxyz"}).success)
print("", flush=True)

# ── open_app tests ──
print("=== open_app ===", flush=True)
check("youtube-blocked", not open_app({"name": "youtube"}).success and "open_web_app" in open_app({"name": "youtube"}).message)
print("", flush=True)

# ── web_search tests ──
print("=== web_search.build_search_url ===", flush=True)
check("yt-search", "youtube.com/results" in build_search_url("youtube", "mark rober") and "mark+rober" in build_search_url("youtube", "mark rober"))
check("google-search", "google.com/search" in build_search_url("google", "python tutorial") and "python+tutorial" in build_search_url("google", "python tutorial"))
check("amazon-search", "amazon" in build_search_url("amazon", "chair") and "chair" in build_search_url("amazon", "chair"))
check("gh-search", "github.com/search" in build_search_url("github", "opencode") and "opencode" in build_search_url("github", "opencode"))
check("maps-search", "google.com/maps/search" in build_search_url("maps", "london") and "london" in build_search_url("maps", "london"))
check("unknown-platform", build_search_url("unknown", "test") == "")
print("", flush=True)

# ── web_search.resolve_platform tests ──
print("=== web_search.resolve_platform ===", flush=True)
check("yt-alias", resolve_platform("yt") == "youtube")
check("videos-alias", resolve_platform("videos") == "youtube")
check("gh-alias", resolve_platform("gh") == "github")
check("maps-alias", resolve_platform("maps") == "maps")
check("search-alias", resolve_platform("search") == "google")
check("unknown-alias", resolve_platform("xyz") == "")
print("", flush=True)

# ── search_web tool tests ──
print("=== search_web tool ===", flush=True)
check("search-tool", search_web({"platform": "youtube", "query": "cat videos"}).success)
check("search-tool-unknown", not search_web({"platform": "unknown", "query": "test"}).success)
check("search-tool-no-platform", not search_web({"query": "test"}).success)
check("search-tool-no-query", not search_web({"platform": "youtube"}).success)
print("", flush=True)

# ── clipboard tests ──
print("=== clipboard_tools ===", flush=True)
# clipboard_get with mocked clipboard returns ""
check("get-empty", clipboard_get({}).success)
check("get-no-params", clipboard_get({}).success)
# clipboard_set with mocked clipboard should succeed (mock returns True by default)
check("set", clipboard_set({"text": "test"}).success)
check("set-empty", not clipboard_set({"text": ""}).success)
check("set-no-text", not clipboard_set({}).success)
check("history-empty", clipboard_history({}).success)
check("history-limit", clipboard_history({"limit": 5}).success)
print("", flush=True)

# ── system_status tests ──
print("=== system_status ===", flush=True)
s = system_status()
check("cpu-exists", "cpu_percent" in s)
check("ram-exists", "ram" in s)
check("disks-exists", "disks" in s)
check("disks-not-empty", len(s["disks"]) > 0)
check("uptime-exists", "uptime_hours" in s)
formatted = format_status(s)
check("format-string", len(formatted) > 20)
# Tool wrapper
r = get_system_status({})
check("tool-success", r.success)
check("tool-data", "cpu_percent" in (r.data or {}))
print("", flush=True)

# ── window_list tests (mocked) ──
print("=== window_tools ===", flush=True)
# With win32gui mocked, EnumWindows callback is never invoked, so list is empty
r = list_windows({})
check("list-success", r.success)
# focus_window with mocked win32gui: SetForegroundWindow raises, so it fails
r = focus_window_tool({"title": "test"})
check("focus-no-hwnd", not r.success)
check("focus-no-title", not focus_window_tool({}).success)
print("", flush=True)

# ── timer tests ──
print("=== timer_tools ===", flush=True)
r = set_timer_tool({"duration": 1, "label": "test"})
check("set-success", r.success)
check("set-has-id", r.data and "id" in r.data)
timer_id = r.data["id"] if r.data else 0
r = list_timers_tool({})
check("list-success", r.success)
check("list-has-timers", r.data and len(r.data.get("timers", [])) > 0)
r = cancel_timer_tool({"id": timer_id})
check("cancel-success", r.success)
check("cancel-unknown", not cancel_timer_tool({"id": 99999}).success)
check("set-zero", not set_timer_tool({"duration": 0}).success)
print("", flush=True)

# ── file_search tests ──
print("=== file_search ===", flush=True)
# Search current directory by name for .py files matching "test"
results = search_files("test", ".", "name", 20)
check("name-finds-results", len(results) > 0)
# Search by name with empty query (should return everything)
results_noquery = search_files("", ".", "name", 5)
check("name-empty-query", len(results_noquery) > 0)
# Search by content for a known string in test_launcher.py
results_content = search_files("clipboard", ".", "content", 20)
check("content-search-ran", True)  # search completed without error
# Search by date
results_date = search_files("", ".", "date", 5, days=365)
check("date-recent", len(results_date) > 0)
# Tool wrapper
r = search_files_tool({"query": "test", "type": "name", "max_results": 5})
check("tool-success", r.success)
check("tool-data", r.data and len(r.data.get("files", [])) > 0)
r = search_files_tool({"type": "invalid"})
check("tool-invalid-type", not r.success)
r = search_files_tool({"query": "??nonexistent_zzz??___", "type": "name"})
check("tool-no-results", r.success)  # success=True even with empty results
print("", flush=True)

# ── execute_tool routing tests ──
print("=== execute_tool routing ===", flush=True)
check("webapp-youtube", execute_tool("open_web_app", {"name": "youtube"}).success)
check("url-github", execute_tool("open_url", {"url": "https://github.com"}).success)
check("app-youtube-blocked", not execute_tool("open_app", {"name": "youtube"}).success)
check("clipboard-get-routed", execute_tool("clipboard_get", {}).success)
check("clipboard-set-routed", execute_tool("clipboard_set", {"text": "x"}).success)
check("status-routed", execute_tool("system_status", {}).success)
check("timer-set-routed", execute_tool("set_timer", {"duration": 10, "label": "x"}).success)
print("", flush=True)

print(f"=== RESULTS: {passed} passed, {failed} failed ===", flush=True)
_browser_patch.stop()
_win32gui_patch.stop()
if _ascanner._CACHE_PATH.exists():
    _ascanner._CACHE_PATH.unlink()
if __name__ == "__main__":
    sys.exit(0 if failed == 0 else 1)
