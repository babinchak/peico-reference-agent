"""Read tools — the wide-open read surface a rep uses to navigate EVERGREEN.

Three modalities, mirroring a real rep's desk (peico-bench doc 07):
  - structured data  -> query_db   (read-only SQL over the snapshot)
  - the policy wiki  -> search_kb / get_doc
  - the rules engine -> quote       (runs the real rating engine)

`check_eligibility` is intentionally absent in iteration 1: it needs a
condition-predicate engine that does not yet exist in peico-bench, and building
it here would fork the world's physics. Until then the agent reasons about
eligibility from the rule rows (query_db) + the wiki — i.e. "hard mode".
"""
from __future__ import annotations

import json
import re

from ..config import settings
from ..world import load_rating, open_ro, rating_context
from . import register

_MAX_ROWS = 200

# Only read statements. A bad agent must not be able to mutate via query_db.
_SQL_OK = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_SQL_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


@register(
    name="query_db",
    description=(
        "Run a read-only SQL query (SELECT/WITH only) against the PEICO world "
        "database and get rows back as JSON. This is your primary way to navigate "
        "the legacy EVERGREEN schema: customers, policies, vehicles, dwellings, "
        "coverages, tiers, eligibility_rules, discounts, promotions, rate_tables, "
        "kb_documents, and more. Money is stored in integer cents. Joins, filters, "
        f"and CTEs are allowed. At most {_MAX_ROWS} rows are returned."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "A single SELECT/WITH statement."}
        },
        "required": ["sql"],
    },
)
def query_db(sql: str) -> str:
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return json.dumps({"error": "one_statement_only"})
    if not _SQL_OK.match(stripped) or _SQL_FORBIDDEN.search(stripped):
        return json.dumps({"error": "read_only", "detail": "Only SELECT/WITH queries are allowed."})
    con = open_ro()
    try:
        cur = con.execute(stripped)
        rows = [dict(r) for r in cur.fetchmany(_MAX_ROWS + 1)]
    except Exception as exc:  # noqa: BLE001 — SQL errors are feedback for the model
        return json.dumps({"error": "sql_error", "detail": str(exc)})
    finally:
        con.close()
    truncated = len(rows) > _MAX_ROWS
    return json.dumps(
        {"rows": rows[:_MAX_ROWS], "row_count": min(len(rows), _MAX_ROWS), "truncated": truncated},
        default=str,
    )


@register(
    name="quote",
    description=(
        "Price a policy by running PEICO's deterministic rating engine and get back "
        "the base and final premium (in cents) plus a step-by-step breakdown. Pass "
        "the policy `facts` (line, tier, region, state, coverages, risk fields, "
        "billing_plan, promo_code, etc. — the same fields the rating engine reads) "
        "and an `as_of` date. This is the easy-mode pricing tool."
    ),
    parameters={
        "type": "object",
        "properties": {
            "facts": {
                "type": "object",
                "description": (
                    "Policy facts dict. Required: line, region, tier. Plus the "
                    "line-specific fields the engine needs (e.g. AUTO: peico_risk, "
                    "annual_miles, incidents_5yr; HOME: replacement_cost; LIFE: age, "
                    "face). coverages is a list of coverage codes."
                ),
                "additionalProperties": True,
            },
            "as_of": {
                "type": "string",
                "description": f"Effective date YYYY-MM-DD. Defaults to {settings.anchor_date} (today in the world).",
            },
        },
        "required": ["facts"],
    },
)
def quote(facts: dict, as_of: str | None = None) -> str:
    rating = load_rating()
    when = as_of or settings.anchor_date
    try:
        result = rating.price(facts, when, rating_context())
    except Exception as exc:  # noqa: BLE001 — missing/invalid facts are feedback
        return json.dumps({"error": "quote_failed", "detail": str(exc)})
    return json.dumps({"as_of": when, **result}, default=str)


@register(
    name="search_kb",
    description=(
        "Search the PEICO policy wiki (knowledge-base documents: underwriting "
        "guides, compliance notes, how-tos, the glossary decoding cryptic codes). "
        "Returns matching documents with id, title, category, and a snippet. Use "
        "get_doc to read the full body."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keywords to search for."},
            "limit": {"type": "integer", "description": "Max results (default 8)."},
        },
        "required": ["query"],
    },
)
def search_kb(query: str, limit: int = 8) -> str:
    terms = [t for t in re.split(r"\s+", query.strip().lower()) if t]
    if not terms:
        return json.dumps({"results": []})
    con = open_ro()
    try:
        docs = con.execute(
            "SELECT doc_id, title, category, applies_to, body_md FROM kb_documents"
        ).fetchall()
    finally:
        con.close()
    scored = []
    for d in docs:
        hay = f"{d['title']} {d['category']} {d['body_md']}".lower()
        score = sum(hay.count(t) for t in terms)
        if score:
            body = d["body_md"] or ""
            scored.append((score, d, body))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [
        {
            "doc_id": d["doc_id"],
            "title": d["title"],
            "category": d["category"],
            "applies_to": d["applies_to"],
            "snippet": (body[:240] + "…") if len(body) > 240 else body,
        }
        for _, d, body in scored[: max(1, limit)]
    ]
    return json.dumps({"results": results}, default=str)


@register(
    name="get_doc",
    description="Fetch one knowledge-base document in full by its doc_id (from search_kb).",
    parameters={
        "type": "object",
        "properties": {"doc_id": {"type": "string"}},
        "required": ["doc_id"],
    },
)
def get_doc(doc_id: str) -> str:
    con = open_ro()
    try:
        row = con.execute(
            "SELECT doc_id, title, category, applies_to, body_md FROM kb_documents WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return json.dumps({"error": "not_found", "doc_id": doc_id})
    return json.dumps(dict(row), default=str)
