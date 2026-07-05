"""
ui/markdown.py — Simple markdown-to-HTML converter for chat rendering.
Handles bold, italic, inline code, code blocks, links, and line breaks.
"""

from __future__ import annotations

import re


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _convert_code_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Extract ```code blocks``` and replace with placeholders.
    Returns (text_with_placeholders, [(placeholder, html), ...]).
    """
    placeholders: list[tuple[str, str]] = []
    def _replacer(m: re.Match) -> str:
        code = m.group(1)
        html = f'<pre style="background:#1e1e2e;color:#cdd6f4;padding:8px;border-radius:6px;font-family:Consolas;font-size:11px;line-height:1.4;overflow-x:auto;"><code>{_escape_html(code)}</code></pre>'
        placeholder = f"\x00BLOCK{len(placeholders)}\x00"
        placeholders.append((placeholder, html))
        return placeholder
    text = re.sub(r"```(.*?)```", _replacer, text, flags=re.DOTALL)
    return text, placeholders


def _convert_inline_code(text: str) -> str:
    """Convert `inline code` to <code> tags."""
    return re.sub(r"`([^`]+)`", lambda m: f"<code>{_escape_html(m.group(1))}</code>", text)


def _convert_bold(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", lambda m: f"<b>{m.group(1)}</b>", text)


def _convert_italic(text: str) -> str:
    """Convert *italic* (but not when preceded by a word char)."""
    return re.sub(r"(?<!\w)\*(?!\*)(.+?)\*(?!\*)", lambda m: f"<i>{m.group(1)}</i>", text)


def _convert_links(text: str) -> str:
    return re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{_escape_html(m.group(2))}" style="color:#89b4fa;">{m.group(1)}</a>',
        text,
    )


def _convert_newlines(text: str) -> str:
    """Convert double newlines to <p> and single newlines to <br>."""
    paragraphs = re.split(r"\n\s*\n", text)
    parts = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if "\n" in para:
            para = para.replace("\n", "<br>")
        parts.append(f"<p style='margin:4px 0;'>{para}</p>")
    return "".join(parts)


def md_to_html(text: str) -> str:
    """Convert markdown text to HTML for QTextEdit rendering."""
    if not text:
        return ""

    text, blocks = _convert_code_blocks(text)
    text = _convert_inline_code(text)
    text = _convert_bold(text)
    text = _convert_italic(text)
    text = _convert_links(text)
    text = _convert_newlines(text)

    for placeholder, html in blocks:
        text = text.replace(placeholder, html)

    return f"<div style='font-family:Consolas;font-size:12px;line-height:1.5;'>{text}</div>"
