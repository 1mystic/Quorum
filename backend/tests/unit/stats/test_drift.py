"""
Known-answer tests for drift monitoring.

Nearly everything in this module is exact or has a published critical value:

- PSI against a distribution is 0 exactly, is symmetric exactly, and equals the
  hand-computed `sum((a_i - b_i) * ln(a_i / b_i))` to machine precision.
- The two-sample Kolmogorov-Smirnov statistic is the maximum absolute gap of two
  empirical CDFs and is hand-computable on small inputs.
- The asymptotic Kolmogorov distribution reproduces the published critical
  value: D = 0.1358 at an effective n of 100 gives p = 0.050, which is the
  standard 1.36 / sqrt(n) figure.
- The Wilson interval has a closed form and is checked against it exactly.

One catalog correction is recorded here. The entry for `drift.label_shift`
originally said the difference interval is "checked against the Newcombe hybrid
score published worked examples". Newcombe's paper is not vendored in this
repository and there is no network access, so asserting against a number
remembered rather than read would be exactly the dishonesty this catalog exists
to prevent. The replacement checks the Wilson interval against its closed form
exactly, and the hybrid-score interval against the construction Newcombe
specifies, computed independently in the test from the two Wilson intervals.
"""
import math
import random
from datetime import datetime, timezone

import pytest

from app.stats import drift
from app.stats.contracts import Evidence
from app.stats.numeric import newcombe_difference, norm_ppf, wilson_interval

