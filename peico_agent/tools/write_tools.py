"""Write tools — the reference agent's mutations of the world.

Under the new contract (peico-bench principle 9) the bench exposes a raw
``write(sql)`` primitive and grades the *outcome*, not the write path. This agent
still chooses to wrap writes in named, validating tools — that's an implementation
choice, not a bench requirement — but the mutation itself now goes through
``env.write`` as SQL. The bench returns the resulting changeset as feedback.

The DB end-state these tools produce is exactly what the benchmark grades.
"""
from __future__ import annotations

import json
import re

from . import register

# A deliberately simple email check — enough to reject obvious garbage before we
# bother the world with a write. Tightening it is a rule decision, not parsing.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


@register(
    name="update_contact",
    description=(
        "Update a customer's contact details (email and/or phone). Provide the "
        "customer's cust_id and at least one of email or phone. Look the customer "
        "up first to get their cust_id and to confirm they exist. Validates that "
        "any new email is well-formed before saving. Returns the changeset."
    ),
    parameters={
        "type": "object",
        "properties": {
            "cust_id": {"type": "string", "description": "The customer's ID (e.g. CUST-...)."},
            "email": {"type": "string", "description": "New email address."},
            "phone": {"type": "string", "description": "New phone number."},
        },
        "required": ["cust_id"],
    },
    writes=True,
)
def update_contact(env, cust_id: str, email: str | None = None, phone: str | None = None) -> str:
    if email is None and phone is None:
        return json.dumps({"error": "nothing_to_update", "detail": "Provide email and/or phone."})
    if email is not None and not _EMAIL.match(email.strip()):
        return json.dumps({"error": "invalid_email", "detail": email})

    sets = []
    if email is not None:
        sets.append(f"email = {_sql_str(email.strip())}")
    if phone is not None:
        sets.append(f"phone = {_sql_str(phone.strip())}")
    sql = f"UPDATE customers SET {', '.join(sets)} WHERE cust_id = {_sql_str(cust_id)}"

    result = env.write(sql)
    if isinstance(result, dict) and result.get("ok") and result.get("rows_affected", 0) == 0:
        # The write was valid SQL but matched no customer — surface that as an error
        # the model can recover from (wrong/looked-up-incorrectly cust_id).
        return json.dumps({"error": "customer_not_found", "cust_id": cust_id})
    return json.dumps(result, default=str)
