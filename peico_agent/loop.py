"""The ReAct loop: reason -> (maybe act) -> observe -> repeat -> answer.

This is the whole agent. The model decides; the loop only keeps the message list,
dispatches tools, and bounds iteration. Everything else (planning, reflection) is
the model's job — deliberately, so the reference baseline stays transparent.
"""
from __future__ import annotations

import json

from . import tools
from .model import Model
from .prompts import SYSTEM_PROMPT


class Agent:
    """Holds the conversation and runs the tool loop for each customer turn."""

    def __init__(self, model: Model, max_tool_iters: int, world):
        self.model = model
        self.max_tool_iters = max_tool_iters
        self.world = world
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._tool_specs = tools.specs()

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def send(self, user_text: str, on_tool=None) -> str:
        """Add a customer turn, run the ReAct loop, return the reply text.

        on_tool(name, args, result) is an optional callback for tracing.
        """
        self.messages.append({"role": "user", "content": user_text})

        for _ in range(self.max_tool_iters):
            msg = self.model.complete(self.messages, self._tool_specs)
            self.messages.append(_assistant_entry(msg))

            if not getattr(msg, "tool_calls", None):
                return msg.content or ""

            for call in msg.tool_calls:
                name = call.function.name
                args = _parse_args(call.function.arguments)
                result = tools.dispatch(name, args, world=self.world)
                if on_tool:
                    on_tool(name, args, result)
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )

        return "(stopped: reached the tool-iteration limit without a final reply)"


def _assistant_entry(msg) -> dict:
    """Normalize a LiteLLM assistant message into a re-sendable dict."""
    entry: dict = {"role": "assistant", "content": msg.content or ""}
    if getattr(msg, "tool_calls", None):
        entry["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.function.name, "arguments": c.function.arguments},
            }
            for c in msg.tool_calls
        ]
    return entry


def _parse_args(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
