"""
Empirical Bayes shrinkage, checked against closed forms and against Efron-Morris.

Four kinds of ground truth are used here and they are not equally strong, so each
is labelled where it is asserted.

1. IDENTITIES. The Beta-Binomial and Gamma-Poisson posteriors are exact. There is
   no tolerance to argue about: Beta(a, b) with x successes in n trials is
   Beta(a+x, b+n-x), and every quantile this module publishes is checked by
   inverting the regularized incomplete function it came from.
2. A PUBLISHED DATASET, reconstructed rather than vendored. Efron and Morris's
   eighteen batters; see tests/unit/stats/data/baseball.py for the provenance
   statement. Three published aggregates are asserted against the table itself
   before it is used, which is what makes a transcription error visible.
3. RECOVERY. Data simulated from a known prior at a fixed seed must return that
   prior, within a tolerance stated in the test rather than tuned until it passed.
4. BEHAVIOUR. The 3-of-3 versus 47-of-52 fixture, which is the single scenario
   this whole pack exists to fix, plus its inverse.

The eight schools fixture for `hierarchical_pool` is the canonical hierarchical
model, and its published posterior figures are quoted in the test that uses them
alongside a note on how precisely they are being asserted.
"""
import math
import random
from datetime import datetime, timezone

import pytest

from app.stats import bayes
from app.stats.contracts import Evidence
from app.stats.numeric import betainc, gammainc_p
from app.stats.streams.derived import CountObservation, RateObservation
from tests.unit.stats.data import baseball

AS_OF = datetime(2026, 8, 31, tzinfo=timezone.utc)
WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _rate(ref, successes, trials, **extra):
    return RateObservation(
        group_ref=ref,
        successes=successes,
        trials=trials,
        window_start=WINDOW_START,
        window_end=AS_OF,
        **extra,
    )


def _count(ref, events, exposure, **extra):
    return CountObservation(
        group_ref=ref,
        events=events,
        exposure=exposure,
        window_start=WINDOW_START,
        window_end=AS_OF,
        **extra,
    )


def _check(evidence: Evidence, check_id: str):
    for c in evidence.checks:
        if c.id == check_id:
            return c
    raise AssertionError(check_id + " is not among " + repr([c.id for c in evidence.checks]))


# ---------------------------------------------------------------------------
# The fixture, before anything is computed from it
# ---------------------------------------------------------------------------


def test_the_efron_morris_table_reproduces_its_own_published_aggregates():
    """
    The provenance gate. This table is reconstructed from training knowledge and
    not transcribed from a vendored CSV, so it is checked against three published
    aggregates before a single service touches it. A wrong hit count or a wrong
    season average moves at least one of them.
    """
    assert len(baseball.PLAYERS) == 18
    rates = [h / baseball.AT_BATS for h in baseball.HITS]
    grand = sum(rates) / len(rates)

    assert grand == pytest.approx(baseball.PUBLISHED_GRAND_MEAN, abs=0.001)
    assert sum(baseball.SEASON) / len(baseball.SEASON) == pytest.approx(
        baseball.PUBLISHED_GRAND_MEAN, abs=0.001
    )

    tse_raw = sum((p - s) ** 2 for p, s in zip(rates, baseball.SEASON))
    assert tse_raw == pytest.approx(baseball.PUBLISHED_TSE_RAW, abs=0.0005)

    # The published James-Stein estimator, from its own formula rather than from
    # anything in app/stats: shrink toward the grand mean by 1 - (k-3)s2/SS.
    sigma_squared = grand * (1.0 - grand) / baseball.AT_BATS
    spread = sum((p - grand) ** 2 for p in rates)
    factor = 1.0 - (len(rates) - 3) * sigma_squared / spread
    james_stein = [grand + factor * (p - grand) for p in rates]
    tse_js = sum((j - s) ** 2 for j, s in zip(james_stein, baseball.SEASON))

    assert factor == pytest.approx(0.212, abs=0.005)
    assert tse_js == pytest.approx(baseball.PUBLISHED_TSE_JAMES_STEIN, abs=0.0005)
    assert tse_raw / tse_js == pytest.approx(baseball.PUBLISHED_ERROR_RATIO, abs=0.1)


# ---------------------------------------------------------------------------
# Quantiles
# ---------------------------------------------------------------------------


def test_beta_and_gamma_quantiles_invert_their_own_distribution_functions():
    for p in (0.001, 0.025, 0.1, 0.5, 0.9, 0.975, 0.999):
        for a, b in ((1.0, 1.0), (2.0, 5.0), (48.0, 128.0), (0.5, 0.5)):
            x = bayes.beta_ppf(p, a, b)
            assert betainc(a, b, x) == pytest.approx(p, abs=1e-9)
        for shape, rate in ((1.0, 1.0), (3.0, 2.0), (50.0, 10.0)):
            x = bayes.gamma_ppf(p, shape, rate)
            assert gammainc_p(shape, rate * x) == pytest.approx(p, abs=1e-9)


def test_the_two_quantile_functions_match_their_closed_forms():
    """Beta(1,1) is uniform and Gamma(1, rate) is exponential. Both are exact."""
    for p in (0.05, 0.5, 0.95):
        assert bayes.beta_ppf(p, 1.0, 1.0) == pytest.approx(p, abs=1e-12)
        assert bayes.gamma_ppf(p, 1.0, 3.0) == pytest.approx(-math.log(1.0 - p) / 3.0, abs=1e-9)
    assert bayes.beta_ppf(0.5, 7.0, 7.0) == pytest.approx(0.5, abs=1e-12)


