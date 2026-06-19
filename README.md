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

## Tools (iteration 1 — read surface only)

| Tool | What it does |
|---|---|
| `query_db(sql)` | Read-only SQL (SELECT/WITH) over the EVERGREEN schema. The main navigation tool. |
| `quote(facts, as_of)` | Runs peico-bench's deterministic rating engine → premium + breakdown. |
| `search_kb(query)` / `get_doc(doc_id)` | The policy wiki (underwriting, compliance, glossary). |

`check_eligibility` and the **write tools** (`bind_policy`, `endorse_policy`, …)
come next, alongside a versioned user simulator to replace the human-in-CLI.

## Configuration

All via env / `.env` (see `.env.example`): `PEICO_AGENT_MODEL`,
`PEICO_BENCH_ROOT` (defaults to `../peico-bench`), `PEICO_DB_PATH`,
`PEICO_MAX_TOOL_ITERS`.
