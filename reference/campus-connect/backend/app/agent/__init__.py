"""
The Campus Connect mini-harness.

A deliberately small agentic loop: seven read-only tools, at most four
iterations, five grounding gates, and a deterministic memory tier the model
cannot write to.

Written by hand rather than pulled from a framework so that every step is
readable and defensible. See docs/AI_ARCHITECTURE_DECISIONS.md for why each
piece is here and why the larger options were declined.

    budget.py     hard caps and the per-turn usage record
    grounding.py  the five gates that keep the model from inventing data
    tools.py      the read-only tool registry
    memory.py     durable per-student facts, never model-authored
    loop.py       the loop itself
"""
