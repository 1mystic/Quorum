"""
Known-answer tests for the runway simulation.

The ground truth is analytic and genuinely external mathematics, not a reference
implementation:

- For a Gaussian random walk the probability of being below a floor AT the end
  of the horizon is exactly `Phi((-distance - h * drift) / (sigma * sqrt(h)))`.
  At h = 1 the running minimum and the terminal value coincide, so the simulator
  must reproduce that number within Monte Carlo error.
- Over a longer horizon the simulator monitors at period ends, so its answer
  must sit between the exact terminal probability (a lower bound: some paths dip
  and recover) and the continuously monitored first-passage probability from the
  reflection principle (an upper bound). Both ends are closed forms.

A catalog correction is recorded here. The entry claimed the simulator would be
checked directly against "the closed-form first-passage solution (the inverse
Gaussian)". That formula is for CONTINUOUSLY monitored Brownian motion. A ledger
is monitored at period ends, because that is when a treasurer looks, so the two
quantities are genuinely different and the continuous one is strictly larger.
Asserting equality would have forced either a wrong simulator or a padded
tolerance. The bracket is the honest statement and both of its ends are exact.
"""
import math
import random
from datetime import datetime, timezone

import pytest

from app.stats import montecarlo
from app.stats.contracts import Check, Evidence
from app.stats.streams import LedgerPeriod
from datetime import timedelta

AS_OF = datetime(2026, 6, 1, tzinfo=timezone.utc)
START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _forecast(values, sds, *, gate_passes=True, as_of=AS_OF):
    """
    A hand-built forecast Evidence, so the simulation can be driven by a process
    whose analytic answer is known.

    Built by hand rather than by running a forecaster because the point of these
    tests is the simulator, and driving it with a fitted model would make the
    known answer depend on the fit.
    """
    z80 = montecarlo.Z80
    checks = (Check(
        id="beats-seasonal-naive",
        label="This forecast beat the naive baseline",
        status="PASS" if gate_passes else "FAIL",
        statistic=0.5 if gate_passes else 1.4,
        detail="" if gate_passes else "lost to seasonal-naive, so the baseline is shown instead",
    ),)
    return Evidence(
        value={
            "x": ["+" + str(i + 1) for i in range(len(values))],
            "y": list(values),
            "lo": [v - z80 * s for v, s in zip(values, sds)],
            "hi": [v + z80 * s for v, s in zip(values, sds)],
        },
        n=48,
        method="forecast.dues_collection",
        as_of=as_of,
        checks=checks,
        params_hash="deadbeef",
    )


def _ledger(n=24, seed=1, correlation="none"):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        base = rng.gauss(0.0, 1.0)
        inflow = 100000 + int(8000 * base)
        if correlation == "negative":
            outflow = -(60000 - int(8000 * base))
        else:
            outflow = -(60000 + int(4000 * rng.gauss(0.0, 1.0)))
        ps = START + timedelta(days=30 * i)
        out.append(LedgerPeriod(
            period_start=ps, period_end=ps + timedelta(days=30),
            inflow_minor=inflow, outflow_minor=outflow, net_minor=inflow + outflow,
            closing_balance_minor=None, complete=True,
        ))
    return out


# ---------------------------------------------------------------------------
# The closed forms
# ---------------------------------------------------------------------------


def test_terminal_probability_is_the_exact_gaussian_closed_form():
    """No approximation in this one: it is a normal tail, written out."""
    from app.stats.numeric import norm_cdf
    drift, sigma, distance, horizon = -1.0, 10.0, 10.0, 4
    expected = norm_cdf((-distance - horizon * drift) / (sigma * math.sqrt(horizon)))
    assert montecarlo.terminal_shortfall_probability(drift, sigma, distance, horizon) == \
        pytest.approx(expected, abs=1e-15)


def test_first_passage_formula_matches_the_reflection_principle():
    """
    The reflection-principle formula for Brownian motion with drift, whose
    first-passage density is the inverse Gaussian. Checked against the algebra
    written out independently.
    """
    from app.stats.numeric import norm_cdf
    drift, sigma, distance, horizon = -1.0, 10.0, 40.0, 12.0
    b = -distance
    root = sigma * math.sqrt(horizon)
    expected = (norm_cdf((b - drift * horizon) / root)
                + math.exp(2.0 * drift * b / (sigma * sigma))
                * norm_cdf((b + drift * horizon) / root))
    assert montecarlo.first_passage_probability(drift, sigma, distance, horizon) == \
        pytest.approx(expected, abs=1e-12)


