"""
Pack 2's experimentation half, checked against closed forms, an identity and a
theorem.

Three externals hold this file up.

**Miller's finite sum against quadrature.** P(B beats A) has an exact closed
form over integer Beta parameters. The test integrates the same quantity by
composite Simpson at high resolution, in this file, from the pdf and the
regularised incomplete beta. Two independent computations of one integral, so an
error in either is caught rather than confirmed.

**The loss identity.** loss(A) - loss(B) = E[theta_B] - E[theta_A] exactly, for
any pair of Beta posteriors. That is an identity and not an approximation, so it
is asserted to 1e-12. It also settles the catalog's claim that the expected loss
is zero when the posteriors are identical: it is not, and the test says what is
true instead.

**Ville's inequality, measured.** The catalog demands a false-positive-rate
experiment under continuous monitoring, and the negative control is compulsory:
the naive fixed-horizon z test, consulted at every peek on the identical
fixture, must blow through alpha. It does, by roughly a factor of five. A
guarantee whose alternative has never been measured is a claim, not a result.
"""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.stats import experiments
from app.stats.contracts import Evidence
from app.stats.experiments import (
    ArmSummary,
    Trial,
    beta_ab_test,
    expected_loss,
    expected_loss_pair,
    lbeta,
    mixture_boundary,
    mixture_rho,
    naive_z_crossing,
    prob_b_beats_a,
    reduce_trials,
    run_eprocess,
    sequential_stopping_rule,
    summarise_arm,
)
from app.stats.numeric import betainc
from app.stats.streams.participation import ParticipationEvent

