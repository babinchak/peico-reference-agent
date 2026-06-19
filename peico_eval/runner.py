"""Run an eval task: rollout(s) + grading, pass^k, report. The CLI entry point.

    peico-eval path/to/task.yaml            # one trial
    peico-eval path/to/task.yaml -k 5 -v    # five trials, verbose transcript

Each trial gets a fresh isolated world (World.from_seed), applies the task setup,
snapshots the baseline, runs the rollout, snapshots the final state, and grades.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from peico_agent import tools  # noqa: F401 — import registers read + write tools
from peico_agent.config import settings
from peico_agent.model import Model
from peico_agent.world import World

from . import changeset as cs
from .checks import GradeContext, build_check
from .orchestrator import run_rollout
from .schema import load_task

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


@dataclass
class TrialResult:
    passed: bool
    verdicts: list
    rollout: object


def _snapshot(world) -> dict:
    con = world.connect()
    try:
        return cs.snapshot(con)
    finally:
        con.close()


def _apply_setup(world, setup) -> None:
    if not setup:
        return
    con = world.connect()
    try:
        for stmt in setup:
            con.execute(stmt)
        con.commit()
    finally:
        con.close()


def run_trial(task, *, agent_model, sim_model, judge_model, verbose=False) -> TrialResult:
    world = World.from_seed()
    try:
        _apply_setup(world, task.setup)
        baseline = _snapshot(world)

        def on_event(role, text):
            if verbose:
                who = f"{DIM}customer{RESET}" if role == "customer" else "rep"
                print(f"  {who}> {text}")

        def on_tool(name, args, result):
            if verbose:
                preview = result if len(result) <= 300 else result[:300] + "…"
                print(f"    {DIM}→ {name}({args}) → {preview}{RESET}")

        rollout = run_rollout(
            task, world, agent_model, sim_model, on_event=on_event, on_tool=on_tool
        )
        final = _snapshot(world)

        ctx = GradeContext(
            task=task, transcript=rollout.transcript,
            baseline=baseline, final=final, judge_model=judge_model,
        )
        verdicts = [build_check(spec).run(ctx) for spec in task.checks]
        passed = all(v.passed for v in verdicts if v.required)
        return TrialResult(passed, verdicts, rollout)
    finally:
        world.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peico-eval", description="Run a PEICO eval task")
    parser.add_argument("task", help="path to a task YAML file")
    parser.add_argument("--trials", "-k", type=int, default=1, help="number of trials (pass^k)")
    parser.add_argument("--model", help="agent model override")
    parser.add_argument("--sim-model", help="user-simulator model override")
    parser.add_argument("--judge-model", help="judge model override")
    parser.add_argument("--verbose", "-v", action="store_true", help="print the transcript + tool calls")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    settings.require_world()
    task = load_task(args.task)

    agent_model = Model(args.model or settings.model)
    sim_model = Model(args.sim_model or settings.model)
    judge_model = Model(args.judge_model or settings.model)

    print(f"Task: {task.task_id}  |  persona: {task.persona.name}  |  trials: {args.trials}")
    print(f"agent={agent_model.name}  sim={sim_model.name}  judge={judge_model.name}\n")

    results: list[TrialResult] = []
    for i in range(args.trials):
        if args.verbose:
            print(f"{DIM}--- trial {i + 1}/{args.trials} ---{RESET}")
        r = run_trial(
            task, agent_model=agent_model, sim_model=sim_model,
            judge_model=judge_model, verbose=args.verbose,
        )
        results.append(r)
        tag = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
        print(f"\nTrial {i + 1}: {tag}  ({r.rollout.turns} msgs, stop={r.rollout.stopped_reason})")
        for v in r.verdicts:
            mark = f"{GREEN}ok{RESET}" if v.passed else f"{RED}XX{RESET}"
            flag = " (stochastic)" if v.stochastic else ""
            req = "" if v.required else " (advisory)"
            print(f"  [{mark}] {v.name}{flag}{req}: {v.detail}")
        print()

    passed = sum(1 for r in results if r.passed)
    print(f"=== {task.task_id}: pass^{args.trials} = {passed}/{args.trials} ===")
    print(f"{DIM}agent: {agent_model.usage}{RESET}")
    print(f"{DIM}sim:   {sim_model.usage}{RESET}")
    print(f"{DIM}judge: {judge_model.usage}{RESET}")
    return 0 if passed == args.trials else 1


if __name__ == "__main__":
    raise SystemExit(main())