def test_continuous_monitoring_dominates_terminal_probability():
    """
    A path can dip below the floor and recover inside a month. Continuous
    monitoring catches that, period-end monitoring does not, so the continuous
    probability is always the larger of the two. This ordering is what makes the
    bracket a valid test rather than a fudge.
    """
    for horizon in (2, 4, 8, 12):
        terminal = montecarlo.terminal_shortfall_probability(-1.0, 10.0, 25.0, horizon)
        continuous = montecarlo.first_passage_probability(-1.0, 10.0, 25.0, float(horizon))
        assert continuous >= terminal


# ---------------------------------------------------------------------------
# The simulator against those closed forms
# ---------------------------------------------------------------------------


def test_simulator_reproduces_the_exact_closed_form_at_horizon_one():
    """
    **The strongest anchor available here.** At h = 1 the running minimum and
    the terminal value are the same random variable, so there is no monitoring
    gap and the simulator must match the closed form exactly, within Monte Carlo
    error at the declared number of draws.
    """
    drift, sigma, floor = -1.0, 10.0, -10.0
    draws = 40000
    result = montecarlo.simulate_balance_paths(
        0.0, [drift], [sigma], [0.0], [0.0], floor=floor, rho=0.0, draws=draws, seed=7,
    )
    exact = montecarlo.terminal_shortfall_probability(drift, sigma, 10.0, 1)
    standard_error = math.sqrt(exact * (1.0 - exact) / draws)
    assert result["p_shortfall"] == pytest.approx(exact, abs=3.0 * standard_error)


@pytest.mark.parametrize("horizon,floor", [(4, -25.0), (12, -40.0)])
def test_simulator_sits_inside_the_analytic_bracket(horizon, floor):
    """
    Period-end monitoring lies between the two closed forms, and strictly so.
    """
    drift, sigma = -1.0, 10.0
    result = montecarlo.simulate_balance_paths(
        0.0, [drift] * horizon, [sigma] * horizon, [0.0] * horizon, [0.0] * horizon,
        floor=floor, rho=0.0, draws=20000, seed=42,
    )
    distance = -floor
    terminal = montecarlo.terminal_shortfall_probability(drift, sigma, distance, horizon)
    continuous = montecarlo.first_passage_probability(drift, sigma, distance, float(horizon))
    assert terminal <= result["p_shortfall"] <= continuous


def test_the_simulation_is_exactly_reproducible_from_its_seed():
    a = montecarlo.simulate_balance_paths(
        0.0, [1.0] * 6, [2.0] * 6, [1.2] * 6, [1.0] * 6, floor=-5.0, rho=0.2, draws=2000, seed=11,
    )
    b = montecarlo.simulate_balance_paths(
        0.0, [1.0] * 6, [2.0] * 6, [1.2] * 6, [1.0] * 6, floor=-5.0, rho=0.2, draws=2000, seed=11,
    )
    assert a == b
    c = montecarlo.simulate_balance_paths(
        0.0, [1.0] * 6, [2.0] * 6, [1.2] * 6, [1.0] * 6, floor=-5.0, rho=0.2, draws=2000, seed=12,
    )
    assert c["p_shortfall"] != a["p_shortfall"]


def test_negative_correlation_raises_the_shortfall_probability():
    """
    The modelling point the Method Card makes: if collections fall in the same
    month that maintenance spend rises, independent sampling understates the
    shortfall badly.

    Measured as a monotone ordering across the correlation, which is a stronger
    statement than a single comparison.
    """
    probabilities = []
    for rho in (-0.8, -0.4, 0.0, 0.4, 0.8):
        result = montecarlo.simulate_balance_paths(
            0.0, [10.0] * 12, [8.0] * 12, [10.0] * 12, [8.0] * 12,
            floor=-25.0, rho=rho, draws=20000, seed=3,
        )
        probabilities.append(result["p_shortfall"])
    assert all(probabilities[i] > probabilities[i + 1] for i in range(len(probabilities) - 1))
    assert probabilities[0] > 2.0 * probabilities[-1]


# ---------------------------------------------------------------------------
# The service and its gates
# ---------------------------------------------------------------------------


def test_a_forecast_that_lost_to_naive_blocks_the_whole_simulation():
    """
    `forecast-gate-inherited`. A runway probability built on a forecast that
    loses to naive is precision theatre, so the failure is blocking and the
    value is emptied rather than flagged.
    """
    inflow = _forecast([100000.0] * 6, [8000.0] * 6, gate_passes=False)
    outflow = _forecast([60000.0] * 6, [4000.0] * 6)
    evidence = montecarlo.runway_shortfall(
        500000, inflow, outflow, _ledger(), horizon=6, seed=1,
    )
    check = next(c for c in evidence.checks if c.id == "forecast-gate-inherited")
    assert check.status == "FAIL"
    assert check.blocking is True
    assert evidence.value == {}
    assert evidence.render_state == "not_interpretable"


