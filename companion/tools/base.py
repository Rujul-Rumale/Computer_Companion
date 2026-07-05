"""Shared tool types and helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    success: bool
    message: str
    data: dict[str, Any] | None = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"[{status}] {self.message}"


def tool_spec(
    *,
    name: str,
    description: str,
    parameters: dict[str, Any],
    handler: Callable[[dict[str, Any]], ToolResult],
    aliases: list[str] | None = None,
    requires_confirmation: bool = False,
    hidden: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": parameters,
        "handler": handler,
        "aliases": aliases or [],
        "requires_confirmation": requires_confirmation,
        "hidden": hidden,
    }
