"""
Known answers for the survival module.

Nothing here is a snapshot. Every assertion is against a published figure (R
`survival` on `lung`, the published Cox coefficients on `rossi`), an analytic
identity (an exponential survival curve, the Aalen-Johansen equality with
1 - Kaplan-Meier under a single cause), or a constructed fixture whose correct
answer was worked out by hand.

The most important test in this file, and arguably in the repository, is
`test_the_censoring_regression`: the fixture where the mean of the closed spells
and the Kaplan-Meier median disagree, asserting that we report the second.
"""
from __future__ import annotations

import math
import random

import pytest

from tests.unit.stats import datasets as ds
from app.stats import survival as sv


# ---------------------------------------------------------------------------
# The censoring regression. docs/RULES.md section 7.
# ---------------------------------------------------------------------------


def censoring_fixture():
    """
    100 requests, worked out by hand so the two figures disagree by a lot.

    51 are closed. Their durations are 17 at 1.0 days, one at 1.1, 10 at 2.0,
    8 at 3.0, 8 at 5.0 and 7 at 8.0, which sum to 158.1 and average to exactly
    3.1 days. The other 49 are still open and have been open for between 9 and
    33 days: the slow ones, exactly as in real life.

    Because nothing is censored before day 8, the Kaplan-Meier curve telescopes
    and S(8) = (100 - 51)/100 = 0.49, so the median is 8.0 days.

    Naive: 3.1 days. Correct: 8.0 days. The naive figure understates by 61%.
    """
    closed = [1.0] * 17 + [1.1] + [2.0] * 10 + [3.0] * 8 + [5.0] * 8 + [8.0] * 7
    open_ages = [9.0 + 0.5 * i for i in range(49)]
    spells = [ds.spell("closed-" + str(i), days=d, observed=True) for i, d in enumerate(closed)]
    spells += [ds.spell("open-" + str(i), days=d, observed=False) for i, d in enumerate(open_ages)]
    return spells


def test_the_censoring_regression():
    """
    The product's core correctness claim, made concrete.

    Every competing community dashboard averages the closed tickets and prints
    3.1 days. The honest figure is 8.0. This asserts we report the second, that
    the first is present only as the thing being contradicted, and that the
    still-open requests are counted rather than dropped.
    """
    spells = censoring_fixture()
    window = ds.window_of(60)

    gap = sv.naive_vs_km_gap(spells, window)
    assert gap.value["naive_mean_closed_days"] == pytest.approx(3.1, abs=1e-9)
    assert gap.value["km_median_days"] == pytest.approx(8.0, abs=1e-9)
    assert gap.value["gap_days"] == pytest.approx(4.9, abs=1e-9)
    assert gap.n == 100
    assert gap.n_censored == 49

    # The reported figure is the Kaplan-Meier one, everywhere it is reported.
    median = sv.median_resolution_days(spells, window)
    assert median.value == pytest.approx(8.0, abs=1e-9)
    assert median.value != pytest.approx(3.1, abs=0.5)
    assert median.n == 100 and median.n_censored == 49
    assert median.unit == "days"

    curve = sv.km_resolution_curve(spells, window)
    assert sv._curve_value_at(curve.value, "survival", 8.0) == pytest.approx(0.49, abs=1e-9)
    assert curve.n_censored == 49


def test_dropping_the_open_requests_is_what_produces_the_wrong_number():
    """
    The counterfactual that names the bug: filter the still-open requests out,
    which is what `WHERE resolved_at IS NOT NULL` does, and the median collapses
    from 8.0 days to 2.0. The bias is downward and it is large.
    """
    spells = censoring_fixture()
    window = ds.window_of(60)
    closed_only = [s for s in spells if s.event_observed]
    filtered = sv.median_resolution_days(closed_only, window)
    honest = sv.median_resolution_days(spells, window)
    assert filtered.value == pytest.approx(2.0, abs=1e-9)
    assert honest.value == pytest.approx(8.0, abs=1e-9)
    assert filtered.n_censored == 0
    assert honest.n_censored == 49


