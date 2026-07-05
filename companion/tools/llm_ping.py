"""Ping LM Studio with a single prompt and measure time-to-first-token and total time.
Usage: run from the `companion` folder with the project's venv Python.
"""
import sys
import time
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tools.registry as registry
from ai.llm_client import ConversationManager
from config.loader import get_config

ORIGINAL_PROMPT = """
You are COMPUTER.
You are a friendly, intelligent teammate. Keep answers concise unless asked for brainstorming.
"""


def long_tool_prompt():
    lines = [
        "Computer control abilities are available.",
        "Available tools:",
    ]
    for spec in registry.TOOL_REGISTRY.values():
        lines.append(f"- {spec['name']}: {spec['description']}")
    return "\n".join(lines)


def ping(system_prompt, tool_prompt, model_override="gemma-4-e4b-it"):
    cfg = get_config()
    cfg._raw["llm"]["model"] = model_override
    # monkeypatch
    cfg._personality["system_prompt"] = system_prompt
    registry.tool_prompt_block = tool_prompt

    mgr = ConversationManager()
    prompt = "Provide a 2-sentence plan to reduce LLM latency."

    start = time.time()
    first = None
    total = None
    full = ""
    for tok in mgr.chat_stream(prompt):
        if first is None:
            first = time.time()
        full += tok
    total = time.time()
    return {
        "time_to_first": None if first is None else first - start,
        "total_time": total - start,
        "response": full[:400],
    }


def main():
    print("Running verbose prompt...", flush=True)
    res_before = ping(ORIGINAL_PROMPT, long_tool_prompt)
    print(res_before, flush=True)

    print("Running compact prompt...", flush=True)
    # load current compact prompt from config
    cfg = get_config()
    compact = cfg.system_prompt
    res_after = ping(compact, registry.tool_prompt_block)
    print(res_after, flush=True)


if __name__ == '__main__':
    main()
