"""
Known answers for the queueing models.

Three kinds of ground truth, in descending order of strength:

1. Theorems. Little's Law is an identity, so it is checked against a simulated
   queue with a known arrival rate. M/M/1 must be the c = 1 case of M/M/c, and
   M/G/1 at a coefficient of variation of 1 must equal M/M/1.
2. Published staffing tables. The standard Erlang-C cases: 20 erlangs of offered
   load at an 80% within 20 seconds target requires 24 agents; 10 erlangs
   requires 14; 3 erlangs requires 5. Erlang B against its published values.
3. Closed-form arithmetic worked by hand for Pollaczek-Khinchine.
"""
from __future__ import annotations

import math
import random
from datetime import timedelta

import pytest

from app.stats import queueing as q
from app.stats.streams.request import FlowPeriod
from tests.unit.stats import datasets as ds


def periods(backlogs, rates, *, complete=True):
    out = []
    for i, (b, r) in enumerate(zip(backlogs, rates)):
        start = ds.EPOCH + timedelta(days=7 * i)
        out.append(FlowPeriod(
            period_start=start, period_end=start + timedelta(days=7),
            arrivals=int(round(r * 7)), terminals=int(round(r * 7)),
            resolutions=int(round(r * 7)), backlog_end=int(b), backlog_start=int(b),
            active_servers=2.0, arrival_rate_per_day=r, exposure_days=7.0, complete=complete,
        ))
    return out


# ---------------------------------------------------------------------------
# Erlang B and C against published tables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("servers, published", [(1, 0.5), (2, 0.2), (3, 0.0625)])
def test_erlang_b_matches_its_published_values_at_one_erlang(servers, published):
    assert q.erlang_b(servers, 1.0) == pytest.approx(published, abs=1e-9)


@pytest.mark.parametrize(
    "offered, required",
    [(20.0, 24), (10.0, 14), (3.0, 5)],
)
def test_erlang_c_staffing_reproduces_the_published_agent_counts(offered, required):
    """
    The standard ACD staffing case: an 80% within 20 seconds service level at an
    average handle time of 180 seconds. The published grid gives 24 agents for
    20 erlangs, 14 for 10 and 5 for 3.
    """
    handle_time_days = 180.0 / 86400.0
    arrival_rate = offered / handle_time_days
    ev = q.erlang_c_staffing(
        arrival_rate, handle_time_days, ds.window_of(30),
        current_servers=required - 1,
        target_fraction=0.8,
        target_within_days=20.0 / 86400.0,
    )
    assert ev.value["required_servers"] == required
    assert ev.value["attained_at_required"] >= 0.8
    one_fewer = next(row for row in ev.value["curve"] if row["c"] == required - 1)
    assert one_fewer["p_within_target"] < 0.8


def test_the_staffing_curve_is_the_honest_output_not_a_confidence_interval():
    handle_time_days = 180.0 / 86400.0
    ev = q.erlang_c_staffing(
        20.0 / handle_time_days, handle_time_days, ds.window_of(30),
        current_servers=22, target_fraction=0.8, target_within_days=20.0 / 86400.0,
    )
    assert ev.interval is None and ev.interval_kind == "none"
    assert ev.value["gap"] == 2
    assert ev.value["attained_at_current"] == pytest.approx(0.545, abs=0.01)
    curve = {row["c"]: row["p_within_target"] for row in ev.value["curve"]}
    assert curve[23] < curve[24] < curve[25]


def test_erlang_c_probability_of_waiting_equals_the_mmc_value():
    """The exact identity the catalog asks for: the two must agree for the same parameters."""
    arrival_rate, service_rate, servers = 6.0, 1.0, 8
    offered = arrival_rate / service_rate
    from_erlang = q.erlang_c(servers, offered)
    ev = q.mmc_metrics(arrival_rate, service_rate, servers, ds.window_of(30))
    assert ev.value["p_wait"] == pytest.approx(from_erlang, abs=1e-12)


def test_the_staffing_service_always_warns_that_the_service_time_is_censored():
    ev = q.erlang_c_staffing(2.0, 0.5, ds.window_of(30), current_servers=3)
    check = next(c for c in ev.checks if c.id == "service-time-censoring")
    assert check.status == "WARN"
    assert "survival.km_resolution_curve" in check.detail


