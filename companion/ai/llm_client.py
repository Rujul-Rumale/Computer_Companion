"""
ai/llm_client.py - OpenAI-compatible LLM client (LM Studio / Ollama)
Handles streaming, context management, memory injection, tools, and summarization.
"""
import json
import re
import uuid
from collections.abc import Callable, Generator
from dataclasses import dataclass, field

from openai import APIError, OpenAI

from adapters import AttachmentSummary, format_attachments_for_prompt, get_model_provider, get_tool_runner
from config import get_config
from memory import (
    build_memory_context,
    build_session_context_block,
    count_turns,
    find_relevant_projects,
    get_recent_turns,
    record_window_focus,
    save_summary,
    save_turn,
    set_session_context,
)
from tools.registry import get_tool_schemas, normalize_tool_name


def _make_client() -> OpenAI:
    return get_model_provider().client()


_GENERIC_GREETING_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|sup|good\s+(morning|afternoon|evening)|"
    r"what'?s\s+up|how\s+are\s+you)[!.?\s]*$",
    re.IGNORECASE,
)
_TASK_RE = re.compile(
    r"\b(build|fix|debug|refactor|implement|add|remove|change|review|"
    r"explain|design|test|write|create|update|continue|resume)\b",
    re.IGNORECASE,
)
_CODING_RE = re.compile(
    r"\b(code|coding|repo|bug|traceback|exception|error|test|tests|pytest|"
    r"commit|branch|pr|pull request|function|class|module|api|refactor|"
    r"implement|compile|syntax|stack trace|launch_companion|\.py|\.js|\.ts)\b",
    re.IGNORECASE,
)
_ENGINEERING_RE = re.compile(
    r"\b(calculate|wing loading|thrust|torque|voltage|current|power|pcb|rf|"
    r"sdr|uav|aerospace|control|pid|firmware|mcu|sensor|imu|thermal|"
    r"mechanical|electrical|circuit|schematic|cad|kicad)\b",
    re.IGNORECASE,
)
_BRAINSTORMING_RE = re.compile(
    r"\b(brainstorm|idea|ideas|plan|outline|name|naming|"
    r"concept|direction|what do you think|thoughts|maybe|could we)\b",
    re.IGNORECASE,
)
_RESTORE_SESSION_RE = re.compile(
    r"\b(restore|resume|reopen|reload|what\s+were\s+we|where\s+were\s+we|"
    r"last\s+project|last\s+session|previous|left\s+off|"
    r"pick\s+up|continue|back\s+to)\b",
    re.IGNORECASE,
)


@dataclass
class SessionMemory:
    """Short-lived state for this app session. Starts empty by design."""
    current_project: dict | None = None
    current_task: str = ""
    current_topic: str = ""
    conversation_mode: str = "casual"
    mentioned_project_ids: set[int] = field(default_factory=set)

    def as_context(self) -> dict:
        return {
            "current_project": self.current_project,
            "current_task": self.current_task,
            "current_topic": self.current_topic,
            "conversation_mode": self.conversation_mode,
        }

    def update_from_user_message(self, user_message: str):
        msg = (user_message or "").strip()
        if not msg or _GENERIC_GREETING_RE.match(msg):
            self.conversation_mode = "casual"
            return

        self.conversation_mode = _classify_mode(msg)
        projects = find_relevant_projects(msg, limit=1)
        if projects and _TASK_RE.search(msg):
            self.current_project = projects[0]
            self.mentioned_project_ids.add(projects[0]["id"])
            self.current_topic = projects[0]["name"]
        elif not self.current_topic:
            self.current_topic = _shorten(msg)

        if _TASK_RE.search(msg):
            self.current_task = _shorten(msg)


def _shorten(text: str, limit: int = 140) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _classify_mode(text: str) -> str:
    if _CODING_RE.search(text):
        return "coding"
    if _ENGINEERING_RE.search(text):
        return "engineering"
    if _BRAINSTORMING_RE.search(text):
        return "brainstorming"
    return "casual"


