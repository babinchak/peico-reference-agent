"""The ReAct loop: reason -> (maybe act) -> observe -> repeat -> answer.

This is the whole agent. The model decides; the loop only keeps the message list,
dispatches tools against the session environment, and bounds iteration. The agent
ends a conversation voluntarily by calling the ``end_conversation`` control tool
(a structured terminate signal, per doc 08) — the loop reports that back so the
adapter can tell the bench the rep is done.
"""
from __future__ import annotations

import json

from . import tools
from .model import Model
from .prompts import SYSTEM_PROMPT

# A control tool the harness understands: not an env call, intercepted here.
_END_TOOL = {
    "type": "function",
    "function": {
        "name": "end_conversation",
        "description": (
            "Signal that the customer's needs are fully resolved and the conversation "
            "should end. Call this together with (or just before) your brief closing/"
            "thank-you message. Do not call it while anything is still outstanding."
        ),
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}
_END = "end_conversation"


class Agent:
    """Holds the conversation and runs the tool loop for each customer turn."""

    def __init__(self, model: Model, max_tool_iters: int, env):
        self.model = model
        self.max_tool_iters = max_tool_iters
        self.env = env
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._tool_specs = tools.specs() + [_END_TOOL]

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def send(self, user_text: str, on_tool=None) -> tuple[str, bool]:
        """Add a customer turn, run the ReAct loop, return (reply_text, terminate).

        on_tool(name, args, result) is an optional callback for tracing.
        """
        self.messages.append({"role": "user", "content": user_text})
        terminate = False
        closing: str | None = None

        for _ in range(self.max_tool_iters):
            msg = self.model.complete(self.messages, self._tool_specs)
            self.messages.append(_assistant_entry(msg))

            if not getattr(msg, "tool_calls", None):
                return (msg.content or closing or ""), terminate

            for call in msg.tool_calls:
                name = call.function.name
                args = _parse_args(call.function.arguments)
                if name == _END:
                    terminate = True
                    closing = msg.content or closing
                    result = json.dumps({"ok": True, "note": "Deliver your closing message now."})
                else:
                    result = tools.dispatch(name, args, env=self.env)
                if on_tool:
                    on_tool(name, args, result)
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )

        return "(stopped: reached the tool-iteration limit without a final reply)", terminate


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
