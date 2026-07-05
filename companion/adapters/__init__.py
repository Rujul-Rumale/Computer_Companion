"""Free local adapter layer for models, search, browser control, tools, and files."""

from .attachment_processor import (
    AttachmentProcessor,
    AttachmentSummary,
    format_attachments_for_prompt,
    get_attachment_processor,
)
from .browser_provider import BrowserProvider, BrowserResult, get_browser_provider
from .llama_backend import LlamaServer, get_llama_server, start_llama_server, stop_llama_server
from .model_provider import ModelProvider, get_model_provider
from .search_provider import SearchResponse, SearchResult, get_search_provider
from .tool_runner import ToolEvent, ToolRunner, get_tool_runner

__all__ = [
    "AttachmentSummary",
    "AttachmentProcessor",
    "format_attachments_for_prompt",
    "get_attachment_processor",
    "LlamaServer",
    "get_llama_server",
    "start_llama_server",
    "stop_llama_server",
    "ModelProvider",
    "get_model_provider",
    "SearchResult",
    "SearchResponse",
    "get_search_provider",
    "ToolEvent",
    "ToolRunner",
    "get_tool_runner",
    "BrowserProvider",
    "BrowserResult",
    "get_browser_provider",
]
