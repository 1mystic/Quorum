"""
Known-answer tests for conformal prediction.

The ground truth here is a **theorem**, which is the strongest form available.
Split conformal guarantees, for any exchangeable distribution whatsoever,

    1 - alpha  <=  P(Y in C(X))  <=  1 - alpha + 1 / (n + 1)

and both bounds are asserted. Testing only the lower bound would pass an
implementation that returns the whole real line, which is why the upper bound is
here: it catches over-conservatism, and over-conservatism in an ETA is how a
committee ends up quoting "up to six months" for a leaking tap.

One subtlety that the first draft of these tests got wrong and which is worth
recording. The guarantee is **marginal**: it is a probability over the
randomness in the calibration set AND the test point jointly. Fixing one
calibration set and measuring coverage over many test points measures the
*conditional* coverage, which fluctuates around the marginal with a standard
deviation of about sqrt(alpha (1 - alpha) / n) and legitimately lands outside
the theorem's band at small n. The tests therefore draw a fresh calibration set
per trial, which is the experiment the theorem actually describes.

The censoring tests carry the negative control that matters most in this whole
package: naive split conformal on the resolved subset must UNDER-cover on the
same fixture where the corrected bound does not, so the fixture proves the
correction is doing work rather than merely not breaking.
"""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.stats import conformal
from app.stats.contracts import Evidence
from app.stats.numeric import percentile
from app.stats.streams import RequestSpell, StreamWindow

START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2025, 1, 1, tzinfo=timezone.utc)
WINDOW = StreamWindow(start=START, end=END, timezone="Asia/Kolkata", complete_through=END)


def heteroskedastic(rng, x):
    """
    Deliberately non-Gaussian and heteroskedastic: skewed, heavy-tailed noise
    whose scale varies with x.

    Conformal prediction assumes exchangeability and nothing else, so the test
    generator is chosen to violate every assumption a normal-theory interval
    would make. If the coverage still lands on nominal, the guarantee is real.
    """
    scale = 0.5 + 2.0 * abs(math.sin(x))
    noise = rng.expovariate(1.0) - 0.3 * rng.expovariate(2.0)
    return 3.0 * x + scale * noise


def _marginal_coverage(alpha, n_cal, trials=20000, seed=7):
    """A fresh calibration set per trial: the experiment the theorem describes."""
    rng = random.Random(seed)
    covered = 0
    for _ in range(trials):
        residuals = []
        for _ in range(n_cal):
            x = rng.uniform(0.0, 6.0)
            residuals.append(abs(heteroskedastic(rng, x) - 3.0 * x))
        q = conformal.conformal_quantile(residuals, alpha)
        x = rng.uniform(0.0, 6.0)
        y = heteroskedastic(rng, x)
        if abs(y - 3.0 * x) <= q:
            covered += 1
    return covered / trials


# ---------------------------------------------------------------------------
# The conformal quantile itself
# ---------------------------------------------------------------------------


def test_conformal_quantile_is_the_ceil_n_plus_one_order_statistic():
    """
    Exact: the (ceil((n + 1)(1 - alpha)))-th smallest score.

    With n = 9 and alpha = 0.1, ceil(10 * 0.9) = 9, so the answer is the largest
    of the nine. With n = 19, ceil(20 * 0.9) = 18, the 18th smallest.
    """
    scores = [float(i) for i in range(1, 10)]
    assert conformal.conformal_quantile(scores, 0.1) == 9.0
    scores = [float(i) for i in range(1, 20)]
    assert conformal.conformal_quantile(scores, 0.1) == 18.0


def test_the_quantile_is_infinite_below_the_mathematical_floor():
    """
    Below ceil(1/alpha) - 1 points the interval is the whole line. The guarantee
    still holds there, which is the honest and unusual thing to state: the
    guarantee and the usefulness have different thresholds.
    """
    assert conformal.theoretical_floor(0.1) == 9
    assert math.isinf(conformal.conformal_quantile([1.0] * 8, 0.1))
    assert not math.isinf(conformal.conformal_quantile([1.0] * 9, 0.1))


