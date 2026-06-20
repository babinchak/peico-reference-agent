"""The seam the bench drives: a factory + an AgentClient over a session environment.

The bench provisions a session :class:`Environment` and calls ``make_agent(env)``
to get an agent it can run turn by turn (doc 08). This is the *only* integration
point — everything else (tools, loop, model, prompts) is the agent's own business.

The contract types live in the bench (peico.harness); we depend on the bench
one-way and implement against it structurally.
"""
from __future__ import annotations

from peico.harness import AgentReply

from .config import settings
from .loop import Agent
from .model import Model

# The rep speaks first. A fixed, friendly opener keeps the greeting cheap and
# deterministic; the model takes over from the customer's first reply.
WELCOME = "Hi, thanks for contacting PEICO — this is the service desk. How can I help you today?"


class ReferenceAgentClient:
    """Wraps the reference ReAct agent in the bench's welcome/respond contract."""

    def __init__(self, env, *, on_tool=None):
        self.model = Model(settings.model)
        self.agent = Agent(self.model, settings.max_tool_iters, env)
        self.on_tool = on_tool
        # Seed the opener into the conversation so the model knows it already greeted.
        self.agent.messages.append({"role": "assistant", "content": WELCOME})

    def welcome(self) -> str:
        return WELCOME

    def respond(self, customer_message: str) -> AgentReply:
        text, terminate = self.agent.send(customer_message, on_tool=self.on_tool)
        return AgentReply(message=text, terminate=terminate)


def make_agent(env, *, on_tool=None) -> ReferenceAgentClient:
    """Factory the bench resolves via ``--agent peico_agent.adapter:make_agent``."""
    return ReferenceAgentClient(env, on_tool=on_tool)