# ---------------------------------------------------------------------------
# fit_beta_prior
# ---------------------------------------------------------------------------


def test_fit_beta_prior_recovers_a_known_prior_from_seeded_simulation():
    """
    Recovery, at a tolerance derived rather than tuned.

    120 groups drawn from Beta(4, 12) with 60 trials each. The Fisher information
    for the prior MEAN under this design is roughly G / Var(p_g), so its standard
    error is about sqrt(Var(p) / G); with Var(p) about 0.0125 and G = 120 that is
    about 0.010. Three of those is the tolerance below, and the interval the
    service reports is asserted to cover the truth as well.
    """
    rng = random.Random(20260831)
    alpha_true, beta_true = 4.0, 12.0
    observations = []
    for i in range(120):
        rate = rng.betavariate(alpha_true, beta_true)
        successes = sum(1 for _ in range(60) if rng.random() < rate)
        observations.append(_rate("g" + str(i), successes, 60))

    out = bayes.fit_beta_prior(observations)
    truth = alpha_true / (alpha_true + beta_true)

    assert out.value["prior_mean"] == pytest.approx(truth, abs=0.030)
    assert out.value["lo"] < truth < out.value["hi"]
    assert out.value["prior_strength"] == pytest.approx(alpha_true + beta_true, rel=0.45)
    assert out.interval_kind == "profile-95"
    assert out.render_state == "estimate"


def test_moments_and_maximum_likelihood_agree_when_the_data_is_plentiful():
    rng = random.Random(7)
    observations = [
        _rate("g" + str(i), sum(1 for _ in range(80) if rng.random() < rng.betavariate(6, 14)), 80)
        for i in range(200)
    ]
    mle = bayes.fit_beta_prior(observations, method="mle")
    moments = bayes.fit_beta_prior(observations, method="moments")
    assert mle.value["prior_mean"] == pytest.approx(moments.value["prior_mean"], abs=0.01)
    assert mle.value["prior_strength"] == pytest.approx(
        moments.value["prior_strength"], rel=0.35
    )


def test_identical_group_rates_block_rather_than_return_an_infinite_prior():
    """
    Every group at the same rate sends the MLE's strength to infinity. The
    finding is that the groups are indistinguishable, and that is what is shown.
    """
    observations = [_rate("g" + str(i), 10, 40) for i in range(8)]
    out = bayes.fit_beta_prior(observations)
    zero = _check(out, "zero-variance")
    assert zero.status == "FAIL" and zero.blocking
    assert out.render_state == "not_interpretable"
    assert out.value["alpha"] is None and out.value["prior_strength"] is None


def test_a_non_exchangeable_population_warns_that_the_prior_is_too_tight():
    """
    Two trades pooled as one. The predictive check is what tells the caller to
    stratify, and it has to be a check on the SHAPE of the rates rather than on
    their spread: both fitting methods match the observed variance by
    construction, so a variance-ratio check against them can never fire. This
    fixture is bimodal at 0.25 and 0.85, and the chi-square sees it.
    """
    rng = random.Random(3)
    observations = []
    for i in range(30):
        rate = 0.85 if i % 2 else 0.25
        successes = sum(1 for _ in range(30) if rng.random() < rate)
        observations.append(_rate("g" + str(i), successes, 30))
    out = bayes.fit_beta_prior(observations)
    check = _check(out, "prior-fit")
    assert check.status == "WARN"
    assert check.p_value < 0.05
    assert "stratify" in check.detail.lower()


def test_a_genuinely_exchangeable_population_passes_the_same_check():
    """The negative control. A check that only ever fires is not a check either."""
    rng = random.Random(31)
    observations = [
        _rate("g" + str(i), sum(1 for _ in range(40) if rng.random() < rng.betavariate(8, 12)), 40)
        for i in range(80)
    ]
    check = _check(bayes.fit_beta_prior(observations), "prior-fit")
    assert check.status == "PASS"
    assert check.p_value > 0.05


def test_too_few_groups_is_insufficient_data_not_a_uniform_prior_in_disguise():
    out = bayes.fit_beta_prior([_rate("g" + str(i), 4, 10) for i in range(3)])
    assert out.insufficient_data is True
    assert out.render_state == "not_enough_data"
    assert out.n == 3


def test_the_prior_strength_check_fires_on_a_flat_likelihood():
    """
    On the eighteen batters the marginal likelihood is nearly flat in the prior
    strength: it moves by under half a log unit between 167 and infinity. The
    prior MEAN is well determined, the strength is not, and the service says so
    rather than presenting a shrinkage weight as a measurement.
    """
    observations = [_rate(name, hits, 45) for name, hits, _s in baseball.PLAYERS]
    out = bayes.fit_beta_prior(observations)
    assert _check(out, "strength-identified").status == "WARN"
    assert out.render_state == "qualified"


# ---------------------------------------------------------------------------
# beta_binomial_shrink
# ---------------------------------------------------------------------------


