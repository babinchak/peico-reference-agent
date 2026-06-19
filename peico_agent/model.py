"""LiteLLM model client with token + cost accounting.

LiteLLM gives one OpenAI-shaped interface across providers, so swapping models is
a string change. We track usage ourselves because the leaderboard reports tokens
and cost alongside score — that accounting must be exact and provider-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass

import litellm

# Tool-call args sometimes arrive as not-quite-JSON; let LiteLLM be lenient and
# don't blow up the whole run on a provider quirk.
litellm.drop_params = True


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __str__(self) -> str:
        return (
            f"{self.calls} calls · {self.prompt_tokens} in / "
            f"{self.completion_tokens} out tokens · ${self.cost_usd:.4f}"
        )


class Model:
    """A single model behind LiteLLM, accumulating usage across the session."""

    def __init__(self, name: str):
        self.name = name
        self.usage = Usage()

    def complete(self, messages: list[dict], tools: list[dict] | None = None):
        """One model turn. Returns the assistant message object.

        `tools` is optional: the agent passes its tool specs, but tool-less
        callers (the user simulator, the judge) omit it.
        """
        kwargs: dict = {"model": self.name, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = litellm.completion(**kwargs)
        self._track(resp)
        return resp.choices[0].message

    def _track(self, resp) -> None:
        self.usage.calls += 1
        u = getattr(resp, "usage", None)
        if u:
            self.usage.prompt_tokens += getattr(u, "prompt_tokens", 0) or 0
            self.usage.completion_tokens += getattr(u, "completion_tokens", 0) or 0
        try:
            self.usage.cost_usd += litellm.completion_cost(resp) or 0.0
        except Exception:  # noqa: BLE001 — cost map may not cover every model
            pass