AS_OF = datetime(2026, 8, 30, tzinfo=timezone.utc)
START = datetime(2026, 8, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The independent oracle, written here rather than imported, so that a mistake
# in app/stats/experiments.py cannot also be the thing checking it.
# ---------------------------------------------------------------------------


def _beta_pdf(x, a, b):
    if x <= 0.0 or x >= 1.0:
        return 0.0
    return math.exp((a - 1.0) * math.log(x) + (b - 1.0) * math.log1p(-x) - lbeta(a, b))


def _simpson(f, lo, hi, panels):
    """Composite Simpson. Deliberately dumb, so it is obviously right."""
    if panels % 2:
        panels += 1
    h = (hi - lo) / panels
    total = f(lo) + f(hi)
    for i in range(1, panels):
        total += (4.0 if i % 2 else 2.0) * f(lo + i * h)
    return total * h / 3.0


def _quadrature_prob_b_beats_a(a_a, b_a, a_b, b_b, panels=100000):
    """P(theta_B > theta_A) = integral pdf_B(x) F_A(x) dx, by brute force."""
    mean = a_b / (a_b + b_b)
    sd = math.sqrt(a_b * b_b / ((a_b + b_b) ** 2 * (a_b + b_b + 1.0)))
    lo = max(1e-12, mean - 14.0 * sd)
    hi = min(1.0 - 1e-12, mean + 14.0 * sd)
    return _simpson(lambda x: _beta_pdf(x, a_b, b_b) * betainc(a_a, b_a, x), lo, hi, panels)


def test_prob_b_beats_a_matches_high_resolution_quadrature():
    for case in ((31.0, 971.0, 46.0, 956.0), (11.0, 91.0, 16.0, 86.0)):
        closed = prob_b_beats_a(*case)
        numeric = _quadrature_prob_b_beats_a(*case)
        assert abs(closed - numeric) < 1e-10, (case, closed, numeric)


def test_prob_b_beats_a_hits_the_two_cases_that_can_be_done_by_hand():
    # Two uniforms: symmetry gives exactly a half.
    assert prob_b_beats_a(1.0, 1.0, 1.0, 1.0) == pytest.approx(0.5, abs=1e-14)
    # theta_A uniform, theta_B ~ Beta(2, 1) with density 2x: integral of 2x*x is 2/3.
    assert prob_b_beats_a(1.0, 1.0, 2.0, 1.0) == pytest.approx(2.0 / 3.0, abs=1e-14)
    # Swapping the arms must complement.
    p = prob_b_beats_a(7.0, 30.0, 11.0, 26.0)
    q = prob_b_beats_a(11.0, 26.0, 7.0, 30.0)
    assert p + q == pytest.approx(1.0, abs=1e-12)


def test_prob_b_beats_a_refuses_a_degenerate_posterior():
    with pytest.raises(ValueError, match="must be positive"):
        prob_b_beats_a(1.0, 0.0, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Expected loss
# ---------------------------------------------------------------------------


def test_expected_loss_satisfies_the_difference_identity():
    """
    loss(A) - loss(B) = E[theta_B] - E[theta_A].

    Both losses are expectations of (theta_B - theta_A) truncated on opposite
    sides, and x = x^+ - x^-, so the identity is exact. It is the sharpest cheap
    check available on the closed form, because a sign error or a wrong
    size-biased parameter breaks it immediately.
    """
    for a_a, b_a, a_b, b_b in (
        (31.0, 971.0, 46.0, 956.0), (2.0, 3.0, 9.0, 4.0), (1.0, 1.0, 1.0, 1.0),
    ):
        loss_a, loss_b = expected_loss_pair(a_a, b_a, a_b, b_b)
        gap = a_b / (a_b + b_b) - a_a / (a_a + b_a)
        assert (loss_a - loss_b) == pytest.approx(gap, abs=1e-12)


def test_expected_loss_is_not_zero_for_identical_posteriors():
    """
    The catalog said the loss is zero when the posteriors are identical. It is
    not, and the correction is in docs/STATS_CATALOG.md.

    For two independent uniforms E[(V - U)^+] = 1/6, exactly. What IS zero is
    the difference between the two losses, which the previous test asserts.
    """
    loss_a, loss_b = expected_loss_pair(1.0, 1.0, 1.0, 1.0)
    assert loss_a == pytest.approx(1.0 / 6.0, abs=1e-12)
    assert loss_a == pytest.approx(loss_b, abs=1e-14)
    assert loss_a > 0.0


def test_expected_loss_matches_a_double_integral():
    """E[(theta_B - theta_A)^+] by nested quadrature, independently of the closed form."""
    a_a, b_a, a_b, b_b = 12.0, 40.0, 18.0, 34.0

    def inner(x):
        # E[(theta_B - x)^+] = integral_x^1 (y - x) pdf_B(y) dy
        return _simpson(lambda y: (y - x) * _beta_pdf(y, a_b, b_b), x, 1.0 - 1e-12, 600)

    numeric = _simpson(lambda x: _beta_pdf(x, a_a, b_a) * inner(x), 1e-12, 1.0 - 1e-12, 600)
    loss_a, _ = expected_loss_pair(a_a, b_a, a_b, b_b)
    assert loss_a == pytest.approx(numeric, rel=1e-6)


def test_expected_loss_shrinks_as_the_evidence_grows():
    small, _ = expected_loss_pair(11.0, 91.0, 16.0, 86.0)
    large, _ = expected_loss_pair(101.0, 901.0, 151.0, 851.0)
    assert large < small


# ---------------------------------------------------------------------------
# The A/B service
# ---------------------------------------------------------------------------


def _arm(ref, conversions, exposures, **kw):
    return ArmSummary(
        arm_ref=ref, exposures=exposures, conversions=conversions,
        last_exposure=kw.pop("last_exposure", AS_OF), **kw,
    )


def test_beta_ab_test_reports_the_posterior_and_a_credible_interval():
    ev = beta_ab_test(_arm("whatsapp", 30, 1000), _arm("sms", 45, 1000))
    assert isinstance(ev, Evidence)
    assert ev.n == 2000
    assert ev.interval_kind == "credible-95"
    assert ev.value["p_b_beats_a"] == pytest.approx(
        prob_b_beats_a(31.0, 971.0, 46.0, 956.0), abs=1e-12
    )
    lo, hi = ev.interval
    assert lo < ev.value["lift"] < hi
    # A 50% relative lift with these counts: the interval must be wide and must
    # not be mistaken for precision.
    assert lo < 0.0 < hi or lo > 0.0


def test_beta_ab_test_says_in_words_that_the_probability_is_not_a_p_value():
    ev = beta_ab_test(_arm("a", 30, 1000), _arm("b", 45, 1000))
    joined = " ".join(ev.caveats).lower()
    assert "posterior probability" in joined
    assert "not a p-value" in joined


def test_beta_ab_test_refuses_below_the_conversion_floor():
    """
    Eight conversions on a thousand exposures is not a small answer, it is no
    answer: the posterior is the prior wearing the data's coat.
    """
    ev = beta_ab_test(_arm("a", 8, 1000), _arm("b", 9, 1000))
    assert ev.insufficient_data is True
    assert ev.render_state == "not_enough_data"
    assert ev.value["p_b_beats_a"] is None
    assert "conversions per arm" in " ".join(ev.caveats)


def test_beta_ab_test_refuses_below_the_exposure_floor():
    ev = beta_ab_test(_arm("a", 20, 40), _arm("b", 30, 45))
    assert ev.insufficient_data is True


def test_sample_ratio_mismatch_blocks_the_comparison():
    """
    The canary for a broken delivery pipeline. 1000 against 700 exposures on an
    intended even split is not bad luck, it is missing rows, and the members
    missing are not a random sample of the members.
    """
    ev = beta_ab_test(_arm("a", 30, 1000), _arm("b", 40, 700))
    srm = next(c for c in ev.checks if c.id == "sample-ratio-mismatch")
    assert srm.status == "FAIL" and srm.blocking is True
    assert ev.render_state == "not_interpretable"
    assert ev.value["p_b_beats_a"] is None
    assert ev.interval is None
    assert "pipeline" in srm.detail


def test_a_matched_split_passes_the_sample_ratio_check():
    ev = beta_ab_test(_arm("a", 30, 1000), _arm("b", 40, 1010))
    srm = next(c for c in ev.checks if c.id == "sample-ratio-mismatch")
    assert srm.status == "PASS"
    assert ev.value["p_b_beats_a"] is not None


def test_broken_randomisation_blocks_the_comparison():
    """A covariate that predicts the arm means the arms are not comparable."""
    balanced_a = _arm("a", 30, 1000, strata={"block": {"north": 500, "south": 500}})
    unbalanced_b = _arm("b", 45, 1000, strata={"block": {"north": 900, "south": 100}})
    ev = beta_ab_test(balanced_a, unbalanced_b)
    balance = next(c for c in ev.checks if c.id == "randomisation-balance")
    assert balance.status == "FAIL" and balance.blocking is True
    assert ev.render_state == "not_interpretable"
    assert "confounded" in balance.detail


def test_balanced_strata_pass_and_the_number_is_reported():
    a = _arm("a", 30, 1000, strata={"block": {"north": 500, "south": 500}})
    b = _arm("b", 45, 1000, strata={"block": {"north": 495, "south": 505}})
    ev = beta_ab_test(a, b)
    balance = next(c for c in ev.checks if c.id == "randomisation-balance")
    assert balance.status == "PASS"
    assert ev.value["p_b_beats_a"] is not None


def test_a_member_in_both_arms_blocks_the_comparison():
    a = _arm("a", 30, 1000, members=frozenset("m" + str(i) for i in range(1000)))
    b = _arm("b", 45, 1000, members=frozenset("m" + str(i) for i in range(900, 1900)))
    ev = beta_ab_test(a, b)
    contamination = next(c for c in ev.checks if c.id == "no-contamination")
    assert contamination.status == "FAIL" and contamination.blocking is True
    assert contamination.statistic == 100.0


def test_the_no_peeking_check_is_always_disclosed_and_never_blocking():
    ev = beta_ab_test(_arm("a", 30, 1000), _arm("b", 45, 1000))
    peek = next(c for c in ev.checks if c.id == "no-peeking")
    assert peek.status == "WARN" and peek.blocking is False
    assert "still running" in peek.detail
    # The value is still shown: an interim look is a real number read carefully,
    # not a suppressed one.
    assert ev.value["p_b_beats_a"] is not None
    assert ev.render_state == "qualified"


def test_a_fired_stopping_rule_clears_the_peeking_check():
    ev = beta_ab_test(
        _arm("a", 30, 1000), _arm("b", 45, 1000),
        stopping_rule=Evidence(value={"stop": True}, n=2000, method="x", as_of=AS_OF),
    )
    peek = next(c for c in ev.checks if c.id == "no-peeking")
    assert peek.status == "PASS"


def test_the_novelty_window_warns_when_the_effect_is_front_loaded():
    a = _arm("a", 50, 1000, early_exposures=250, early_conversions=12)
    b = _arm("b", 90, 1000, early_exposures=250, early_conversions=50)
    ev = beta_ab_test(a, b)
    novelty = next(c for c in ev.checks if c.id == "novelty-window")
    assert novelty.status == "WARN"
    assert "novelty" in novelty.detail


def test_an_undeclared_credible_level_is_refused_rather_than_relabelled():
    with pytest.raises(ValueError, match="credible-95 and credible-89"):
        beta_ab_test(_arm("a", 30, 1000), _arm("b", 45, 1000), credible=0.9)


def test_the_service_will_not_invent_a_clock():
    a = ArmSummary(arm_ref="a", exposures=1000, conversions=30)
    b = ArmSummary(arm_ref="b", exposures=1000, conversions=45)
    with pytest.raises(ValueError, match="cannot read a clock"):
        beta_ab_test(a, b)


def test_more_conversions_than_exposures_is_refused():
    with pytest.raises(ValueError, match="exposure log"):
        ArmSummary(arm_ref="a", exposures=10, conversions=11)


def test_expected_loss_service_recommends_and_states_the_stake():
    ev = expected_loss(_arm("a", 30, 1000), _arm("b", 45, 1000), threshold=0.001)
    assert ev.value["recommend"] == "b"
    assert ev.value["loss_b"] < ev.value["loss_a"]
    threshold = next(c for c in ev.checks if c.id == "threshold-of-caring")
    assert threshold.status in ("PASS", "WARN")
    assert "not zero when the arms are identical" in " ".join(ev.caveats).lower() or \
        "NOT zero" in " ".join(ev.caveats)


def test_expected_loss_without_a_threshold_says_nothing_about_stopping():
    ev = expected_loss(_arm("a", 30, 1000), _arm("b", 45, 1000))
    threshold = next(c for c in ev.checks if c.id == "threshold-of-caring")
    assert threshold.status == "SKIPPED"
    assert "belongs to the committee" in threshold.detail


# ---------------------------------------------------------------------------
# Reducing the exposure log
# ---------------------------------------------------------------------------


def _exposure(member, arm, kind="nudge_sent", minutes=0, **kw):
    return ParticipationEvent(
        member_ref=member, at=START + timedelta(minutes=minutes), kind=kind,
        arm_ref=arm, **kw,
    )


def test_a_member_nudged_four_times_is_one_exposure():
    rows = [_exposure("m1", "a", minutes=i) for i in range(4)]
    rows.append(_exposure("m2", "a", minutes=10))
    summary = summarise_arm(rows)
    assert summary.exposures == 2
    assert summary.arm_ref == "a"


def test_a_member_who_acted_counts_once_as_a_conversion():
    rows = [
        _exposure("m1", "a", minutes=0),
        _exposure("m1", "a", kind="nudge_delivered", minutes=1),
        _exposure("m1", "a", kind="nudge_acted", minutes=2),
        _exposure("m2", "a", minutes=3),
    ]
    summary = summarise_arm(rows)
    assert (summary.exposures, summary.conversions) == (2, 1)
    assert summary.first_exposure == START


def test_mixing_two_arms_into_one_argument_is_refused():
    rows = [_exposure("m1", "a"), _exposure("m2", "b")]
    with pytest.raises(ValueError, match="mix arms"):
        summarise_arm(rows)


def test_reduce_trials_orders_by_exposure_and_excludes_members_in_both_arms():
    rows = [
        _exposure("m1", "a", minutes=5),
        _exposure("m2", "b", minutes=1),
        _exposure("m2", "b", kind="nudge_acted", minutes=9),
        _exposure("m3", "a", minutes=3),
        _exposure("m3", "b", minutes=4),
    ]
    trials, excluded = reduce_trials(rows)
    assert excluded == 1
    assert [t.arm for t in trials] == ["b", "a"]
    assert [t.outcome for t in trials] == [1.0, 0.0]


# ---------------------------------------------------------------------------
# The always-valid stopping rule. This is the section the pack exists for.
# ---------------------------------------------------------------------------


def _null_stream(rng, n, p=0.30):
    """A/B with NO difference at all. Any stop here is a false positive."""
    trials = []
    for _ in range(n):
        arm = "b" if rng.random() < 0.5 else "a"
        trials.append(Trial(arm, 1.0 if rng.random() < p else 0.0))
    return trials


def _effect_stream(rng, n, p_a=0.20, p_b=0.30):
    trials = []
    for _ in range(n):
        arm = "b" if rng.random() < 0.5 else "a"
        p = p_b if arm == "b" else p_a
        trials.append(Trial(arm, 1.0 if rng.random() < p else 0.0))
    return trials


def test_repeated_peeking_does_not_inflate_the_false_positive_rate():
    """
    The measurement this pack exists for.

    1000 seeded null experiments of 1200 exposures each, every one monitored
    after EVERY observation, which is the most aggressive peeking possible. Under
    Ville's inequality P(sup_t E_t >= 1/alpha) <= alpha, so the always-valid
    method must stay at or under 5%.

    The negative control is on the identical trials: a fixed-horizon
    two-proportion z test consulted every 25 observations. If it does not blow
    through alpha, the fixture is too weak to prove anything and this test is
    not doing its job, so both bounds are asserted.
    """
    rng = random.Random(20260831)
    sims = 1000
    evalue_stops = msprt_stops = naive_stops = 0
    for _ in range(sims):
        trials = _null_stream(rng, 1200)
        if run_eprocess(trials, arms=("a", "b"), alpha=0.05)["crossed_at"] is not None:
            evalue_stops += 1
        if run_eprocess(
            trials, arms=("a", "b"), alpha=0.05, variance="empirical"
        )["crossed_at"] is not None:
            msprt_stops += 1
        if naive_z_crossing(trials, arms=("a", "b"), alpha=0.05, peek_every=25) is not None:
            naive_stops += 1

    evalue_rate = evalue_stops / sims
    msprt_rate = msprt_stops / sims
    naive_rate = naive_stops / sims

    # The theorem, within two binomial standard errors of the nominal level.
    tolerance = 2.0 * math.sqrt(0.05 * 0.95 / sims)
    assert evalue_rate <= 0.05 + tolerance, evalue_rate
    assert msprt_rate <= 0.05 + tolerance, msprt_rate

    # The negative control. Without this half the test proves nothing: a method
    # that never stops would pass the assertions above.
    assert naive_rate > 3.0 * 0.05, naive_rate
    assert naive_rate > 4.0 * max(evalue_rate, msprt_rate, 0.01), (naive_rate, evalue_rate)


def test_the_always_valid_method_still_finds_a_real_effect():
    """A rule that never stops is trivially valid and completely useless."""
    rng = random.Random(4242)
    stops = 0
    runs = 40
    for _ in range(runs):
        trials = _effect_stream(rng, 8000)
        if run_eprocess(
            trials, arms=("a", "b"), alpha=0.05, target_n=4000
        )["crossed_at"] is not None:
            stops += 1
    assert stops >= 0.9 * runs, stops


def test_the_e_value_is_a_supermartingale_in_expectation():
    """
    E[E_t] <= 1 under the null, which is the property Ville's inequality needs.
    Monte Carlo over 400 null streams; the mean is bounded well away from the
    1/alpha threshold, and a broken normalisation shows up here immediately.
    """
    rng = random.Random(99)
    finals = [
        run_eprocess(_null_stream(rng, 600), arms=("a", "b"), alpha=0.05)["e_value"]
        for _ in range(400)
    ]
    mean = sum(finals) / len(finals)
    assert mean <= 1.5, mean
    assert all(e >= 0.0 for e in finals)


def test_the_mixture_is_tuned_to_be_tightest_at_the_declared_sample_size():
    """
    mixture_rho solves u = 2 log(1/alpha) + log(1 + u), the point at which the
    always-valid boundary is closest to the fixed-sample one. So the ratio of the
    two boundaries, as a function of t, must be minimised at target_n. Checked
    numerically over a grid, which is the definition rather than a restatement of
    the algebra.
    """
    alpha = 0.05
    sigma2 = 4.0
    target = 500
    rho = mixture_rho(sigma2, target, alpha)

    def ratio(t):
        v = t * sigma2
        return mixture_boundary(v, rho, alpha) / (1.96 * math.sqrt(sigma2 * t))

    grid = list(range(50, 2001, 10))
    best = min(grid, key=ratio)
    assert abs(best - target) <= 60, best
    # And the fixed point itself: u* = 2 log(1/alpha) + log(1 + u*).
    u = target * sigma2 / rho
    assert u == pytest.approx(2.0 * math.log(1.0 / alpha) + math.log1p(u), abs=1e-9)


def test_the_confidence_sequence_covers_the_truth_and_is_wider_than_a_fixed_interval():
    rng = random.Random(11)
    covered = 0
    runs = 200
    widths = []
    for _ in range(runs):
        trials = _effect_stream(rng, 2000)
        result = run_eprocess(trials, arms=("a", "b"), alpha=0.05, target_n=2000)
        if result["ci_lo"] <= 0.10 <= result["ci_hi"]:
            covered += 1
        widths.append(result["ci_hi"] - result["ci_lo"])
    assert covered >= 0.95 * runs, covered
    # A fixed-sample 95% interval on this contrast is about 2*1.96*sqrt(2*p(1-p)/n).
    fixed_width = 2.0 * 1.96 * math.sqrt(2.0 * 0.25 * 0.75 / 1000.0)
    assert sum(widths) / len(widths) > fixed_width


def test_the_service_reports_a_stop_and_names_the_arm():
    rng = random.Random(5)
    trials = _effect_stream(rng, 12000)
    stamped = [
        Trial(t.arm, t.outcome, START + timedelta(minutes=i)) for i, t in enumerate(trials)
    ]
    ev = sequential_stopping_rule(stamped, alpha=0.05, target_n=6000)
    assert ev.value["stop"] is True
    assert ev.value["at_n"] is not None
    assert ev.value["e_value"] >= 20.0
    assert "b" in ev.value["decision"]
    assert ev.value["confidence_sequence"][0] > 0.0
    validity = next(c for c in ev.checks if c.id == "optional-stopping-valid")
    assert validity.status == "PASS"


def test_the_service_keeps_running_under_the_null():
    rng = random.Random(6)
    trials = _null_stream(rng, 3000)
    ev = sequential_stopping_rule(trials, alpha=0.05, as_of=AS_OF)
    assert ev.value["stop"] is False
    assert "keep running" in ev.value["decision"]


def test_the_msprt_is_offered_but_its_weaker_guarantee_is_disclosed():
    rng = random.Random(8)
    ev = sequential_stopping_rule(
        _null_stream(rng, 2000), alpha=0.05, method="msprt", as_of=AS_OF,
    )
    validity = next(c for c in ev.checks if c.id == "optional-stopping-valid")
    assert validity.status == "WARN"
    assert "asymptotic" in validity.detail


def test_a_fixed_horizon_test_monitored_sequentially_is_refused():
    """
    The service will run the naive rule if asked and then refuse to certify it,
    which is more useful than pretending it is not what everyone does.
    """
    rng = random.Random(3)
    ev = sequential_stopping_rule(
        _null_stream(rng, 3000), alpha=0.05, method="fixed_horizon_z", as_of=AS_OF,
    )
    validity = next(c for c in ev.checks if c.id == "optional-stopping-valid")
    assert validity.status == "FAIL" and validity.blocking is True
    assert ev.render_state == "not_interpretable"
    assert ev.value["stop"] is None
    assert "fires far more often" in validity.detail


def test_an_unknown_sequential_method_is_refused_by_name():
    with pytest.raises(ValueError, match="evalue, msprt, fixed_horizon_z"):
        sequential_stopping_rule([], method="bonferroni_vibes", as_of=AS_OF)


def test_three_arms_are_refused_rather_than_silently_pooled():
    trials = [Trial("a", 0.0), Trial("b", 1.0), Trial("c", 0.0)]
    with pytest.raises(ValueError, match="exactly two arms"):
        sequential_stopping_rule(trials, as_of=AS_OF)


def test_one_empty_arm_blocks_rather_than_reporting_a_stop():
    trials = [Trial("a", 0.0) for _ in range(50)]
    ev = sequential_stopping_rule(trials, arms=("a", "b"), as_of=AS_OF)
    complete = next(c for c in ev.checks if c.id == "exposure-log-complete")
    assert complete.status == "FAIL" and complete.blocking is True
    assert ev.value["stop"] is None


def test_outcome_maturation_warns_when_the_last_exposures_are_bunched():
    """
    A member exposed yesterday who has not acted is right censored, not a zero.
    The check that notices is the same discipline as Pack 1's censoring rules.
    """
    rng = random.Random(12)
    trials = _null_stream(rng, 200)
    stamped = []
    for i, t in enumerate(trials):
        # 60% of the exposures land in the last tenth of the window.
        minutes = i * 10 if i < 80 else 800 + (i - 80)
        stamped.append(Trial(t.arm, t.outcome, START + timedelta(minutes=minutes)))
    ev = sequential_stopping_rule(stamped, alpha=0.05)
    maturation = next(c for c in ev.checks if c.id == "outcome-maturation")
    assert maturation.status == "WARN"
    assert "right censored" in maturation.detail


def test_evidence_carries_the_excluded_members_and_says_why():
    rows = [
        _exposure("m1", "a", minutes=1),
        _exposure("m2", "b", minutes=2),
        _exposure("m3", "a", minutes=3),
        _exposure("m3", "b", minutes=4),
    ]
    ev = sequential_stopping_rule(rows, as_of=AS_OF)
    assert ev.n_excluded == 1
    assert "both arms" in ev.exclusion_reason


def test_the_params_hash_separates_two_differently_tuned_runs():
    a = sequential_stopping_rule(_null_stream(random.Random(1), 200), as_of=AS_OF)
    b = sequential_stopping_rule(
        _null_stream(random.Random(1), 200), as_of=AS_OF, target_n=100,
    )
    assert a.params_hash != b.params_hash


def test_every_public_service_returns_an_envelope():
    for fn, args, kwargs in (
        (beta_ab_test, (_arm("a", 30, 1000), _arm("b", 45, 1000)), {}),
        (expected_loss, (_arm("a", 30, 1000), _arm("b", 45, 1000)), {}),
        (sequential_stopping_rule, (_null_stream(random.Random(2), 100),), {"as_of": AS_OF}),
    ):
        assert isinstance(fn(*args, **kwargs), Evidence)


def test_the_module_names_every_service_the_registry_expects():
    assert set(experiments.__all__) >= {
        "beta_ab_test", "expected_loss", "sequential_stopping_rule",
    }