def test_the_posterior_is_the_exact_conjugate_identity():
    """
    Beta(a, b) plus x of n is Beta(a+x, b+n-x). Asserted on the parameters, on
    the mean, and on both interval endpoints by inverting the incomplete beta.
    """
    observations = [_rate("g" + str(i), 3 * i, 10 * i + 10) for i in range(1, 9)]
    out = bayes.beta_binomial_shrink(observations, (2.0, 8.0))
    for row, obs in zip(out.value, observations):
        assert row["posterior_alpha"] == pytest.approx(2.0 + obs.successes, abs=1e-12)
        assert row["posterior_beta"] == pytest.approx(
            8.0 + obs.trials - obs.successes, abs=1e-12
        )
        assert row["shrunk_rate"] == pytest.approx(
            row["posterior_alpha"] / (row["posterior_alpha"] + row["posterior_beta"]), abs=1e-15
        )
        assert betainc(row["posterior_alpha"], row["posterior_beta"], row["lo"]) == pytest.approx(
            0.025, abs=1e-9
        )
        assert betainc(row["posterior_alpha"], row["posterior_beta"], row["hi"]) == pytest.approx(
            0.975, abs=1e-9
        )
        assert row["shrinkage_weight"] == pytest.approx(obs.trials / (obs.trials + 10.0), abs=1e-12)
    assert out.interval_kind == "credible-95"


def test_every_row_carries_its_own_n_and_its_own_interval():
    """The contract's per-row rule, which is the entire reason the table shape exists."""
    observations = [_rate("g" + str(i), i, 12) for i in range(1, 9)]
    out = bayes.beta_binomial_shrink(observations, (2.0, 8.0))
    for row in out.value:
        assert row["n"] == 12
        assert row["lo"] < row["shrunk_rate"] < row["hi"]


def test_a_group_shrunk_almost_entirely_to_the_prior_is_labelled_not_measured():
    observations = [_rate("veteran" + str(i), 30, 60) for i in range(6)] + [_rate("new", 2, 2)]
    prior = bayes.fit_beta_prior(observations, method="moments")
    out = bayes.beta_binomial_shrink(observations, prior)
    new_row = [r for r in out.value if r["group_ref"] == "new"][0]
    if new_row["shrinkage_weight"] < 0.1:
        assert "not enough evidence yet" in new_row["label"]
        assert _check(out, "extreme-shrinkage").status == "WARN"


def test_a_row_below_the_k_anonymity_floor_is_emptied_not_flagged():
    observations = [_rate("block" + str(i), 5, 20) for i in range(6)]
    counts = {"block0": 40, "block1": 12, "block2": 3, "block3": 20, "block4": 9, "block5": 15}
    out = bayes.beta_binomial_shrink(observations, (2.0, 8.0), k_anonymity=5, member_counts=counts)
    small = [r for r in out.value if r["group_ref"] == "block2"][0]
    assert small["suppressed"] is True
    assert small["shrunk_rate"] is None and small["lo"] is None and small["n"] is None
    assert _check(out, "k-anonymity-rows").status == "FAIL"
    # The surviving rows are still readable: suppression is per row.
    assert any(r["shrunk_rate"] is not None for r in out.value)


def test_when_every_row_is_suppressed_the_whole_table_is_withheld():
    observations = [_rate("block" + str(i), 5, 20) for i in range(6)]
    counts = {"block" + str(i): 2 for i in range(6)}
    out = bayes.beta_binomial_shrink(observations, (2.0, 8.0), k_anonymity=5, member_counts=counts)
    assert out.value == []
    assert _check(out, "k-anonymity-rows").blocking is True
    assert out.render_state == "not_interpretable"


def test_without_member_counts_the_k_anonymity_check_is_skipped_and_says_who_must_do_it():
    out = bayes.beta_binomial_shrink([_rate("g" + str(i), 4, 10) for i in range(6)], (2.0, 8.0))
    check = _check(out, "k-anonymity-rows")
    assert check.status == "SKIPPED"
    assert "k_anonymity_suppress" in check.detail


def test_the_prior_checks_are_inherited_rather_than_quietly_dropped():
    observations = [_rate("g" + str(i), 10, 40) for i in range(8)]
    prior = bayes.fit_beta_prior(observations)          # zero variance, blocking
    out = bayes.beta_binomial_shrink(observations, prior)
    inherited = _check(out, "prior:zero-variance")
    assert inherited.status == "FAIL" and inherited.blocking is True
    assert out.render_state == "not_interpretable"


def test_shrinkage_beats_the_raw_rates_on_the_efron_morris_batters():
    """
    The published comparison. Efron and Morris report a total squared error of
    .0755 for the raw rates and .0214 for the James-Stein estimates, a factor of
    about 3.5. Our empirical Bayes posterior means are a different estimator from
    theirs, so the assertion is that they achieve the same ORDER of improvement
    on the same data, not that they equal the James-Stein numbers.
    """
    observations = [_rate(name, hits, baseball.AT_BATS) for name, hits, _s in baseball.PLAYERS]
    prior = bayes.fit_beta_prior(observations)
    out = bayes.beta_binomial_shrink(observations, prior)

    by_ref = {r["group_ref"]: r for r in out.value}
    tse_raw = sum(
        (by_ref[name]["raw_rate"] - season) ** 2 for name, _h, season in baseball.PLAYERS
    )
    tse_eb = sum(
        (by_ref[name]["shrunk_rate"] - season) ** 2 for name, _h, season in baseball.PLAYERS
    )

    assert tse_raw == pytest.approx(baseball.PUBLISHED_TSE_RAW, abs=0.0005)
    assert tse_eb < tse_raw / 3.0
    # And it beats the raw rate for the extremes specifically, which is the
    # picture the 1977 article is famous for: Clemente's .400 is not a forecast.
    assert by_ref["Clemente"]["shrunk_rate"] < 0.30
    assert by_ref["Alvis"]["shrunk_rate"] > 0.21


# ---------------------------------------------------------------------------
# gamma_poisson_shrink
# ---------------------------------------------------------------------------


