"""
memory/store.py - SQLite-backed persistent memory
"""
import json
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from config import get_config

_conn: sqlite3.Connection | None = None
_conn_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        with _conn_lock:
            if _conn is None:
                cfg = get_config()
                db = Path(cfg.db_path)
                db.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(db), check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA busy_timeout=5000")
                _conn = conn
    return _conn


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            relationship TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, key)
        );

        CREATE TABLE IF NOT EXISTS conversation_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            turn_count INTEGER DEFAULT 0,
            topics TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversation_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_call TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS session_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS window_focus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            process_name TEXT,
            class_name TEXT,
            duration_seconds REAL DEFAULT 0,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


# ── Projects ──────────────────────────────────────────────────────────────────

def add_project(name: str, description: str = "", status: str = "active", notes: str = "") -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO projects (name, description, status, notes) VALUES (?, ?, ?, ?)",
        (name, description, status, notes)
    )
    conn.commit()
    pid = cur.lastrowid
    return pid


def update_project(pid: int, **kwargs):
    allowed = {"name", "description", "status", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.now().isoformat()
    cols = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [pid]
    conn = _get_conn()
    conn.execute(f"UPDATE projects SET {cols} WHERE id=?", vals)
    conn.commit()



def get_projects(status: str | None = None) -> list[dict]:
    conn = _get_conn()
    if status:
        rows = conn.execute("SELECT * FROM projects WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()

    return [dict(r) for r in rows]


def get_project_by_name(name: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM projects WHERE name LIKE ?", (f"%{name}%",)).fetchone()

    return dict(row) if row else None


# ── People ─────────────────────────────────────────────────────────────────────

def add_person(name: str, relationship: str = "", notes: str = "") -> int:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO people (name, relationship, notes) VALUES (?, ?, ?)", (name, relationship, notes))
    conn.commit()
    pid = cur.lastrowid

    return pid


def get_people() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM people ORDER BY name").fetchall()

    return [dict(r) for r in rows]


def update_person(pid: int, **kwargs):
    allowed = {"name", "relationship", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [pid]
    conn = _get_conn()
    conn.execute(f"UPDATE people SET {cols} WHERE id=?", vals)
    conn.commit()



# ── Facts ──────────────────────────────────────────────────────────────────────

def set_fact(category: str, key: str, value: str):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO facts (category, key, value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(category, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (category, key, value))
    conn.commit()



def get_fact(category: str, key: str) -> str | None:
    conn = _get_conn()
    row = conn.execute("SELECT value FROM facts WHERE category=? AND key=?", (category, key)).fetchone()

    return row["value"] if row else None


def get_facts_by_category(category: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM facts WHERE category=?", (category,)).fetchall()

    return [dict(r) for r in rows]


def get_all_facts() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM facts ORDER BY category, key").fetchall()

    return [dict(r) for r in rows]


# ── Conversation turns ─────────────────────────────────────────────────────────

def save_turn(session_id: str, role: str, content: str, tool_call: str | None = None):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO conversation_turns (session_id, role, content, tool_call) VALUES (?, ?, ?, ?)",
        (session_id, role, content, tool_call)
    )
    conn.commit()



def get_recent_turns(session_id: str, limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM conversation_turns WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit)
    ).fetchall()

    return list(reversed([dict(r) for r in rows]))


def count_turns(session_id: str) -> int:
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) as c FROM conversation_turns WHERE session_id=?", (session_id,)).fetchone()

    return row["c"]


# ── Summaries ──────────────────────────────────────────────────────────────────

def save_summary(session_id: str, summary: str, turn_count: int, topics: list[str]):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO conversation_summaries (session_id, summary, turn_count, topics) VALUES (?, ?, ?, ?)",
        (session_id, summary, turn_count, json.dumps(topics))
    )
    conn.commit()



def get_recent_summaries(limit: int = 3) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM conversation_summaries ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()

    return [dict(r) for r in rows]


# ── Session Context (cross-session persistence) ────────────────────────────────

def set_session_context(key: str, value: str):
    """Persist a key-value pair across sessions (e.g. last_active_window, last_project)."""
    conn = _get_conn()
    conn.execute("""
        INSERT INTO session_context (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (key, value))
    conn.commit()



def get_session_context(key: str) -> str | None:
    conn = _get_conn()
    row = conn.execute("SELECT value FROM session_context WHERE key=?", (key,)).fetchone()

    return row["value"] if row else None


def get_all_session_context() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM session_context ORDER BY updated_at DESC").fetchall()

    return [dict(r) for r in rows]


def clear_session_context(key: str | None = None):
    conn = _get_conn()
    if key:
        conn.execute("DELETE FROM session_context WHERE key=?", (key,))
    else:
        conn.execute("DELETE FROM session_context")
    conn.commit()



# ── Window Focus Context ───────────────────────────────────────────────────────

def record_window_focus(title: str, process_name: str = "", class_name: str = ""):
    """Record or update a window focus entry. If the same title/process exists,
    update last_seen and accumulate duration."""
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id, first_seen FROM window_focus WHERE title=? AND process_name=?",
        (title, process_name)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE window_focus SET last_seen=CURRENT_TIMESTAMP, class_name=? WHERE id=?",
            (class_name, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO window_focus (title, process_name, class_name) VALUES (?, ?, ?)",
            (title, process_name, class_name)
        )
    conn.commit()



def get_recent_window_focus(limit: int = 5) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM window_focus ORDER BY last_seen DESC LIMIT ?", (limit,)
    ).fetchall()

    return [dict(r) for r in rows]


def build_active_window_context(title: str = "", process_name: str = "") -> str:
    """Build a short context string describing the user's current active window."""
    if not title and not process_name:
        return ""
    parts = []
    if title:
        parts.append(f"Window: {title}")
    if process_name:
        parts.append(f"Application: {process_name}")
    return "Active window: " + " | ".join(parts)


def build_session_context_block(user_message: str = "") -> str:
    """Build a [PREVIOUS SESSION] context block from persisted session_context entries.
    Only returns content when the user explicitly asks about previous sessions.
    """
    needs_context = bool(re.search(
        r"\b(restore|resume|reopen|reload|what\s+were\s+we|where\s+were\s+we|"
        r"last\s+(project|session)|previous|left\s+off|pick\s+up|back\s+to)\b",
        user_message or "", re.IGNORECASE,
    ))
    if not needs_context:
        return ""
    ctx = get_all_session_context()
    if not ctx:
        return ""
    lines = []
    for entry in ctx:
        key = entry.get("key", "")
        val = entry.get("value", "")
        if key in ("last_project", "last_task"):
            lines.append(f"  - {key.replace('_', ' ').title()}: {val}")
    if not lines:
        return ""
    return "\n\n[PREVIOUS SESSION CONTEXT]\n" + "\n".join(lines) + "\n[/PREVIOUS SESSION CONTEXT]"


# ── Context builder ────────────────────────────────────────────────────────────

_GENERIC_GREETING_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|sup|good\s+(morning|afternoon|evening)|"
    r"what'?s\s+up|how\s+are\s+you)[!.?\s]*$",
    re.IGNORECASE,
)
_PROJECT_ACTIVATION_RE = re.compile(
    r"\b(continue|resume|load|open|switch\s+to|work\s+on|back\s+to|"
    r"pick\s+up|start|activate)\b",
    re.IGNORECASE,
)
_SUMMARY_REQUEST_RE = re.compile(
    r"\b(what\s+did\s+we|where\s+did\s+we|where\s+were\s+we|left\s+off|"
    r"recap|summari[sz]e|previous\s+session|last\s+time)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+\-_.]*", re.IGNORECASE)
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "about",
    "project", "task", "topic", "current", "continue", "resume", "load",
    "open", "work", "start", "help", "today", "please", "can", "you",
}


def _tokens(text: str) -> set[str]:
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if len(t) > 2 and t.lower() not in _STOPWORDS
    }


