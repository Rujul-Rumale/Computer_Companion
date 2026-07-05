"""Utility tools — weather, math, wikipedia, dictionary, currency, notes, time, uuid, news, network."""

from __future__ import annotations

import ast
import json
import math
import operator
import socket
import subprocess
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.parse import quote
from zoneinfo import ZoneInfo

import psutil

from tools.base import ToolResult

# ── Helpers ─────────────────────────────────────────────────────────────────────


def _get_json(url: str, timeout: int = 10) -> dict | list:
    """Simple stdlib HTTP GET → JSON, no 'requests' dependency needed."""
    resp = urllib_request.urlopen(url, timeout=timeout)
    return json.loads(resp.read().decode())


def _get_text(url: str, timeout: int = 10) -> str:
    resp = urllib_request.urlopen(url, timeout=timeout)
    return resp.read().decode()


# ── 1. calculate ────────────────────────────────────────────────────────────────

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_NAMES = {
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
    "nan": math.nan,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "degrees": math.degrees,
    "radians": math.radians,
    "ceil": math.ceil,
    "floor": math.floor,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
}


def _eval_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value) if isinstance(node.value, (int, float)) else node.value
    if isinstance(node, ast.UnaryOp):
        return _SAFE_OPS[type(node.op)](_eval_ast(node.operand))
    if isinstance(node, ast.BinOp):
        return _SAFE_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    if isinstance(node, ast.Call):
        fn = _SAFE_NAMES.get(node.func.id)
        if fn is None:
            raise ValueError(f"Unknown function: {node.func.id}")
        args = [_eval_ast(a) for a in node.args]
        kwargs = {kw.arg: _eval_ast(kw.value) for kw in node.keywords}
        return fn(*args, **kwargs)
    if isinstance(node, ast.Name):
        val = _SAFE_NAMES.get(node.id)
        if val is None:
            raise ValueError(f"Unknown name: {node.id}")
        return val
    raise ValueError(f"Unsupported expression: {type(node).__name__}")


def calculate(params: dict[str, Any]) -> ToolResult:
    expression = str(params.get("expression", "")).strip()
    if not expression:
        return ToolResult(False, "No expression provided")
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_ast(tree.body)
        label = f"{expression} = {result}"
        return ToolResult(True, label, {"expression": expression, "result": result})
    except Exception as exc:
        return ToolResult(False, f"Calculation error: {exc}")


# ── 2. uuid ─────────────────────────────────────────────────────────────────────


def generate_uuid(params: dict[str, Any]) -> ToolResult:
    version = int(params.get("version", 4))
    if version == 4:
        val = str(_uuid.uuid4())
    elif version == 1:
        val = str(_uuid.uuid1())
    elif version == 7:
        val = str(_uuid.uuid7())
    else:
        return ToolResult(False, f"Unsupported UUID version: {version}")
    return ToolResult(True, val, {"uuid": val})


# ── 3. time_in ──────────────────────────────────────────────────────────────────


_TIMEZONE_ALIASES = {
    "ist": "Asia/Kolkata",
    "pst": "US/Pacific",
    "pdt": "US/Pacific",
    "cst": "US/Central",
    "cdt": "US/Central",
    "est": "US/Eastern",
    "edt": "US/Eastern",
    "gmt": "Etc/GMT",
    "utc": "Etc/UTC",
    "bst": "Europe/London",
    "cet": "Europe/Paris",
    "eet": "Europe/Helsinki",
    "aest": "Australia/Sydney",
    "aedt": "Australia/Sydney",
    "jst": "Asia/Tokyo",
    "cst_china": "Asia/Shanghai",
    "hkt": "Asia/Hong_Kong",
    "sgt": "Asia/Singapore",
}


def time_in(params: dict[str, Any]) -> ToolResult:
    tz_name = str(params.get("timezone", "")).strip()
    tz_name2 = str(params.get("target_timezone", "")).strip()
    tz_name = tz_name or tz_name2

    if not tz_name:
        return ToolResult(False, "No timezone provided")

    alias = _TIMEZONE_ALIASES.get(tz_name.lower().replace(" ", "_"))
    if alias:
        tz_name = alias

    try:
        tz = ZoneInfo(tz_name)
    except KeyError:
        return ToolResult(False, f"Unknown timezone: {tz_name}")

    now = datetime.now(tz)
    return ToolResult(True, now.strftime("%A, %d %B %Y %I:%M:%S %p %Z"), {
        "timezone": str(tz),
        "time": now.isoformat(),
    })