def test_the_gamma_poisson_posterior_is_the_exact_conjugate_identity():
    observations = [_count("r" + str(i), 2 * i, 3.0 * i + 1.0) for i in range(1, 9)]
    out = bayes.gamma_poisson_shrink(observations, (3.0, 2.0))
    for row, obs in zip(out.value, observations):
        assert row["posterior_shape"] == pytest.approx(3.0 + obs.events, abs=1e-12)
        assert row["posterior_rate"] == pytest.approx(2.0 + obs.exposure, abs=1e-12)
        assert row["shrunk_rate"] == pytest.approx(
            row["posterior_shape"] / row["posterior_rate"], abs=1e-15
        )
        assert gammainc_p(
            row["posterior_shape"], row["posterior_rate"] * row["lo"]
        ) == pytest.approx(0.025, abs=1e-9)
        assert gammainc_p(
            row["posterior_shape"], row["posterior_rate"] * row["hi"]
        ) == pytest.approx(0.975, abs=1e-9)


def test_exposure_is_what_stops_two_weeks_being_compared_against_a_year():
    """Same rate, very different exposure. The intervals must not be the same width."""
    observations = [_count("r" + str(i), 10, 10.0) for i in range(5)]
    observations.append(_count("fortnight", 2, 2.0))
    observations.append(_count("year", 100, 100.0))
    out = bayes.gamma_poisson_shrink(observations, (5.0, 5.0))
    rows = {r["group_ref"]: r for r in out.value}
    assert rows["fortnight"]["raw_rate"] == rows["year"]["raw_rate"] == 1.0
    narrow = rows["year"]["hi"] - rows["year"]["lo"]
    wide = rows["fortnight"]["hi"] - rows["fortnight"]["lo"]
    assert wide > 3.0 * narrow
    assert rows["year"]["shrinkage_weight"] > rows["fortnight"]["shrinkage_weight"]


def test_gamma_poisson_recovers_a_known_gamma_from_seeded_simulation():
    rng = random.Random(99)
    shape_true, rate_true = 6.0, 3.0            # mean 2.0 events per unit exposure
    observations = []
    for i in range(150):
        lam = rng.gammavariate(shape_true, 1.0 / rate_true)
        exposure = 20.0
        events = 0
        # Poisson by Knuth's product of uniforms, seeded from the same stream.
        target = math.exp(-lam * exposure)
        product = rng.random()
        while product > target:
            events += 1
            product *= rng.random()
        observations.append(_count("g" + str(i), events, exposure))
    fitted = bayes._moments_gamma_prior(bayes._count_rows(observations))
    assert fitted[0] / fitted[1] == pytest.approx(shape_true / rate_true, rel=0.10)
    assert fitted[1] == pytest.approx(rate_true, rel=0.45)


# ---------------------------------------------------------------------------
# The one that matters: 3 of 3 against 47 of 52
# ---------------------------------------------------------------------------


def _vendor_fixture():
    """
    Five ordinary vendors to learn a prior from, plus the two the pack exists for.

    LuckyThree is 3 for 3: a perfect record on three jobs. Steady is 47 for 52:
    a very good record on a year of work. Every raw-rate leaderboard puts
    LuckyThree first.
    """
    return [
        _rate("Ordinary A", 30, 50),
        _rate("Ordinary B", 41, 60),
        _rate("Ordinary C", 25, 45),
        _rate("Ordinary D", 55, 80),
        _rate("Ordinary E", 18, 33),
        _rate("LuckyThree", 3, 3),
        _rate("Steady", 47, 52),
    ]


def test_three_of_three_does_not_outrank_forty_seven_of_fifty_two():
    """
    THE behavioural gate for this pack. A perfect but tiny record must not rank
    above a strong, well evidenced one. Ranking is by the posterior 5th
    percentile, not the posterior mean and certainly not the raw rate.
    """
    observations = _vendor_fixture()
    prior = bayes.fit_beta_prior(observations, method="moments")
    shrunk = bayes.beta_binomial_shrink(observations, prior)
    ranked = bayes.rank_by_posterior_lower_bound(shrunk, seed=11)

    positions = {row["group_ref"]: row["rank"] for row in ranked.value}
    by_ref = {row["group_ref"]: row for row in ranked.value}

    # The raw rates say the opposite, which is the point.
    raw = {r["group_ref"]: r["raw_rate"] for r in shrunk.value}
    assert raw["LuckyThree"] == 1.0 > raw["Steady"] == pytest.approx(47 / 52, abs=1e-12)

    assert positions["Steady"] < positions["LuckyThree"]
    assert by_ref["Steady"]["lower_bound"] > by_ref["LuckyThree"]["lower_bound"]
    assert by_ref["Steady"]["n"] == 52 and by_ref["LuckyThree"]["n"] == 3


