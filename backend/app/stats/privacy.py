"""
Disclosure control. The last thing every Pack 4 service calls.

Small communities are small. A per-block statistic over three households is a
disclosure, and there is no admin override, because the admin asking for it is
precisely the risk.

Two mechanisms live here and they answer different threats.

`k_anonymity_suppress` removes rows that describe too few people. Its whole
subtlety is the second pass: an `Evidence` always publishes `n`, so a table with
exactly one suppressed row hands that row back by subtraction. Suppressing one
cell is therefore not suppression at all, and the service keeps suppressing
until nothing suppressed is uniquely determined by what is published.

`laplace_noise` protects a figure that must still be published. It is not a
substitute for suppression: a noised cell over three households is still a cell
about three households, so the two compose, suppression first.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
import random
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, params_hash

# P(|Laplace(0, b)| <= t) = 1 - exp(-t / b), so the two-sided 95% half-width is
# b * ln(20). Written out rather than inlined because the Method Card quotes it.
LAPLACE_95_MULTIPLIER = math.log(20.0)


# ---------------------------------------------------------------------------
# k-anonymity
# ---------------------------------------------------------------------------


def _row_key(row: Mapping[str, Any], index: int) -> Any:
    """
    Whatever the caller keyed `cell_counts` by: an explicit stratum label if the
    row carries one, otherwise the row's position.
    """
    for name in ("stratum", "key", "group", "cell", "label"):
        if name in row:
            return row[name]
    return index


# Fields that name the row rather than describe it. A suppressed row keeps its
# label ("Block C: suppressed") because hiding the label as well tells a reader
# that a whole stratum vanished without telling them which, which is worse for
# them and no better for the household. Everything else is emptied.
_LABEL_FIELDS = ("stratum", "key", "group", "cell", "label", "kind")


def _suppress_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, value in row.items():
        out[name] = value if name in _LABEL_FIELDS else None
    out["suppressed"] = True
    return out


def k_anonymity_suppress(table_evidence, *, k, cell_counts, secondary=True) -> Evidence:
    """privacy.k_anonymity_suppress. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "privacy.k_anonymity_suppress"
    phash = params_hash(method, 1, {"k": k, "secondary": secondary})

    raw = table_evidence.value
    if isinstance(raw, Mapping) and "rows" in raw:
        rows = list(raw["rows"])
        wrapper: Mapping[str, Any] | None = raw
    else:
        rows = list(raw or ())
        wrapper = None

    counts: list[int] = []
    for index, row in enumerate(rows):
        key = _row_key(row, index)
        if isinstance(cell_counts, Mapping):
            count = cell_counts.get(key, cell_counts.get(index, 0))
        else:
            count = cell_counts[index]
        counts.append(int(count))

    published_total = int(table_evidence.n)
    primary = {i for i, c in enumerate(counts) if c < k}

    # ---- complementary suppression -------------------------------------
    # The envelope always publishes `n`, so the hidden cells are known to sum
    # to R = n minus the published rows. That linear constraint plus what an
    # attacker already knows about each hidden cell gives every hidden cell a
    # feasible interval, and a cell whose interval is a single point has not
    # been suppressed at all, it has been spelled out.
    #
    # An attacker knows a PRIMARILY suppressed cell is below k, because that is
    # the published reason it went. So its upper bound is k-1. A cell hidden
    # only to protect the others carries no such bound. This is Cox (1980):
    # two hidden cells are not automatically safe. Counts (20, 4, 4) with k=5
    # hide two cells, leave R = 8, and each hidden cell is then pinned at
    # exactly 4 by the bound alone.
    suppressed = set(primary)
    secondary_added: list[int] = []
    whole_table = False

    def leaks(hidden: set[int]) -> bool:
        if not hidden:
            return False
        if len(hidden) < 2:
            return True
        residual = published_total - sum(c for i, c in enumerate(counts) if i not in hidden)
        if residual <= 0:
            # Every hidden cell is pinned at zero.
            return True
        bounds = {i: (k - 1 if i in primary else residual) for i in hidden}
        for i in hidden:
            others = sum(bounds[j] for j in hidden if j != i)
            low = max(0, residual - others)
            high = min(residual, bounds[i])
            if low >= high:
                return True
        return False

    if suppressed and secondary:
        order = sorted(
            (i for i in range(len(rows)) if i not in suppressed),
            key=lambda i: (counts[i], i),
        )
        for candidate in order:
            if not leaks(suppressed):
                break
            suppressed.add(candidate)
            secondary_added.append(candidate)
        if leaks(suppressed):
            # Nothing short of the whole table protects the primary cells.
            whole_table = True
            for i in range(len(rows)):
                if i not in suppressed:
                    secondary_added.append(i)
                suppressed.add(i)

    out_rows = [
        _suppress_row(row) if i in suppressed else {**row, "suppressed": False}
        for i, row in enumerate(rows)
    ]

    note = {
        "k": int(k),
        "n_rows": len(rows),
        "n_suppressed": len(suppressed),
        "n_primary": len(primary),
        "n_secondary": len(secondary_added),
        "whole_table_suppressed": whole_table,
        "suppressed_keys": [_row_key(rows[i], i) for i in sorted(suppressed)],
        "secondary_reason": (
            "the envelope publishes n, so a single hidden row is recoverable by subtraction"
            if secondary_added else ""
        ),
    }

    if wrapper is not None:
        value: Any = {**wrapper, "rows": out_rows, "suppression": note}
    else:
        value = out_rows

    checks = [
        Check(
            id="k-anonymity-rows",
            label="Every published row describes at least k people",
            status="PASS" if not primary else "FAIL",
            statistic=float(k),
            blocking=False,
            detail=(
                str(len(primary)) + " of " + str(len(rows)) + " rows described fewer than "
                + str(k) + " people and were emptied. There is no admin override for this."
            ) if primary else "",
        ),
        Check(
            id="complementary-suppression",
            label="No hidden row can be recovered by subtracting the published ones",
            status=("SKIPPED" if not secondary else ("FAIL" if whole_table else "PASS")),
            statistic=float(len(secondary_added)),
            blocking=whole_table,
            detail=(
                "Protecting the small rows was impossible without hiding every row, so the "
                "whole table is suppressed. The aggregate n is still published; nothing else is."
            ) if whole_table else (
                str(len(secondary_added)) + " further rows were hidden so that no hidden "
                "count is uniquely determined by the published ones."
                if secondary_added else ""
            ),
        ),
    ]

    caveats = list(table_evidence.caveats)
    if primary:
        caveats.append(
            "Rows covering fewer than " + str(k) + " people are suppressed. This floor is not "
            "configurable per request: a per-block figure over a handful of households "
            "identifies those households."
        )
    if secondary_added and not whole_table:
        caveats.append(
            "A further " + str(len(secondary_added)) + " rows are suppressed only to stop the "
            "small ones being recovered by subtraction from the published total."
        )

    return Evidence(
        value=value,
        n=table_evidence.n,
        method=method,
        as_of=table_evidence.as_of,
        interval=table_evidence.interval,
        interval_kind=table_evidence.interval_kind,
        assumptions=table_evidence.assumptions,
        checks=tuple(table_evidence.checks) + tuple(checks),
        caveats=tuple(caveats),
        insufficient_data=table_evidence.insufficient_data,
        n_censored=table_evidence.n_censored,
        n_excluded=table_evidence.n_excluded,
        exclusion_reason=table_evidence.exclusion_reason,
        unit=table_evidence.unit,
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# The Laplace mechanism
# ---------------------------------------------------------------------------


def laplace_sample(rng: random.Random, scale: float) -> float:
    """
    One Laplace(0, scale) draw by inverse transform.

    u ~ Uniform(-1/2, 1/2); x = -scale * sgn(u) * ln(1 - 2|u|). Written out
    rather than taken from a library so the seeded stream is ours and a test can
    assert the empirical distribution against the analytic CDF.
    """
    u = rng.random() - 0.5
    if u == 0.0:
        return 0.0
    sign = 1.0 if u > 0 else -1.0
    return -scale * sign * math.log(1.0 - 2.0 * abs(u))


def laplace_cdf(x: float, scale: float) -> float:
    """F(x) for Laplace(0, scale). Used by the mechanism's own KS test."""
    if scale <= 0.0:
        return 1.0 if x >= 0.0 else 0.0
    if x < 0.0:
        return 0.5 * math.exp(x / scale)
    return 1.0 - 0.5 * math.exp(-x / scale)


def laplace_noise(value, as_of, *, sensitivity, epsilon, seed, clamp=None) -> Evidence:
    """privacy.laplace_noise. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "privacy.laplace_noise"
    phash = params_hash(method, 1, {
        "sensitivity": sensitivity, "epsilon": epsilon, "seed": seed, "clamp": clamp,
    })

    declared = sensitivity is not None and float(sensitivity) > 0.0
    valid_epsilon = epsilon is not None and float(epsilon) > 0.0

    if not declared or not valid_epsilon:
        detail = (
            "The caller did not state the sensitivity, so the noise scale is arbitrary and "
            "the privacy claim is empty. Nothing is published."
            if not declared else
            "Epsilon must be positive. An epsilon of zero or less is not a privacy budget, "
            "it is an instruction to publish infinite noise. Nothing is published."
        )
        return Evidence(
            value=None,
            n=0,
            method=method,
            as_of=as_of,
            checks=(
                Check(
                    id="sensitivity-declared",
                    label="The caller stated how much one member can move this figure",
                    status="FAIL",
                    blocking=True,
                    detail=detail,
                ),
            ),
            caveats=(detail,),
            params_hash=phash,
        )

    scale = float(sensitivity) / float(epsilon)
    rng = random.Random(seed)
    noised = float(value) + laplace_sample(rng, scale)

    clamped = False
    if clamp is not None:
        low, high = clamp
        if noised < low:
            noised, clamped = float(low), True
        elif noised > high:
            noised, clamped = float(high), True

    half_width = LAPLACE_95_MULTIPLIER * scale
    interval = (noised - half_width, noised + half_width)

    checks = [
        Check(
            id="sensitivity-declared",
            label="The caller stated how much one member can move this figure",
            status="PASS",
            statistic=float(sensitivity),
        ),
        Check(
            id="budget-accounting",
            label="The epsilon this query consumed is returned so a budget can be kept",
            status="PASS",
            statistic=float(epsilon),
            detail=(
                "This query spent epsilon " + repr(float(epsilon)) + ". Epsilon composes by "
                "addition across every query on the same data; keeping the running total is "
                "the service layer's job, the number comes from here."
            ),
        ),
        Check(
            id="clamped",
            label="Whether the noised figure was clipped to a declared range",
            status="WARN" if clamped else "PASS",
            statistic=1.0 if clamped else 0.0,
            detail=(
                "The noised value fell outside the declared range and was clipped to the "
                "boundary. Clipping is post-processing and does not weaken the guarantee, but "
                "it does bias the published figure towards the range."
            ) if clamped else "",
        ),
    ]

    return Evidence(
        value=noised,
        n=1,
        method=method,
        as_of=as_of,
        interval=interval,
        interval_kind="dp-noise-95",
        assumptions=(
            "One member can change the true figure by at most " + repr(float(sensitivity)) + ".",
            "Noise is drawn from Laplace with scale sensitivity/epsilon = " + repr(scale) + ".",
        ),
        checks=tuple(checks),
        caveats=(
            "This figure is deliberately imprecise. It carries Laplace noise at epsilon "
            + repr(float(epsilon)) + " so that no single household can be read out of it.",
            "The interval shown is the noise, not sampling uncertainty. A figure computed from "
            "few people has both, and only one of them is drawn here.",
        ),
        unit="dp-noised",
        params_hash=phash,
    )


def compose_epsilon(spent: Sequence[float]) -> float:
    """
    Sequential composition: epsilons add. Exactly, with no correction term.

    Here so the accounting number has one definition rather than one per caller.
    """
    return math.fsum(float(e) for e in spent)


__all__ = [
    "LAPLACE_95_MULTIPLIER",
    "compose_epsilon",
    "k_anonymity_suppress",
    "laplace_cdf",
    "laplace_noise",
    "laplace_sample",
]
