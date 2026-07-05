"""
tools/web_search.py - Search platform URL builder for web search actions.
"""
from urllib.parse import quote_plus

SEARCH_URLS = {
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "google": "https://www.google.com/search?q={query}",
    "amazon": "https://www.amazon.in/s?k={query}",
    "github": "https://github.com/search?q={query}",
    "maps": "https://www.google.com/maps/search/{query}",
    "reddit": "https://www.reddit.com/search/?q={query}",
    "scholar": "https://scholar.google.com/scholar?q={query}",
    "stackoverflow": "https://stackoverflow.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
}

PLATFORM_ALIASES = {
    "yt": "youtube",
    "videos": "youtube",
    "shop": "amazon",
    "store": "amazon",
    "gh": "github",
    "map": "maps",
    "so": "stackoverflow",
    "stack overflow": "stackoverflow",
    "reddit": "reddit",
    "scholar": "scholar",
    "search": "google",
}


def resolve_platform(name: str) -> str:
    key = name.strip().lower()
    if key in SEARCH_URLS:
        return key
    return PLATFORM_ALIASES.get(key, "")


def build_search_url(platform: str, query: str) -> str:
    canonical = resolve_platform(platform)
    if not canonical:
        return ""
    template = SEARCH_URLS[canonical]
    return template.format(query=quote_plus(query))
