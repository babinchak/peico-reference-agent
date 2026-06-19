"""peico_eval — the benchmark harness that drives the reference agent.

This is deliberately a separate package from `peico_agent` (the system-under-test):
the agent plays the rep, the harness runs the scenario, simulates the customer,
and grades the outcome. Keeping the boundary clean is what lets this package lift
into peico-bench later with the agent plugged in as a dependency.

Pieces:
  schema        — what a Task is (persona, setup, checks) + a YAML loader
  changeset     — pure seed->final DB diff (the deterministic grading backbone)
  checks        — pluggable grading: ChangesetCheck (state) + JudgeCheck (behavior)
  simulator     — the LLM user simulator (plays the customer)
  orchestrator  — runs one rollout: customer <-> rep over a session World
  runner        — load a task, run pass^k, grade, report (the CLI entry point)
"""

__version__ = "0.1.0"