def test_dropping_the_plus_one_would_under_cover():
    """
    The `+1` in `(n + 1)(1 - alpha)` is the entire finite-sample theorem.

    Asserted as a difference: the conformal quantile is at least the plain
    empirical quantile, and strictly greater where the order statistics differ.
    Taking the plain quantile instead is the standard implementation slip, and
    it under-covers by exactly one observation's worth.
    """
    scores = [float(i) for i in range(1, 21)]
    conformal_q = conformal.conformal_quantile(scores, 0.1)
    plain_q = sorted(scores)[int(math.ceil(20 * 0.9)) - 1]
    assert conformal_q >= plain_q
    assert conformal_q == 19.0 and plain_q == 18.0


def test_weighted_quantile_reduces_to_the_unweighted_one_with_equal_weights():
    """The weighted form must be a strict generalisation, not a different estimator."""
    rng = random.Random(3)
    scores = [rng.gauss(0.0, 1.0) for _ in range(200)]
    weighted = conformal.weighted_conformal_quantile(scores, [1.0] * 200, 0.1)
    assert weighted == pytest.approx(conformal.conformal_quantile(scores, 0.1), abs=1e-12)


# ---------------------------------------------------------------------------
# The coverage theorem, both bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alpha,n_cal", [(0.1, 99), (0.1, 999)])
def test_empirical_coverage_lands_inside_the_theorem_bounds_at_ninety_percent(alpha, n_cal):
    """
    The headline guarantee, measured.

    Tolerance is two binomial standard errors at the number of trials, which is
    a stated statistical criterion rather than a number chosen to pass.
    """
    trials = 20000
    empirical = _marginal_coverage(alpha, n_cal, trials=trials)
    standard_error = math.sqrt(empirical * (1.0 - empirical) / trials)
    lower = 1.0 - alpha
    upper = 1.0 - alpha + 1.0 / (n_cal + 1)
    assert empirical > lower - 2.0 * standard_error
    assert empirical < upper + 2.0 * standard_error


@pytest.mark.parametrize("alpha,n_cal", [(0.05, 99), (0.05, 999)])
def test_empirical_coverage_lands_inside_the_theorem_bounds_at_ninety_five_percent(alpha, n_cal):
    trials = 20000
    empirical = _marginal_coverage(alpha, n_cal, trials=trials)
    standard_error = math.sqrt(empirical * (1.0 - empirical) / trials)
    assert empirical > 1.0 - alpha - 2.0 * standard_error
    assert empirical < 1.0 - alpha + 1.0 / (n_cal + 1) + 2.0 * standard_error


def test_the_interval_is_not_trivially_wide():
    """
    The upper bound of the theorem is what stops an implementation "passing" by
    returning the whole line. Asserted directly on the width as well.
    """
    rng = random.Random(11)
    residuals = [heteroskedastic(rng, rng.uniform(0.0, 6.0)) - 3.0 * 0.0 for _ in range(500)]
    evidence = conformal.split_conformal_interval(residuals, 10.0, END, alpha=0.1)
    lo, hi = evidence.interval
    assert hi - lo < 4.0 * (percentile(sorted(abs(r) for r in residuals), 0.9) + 1.0)


# ---------------------------------------------------------------------------
# The split conformal service
# ---------------------------------------------------------------------------


def test_split_conformal_service_reports_both_theorem_bounds_in_its_caveats():
    rng = random.Random(5)
    residuals = [rng.gauss(0.0, 2.0) for _ in range(500)]
    evidence = conformal.split_conformal_interval(residuals, 12.0, END, alpha=0.1)
    assert isinstance(evidence, Evidence)
    assert evidence.value == 12.0
    assert evidence.interval_kind == "conformal-90"
    assert evidence.interval[0] < 12.0 < evidence.interval[1]
    assert any("MARGINAL" in c for c in evidence.caveats)
    assert any("at most" in c for c in evidence.caveats)


def test_split_conformal_below_the_practical_floor_is_calm_not_wrong():
    rng = random.Random(6)
    residuals = [rng.gauss(0.0, 1.0) for _ in range(40)]
    evidence = conformal.split_conformal_interval(residuals, 5.0, END)
    assert evidence.insufficient_data is True
    assert evidence.interval is None
    assert any("different thresholds" in c for c in evidence.caveats)


def test_an_alpha_with_no_interval_kind_is_refused():
    """
    Relabelling a 70% interval as `conformal-90` would misdescribe the guarantee
    on the wire, so the service refuses rather than rounds.
    """
    with pytest.raises(ValueError):
        conformal.split_conformal_interval([1.0] * 200, 3.0, END, alpha=0.3)


