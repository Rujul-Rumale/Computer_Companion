"""
tools/file_search.py — Search files by name, content, or date.
"""

from __future__ import annotations

import fnmatch
import os
import time
from pathlib import Path

_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".csv", ".log", ".sh", ".bat", ".ps1", ".env",
    ".c", ".cpp", ".h", ".hpp", ".java", ".rs", ".go", ".rb", ".php",
    ".sql", ".r", ".m", ".swift", ".kt", ".scala", ".lua",
    ".dockerfile", ".makefile", ".cmake",
}

_MAX_CONTENT_SIZE = 10 * 1024 * 1024  # 10 MB max file size for content search
_MAX_RESULTS = 30
_MAX_CONTENT_MATCHES = 50


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return not bool(chunk.translate(None, bytes(range(32, 127)) + b"\n\r\t\f\b"))
    except Exception:
        return False


def _search_by_name(
    query: str,
    directory: Path,
    max_results: int,
) -> list[dict]:
    results = []
    query_lower = query.lower()
    try:
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                if len(results) >= max_results:
                    break
                if fnmatch.fnmatch(fname.lower(), f"*{query_lower}*") or query_lower in fname.lower():
                    fpath = Path(root) / fname
                    try:
                        stat = fpath.stat()
                        results.append({
                            "path": str(fpath),
                            "name": fname,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                        })
                    except OSError:
                        continue
            if len(results) >= max_results:
                break
    except PermissionError:
        pass
    return results


def _search_by_content(
    query: str,
    directory: Path,
    max_results: int,
) -> list[dict]:
    results = []
    query_lower = query.lower()
    total_read = 0
    try:
        for root, _dirs, files in os.walk(directory):
            if total_read > _MAX_CONTENT_MATCHES:
                break
            for fname in files:
                if len(results) >= max_results or total_read > _MAX_CONTENT_MATCHES:
                    break
                fpath = Path(root) / fname
                try:
                    if fpath.stat().st_size > _MAX_CONTENT_SIZE:
                        continue
                    if not _is_text_file(fpath):
                        continue
                except OSError:
                    continue
                try:
                    with open(fpath, encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            if query_lower in line.lower():
                                results.append({
                                    "path": str(fpath),
                                    "name": fname,
                                    "line": lineno,
                                    "snippet": line.strip()[:200],
                                })
                                total_read += 1
                                if len(results) >= max_results:
                                    break
                except Exception:
                    continue
    except PermissionError:
        pass
    return results


def _search_by_date(
    days: int,
    directory: Path,
    max_results: int,
) -> list[dict]:
    cutoff = time.time() - (days * 86400)
    results = []
    try:
        for root, _dirs, files in os.walk(directory):
            for fname in files:
                if len(results) >= max_results:
                    break
                fpath = Path(root) / fname
                try:
                    mtime = fpath.stat().st_mtime
                    if mtime >= cutoff:
                        results.append({
                            "path": str(fpath),
                            "name": fname,
                            "size": fpath.stat().st_size,
                            "modified": mtime,
                        })
                except OSError:
                    continue
            if len(results) >= max_results:
                break
    except PermissionError:
        pass
    return results


def search_files(
    query: str = "",
    directory: str = "",
    search_type: str = "name",
    max_results: int = 20,
    days: int = 7,
) -> list[dict]:
    base = Path(directory).resolve() if directory else Path.cwd()

    if not base.exists():
        return []

    max_results = min(max_results, _MAX_RESULTS)

    if search_type == "content":
        return _search_by_content(query, base, max_results)
    elif search_type == "date":
        return _search_by_date(days, base, max_results)
    else:
        return _search_by_name(query, base, max_results)