# ---------------------------------------------------------------------------
# Kaplan-Meier against R survival on lung
# ---------------------------------------------------------------------------


def test_median_matches_r_survfit_on_lung():
    """R: survfit(Surv(time, status) ~ 1, data = lung) prints median 310, 95% CI 285 to 363."""
    ev = sv.median_resolution_days(ds.lung_spells(), ds.window_of(1200))
    assert ev.value == pytest.approx(310.0, abs=1e-9)
    assert ev.interval == pytest.approx((285.0, 363.0), abs=1e-9)
    assert ev.n == 228
    assert ev.n_censored == 63          # lung has 165 deaths in 228 rows
    assert ev.interval_kind == "greenwood-95"


def test_survival_at_one_year_matches_published_summary_on_lung():
    """R: summary(survfit(...), times = 365) gives 0.409, 95% CI 0.345 to 0.486."""
    ev = sv.sla_attainment(ds.lung_spells(), ds.window_of(1200), horizon_days=365)
    assert 1.0 - ev.value == pytest.approx(0.409, abs=5e-4)
    lo, hi = ev.interval
    assert 1.0 - hi == pytest.approx(0.345, abs=1e-3)
    assert 1.0 - lo == pytest.approx(0.486, abs=1e-3)


def test_sla_attainment_refuses_to_extrapolate_past_the_data():
    ev = sv.sla_attainment(ds.lung_spells(), ds.window_of(2000), horizon_days=1500)
    assert ev.value is None
    assert ev.render_state == "not_interpretable"
    assert any(c.id == "horizon-in-support" and c.blocking for c in ev.checks)


def test_logrank_by_sex_matches_r_survdiff_on_lung():
    """R: survdiff(Surv(time, status) ~ sex, data = lung) gives chi-square 10.3 on 1 df, p = 0.001."""
    ev = sv.logrank_compare(ds.lung_spells(), ds.window_of(1200), group_by="category")
    assert ev.value["chi_square"] == pytest.approx(10.3, abs=0.05)
    assert ev.value["df"] == 1
    assert ev.value["p_value"] == pytest.approx(0.00131, abs=1e-4)
    by_key = {g["key"]: g for g in ev.value["groups"]}
    # Published group medians from survfit(~ sex): female 426, male 270.
    assert by_key["female"]["median"] == pytest.approx(426.0)
    assert by_key["male"]["median"] == pytest.approx(270.0)
    assert by_key["female"]["n"] == 90 and by_key["male"]["n"] == 138
    assert ev.interval is None and ev.interval_kind == "none"


# ---------------------------------------------------------------------------
# Delayed entry and analytic ground truth
# ---------------------------------------------------------------------------


def test_delayed_entry_risk_set_matches_a_hand_count_on_heart():
    """
    The Stanford heart data is the canonical (start, stop, event) example. The
    risk set at a time is counted straight off the CSV, independently of the
    estimator, and the estimator must agree.
    """
    triples = ds.heart_rows()
    rows = [sv._Row(entry=a, exit=b, event=e, outcome=None, censoring="none",
                    left_truncated=a > 0, ref="", keys={}) for a, b, e in triples]
    for t in (10.0, 50.0, 100.0, 500.0):
        expected = sum(1 for a, b, _ in triples if a < t <= b)
        assert sv._at_risk(rows, t) == expected


