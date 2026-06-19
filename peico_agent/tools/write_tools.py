"""Write tools — rule-enforcing mutations of the world.

The integrity rule (peico-bench principle 9): writes NEVER take raw SQL from the
model. Each write validates against the world first, mutates only what the rule
allows through fixed, parameterized statements, and returns a structured result
or a structured rejection (which the model is expected to read and recover from).

The DB end-state these tools produce is exactly what the benchmark grades.
"""
from __future__ import annotations

import json
import re

from . import register

# A deliberately simple email check — enough to reject obvious garbage. Tightening
# this is a rule decision, not a parsing exercise.
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@register(
    name="update_contact",
    description=(
        "Update a customer's contact details (email and/or phone). Provide the "
        "customer's cust_id and at least one of email or phone. Validates that the "
        "customer exists and that any new email is well-formed before saving. "
        "Returns the updated contact record."
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
def update_contact(world, cust_id: str, email: str | None = None, phone: str | None = None) -> str:
    if email is None and phone is None:
        return json.dumps({"error": "nothing_to_update", "detail": "Provide email and/or phone."})
    if email is not None and not _EMAIL.match(email.strip()):
        return json.dumps({"error": "invalid_email", "detail": email})

    con = world.connect()
    try:
        row = con.execute(
            "SELECT cust_id, email, phone FROM customers WHERE cust_id = ?", (cust_id,)
        ).fetchone()
        if row is None:
            return json.dumps({"error": "customer_not_found", "cust_id": cust_id})

        sets, params = [], []
        if email is not None:
            sets.append("email = ?")
            params.append(email.strip())
        if phone is not None:
            sets.append("phone = ?")
            params.append(phone.strip())
        params.append(cust_id)
        con.execute(f"UPDATE customers SET {', '.join(sets)} WHERE cust_id = ?", params)
        con.commit()
        updated = con.execute(
            "SELECT cust_id, email, phone FROM customers WHERE cust_id = ?", (cust_id,)
        ).fetchone()
    finally:
        con.close()

    return json.dumps(
        {"ok": True, "cust_id": updated["cust_id"], "email": updated["email"], "phone": updated["phone"]}
    )
