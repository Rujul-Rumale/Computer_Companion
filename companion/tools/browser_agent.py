"""General-purpose Playwright browser agent for multi-step web automation.

The LLM chains ``browser_go``, ``browser_click``, ``browser_type``, etc.
to accomplish arbitrary web tasks — WhatsApp, Gmail, Twitter, research, etc.

Singleton — one persistent Chromium profile survives across tool calls.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from config import get_config
from tools.base import ToolResult


class BrowserAgent:
    """Playwright-based browser controller with a persistent profile."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    # ── lifecycle ────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return get_config().browser_enabled

    def _ensure_browser(self):
        if not self.enabled:
            raise RuntimeError(
                "Browser automation is disabled. "
                "Set browser.enabled: true in config.yaml"
            )
        if self._browser is None:
            cfg = get_config()
            import playwright.sync_api
            self._playwright = playwright.sync_api.sync_playwright().start()
            profile_dir = Path(cfg.browser_profile_path)
            profile_dir.mkdir(parents=True, exist_ok=True)
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=cfg.browser_headless,
                no_viewport=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            pages = self._context.pages
            self._page = pages[0] if pages else self._context.new_page()
            self._browser = self._context.browser
        return self._page

    @property
    def page(self):
        self._ensure_browser()
        return self._page

    # ── browser primitives (tool handlers) ───────────────────────────────

    def navigate(self, url: str, wait_until: str = "domcontentloaded",
                 timeout_ms: int = 15000) -> ToolResult:
        try:
            p = self.page
            p.goto(url, wait_until=wait_until, timeout=timeout_ms)
            title = p.title()
            return ToolResult(True, f"Navigated to {url}",
                              {"title": title, "url": url})
        except Exception as e:
            return ToolResult(False, f"Navigation failed: {e}")

    def click(self, label: str, timeout_ms: int = 5000) -> ToolResult:
        """Click an element whose visible text matches *label*."""
        try:
            p = self.page
            elem = p.get_by_text(label, exact=False).first
            if elem.count() == 0:
                elem = p.locator(f"css=[aria-label*='{label}']").first
            if elem.count() == 0:
                elem = p.locator(f"text={label}").first
            if elem.count() == 0:
                return ToolResult(False, f"Could not find element with text: {label}")
            elem.click(timeout=timeout_ms)
            return ToolResult(True, f"Clicked: {label}")
        except Exception as e:
            return ToolResult(False, f"Click failed: {e}")

    def type_text(self, label: str, text: str,
                  timeout_ms: int = 5000) -> ToolResult:
        """Type *text* into an input field identified by *label*."""
        try:
            p = self.page
            elem = (p.get_by_label(label).first
                    if p.get_by_label(label).count() > 0
                    else p.locator(f"input[type='text']").first)
            if elem.count() == 0:
                elem = p.locator("textarea").first
            if elem.count() == 0:
                return ToolResult(False, f"Could not find input for: {label}")
            elem.click(timeout=timeout_ms)
            elem.fill("")
            elem.type(text, delay=10)
            return ToolResult(True, f"Typed into {label}")
        except Exception as e:
            return ToolResult(False, f"Type failed: {e}")

    def press_key(self, key: str) -> ToolResult:
        """Press a keyboard key (Enter, Tab, Escape, …)."""
        try:
            self.page.keyboard.press(key)
            return ToolResult(True, f"Pressed: {key}")
        except Exception as e:
            return ToolResult(False, f"Key press failed: {e}")

    def read_text(self) -> ToolResult:
        """Extract visible text from the current page."""
        try:
            text = self.page.inner_text("body")
            # Truncate to avoid blowing up the context
            text = text[:5000]
            return ToolResult(True, "Page text extracted",
                              {"text": text, "length": len(text)})
        except Exception as e:
            return ToolResult(False, f"Read failed: {e}")

    def screenshot(self) -> ToolResult:
        """Take a screenshot of the current page."""
        try:
            cfg = get_config()
            path = Path(cfg.browser_screenshot_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(path), full_page=False)
            return ToolResult(True, f"Screenshot saved to {path}",
                              {"path": str(path)})
        except Exception as e:
            return ToolResult(False, f"Screenshot failed: {e}")

    def wait(self, ms: int = 1000) -> ToolResult:
        """Wait for *ms* milliseconds."""
        try:
            time.sleep(ms / 1000.0)
            return ToolResult(True, f"Waited {ms}ms")
        except Exception as e:
            return ToolResult(False, f"Wait failed: {e}")

    def evaluate(self, js: str) -> ToolResult:
        """Run arbitrary JavaScript in the page."""
        try:
            result = self.page.evaluate(js)
            return ToolResult(True, "JS evaluated",
                              {"result": str(result)[:2000]})
        except Exception as e:
            return ToolResult(False, f"JS evaluate failed: {e}")

    # ── cleanup ──────────────────────────────────────────────────────────

    def shutdown(self):
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._browser = None
        self._page = None


# ── Singleton ────────────────────────────────────────────────────────────

_BROWSER: BrowserAgent | None = None
_LOCK = threading.Lock()


def get_browser_agent() -> BrowserAgent:
    global _BROWSER
    if _BROWSER is None:
        with _LOCK:
            if _BROWSER is None:
                _BROWSER = BrowserAgent()
    return _BROWSER