def test_kaplan_meier_recovers_an_exponential_curve_under_staggered_entry():
    """
    Exponential survival is a closed form, so this is an external truth rather
    than a comparison with another implementation. Spells enter the risk set at
    a random age (rule C3) and are censored at a random time; the delayed-entry
    estimator must still recover exp(-rate * t).
    """
    rng = random.Random(11)
    rate = 0.05
    spells = []
    for i in range(800):
        lifetime = rng.expovariate(rate)
        censor_at = rng.uniform(0.0, 60.0)
        entry = rng.uniform(0.0, 10.0)
        if lifetime <= entry:
            continue                      # never observed: truncated away, not censored
        observed = lifetime <= censor_at
        spells.append(ds.spell(
            "exp-" + str(i),
            days=max(0.0, min(lifetime, censor_at) - entry),
            observed=observed,
            entry_days=entry,
        ))
    rows, _, _ = sv._request_rows(spells)
    curve = sv._km_fit(rows)
    for t in (5.0, 10.0, 20.0, 30.0):
        assert sv._curve_value_at(curve, "survival", t) == pytest.approx(
            math.exp(-rate * t), abs=0.03
        )


# ---------------------------------------------------------------------------
# Cox on rossi
# ---------------------------------------------------------------------------


def rossi_design():
    rows, _, _ = sv._request_rows(ds.rossi_spells())
    return sv._build_design(rows, list(ds.ROSSI_COVARIATES)), rows


def test_cox_coefficients_match_the_published_rossi_fit():
    """
    The standard fixture. Published coefficients: fin -0.379, age -0.057,
    race 0.314, wexp -0.150, mar -0.434, paro -0.085, prio 0.091. Tolerance
    1e-3 on the coefficient, per docs/STATS_CATALOG.md.
    """
    design, _ = rossi_design()
    beta, loglik, _, hess = sv._cox_fit(design)
    fitted = dict(zip(design.names, beta))
    for name, published in ds.ROSSI_PUBLISHED.items():
        assert fitted[name] == pytest.approx(published, abs=1e-3)
    # Published partial log-likelihood at convergence: -658.748.
    assert loglik == pytest.approx(-658.748, abs=1e-2)


def test_cox_standard_errors_match_the_published_rossi_fit():
    """Published standard errors: fin 0.1914, age 0.0220, prio 0.0287."""
    from app.stats.numeric import inverse

    design, _ = rossi_design()
    beta, _, _, hess = sv._cox_fit(design)
    info = [[-hess[a][b] for b in range(len(beta))] for a in range(len(beta))]
    cov = inverse(info)
    se = dict(zip(design.names, [math.sqrt(cov[a][a]) for a in range(len(beta))]))
    assert se["fin"] == pytest.approx(0.1914, abs=1e-2)
    assert se["age"] == pytest.approx(0.0220, abs=1e-2)
    assert se["prio"] == pytest.approx(0.0287, abs=1e-2)


def test_schoenfeld_check_fails_for_age_and_passes_for_fin_on_rossi():
    """
    A ground truth about the *check*, not only about the model: R's
    cox.zph(coxph(Surv(week, arrest) ~ ., rossi)) reports age violating
    proportional hazards at the 5% level and fin comfortably not, with a global
    p of about 0.014.
    """
    ev = sv.cox_hazard_ratios(ds.rossi_spells(), ds.window_of(600),
                              covariates=ds.ROSSI_COVARIATES)
    per_covariate = {
        c.label: c for c in ev.checks if c.id == "proportional-hazards"
    }
    age = per_covariate["The effect of age is constant over time"]
    fin = per_covariate["The effect of fin is constant over time"]
    assert age.status == "FAIL" and age.blocking
    assert age.p_value < 0.05
    assert fin.status == "PASS"
    assert fin.p_value > 0.5
    global_check = next(c for c in ev.checks if c.id == "proportional-hazards-global")
    assert global_check.p_value == pytest.approx(0.014, abs=0.01)
    assert global_check.status == "FAIL"