AS_OF = datetime(2026, 3, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# PSI: exact and hand-computable
# ---------------------------------------------------------------------------


def test_psi_of_a_distribution_against_itself_is_exactly_zero():
    shares = [0.4, 0.35, 0.25]
    assert drift.psi_from_shares(shares, shares) == 0.0


@pytest.mark.parametrize("a,b", [
    ([0.4, 0.35, 0.25], [0.3, 0.4, 0.3]),
    ([0.5, 0.5], [0.1, 0.9]),
    ([0.2, 0.2, 0.2, 0.2, 0.2], [0.05, 0.15, 0.2, 0.3, 0.3]),
])
def test_psi_matches_the_hand_computed_sum(a, b):
    """`sum((a_i - b_i) * ln(a_i / b_i))`, asserted to machine precision."""
    expected = math.fsum((x - y) * math.log(x / y) for x, y in zip(a, b))
    assert drift.psi_from_shares(a, b) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("a,b", [
    ([0.4, 0.35, 0.25], [0.3, 0.4, 0.3]),
    ([0.5, 0.5], [0.1, 0.9]),
])
def test_psi_is_symmetric(a, b):
    """
    Swapping the two arguments negates both factors, so the product and
    therefore the sum are unchanged. A "divergence" that was not symmetric here
    would be a different quantity than the one the thresholds were calibrated on.
    """
    assert drift.psi_from_shares(a, b) == pytest.approx(drift.psi_from_shares(b, a), abs=1e-12)


def test_psi_bins_come_from_the_reference_not_the_current_window():
    """
    The standard implementation bug in this family.

    Recomputing the quantile edges on the current data makes both histograms
    equal by construction and PSI approximately zero always. The test shifts the
    current window hard and asserts PSI notices, which it can only do if the
    edges were frozen from the reference.
    """
    rng = random.Random(1)
    reference = [rng.gauss(0.0, 1.0) for _ in range(2000)]
    shifted = [rng.gauss(2.0, 1.0) for _ in range(2000)]
    edges = drift.quantile_edges(reference, 10)
    reference_counts = drift._histogram(reference, edges)
    shifted_counts = drift._histogram(shifted, edges)
    value = drift.psi_from_shares(drift._shares(reference_counts), drift._shares(shifted_counts))
    assert value > drift.PSI_SIGNIFICANT

    # And with edges wrongly recomputed on the current data, the signal vanishes.
    wrong_edges = drift.quantile_edges(shifted, 10)
    wrong = drift.psi_from_shares(
        drift._shares(drift._histogram(reference, edges)),
        drift._shares(drift._histogram(shifted, wrong_edges)),
    )
    assert wrong < value


def test_psi_service_ranks_the_drifted_feature_first():
    rng = random.Random(2)
    reference = {
        "tenure_days": [rng.gauss(500.0, 100.0) for _ in range(1000)],
        "recency_days": [rng.gauss(20.0, 5.0) for _ in range(1000)],
    }
    current = {
        "tenure_days": [rng.gauss(505.0, 100.0) for _ in range(1000)],
        "recency_days": [rng.gauss(45.0, 5.0) for _ in range(1000)],
    }
    evidence = drift.psi(reference, current, AS_OF)
    assert isinstance(evidence, Evidence)
    assert evidence.value[0]["feature"] == "recency_days"
    assert evidence.value[0]["verdict"] == "significant shift"
    assert evidence.value[1]["verdict"] == "stable"
    assert evidence.interval_kind == "none"
    assert evidence.interval is None


def test_a_feature_that_moved_clean_off_its_reference_bins_still_reports_a_shift():
    """
    Regression test for a real bug found while building this module.

    Bins were being merged when EITHER window's count was thin. When a feature
    moves far enough that the current window empties most of the reference bins,
    every bin is thin, everything merges into a single bin, and PSI reports
    exactly 0.0 for the largest shift the system will ever see. The merge rule
    now looks only at the reference counts: an empty current bin is the finding,
    not a defect in the binning.
    """
    rng = random.Random(77)
    reference = {"recency_days": [rng.gauss(20.0, 5.0) for _ in range(1000)]}
    current = {"recency_days": [rng.gauss(45.0, 5.0) for _ in range(1000)]}
    evidence = drift.psi(reference, current, AS_OF)
    row = evidence.value[0]
    assert row["n_bins"] > 1, "the reference bins must survive the merge"
    assert row["psi"] > drift.PSI_SIGNIFICANT
    assert row["verdict"] == "significant shift"


def test_psi_carries_no_interval_and_says_why():
    rng = random.Random(3)
    values = [rng.gauss(0.0, 1.0) for _ in range(500)]
    evidence = drift.psi({"f": values}, {"f": values}, AS_OF)
    assert evidence.interval is None
    assert any("not derived from any distribution" in c for c in evidence.caveats)
    assert evidence.value[0]["psi"] == pytest.approx(0.0, abs=1e-12)


def test_psi_below_the_window_floor_is_calm():
    rng = random.Random(4)
    small = [rng.gauss(0.0, 1.0) for _ in range(50)]
    evidence = drift.psi({"f": small}, {"f": small}, AS_OF)
    assert evidence.insufficient_data is True


def test_equal_width_binning_is_refused():
    rng = random.Random(5)
    values = [rng.gauss(0.0, 1.0) for _ in range(500)]
    with pytest.raises(ValueError):
        drift.psi({"f": values}, {"f": values}, AS_OF, binning="equal_width")


# ---------------------------------------------------------------------------
# Kolmogorov-Smirnov
# ---------------------------------------------------------------------------


def test_ks_statistic_is_hand_computable():
    """
    For [1, 2, 3, 4] against [2, 3, 4, 5] the empirical CDFs differ by at most
    one observation's worth, 1/4, which is reached at x = 1.
    """
    assert drift.ks_statistic([1, 2, 3, 4], [2, 3, 4, 5]) == 0.25
    assert drift.ks_statistic([1, 2, 3, 4], [1, 2, 3, 4]) == 0.0
    assert drift.ks_statistic([0, 0, 0, 0], [1, 1, 1, 1]) == 1.0


def test_ks_p_value_reproduces_the_published_critical_value():
    """
    The external ground truth for this function: the standard one-sample
    Kolmogorov critical value at n = 100 and alpha = 0.05 is
    1.36 / sqrt(100) = 0.1358. Feeding that statistic back must return 0.05.
    """
    assert drift.ks_p_value(0.1358, 100) == pytest.approx(0.05, abs=0.001)
    assert drift.ks_p_value(1.36 / math.sqrt(100), 100) == pytest.approx(0.05, abs=0.001)


def test_ks_p_value_is_monotone_and_bounded():
    previous = 1.0
    for statistic in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8):
        p = drift.ks_p_value(statistic, 200)
        assert 0.0 <= p <= 1.0
        assert p <= previous
        previous = p


def test_holm_correction_matches_the_hand_computed_step_down():
    """
    Holm: sort ascending, multiply the k-th smallest by (n - k + 1), then
    enforce monotonicity. For [0.01, 0.02, 0.03] with n = 3 that is
    [0.03, 0.04, 0.03] before the running maximum, so [0.03, 0.04, 0.04].
    """
    adjusted = drift.holm_adjust([0.01, 0.02, 0.03])
    assert adjusted[0] == pytest.approx(0.03)
    assert adjusted[1] == pytest.approx(0.04)
    assert adjusted[2] == pytest.approx(0.04)