def test_specialised_resolvers_are_flagged_because_pooling_understates_the_need():
    ev = q.erlang_c_staffing(
        2.0, 0.5, ds.window_of(30), current_servers=3,
        category_mix={"a": {"plumbing": 40, "other": 1}, "b": {"electrical": 30, "other": 2}},
    )
    check = next(c for c in ev.checks if c.id == "servers-are-fungible")
    assert check.status == "WARN"
    assert "plumbing request cannot be taken by the electrical volunteer" in check.detail


# ---------------------------------------------------------------------------
# M/M/c and M/G/1 identities
# ---------------------------------------------------------------------------


def test_mmc_reduces_to_mm1_at_one_server():
    """M/M/1: Wq = rho / (mu - lambda). The c = 1 case must reproduce it exactly."""
    arrival_rate, service_rate = 0.6, 1.0
    rho = arrival_rate / service_rate
    expected = rho / (service_rate - arrival_rate)
    ev = q.mmc_metrics(arrival_rate, service_rate, 1, ds.window_of(30))
    assert ev.value["wq_days"] == pytest.approx(expected, abs=1e-12)


def test_mmc_outputs_satisfy_littles_law_internally():
    ev = q.mmc_metrics(6.0, 1.0, 8, ds.window_of(30))
    assert ev.value["l"] == pytest.approx(6.0 * ev.value["w_days"], abs=1e-12)
    assert ev.value["lq"] == pytest.approx(6.0 * ev.value["wq_days"], abs=1e-12)


def test_an_unstable_queue_reports_no_wait_at_all():
    ev = q.mmc_metrics(9.0, 1.0, 8, ds.window_of(30))
    check = next(c for c in ev.checks if c.id == "stability")
    assert check.status == "FAIL" and check.blocking
    assert ev.value["wq_days"] is None
    assert ev.render_state == "not_interpretable"
    assert "grows without bound" in check.detail
    assert "at least 10 active servers" in check.detail


def test_mg1_equals_mm1_when_service_is_exponential():
    """
    At a coefficient of variation of 1 the Pollaczek-Khinchine formula must
    reduce to M/M/1 to floating-point tolerance.
    """
    arrival_rate, service_mean = 0.6, 1.0
    exponential_variance = service_mean ** 2
    pk = q.pollaczek_khinchine_wait(arrival_rate, service_mean, exponential_variance)
    rho = arrival_rate * service_mean
    assert pk == pytest.approx(rho * service_mean / (1.0 - rho), abs=1e-12)


def test_mg1_wait_matches_hand_computation():
    """lambda = 0.5, mean = 1, var = 3: Wq = 0.5 * (3 + 1) / (2 * 0.5) = 2.0 days."""
    ev = q.mg1_wait(0.5, 1.0, 3.0, ds.window_of(30))
    assert ev.value == pytest.approx(2.0, abs=1e-12)
    assert ev.unit == "days"


def test_mg1_blocks_when_more_than_one_person_works_the_queue():
    ev = q.mg1_wait(0.5, 1.0, 3.0, ds.window_of(30), active_servers=3.0)
    check = next(c for c in ev.checks if c.id == "single-server-appropriate")
    assert check.status == "FAIL" and check.blocking
    assert ev.value is None
    assert "queueing.mmc_metrics" in check.detail


def test_heavy_tailed_service_times_are_flagged_as_the_wrong_model():
    samples = [0.1] * 40 + [50.0] * 5
    ev = q.mmc_metrics(0.5, 1.0, 4, ds.window_of(30), service_samples=samples)
    check = next(c for c in ev.checks if c.id == "exponential-service")
    assert check.status == "FAIL"
    assert "queueing.mg1_wait" in check.detail


# ---------------------------------------------------------------------------
# Little's Law
# ---------------------------------------------------------------------------


