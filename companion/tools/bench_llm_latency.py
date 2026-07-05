"""Simple benchmark for LLM time-to-first-token and total response time.

Run from the project root with the venv activated.
"""
import json
import sys
import time
from pathlib import Path

# Ensure project root (the `companion` folder) is on sys.path for imports
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config.loader as loader_mod
import tools.registry as registry
from ai.llm_client import ConversationManager

ORIGINAL_PROMPT = '''
You are COMPUTER.

You are a friendly, intelligent teammate.
Your primary goal is to be pleasant to talk to and useful.
You are a teammate, not a consultant.

Default behavior:
 - Talk naturally
 - Use contractions
 - Keep responses short unless the user asks for detail
 - Do not sound like documentation
 - Do not sound like customer support
 - Do not assume every conversation is technical
 - Match the user's energy and topic
 - Ask follow-up questions naturally
 - Keep startup greetings simple and neutral
 - Reference stored projects only when they are active in session memory or directly relevant
 - Simple greetings stay simple; never continue a project unless the user has activated it
 - If you can act through a tool, do that first and say it plainly

Conversation modes:
 - Casual: for greetings, small talk, everyday comments, loose questions, and non-technical topics. Stay relaxed and brief.
 - Brainstorming: for ideas, possibilities, naming, planning, creative direction, and "what do you think" with context. Be playful and useful.
 - Engineering: for calculations, design tradeoffs, hardware, systems, RF, aerospace, controls, debugging, and technical analysis. Be precise and direct.
 - Coding: for code, repo work, implementation, tests, errors, refactors, and command output. Be concrete and action-oriented.

Examples:
User: "Hi"
Good: "Hey. What are we working on today?"
Good: "Good to see you. What's the plan?"
Bad: "Let's continue the telemetry project."

User: "Open Chrome"
Good: "Opening Chrome."
Bad: "I cannot open applications."

User: "I'm recording a video."
Good: "Oh nice. What's it about?"
Good: "For YouTube?"
Bad: "Specify the technical domain."

User: "What do you think?"
Good: "About what?"
Good: "Depends. What are we talking about?"
Bad: "Provide additional context so I can formulate an assessment."

If the user says something technical like "calculate wing loading," shift gears into engineering mode.
If the user asks for code or gives an error, shift into coding mode.
'''


def long_tool_prompt():
    lines = [
        "Computer control abilities are available.",
        "Use a tool immediately when the user asks for an action that matches one.",
        "Never claim you cannot open apps, switch windows, type, move the mouse, or change volume if a tool exists.",
        "When a tool is needed, keep the response short and action-first.",
        "Available tools:",
    ]
    for spec in registry.TOOL_REGISTRY.values():
        param_names = list(spec["parameters"].get("properties", {}).keys())
        required = spec["parameters"].get("required", [])
        params = required or param_names
        lines.append(f"- {spec['name']}: {spec['description']}" + (f" (params: {', '.join(params)})" if params else ""))
    return "\n".join(lines)


def run_once(label: str, monkey_system_prompt=None, monkey_tool_prompt=None):
    cfg = loader_mod.get_config()
    # monkeypatch system prompt and tool prompt function if provided
    if monkey_system_prompt is not None:
        cfg._personality["system_prompt"] = monkey_system_prompt
    if monkey_tool_prompt is not None:
        registry.tool_prompt_block = monkey_tool_prompt

    print(f"[bench] starting run: {label}", flush=True)
    mgr = ConversationManager()
    prompt = "Give a concise plan to reduce latency in a local LLM setup. Keep it short."

    print(f"[bench] calling chat_stream for: {label}", flush=True)
    gen = mgr.chat_stream(prompt, on_token=None)
    first_token_time = None
    start_time = time.time()
    full = ""
    try:
        for tok in gen:
            if first_token_time is None:
                first_token_time = time.time()
            full += tok
    except StopIteration:
        pass
    end_time = time.time()
    return {
        "label": label,
        "start_time": start_time,
        "first_token_time": first_token_time,
        "end_time": end_time,
        "time_to_first": None if first_token_time is None else first_token_time - start_time,
        "total_time": end_time - start_time,
        "response_snippet": full[:400],
    }


def main():
    results = []

    # Run 'before' with verbose system prompt and detailed tool prompt
    results.append(run_once("before", monkey_system_prompt=ORIGINAL_PROMPT, monkey_tool_prompt=long_tool_prompt))
    print("[bench] completed run: before", flush=True)

    # Run 'after' with current compact prompt and compact tool prompt
    cfg = loader_mod.get_config()
    compact_prompt = cfg.system_prompt
    results.append(run_once("after", monkey_system_prompt=compact_prompt, monkey_tool_prompt=registry.tool_prompt_block))
    print("[bench] completed run: after", flush=True)

    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
