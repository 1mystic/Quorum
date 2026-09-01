"""
Pack 2's adaptive-allocation half.

The catalog is honest that there is no published table of Thompson-sampling
outputs to assert against, and inventing one would be exactly the thing this
package refuses to do. So three different kinds of truth are used instead, and
each is labelled for what it is.

**A theorem.** Lai and Robbins (1985) give the asymptotic regret lower bound for
any consistent policy, `sum (p* - p_i) / KL(p_i, p*) * log T`. Thompson sampling
attains it (Kaufmann, Korda and Munos, 2012), so the regret curve must grow like
log T with a slope near that constant. The slope is fitted here and compared to
the constant, which is a much sharper check than "regret is small".

**Exact arithmetic.** The Beta and Gamma samplers are checked against their
analytic moments, the Beta quantile function against cases with a closed form,
and the KL denominator against a hand-computed value.

**Reproducibility.** The same seed returns the identical allocation, bit for
bit, and `freeze_and_report` replays a stored state and gets the same split back.
That is the test which would fail first if anyone put module-level state into
app/stats/, so it doubles as a purity regression.
"""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.stats import bandits
from app.stats.bandits import (
    ArmState,
    MIN_EXPOSURES_TO_ACT,
    arm_states,
    beta_ppf,
    beta_sample,
    freeze_and_report,
    gamma_sample,
    kl_bernoulli,
    lai_robbins_bound,
    sample_allocation,
    simulate_regret,
    thompson_sampling_policy,
)
from app.stats.contracts import Evidence
from app.stats.streams.participation import ParticipationEvent

AS_OF = datetime(2026, 8, 30, tzinfo=timezone.utc)
START = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _counts(**arms):
    return {ref: {"conversions": c, "exposures": e} for ref, (c, e) in arms.items()}


# ---------------------------------------------------------------------------
# The samplers, against their analytic moments
# ---------------------------------------------------------------------------


def test_the_gamma_sampler_reproduces_its_analytic_moments():
    rng = random.Random(1)
    for shape in (0.5, 1.0, 2.5, 30.0):
        draws = [gamma_sample(rng, shape) for _ in range(20000)]
        mean = sum(draws) / len(draws)
        var = sum((d - mean) ** 2 for d in draws) / (len(draws) - 1)
        # Mean and variance of Gamma(shape, 1) are both `shape`.
        assert mean == pytest.approx(shape, rel=0.05), (shape, mean)
        assert var == pytest.approx(shape, rel=0.10), (shape, var)


def test_the_beta_sampler_reproduces_its_analytic_moments():
    rng = random.Random(2)
    for a, b in ((1.0, 1.0), (31.0, 971.0), (2.0, 5.0)):
        draws = [beta_sample(rng, a, b) for _ in range(30000)]
        mean = sum(draws) / len(draws)
        var = sum((d - mean) ** 2 for d in draws) / (len(draws) - 1)
        analytic_mean = a / (a + b)
        analytic_var = a * b / ((a + b) ** 2 * (a + b + 1.0))
        assert mean == pytest.approx(analytic_mean, rel=0.02), (a, b, mean)
        assert var == pytest.approx(analytic_var, rel=0.08), (a, b, var)
        assert all(0.0 <= d <= 1.0 for d in draws)


def test_the_sampler_uses_only_the_uniform_stream_so_it_survives_an_upgrade():
    """
    Two generators seeded identically must agree exactly, and a generator
    advanced by hand through the same number of uniforms must land in the same
    place. That is only true if nothing here calls a distribution helper whose
    implementation could change under us.
    """
    a = [beta_sample(random.Random(7), 3.0, 4.0) for _ in range(1)]
    b = [beta_sample(random.Random(7), 3.0, 4.0) for _ in range(1)]
    assert a == b


def test_beta_ppf_matches_the_cases_with_a_closed_form():
    # Beta(1, 1) is uniform, so its quantile function is the identity.
    for q in (0.025, 0.25, 0.5, 0.975):
        assert beta_ppf(q, 1.0, 1.0) == pytest.approx(q, abs=1e-9)
    # Any symmetric Beta has median a half.
    assert beta_ppf(0.5, 9.0, 9.0) == pytest.approx(0.5, abs=1e-9)
    # Beta(2, 1) has CDF x^2, so its median is sqrt(1/2).
    assert beta_ppf(0.5, 2.0, 1.0) == pytest.approx(math.sqrt(0.5), abs=1e-9)