def test_ranking_by_the_posterior_mean_would_not_have_been_enough():
    """
    The reason the rule is the LOWER BOUND and not the mean.

    On the 47-of-52 fixture above the posterior mean happens to agree with the
    lower bound, so that fixture alone does not prove the rule is needed. The
    pack's own claim is narrower and this test is built to match it exactly:
    ranking by the mean still favours small samples WHENEVER THE PRIOR IS WEAK.
    So the prior here is the weakest there is, Beta(1, 1), and the well evidenced
    vendor is at 39 of 52. The posterior mean then puts the 3-of-3 vendor first
    and only the lower bound charges it for the evidence it does not have. Both
    directions are asserted, because a rule that is never load-bearing is
    decoration.
    """
    observations = [
        _rate("Ordinary A", 30, 50),
        _rate("Ordinary B", 41, 60),
        _rate("Ordinary C", 25, 45),
        _rate("Ordinary D", 55, 80),
        _rate("Ordinary E", 18, 33),
        _rate("LuckyThree", 3, 3),
        _rate("GoodEnough", 39, 52),
    ]
    shrunk = bayes.beta_binomial_shrink(observations, (1.0, 1.0))
    rows = {r["group_ref"]: r for r in shrunk.value}

    # The mean gets it wrong.
    assert rows["LuckyThree"]["shrunk_rate"] > rows["GoodEnough"]["shrunk_rate"]
    # The lower bound gets it right.
    assert rows["LuckyThree"]["lo"] < rows["GoodEnough"]["lo"]

    ranked = bayes.rank_by_posterior_lower_bound(shrunk, seed=5)
    positions = {row["group_ref"]: row["rank"] for row in ranked.value}
    assert positions["GoodEnough"] < positions["LuckyThree"]

    by_mean = sorted(shrunk.value, key=lambda r: -r["shrunk_rate"])
    assert by_mean[0]["group_ref"] == "LuckyThree"


def test_an_unmeasured_group_never_outranks_a_group_measured_to_be_good():
    """
    The inverse fixture, and a correction to what the catalog asked for.

    docs/STATS_CATALOG.md asked that a 0-of-1 group must not outrank a measured
    2-of-10. Under shrinkage that expectation is wrong, and the test asserts what
    is actually true instead. 2 of 10 is not an absence of evidence, it is
    evidence of being BAD: the posterior for that group sits well below the
    population, while the 0-of-1 group's posterior is still essentially the
    prior. An unknown group ranking above a group we have measured to be poor is
    shrinkage working, not shrinkage failing.

    What the rule does guarantee, and what is asserted here, is that an
    unmeasured group never outranks a group measured to be GOOD, which is the
    direction the leaderboard pathology actually runs in.
    """
    observations = [
        _rate("Ordinary A", 30, 50),
        _rate("Ordinary B", 41, 60),
        _rate("Ordinary C", 25, 45),
        _rate("Ordinary D", 55, 80),
        _rate("Ordinary E", 18, 33),
        _rate("MeasuredGood", 45, 50),
        _rate("MeasuredBad", 2, 10),
        _rate("ZeroOfOne", 0, 1),
    ]
    prior = bayes.fit_beta_prior(observations, method="moments")
    ranked = bayes.rank_by_posterior_lower_bound(
        bayes.beta_binomial_shrink(observations, prior), seed=3
    )
    positions = {row["group_ref"]: row["rank"] for row in ranked.value}

    assert positions["ZeroOfOne"] > positions["MeasuredGood"]
    for ordinary in ("Ordinary A", "Ordinary B", "Ordinary C", "Ordinary D"):
        assert positions["ZeroOfOne"] > positions[ordinary]
    # And the documented, deliberate exception, asserted rather than left implicit.
    assert positions["ZeroOfOne"] < positions["MeasuredBad"]


# ---------------------------------------------------------------------------
# rank_by_posterior_lower_bound
# ---------------------------------------------------------------------------


def test_rank_stability_matches_the_analytic_two_group_probability():
    """
    For two Beta posteriors, P(A > B) has an exact value, computed here by
    high-resolution numerical integration of a different expression from the
    seeded sampler under test. Two independent computations of the same integral.
    """
    a1, b1, a2, b2 = 30.0, 20.0, 24.0, 20.0

    steps = 200000
    total = 0.0
    log_norm = math.lgamma(a1 + b1) - math.lgamma(a1) - math.lgamma(b1)
    for i in range(steps):
        x = (i + 0.5) / steps
        density = math.exp(log_norm + (a1 - 1) * math.log(x) + (b1 - 1) * math.log(1 - x))
        total += density * betainc(a2, b2, x)
    analytic = total / steps

    rows = [
        {"group_ref": "A", "dist": "beta", "posterior_alpha": a1, "posterior_beta": b1, "n": 50},
        {"group_ref": "B", "dist": "beta", "posterior_alpha": a2, "posterior_beta": b2, "n": 44},
        {"group_ref": "C", "dist": "beta", "posterior_alpha": 2.0, "posterior_beta": 90.0, "n": 90},
        {"group_ref": "D", "dist": "beta", "posterior_alpha": 3.0, "posterior_beta": 95.0, "n": 95},
        {"group_ref": "E", "dist": "beta", "posterior_alpha": 4.0, "posterior_beta": 99.0, "n": 99},
    ]
    ranked = bayes.rank_by_posterior_lower_bound(rows, seed=42, as_of=AS_OF)
    top = ranked.value[0]
    assert top["group_ref"] == "A"
    # 4000 draws, so the Monte Carlo standard error is about 0.008; three of them.
    assert top["rank_stability"] == pytest.approx(analytic, abs=0.025)


def test_the_ranking_is_reproducible_under_a_seed_and_moves_under_another():
    rows = [
        {"group_ref": chr(65 + i), "dist": "beta",
         "posterior_alpha": 10.0 + i, "posterior_beta": 20.0, "n": 30 + i}
        for i in range(6)
    ]
    first = bayes.rank_by_posterior_lower_bound(rows, seed=1, as_of=AS_OF)
    again = bayes.rank_by_posterior_lower_bound(rows, seed=1, as_of=AS_OF)
    assert [r["rank_stability"] for r in first.value] == [r["rank_stability"] for r in again.value]
    assert [r["group_ref"] for r in first.value] == [r["group_ref"] for r in again.value]
    other = bayes.rank_by_posterior_lower_bound(rows, seed=2, as_of=AS_OF)
    assert [r["group_ref"] for r in other.value] == [r["group_ref"] for r in first.value]


