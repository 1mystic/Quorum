"""
Hard caps for one turn of the agent loop, plus the usage record for that turn.

An agentic loop's real failure mode is not that it is complicated - it is that
an unbounded loop keeps calling the model, keeps costing money, and keeps the
user waiting. Every limit here is enforced in code rather than requested in the
prompt, because a prompt is a suggestion and a counter is not.

When a cap trips we do NOT raise. exhausted() flips to True, the loop feeds the
model a short "answer from what you already have" note, and the model produces
one final summary. The member gets a real, slightly less complete answer
instead of a 500. That behaviour is what makes the caps safe to set tight.

The usage numbers collected here are also the source of the cost and latency
figures in docs/AI_ARCHITECTURE_DECISIONS.md, section 8 - including the
measured cache_read_input_tokens, which is how we show that prompt caching
genuinely does not fire on Haiku 4.5 rather than just asserting it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from app.core.config import settings


@dataclass
class TurnBudget:
    """Tracks one turn against the configured caps."""

    max_iterations: int = field(default_factory=lambda: settings.AGENT_MAX_ITERATIONS)
    max_tool_calls: int = field(default_factory=lambda: settings.AGENT_MAX_TOOL_CALLS)
    max_input_tokens: int = field(default_factory=lambda: settings.AGENT_MAX_INPUT_TOKENS)
    deadline_seconds: float = field(default_factory=lambda: settings.AGENT_DEADLINE_SECONDS)

    # Counters
    iterations: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    started_at: float = field(default_factory=time.monotonic)
    exhausted_reason: str = ""

    # -- accounting -----------------------------------------------------

    def record_iteration(self) -> None:
        self.iterations += 1

    def record_tool_calls(self, count: int) -> None:
        self.tool_calls += count

    def record_usage(self, usage) -> None:
        """
        Fold one API response's usage into the running totals.

        usage may be an SDK object or a plain dict, and any field may be
        missing, so every read is defensive. A metrics helper must never be
        the thing that breaks a request.
        """
        if usage is None:
            return

        def read(name: str) -> int:
            if isinstance(usage, dict):
                value = usage.get(name)
            else:
                value = getattr(usage, name, None)
            return int(value) if isinstance(value, (int, float)) else 0

        self.input_tokens += read("input_tokens")
        self.output_tokens += read("output_tokens")
        self.cache_read_input_tokens += read("cache_read_input_tokens")
        self.cache_creation_input_tokens += read("cache_creation_input_tokens")

    # -- limits ---------------------------------------------------------

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def exhausted(self) -> bool:
        """
        True when any cap has been reached.

        Sets exhausted_reason on the first trip so the log line says which
        limit actually bound, which is what makes the caps tunable from
        evidence rather than guesswork.
        """
        if self.exhausted_reason:
            return True

        if self.iterations >= self.max_iterations:
            self.exhausted_reason = "max_iterations"
        elif self.tool_calls >= self.max_tool_calls:
            self.exhausted_reason = "max_tool_calls"
        elif self.input_tokens >= self.max_input_tokens:
            self.exhausted_reason = "max_input_tokens"
        elif self.elapsed_seconds >= self.deadline_seconds:
            self.exhausted_reason = "deadline"

        return bool(self.exhausted_reason)

    def remaining_tool_calls(self) -> int:
        return max(self.max_tool_calls - self.tool_calls, 0)

    # -- reporting ------------------------------------------------------

    def estimated_cost_usd(self) -> float:
        """
        Claude Haiku 4.5 list price: 1.00 USD per million input tokens,
        5.00 USD per million output tokens. Cached reads bill at roughly a
        tenth of the input rate.
        """
        uncached_input = max(self.input_tokens - self.cache_read_input_tokens, 0)
        cost = uncached_input * 1.00 / 1_000_000
        cost += self.cache_read_input_tokens * 0.10 / 1_000_000
        cost += self.output_tokens * 5.00 / 1_000_000
        return round(cost, 6)

    def as_log_record(
        self,
        turn_id: str,
        user_label: Optional[str],
        tools_used: list,
        degraded: bool,
    ) -> dict:
        """
        The single structured log line per turn.

        This is the whole of our observability story - see decision 4.17 in
        the architecture report, where hosted tracing was declined in favour
        of something greppable that never sends member data to a vendor.
        """
        return {
            "turn_id": turn_id,
            "user": user_label or "anonymous",
            "iterations": self.iterations,
            "tools": tools_used,
            "tool_calls": self.tool_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "estimated_cost_usd": self.estimated_cost_usd(),
            "latency_ms": int(self.elapsed_seconds * 1000),
            "budget_exhausted": bool(self.exhausted_reason),
            "exhausted_reason": self.exhausted_reason or None,
            "degraded": degraded,
        }