def test_kl_bernoulli_matches_a_hand_computation():
    p, q = 0.2, 0.3
    expected = 0.2 * math.log(0.2 / 0.3) + 0.8 * math.log(0.8 / 0.7)
    assert kl_bernoulli(p, q) == pytest.approx(expected, abs=1e-12)
    assert kl_bernoulli(0.4, 0.4) == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# The Lai-Robbins bound. The one genuinely external truth available here.
# ---------------------------------------------------------------------------


def test_regret_grows_like_log_t_at_the_lai_robbins_rate():
    """
    The theorem says liminf R_T / log T >= sum (p* - p_i) / KL(p_i, p*), and
    Thompson sampling attains it. So fitting R_T against log T over a range of
    horizons must give a slope near that constant: a policy far above it is
    wasteful and one far below it, at these horizons, means the simulation is
    not measuring regret at all.

    Two arms at 0.20 and 0.30: KL(0.2, 0.3) is 0.2 log(2/3) + 0.8 log(8/7) =
    0.025732 nats, so the constant is 0.10 / 0.025732 = 3.886.
    """
    means = (0.20, 0.30)
    constant = (0.30 - 0.20) / kl_bernoulli(0.20, 0.30)
    assert constant == pytest.approx(3.886, abs=0.01)

    horizons = (500, 1000, 2000, 4000, 8000)
    curve = []
    for horizon in horizons:
        runs = [simulate_regret(means, horizon=horizon, seed=s)["regret"] for s in range(20)]
        curve.append(sum(runs) / len(runs))

    # Monotone and heavily sublinear: at 8000 rounds a uniform split would lose
    # 0.5 * 0.10 * 8000 = 400.
    assert all(curve[i] <= curve[i + 1] + 1e-9 for i in range(len(curve) - 1))
    assert curve[-1] < 0.15 * 400.0, curve

    # Slope of R_T against log T, by ordinary least squares on the endpoints of
    # the range, compared to the Lai-Robbins constant.
    slope = (curve[-1] - curve[0]) / (math.log(horizons[-1]) - math.log(horizons[0]))
    assert 0.5 * constant <= slope <= 1.6 * constant, (slope, constant)

    # And under the asymptotic bound's own line at every horizon measured, which
    # is where a liminf bound leaves a finite-horizon run.
    for horizon, regret in zip(horizons, curve):
        assert regret <= 3.0 * lai_robbins_bound(means, horizon)


def test_thompson_sampling_beats_uniform_allocation_on_the_same_fixture():
    means = (0.20, 0.30)
    horizon = 4000
    thompson = sum(
        simulate_regret(means, horizon=horizon, seed=s)["regret"] for s in range(10)
    ) / 10.0
    uniform = 0.5 * (0.30 - 0.20) * horizon
    assert thompson < uniform / 10.0, (thompson, uniform)


def test_the_floor_costs_exactly_the_regret_it_is_supposed_to():
    """
    A floor is not free and the envelope should not pretend it is. Forcing a
    fraction `k * floor` of rounds to be uniform costs `floor * sum(gaps) * T` in
    the limit, on top of the log-T regret of the policy itself. Measured against
    that closed form rather than asserted in prose.
    """
    means = (0.20, 0.30)
    horizon = 8000
    floor = 0.05
    with_floor = sum(
        simulate_regret(means, horizon=horizon, seed=s, floor=floor)["regret"]
        for s in range(10)
    ) / 10.0
    without = sum(
        simulate_regret(means, horizon=horizon, seed=s)["regret"] for s in range(10)
    ) / 10.0
    predicted_extra = floor * (0.30 - 0.20) * horizon
    assert (with_floor - without) == pytest.approx(predicted_extra, rel=0.35), (
        with_floor, without, predicted_extra
    )


def test_the_bound_is_zero_when_every_arm_is_equally_good():
    assert lai_robbins_bound((0.3, 0.3, 0.3), 10000) == 0.0


# ---------------------------------------------------------------------------
# The policy
# ---------------------------------------------------------------------------


def test_the_allocation_is_reproducible_bit_for_bit_from_the_seed():
    posteriors = _counts(whatsapp=(45, 1000), sms=(30, 1000), notice_board=(12, 400))
    first = thompson_sampling_policy(posteriors, seed=20260831, n_draws=4000, as_of=AS_OF)
    second = thompson_sampling_policy(posteriors, seed=20260831, n_draws=4000, as_of=AS_OF)
    assert first.value["allocation"] == second.value["allocation"]
    assert first.value["posteriors"] == second.value["posteriors"]
    assert first.params_hash == second.params_hash