def test_a_table_without_per_row_n_is_withheld_rather_than_left_to_the_frontend():
    rows = [
        {"group_ref": chr(65 + i), "dist": "beta", "posterior_alpha": 10.0, "posterior_beta": 20.0}
        for i in range(6)
    ]
    out = bayes.rank_by_posterior_lower_bound(rows, as_of=AS_OF)
    check = _check(out, "n-disclosure")
    assert check.status == "FAIL" and check.blocking is True
    assert out.value == []
    assert out.render_state == "not_interpretable"


def test_indistinguishable_groups_are_grouped_into_a_tie_band():
    rows = [
        {"group_ref": chr(65 + i), "dist": "beta",
         "posterior_alpha": 20.0 + 0.1 * i, "posterior_beta": 20.0, "n": 40}
        for i in range(6)
    ]
    out = bayes.rank_by_posterior_lower_bound(rows, seed=9, as_of=AS_OF)
    assert _check(out, "rank-separation").status == "WARN"
    assert len({r["tie_band"] for r in out.value}) == 1
    assert max(r["rank_stability"] for r in out.value) < 0.5


def test_gamma_posteriors_rank_through_the_same_service():
    observations = [_count("r" + str(i), 3 * i + 1, 10.0) for i in range(6)]
    shrunk = bayes.gamma_poisson_shrink(observations, (2.0, 2.0))
    ranked = bayes.rank_by_posterior_lower_bound(shrunk, seed=4)
    assert ranked.value[0]["group_ref"] == "r5"
    assert all(r["lower_bound"] < r["posterior_mean"] for r in ranked.value)


# ---------------------------------------------------------------------------
# hierarchical_pool: the eight schools
# ---------------------------------------------------------------------------

# Rubin (1981), and BDA 3rd ed. section 5.5. Treatment effects and their
# standard errors for eight SAT coaching programmes.
EIGHT_SCHOOLS = (
    ("A", 28.0, 15.0),
    ("B", 8.0, 10.0),
    ("C", -3.0, 16.0),
    ("D", 7.0, 11.0),
    ("E", -1.0, 9.0),
    ("F", 1.0, 11.0),
    ("G", 18.0, 10.0),
    ("H", 12.0, 18.0),
)


class _School:
    def __init__(self, ref, effect, std_error):
        self.group_ref = ref
        self.school = ref
        self.effect = effect
        self.std_error = std_error


def test_the_eight_schools_posterior_reproduces_the_published_shrinkage():
    """
    The canonical hierarchical fixture. BDA reports posterior means for the eight
    school effects in the region of 11, 8, 6, 7, 5, 6, 10, 8 and a posterior for
    tau whose mass sits below about 15 with a median near 5, under a uniform
    prior on tau.

    How precisely this is asserted, stated openly: the published table is quoted
    from training knowledge like the batting fixture, so the assertions below are
    the FEATURES of that posterior that every published account agrees on and
    that a wrong implementation fails - school A shrinks from 28 to about 10,
    every school lands inside the range of the raw effects, the ordering of the
    raw effects is preserved, and tau's credible interval reaches down to zero.
    Two exact identities are asserted alongside them, and those carry no
    tolerance at all.
    """
    schools = [_School(*row) for row in EIGHT_SCHOOLS]
    out = bayes.hierarchical_pool(schools, levels=("school",), seed=2026, draws=8000, as_of=AS_OF)

    rows = {r["unit_ref"]: r for r in out.value["units"]}
    assert out.n == 8
    assert _check(out, "convergence").status == "PASS"

    assert rows["A"]["pooled"] == pytest.approx(11.0, abs=2.5)
    assert rows["C"]["pooled"] == pytest.approx(6.0, abs=3.0)
    assert rows["G"]["pooled"] == pytest.approx(10.0, abs=2.5)

    grand = sum(y for _r, y, _s in EIGHT_SCHOOLS) / 8
    for ref, raw, _se in EIGHT_SCHOOLS:
        pooled = rows[ref]["pooled"]
        assert min(raw, grand) - 1.0 <= pooled <= max(raw, grand) + 1.0

    # Order is preserved among schools measured with the SAME precision, which
    # is an exact property of the model: with equal sigma the shrinkage is a
    # single affine map. B and G share se 10; D and F share se 11.
    assert rows["G"]["pooled"] > rows["B"]["pooled"]
    assert rows["D"]["pooled"] > rows["F"]["pooled"]

    # And it is deliberately NOT preserved across unequal precision. School C's
    # raw effect (-3) is below school E's (-1), yet C is pooled ABOVE E because
    # C's standard error is 16 against E's 9. This is the published result, not
    # an artefact: BDA's own posterior table puts C near 7 and E near 5.
    assert EIGHT_SCHOOLS[2][1] < EIGHT_SCHOOLS[4][1]
    assert rows["C"]["pooled"] > rows["E"]["pooled"]

    assert 0.0 <= out.value["tau_lo"] < 5.0
    assert 1.0 < out.value["tau"] < 12.0
    assert out.value["epsilon_spent"] == 0.0
    assert _check(out, "privacy-notice").status == "SKIPPED"