def test_a_hazard_ratio_that_fails_proportionality_is_suppressed_not_printed():
    """
    The single most important failure path in Pack 1. A hazard ratio whose
    Schoenfeld test fails is not interpretable as a constant multiplier, so the
    row carries no number at all and says why.
    """
    ev = sv.cox_hazard_ratios(ds.rossi_spells(), ds.window_of(600),
                              covariates=ds.ROSSI_COVARIATES)
    rows = {r["covariate"]: r for r in ev.value}
    assert rows["age"]["suppressed"] is True
    assert rows["age"]["hazard_ratio"] is None
    assert rows["age"]["coef"] is None
    assert "changes over time" in rows["age"]["suppression_reason"]
    assert "stratified" in rows["age"]["suppression_reason"]
    # A covariate that passes still reports its ratio and a profile interval.
    assert rows["prio"]["suppressed"] is False
    assert rows["prio"]["hazard_ratio"] == pytest.approx(math.exp(0.0915), abs=1e-3)
    assert rows["prio"]["lo"] < rows["prio"]["hazard_ratio"] < rows["prio"]["hi"]
    assert ev.interval_kind == "profile-95"
    assert ev.render_state == "not_interpretable"


def test_cox_profile_interval_brackets_the_wald_interval_on_rossi():
    """
    A profile-likelihood interval is not symmetric and is not the Wald interval,
    but on a well-behaved coefficient the two agree closely. Published Wald
    interval for prio: exp(0.0915 +/- 1.96 * 0.0287) = 1.035 to 1.157.
    """
    ev = sv.cox_hazard_ratios(ds.rossi_spells(), ds.window_of(600),
                              covariates=ds.ROSSI_COVARIATES)
    prio = next(r for r in ev.value if r["covariate"] == "prio")
    assert prio["lo"] == pytest.approx(1.035, abs=0.01)
    assert prio["hi"] == pytest.approx(1.157, abs=0.01)


def test_cox_blocks_below_five_events_per_covariate():
    spells = ds.rossi_spells()[:120]
    ev = sv.cox_hazard_ratios(spells, ds.window_of(600), covariates=ds.ROSSI_COVARIATES)
    assert ev.insufficient_data or ev.render_state == "not_interpretable"
    assert ev.value in ([], None)


# ---------------------------------------------------------------------------
# Competing risks
# ---------------------------------------------------------------------------


def test_single_cause_cumulative_incidence_equals_one_minus_kaplan_meier():
    """
    A theorem, and therefore a stronger ground truth than any dataset: with one
    cause the Aalen-Johansen estimator must reduce to 1 - KM exactly.
    """
    spells = [ds.spell("x" + str(i), days=1.0 + i % 20, observed=(i % 3 != 0)) for i in range(120)]
    window = ds.window_of(60)
    cif = sv.competing_risks_cif(spells, window, causes=("resolved",))
    rows, _, _ = sv._request_rows(spells)
    km = sv._km_fit(rows)
    for estimated, survival in zip(cif.value["resolved"]["cif"], km["survival"]):
        assert estimated == pytest.approx(1.0 - survival, abs=1e-12)


def test_cumulative_incidences_and_the_open_share_sum_to_one():
    spells = []
    for i in range(150):
        outcome = ("resolved", "escalated", "withdrawn")[i % 3] if i % 4 else None
        spells.append(ds.spell(
            "y" + str(i), days=1.0 + (i % 25), observed=outcome is not None, outcome=outcome,
        ))
    ev = sv.competing_risks_cif(spells, ds.window_of(60))
    for i, _ in enumerate(ev.value["still_open"]["t_days"]):
        total = ev.value["still_open"]["probability"][i] + sum(
            ev.value[c]["cif"][i] for c in ("resolved", "escalated", "withdrawn")
        )
        assert total == pytest.approx(1.0, abs=1e-12)
    assert next(c for c in ev.checks if c.id == "cif-sums-to-one").status == "PASS"