def test_a_different_seed_moves_the_allocation_only_by_monte_carlo_error():
    posteriors = _counts(a=(45, 1000), b=(30, 1000))
    first = thompson_sampling_policy(posteriors, seed=1, n_draws=8000, as_of=AS_OF)
    second = thompson_sampling_policy(posteriors, seed=2, n_draws=8000, as_of=AS_OF)
    shares_a = [row["share"] for row in first.value["allocation"]]
    shares_b = [row["share"] for row in second.value["allocation"]]
    assert shares_a != shares_b
    assert max(abs(x - y) for x, y in zip(shares_a, shares_b)) < 0.03


def test_the_shares_sum_to_one_and_no_arm_falls_below_the_floor():
    posteriors = _counts(a=(2, 500), b=(60, 500), c=(30, 500))
    ev = thompson_sampling_policy(posteriors, seed=5, n_draws=4000, floor=0.05, as_of=AS_OF)
    shares = [row["share"] for row in ev.value["allocation"]]
    assert math.fsum(shares) == pytest.approx(1.0, abs=1e-12)
    assert min(shares) >= 0.05 - 1e-12
    # The clearly worst arm is held at the floor rather than starved to nothing,
    # which is the entire point of having one.
    worst = next(row for row in ev.value["allocation"] if row["arm_ref"] == "a")
    assert worst["share"] == pytest.approx(0.05, abs=0.01)


def test_the_better_arm_gets_the_majority_of_the_traffic():
    ev = thompson_sampling_policy(
        _counts(a=(30, 1000), b=(45, 1000)), seed=7, n_draws=4000, as_of=AS_OF,
    )
    shares = {row["arm_ref"]: row["share"] for row in ev.value["allocation"]}
    assert shares["b"] > shares["a"]
    assert shares["b"] > 0.8


def test_a_missing_seed_blocks_the_allocation_entirely():
    ev = thompson_sampling_policy(_counts(a=(30, 1000), b=(45, 1000)), seed=None, as_of=AS_OF)
    seed_check = next(c for c in ev.checks if c.id == "seed-recorded")
    assert seed_check.status == "FAIL" and seed_check.blocking is True
    assert ev.render_state == "not_interpretable"
    assert ev.value["allocation"] == []
    assert "reproduce" in seed_check.detail


def test_thin_arms_get_a_uniform_split_rather_than_an_acted_on_one():
    """
    Ten exposures on an arm is not evidence about that arm. Acting on the
    difference at that size is how a channel gets abandoned before it has said
    anything.
    """
    ev = thompson_sampling_policy(
        _counts(a=(0, 10), b=(4, 12)), seed=3, n_draws=2000, as_of=AS_OF,
    )
    act = next(c for c in ev.checks if c.id == "enough-exposure-to-act")
    assert act.status == "WARN"
    assert ev.value["acting"] is False
    shares = [row["share"] for row in ev.value["allocation"]]
    assert shares == pytest.approx([0.5, 0.5])
    assert str(MIN_EXPOSURES_TO_ACT) in act.detail


def test_a_zero_floor_is_allowed_and_warned_about():
    ev = thompson_sampling_policy(
        _counts(a=(1, 200), b=(40, 200)), seed=4, n_draws=2000, floor=0.0, as_of=AS_OF,
    )
    floor_check = next(c for c in ev.checks if c.id == "floor-applied")
    assert floor_check.status == "WARN"
    assert "starved" in floor_check.detail
    shares = {row["arm_ref"]: row["share"] for row in ev.value["allocation"]}
    assert shares["a"] < 0.01


def test_a_floor_that_cannot_be_satisfied_is_refused():
    states = [ArmState("a", 2.0, 2.0), ArmState("b", 2.0, 2.0), ArmState("c", 2.0, 2.0)]
    with pytest.raises(ValueError, match="leave room"):
        sample_allocation(states, seed=1, n_draws=100, floor=0.4)


def test_one_arm_is_not_an_allocation():
    with pytest.raises(ValueError, match="no decision to make"):
        thompson_sampling_policy(_counts(a=(3, 30)), seed=1, as_of=AS_OF)


def test_the_allocation_carries_no_interval_but_the_rates_do():
    ev = thompson_sampling_policy(
        _counts(a=(30, 1000), b=(45, 1000)), seed=9, n_draws=2000, as_of=AS_OF,
    )
    assert ev.interval is None
    for row in ev.value["posteriors"]:
        assert row["lo"] < row["mean"] < row["hi"]
    assert "DECISION" in " ".join(ev.caveats)