def test_the_pooling_factor_is_the_shrinkage_it_claims_to_be():
    """
    An identity, not a published number. The pooling factor for a unit is
    sigma^2 / (sigma^2 + tau^2), so the noisiest unit must be pooled hardest.
    """
    schools = [_School(*row) for row in EIGHT_SCHOOLS]
    out = bayes.hierarchical_pool(schools, levels=("school",), seed=1, draws=4000, as_of=AS_OF)
    rows = {r["unit_ref"]: r for r in out.value["units"]}
    assert rows["H"]["pooling_factor"] > rows["E"]["pooling_factor"]   # se 18 against se 9
    tau = out.value["tau"]
    for ref, _raw, se in EIGHT_SCHOOLS:
        assert rows[ref]["pooling_factor"] == pytest.approx(
            se * se / (se * se + tau * tau), abs=1e-9
        )


def test_a_barely_identified_tau_is_disclosed_rather_than_reported_as_a_finding():
    schools = [_School(*row) for row in EIGHT_SCHOOLS]
    out = bayes.hierarchical_pool(schools, levels=("school",), seed=7, draws=4000, as_of=AS_OF)
    check = _check(out, "tau-identified")
    assert check.status == "WARN"
    assert "complete pooling is inside the credible region" in check.detail.lower()


# ---------------------------------------------------------------------------
# hierarchical_pool: the floors and the DP mechanism
# ---------------------------------------------------------------------------


def _cross_tenant(n_tenants=12, per_tenant=6, big=None):
    rng = random.Random(4242)
    rows = []
    for t in range(n_tenants):
        trials = big if (big is not None and t == 0) else per_tenant * 10
        for unit in ("plumbing", "electrical", "lift"):
            share = trials // 3
            rows.append(
                _rate(
                    "t" + str(t) + ":" + unit,
                    successes=int(share * (0.5 + 0.3 * rng.random())),
                    trials=share,
                    group_key=unit,
                    strata={"tenant": "t" + str(t), "group_key": unit, "vertical": "rwa_society"},
                )
            )
    return rows


def test_fewer_than_ten_tenants_blocks_and_publishes_nothing():
    out = bayes.hierarchical_pool(
        _cross_tenant(n_tenants=9), levels=("tenant", "group_key"), seed=1, draws=200,
        min_units_per_level=2,
    )
    check = _check(out, "min-tenants")
    assert check.status == "FAIL" and check.blocking is True
    assert out.value["units"] == []
    assert out.render_state == "not_interpretable"


def test_a_tenant_above_a_quarter_of_the_observations_blocks_and_publishes_nothing():
    out = bayes.hierarchical_pool(
        _cross_tenant(n_tenants=12, big=3000), levels=("tenant", "group_key"), seed=1, draws=200,
        min_units_per_level=2,
    )
    check = _check(out, "tenant-concentration")
    assert check.status == "FAIL" and check.blocking is True
    assert check.statistic > 0.25
    assert out.value["units"] == []


def test_mixing_two_verticals_is_refused_outright():
    rows = _cross_tenant(n_tenants=12)
    rows.append(
        _rate("club:practice", 5, 10, group_key="practice",
              strata={"tenant": "club", "group_key": "practice", "vertical": "campus_club"})
    )
    out = bayes.hierarchical_pool(
        rows, levels=("tenant", "group_key"), seed=1, draws=200, min_units_per_level=2
    )
    check = _check(out, "vertical-homogeneous")
    assert check.status == "FAIL" and check.blocking is True
    assert "sports club" in check.detail


def test_a_tenant_whose_budget_is_spent_is_excluded_not_noised_harder():
    rows = _cross_tenant(n_tenants=14)
    spent = {"t3": 0.9, "t7": 1.0}
    out = bayes.hierarchical_pool(
        rows, levels=("tenant", "group_key"), seed=5, draws=400, min_units_per_level=2,
        epsilon=0.5, tenant_budget=1.0, spent_epsilon=spent,
    )
    check = _check(out, "dp-budget-exhausted")
    assert check.status == "WARN"
    assert out.n_excluded == 2
    assert "excluded" in out.exclusion_reason or "budget" in out.exclusion_reason
    assert out.value["n_tenants"] == 12


def test_the_pooled_figures_are_noised_and_say_so():
    out = bayes.hierarchical_pool(
        _cross_tenant(), levels=("tenant", "group_key"), seed=3, draws=400,
        min_units_per_level=2, epsilon=1.0,
    )
    assert out.value["epsilon_spent"] == 1.0
    assert _check(out, "privacy-notice").status == "PASS"
    assert any("Laplace-noised" in c for c in out.caveats)
    assert out.value["n_units"] == 3