def test_residual_drift_is_detected_and_downgrades_the_envelope():
    """
    Exchangeability is the only assumption, so a residual distribution that
    shifts inside the calibration window is the one thing worth testing hard.
    """
    rng = random.Random(9)
    early = [rng.gauss(0.0, 1.0) for _ in range(250)]
    late = [rng.gauss(6.0, 1.0) for _ in range(250)]
    evidence = conformal.split_conformal_interval(early + late, 5.0, END)
    drift = next(c for c in evidence.checks if c.id == "exchangeability-time-drift")
    assert drift.status == "FAIL"
    assert drift.p_value < 0.01
    assert evidence.render_state == "qualified"


def test_a_stable_residual_stream_passes_the_drift_check():
    rng = random.Random(10)
    residuals = [rng.gauss(0.0, 1.0) for _ in range(500)]
    evidence = conformal.split_conformal_interval(residuals, 5.0, END)
    drift = next(c for c in evidence.checks if c.id == "exchangeability-time-drift")
    assert drift.status == "PASS"
    assert evidence.render_state == "estimate"


# ---------------------------------------------------------------------------
# Censoring: the fixture that proves the correction does work
# ---------------------------------------------------------------------------


def censored_fixture(n=20000, seed=101):
    """
    A known joint distribution of event and censoring times.

    True waiting time is lognormal; censoring is exponential and independent.
    Roughly 43% of requests are still open at the boundary, which is a realistic
    censoring rate for a housing society's complaint queue and is high enough
    that dropping them is visibly wrong.
    """
    rng = random.Random(seed)
    true_times = [math.exp(rng.gauss(1.4, 0.8)) for _ in range(n)]
    censor_times = [rng.expovariate(1.0 / 8.0) for _ in range(n)]
    durations = [min(t, c) for t, c in zip(true_times, censor_times)]
    observed = [t <= c for t, c in zip(true_times, censor_times)]
    return true_times, durations, observed


def test_naive_resolved_only_bound_under_covers_on_the_censored_fixture():
    """
    **The negative control, and the single most important test in this file.**

    `WHERE resolved_at IS NOT NULL` calibrates on exactly the fast requests. Its
    claimed 90% upper bound covers only about 76% of true waiting times: a
    fourteen point shortfall, in the direction that makes the ETA look good,
    which is the worst possible direction for a number a resident will quote.
    """
    true_times, durations, observed = censored_fixture()
    resolved = sorted(d for d, o in zip(durations, observed) if o)
    naive_bound = percentile(resolved, 0.9)
    naive_coverage = sum(1 for t in true_times if t <= naive_bound) / len(true_times)
    assert naive_coverage < 0.80, "the naive bound is supposed to under-cover badly"
    assert naive_coverage == pytest.approx(0.76, abs=0.03)


def test_the_censoring_aware_bound_covers_where_the_naive_one_does_not():
    """
    The same fixture, corrected. Kaplan-Meier uses the open requests as
    censored observations rather than dropping them, and the 90% bound really
    does cover about 90%.
    """
    true_times, durations, observed = censored_fixture()
    times, survival = conformal.kaplan_meier(durations, observed)
    km_bound = conformal.km_quantile(times, survival, 0.9)
    km_coverage = sum(1 for t in true_times if t <= km_bound) / len(true_times)
    assert km_coverage == pytest.approx(0.90, abs=0.02)

    resolved = sorted(d for d, o in zip(durations, observed) if o)
    naive_bound = percentile(resolved, 0.9)
    # And the correction is large, not cosmetic.
    assert km_bound > 1.5 * naive_bound


def test_the_lower_bound_attains_its_nominal_coverage_under_censoring():
    """
    The coverage theorem under censoring: P(T >= L) >= 1 - alpha.

    This is the bound the service guarantees, and it is a lower bound precisely
    because right censoring makes the data informative about short waits and
    systematically missing about long ones.
    """
    true_times, durations, observed = censored_fixture(n=20000, seed=55)
    times, survival = conformal.kaplan_meier(durations, observed)
    lower = conformal.km_quantile(times, survival, 0.1)
    coverage = sum(1 for t in true_times if t >= lower) / len(true_times)
    assert coverage >= 0.90 - 0.02


