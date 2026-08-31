"""
Benford's law, and the two blocking checks that matter more than the test itself.

The Benford probabilities are a closed form, log10(1 + 1/d), so they are
asserted exactly rather than against a typed-in table. The chi-square against
known counts is hand computable and is asserted on a fixture whose arithmetic is
written out in the test.

The negative control is in two parts and both are necessary. A sample drawn from
a genuine Benford process at a fixed seed must NOT be flagged, and a uniform
digit distribution must be. A conformity test that only ever passes and one that
only ever fails are equally worthless.

The structural checks get more attention here than the statistic does, because
in a small community ledger they are almost always the answer. A society that
charges every flat the same monthly maintenance produces a first-digit spike;
running Benford on it yields a spectacular deviation that means the dues are
fixed. The service must refuse, not report.
"""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.stats import audit
from app.stats.streams.ledger import LedgerEntry
from app.stats.streams.window import StreamWindow

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 8, 30, tzinfo=timezone.utc)
WINDOW = StreamWindow(start=START, end=END, timezone="UTC", complete_through=END)


def _entries(amounts, category="expense"):
    out = []
    for i, amount in enumerate(amounts):
        at = START + timedelta(hours=i)
        out.append(LedgerEntry(
            entry_ref="e" + str(i), at=at, booked_at=at, amount_minor=int(amount),
            currency="INR", category=category,
            direction="outflow" if amount < 0 else "inflow",
            instrument="bank_transfer", status="settled",
        ))
    return out


# ---------------------------------------------------------------------------
# The closed form
# ---------------------------------------------------------------------------


def test_the_benford_probabilities_are_the_closed_form_exactly():
    """
    log10(1 + 1/d). The published first-digit table is 0.30103, 0.17609,
    0.12494, 0.09691, 0.07918, 0.06695, 0.05799, 0.05115, 0.04576.
    """
    published = [0.30103, 0.17609, 0.12494, 0.09691, 0.07918,
                 0.06695, 0.05799, 0.05115, 0.04576]
    for digit, expected in zip(range(1, 10), published):
        assert abs(audit.benford_probability(digit) - expected) < 1e-5, digit
    assert abs(math.fsum(audit.benford_probability(d) for d in range(1, 10)) - 1.0) < 1e-12


def test_the_second_digit_probabilities_sum_to_one_and_are_nearly_flat():
    """
    The second-digit distribution is much closer to uniform than the first,
    which is why a second-digit test is weaker. P(0) is about 0.1197 and
    P(9) about 0.0850.
    """
    values = [audit.benford_probability(d, position=2) for d in range(10)]
    assert abs(math.fsum(values) - 1.0) < 1e-12
    assert abs(values[0] - 0.11968) < 1e-4
    assert abs(values[9] - 0.08500) < 1e-4


def test_leading_digit_extraction_is_scale_invariant():
    """Benford's law is about the mantissa, so 3, 30 and 0.003 all lead with 3."""
    for value in (3.0, 30.0, 300.0, 0.003, 34567.0):
        assert audit.leading_digits(value) == 3
    assert audit.leading_digits(0.0) is None
    assert audit.leading_digits(-450.0) == 4
    assert audit.leading_digits(4567.0, position=2) == 5


def test_an_unsupported_digit_position_is_refused():
    with pytest.raises(ValueError):
        audit.benford_probability(1, position=3)
    with pytest.raises(ValueError):
        audit.benford_probability(0, position=1)


# ---------------------------------------------------------------------------
# The chi-square, by hand
# ---------------------------------------------------------------------------


