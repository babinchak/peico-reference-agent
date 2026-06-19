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
| Tools | owned here, behind a **registry** | The agent owns its tools for now. The registry keeps an MCP wrapper / migration of writes into the harness cheap. |
| World | `peico-bench/out/peico.sqlite` + its `rating.py` | Reads go straight at the DB; pricing calls the bench's real engine so the engine and DB never disagree. |

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

**Reads** are wide open; **writes** are rule-enforcing (validated, parameterized,
never raw SQL from the model).

| Tool | Kind | What it does |
|---|---|---|
| `query_db(sql)` | read | Read-only SQL (SELECT/WITH) over the EVERGREEN schema. The main navigation tool. |
| `quote(facts, as_of)` | read | Runs peico-bench's deterministic rating engine → premium + breakdown. |
| `search_kb(query)` / `get_doc(doc_id)` | read | The policy wiki (underwriting, compliance, glossary). |
| `update_contact(cust_id, email, phone)` | write | Change a customer's contact details after validating the customer exists. |

More write tools (`bind_policy`, `endorse_policy`, …) and `check_eligibility`
come next.

## Evaluation (`peico_eval`)

A τ²-bench-style harness lives in the separate `peico_eval` package: it runs a
scenario where an LLM **user simulator** talks to the agent over an isolated copy
of the world, then grades the outcome.

```bash
peico-eval peico_eval/tasks/update_contact_email.yaml        # one trial
peico-eval peico_eval/tasks/update_contact_email.yaml -k 5 -v # five trials, verbose
```

Each trial gets its own `World.from_seed()` copy, so runs are independent (and
parallelizable later). A **task** (YAML) defines the customer persona + goal, any
per-task setup, and a list of **checks**:

- **changeset** — diffs the seed→final database and asserts it equals the expected
  change (so "the right thing changed" *and* "nothing else did" in one check).
  Deterministic and free.
- **judge** — an LLM grades a behavioral rubric against the transcript. Flagged as
  stochastic; mark it `required: false` to keep it advisory.

`pass^k` reports how many of `k` trials passed.

## Configuration

All via env / `.env` (see `.env.example`): `PEICO_AGENT_MODEL`,
`PEICO_BENCH_ROOT` (defaults to `../peico-bench`), `PEICO_DB_PATH`,
`PEICO_MAX_TOOL_ITERS`.
