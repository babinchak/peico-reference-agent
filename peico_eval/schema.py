"""What a Task is, and how to load one from YAML.

A task is a self-contained eval case: who the customer is and what they want
(drives the simulator), any per-task setup applied to the fresh world copy, a
turn budget, and the list of checks that grade the outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Persona:
    name: str
    goal: str
    profile: str = ""
    knowledge: str = ""


@dataclass
class Task:
    task_id: str
    persona: Persona
    checks: list             # list of check spec dicts (see checks.build_check)
    max_turns: int = 8
    setup: list = field(default_factory=list)  # SQL applied to the seed copy first

    @property
    def has_writes_expected(self) -> bool:
        return any(c.get("type") == "changeset" for c in self.checks)


def load_task(path: str | Path) -> Task:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    p = data["persona"]
    return Task(
        task_id=data["task_id"],
        persona=Persona(
            name=p["name"],
            goal=p["goal"],
            profile=p.get("profile", ""),
            knowledge=p.get("knowledge", ""),
        ),
        checks=data.get("checks", []),
        max_turns=int(data.get("max_turns", 8)),
        setup=data.get("setup", []),
    )
