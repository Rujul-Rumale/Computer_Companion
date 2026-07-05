"""Free search provider adapters with a SearXNG-first path and URL fallback."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: list[SearchResult] = field(default_factory=list)
    provider: str = "fallback"
    fallback_url: str = ""
    error: str = ""


class SearchProvider:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("COMPANION_SEARXNG_URL", "")).strip().rstrip("/")

    def search(self, query: str, limit: int = 5) -> SearchResponse:
        query = (query or "").strip()
        if not query:
            return SearchResponse(query="", results=[], error="No query provided")

        if self.base_url:
            try:
                params = urlencode({"q": query, "format": "json", "language": "en"})
                request = Request(f"{self.base_url}/search?{params}", headers={"User-Agent": "Companion/1.0"})
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8", errors="replace"))
                items = []
                for entry in payload.get("results", [])[:limit]:
                    items.append(
                        SearchResult(
                            title=str(entry.get("title") or entry.get("url") or "Result"),
                            url=str(entry.get("url") or ""),
                            snippet=str(entry.get("content") or ""),
                        )
                    )
                return SearchResponse(query=query, results=items, provider="searxng")
            except Exception as exc:
                return SearchResponse(
                    query=query,
                    results=[],
                    provider="searxng",
                    fallback_url=self.fallback_url(query),
                    error=str(exc),
                )

        return SearchResponse(
            query=query,
            results=[],
            provider="fallback",
            fallback_url=self.fallback_url(query),
        )

    def fallback_url(self, query: str) -> str:
        return f"https://duckduckgo.com/?q={quote_plus(query)}"


_SEARCH_PROVIDER: SearchProvider | None = None


def get_search_provider() -> SearchProvider:
    global _SEARCH_PROVIDER
    if _SEARCH_PROVIDER is None:
        try:
            from config import get_config
            url = get_config().search_searxng_url
        except Exception:
            url = ""
        _SEARCH_PROVIDER = SearchProvider(base_url=url or None)
    return _SEARCH_PROVIDER
