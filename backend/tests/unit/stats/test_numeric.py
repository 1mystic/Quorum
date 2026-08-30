"""
Known answers for the numerical primitives.

Every special function here is checked against a published value, never against
a previous run of itself. If these are wrong, every Method Card above them is
wrong too, so they get the same treatment as the services.
"""
from __future__ import annotations

import math

import pytest

from app.stats import numeric as nm


# ---------------------------------------------------------------------------
# Normal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "p, expected",
    [
        (0.5, 0.0),
        (0.975, 1.959963984540054),    # the textbook 1.96
        (0.95, 1.6448536269514722),
        (0.995, 2.5758293035489004),
        (0.001, -3.090232306167813),
    ],
)
def test_norm_ppf_matches_published_quantiles(p, expected):
    assert nm.norm_ppf(p) == pytest.approx(expected, abs=1e-9)


def test_norm_cdf_matches_published_values():
    # Standard normal table, three of the values every textbook prints.
    assert nm.norm_cdf(0.0) == pytest.approx(0.5, abs=1e-12)
    assert nm.norm_cdf(1.0) == pytest.approx(0.8413447460685429, abs=1e-12)
    assert nm.norm_cdf(-1.96) == pytest.approx(0.024997895148220435, abs=1e-12)


def test_norm_ppf_inverts_norm_cdf():
    for z in (-3.5, -1.0, 0.0, 0.25, 2.7):
        assert nm.norm_ppf(nm.norm_cdf(z)) == pytest.approx(z, abs=1e-9)


# ---------------------------------------------------------------------------
# Chi-square. The critical values are the ones printed in every table.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "df, critical",
    [(1, 3.841458820694124), (2, 5.991464547107979), (3, 7.814727903251179), (10, 18.30703805327515)],
)
def test_chi2_upper_tail_at_the_published_five_percent_point(df, critical):
    assert nm.chi2_sf(critical, df) == pytest.approx(0.05, abs=1e-9)
    assert nm.chi2_ppf(0.95, df) == pytest.approx(critical, abs=1e-6)


def test_chi2_sf_of_the_logrank_statistic_on_lung():
    """survdiff(Surv(time, status) ~ sex, lung) prints chi-square 10.3, p = 0.001."""
    assert nm.chi2_sf(10.3, 1) == pytest.approx(0.00133, abs=5e-5)


# ---------------------------------------------------------------------------
# Student's t
# ---------------------------------------------------------------------------


def test_t_distribution_against_published_critical_values():
    # t table: 2.5% upper tail at 10 df is 2.228, at 30 df is 2.042.
    assert nm.t_sf(2.228138852, 10) == pytest.approx(0.025, abs=1e-8)
    assert nm.t_sf(2.042272456, 30) == pytest.approx(0.025, abs=1e-8)
    # t with 1 df is Cauchy: the upper tail at 1.0 is exactly 0.25.
    assert nm.t_sf(1.0, 1) == pytest.approx(0.25, abs=1e-10)


# ---------------------------------------------------------------------------
# Poisson. Exactness here is the whole argument of spc.poisson_rate_chart.
# ---------------------------------------------------------------------------


def test_poisson_cdf_equals_the_explicit_sum():
    for mu in (0.7, 3.0, 19.85):
        for k in (0, 1, 5, 12):
            explicit = math.fsum(nm.poisson_pmf(j, mu) for j in range(k + 1))
            assert nm.poisson_cdf(k, mu) == pytest.approx(explicit, abs=1e-12)


def test_poisson_ppf_is_the_smallest_k_reaching_p():
    mu = 19.85
    for p in (0.00135, 0.025, 0.5, 0.975, 0.99865):
        k = nm.poisson_ppf(p, mu)
        assert nm.poisson_cdf(k, mu) >= p
        assert k == 0 or nm.poisson_cdf(k - 1, mu) < p


# ---------------------------------------------------------------------------
# Linear algebra
# ---------------------------------------------------------------------------


def test_solve_and_inverse_on_a_hand_computed_system():
    a = [[4.0, 7.0], [2.0, 6.0]]
    assert nm.solve(a, [1.0, 0.0]) == pytest.approx([0.6, -0.2], abs=1e-12)
    inv = nm.inverse(a)
    assert inv[0] == pytest.approx([0.6, -0.7], abs=1e-12)
    assert inv[1] == pytest.approx([-0.2, 0.4], abs=1e-12)


def test_solve_raises_on_a_singular_system():
    with pytest.raises(ValueError):
        nm.solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


# ---------------------------------------------------------------------------
# Regression and bootstrap
# ---------------------------------------------------------------------------


def test_ols_slope_recovers_an_exact_line():
    xs = list(range(10))
    ys = [3.0 + 2.0 * x for x in xs]
    slope, se, p = nm.ols_slope(xs, ys)
    assert slope == pytest.approx(2.0, abs=1e-12)
    assert se == pytest.approx(0.0, abs=1e-9)


def test_ols_slope_finds_no_trend_in_a_flat_series():
    xs = list(range(12))
    ys = [5.0, 4.0, 6.0, 5.0, 4.0, 6.0, 5.0, 4.0, 6.0, 5.0, 4.0, 6.0]
    slope, se, p = nm.ols_slope(xs, ys)
    assert p > 0.5


def test_bootstrap_is_deterministic_under_a_seed():
    data = [float(i) for i in range(40)]
    first = nm.bootstrap_bca(data, lambda xs: nm.mean(xs), seed=7, n_boot=200)
    second = nm.bootstrap_bca(data, lambda xs: nm.mean(xs), seed=7, n_boot=200)
    assert first == second
    assert first[0] < nm.mean(data) < first[1]