def test_holm_correction_controls_the_family_wise_false_alarm_rate():
    """
    The reason the correction is there, measured over replicates rather than
    asserted on one lucky seed.

    Twenty features tested at 0.05 with nothing actually drifting raise at least
    one false alarm on the large majority of nights: the theoretical rate is
    1 - 0.95^20, about 64%. Holm brings that back to the nominal 5%.

    Note what this test does NOT claim. Holm controls the family-wise error rate
    at alpha; it does not drive it to zero. An earlier version of this test
    asserted "no feature is ever flagged" and failed on a seed where a genuine
    5%-probability false alarm occurred. That was the test being wrong, not the
    correction, and the fix was to assert the rate the method actually promises.
    """
    replicates = 150
    n_features = 20
    n = 250
    rng = random.Random(1234)
    uncorrected_nights = 0
    holm_nights = 0
    for _ in range(replicates):
        p_values = []
        for _ in range(n_features):
            a = [rng.gauss(0.0, 1.0) for _ in range(n)]
            b = [rng.gauss(0.0, 1.0) for _ in range(n)]
            statistic = drift.ks_statistic(a, b)
            p_values.append(drift.ks_p_value(statistic, n * n / (2.0 * n)))
        if any(p < 0.05 for p in p_values):
            uncorrected_nights += 1
        if any(p < 0.05 for p in drift.holm_adjust(p_values)):
            holm_nights += 1
    uncorrected_rate = uncorrected_nights / replicates
    holm_rate = holm_nights / replicates
    assert uncorrected_rate > 0.40, "without correction the alarm should fire most nights"
    # 5% nominal plus three binomial standard errors at this many replicates.
    assert holm_rate <= 0.05 + 3.0 * math.sqrt(0.05 * 0.95 / replicates) + 0.02
    assert holm_rate < uncorrected_rate


def test_ks_service_finds_a_feature_that_really_moved():
    rng = random.Random(7)
    reference = {
        "stable": [rng.gauss(0.0, 1.0) for _ in range(600)],
        "moved": [rng.gauss(0.0, 1.0) for _ in range(600)],
    }
    current = {
        "stable": [rng.gauss(0.0, 1.0) for _ in range(600)],
        "moved": [rng.gauss(1.0, 1.0) for _ in range(600)],
    }
    evidence = drift.ks_test(reference, current, AS_OF)
    rows = {row["feature"]: row for row in evidence.value}
    assert rows["moved"]["drifted"] is True
    assert rows["stable"]["drifted"] is False
    assert rows["moved"]["statistic"] > rows["stable"]["statistic"]


def test_ks_reports_the_statistic_alongside_the_p_value():
    """
    At a large enough sample a trivially small shift is significant, so the
    statistic has to be visible next to the verdict or the dashboard misleads.
    """
    rng = random.Random(8)
    reference = {"f": [rng.gauss(0.0, 1.0) for _ in range(20000)]}
    current = {"f": [rng.gauss(0.03, 1.0) for _ in range(20000)]}
    evidence = drift.ks_test(reference, current, AS_OF)
    row = evidence.value[0]
    assert row["statistic"] < 0.05, "the shift really is tiny"
    assert any("trivially small shift" in c for c in evidence.caveats)


def test_discrete_features_are_flagged_rather_than_silently_tested():
    reference = {"f": [float(i % 3) for i in range(600)]}
    current = {"f": [float(i % 3) for i in range(600)]}
    evidence = drift.ks_test(reference, current, AS_OF)
    check = next(c for c in evidence.checks if c.id == "continuous-features")
    assert check.status == "WARN"


# ---------------------------------------------------------------------------
# Label shift
# ---------------------------------------------------------------------------


