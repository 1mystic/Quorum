"""
Known answers for the control charts.

The ground truth is the published average-run-length tables, because that is
what a control chart's constants actually mean. Lucas and Saccucci (1990)
Table 3 for EWMA, and the standard CUSUM table reproduced in Montgomery for
k = 0.5, h = 5. Both are reproduced here to three significant figures by the
Brook and Evans Markov-chain approximation, which is the method the tables were
built with.

The chart arithmetic itself is checked against the recursion written out by
hand, and the exact Poisson limits against the explicit distribution sum.
"""
from __future__ import annotations

import math
import random
from datetime import timedelta

import pytest

from app.stats import spc
from app.stats.numeric import poisson_cdf
from app.stats.streams.request import FlowPeriod
from tests.unit.stats import datasets as ds


# ---------------------------------------------------------------------------
# Published average run lengths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lam, published_L",
    [(0.05, 2.615), (0.10, 2.814), (0.25, 2.998), (0.50, 3.071)],
)
def test_ewma_limit_solver_reproduces_lucas_and_saccucci_table_three(lam, published_L):
    """
    The published limit constants for an in-control run length of 500. These
    four pairs are the row every EWMA implementation is checked against, and
    they are the reason `target_arl0` is a parameter rather than 3 being a habit.
    """
    solved = spc.solve_ewma_limit(lam, 500)
    assert solved == pytest.approx(published_L, abs=0.01)
    assert spc.ewma_arl(lam, published_L) == pytest.approx(500.0, rel=0.01)


def test_ewma_out_of_control_run_length_matches_the_published_value():
    """Lucas and Saccucci: at lam = 0.10 and L = 2.814, a one-sigma shift is caught in 10.3 periods."""
    assert spc.ewma_arl(0.10, 2.814, shift=1.0) == pytest.approx(10.3, abs=0.1)


def test_ewma_arl_agrees_with_a_seeded_simulation():
    """
    An independent oracle for the Markov chain: simulate the chart directly.
    If the discretization were wrong, these would disagree.
    """
    rng = random.Random(5)
    lam, limit = 0.2, 2.9
    ucl = limit * math.sqrt(lam / (2.0 - lam))
    runs = []
    for _ in range(4000):
        z, i = 0.0, 0
        while True:
            i += 1
            z = lam * rng.gauss(1.0, 1.0) + (1.0 - lam) * z
            if abs(z) > ucl:
                break
        runs.append(i)
    simulated = sum(runs) / len(runs)
    assert spc.ewma_arl(lam, limit, shift=1.0) == pytest.approx(simulated, rel=0.06)


@pytest.mark.parametrize(
    "shift, published",
    [(0.0, 465.0), (1.0, 10.4), (1.5, 5.75), (2.0, 4.01)],
)
def test_cusum_run_lengths_match_the_published_table(shift, published):
    """The standard k = 0.5, h = 5 CUSUM table, reproduced in Montgomery ch. 9."""
    assert spc.cusum_arl(0.5, 5.0, shift=shift) == pytest.approx(published, rel=0.02)


# ---------------------------------------------------------------------------
# Chart arithmetic
# ---------------------------------------------------------------------------


def flow_periods(values, *, exposure=1.0, complete=True):
    periods = []
    for i, v in enumerate(values):
        start = ds.EPOCH + timedelta(days=7 * i)
        periods.append(FlowPeriod(
            period_start=start,
            period_end=start + timedelta(days=7),
            arrivals=int(v),
            terminals=0,
            resolutions=0,
            backlog_end=0,
            backlog_start=0,
            active_servers=2.0,
            arrival_rate_per_day=v / 7.0,
            exposure_days=exposure,
            complete=complete if i < len(values) - 1 else complete,
        ))
    return periods


def shifted_series(seed=3, before=30, after=10, level=10.0, shift=3.0):
    rng = random.Random(seed)
    return ([level + rng.gauss(0.0, 1.0) for _ in range(before)]
            + [level + shift + rng.gauss(0.0, 1.0) for _ in range(after)])


def test_ewma_statistic_matches_the_recursion_written_out_by_hand():
    values = shifted_series()
    window = ds.window_of(400)
    ev = spc.ewma_chart(values, window, lam=0.2, baseline_periods=30)
    centre = ev.value["center"]
    z = centre
    expected = []
    for v in values:
        z = 0.2 * v + 0.8 * z
        expected.append(z)
    assert ev.value["ewma"] == pytest.approx(expected)
    assert ev.value["ucl"] > centre > ev.value["lcl"]
    assert ev.interval_kind == "control-limits"


def test_cusum_statistic_matches_the_recursion_written_out_by_hand():
    values = shifted_series()
    window = ds.window_of(400)
    ev = spc.cusum_chart(values, window, k=0.5, h=5.0, baseline_periods=30)
    centre, sigma = ev.value["center"], ev.value["sigma"]
    hi = lo = 0.0
    expected_hi, expected_lo = [], []
    for v in values:
        z = (v - centre) / sigma
        hi = max(0.0, hi + z - 0.5)
        lo = max(0.0, lo - z - 0.5)
        expected_hi.append(hi)
        expected_lo.append(lo)
    assert ev.value["c_hi"] == pytest.approx(expected_hi)
    assert ev.value["c_lo"] == pytest.approx(expected_lo)


def test_both_charts_find_a_shift_that_was_planted_and_neither_signals_before_it():
    values = shifted_series()
    window = ds.window_of(400)
    ewma = spc.ewma_chart(values, window, lam=0.2, baseline_periods=30)
    cusum = spc.cusum_chart(values, window, baseline_periods=30)
    for ev in (ewma, cusum):
        indices = [s["index"] for s in ev.value["signals"]]
        assert indices, "the planted three-sigma shift was not detected"
        assert min(indices) >= 30
        assert all(s["direction"] == "above" for s in ev.value["signals"])
    # CUSUM is the faster detector of a persistent step; that is why both run.
    assert min(s["index"] for s in cusum.value["signals"]) <= \
        min(s["index"] for s in ewma.value["signals"])


