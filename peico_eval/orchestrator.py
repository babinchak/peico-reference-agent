"""Run one rollout: customer (simulator) <-> rep (agent) over a session World.

The orchestrator is deliberately dumb. It alternates turns, captures the
transcript, and stops on the customer's [[DONE]] signal or the turn budget. All
grading happens afterward against the final world + transcript — the loop itself
makes no judgments.
"""
from __future__ import annotations

from dataclasses import dataclass

from peico_agent.config import settings
from peico_agent.loop import Agent

from .simulator import UserSimulator


@dataclass
class Rollout:
    transcript: list      # list of (role, text): role in {"customer", "rep"}
    turns: int
    stopped_reason: str   # "customer_done" | "max_turns"


def run_rollout(task, world, agent_model, sim_model, *, on_event=None, on_tool=None) -> Rollout:
    agent = Agent(agent_model, settings.max_tool_iters, world)
    sim = UserSimulator(sim_model, task.persona)

    transcript: list = []
    reason = "max_turns"

    for _ in range(task.max_turns):
        customer, done = sim.say(transcript)
        if customer:
            transcript.append(("customer", customer))
            if on_event:
                on_event("customer", customer)
        if done:
            reason = "customer_done"
            break

        rep = agent.send(customer, on_tool=on_tool)
        transcript.append(("rep", rep))
        if on_event:
            on_event("rep", rep)

    return Rollout(transcript, len(transcript), reason)
