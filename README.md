# peico-reference-agent

The reference **system-under-test** for [`peico-bench`](../peico-bench): a thin
ReAct (reason + act) agent that plays a PEICO insurance sales/service rep. It's a
deliberately simple, transparent baseline — its job is to prove the benchmark is
solvable and to shake out world bugs while the dataset and (later) harness are
built in tandem.

## Stack (and why)

| Piece | Choice | Why |
|---|---|---|
| Agent loop | hand-rolled **ReAct loop** (~one file) | A flat observe→act→observe loop is all a rep needs. Full control of the message list + exact token accounting matters for a benchmark. LangGraph/Pydantic-AI agents are a *future benchmarked variant*, plugged in through the same tool seam — not the baseline. |
| Model access | **LiteLLM** | One interface across providers + built-in token/cost tracking, which the leaderboard reports. Swap models with one string. |
| Tools | owned here, behind a **registry** | The agent owns its tools and loop; the bench grades outcomes, not tool calls. The registry keeps an MCP wrapper or alternate tool set a thin add. |
| World | the bench's **environment service** (`query`/`write`/`rate`/`search_kb`) | The agent never holds the DB. It calls the per-session handle the bench injects; pricing goes through the bench's real engine, so the engine and DB never disagree. |

## Setup

Uses [uv](https://docs.astral.sh/uv/) for env + dependency management.

```bash
uv sync                         # create .venv and install from pyproject.toml + uv.lock
cp .env.example .env            # add ANTHROPIC_API_KEY (or another provider key)
```

Build the world once in the bench repo (the agent reads it):

```bash
cd ../peico-bench
python src/peico/build_reference.py && python src/peico/generate.py
```

## Run

```bash
uv run peico-agent               # you play the customer; the agent plays the rep
uv run peico-agent --verbose     # also print every tool call + result
uv run peico-agent --model anthropic/claude-sonnet-4-6
```

Commands inside the chat: `/reset`, `/usage`, `/quit`.

## Tools

All tools are thin wrappers over the bench's environment service. Reads are wide
open; writes now go through the bench's raw `write(sql)` primitive — rule
enforcement lives in the expected outcome, not the write path (peico-bench
principle 9), and the bench returns the resulting changeset as feedback. Wrapping
writes in named, validating tools is this agent's choice, not a bench requirement.

| Tool | Kind | What it does |
|---|---|---|
| `query_db(sql)` | read | `env.query`: read-only SQL (SELECT/WITH) over the EVERGREEN schema. The main navigation tool. |
| `quote(facts, as_of)` | read | `env.rate`: runs peico-bench's deterministic rating engine → premium + breakdown. |
| `search_kb(query)` / `get_doc(doc_id)` | read | `env.search_kb` / `env.query`: the policy wiki (underwriting, compliance, glossary). |
| `update_contact(cust_id, email, phone)` | write | `env.write`: change a customer's contact details (validates the email, then issues an `UPDATE`). |
| `end_conversation()` | control | Signals the rep is done — the agent closes the session (the rep speaks last). |

More write tools (`bind_policy`, `endorse_policy`, …) come next.

## Running against the benchmark

The eval **harness lives in `peico-bench`** (`peico.harness`): it owns the world,
the environment service, the customer simulator, and grading. This repo provides
the agent and a tiny adapter — `peico_agent.adapter:make_agent` — that the bench
calls to drive the agent (`welcome` / `respond`). Run the bench's `peico-eval`
from this venv (which has both packages):

```bash
uv run peico-eval update_contact_email --agent peico_agent.adapter:make_agent       # one trial
uv run peico-eval update_contact_email --agent peico_agent.adapter:make_agent -k 5 -v # five trials, verbose
```

Tasks, checks (changeset + judge), and `pass^k` are documented in peico-bench
(`docs/08-agent-interface-and-harness-spec.md`).

## Configuration

All via env / `.env` (see `.env.example`): `PEICO_AGENT_MODEL`,
`PEICO_MAX_TOOL_ITERS`. The bench harness reads `PEICO_SIM_MODEL`,
`PEICO_JUDGE_MODEL`, and `PEICO_DB_PATH` from the same `.env` when you run the
eval from here.