def test_the_chi_square_against_known_counts_is_hand_computable():
    """
    900 amounts distributed exactly as Benford predicts, to the nearest whole
    count, must give a chi-square close to zero. Expected counts are 900 times
    the closed-form shares: 270.9, 158.5, 112.4, 87.2, 71.3, 60.3, 52.2, 46.0,
    41.2, and the fixture uses the rounded versions of those.
    """
    counts = [round(900 * audit.benford_probability(d)) for d in range(1, 10)]
    amounts = []
    rng = random.Random(1)
    for digit, count in zip(range(1, 10), counts):
        for _ in range(count):
            # Vary the magnitude so the span check passes while PINNING the
            # leading digit. The jitter has to stay inside the decade: adding
            # 0 to 9 on top of digit * 10^0 turns a 3 into a 12, which leads
            # with 1, and the fixture then tests counts nobody intended.
            decade = rng.randint(1, 3)
            amounts.append(digit * (10 ** decade) + rng.randrange(10 ** decade))

    out = audit.benford_digits(_entries(amounts), WINDOW)
    observed = {row["digit"]: row["observed"] for row in out.value}
    assert sum(observed.values()) == len(amounts)

    chi_square = math.fsum(
        (observed[d] - len(amounts) * audit.benford_probability(d)) ** 2
        / (len(amounts) * audit.benford_probability(d))
        for d in range(1, 10)
    )
    reported = [c for c in out.checks if c.id == "benford-conformity"][0]
    assert abs(reported.statistic - chi_square) < 1e-9
    assert reported.status == "PASS"


def test_the_wilson_interval_on_each_digit_row_is_the_closed_form():
    counts = [round(900 * audit.benford_probability(d)) for d in range(1, 10)]
    rng = random.Random(2)
    # Spread across three decades, since a fixture confined to one would be
    # correctly refused by the magnitude-span check before any row exists.
    amounts = []
    for digit, count in zip(range(1, 10), counts):
        for _ in range(count):
            decade = rng.randint(1, 3)
            amounts.append(digit * (10 ** decade) + rng.randrange(10 ** decade))
    out = audit.benford_digits(_entries(amounts), WINDOW)
    row = out.value[0]
    x, n, z = row["observed"], out.n, 1.959963984540054
    centre = (x + z * z / 2) / (n + z * z)
    half = z * math.sqrt(x * (n - x) / n + z * z / 4) / (n + z * z)
    assert abs(row["lo"] - (centre - half)) < 1e-9
    assert abs(row["hi"] - (centre + half)) < 1e-9


# ---------------------------------------------------------------------------
# The negative control, both ways
# ---------------------------------------------------------------------------


def _benford_sample(n, seed):
    """
    Draw from a genuine Benford process: 10^U for U uniform on a few decades.
    The mantissa of such a variable is Benford distributed exactly, which is why
    it is the right positive control.
    """
    rng = random.Random(seed)
    return [max(1.0, 10 ** rng.uniform(0.0, 4.0)) for _ in range(n)]


def test_a_genuine_benford_process_is_not_flagged():
    out = audit.benford_digits(_entries(_benford_sample(1200, 20260830)), WINDOW)
    check = [c for c in out.checks if c.id == "benford-conformity"][0]
    assert check.status == "PASS", check.detail
    assert check.p_value > 0.05


def test_a_uniform_digit_distribution_is_flagged():
    """
    The negative control. Equal counts of every leading digit is about as far
    from Benford as a real ledger can get, and if the test does not catch it the
    test is not measuring anything.
    """
    rng = random.Random(7)
    amounts = [
        digit * (10 ** rng.randint(1, 3)) + rng.randrange(10)
        for _ in range(100) for digit in range(1, 10)
    ]
    out = audit.benford_digits(_entries(amounts), WINDOW)
    check = [c for c in out.checks if c.id == "benford-conformity"][0]
    assert check.status == "FAIL"
    assert check.p_value < 1e-6
    assert "reason to open the ledger, and nothing more" in check.detail


# ---------------------------------------------------------------------------
# The blocking structural checks, which matter more
# ---------------------------------------------------------------------------


