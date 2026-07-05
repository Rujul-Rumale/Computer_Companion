"""Free web research tools — DuckDuckGo search + trafilatura page extraction."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any

from tools.registry import ToolResult


def web_search_results(params: dict[str, Any]) -> ToolResult:
    query = str(params.get("query", "")).strip()
    count = min(int(params.get("count", 5) or params.get("max_results", 5)), 10)
    if not query:
        return ToolResult(False, "query is required")

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=count))
    except ImportError:
        return ToolResult(False, "Web search library not installed (ddgs or duckduckgo_search)")
    except Exception as exc:
        return ToolResult(False, f"Web search failed: {exc}")

    if not raw:
        return ToolResult(True, f"No results for '{query}'.", {"results": []})

    lines = []
    data_results = []
    for r in raw:
        title = r.get("title", "").strip()
        url = r.get("href", "").strip()
        snippet = r.get("body", "").strip()
        lines.append(f"Title: {title}\nURL: {url}\nSnippet: {snippet}")
        data_results.append({"title": title, "url": url, "snippet": snippet})

    body = f"Search results for '{query}':\n\n" + "\n\n".join(lines)
    return ToolResult(True, body[:8000], {"results": data_results, "provider": "duckduckgo"})


def web_read_page(params: dict[str, Any]) -> ToolResult:
    url = str(params.get("url", "")).strip()
    max_chars = min(int(params.get("max_chars", 8000)), 50000)
    if not url:
        return ToolResult(False, "url is required")
    if not url.startswith("http"):
        url = "https://" + url

    try:
        import trafilatura
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(trafilatura.fetch_url, url)
            try:
                downloaded = future.result(timeout=15)
            except FuturesTimeout:
                return ToolResult(False, f"Timeout fetching URL: {url}")
        if not downloaded:
            return ToolResult(False, f"Could not fetch URL: {url}")
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=True) or ""
        if not text.strip():
            return ToolResult(False, f"No readable content extracted from {url}")
    except ImportError:
        # fallback: requests + html2text
        try:
            import html2text
            import requests
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            text = converter.handle(resp.text)
        except Exception as exc:
            return ToolResult(False, f"Failed to read page: {exc}")
    except Exception as exc:
        return ToolResult(False, f"Failed to read page: {exc}")

    text = text[:max_chars]
    if len(text) >= max_chars:
        text += "\n\n[truncated]"
    return ToolResult(True, text, {"url": url, "chars": len(text)})


def web_search_deep(params: dict[str, Any]) -> ToolResult:
    """Search + auto-read the top result in one call."""
    query = str(params.get("query", "")).strip()
    if not query:
        return ToolResult(False, "query is required")

    # First, search
    search_result = web_search_results({"query": query, "count": 1})
    if not search_result.success:
        return search_result

    results = search_result.data.get("results", [])
    if not results:
        return ToolResult(False, f"No results for '{query}'")

    top = results[0]
    top_url = top.get("url", "")
    if not top_url:
        return search_result  # search result snippet is all we have

    # Read the page
    page_result = web_read_page({"url": top_url, "max_chars": 6000})
    if not page_result.success:
        # fallback: return search results
        return search_result

    combined = (
        f"Deep search: {query}\n\n"
        f"Top result: {top.get('title')}\n{top_url}\n\n"
        f"{page_result.message}"
    )
    return ToolResult(
        True,
        combined,
        {
            "query": query,
            "source_url": top_url,
            "source_title": top.get("title"),
            "search_snippet": top.get("snippet"),
            "page_content": page_result.message,
        },
    )
