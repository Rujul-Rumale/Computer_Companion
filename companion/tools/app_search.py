"""
tools/app_search.py - Fuzzy app name resolution using rapidfuzz.
"""
from tools.app_scanner import load_cache


def _get_fuzzy_scorer():
    try:
        from rapidfuzz import fuzz
        return fuzz
    except ImportError:
        return None


def fuzzy_find_app(query: str, threshold: int = 60) -> tuple[str, dict]:
    """Find an installed app by fuzzy name matching. Returns (name, info) or ("", {})."""
    apps = load_cache()
    if not apps:
        return "", {}

    query = query.strip().lower()
    if query in apps:
        return query, apps[query]

    fuzz = _get_fuzzy_scorer()
    if fuzz is None:
        return "", {}

    best_score = 0
    best_name = ""

    for name, info in apps.items():
        score = fuzz.ratio(query, name.lower())
        if score > best_score:
            best_score = score
            best_name = name

        for alias in info.get("aliases", []):
            alias_score = fuzz.ratio(query, alias.lower())
            if alias_score > best_score:
                best_score = alias_score
                best_name = name

        if fuzz.partial_ratio(query, name.lower()) > best_score:
            best_score = fuzz.partial_ratio(query, name.lower())
            best_name = name

    if best_score >= threshold and best_name:
        return best_name, apps[best_name]

    return "", {}