def _spells(durations, observed, categories=None):
    out = []
    for i, (d, o) in enumerate(zip(durations, observed)):
        out.append(RequestSpell(
            request_ref="r" + str(i),
            opened_at=START,
            at_risk_from=START,
            left_truncated=False,
            duration_hours=float(d) * 24.0,
            duration_active_hours=None,
            event_observed=bool(o),
            outcome="resolved" if o else None,
            terminal_at=START + timedelta(hours=float(d) * 24.0) if o else None,
            censoring="none" if o else "right",
            interval_lo_hours=None,
            interval_hi_hours=None,
            first_response_hours=None,
            paused_hours=0.0,
            reopened_count=0,
            duplicate_count=0,
            category=(categories[i] if categories else "plumbing"),
        ))
    return out


def test_survival_eta_service_reports_a_guaranteed_lower_bound_and_labels_the_rest():
    _, durations, observed = censored_fixture(n=1200, seed=77)
    evidence = conformal.survival_eta_bound(
        _spells(durations, observed), WINDOW, covariates=("category",), seed=1,
    )
    assert isinstance(evidence, Evidence)
    assert evidence.unit == "days"
    assert evidence.n_censored > 0, "open requests must be censored, never dropped"
    if evidence.value:
        assert evidence.value["lower_days"] >= 0.0
        assert evidence.value["coverage_target"] == pytest.approx(0.9)
        assert evidence.value["lower_days"] <= evidence.value["point_days"]
    assert any("only the LOWER bound" in c for c in evidence.caveats)
    assert any("never dropped" in c for c in evidence.caveats)


def test_survival_eta_is_refused_below_its_floor():
    _, durations, observed = censored_fixture(n=120, seed=78)
    evidence = conformal.survival_eta_bound(
        _spells(durations, observed), WINDOW, covariates=(), seed=1,
    )
    assert evidence.insufficient_data is True
    assert any("Kaplan-Meier curve instead" in c for c in evidence.caveats)


def test_survival_eta_blocks_rather_than_showing_a_resident_a_wrong_number():
    """
    A wrong ETA shown to a resident is the single most damaging output this
    platform can produce, so any blocking failure suppresses it entirely.
    """
    rng = random.Random(4)
    n = 600
    # Censoring so aggressive that almost nothing is ever observed: the weights
    # become unstable and no honest ETA exists.
    durations = [rng.expovariate(1.0) for _ in range(n)]
    observed = [i < 110 for i in range(n)]
    evidence = conformal.survival_eta_bound(
        _spells(durations, observed), WINDOW, covariates=(), seed=2,
    )
    if evidence.blocking_failures:
        assert evidence.value == {}
        assert evidence.render_state == "not_interpretable"
        assert all(c.detail for c in evidence.blocking_failures)


# ---------------------------------------------------------------------------
# Mondrian: coverage within each class
# ---------------------------------------------------------------------------


def heterogeneous_classes(n_per_class=400, seed=202):
    """
    Two classes with very different difficulty: an easy one resolved in about a
    day, a hard one taking about two weeks.

    Marginal conformal pools them and produces one bound that is too loose for
    the easy class and too tight for the hard one, which is precisely the
    failure class-conditional coverage exists to fix.
    """
    rng = random.Random(seed)
    durations, observed, categories = [], [], []
    for _ in range(n_per_class):
        durations.append(max(0.05, rng.gauss(1.0, 0.3)))
        observed.append(True)
        categories.append("easy")
    for _ in range(n_per_class):
        durations.append(max(0.05, rng.gauss(14.0, 3.0)))
        observed.append(True)
        categories.append("hard")
    return durations, observed, categories


def test_marginal_conformal_fails_per_class_coverage_on_heterogeneous_classes():
    """
    The negative control for Mondrian.

    A single pooled lower bound is computed from both classes together. For the
    easy class, whose true waits are around one day, a bound derived from the
    pooled distribution sits far too low or far too high to be a per-class
    promise, so per-class coverage departs from nominal in at least one class.
    """
    durations, observed, categories = heterogeneous_classes()
    times, survival = conformal.kaplan_meier(durations, observed)
    pooled_lower = conformal.km_quantile(times, survival, 0.1)
    per_class = {}
    for name in ("easy", "hard"):
        members = [d for d, c in zip(durations, categories) if c == name]
        per_class[name] = sum(1 for d in members if d >= pooled_lower) / len(members)
    # Marginal coverage is fine on average and wrong in at least one class.
    assert min(per_class.values()) < 0.85 or max(per_class.values()) > 0.98
    assert abs(per_class["easy"] - per_class["hard"]) > 0.1


