"""
tools/app_scanner.py - Scan Windows Start Menu for installed applications.
Generates data/installed_apps.json for fuzzy app matching.
"""
import json
import os
import threading
from pathlib import Path

_INSTALLED_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "installed_apps.json"


def _scan_directory(directory: Path) -> dict[str, dict]:
    """Scan a directory for .lnk files and return {name: {path, aliases}}."""
    apps = {}
    if not directory.exists():
        return apps
    try:
        for f in directory.iterdir():
            if f.suffix.lower() == ".lnk":
                name = f.stem.lower()
                try:
                    target = _resolve_lnk(f)
                except Exception:
                    target = str(f)
                if name not in apps:
                    apps[name] = {"path": target, "aliases": []}
            elif f.is_dir():
                sub = _scan_directory(f)
                for k, v in sub.items():
                    if k not in apps:
                        apps[k] = v
    except PermissionError:
        pass
    return apps


def _resolve_lnk(lnk_path: Path) -> str:
    """Resolve a .lnk shortcut to its target path using winshell if available."""
    try:
        import winshell
        shortcut = winshell.shortcut(str(lnk_path))
        target = shortcut.path
        if target:
            return target
    except ImportError:
        pass
    except Exception:
        pass
    return str(lnk_path)


def scan_installed_apps() -> dict[str, dict]:
    """Scan Start Menu directories and return combined app map."""
    apps = {}

    system_start = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    user_start = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    for directory in [system_start, user_start]:
        apps.update(_scan_directory(directory))

    return apps


def _generate_aliases(name: str) -> list[str]:
    """Generate common aliases for an app name."""
    aliases = []
    parts = name.lower().split()
    if len(parts) > 1:
        aliases.append("".join(parts))
        aliases.append(parts[-1])
    for separator in (" - ", " ", "_", "-"):
        if separator in name:
            alias = name.lower().split(separator)[0]
            if alias != name.lower():
                aliases.append(alias)
    return list(set(aliases))


def refresh_cache() -> dict[str, dict]:
    """Scan apps, build cache, write to disk."""
    global _INSTALLED_CACHE
    with _CACHE_LOCK:
        apps = scan_installed_apps()
        enriched = {}
        for name, info in apps.items():
            enriched[name] = {
                "path": info["path"],
                "aliases": _generate_aliases(name) + info.get("aliases", []),
            }
        _INSTALLED_CACHE = enriched
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w") as f:
            json.dump(enriched, f, indent=2)
    return enriched


def load_cache() -> dict[str, dict]:
    """Load cached installed apps, scanning if missing."""
    global _INSTALLED_CACHE
    if _INSTALLED_CACHE:
        return _INSTALLED_CACHE
    with _CACHE_LOCK:
        if _INSTALLED_CACHE:
            return _INSTALLED_CACHE
        if _CACHE_PATH.exists():
            try:
                with open(_CACHE_PATH) as f:
                    _INSTALLED_CACHE = json.load(f)
                return _INSTALLED_CACHE
            except Exception:
                pass
        return refresh_cache()