def _build_system_prompt(
    user_message: str = "",
    session_memory: SessionMemory | None = None,
    mode_config: dict | None = None,
    active_window_info: dict | None = None,
) -> str:
    cfg = get_config()
    base = cfg.system_prompt.strip()
    mode = session_memory.conversation_mode if session_memory else "casual"
    mode_instructions = ""
    if mode_config:
        instructions = mode_config.get("instructions", [])
        if instructions:
            mode_instructions = "\n\nMode instructions:\n" + "\n".join(f"- {i}" for i in instructions)
    guardrails = (
        f"Mode: {mode}.\n"
        "SESSION MEMORY = active project/task/topic for this session.\n"
        "CURRENT CONTEXT = user's active window.\n"
        f"{mode_instructions}"
    )
    prev_session = build_session_context_block(user_message) if _RESTORE_SESSION_RE.search(user_message) else ""
    mem = build_memory_context(
        user_message=user_message,
        session_memory=session_memory.as_context() if session_memory else None,
        active_window_info=active_window_info,
    )
    user_ctx = cfg.user_context
    local_block = ""
    if user_ctx.get("city"):
        parts = [user_ctx["city"]]
        if user_ctx.get("country"):
            parts.append(user_ctx["country"])
        local_block += f"Location: {', '.join(parts)}. "
    if user_ctx.get("timezone"):
        local_block += f"Timezone: {user_ctx['timezone']}. "
    if user_ctx.get("date_format"):
        local_block += f"Date format: {user_ctx['date_format']}. "
    if user_ctx.get("temperature_unit"):
        local_block += f"Temperature: {user_ctx['temperature_unit']}. "
    if user_ctx.get("currency"):
        local_block += f"Currency: {user_ctx['currency']}. "
    if local_block:
        local_block = "User context:\n" + local_block.strip()

    return base + "\n\n" + guardrails + prev_session + ("\n\n" + mem if mem else "") + ("\n\n" + local_block if local_block else "")


def _turns_to_messages(turns: list[dict]) -> list[dict]:
    msgs = []
    for t in turns:
        if t["role"] in ("user", "assistant", "tool"):
            msgs.append({"role": t["role"], "content": t["content"]})
    return msgs