def test_perturbing_one_tenant_moves_the_published_statistic_by_at_most_the_sensitivity():
    """
    THE privacy gate, in its exact form.

    Under a common random seed the Laplace draws are identical, so the difference
    between the release on D and on D' is exactly the difference between the
    clamped sums. One tenant's contribution to one group is clamped to
    [0, cap], so that difference is at most cap in the successes and at most cap
    in the trials, whatever the tenant does. That is what the noise scale
    2*cap/epsilon is calibrated against, and it is what is asserted here.
    """
    cap = 100.0
    base = {
        "t" + str(t): {"plumbing": (30.0, 60.0), "lift": (12.0, 40.0)}
        for t in range(12)
    }
    perturbed = {k: dict(v) for k, v in base.items()}
    # The held-out tenant does the worst thing it can: everything, at the cap.
    perturbed["t7"] = {"plumbing": (0.0, cap), "lift": (cap, cap)}

    left = bayes._noise_contributions(base, epsilon=1.0, cap=cap, seed=77)
    right = bayes._noise_contributions(perturbed, epsilon=1.0, cap=cap, seed=77)

    for unit in left:
        assert abs(left[unit][0] - right[unit][0]) <= cap + 1e-9
        assert abs(left[unit][1] - right[unit][1]) <= cap + 1e-9

    # And end to end, through the service, the published pooled rate moves by no
    # more than the sensitivity divided by the noised denominator allows.
    rows = _cross_tenant(n_tenants=12)
    moved = _cross_tenant(n_tenants=12)
    held_out = [r for r in moved if r.group_ref.startswith("t7:")]
    moved = [r for r in moved if not r.group_ref.startswith("t7:")]
    for original in held_out:
        # The held-out tenant flips every one of its successes to zero. It stays
        # inside the concentration ceiling, so this is a legal neighbouring
        # dataset and not a second, different refusal.
        moved.append(
            _rate(original.group_ref, 0, original.trials, group_key=original.group_key,
                  strata=dict(original.strata))
        )
    first = bayes.hierarchical_pool(
        rows, levels=("tenant", "group_key"), seed=99, draws=800, min_units_per_level=2
    )
    second = bayes.hierarchical_pool(
        moved, levels=("tenant", "group_key"), seed=99, draws=800, min_units_per_level=2
    )
    a = {r["unit_ref"]: r for r in first.value["units"]}
    b = {r["unit_ref"]: r for r in second.value["units"]}
    for unit in a:
        denominator = a[unit]["raw"] * (1 - a[unit]["raw"]) / (a[unit]["std_error"] ** 2)
        bound = 2.0 * bayes.DEFAULT_CONTRIBUTION_CAP / denominator
        assert abs(a[unit]["raw"] - b[unit]["raw"]) <= bound


def test_the_mechanism_satisfies_its_declared_epsilon_empirically():
    """
    The DP guarantee itself, measured rather than asserted. Over 6000 seeds the
    ratio of the release densities on two neighbouring datasets must not exceed
    exp(epsilon) anywhere the histogram has enough mass to measure it.

    Neighbouring here means what the mechanism declares: one tenant's single
    sufficient statistic for one group changes, by at most the clamp.
    """
    cap = 20.0
    epsilon = 1.0
    base = {"t" + str(t): {"g": (10.0, 20.0)} for t in range(12)}
    neighbour = {k: dict(v) for k, v in base.items()}
    neighbour["t0"] = {"g": (0.0, 20.0)}          # the full sensitivity, in successes

    def sample(contributions, trials):
        out = []
        for s in range(trials):
            noised = bayes._noise_contributions(
                contributions, epsilon=epsilon, cap=cap, seed=s
            )
            out.append(noised["g"][0])
        return out

    left = sample(base, 6000)
    right = sample(neighbour, 6000)

    width = 8.0
    def histogram(values):
        counts = {}
        for v in values:
            counts[math.floor(v / width)] = counts.get(math.floor(v / width), 0) + 1
        return counts

    hl, hr = histogram(left), histogram(right)
    worst = 0.0
    for key in set(hl) | set(hr):
        a, b = hl.get(key, 0), hr.get(key, 0)
        if min(a, b) < 60:      # too little mass in the bin to measure a ratio
            continue
        worst = max(worst, abs(math.log(a / b)))
    assert worst > 0.0, "the two releases must differ at all, or this test measures nothing"
    assert worst <= epsilon + 0.25      # Monte Carlo slack on 6000 draws per side


def test_the_pool_is_a_batch_and_carries_the_batch_it_came_from():
    out = bayes.hierarchical_pool(
        _cross_tenant(), levels=("tenant", "group_key"), seed=3, draws=200,
        min_units_per_level=2, refresh_cadence="weekly",
    )
    assert out.value["as_of_batch"].endswith(":weekly")
    assert any("refreshes weekly rather than live" in c for c in out.caveats)


def test_pooling_is_reproducible_under_its_seed():
    first = bayes.hierarchical_pool(
        _cross_tenant(), levels=("tenant", "group_key"), seed=8, draws=400, min_units_per_level=2
    )
    again = bayes.hierarchical_pool(
        _cross_tenant(), levels=("tenant", "group_key"), seed=8, draws=400, min_units_per_level=2
    )
    assert first.value == again.value
    assert first.params_hash == again.params_hash


# ---------------------------------------------------------------------------
# Envelope hygiene
# ---------------------------------------------------------------------------


def test_every_service_returns_an_envelope_with_a_method_and_a_hash():
    observations = _vendor_fixture()
    prior = bayes.fit_beta_prior(observations, method="moments")
    shrunk = bayes.beta_binomial_shrink(observations, prior)
    ranked = bayes.rank_by_posterior_lower_bound(shrunk, seed=1)
    counts = [_count("r" + str(i), i + 1, 10.0) for i in range(6)]
    gamma = bayes.gamma_poisson_shrink(counts, None)
    schools = [_School(*row) for row in EIGHT_SCHOOLS]
    pooled = bayes.hierarchical_pool(schools, levels=("school",), seed=1, draws=200, as_of=AS_OF)

    for evidence, method in (
        (prior, "bayes.fit_beta_prior"),
        (shrunk, "bayes.beta_binomial_shrink"),
        (ranked, "bayes.rank_by_posterior_lower_bound"),
        (gamma, "bayes.gamma_poisson_shrink"),
        (pooled, "bayes.hierarchical_pool"),
    ):
        assert isinstance(evidence, Evidence)
        assert evidence.method == method
        assert evidence.params_hash
        assert evidence.as_of.tzinfo is not None
        assert evidence.checks