def test_mondrian_gives_each_class_its_own_bound():
    durations, observed, categories = heterogeneous_classes()
    evidence = conformal.mondrian_eta(
        _spells(durations, observed, categories), WINDOW, seed=1, taxonomy="category",
    )
    assert isinstance(evidence, Evidence)
    rows = {row["class"]: row for row in evidence.value}
    assert set(rows) == {"easy", "hard"}
    for row in rows.values():
        assert row["fallback"] is False
        assert row["n"] >= conformal.MIN_PER_CLASS
    # The hard class must get a materially later bound than the easy one.
    assert rows["hard"]["lower_days"] > 3.0 * rows["easy"]["lower_days"]


def test_mondrian_class_conditional_coverage_holds_within_each_class():
    """
    The class-conditional coverage theorem, asserted per class rather than on
    average. This is the thing a resident actually cares about.
    """
    durations, observed, categories = heterogeneous_classes(n_per_class=1000, seed=303)
    evidence = conformal.mondrian_eta(
        _spells(durations, observed, categories), WINDOW, seed=1,
    )
    rows = {row["class"]: row for row in evidence.value}
    for name in ("easy", "hard"):
        members = [d for d, c in zip(durations, categories) if c == name]
        covered = sum(1 for d in members if d >= rows[name]["lower_days"]) / len(members)
        assert covered >= 0.88, name + " class under-covered at " + str(covered)


def test_a_thin_class_falls_back_to_the_marginal_interval_and_says_so():
    durations, observed, categories = heterogeneous_classes()
    # A third class with far too little history to support a promise of its own.
    rng = random.Random(9)
    for _ in range(12):
        durations.append(max(0.05, rng.gauss(5.0, 1.0)))
        observed.append(True)
        categories.append("rare")
    evidence = conformal.mondrian_eta(
        _spells(durations, observed, categories), WINDOW, seed=1,
    )
    rows = {row["class"]: row for row in evidence.value}
    assert rows["rare"]["fallback"] is True
    assert rows["easy"]["fallback"] is False
    check = next(c for c in evidence.checks if c.id == "classes-populated")
    assert check.status == "WARN"


def test_a_taxonomy_so_fine_that_everything_falls_back_is_refused():
    """
    If every class falls back this is marginal conformal with extra steps, and
    saying so is more useful than serving it under a name that promises more.
    """
    rng = random.Random(12)
    n = 400
    durations = [max(0.05, rng.gauss(3.0, 1.0)) for _ in range(n)]
    observed = [True] * n
    categories = ["cat" + str(i) for i in range(n)]
    evidence = conformal.mondrian_eta(
        _spells(durations, observed, categories), WINDOW, seed=1,
    )
    check = next(c for c in evidence.checks if c.id == "taxonomy-not-too-fine")
    assert check.status == "FAIL"
    assert check.blocking is True
    assert evidence.value == []


def test_an_unknown_taxonomy_is_refused():
    durations, observed, categories = heterogeneous_classes(n_per_class=150)
    with pytest.raises(ValueError):
        conformal.mondrian_eta(
            _spells(durations, observed, categories), WINDOW, seed=1, taxonomy="assignee_ref",
        )


def test_every_conformal_service_returns_an_envelope():
    durations, observed, categories = heterogeneous_classes(n_per_class=150)
    spells = _spells(durations, observed, categories)
    rng = random.Random(2)
    envelopes = [
        conformal.split_conformal_interval([rng.gauss(0, 1) for _ in range(300)], 4.0, END),
        conformal.survival_eta_bound(spells, WINDOW, covariates=(), seed=1),
        conformal.mondrian_eta(spells, WINDOW, seed=1),
    ]
    for evidence in envelopes:
        assert isinstance(evidence, Evidence)
        assert evidence.method.startswith("conformal.")
        assert evidence.params_hash