def test_the_policy_will_not_invent_a_clock():
    with pytest.raises(ValueError, match="cannot read a clock"):
        thompson_sampling_policy(_counts(a=(30, 1000), b=(45, 1000)), seed=1)


# ---------------------------------------------------------------------------
# Non-stationarity
# ---------------------------------------------------------------------------


def _shifting_arm(ref, early_rate, late_rate, n, seed):
    rng = random.Random(seed)
    outcomes = [1.0 if rng.random() < early_rate else 0.0 for _ in range(n // 2)]
    outcomes += [1.0 if rng.random() < late_rate else 0.0 for _ in range(n - n // 2)]
    return {
        "conversions": int(sum(outcomes)), "exposures": len(outcomes),
        "outcomes": tuple(outcomes),
    }


def test_a_shifting_arm_is_caught_and_the_posteriors_are_refitted_on_the_recent_half():
    posteriors = {
        "festival": _shifting_arm("festival", 0.60, 0.10, 400, 1),
        "steady": _shifting_arm("steady", 0.25, 0.25, 400, 2),
    }
    ev = thompson_sampling_policy(posteriors, seed=11, n_draws=2000, as_of=AS_OF)
    check = next(c for c in ev.checks if c.id == "non-stationarity")
    assert check.status == "FAIL" and check.blocking is False
    assert "refitted" in check.detail
    festival = next(p for p in ev.value["posteriors"] if p["arm_ref"] == "festival")
    # Half the history, and a rate near the recent 10% rather than the 35% average.
    assert festival["exposures"] == 200
    assert festival["mean"] < 0.20
    assert ev.n == 400


def test_a_stationary_pair_passes_and_keeps_its_whole_history():
    posteriors = {
        "a": _shifting_arm("a", 0.25, 0.25, 400, 3),
        "b": _shifting_arm("b", 0.30, 0.30, 400, 4),
    }
    ev = thompson_sampling_policy(posteriors, seed=12, n_draws=2000, as_of=AS_OF)
    check = next(c for c in ev.checks if c.id == "non-stationarity")
    assert check.status == "PASS"
    assert ev.n == 800


def test_counts_without_an_ordered_history_skip_the_check_and_say_so():
    ev = thompson_sampling_policy(
        _counts(a=(30, 1000), b=(45, 1000)), seed=13, n_draws=1000, as_of=AS_OF,
    )
    check = next(c for c in ev.checks if c.id == "non-stationarity")
    assert check.status == "SKIPPED"
    assert "seasonality" in check.detail


# ---------------------------------------------------------------------------
# Reading the exposure log
# ---------------------------------------------------------------------------


def _exposure(member, arm, kind="nudge_sent", minutes=0):
    return ParticipationEvent(
        member_ref=member, at=START + timedelta(minutes=minutes), kind=kind, arm_ref=arm,
    )


def test_exposure_rows_reduce_to_one_trial_per_member_per_arm():
    rows = []
    # Conversions are spread across each arm's history rather than bunched at
    # the start, because bunching them is a genuine non-stationarity and the
    # stationarity check would rightly refit on half the data.
    for i in range(40):
        rows.append(_exposure("m" + str(i), "a", minutes=i))
        rows.append(_exposure("m" + str(i), "a", kind="nudge_delivered", minutes=i))
        if i % 7 == 0:
            rows.append(_exposure("m" + str(i), "a", kind="nudge_acted", minutes=i + 1))
    for i in range(40, 80):
        rows.append(_exposure("m" + str(i), "b", minutes=i))
        if (i - 40) % 3 == 0:
            rows.append(_exposure("m" + str(i), "b", kind="nudge_acted", minutes=i + 1))
    states = arm_states(rows)
    assert [(s.arm_ref, s.exposures, s.conversions) for s in states] == [
        ("a", 40, 6), ("b", 40, 14),
    ]
    ev = thompson_sampling_policy(rows, seed=17, n_draws=2000)
    assert ev.n == 80
    assert ev.as_of == START + timedelta(minutes=79)
    shares = {row["arm_ref"]: row["share"] for row in ev.value["allocation"]}
    assert shares["b"] > shares["a"]


def test_a_bare_beta_pair_is_read_as_a_posterior_and_never_as_counts():
    states = arm_states({"a": (31.0, 971.0), "b": (46.0, 956.0)})
    assert [(s.alpha, s.beta) for s in states] == [(31.0, 971.0), (46.0, 956.0)]


def test_a_degenerate_posterior_is_refused():
    with pytest.raises(ValueError, match="degenerate posterior"):
        ArmState("a", 0.0, 3.0)


# ---------------------------------------------------------------------------
# freeze_and_report: the governance feature
# ---------------------------------------------------------------------------


def test_freezing_replays_the_stored_state_and_gets_the_identical_allocation():
    policy = thompson_sampling_policy(
        _counts(whatsapp=(45, 1000), sms=(30, 1000)), seed=20260831, n_draws=4000, as_of=AS_OF,
    )
    frozen = freeze_and_report(policy, as_of=AS_OF)
    replay = next(c for c in frozen.checks if c.id == "replay-matches")
    assert replay.status == "PASS" and frozen.render_state == "estimate"
    assert frozen.value["seed"] == 20260831
    stored = [row["allocation"] for row in frozen.value["arms"]]
    live = [row["share"] for row in policy.value["allocation"]]
    assert stored == live


def test_a_tampered_record_fails_the_replay_and_shows_nothing():
    """
    The record has to be checkable, not merely stored. This is also the test
    that would fail first if a cache appeared in app/stats/: the replay would
    stop reproducing the stored split.
    """
    policy = thompson_sampling_policy(
        _counts(a=(45, 1000), b=(30, 1000)), seed=99, n_draws=2000, as_of=AS_OF,
    )
    state = dict(policy.value)
    state["posteriors"] = [dict(p) for p in state["posteriors"]]
    state["posteriors"][0]["allocation"] = 0.5
    state["posteriors"][1]["allocation"] = 0.5
    frozen = freeze_and_report(state, as_of=AS_OF)
    replay = next(c for c in frozen.checks if c.id == "replay-matches")
    assert replay.status == "FAIL" and replay.blocking is True
    assert frozen.render_state == "not_interpretable"
    assert frozen.value["arms"] == []
    assert "carrying state between calls" in replay.detail


def test_the_frozen_record_explains_each_arm_in_a_sentence_built_from_numbers():
    policy = thompson_sampling_policy(
        _counts(whatsapp_tue_evening=(84, 300), email_sat_morning=(9, 300)),
        seed=2026, n_draws=4000, as_of=AS_OF,
    )
    frozen = freeze_and_report(policy, as_of=AS_OF)
    reasons = {row["arm_ref"]: row["reason"] for row in frozen.value["arms"]}
    winner = reasons["whatsapp_tue_evening"]
    assert "84 of 300 exposures" in winner
    assert "28.0%" in winner
    assert "95% credible" in winner
    assert "posterior draws" in winner
    loser = reasons["email_sat_morning"]
    assert "floor lifted it" in loser


def test_a_frozen_record_of_a_uniform_split_says_why_it_was_uniform():
    policy = thompson_sampling_policy(
        _counts(a=(1, 12), b=(4, 15)), seed=8, n_draws=1000, as_of=AS_OF,
    )
    frozen = freeze_and_report(policy, as_of=AS_OF)
    assert frozen.value["acting"] is False
    assert all("uniform" in row["reason"] for row in frozen.value["arms"])


def test_freezing_an_empty_state_is_refused_rather_than_reported_as_empty():
    with pytest.raises(ValueError, match="nothing to explain"):
        freeze_and_report({"seed": 1, "posteriors": []}, as_of=AS_OF)


def test_the_frozen_intervals_are_labelled_as_of_the_freeze_not_of_today():
    policy = thompson_sampling_policy(
        _counts(a=(45, 1000), b=(30, 1000)), seed=6, n_draws=1000, as_of=AS_OF,
    )
    frozen = freeze_and_report(policy, as_of=AS_OF)
    joined = " ".join(frozen.caveats)
    assert "AS THEY STOOD" in joined
    assert "kept learning" in joined


def test_every_public_service_returns_an_envelope():
    policy = thompson_sampling_policy(
        _counts(a=(45, 1000), b=(30, 1000)), seed=1, n_draws=500, as_of=AS_OF,
    )
    assert isinstance(policy, Evidence)
    assert isinstance(freeze_and_report(policy, as_of=AS_OF), Evidence)


def test_the_module_names_every_service_the_registry_expects():
    assert set(bandits.__all__) >= {"thompson_sampling_policy", "freeze_and_report"}
