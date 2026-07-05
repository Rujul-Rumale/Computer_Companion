"""Structured tool execution wrapper for UI event reporting."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from tools import execute_tool


@dataclass(frozen=True)
class ToolEvent:
    name: str
    status: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class ToolRunner:
    def run(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        *,
        require_confirmation: bool | None = None,
        on_event: Callable[[ToolEvent], None] | None = None,
    ) -> Any:
        params = params or {}
        if on_event:
            on_event(ToolEvent(name=name, status="started", message="Tool started"))

        result = execute_tool(name, params, require_confirmation=require_confirmation)
        event = ToolEvent(
            name=name,
            status="completed" if result.success else "failed",
            message=result.message,
            data=result.data or {},
        )
        if on_event:
            on_event(event)
        return result


_TOOL_RUNNER: ToolRunner | None = None
_tool_runner_lock = threading.Lock()


def get_tool_runner() -> ToolRunner:
    global _TOOL_RUNNER
    if _TOOL_RUNNER is None:
        with _tool_runner_lock:
            if _TOOL_RUNNER is None:
                _TOOL_RUNNER = ToolRunner()
    return _TOOL_RUNNER