def test_fixed_monthly_dues_are_refused_rather_than_reported_on():
    """
    The spectacular false positive this service exists to avoid. Every flat pays
    2500 a month; the first digit is 2 every single time. Benford would report a
    devastating deviation that means only that the dues are fixed.
    """
    amounts = [250000] * 320
    out = audit.benford_digits(_entries(amounts, category="dues"), WINDOW)
    assert out.value == []

    bounded = [c for c in out.checks if c.id == "bounded-amounts"][0]
    assert bounded.status == "FAIL" and bounded.blocking is True
    assert "fixed monthly maintenance charge" in bounded.detail
    assert out.render_state == "not_interpretable"


def test_amounts_spanning_less_than_two_orders_of_magnitude_are_refused():
    rng = random.Random(3)
    amounts = [rng.randint(5000, 9000) for _ in range(400)]
    out = audit.benford_digits(_entries(amounts), WINDOW)
    check = [c for c in out.checks if c.id == "magnitude-span"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert check.statistic < 100.0
    assert "two orders of magnitude" in check.detail
    assert out.value == []


def test_heavily_rounded_amounts_are_refused():
    """A vendor who always invoices in round thousands is a bookkeeping habit, not a signal."""
    rng = random.Random(4)
    amounts = [rng.choice([100000, 200000, 500000, 1000000, 2500000]) for _ in range(400)]
    out = audit.benford_digits(_entries(amounts), WINDOW)
    check = [c for c in out.checks if c.id == "bounded-amounts"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert out.value == []


# ---------------------------------------------------------------------------
# The permanent caveat and the floor
# ---------------------------------------------------------------------------


def test_the_not_a_fraud_test_caveat_is_present_on_every_return_path():
    """It is not removable, so no path may omit it, including the refusals."""
    paths = [
        audit.benford_digits(_entries(_benford_sample(1200, 5)), WINDOW),
        audit.benford_digits(_entries([250000] * 320), WINDOW),
        audit.benford_digits(_entries(_benford_sample(10, 5)), WINDOW),
    ]
    for out in paths:
        assert any("prompt to LOOK" in c for c in out.caveats), out.method


def test_the_not_a_fraud_check_is_present_and_warns_even_on_a_clean_result():
    out = audit.benford_digits(_entries(_benford_sample(1200, 6)), WINDOW)
    check = [c for c in out.checks if c.id == "not-a-fraud-test"][0]
    assert check.status == "WARN"
    assert check.blocking is False
    # So even a conforming ledger renders as qualified, never as a bare estimate.
    assert out.render_state == "qualified"


def test_below_three_hundred_entries_the_service_returns_the_calm_empty_state():
    out = audit.benford_digits(_entries(_benford_sample(120, 8)), WINDOW)
    assert out.insufficient_data is True
    assert out.n == 120
    assert "Needs 300 entries" in out.caveats[0]


def test_the_category_filter_and_window_are_both_applied():
    inside = _entries(_benford_sample(400, 9), category="expense")
    other = _entries(_benford_sample(400, 10), category="dues")
    out = audit.benford_digits(inside + other, WINDOW, category="expense")
    assert out.n == 400

    outside = [
        LedgerEntry(entry_ref="old", at=START - timedelta(days=1),
                    booked_at=START - timedelta(days=1), amount_minor=1234,
                    currency="INR", category="expense", direction="inflow",
                    instrument="cash", status="settled")
    ]
    assert audit.benford_digits(inside + outside, WINDOW, category="expense").n == 400


def test_an_unsupported_digit_argument_is_refused():
    with pytest.raises(ValueError, match="first or second"):
        audit.benford_digits(_entries(_benford_sample(400, 11)), WINDOW, digit=3)


def test_the_second_digit_test_runs_and_reports_ten_rows():
    out = audit.benford_digits(_entries(_benford_sample(1200, 12)), WINDOW, digit=2)
    assert [row["digit"] for row in out.value] == list(range(10))
    assert abs(math.fsum(row["expected_share"] for row in out.value) - 1.0) < 1e-12
