"""
Known answers for level-shift detection.

The benchmark is the Nile: annual flow at Aswan, 1871 to 1970, the dataset every
changepoint paper and package is checked against. PELT with an mBIC penalty must
find exactly one shift, at the year the first Aswan works began, with the
published segment means of about 1097 and about 850.
"""
from __future__ import annotations

import random

import pytest

from app.stats import changepoint as cp
from app.stats.changepoint import pelt
from app.stats.series import robust_sigma
from tests.unit.stats import datasets as ds


def nile_values():
    return [flow for _, flow in ds.nile_series()]


def nile_years():
    return [year for year, _ in ds.nile_series()]


def test_pelt_finds_the_single_nile_changepoint_at_1898():
    """
    The canonical result. Our index is the first year of the new, lower level;
    R's `changepoint` package reports the last year of the old one, so index 28
    here and cpt = 28 there are the same shift: the flow dropped after 1898, the
    year construction of the first Aswan dam began.
    """
    values = nile_values()
    years = nile_years()
    ev = cp.detect_level_shifts(values, ds.window_of(200))
    assert len(ev.value) == 1
    row = ev.value[0]
    assert row["index"] == 28
    assert years[row["index"]] == 1899
    assert years[row["index"] - 1] == 1898
    assert row["before_mean"] == pytest.approx(1097.75, abs=0.01)
    assert row["after_mean"] == pytest.approx(849.97, abs=0.01)
    assert row["delta"] == pytest.approx(-247.78, abs=0.05)


def test_the_nile_changepoint_survives_its_permutation_test():
    ev = cp.detect_level_shifts(nile_values(), ds.window_of(200))
    assert ev.value[0]["p_value"] < 0.01
    assert next(c for c in ev.checks if c.id == "significance").status == "PASS"


def test_the_interval_is_on_the_date_and_brackets_the_estimate():
    """
    The interval says "the level shifted somewhere between these two years", not
    "the shift was this big". The second is reported separately as delta.
    """
    ev = cp.detect_level_shifts(nile_values(), ds.window_of(200))
    row = ev.value[0]
    assert row["lo_index"] <= row["index"] <= row["hi_index"]
    assert row["hi_index"] - row["lo_index"] < 15
    assert ev.interval_kind == "bootstrap-bca-95"


def test_the_penalty_is_a_declared_choice_and_it_matters():
    """
    BIC over-segments the Nile into five changepoints; mBIC finds the one that
    is really there. The penalty is therefore a declared parameter in
    params_hash rather than something tuned until the answer looks good.
    """
    values = nile_values()
    sigma2 = robust_sigma(values) ** 2
    import math

    bic = pelt(values, penalty=math.log(len(values)), min_segment=4, sigma2=sigma2)
    mbic = pelt(values, penalty=3.0 * math.log(len(values)), min_segment=4, sigma2=sigma2)
    assert len(bic) > len(mbic)
    assert mbic == [28]
    a = cp.detect_level_shifts(values, ds.window_of(200), penalty="bic")
    b = cp.detect_level_shifts(values, ds.window_of(200), penalty="mbic")
    assert a.params_hash != b.params_hash


def test_a_flat_series_has_no_changepoints():
    rng = random.Random(1)
    values = [50.0 + rng.gauss(0.0, 2.0) for _ in range(60)]
    ev = cp.detect_level_shifts(values, ds.window_of(200))
    assert ev.value == []
    assert ev.render_state == "estimate"


def test_a_changepoint_against_the_edge_is_suppressed_not_reported():
    """The most common false positive in this family, so it is a blocking row-level failure."""
    rng = random.Random(2)
    values = [10.0 + rng.gauss(0.0, 0.5) for _ in range(40)] + [40.0, 41.0]
    ev = cp.detect_level_shifts(values, ds.window_of(200), min_segment=4)
    assert ev.value == []
    check = next(c for c in ev.checks if c.id == "edge-changepoint")
    assert check.status == "FAIL" and check.blocking
    assert ev.render_state == "not_interpretable"


def test_two_planted_shifts_are_both_found_at_the_right_places():
    rng = random.Random(4)
    values = ([10.0 + rng.gauss(0.0, 1.0) for _ in range(30)]
              + [20.0 + rng.gauss(0.0, 1.0) for _ in range(30)]
              + [14.0 + rng.gauss(0.0, 1.0) for _ in range(30)])
    ev = cp.detect_level_shifts(values, ds.window_of(200))
    found = [row["index"] for row in ev.value]
    assert found == [30, 60]
    assert ev.value[0]["delta"] == pytest.approx(10.0, abs=1.0)
    assert ev.value[1]["delta"] == pytest.approx(-6.0, abs=1.0)


def test_autocorrelation_raises_the_penalty_rather_than_reporting_a_staircase():
    rng = random.Random(11)
    values, previous = [], 0.0
    for _ in range(80):
        previous = 0.75 * previous + rng.gauss(0.0, 1.0)
        values.append(20.0 + 3.0 * previous)
    ev = cp.detect_level_shifts(values, ds.window_of(300))
    check = next(c for c in ev.checks if c.id == "residual-autocorrelation")
    assert check.status == "WARN"
    assert "penalty was raised" in check.detail


def test_below_twenty_four_periods_is_the_calm_empty_state():
    ev = cp.detect_level_shifts([1.0] * 10, ds.window_of(50))
    assert ev.insufficient_data
    assert ev.value == []
    assert "needs 24 periods, has 10" in ev.caveats[0]


def test_the_result_is_deterministic_under_a_seed():
    a = cp.detect_level_shifts(nile_values(), ds.window_of(200), seed=7)
    b = cp.detect_level_shifts(nile_values(), ds.window_of(200), seed=7)
    assert a.value == b.value
    assert a.params_hash == b.params_hash