def test_a_healthy_fund_reports_a_low_shortfall_probability():
    inflow = _forecast([100000.0] * 6, [5000.0] * 6)
    outflow = _forecast([60000.0] * 6, [4000.0] * 6)
    evidence = montecarlo.runway_shortfall(
        500000, inflow, outflow, _ledger(), horizon=6, seed=1, floor_minor=0,
    )
    assert isinstance(evidence, Evidence)
    assert evidence.value["p_shortfall"] == 0.0
    assert evidence.unit == "probability"


def test_a_fund_bleeding_money_reports_a_high_shortfall_probability_and_a_date():
    inflow = _forecast([50000.0] * 12, [5000.0] * 12)
    outflow = _forecast([100000.0] * 12, [8000.0] * 12)
    evidence = montecarlo.runway_shortfall(
        200000, inflow, outflow, _ledger(), horizon=12, seed=1, floor_minor=0, draws=5000,
    )
    assert evidence.value["p_shortfall"] > 0.9
    assert evidence.value["first_shortfall_period_p50"] is not None
    assert evidence.interval is not None
    assert evidence.interval_kind == "predictive-95"
    assert evidence.interval[0] <= evidence.value["first_shortfall_period_p50"] <= evidence.interval[1]


def test_too_little_ledger_history_warns_that_the_answer_is_understated():
    inflow = _forecast([100000.0] * 6, [8000.0] * 6)
    outflow = _forecast([90000.0] * 6, [8000.0] * 6)
    evidence = montecarlo.runway_shortfall(
        100000, inflow, outflow, _ledger(n=6), horizon=6, seed=1,
    )
    check = next(c for c in evidence.checks if c.id == "correlation-estimable")
    assert check.status == "WARN"
    assert "UNDERSTATES" in check.detail
    assert evidence.value["correlation"] == 0.0


def test_the_correlation_is_estimated_from_the_ledger_when_there_is_enough_of_it():
    inflow = _forecast([100000.0] * 6, [8000.0] * 6)
    outflow = _forecast([60000.0] * 6, [8000.0] * 6)
    evidence = montecarlo.runway_shortfall(
        100000, inflow, outflow, _ledger(n=24, correlation="negative"), horizon=6, seed=1,
    )
    check = next(c for c in evidence.checks if c.id == "correlation-estimable")
    assert check.status == "PASS"
    # The fixture makes outflow fall when inflow rises, which is a negative
    # correlation between inflow and the magnitude of outflow.
    assert evidence.value["correlation"] < -0.5


def test_the_balance_path_quantiles_are_ordered():
    inflow = _forecast([100000.0] * 6, [8000.0] * 6)
    outflow = _forecast([95000.0] * 6, [8000.0] * 6)
    evidence = montecarlo.runway_shortfall(
        100000, inflow, outflow, _ledger(), horizon=6, seed=2, draws=4000,
    )
    for row in evidence.value["balance_paths_quantiles"]:
        assert row["p05"] <= row["p50"] <= row["p95"]


def test_a_forecast_shorter_than_the_horizon_is_refused_rather_than_extrapolated():
    inflow = _forecast([100000.0] * 3, [8000.0] * 3)
    outflow = _forecast([60000.0] * 3, [4000.0] * 3)
    with pytest.raises(ValueError):
        montecarlo.runway_shortfall(100000, inflow, outflow, _ledger(), horizon=6, seed=1)


def test_an_insufficient_forecast_produces_an_insufficient_simulation():
    from app.stats.contracts import insufficient as make_insufficient
    empty = make_insufficient("forecast.dues_collection", n=4, as_of=AS_OF, empty_value={})
    outflow = _forecast([60000.0] * 6, [4000.0] * 6)
    evidence = montecarlo.runway_shortfall(100000, empty, outflow, _ledger(), horizon=6, seed=1)
    assert evidence.insufficient_data is True


def test_the_service_returns_an_envelope_with_a_params_hash():
    inflow = _forecast([100000.0] * 6, [8000.0] * 6)
    outflow = _forecast([60000.0] * 6, [4000.0] * 6)
    evidence = montecarlo.runway_shortfall(
        100000, inflow, outflow, _ledger(), horizon=6, seed=1, draws=2000,
    )
    assert evidence.method == "montecarlo.runway_shortfall"
    assert evidence.params_hash
    seed_check = next(c for c in evidence.checks if c.id == "seed-recorded")
    assert seed_check.status == "PASS"