def test_wilson_interval_matches_its_closed_form_exactly():
    """
    The closed form, written out independently in the test so the assertion is
    against the algebra rather than against the implementation.
    """
    successes, trials = 12, 100
    lo, hi = wilson_interval(successes, trials)
    z = norm_ppf(0.975)
    p = successes / trials
    denominator = 1.0 + z * z / trials
    centre = (p + z * z / (2.0 * trials)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denominator
    assert lo == pytest.approx(centre - half, abs=1e-15)
    assert hi == pytest.approx(centre + half, abs=1e-15)


def test_wilson_is_not_degenerate_at_the_boundary():
    """
    "0 of 7 late" under a Wald interval is [0, 0], which is a false statement.
    Wilson gives a real interval, which is why it is used everywhere here.
    """
    lo, hi = wilson_interval(0, 7)
    assert lo == 0.0
    assert hi > 0.3
    lo, hi = wilson_interval(7, 7)
    assert hi == 1.0
    assert lo < 0.7


def test_newcombe_difference_follows_the_published_construction():
    """
    Newcombe's method 10, built from the two Wilson intervals:

        lower = d - sqrt((p1 - l1)^2 + (u2 - p2)^2)
        upper = d + sqrt((u1 - p1)^2 + (p2 - l2)^2)

    Recomputed independently here from the Wilson bounds. The catalog's original
    claim of agreement with Newcombe's published worked examples was replaced by
    this construction check, because the paper is not vendored and asserting a
    remembered number would be worse than asserting the algebra.
    """
    successes_a, trials_a = 56, 70
    successes_b, trials_b = 48, 80
    lo, hi = newcombe_difference(successes_a, trials_a, successes_b, trials_b)
    p_a = successes_a / trials_a
    p_b = successes_b / trials_b
    lo_a, hi_a = wilson_interval(successes_a, trials_a)
    lo_b, hi_b = wilson_interval(successes_b, trials_b)
    difference = p_a - p_b
    expected_lo = difference - math.sqrt((p_a - lo_a) ** 2 + (hi_b - p_b) ** 2)
    expected_hi = difference + math.sqrt((hi_a - p_a) ** 2 + (p_b - lo_b) ** 2)
    assert lo == pytest.approx(expected_lo, abs=1e-15)
    assert hi == pytest.approx(expected_hi, abs=1e-15)
    assert lo < difference < hi


def test_newcombe_interval_is_antisymmetric_under_swapping_the_groups():
    """Swapping the two groups must negate and reverse the interval."""
    lo, hi = newcombe_difference(56, 70, 48, 80)
    swapped_lo, swapped_hi = newcombe_difference(48, 80, 56, 70)
    assert swapped_lo == pytest.approx(-hi, abs=1e-12)
    assert swapped_hi == pytest.approx(-lo, abs=1e-12)


def test_label_shift_detects_the_change_that_invalidates_a_risk_model():
    """
    The catalog's own example: a model fitted when 12% of dues were late is
    meaningless once 30% are.
    """
    reference = [1] * 120 + [0] * 880
    current = [1] * 300 + [0] * 700
    evidence = drift.label_shift(reference, current, AS_OF)
    assert evidence.value["reference_rate"] == pytest.approx(0.12)
    assert evidence.value["current_rate"] == pytest.approx(0.30)
    assert evidence.value["shifted"] is True
    check = next(c for c in evidence.checks if c.id == "base-rate-stable")
    assert check.status == "FAIL"
    assert "blocking" in check.detail
    assert evidence.interval[0] > 0.0     # the difference interval excludes zero


def test_label_shift_stays_quiet_when_the_rate_is_stable():
    rng = random.Random(9)
    reference = [1 if rng.random() < 0.2 else 0 for _ in range(2000)]
    current = [1 if rng.random() < 0.2 else 0 for _ in range(2000)]
    evidence = drift.label_shift(reference, current, AS_OF)
    assert evidence.value["shifted"] is False
    check = next(c for c in evidence.checks if c.id == "base-rate-stable")
    assert check.status == "PASS"
    assert evidence.interval[0] <= 0.0 <= evidence.interval[1]


def test_label_shift_reports_each_window_with_its_own_interval():
    reference = [1] * 120 + [0] * 880
    current = [1] * 300 + [0] * 700
    evidence = drift.label_shift(reference, current, AS_OF)
    value = evidence.value
    assert value["reference_lo"] < value["reference_rate"] < value["reference_hi"]
    assert value["current_lo"] < value["current_rate"] < value["current_hi"]
    assert value["difference"] == pytest.approx(
        value["current_rate"] - value["reference_rate"], abs=1e-15
    )


def test_label_shift_below_its_floor_is_calm():
    evidence = drift.label_shift([1, 0] * 20, [1, 0] * 20, AS_OF)
    assert evidence.insufficient_data is True
    assert evidence.render_state == "not_enough_data"


def test_every_drift_service_returns_an_envelope():
    rng = random.Random(10)
    reference = {"f": [rng.gauss(0.0, 1.0) for _ in range(400)]}
    current = {"f": [rng.gauss(0.1, 1.0) for _ in range(400)]}
    labels_a = [1 if rng.random() < 0.2 else 0 for _ in range(400)]
    labels_b = [1 if rng.random() < 0.25 else 0 for _ in range(400)]
    envelopes = [
        drift.psi(reference, current, AS_OF),
        drift.ks_test(reference, current, AS_OF),
        drift.label_shift(labels_a, labels_b, AS_OF),
    ]
    for evidence in envelopes:
        assert isinstance(evidence, Evidence)
        assert evidence.method.startswith("drift.")
        assert evidence.params_hash


def test_a_bare_sequence_is_accepted_as_a_single_feature():
    rng = random.Random(11)
    reference = [rng.gauss(0.0, 1.0) for _ in range(400)]
    current = [rng.gauss(0.0, 1.0) for _ in range(400)]
    evidence = drift.psi(reference, current, AS_OF)
    assert [row["feature"] for row in evidence.value] == ["value"]


def test_windows_with_no_shared_features_are_refused():
    rng = random.Random(12)
    with pytest.raises(ValueError):
        drift.psi(
            {"a": [rng.gauss(0, 1) for _ in range(400)]},
            {"b": [rng.gauss(0, 1) for _ in range(400)]},
            AS_OF,
        )