# ── 4. dictionary ───────────────────────────────────────────────────────────────


def dictionary_lookup(params: dict[str, Any]) -> ToolResult:
    word = str(params.get("word", "")).strip()
    if not word:
        return ToolResult(False, "No word provided")

    try:
        data = _get_json(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}"
        )
        if isinstance(data, list) and len(data) > 0:
            entry = data[0]
        else:
            return ToolResult(False, f"No definition found for '{word}'")
    except Exception as exc:
        return ToolResult(False, f"Dictionary lookup failed: {exc}")

    phonetic = entry.get("phonetic") or ""
    meanings = entry.get("meanings", [])
    lines = [f"**{word}**{f' ({phonetic})' if phonetic else ''}"]
    for m in meanings[:3]:
        pos = m.get("partOfSpeech", "")
        defs = m.get("definitions", [])
        if defs:
            d = defs[0]
            definition = d.get("definition", "")
            example = d.get("example", "")
            lines.append(f"  *({pos})* {definition}")
            if example:
                lines.append(f"    *\"{example}\"*")
    return ToolResult(True, "\n".join(lines), {"word": word, "phonetic": phonetic, "data": entry})


# ── 5. currency_convert ────────────────────────────────────────────────────────


def currency_convert(params: dict[str, Any]) -> ToolResult:
    amount = float(params.get("amount", 1))
    from_cur = str(params.get("from", "")).upper().strip()
    to_cur = str(params.get("to", "")).upper().strip()
    if not from_cur or not to_cur:
        return ToolResult(False, "Both 'from' and 'to' currencies required")

    try:
        data = _get_json(
            f"https://api.frankfurter.app/latest?from={from_cur}&to={to_cur}"
        )
        rate = data.get("rates", {}).get(to_cur)
        if rate is None:
            return ToolResult(False, f"Currency pair not supported: {from_cur} → {to_cur}")
        converted = round(amount * rate, 2)
        return ToolResult(
            True,
            f"{amount} {from_cur} = {converted} {to_cur} (rate: {rate})",
            {"amount": amount, "from": from_cur, "to": to_cur, "rate": rate, "result": converted},
        )
    except Exception as exc:
        return ToolResult(False, f"Currency conversion failed: {exc}")


# ── 6. get_weather ──────────────────────────────────────────────────────────────


def get_weather(params: dict[str, Any]) -> ToolResult:
    city = str(params.get("city", "")).strip()
    if not city:
        return ToolResult(False, "No city provided")

    try:
        text = _get_text(
            f"https://wttr.in/{quote(city)}?format=%C+%t+%h+%w"
        ).strip()
        if "Unknown location" in text or "Sorry" in text:
            return ToolResult(False, f"Weather not found for: {city}")
        return ToolResult(True, f"{city}: {text}", {"city": city, "raw": text})
    except Exception as exc:
        return ToolResult(False, f"Weather fetch failed: {exc}")


# ── 7. wikipedia ────────────────────────────────────────────────────────────────


def wikipedia_search(params: dict[str, Any]) -> ToolResult:
    query = str(params.get("query", "")).strip()
    if not query:
        return ToolResult(False, "No search query provided")

    try:
        data = _get_json(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(query)}"
        )
    except Exception as exc:
        return ToolResult(False, f"Wikipedia lookup failed: {exc}")

    title = data.get("title", query)
    extract = data.get("extract", "")
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    snippet = extract[:2000]
    if len(extract) > 2000:
        snippet += "\n\n[truncated — full article on Wikipedia]"

    lines = [f"**{title}**"]
    if data.get("description"):
        lines.append(f"*{data['description']}*")
    lines.append("")
    lines.append(snippet)
    if url:
        lines.append(f"\nFull article: {url}")

    return ToolResult(True, "\n".join(lines), {
        "title": title,
        "extract": extract,
        "url": url,
        "description": data.get("description"),
    })


# ── 8. news_headlines ───────────────────────────────────────────────────────────


