"""The user simulator: an LLM playing the customer.

A separate model + persona from the agent. It sees the conversation from the
customer's side (its own lines are the assistant role, the rep's lines are the
user role) and produces one short message per turn. When its goal is met — or
it would realistically give up — it ends its final message with [[DONE]], which
the orchestrator uses to terminate the rollout.
"""
from __future__ import annotations

from .schema import Persona

DONE = "[[DONE]]"

_SIM_SYS = """You are role-playing a CUSTOMER contacting PEICO insurance support over chat. \
You are the customer, NOT the agent — never act as the rep.

Rules:
- Speak only as the customer, one short, natural message at a time.
- Pursue your goal. Provide details when asked, but only details you actually have.
- Do not invent account facts beyond what you're given; if you don't know something, say so.
- When your goal has been accomplished (the rep confirms it's done), or it's clearly \
impossible and you'd give up, thank the rep and end that final message with the token {done}.
- Keep it realistic and concise. No stage directions or narration.""".format(done=DONE)

_PERSONA_TMPL = """Your character:
Name: {name}
{profile}

Your goal:
{goal}

What you know / will reveal if relevant:
{knowledge}"""


class UserSimulator:
    def __init__(self, model, persona: Persona):
        self.model = model
        self.persona = persona

    def _messages(self, transcript: list) -> list[dict]:
        system = _SIM_SYS + "\n\n" + _PERSONA_TMPL.format(
            name=self.persona.name,
            profile=self.persona.profile,
            goal=self.persona.goal,
            knowledge=self.persona.knowledge,
        )
        msgs = [{"role": "system", "content": system}]
        for role, text in transcript:
            # Flip roles: the customer's own turns are "assistant" from its POV.
            msgs.append({"role": "assistant" if role == "customer" else "user", "content": text})
        if not transcript:
            msgs.append(
                {"role": "user", "content": "(Begin the conversation: greet the rep and say what you need.)"}
            )
        return msgs

    def say(self, transcript: list) -> tuple[str, bool]:
        """Return (customer_message, done)."""
        msg = self.model.complete(self._messages(transcript))
        text = (msg.content or "").strip()
        done = DONE in text
        return text.replace(DONE, "").strip(), done