def test_the_chart_reports_the_run_length_it_actually_attains():
    ev = spc.ewma_chart(shifted_series(), ds.window_of(400), lam=0.2, target_arl0=200,
                        baseline_periods=30)
    assert ev.value["target_arl0"] == 200.0
    assert ev.value["attained_arl0"] == pytest.approx(200.0, rel=0.02)
    assert ev.value["limit_constant"] < spc.solve_ewma_limit(0.2, 500)


def test_an_out_of_control_baseline_blocks_the_chart():
    """
    An out-of-control baseline produces a chart that says everything is fine,
    which is worse than no chart. It is a blocking failure for that reason.
    """
    values = shifted_series(before=12, after=12, shift=8.0)
    ev = spc.ewma_chart(values, ds.window_of(400), lam=0.2)
    check = next(c for c in ev.checks if c.id == "baseline-stability")
    assert check.status == "FAIL" and check.blocking
    assert ev.render_state == "not_interpretable"
    assert ev.value["points"] == []
    assert "quiet baseline" in check.detail


def test_autocorrelation_is_detected_and_the_attained_run_length_reported():
    rng = random.Random(9)
    values, previous = [], 0.0
    for _ in range(60):
        previous = 0.7 * previous + rng.gauss(0.0, 1.0)
        values.append(10.0 + previous)
    ev = spc.ewma_chart(values, ds.window_of(500), lam=0.2)
    check = next(c for c in ev.checks if c.id == "residual-autocorrelation")
    assert check.status == "WARN"
    assert check.statistic > 0.3
    assert "attained run length is nearer" in check.detail


def test_incomplete_periods_are_excluded_and_disclosed():
    periods = flow_periods([10] * 25)
    partial = periods[-1]
    periods[-1] = FlowPeriod(
        period_start=partial.period_start, period_end=partial.period_end, arrivals=1,
        terminals=0, resolutions=0, backlog_end=0, backlog_start=0, active_servers=2.0,
        arrival_rate_per_day=0.1, exposure_days=1.0, complete=False,
    )
    ev = spc.ewma_chart(periods, ds.window_of(400))
    assert ev.n == 24
    assert ev.n_excluded == 1
    assert ev.exclusion_reason == "incomplete_period"
    assert next(c for c in ev.checks if c.id == "incomplete-periods").status == "WARN"


def test_below_twenty_periods_is_the_calm_empty_state():
    ev = spc.ewma_chart([10.0] * 12, ds.window_of(200))
    assert ev.insufficient_data
    assert ev.render_state == "not_enough_data"
    assert ev.value["points"] == []
    assert "needs 20 complete periods, has 12" in ev.caveats[0]


# ---------------------------------------------------------------------------
# Poisson rate chart
# ---------------------------------------------------------------------------


def test_poisson_limits_are_the_exact_quantiles_not_a_normal_approximation():
    """
    For a known Poisson mean the limits must be the exact distribution
    quantiles. Montgomery's c-chart would draw 3-sigma lines instead, which is
    what the Method Card says this chart replaces.
    """
    rng = random.Random(2)
    counts = [rng.gauss(20.0, 4.0) for _ in range(30)]
    counts = [max(1.0, round(c)) for c in counts]
    ev = spc.poisson_rate_chart(flow_periods(counts), ds.window_of(400))
    centre = ev.value["center"]
    upper, lower = ev.value["ucl"][0], ev.value["lcl"][0]
    assert poisson_cdf(int(upper), centre) >= 1.0 - 0.00135
    assert poisson_cdf(int(upper) - 1, centre) < 1.0 - 0.00135
    assert poisson_cdf(int(lower), centre) <= 0.00135 + 1e-12 or lower == 0.0
    assert ev.value["distribution"] == "poisson"


def test_unequal_period_lengths_give_limits_that_vary_by_period():
    counts = [20, 22, 19, 21, 18, 23, 20, 21, 19, 22] * 3
    periods = []
    for i, c in enumerate(counts):
        start = ds.EPOCH + timedelta(days=30 * i)
        periods.append(FlowPeriod(
            period_start=start, period_end=start + timedelta(days=30), arrivals=c,
            terminals=0, resolutions=0, backlog_end=0, backlog_start=0, active_servers=1.0,
            arrival_rate_per_day=c / 30.0, exposure_days=28.0 if i % 2 else 31.0,
            complete=True,
        ))
    ev = spc.poisson_rate_chart(periods, ds.window_of(1000))
    assert len(set(ev.value["ucl"])) > 1
    assert next(c for c in ev.checks if c.id == "unequal-exposure").detail
    assert ev.unit == "events per unit exposure"


def test_overdispersion_switches_the_limits_to_negative_binomial_and_says_so():
    rng = random.Random(7)
    counts = [max(1, int(rng.gauss(20.0, 9.0))) for _ in range(40)]
    ev = spc.poisson_rate_chart(flow_periods(counts), ds.window_of(400))
    check = next(c for c in ev.checks if c.id == "overdispersion")
    assert check.status == "WARN"
    assert ev.value["distribution"] == "negative-binomial"
    assert check.statistic > 1.5


def test_poisson_chart_refuses_below_an_average_of_five_events():
    ev = spc.poisson_rate_chart(flow_periods([1, 2, 0, 1, 3] * 6), ds.window_of(400))
    assert ev.insufficient_data
    assert "averaging at least 5" in ev.caveats[0]