def test_littles_law_holds_on_a_simulated_queue_with_a_known_arrival_rate():
    """
    A theorem, which is a stronger ground truth than any published table: build
    a queue whose arrival rate and waits are known by construction, measure L by
    simulation, and assert L = lambda * W.
    """
    def poisson(rng, mean_count):
        """Knuth's sampler, so the simulation needs nothing but the seeded rng."""
        limit = math.exp(-mean_count)
        k, product = 0, rng.random()
        while product > limit:
            k += 1
            product *= rng.random()
        return k

    rng = random.Random(17)
    arrival_rate = 4.0            # per day
    mean_wait = 2.5               # days
    horizon = 400
    in_system = [0] * (horizon + 200)
    total_wait = 0.0
    arrivals = 0
    for day in range(horizon):
        for _ in range(poisson(rng, arrival_rate)):
            wait = rng.expovariate(1.0 / mean_wait)
            total_wait += wait
            arrivals += 1
            for d in range(day, min(len(in_system), day + max(1, int(round(wait))))):
                in_system[d] += 1
    observed_l = sum(in_system[100:horizon]) / (horizon - 100)
    observed_w = total_wait / arrivals
    observed_rate = arrivals / horizon
    assert observed_l == pytest.approx(observed_rate * observed_w, rel=0.15)


def test_little_law_service_reports_the_ratio_with_a_seeded_interval():
    rng = random.Random(5)
    backlogs = [20 + rng.randint(-2, 2) for _ in range(16)]
    rates = [4.0 for _ in range(16)]
    ev = q.little_law_wait(periods(backlogs, rates), ds.window_of(120), seed=3)
    assert ev.value == pytest.approx(sum(backlogs) / len(backlogs) / 4.0, abs=1e-9)
    assert ev.interval[0] < ev.value < ev.interval[1]
    assert ev.interval_kind == "bootstrap-bca-95"
    repeat = q.little_law_wait(periods(backlogs, rates), ds.window_of(120), seed=3)
    assert repeat.interval == ev.interval


def test_a_growing_backlog_blocks_the_wait_because_there_is_no_steady_state():
    backlogs = [10 + 4 * i for i in range(16)]
    ev = q.little_law_wait(periods(backlogs, [4.0] * 16), ds.window_of(120))
    check = next(c for c in ev.checks if c.id == "steady-state")
    assert check.status == "FAIL" and check.blocking
    assert ev.value is None
    assert ev.interval is None
    assert "the queue is diverging" in check.detail


def test_little_law_needs_eight_periods():
    ev = q.little_law_wait(periods([10] * 5, [2.0] * 5), ds.window_of(60))
    assert ev.insufficient_data
    assert "needs 8 complete periods, has 5" in ev.caveats[0]


# ---------------------------------------------------------------------------
# Backlog projection
# ---------------------------------------------------------------------------


def test_projection_with_no_capacity_accumulates_the_forecast_exactly():
    """The composition check: at zero capacity the projection is the running total of arrivals."""
    base = periods([12] * 10, [3.0] * 10)
    forecast = [5.0, 6.0, 7.0, 8.0]
    ev = q.backlog_projection(base, forecast, ds.window_of(120), current_servers=0, horizon=4)
    assert ev.value["backlog"] == pytest.approx([17.0, 23.0, 30.0, 38.0])
    assert ev.value["starting_backlog"] == 12.0


def test_projection_holds_the_backlog_flat_when_capacity_matches_arrivals():
    base = periods([12] * 10, [3.0] * 10)
    ev = q.backlog_projection(base, [21.0] * 5, ds.window_of(120), current_servers=1,
                              horizon=5, service_rate=21.0)
    assert ev.value["backlog"] == pytest.approx([12.0] * 5)


def test_projection_inherits_a_failing_forecast_check_rather_than_hiding_it():
    from app.stats.contracts import Check, Evidence

    forecast = Evidence(
        value={"y": [5.0, 5.0, 5.0], "lo": [3.0, 3.0, 3.0], "hi": [8.0, 9.0, 10.0]},
        n=40, method="forecast.request_volume", as_of=ds.window_of(120).end,
        checks=(Check(id="beats-seasonal-naive", label="Beats the seasonal-naive baseline",
                      status="FAIL", blocking=True,
                      detail="MASE above 1: the seasonal-naive forecast is reported instead"),),
    )
    base = periods([12] * 10, [3.0] * 10)
    ev = q.backlog_projection(base, forecast, ds.window_of(120), current_servers=0, horizon=3)
    assert any(c.id == "beats-seasonal-naive" and c.blocking for c in ev.checks)
    assert ev.render_state == "not_interpretable"
    assert ev.value["lo"] and ev.value["hi"]