def news_headlines(params: dict[str, Any]) -> ToolResult:
    from tools.registry import execute_tool
    topic = str(params.get("topic", "latest news India today")).strip()
    count = int(params.get("count", 5))
    result = execute_tool("web_search_results", {"query": topic, "count": min(count, 10)})
    return result


# ── 9. notes ───────────────────────────────────────────────────────────────────


_NOTES_PATH = Path(__file__).resolve().parent.parent / "data" / "notes.json"


def _load_notes() -> list[dict]:
    if not _NOTES_PATH.exists():
        return []
    try:
        with open(_NOTES_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_notes(notes: list[dict]):
    _NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_NOTES_PATH, "w") as f:
        json.dump(notes, f, indent=2)


def notes_create(params: dict[str, Any]) -> ToolResult:
    title = str(params.get("title", "Untitled")).strip()
    content = str(params.get("content", "")).strip()
    if not content:
        return ToolResult(False, "Note content is empty")
    notes = _load_notes()
    note = {
        "id": str(_uuid.uuid4()),
        "title": title,
        "content": content,
        "created": datetime.now().isoformat(),
    }
    notes.append(note)
    _save_notes(notes)
    return ToolResult(True, f"Note created: {title}", {"id": note["id"], **note})


def notes_list(params: dict[str, Any]) -> ToolResult:
    notes = _load_notes()
    if not notes:
        return ToolResult(True, "No notes saved")
    lines = [f"{i+1}. [{n['id'][:8]}] {n['title']}" for i, n in enumerate(notes)]
    return ToolResult(True, f"Saved notes ({len(notes)}):\n" + "\n".join(lines), {"notes": notes})


def notes_read(params: dict[str, Any]) -> ToolResult:
    note_id = str(params.get("id", "")).strip()
    if not note_id:
        return ToolResult(False, "Note ID required")
    notes = _load_notes()
    for n in notes:
        if n["id"] == note_id or n["id"].startswith(note_id):
            return ToolResult(True, f"**{n['title']}**\n{n['content']}", n)
    return ToolResult(False, f"Note not found: {note_id}")


def notes_delete(params: dict[str, Any]) -> ToolResult:
    note_id = str(params.get("id", "")).strip()
    if not note_id:
        return ToolResult(False, "Note ID required")
    notes = _load_notes()
    kept = [n for n in notes if n["id"] != note_id and not n["id"].startswith(note_id)]
    if len(kept) == len(notes):
        return ToolResult(False, f"Note not found: {note_id}")
    _save_notes(kept)
    return ToolResult(True, f"Deleted note: {note_id}")


# ── 10. network_info ────────────────────────────────────────────────────────────


def network_info(params: dict[str, Any]) -> ToolResult:
    data = {}
    lines = []

    try:
        ip_data = _get_json("https://api.ipify.org?format=json")
        ip = ip_data.get("ip", "")
        data["public_ip"] = ip
        lines.append(f"Public IP: {ip}")
    except Exception:
        data["public_ip"] = None
        lines.append("Public IP: unavailable")

    try:
        host = socket.gethostname()
        local_ip = socket.gethostbyname(host)
        data["hostname"] = host
        data["local_ip"] = local_ip
        lines.append(f"Hostname: {host}")
        lines.append(f"Local IP: {local_ip}")
    except Exception:
        pass

    try:
        ping = subprocess.run(
            ["ping", "-n", "1", "8.8.8.8"],
            capture_output=True, text=True, timeout=5,
        )
        for line in ping.stdout.splitlines():
            if "ms" in line and "time" in line:
                data["ping_ms"] = line.strip()
                lines.append(f"Ping 8.8.8.8: {line.strip()}")
                break
    except Exception:
        data["ping_ms"] = None

    addrs = psutil.net_if_addrs()
    io = psutil.net_io_counters()
    interfaces = {}
    for name, snics in addrs.items():
        for snic in snics:
            if snic.family == 2:
                interfaces[name] = snic.address
    data["interfaces"] = interfaces
    data["bytes_sent"] = io.bytes_sent
    data["bytes_recv"] = io.bytes_recv

    lines.append(f"Interfaces: {', '.join(f'{k}={v}' for k, v in interfaces.items())}")
    lines.append(f"Sent: {io.bytes_sent:,} bytes | Received: {io.bytes_recv:,} bytes")

    return ToolResult(True, "\n".join(lines), data)