def test_one_minus_kaplan_meier_overstates_incidence_when_a_cause_competes():
    """
    The mistake the Aalen-Johansen estimator exists to fix: 1 - KM for one cause
    is the probability in a world where the competing cause cannot happen, and
    it always exceeds the true incidence.
    """
    spells = []
    for i in range(180):
        outcome = "resolved" if i % 2 else "withdrawn"
        spells.append(ds.spell("z" + str(i), days=1.0 + (i % 30), observed=True, outcome=outcome))
    window = ds.window_of(60)
    cif = sv.competing_risks_cif(spells, window, causes=("resolved", "withdrawn"))
    rows, _, _ = sv._request_rows(spells, event_causes=("resolved",))
    km = sv._km_fit(rows)
    t = 15.0
    naive = 1.0 - sv._curve_value_at(km, "survival", t)
    honest = max(v for tt, v in zip(cif.value["resolved"]["t_days"], cif.value["resolved"]["cif"])
                 if tt <= t)
    assert naive > honest


# ---------------------------------------------------------------------------
# Floors, blocking checks and the shape of the envelope
# ---------------------------------------------------------------------------


def test_below_the_events_floor_returns_a_calm_empty_state_and_never_raises():
    spells = [ds.spell("s" + str(i), days=float(i + 1), observed=i < 10) for i in range(40)]
    ev = sv.km_resolution_curve(spells, ds.window_of(60))
    assert ev.insufficient_data is True
    assert ev.render_state == "not_enough_data"
    assert ev.value == {"t_days": [], "survival": [], "lo": [], "hi": [], "at_risk": [],
                        "events": [], "censored": []}
    assert ev.n == 40 and ev.n_censored == 30
    assert "needs 30 observed events, has 10" in ev.caveats[0]


def test_a_material_share_of_competing_exits_blocks_the_curve():
    """Spine rule C5: above 15% the curve must not be read as 'percent resolved by day t'."""
    spells = []
    for i in range(150):
        outcome = "withdrawn" if i % 4 == 0 else "resolved"
        spells.append(ds.spell("c" + str(i), days=1.0 + (i % 20), observed=True, outcome=outcome))
    ev = sv.km_resolution_curve(spells, ds.window_of(60))
    check = next(c for c in ev.checks if c.id == "competing-risks-material")
    assert check.status == "FAIL" and check.blocking
    assert ev.render_state == "not_interpretable"
    assert ev.value["t_days"] == []
    assert "competing_risks_cif" in check.detail


def test_bracketed_terminal_timestamps_block_the_curve_above_the_share():
    """Spine rule C4: no honest curve without a Turnbull estimator, so none is shown."""
    spells = []
    for i in range(120):
        if i % 3 == 0:
            spells.append(ds.spell(
                "b" + str(i), days=5.0, observed=False, censoring="interval",
                interval_lo_hours=48.0, interval_hi_hours=240.0,
            ))
        else:
            spells.append(ds.spell("b" + str(i), days=1.0 + (i % 20), observed=True))
    ev = sv.km_resolution_curve(spells, ds.window_of(60))
    check = next(c for c in ev.checks if c.id == "interval-censoring-share")
    assert check.status == "FAIL" and check.blocking
    assert ev.render_state == "not_interpretable"


def test_informative_censoring_is_detected_and_only_warns():
    """
    An admin bulk-closing stale tickets makes censoring informative. The curve
    is still shown, because there is no better estimator available, but the
    caveat names the covariate and the direction of the bias (rule C9).
    """
    spells = []
    for i in range(120):
        observed = i % 2 == 0
        spells.append(ds.spell(
            "i" + str(i), days=1.0 + (i % 20), observed=observed,
            covariates={"age_of_reporter": 20.0 + (0 if observed else 30.0) + i % 5},
        ))
    ev = sv.km_resolution_curve(spells, ds.window_of(60))
    check = next(c for c in ev.checks if c.id == "censoring-informative")
    assert check.status == "WARN"
    assert not check.blocking
    assert "age_of_reporter" in check.detail
    assert ev.render_state == "qualified"


