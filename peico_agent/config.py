"""Runtime configuration, resolved once from the environment.

Everything the agent needs to find the world and the model lives here so the
rest of the code never touches os.environ directly. Paths are resolved eagerly
so a misconfiguration fails loudly at startup, not mid-conversation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # pull .env into the environment if present

# "today" for the snapshot world; promos/rate versions resolve against this.
# Must match peico-bench's WORLD_ANCHOR_DATE (build_reference.py).
WORLD_ANCHOR_DATE = "2025-06-01"

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_bench_root() -> Path:
    env = os.getenv("PEICO_BENCH_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # Default: sibling checkout next to this repo.
    return (_REPO_ROOT.parent / "peico-bench").resolve()


def _resolve_db_path(bench_root: Path) -> Path:
    env = os.getenv("PEICO_DB_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return bench_root / "out" / "peico.sqlite"


@dataclass(frozen=True)
class Settings:
    model: str
    bench_root: Path
    db_path: Path
    max_tool_iters: int
    anchor_date: str = WORLD_ANCHOR_DATE

    def require_world(self) -> None:
        """Fail fast with an actionable message if the dataset isn't built."""
        if not self.db_path.exists():
            raise SystemExit(
                f"World DB not found at {self.db_path}\n"
                f"Build it first in peico-bench:\n"
                f"  python src/peico/build_reference.py && python src/peico/generate.py"
            )


def load_settings() -> Settings:
    bench_root = _resolve_bench_root()
    return Settings(
        model=os.getenv("PEICO_AGENT_MODEL", "anthropic/claude-opus-4-8"),
        bench_root=bench_root,
        db_path=_resolve_db_path(bench_root),
        max_tool_iters=int(os.getenv("PEICO_MAX_TOOL_ITERS", "12")),
    )


settings = load_settings()
