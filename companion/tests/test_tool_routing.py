import unittest.mock
from pathlib import Path

import pytest

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


@pytest.fixture(autouse=True)
def _setup_mocks():
    # Isolate app cache so tests don't depend on installed apps
    import tools.app_scanner as _ascanner
    _orig_cache = _ascanner._CACHE_PATH
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        import json
        json.dump({}, tmp)
        tmp_path = tmp.name
    _ascanner._CACHE_PATH = Path(tmp_path)

    from contextlib import suppress

    with (
        unittest.mock.patch("tools.registry.webbrowser.open", return_value=True),
        unittest.mock.patch("tools.window_tools.win32gui"),
    ):
        from tools.clipboard import _get_manager
        _get_manager().start_watcher()
        yield
    _ascanner._CACHE_PATH = _orig_cache
    with suppress(OSError):
        Path(tmp_path).unlink()


class TestResolveWebApp:
    def test_youtube(self):
        assert resolve_web_app("youtube") == "https://youtube.com"

    def test_yt_alias(self):
        assert resolve_web_app("yt") == "https://youtube.com"

    def test_gmail(self):
        assert resolve_web_app("gmail") == "https://mail.google.com"

    def test_email_alias(self):
        assert resolve_web_app("email") == "https://mail.google.com"

    def test_amazon(self):
        assert resolve_web_app("amazon") == "https://amazon.com"

    def test_github(self):
        assert resolve_web_app("github") == "https://github.com"

    def test_unknown_returns_empty(self):
        assert resolve_web_app("unknown123") == ""


class TestOpenUrl:
    def test_explicit_url(self):
        assert open_url({"url": "https://example.com"}).success

    def test_auto_https(self):
        assert open_url({"url": "example.com"}).success

    def test_no_url_fails(self):
        assert not open_url({}).success


class TestOpenWebApp:
    def test_youtube(self):
        assert open_web_app({"name": "youtube"}).success

    def test_gmail(self):
        assert open_web_app({"name": "gmail"}).success

    def test_unknown_fails(self):
        assert not open_web_app({"name": "unknownxyz"}).success


class TestOpenApp:
    def test_unknown_app_fails(self):
        name = "qwertyuioplkjhgfdsazxcvbnm" * 8
        result = open_app({"name": name})
        assert not result.success
        # open_app should suggest using open_web_app for unrecognized names
        assert "open_web_app" in result.message


class TestWebSearch:
    def test_build_youtube_search_url(self):
        url = build_search_url("youtube", "mark rober")
        assert "youtube.com/results" in url
        assert "mark+rober" in url

    def test_build_google_search_url(self):
        url = build_search_url("google", "python tutorial")
        assert "google.com/search" in url
        assert "python+tutorial" in url

    def test_build_amazon_search_url(self):
        url = build_search_url("amazon", "chair")
        assert "amazon" in url
        assert "chair" in url

    def test_build_github_search_url(self):
        url = build_search_url("github", "opencode")
        assert "github.com/search" in url
        assert "opencode" in url

    def test_build_maps_search_url(self):
        url = build_search_url("maps", "london")
        assert "google.com/maps/search" in url
        assert "london" in url

    def test_unknown_platform(self):
        assert build_search_url("unknown", "test") == ""


class TestResolvePlatform:
    def test_youtube_alias(self):
        assert resolve_platform("yt") == "youtube"

    def test_videos_alias(self):
        assert resolve_platform("videos") == "youtube"

    def test_github_alias(self):
        assert resolve_platform("gh") == "github"

    def test_maps_alias(self):
        assert resolve_platform("maps") == "maps"

    def test_search_alias(self):
        assert resolve_platform("search") == "google"

    def test_unknown(self):
        assert resolve_platform("xyz") == ""


class TestSearchWebTool:
    def test_valid_search(self):
        assert search_web({"platform": "youtube", "query": "cat videos"}).success

    def test_unknown_platform(self):
        assert not search_web({"platform": "unknown", "query": "test"}).success

    def test_no_platform(self):
        assert not search_web({"query": "test"}).success

    def test_no_query(self):
        assert not search_web({"platform": "youtube"}).success


class TestClipboard:
    def test_get_empty_succeeds(self):
        assert clipboard_get({}).success

    def test_get_no_params_succeeds(self):
        assert clipboard_get({}).success

    def test_set_succeeds(self):
        assert clipboard_set({"text": "test"}).success

    def test_set_empty_fails(self):
        assert not clipboard_set({"text": ""}).success

    def test_set_no_text_fails(self):
        assert not clipboard_set({}).success

    def test_history_empty(self):
        assert clipboard_history({}).success

    def test_history_with_limit(self):
        assert clipboard_history({"limit": 5}).success


class TestSystemStatus:
    def test_status_keys_present(self):
        s = system_status()
        assert "cpu_percent" in s
        assert "ram" in s
        assert "disks" in s
        assert len(s["disks"]) > 0
        assert "uptime_hours" in s

    def test_format_length(self):
        s = system_status()
        formatted = format_status(s)
        assert len(formatted) > 20

    def test_tool_wrapper(self):
        r = get_system_status({})
        assert r.success
        assert "cpu_percent" in (r.data or {})


class TestWindowTools:
    def test_list_succeeds(self):
        r = list_windows({})
        assert r.success

    def test_focus_no_title(self):
        assert not focus_window_tool({}).success


class TestTimers:
    def test_set_and_list(self):
        r = set_timer_tool({"duration": 1, "label": "test"})
        assert r.success
        assert r.data and "id" in r.data
        timer_id = r.data["id"]

        r = list_timers_tool({})
        assert r.success
        assert r.data and len(r.data.get("timers", [])) > 0

        r = cancel_timer_tool({"id": timer_id})
        assert r.success

    def test_cancel_unknown(self):
        assert not cancel_timer_tool({"id": 99999}).success

    def test_set_zero_duration(self):
        assert not set_timer_tool({"duration": 0}).success


class TestFileSearch:
    def test_name_finds_self(self):
        results = search_files("test", ".", "name", 10)
        assert any("test_" in r["name"] for r in results)

    def test_name_empty_query(self):
        results = search_files("", ".", "name", 5)
        assert len(results) > 0

    def test_content_search(self):
        results = search_files("clipboard", ".", "content", 5)
        assert any("clipboard" in r.get("snippet", "") for r in results)

    def test_date_search(self):
        results = search_files("", ".", "date", 5, days=365)
        assert len(results) > 0

    def test_tool_wrapper(self):
        r = search_files_tool({"query": "test", "type": "name", "max_results": 5})
        assert r.success
        assert r.data and len(r.data.get("files", [])) > 0

    def test_tool_invalid_type(self):
        r = search_files_tool({"type": "invalid"})
        assert not r.success

    def test_tool_no_results(self):
        r = search_files_tool({"query": "??nonexistent_zzz??___", "type": "name"})
        assert r.success


class TestExecuteToolRouting:
    def test_webapp_youtube(self):
        assert execute_tool("open_web_app", {"name": "youtube"}).success

    def test_url_github(self):
        assert execute_tool("open_url", {"url": "https://github.com"}).success

    def test_app_unknown_fails(self):
        assert not execute_tool("open_app", {"name": "zzz_tool_test_nonexistent_xyz"}).success

    def test_clipboard_get(self):
        assert execute_tool("clipboard_get", {}).success

    def test_clipboard_set(self):
        assert execute_tool("clipboard_set", {"text": "x"}).success

    def test_system_status(self):
        assert execute_tool("system_status", {}).success

    def test_timer_set(self):
        assert execute_tool("set_timer", {"duration": 10, "label": "x"}).success
