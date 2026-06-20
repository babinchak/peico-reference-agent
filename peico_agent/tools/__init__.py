"""Tool registry — the clean seam between the agent loop and the world.

Tools register themselves with a name, description, and JSON Schema for their
arguments. The loop asks the registry for `specs()` (OpenAI/LiteLLM function
format, which LiteLLM normalizes per provider) and calls `dispatch()` to run one.

Keeping every tool behind this registry is deliberate: it's what makes an MCP
wrapper, a permission layer, or the eventual migration of writes into the bench
harness a thin add rather than a rewrite.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

ToolFn = Callable[..., Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema for the arguments object
    fn: ToolFn
    writes: bool = False  # informational: this tool mutates the world via env.write


_REGISTRY: dict[str, Tool] = {}


def register(name: str, description: str, parameters: dict, *, writes: bool = False):
    """Decorator: register a function as an agent tool."""

    def deco(fn: ToolFn) -> ToolFn:
        if name in _REGISTRY:
            raise ValueError(f"duplicate tool name: {name}")
        _REGISTRY[name] = Tool(name, description, parameters, fn, writes)
        return fn

    return deco


def specs() -> list[dict]:
    """Tool definitions in OpenAI/LiteLLM function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in _REGISTRY.values()
    ]


def dispatch(name: str, args: dict, *, env) -> str:
    """Run a tool by name against the session `env`. Always returns a string result.

    `env` is the bench's per-session environment handle (query/write/rate/
    search_kb), injected here (not model-provided) and passed as the tool's first
    argument — the agent never holds the database, only this handle, which is what
    keeps tools free of global state and makes concurrent sessions safe.

    Tool-level failures are returned as structured error strings (not raised) so
    the model sees them and can recover — recovering from a structured rejection
    is exactly the skill the benchmark measures.
    """
    tool = _REGISTRY.get(name)
    if tool is None:
        return json.dumps({"error": "unknown_tool", "name": name})
    try:
        result = tool.fn(env, **args)
    except TypeError as exc:  # bad/missing arguments from the model
        return json.dumps({"error": "bad_arguments", "detail": str(exc)})
    except Exception as exc:  # noqa: BLE001 — surface, don't crash the loop
        return json.dumps({"error": "tool_failed", "detail": str(exc)})
    return result if isinstance(result, str) else json.dumps(result, default=str)


# Importing the tool modules registers their tools as a side effect.
from . import read_tools  # noqa: E402,F401
from . import write_tools  # noqa: E402,F401