def _is_generic_greeting(text: str) -> bool:
    return bool(_GENERIC_GREETING_RE.match(text or ""))


def _project_tokens(project: dict) -> set[str]:
    return _tokens(" ".join([
        project.get("name") or "",
        project.get("description") or "",
        project.get("notes") or "",
    ]))


def find_relevant_projects(user_message: str, limit: int | None = None) -> list[dict]:
    """Returns active projects explicitly mentioned by the user message."""
    if _is_generic_greeting(user_message):
        return []

    msg = user_message or ""
    msg_lower = msg.lower()
    msg_tokens = _tokens(msg)
    if not msg_tokens:
        return []

    matches = []
    for project in get_projects(status="active"):
        name = (project.get("name") or "").lower()
        name_tokens = _tokens(name)
        overlap = msg_tokens & _project_tokens(project)
        mentioned_by_name = name and name in msg_lower
        mentioned_by_key_terms = bool(name_tokens and (msg_tokens & name_tokens))
        explicitly_loaded = bool(_PROJECT_ACTIVATION_RE.search(msg)) and (mentioned_by_name or overlap)

        if mentioned_by_name or mentioned_by_key_terms or explicitly_loaded:
            project = dict(project)
            project["_relevance"] = len(overlap) + (3 if mentioned_by_name else 0)
            matches.append(project)

    matches.sort(key=lambda p: p.get("_relevance", 0), reverse=True)
    return matches[:limit] if limit else matches


