"""peico-reference-agent: the τ-bench-style system-under-test for peico-bench.

A thin ReAct (reason + act) agent that plays a PEICO sales/service rep: it talks
to a customer, reads the world (read-only SQL, the policy wiki, the rating
engine), and — later — writes through rule-enforcing tools. The model is reached
through LiteLLM so any provider can be swapped in by changing one string.

Iteration 1 ships the read surface only (query_db, quote, search_kb, get_doc)
and a human-as-customer CLI. Write tools and a user simulator come next.
"""

__version__ = "0.1.0"
