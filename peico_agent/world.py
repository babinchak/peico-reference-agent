"""The seam to the peico-bench world: read-only SQLite + the rating engine.

The agent owns its tools (for now), but the *physics* — the rating engine — must
stay the single source of truth in peico-bench so the engine and the database can
never disagree (peico-bench design principle 8/10). So we import peico-bench's
`rating` module rather than reimplementing pricing here.

If/when this layer migrates into the bench harness, only this file and the tool
wrappers move.
"""
from __future__ import annotations

import sqlite3
import sys
from functools import lru_cache

from .config import settings


def _ensure_rating_importable() -> None:
    src = settings.bench_root / "src" / "peico"
    if not src.exists():
        raise SystemExit(
            f"peico-bench source not found at {src}\n"
            f"Set PEICO_BENCH_ROOT to your peico-bench checkout."
        )
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


@lru_cache(maxsize=1)
def load_rating():
    """Import and return peico-bench's rating module (cached)."""
    _ensure_rating_importable()
    import rating  # noqa: WPS433 — local module from peico-bench/src/peico

    return rating


@lru_cache(maxsize=1)
def rating_context():
    """The reference snapshot the pricing engine reads (cached)."""
    rating = load_rating()
    return rating.load_context(settings.db_path)


def open_ro() -> sqlite3.Connection:
    """A read-only connection to the world DB. Reads are wide open by design."""
    settings.require_world()
    con = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con
