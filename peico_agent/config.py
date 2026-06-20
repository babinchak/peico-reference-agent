"""Runtime configuration for the reference agent, resolved once from the environment.

The agent no longer holds the database — it talks to the bench's environment
service (query/write/rate/search_kb). So this config is just the agent's own
concerns: which model it runs and how hard it loops. The world (and its anchor
date) is provisioned by the bench harness; the anchor here is only the default the
agent assumes when it has no session to ask, and must match the bench's.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # pull .env into the environment if present

# "Today" in the world. Must match peico-bench's WORLD_ANCHOR_DATE.
WORLD_ANCHOR_DATE = "2025-06-01"


@dataclass(frozen=True)
class Settings:
    model: str
    max_tool_iters: int
    anchor_date: str = WORLD_ANCHOR_DATE


def load_settings() -> Settings:
    return Settings(
        model=os.getenv("PEICO_AGENT_MODEL", "anthropic/claude-opus-4-8"),
        max_tool_iters=int(os.getenv("PEICO_MAX_TOOL_ITERS", "12")),
    )


settings = load_settings()
