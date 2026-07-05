"""Attachment summarization helpers for dropped files and future chat context."""

from __future__ import annotations

import base64
import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".py", ".json", ".yaml", ".yml", ".csv", ".log", ".ini", ".cfg", ".toml"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


@dataclass(frozen=True)
class AttachmentSummary:
    path: str
    display_name: str
    kind: str
    mime_type: str = ""
    size: int = 0
    text: str = ""
    image_payload: str = ""


class AttachmentProcessor:
    def summarize_path(self, path: str, max_chars: int = 4000) -> AttachmentSummary:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        size = file_path.stat().st_size if file_path.exists() else 0
        display_name = file_path.name or path

        if suffix in IMAGE_EXTENSIONS:
            payload = self._read_image_payload(file_path)
            return AttachmentSummary(path=str(file_path), display_name=display_name, kind="image", mime_type=f"image/{suffix.lstrip('.') or 'png'}", size=size, image_payload=payload)

        text = ""
        if suffix in TEXT_EXTENSIONS or self._looks_text_like(file_path):
            text = self._read_text(file_path, max_chars=max_chars)
            if suffix == ".csv":
                text = self._format_csv(text)
            elif suffix == ".json":
                text = self._format_json(text)
            return AttachmentSummary(path=str(file_path), display_name=display_name, kind="text", mime_type="text/plain", size=size, text=text)

        return AttachmentSummary(path=str(file_path), display_name=display_name, kind="file", size=size)

    def summarize_many(self, paths: Iterable[str], max_chars: int = 4000) -> list[AttachmentSummary]:
        return [self.summarize_path(path, max_chars=max_chars) for path in paths]

    def _read_text(self, file_path: Path, max_chars: int) -> str:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
        return text[:max_chars]

    def _read_image_payload(self, file_path: Path) -> str:
        try:
            return base64.b64encode(file_path.read_bytes()).decode("ascii")
        except Exception:
            return ""

    def _looks_text_like(self, file_path: Path) -> bool:
        try:
            with file_path.open("rb") as handle:
                chunk = handle.read(512)
            return b"\x00" not in chunk
        except Exception:
            return False

    def _format_csv(self, text: str) -> str:
        try:
            rows = list(csv.reader(text.splitlines()))
        except Exception:
            return text
        return "\n".join(", ".join(row) for row in rows[:40])

    def _format_json(self, text: str) -> str:
        try:
            data = json.loads(text)
            return json.dumps(data, indent=2)[:4000]
        except Exception:
            return text


_ATTACHMENT_PROCESSOR: AttachmentProcessor | None = None


def get_attachment_processor() -> AttachmentProcessor:
    global _ATTACHMENT_PROCESSOR
    if _ATTACHMENT_PROCESSOR is None:
        _ATTACHMENT_PROCESSOR = AttachmentProcessor()
    return _ATTACHMENT_PROCESSOR


def format_attachments_for_prompt(attachments: Iterable[AttachmentSummary]) -> str:
    blocks: list[str] = []
    for attachment in attachments:
        if attachment.kind == "image":
            blocks.append(f"Attachment: {attachment.display_name} [image, {attachment.size} bytes]")
        elif attachment.text:
            blocks.append(f"Attachment: {attachment.display_name}\n{attachment.text}")
        else:
            blocks.append(f"Attachment: {attachment.display_name} [{attachment.kind}, {attachment.size} bytes]")
    return "\n\n".join(blocks)