def test_merged_duplicates_are_excluded_with_a_stated_reason():
    """Spine rule C7: a request merged into another is the same request counted twice."""
    spells = [ds.spell("m" + str(i), days=2.0 + i % 10, observed=True) for i in range(40)]
    spells.append(ds.spell("dupe", days=3.0, observed=True, outcome="merged"))
    ev = sv.km_resolution_curve(spells, ds.window_of(60))
    assert ev.n_excluded == 1
    assert ev.exclusion_reason == "merged_duplicate"
    assert ev.n == 40


def test_first_response_curve_is_numerically_identical_to_the_resolution_curve():
    """
    Same machinery, different promise. Relabelling the fields must not change a
    single number, which is a real regression risk if someone forks the
    estimator (docs/STATS_CATALOG.md).
    """
    window = ds.window_of(200)
    resolution = [ds.spell("r" + str(i), days=1.0 + (i % 30), observed=i % 4 != 0)
                  for i in range(140)]
    response = [
        ds.spell(
            "f" + str(i),
            days=1.0 + (i % 30),
            observed=False,
            first_response_hours=(1.0 + (i % 30)) * 24.0 if i % 4 != 0 else None,
        )
        for i in range(140)
    ]
    a = sv.km_resolution_curve(resolution, window)
    b = sv.first_response_curve(response, window)
    assert a.value["t_days"] == b.value["t_days"]
    assert a.value["survival"] == pytest.approx(b.value["survival"])
    assert a.value["lo"] == pytest.approx(b.value["lo"])
    assert b.unit == "probability unanswered"


def test_churn_curve_recovers_an_exponential_membership_lifetime():
    """
    The analytic check the catalog asks for: lifetimes drawn from an
    Exponential(rate) with independent uniform censoring must give a curve
    within Monte Carlo tolerance of exp(-rate * t), seeded.
    """
    from datetime import timedelta

    from app.stats.streams.member import MemberSpell

    rng = random.Random(4)
    rate = 0.02
    spells = []
    for i in range(900):
        lifetime = rng.expovariate(rate)
        censor_at = rng.uniform(0.0, 150.0)
        observed = lifetime <= censor_at
        entered = ds.EPOCH
        spells.append(MemberSpell(
            member_ref="m" + str(i),
            entered_at=entered,
            at_risk_from=entered,
            left_truncated=False,
            exited_at=entered + timedelta(days=lifetime) if observed else None,
            exit_kind="lapse" if observed else None,
            event_observed=observed,
            duration_days=min(lifetime, censor_at),
        ))
    ev = sv.churn_curve(spells, ds.window_of(200))
    for t in (10.0, 30.0, 60.0):
        assert sv._curve_value_at(ev.value, "survival", t) == pytest.approx(
            math.exp(-rate * t), abs=0.04
        )


def test_every_service_returns_an_evidence_with_a_method_and_a_params_hash():
    window = ds.window_of(1200)
    spells = ds.lung_spells(with_sex=True)
    envelopes = [
        sv.km_resolution_curve(spells, window),
        sv.median_resolution_days(spells, window),
        sv.sla_attainment(spells, window, horizon_days=365),
        sv.first_response_curve(spells, window),
        sv.logrank_compare(spells, window, group_by="category"),
        sv.competing_risks_cif(spells, window, causes=("resolved",)),
        sv.naive_vs_km_gap(spells, window),
    ]
    for ev in envelopes:
        assert ev.method.startswith("survival.")
        assert len(ev.params_hash) == 8
        assert ev.as_of == window.end
        assert ev.n == 228
        assert not isinstance(ev.value, float) or ev.unit


def test_params_hash_changes_with_a_tuning_parameter_and_not_with_the_data():
    window = ds.window_of(60)
    a = sv.median_resolution_days(censoring_fixture(), window)
    b = sv.median_resolution_days(censoring_fixture()[:80], window)
    c = sv.median_resolution_days(censoring_fixture(), window, quantile=0.75)
    assert a.params_hash == b.params_hash
    assert a.params_hash != c.params_hash
