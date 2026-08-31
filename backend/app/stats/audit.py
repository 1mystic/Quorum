"""
Ledger audit statistics.

A Benford deviation is a prompt to look, not evidence of anything, and the caveat
saying so is not removable.

This service is unusual in the catalog because its Method Card's `wrong_when`
is "almost always, in a small community ledger". Benford's law describes numbers
arising from a process spanning several orders of magnitude; a society charging
every flat the same monthly maintenance produces a first-digit distribution that
is a single spike, and testing it against Benford yields a spectacular deviation
that means only that the dues are fixed. So the two structural checks come
FIRST and they are blocking: if the amounts do not span two orders of magnitude,
or if they are bounded or heavily rounded, the service refuses rather than
reports.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import chi2_sf, wilson_interval

MIN_ENTRIES = 300
MAGNITUDE_SPAN = 100.0          # two orders of magnitude
MODE_SHARE_LIMIT = 0.10         # one repeated amount above this means bounded or fixed
DISTINCT_SHARE_LIMIT = 0.20     # fewer distinct values than this share means rounded

# Nigrini's mean-absolute-deviation conformity bands for the first digit.
MAD_BANDS = (
    (0.006, "close conformity"),
    (0.012, "acceptable conformity"),
    (0.015, "marginally acceptable conformity"),
)


def benford_probability(digit: int, *, position: int = 1) -> float:
    """
    log10(1 + 1/d) for the first digit; the summed form for the second.

    A closed form, so the tests assert it exactly rather than against a table
    somebody typed in.
    """
    if position == 1:
        if not 1 <= digit <= 9:
            raise ValueError("the first significant digit is between 1 and 9, got " + str(digit))
        return math.log10(1.0 + 1.0 / digit)
    if position == 2:
        if not 0 <= digit <= 9:
            raise ValueError("the second digit is between 0 and 9, got " + str(digit))
        return math.fsum(
            math.log10(1.0 + 1.0 / (10 * k + digit)) for k in range(1, 10)
        )
    raise ValueError("audit.benford_digits supports the first two digits only")


def leading_digits(value: float, *, position: int = 1) -> int | None:
    """The digit at the given significant position, or None if there is not one."""
    magnitude = abs(float(value))
    if magnitude <= 0:
        return None
    scaled = magnitude
    while scaled >= 10.0:
        scaled /= 10.0
    while scaled < 1.0:
        scaled *= 10.0
    if position == 1:
        return int(scaled)
    second = int(scaled * 10) % 10
    return second


def benford_digits(entries, window, *, digit=1, category=None) -> Evidence:
    """audit.benford_digits. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "audit.benford_digits"
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": getattr(window, "end", None),
        "digit": digit, "category": category,
    })
    as_of = getattr(window, "end", None)
    start = getattr(window, "start", None)
    if digit not in (1, 2):
        raise ValueError(
            "audit.benford_digits tests the first or second digit, got " + repr(digit)
        )

    amounts = []
    for entry in entries:
        at = getattr(entry, "at", None)
        if start is not None and as_of is not None and not (start <= at < as_of):
            continue
        if category is not None and getattr(entry, "category", None) != category:
            continue
        amount = abs(float(getattr(entry, "amount_minor", 0)))
        if amount > 0:
            amounts.append(amount)

    n = len(amounts)
    levels = list(range(1, 10)) if digit == 1 else list(range(0, 10))
    empty = []

    # The permanent, non-removable caveat. It is here before any arithmetic so
    # that no return path can omit it.
    not_a_fraud_test = Check(
        id="not-a-fraud-test",
        label="What a deviation here does and does not mean",
        status="WARN",
        statistic=None,
        blocking=False,
        detail=(
            "A Benford deviation is a prompt to LOOK, not evidence of anything. Bookkeeping "
            "habits, price points, rounding and a supplier who invoices in round thousands all "
            "produce deviations, and none of them is wrongdoing. This check is permanent and "
            "cannot be switched off."
        ),
    )

    if n < MIN_ENTRIES:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="frequency",
            caveats=(
                "Needs " + str(MIN_ENTRIES) + " entries; has " + str(n) + ".",
                not_a_fraud_test.detail,
            ),
        )

    smallest, largest = min(amounts), max(amounts)
    span = largest / smallest if smallest > 0 else 0.0
    counts_of_value: dict[float, int] = {}
    for amount in amounts:
        counts_of_value[amount] = counts_of_value.get(amount, 0) + 1
    mode_share = max(counts_of_value.values()) / n
    distinct_share = len(counts_of_value) / n

    spans_enough = span >= MAGNITUDE_SPAN
    bounded = mode_share > MODE_SHARE_LIMIT or distinct_share < DISTINCT_SHARE_LIMIT

    magnitude_check = Check(
        id="magnitude-span",
        label="The amounts span enough orders of magnitude for Benford to apply",
        status="PASS" if spans_enough else "FAIL",
        statistic=span,
        blocking=not spans_enough,
        detail=(
            "The largest amount is only " + "{:.1f}".format(span) + " times the smallest, which "
            "is under the two orders of magnitude Benford's law describes. Applying it here "
            "would produce a confident deviation that means nothing at all, so no result is "
            "reported."
        ) if not spans_enough else "",
    )
    bounded_check = Check(
        id="bounded-amounts",
        label="The amounts are neither fixed nor heavily rounded",
        status="PASS" if not bounded else "FAIL",
        statistic=mode_share,
        blocking=bounded,
        detail=(
            "One amount accounts for " + "{:.0%}".format(mode_share) + " of these entries and "
            "only " + "{:.0%}".format(distinct_share) + " of them are distinct. A fixed monthly "
            "maintenance charge is the clearest example: its first digit is a single spike and "
            "the deviation from Benford is guaranteed and meaningless. No result is reported."
        ) if bounded else "",
    )

    if not spans_enough or bounded:
        return Evidence(
            value=empty,
            n=n,
            method=method,
            as_of=as_of,
            checks=(magnitude_check, bounded_check, not_a_fraud_test),
            caveats=(
                "Benford's law does not apply to this set of amounts, so nothing is reported "
                "about them. That is the finding.",
                not_a_fraud_test.detail,
            ),
            unit="frequency",
            params_hash=phash,
        )

    observed = {level: 0 for level in levels}
    for amount in amounts:
        d = leading_digits(amount, position=digit)
        if d is not None and d in observed:
            observed[d] += 1

    rows = []
    chi_square = 0.0
    absolute_deviation = []
    for level in levels:
        expected_share = benford_probability(level, position=digit)
        expected = expected_share * n
        lo, hi = wilson_interval(observed[level], n)
        share = observed[level] / n
        absolute_deviation.append(abs(share - expected_share))
        if expected > 0:
            chi_square += (observed[level] - expected) ** 2 / expected
        rows.append({
            "digit": level,
            "observed": observed[level],
            "expected": expected,
            "observed_share": share,
            "expected_share": expected_share,
            "lo": lo,
            "hi": hi,
            "n": n,
        })

    df = len(levels) - 1
    p_value = chi2_sf(chi_square, df)
    mad = math.fsum(absolute_deviation) / len(levels)
    verdict = "nonconformity"
    for limit, label in MAD_BANDS:
        if mad <= limit:
            verdict = label
            break

    conformity = Check(
        id="benford-conformity",
        label="Whether the observed digits follow the Benford expectation",
        status="PASS" if p_value >= 0.05 else "FAIL",
        statistic=chi_square,
        p_value=p_value,
        blocking=False,
        detail=(
            "Chi-square " + "{:.2f}".format(chi_square) + " on " + str(df) + " df, p = "
            + "{:.4g}".format(p_value) + "; mean absolute deviation "
            + "{:.4f}".format(mad) + " (" + verdict + "). The digits do not follow the "
            "Benford expectation. That is a reason to open the ledger, and nothing more."
        ) if p_value < 0.05 else "",
    )

    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="normal-95",
        assumptions=(
            "Amounts arise from a process spanning several orders of magnitude; here they span "
            "a factor of " + "{:.0f}".format(span) + ".",
            "Amounts are neither bounded nor rounded to a small set of values.",
        ),
        checks=(magnitude_check, bounded_check, conformity, not_a_fraud_test),
        caveats=(
            not_a_fraud_test.detail,
            "Chi-square " + "{:.2f}".format(chi_square) + " on " + str(df) + " df, p = "
            + "{:.4g}".format(p_value) + ". Mean absolute deviation " + "{:.4f}".format(mad)
            + ", which Nigrini's bands call " + verdict + ".",
            "The interval on each digit row is a Wilson interval on the OBSERVED frequency. It "
            "is not an interval on the Benford expectation, which is a constant.",
        ),
        unit="frequency",
        params_hash=phash,
    )


__all__ = [
    "MAD_BANDS",
    "benford_digits",
    "benford_probability",
    "leading_digits",
]
