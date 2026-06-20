"""Read tools — the wide-open read surface a rep uses to navigate EVERGREEN.

These are the reference agent's *named* tools, each a thin wrapper over the bench
environment service (peico-bench doc 07). Three modalities, mirroring a real rep's
desk:
  - structured data  -> query_db   (env.query: read-only SQL over the session world)
  - the policy wiki  -> search_kb / get_doc (env.search_kb / env.query)
  - the rules engine -> quote       (env.rate: the bench's deterministic engine)

The agent owns these tools; a different implementation could expose entirely
different ones over the same env primitives.
"""
from __future__ import annotations

import json

from ..config import settings
from . import register


@register(
    name="query_db",
    description=(
        "Run a read-only SQL query (SELECT/WITH only) against the PEICO world "
        "database and get rows back as JSON. This is your primary way to navigate "
        "the legacy EVERGREEN schema: customers, policies, vehicles, dwellings, "
        "coverages, tiers, eligibility_rules, discounts, promotions, rate_tables, "
        "kb_documents, and more. Money is stored in integer cents. Joins, filters, "
        "and CTEs are allowed."
    ),
    parameters={
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "A single SELECT/WITH statement."}
        },
        "required": ["sql"],
    },
)
def query_db(env, sql: str) -> str:
    return json.dumps(env.query(sql), default=str)


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
def quote(env, facts: dict, as_of: str | None = None) -> str:
    return json.dumps(env.rate(facts, as_of), default=str)


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
def search_kb(env, query: str, limit: int = 8) -> str:
    return json.dumps(env.search_kb(query, limit), default=str)


@register(
    name="get_doc",
    description="Fetch one knowledge-base document in full by its doc_id (from search_kb).",
    parameters={
        "type": "object",
        "properties": {"doc_id": {"type": "string"}},
        "required": ["doc_id"],
    },
)
def get_doc(env, doc_id: str) -> str:
    safe = doc_id.replace("'", "''")
    result = env.query(
        "SELECT doc_id, title, category, applies_to, body_md "
        f"FROM kb_documents WHERE doc_id = '{safe}'"
    )
    rows = result.get("rows") if isinstance(result, dict) else None
    if rows:
        return json.dumps(rows[0], default=str)
    if isinstance(result, dict) and "error" in result:
        return json.dumps(result, default=str)
    return json.dumps({"error": "not_found", "doc_id": doc_id})
