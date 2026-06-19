"""Human-as-customer REPL for driving the agent in tandem with peico-bench.

Iteration 1's harness stand-in: you play the customer, the agent plays the rep.
The real (versioned) user simulator replaces you later.

  python -m peico_agent            # chat
  python -m peico_agent --verbose  # also print each tool call + result

Commands inside the chat: /reset, /usage, /quit
"""
from __future__ import annotations

import argparse
import sys

from .config import settings
from .loop import Agent
from .model import Model


def _print_tool(name: str, args: dict, result: str) -> None:
    preview = result if len(result) <= 500 else result[:500] + "…"
    print(f"\n  \033[2m→ {name}({args})\033[0m")
    print(f"  \033[2m← {preview}\033[0m\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peico_agent", description="PEICO reference agent (CLI)")
    parser.add_argument("--verbose", "-v", action="store_true", help="print tool calls + results")
    parser.add_argument("--model", help="override the LiteLLM model string")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # breakdowns/glyphs
    except (AttributeError, ValueError):
        pass

    settings.require_world()
    model = Model(args.model or settings.model)
    agent = Agent(model, settings.max_tool_iters)
    on_tool = _print_tool if args.verbose else None

    print(f"PEICO reference agent — model: {model.name}")
    print(f"World: {settings.db_path}  (today = {settings.anchor_date})")
    print("You are the customer. Commands: /reset  /usage  /quit\n")

    while True:
        try:
            user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in ("/quit", "/exit"):
            break
        if user == "/reset":
            agent.reset()
            print("(conversation reset)\n")
            continue
        if user == "/usage":
            print(f"  usage: {model.usage}\n")
            continue

        try:
            reply = agent.send(user, on_tool=on_tool)
        except Exception as exc:  # noqa: BLE001 — keep the REPL alive
            print(f"\n[error] {exc}\n")
            continue
        print(f"\nrep> {reply}\n")

    print(f"\nSession usage: {model.usage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
