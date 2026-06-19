"""The seam to the peico-bench world: an isolated, per-session SQLite + the engine.

The agent owns its tools (for now), but the *physics* — the rating engine — must
stay the single source of truth in peico-bench so the engine and the database can
never disagree (peico-bench design principle 8/10). So we import peico-bench's
`rating` module rather than reimplementing pricing here.

A `World` is the per-session handle to one database. The canonical
`out/peico.sqlite` is treated as a read-only *seed*: `World.from_seed()` copies it
to a private temp file so each session is completely independent and writable
without touching the seed or any other session. That isolation is also what makes
parallel/concurrent runs safe — every session gets its own file, so there is no
shared mutable state and no cross-session locking.

If/when this layer migrates into the bench harness, only this file and the tool
wrappers move.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

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
    """Import and return peico-bench's rating module.

    The module is stateless given a context, so importing it once per process is
    safe even across concurrent sessions — the per-session state lives in the
    rating *context*, which each World builds from its own database.
    """
    _ensure_rating_importable()
    import rating  # noqa: WPS433 — local module from peico-bench/src/peico

    return rating


def _missing_db(path: Path) -> SystemExit:
    return SystemExit(
        f"World DB not found at {path}\n"
        f"Build it first in peico-bench:\n"
        f"  python src/peico/build_reference.py && python src/peico/generate.py"
    )


class World:
    """A handle to one session's database (plus its rating context).

    Construct via the classmethods, not directly:
      - ``World.from_seed()`` — copy the seed to a private temp file (isolated,
        writable). This is the per-session default.
      - ``World.open(path)`` — open an existing DB in place (read-only by default).

    Use as a context manager so the temp copy is cleaned up:
        with World.from_seed() as world:
            ...
    """

    def __init__(self, db_path: Path, anchor_date: str, *, writable: bool, _tmp: str | None = None):
        self.db_path = Path(db_path)
        self.anchor_date = anchor_date
        self.writable = writable
        self._tmp = _tmp  # temp dir to remove on cleanup, if this World owns one
        self._rating_ctx = None

    # -- construction ---------------------------------------------------------

    @classmethod
    def open(cls, db_path: Path | str | None = None, *, anchor_date: str | None = None, writable: bool = False) -> "World":
        """Open an existing database in place (read-only by default)."""
        path = Path(db_path) if db_path is not None else settings.db_path
        if not path.exists():
            raise _missing_db(path)
        return cls(path, anchor_date or settings.anchor_date, writable=writable)

    @classmethod
    def from_seed(cls, seed_path: Path | str | None = None, *, anchor_date: str | None = None) -> "World":
        """Copy the seed DB to a private temp file → an isolated, writable session.

        The copy is cheap (the seed is small) and gives the session a database it
        can mutate freely; the seed and every other session are untouched.
        """
        seed = Path(seed_path) if seed_path is not None else settings.db_path
        if not seed.exists():
            raise _missing_db(seed)
        tmp = tempfile.mkdtemp(prefix="peico-session-")
        dst = Path(tmp) / "world.sqlite"
        shutil.copy2(seed, dst)
        return cls(dst, anchor_date or settings.anchor_date, writable=True, _tmp=tmp)

    # -- access ---------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        """A fresh connection to this session's DB (read-only unless writable)."""
        if self.writable:
            con = sqlite3.connect(str(self.db_path))
        else:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    def rating_context(self):
        """The reference snapshot this session's pricing engine reads (cached).

        Built from *this* World's database, so a session that mutates reference
        rows would price against its own copy — never a shared global context.
        """
        if self._rating_ctx is None:
            self._rating_ctx = load_rating().load_context(str(self.db_path))
        return self._rating_ctx

    # -- lifecycle ------------------------------------------------------------

    def cleanup(self) -> None:
        """Remove the temp copy this World owns (no-op for in-place opens)."""
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None
            self._rating_ctx = None

    def __enter__(self) -> "World":
        return self

    def __exit__(self, *exc) -> None:
        self.cleanup()