def build_memory_context(
    user_message: str = "",
    session_memory: dict | None = None,
    active_window_info: dict | None = None,
) -> str:
    """Assembles only conversation-relevant memory into a context block.
    active_window_info: optional dict with title, process_name keys from ActiveWindowTracker.
    """
    cfg = get_config()
    parts = []
    session_memory = session_memory or {}
    session_project = session_memory.get("current_project")
    session_topic = session_memory.get("current_topic") or ""
    session_task = session_memory.get("current_task") or ""
    user_message = user_message or ""

    session_lines = []
    if session_project:
        session_lines.append(f"  - Current Project: {session_project.get('name', '')}")
    if session_task:
        session_lines.append(f"  - Current Task: {session_task}")
    if session_topic:
        session_lines.append(f"  - Current Topic: {session_topic}")
    if session_lines:
        parts.append("SESSION MEMORY:\n" + "\n".join(session_lines))

    active_window_context = ""
    if active_window_info and cfg.track_active_window and cfg.show_in_prompt:
        title = (active_window_info.get("title") or "").strip()
        proc = (active_window_info.get("process_name") or "").strip()
        if title or proc:
            aw_parts = []
            if title:
                aw_parts.append(f"Window: {title}")
            if proc:
                aw_parts.append(f"Application: {proc}")
            active_window_context = " | ".join(aw_parts)

    if _is_generic_greeting(user_message) and not session_lines and not active_window_context:
        return ""

    if active_window_context:
        parts.append("CURRENT CONTEXT:\n  - " + active_window_context)

    projects = find_relevant_projects(user_message, limit=cfg.max_context_memories)
    if session_project and not any(p["id"] == session_project.get("id") for p in projects):
        projects.insert(0, session_project)
    if projects:
        p_lines = []
        for p in projects[:cfg.max_context_memories]:
            line = f"  - [{p['status']}] {p['name']}: {p['description']}"
            if p["notes"]:
                line += f" | Notes: {p['notes']}"
            p_lines.append(line)
        parts.append("ACTIVE PROJECTS:\n" + "\n".join(p_lines))

    relevance_text = " ".join([user_message, session_topic, session_task]).strip()
    relevance_tokens = _tokens(relevance_text)

    facts = [
        f for f in get_all_facts()
        if relevance_tokens & _tokens(f"{f['category']} {f['key']} {f['value']}")
    ]
    if facts:
        f_lines = [f"  - [{f['category']}] {f['key']}: {f['value']}" for f in facts[:8]]
        parts.append("USER FACTS & PREFERENCES:\n" + "\n".join(f_lines))

    summaries = []
    if _SUMMARY_REQUEST_RE.search(user_message) or relevance_tokens:
        summaries = [
            s for s in get_recent_summaries(limit=6)
            if _SUMMARY_REQUEST_RE.search(user_message)
            or relevance_tokens & _tokens(s.get("summary", ""))
        ][:2]
    if summaries:
        s_lines = [f"  - {s['created_at'][:16]}: {s['summary']}" for s in summaries]
        parts.append("RECENT SESSION SUMMARIES:\n" + "\n".join(s_lines))

    people = [
        p for p in get_people()
        if (p.get("name") or "").lower() in user_message.lower()
    ]
    if people:
        pe_lines = [f"  - {p['name']} ({p['relationship']}): {p['notes']}" for p in people[:6]]
        parts.append("KNOWN PEOPLE:\n" + "\n".join(pe_lines))

    if not parts:
        return ""

    return "\n\n[MEMORY CONTEXT]\n" + "\n\n".join(parts) + "\n[/MEMORY CONTEXT]"
