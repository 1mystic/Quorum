"""
The Evidence envelope, exactly as specified in docs/EVIDENCE_CONTRACT.md section 2.

Every public function in app/stats/ returns an `Evidence`. Never a bare float.
Three layers enforce it with one type: a service cannot return a number because
the return annotation is `Evidence`, a component cannot render a number because
its prop is `Evidence`, and the agent cannot state a number because its tools
return `Evidence` and the grounding layer rejects any figure absent from one.

Nothing in this module reads a clock, touches a database or imports anything
outside the standard library. `as_of` arrives from the caller; see spine rule S6.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping

CheckStatus = Literal["PASS", "WARN", "FAIL", "SKIPPED"]

IntervalKind = Literal[
    "none",              # the value is exact: a count, a rank, a sum
    "normal-95",         # asymptotic normal CI
    "bootstrap-bca-95",  # bias-corrected accelerated bootstrap
    "greenwood-95",      # Kaplan-Meier pointwise CI
    "profile-95",        # profile likelihood
    "credible-95",       # Bayesian posterior, NOT a confidence interval
    "credible-89",
    "conformal-90",      # distribution-free, guaranteed marginal coverage
    "conformal-95",
    "predictive-80",     # forecast prediction interval
    "predictive-95",
    "control-limits",    # SPC chart limits: a decision boundary, not an estimate
    "dp-noise-95",       # differential privacy noise interval, not sampling error
]

# The four shapes Evidence.value may take, per the contract section 4.
ValueShape = Literal["scalar", "series", "table", "structure"]

CONTRACT_VERSION = 1


@dataclass(frozen=True)
class Check:
    """
    One automatic assumption test, run by the service on its own output.

    A hand-written claim in `Evidence.assumptions` is an assertion by the author.
    A `Check` is a measurement. Only the second can fail loudly, which is why
    every service computes its checks rather than describing them.
    """

    id: str                       # "proportional-hazards", "seasonality-stable"
    label: str                    # human sentence: "Hazards stay proportional over time"
    status: CheckStatus
    statistic: float | None = None
    p_value: float | None = None
    detail: str = ""              # what a FAIL means for reading this number
    blocking: bool = False        # True: the value must not be read as an estimate at all

    def __post_init__(self) -> None:
        if self.status not in ("PASS", "WARN", "FAIL", "SKIPPED"):
            raise ValueError("Check.status must be PASS, WARN, FAIL or SKIPPED, got " + repr(self.status))
        if self.blocking and self.status == "FAIL" and not self.detail:
            raise ValueError(
                "a blocking FAIL suppresses the value, so Check.detail must say "
                "what is shown in its place (check id " + self.id + ")"
            )


@dataclass(frozen=True)
class Evidence:
    """
    The envelope. Nothing crosses a layer boundary without one.

    `n` is mandatory and separate from `value` because it is the most
    load-bearing number on the screen. `n_censored` is its own field because
    for request_flow the count of still-open requests is the field that catches
    the industry's most common bug (contract section 6, spine rules C1 and C2).
    """

    value: Any
    n: int
    method: str
    as_of: datetime

    interval: tuple[float, float] | None = None
    interval_kind: IntervalKind = "none"

    assumptions: tuple[str, ...] = ()
    checks: tuple[Check, ...] = ()
    caveats: tuple[str, ...] = ()

    insufficient_data: bool = False
    n_censored: int = 0
    n_excluded: int = 0
    exclusion_reason: str = ""

    unit: str = ""
    params_hash: str = ""
    contract_version: int = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.n < 0:
            raise ValueError("Evidence.n cannot be negative")
        if self.n_censored < 0 or self.n_excluded < 0:
            raise ValueError("Evidence.n_censored and n_excluded cannot be negative")
        if self.n_excluded and not self.exclusion_reason:
            raise ValueError(
                "Evidence.n_excluded is " + str(self.n_excluded)
                + " but exclusion_reason is empty; a dropped observation must state why"
            )
        if self.as_of.tzinfo is None:
            raise ValueError("Evidence.as_of must be timezone-aware UTC (spine rule S1)")
        if self.interval is not None:
            if self.interval_kind == "none":
                raise ValueError("Evidence carries an interval but interval_kind is 'none'")
            lo, hi = self.interval
            if lo > hi:
                raise ValueError("Evidence.interval bounds are inverted: " + repr(self.interval))

    # ---- render-state helpers. The four states in contract section 3. ----

    @property
    def blocking_failures(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.status == "FAIL" and c.blocking)

    @property
    def worst_status(self) -> CheckStatus:
        for status in ("FAIL", "WARN", "PASS"):
            if any(c.status == status for c in self.checks):
                return status  # type: ignore[return-value]
        return "SKIPPED" if self.checks else "PASS"

    @property
    def render_state(self) -> Literal["estimate", "qualified", "not_interpretable", "not_enough_data"]:
        """
        Decided by the data, never by a component. The order matters: not enough
        data wins over everything, because a check on an unestimated value is noise.
        """
        if self.insufficient_data:
            return "not_enough_data"
        if self.blocking_failures:
            return "not_interpretable"
        if any(c.status in ("FAIL", "WARN") for c in self.checks):
            return "qualified"
        return "estimate"

    def to_wire(self) -> dict:
        """
        Snake-case JSON per contract section 5. Nothing is dropped: a field the
        frontend currently ignores is still sent, because the Method Card page
        and the agent both read them.
        """
        return {
            "value": self.value,
            "n": self.n,
            "method": self.method,
            "as_of": self.as_of.isoformat().replace("+00:00", "Z"),
            "interval": list(self.interval) if self.interval is not None else None,
            "interval_kind": self.interval_kind,
            "assumptions": list(self.assumptions),
            "checks": [
                {
                    "id": c.id,
                    "label": c.label,
                    "status": c.status,
                    "statistic": c.statistic,
                    "p_value": c.p_value,
                    "detail": c.detail,
                    "blocking": c.blocking,
                }
                for c in self.checks
            ],
            "caveats": list(self.caveats),
            "insufficient_data": self.insufficient_data,
            "n_censored": self.n_censored,
            "n_excluded": self.n_excluded,
            "exclusion_reason": self.exclusion_reason,
            "unit": self.unit,
            "params_hash": self.params_hash,
            "contract_version": self.contract_version,
        }


@dataclass(frozen=True)
class MethodCard:
    """
    What a method assumes, when it is wrong, and where it comes from.

    A ServiceSpec without one fails at import (docs/RULES.md section 4 as a
    load-time error rather than a review convention). `GET /api/methods/{id}`
    serves this, unauthenticated, because the trust story only works if a
    sceptical reader can check it without an account.
    """

    id: str                       # matches Evidence.method
    name: str
    one_liner: str                # what it answers, in a sentence a secretary understands
    assumes: tuple[str, ...]
    wrong_when: tuple[str, ...]   # the honest failure modes
    min_n: int
    interval_meaning: str         # plain-language reading of THIS interval kind
    references: tuple[str, ...]
    known_answer: str = ""        # the external ground truth its test asserts against
    version: int = 1

    def __post_init__(self) -> None:
        if not self.assumes:
            raise ValueError("MethodCard " + self.id + " has no assumptions; every method has at least one")
        if not self.wrong_when:
            raise ValueError("MethodCard " + self.id + " does not say when it is wrong")
        if not self.references:
            raise ValueError("MethodCard " + self.id + " has no references")
        if not self.interval_meaning:
            raise ValueError("MethodCard " + self.id + " does not explain how to read its interval")
        if self.min_n < 0:
            raise ValueError("MethodCard " + self.id + " has a negative min_n")

    def to_wire(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "one_liner": self.one_liner,
            "assumes": list(self.assumes),
            "wrong_when": list(self.wrong_when),
            "min_n": self.min_n,
            "interval_meaning": self.interval_meaning,
            "references": list(self.references),
            "known_answer": self.known_answer,
            "version": self.version,
        }


class InsufficientData(Exception):
    """
    Raised only when a service cannot even construct a shaped Evidence, for
    example because the tenant has not enabled the stream the service needs.

    Being below `min_n` is NOT this. That returns
    `Evidence(insufficient_data=True, n=<actual>)` with a shaped-but-empty
    value, served as HTTP 200, because honesty must not look like an error
    (contract section 8, docs/STATS_API.md section 5).
    """

    def __init__(self, method: str, n: int, min_n: int, reason: str = "") -> None:
        self.method = method
        self.n = n
        self.min_n = min_n
        self.reason = reason
        message = method + " cannot be computed: has " + str(n) + ", needs " + str(min_n)
        if reason:
            message = message + " (" + reason + ")"
        super().__init__(message)


def insufficient(
    method: str,
    *,
    n: int,
    as_of: datetime,
    empty_value: Any = None,
    unit: str = "",
    caveats: tuple[str, ...] = (),
    n_censored: int = 0,
    params_hash: str = "",
) -> Evidence:
    """
    The calm empty state, as an envelope. A service below its floor calls this;
    it does not raise and it does not return a number with a wide interval and
    hope the reader notices.
    """
    return Evidence(
        value=empty_value,
        n=n,
        method=method,
        as_of=as_of,
        insufficient_data=True,
        n_censored=n_censored,
        unit=unit,
        caveats=caveats,
        params_hash=params_hash,
    )


def _canonical(obj: Any) -> Any:
    """Deterministic ordering so two equal parameter sets hash identically."""
    if isinstance(obj, Mapping):
        return {str(k): _canonical(obj[k]) for k in sorted(obj, key=str)}
    if isinstance(obj, (list, tuple)):
        return [_canonical(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted((_canonical(v) for v in obj), key=repr)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return repr(obj)


def params_hash(method: str, version: int, params: Mapping[str, Any]) -> str:
    """
    A short stable digest over the method id, its version, and every tuning
    parameter including the window bounds and the filter predicate.

    Contract section 7. Deliberately excluded: the tenant id and the data
    itself. The hash identifies HOW a number was computed, not what from. Two
    envelopes with the same params_hash and the same as_of must be byte
    identical, which is what makes the insight_runs cache key sound and lets
    the UI say "computed differently from last month" rather than silently
    drawing a line between incomparable numbers.
    """
    blob = json.dumps(
        {"method": method, "version": version, "params": _canonical(params)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.blake2s(blob.encode("utf-8"), digest_size=4).hexdigest()


__all__ = [
    "CONTRACT_VERSION",
    "Check",
    "CheckStatus",
    "Evidence",
    "InsufficientData",
    "IntervalKind",
    "MethodCard",
    "ValueShape",
    "insufficient",
    "params_hash",
]