class ConversationManager:
    def __init__(self):
        self.session_id = str(uuid.uuid4())[:8]
        self._client: OpenAI | None = None
        self._interrupted = False
        self.session_memory = SessionMemory()

    def _save_session_context(self):
        """Persist current session state to DB for cross-session continuity."""
        cfg = get_config()
        if not cfg.session_persistence:
            return
        proj = self.session_memory.current_project
        if proj and proj.get("name"):
            set_session_context("last_project", proj["name"])
        if self.session_memory.current_task:
            set_session_context("last_task", self.session_memory.current_task)

    def _client_lazy(self) -> OpenAI:
        if self._client is None:
            self._client = _make_client()
        return self._client

    def interrupt(self):
        self._interrupted = True

    def reset_interrupt(self):
        self._interrupted = False

    def chat_stream(
        self,
        user_message: str,
        image_path: str | None = None,
        on_token: Callable[[str], None] | None = None,
        on_tool: Callable[[str], None] | None = None,
        on_state: Callable[[str], None] | None = None,
        mode_config: dict | None = None,
        active_window_info: dict | None = None,
        attachments: list[AttachmentSummary] | None = None,
    ) -> Generator[str, None, str]:
        """
        Streams the final assistant response token by token.
        If the model requests tools, executes them and then streams the answer.
        mode_config: optional dict with temperature, max_tokens, instructions
        active_window_info: optional dict with title, process_name keys
        """
        self.reset_interrupt()
        cfg = get_config()

        save_turn(self.session_id, "user", user_message)
        self.session_memory.update_from_user_message(user_message)

        if cfg.persist_window_context and active_window_info:
            title = (active_window_info.get("title") or "").strip()
            proc = (active_window_info.get("process_name") or "").strip()
            if title:
                record_window_focus(title, proc)

        system = _build_system_prompt(user_message, self.session_memory, mode_config, active_window_info)
        # Limit history size to reduce prompt length and latency.
        history_limit = max(4, cfg.max_context_memories * 4)
        history = get_recent_turns(self.session_id, limit=history_limit)
        messages = [{"role": "system", "content": system}]
        messages += _turns_to_messages(history[:-1])

        att_list = attachments or []
        attachment_block = format_attachments_for_prompt(att_list) if att_list else ""
        msg_text = user_message
        if attachment_block:
            msg_text = f"{attachment_block}\n\n{user_message}" if (user_message or "").strip() else attachment_block

        if image_path is None:
            for att in att_list:
                if att.kind == "image" and att.path:
                    image_path = att.path
                    break

        if image_path:
            import base64

            try:
                with open(image_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                user_content = [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": msg_text},
                ]
            except Exception as exc:
                fallback = f"Screenshot captured, but I couldn't load it: {exc}"
                save_turn(self.session_id, "assistant", fallback)
                yield fallback
                return fallback
        else:
            user_content = msg_text

        messages.append({"role": "user", "content": user_content})

        client = self._client_lazy()
        full_response = ""
        tool_schemas = get_tool_schemas()

        try:
            for _ in range(3):
                if on_state:
                    on_state("THINKING")

                # Choose per-request max tokens. Give more budget for brainstorming mode.
                per_request_max = cfg.llm_max_tokens
                try:
                    if getattr(self.session_memory, "conversation_mode", "") == "brainstorming":
                        per_request_max = cfg.llm_max_tokens_brainstorm
                except Exception:
                    pass

                temp = mode_config.get("temperature", cfg.llm_temperature) if mode_config else cfg.llm_temperature
                max_tok = mode_config.get("max_tokens", per_request_max) if mode_config else per_request_max
                stream = client.chat.completions.create(
                    model=cfg.llm_model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=max_tok,
                    stream=True,
                    tools=tool_schemas,
                    tool_choice="auto",
                    timeout=30,
                )

                assistant_tokens: list[str] = []
                tool_calls: dict[int, dict] = {}

                for chunk in stream:
                    if self._interrupted:
                        break
                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", None)
                    if content:
                        assistant_tokens.append(content)
                        yield content
                        if on_token:
                            on_token(content)
                    if getattr(delta, "tool_calls", None):
                        for tool_call in delta.tool_calls:
                            bucket = tool_calls.setdefault(
                                tool_call.index,
                                {"id": "", "name": "", "arguments": ""},
                            )
                            if getattr(tool_call, "id", None):
                                bucket["id"] = tool_call.id
                            if getattr(tool_call.function, "name", None):
                                bucket["name"] = tool_call.function.name
                            if getattr(tool_call.function, "arguments", None):
                                bucket["arguments"] += tool_call.function.arguments

                assistant_text = "".join(assistant_tokens).strip()

                if not tool_calls:
                    full_response = assistant_text
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_text or None,
                        "tool_calls": [
                            {
                                "id": call["id"] or f"call_{index}",
                                "type": "function",
                                "function": {
                                    "name": normalize_tool_name(call["name"]),
                                    "arguments": call["arguments"],
                                },
                            }
                            for index, call in tool_calls.items()
                        ],
                    }
                )

                for index, call in tool_calls.items():
                    tool_name = normalize_tool_name(call["name"])
                    try:
                        tool_args = json.loads(call["arguments"] or "{}")
                    except Exception:
                        tool_args = {}
                    if on_state:
                        on_state("ACTING")
                    result = get_tool_runner().run(
                        tool_name,
                        tool_args,
                        require_confirmation=cfg.require_confirmation,
                    )
                    if on_tool:
                        on_tool(str(result))
                    save_turn(self.session_id, "tool", str(result), tool_call=tool_name)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"] or f"call_{index}",
                            "content": str(result),
                        }
                    )

                if on_state:
                    on_state("THINKING")

            if not full_response:
                full_response = assistant_text.strip() if 'assistant_text' in locals() else ""
        except APIError as e:
            if self._interrupted:
                return ""
            self._client = None
            from adapters.model_provider import reset_provider
            reset_provider()
            if image_path:
                full_response = "Screenshot captured, but vision is unavailable right now."
                yield full_response
            else:
                err = f"[LLM ERROR: {e}]"
                yield err
                return err

        if self._interrupted:
            return ""

        save_turn(self.session_id, "assistant", full_response)
        self._save_session_context()

        n = count_turns(self.session_id)
        if n >= cfg.summary_threshold and n % cfg.summary_threshold == 0:
            self._summarize_async(full_response)

        if on_state:
            on_state("SPEAKING" if full_response else "IDLE")

        return full_response

    def chat_sync(self, user_message: str, image_path: str | None = None) -> str:
        """Non-streaming version. Returns full response."""
        response = ""
        for token in self.chat_stream(user_message, image_path):
            response += token
        return response

    def _summarize_async(self, last_response: str):
        """Fire-and-forget summary of recent turns."""
        import threading
        def _do():
            try:
                cfg = get_config()
                turns = get_recent_turns(self.session_id, limit=cfg.summary_threshold)
                transcript = "\n".join(
                    f"{t['role'].upper()}: {t['content'][:200]}" for t in turns
                )
                client = self._client_lazy()
                resp = client.chat.completions.create(
                    model=cfg.llm_model,
                    messages=[
                        {"role": "system", "content": "You are a summarizer. Be very concise."},
                        {"role": "user", "content": f"Summarize this conversation in 2-3 sentences, noting key topics and decisions:\n\n{transcript}"}
                    ],
                    max_tokens=200,
                    stream=False,
                )
                summary = resp.choices[0].message.content.strip()
                save_summary(self.session_id, summary, len(turns), [])
            except Exception as e:
                print(f"[SUMMARY ERR] {e}")
        threading.Thread(target=_do, daemon=True).start()

    def test_connection(self) -> tuple[bool, str]:
        """Tests LM Studio connectivity. Returns (ok, message)."""
        cfg = get_config()
        try:
            client = self._client_lazy()
            models = client.models.list()
            model_ids = [m.id for m in models.data]
            if cfg.llm_model in model_ids:
                return True, f"Connected. Model '{cfg.llm_model}' is loaded."
            else:
                avail = ", ".join(model_ids[:5]) if model_ids else "none"
                return False, f"Connected but model '{cfg.llm_model}' not found. Available: {avail}"
        except Exception as e:
            return False, f"Cannot reach {cfg.llm_backend} at {cfg.llm_base_url}: {e}"
