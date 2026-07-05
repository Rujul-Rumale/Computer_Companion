"""Playwright browser automation adapter (optional, disabled by default)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import get_config


@dataclass(frozen=True)
class BrowserResult:
    success: bool
    message: str
    data: dict[str, Any] | None = None


class BrowserProvider:
    def __init__(self):
        self._playwright = None
        self._browser = None

    @property
    def enabled(self) -> bool:
        return get_config().browser_enabled

    def _ensure_browser(self):
        if not self.enabled:
            raise RuntimeError("Browser automation is disabled. Set browser.enabled: true in config.yaml.")
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=get_config().browser_headless)
        return self._browser

    def navigate(self, url: str, wait_ms: int = 2000) -> BrowserResult:
        browser = self._ensure_browser()
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(wait_ms)
            title = page.title()
            content = page.content()[:50000]
            return BrowserResult(True, f"Loaded: {title}", {"title": title, "html": content, "url": url})
        except Exception as exc:
            return BrowserResult(False, str(exc))
        finally:
            page.close()

    def screenshot(self, url: str) -> BrowserResult:
        browser = self._ensure_browser()
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            path = str(get_config().browser_screenshot_path)
            page.screenshot(path=path, full_page=False)
            return BrowserResult(True, f"Screenshot saved: {path}", {"path": path, "url": url})
        except Exception as exc:
            return BrowserResult(False, str(exc))
        finally:
            page.close()

    def shutdown(self):
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None


_BROWSER_PROVIDER: BrowserProvider | None = None


def get_browser_provider() -> BrowserProvider:
    global _BROWSER_PROVIDER
    if _BROWSER_PROVIDER is None:
        _BROWSER_PROVIDER = BrowserProvider()
    return _BROWSER_PROVIDER
