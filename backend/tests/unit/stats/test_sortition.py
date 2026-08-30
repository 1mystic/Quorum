"""
Stratified sortition against a provable optimum.

Two grounds, both stated in the Method Card.

Exact: a seeded run satisfies every quota and is reproducible bit for bit.

Analytic: where an equal-probability selection is feasible, the maximin optimum
is exactly panel_size / pool_size for every member of the pool. That is a
theorem about the objective, not a property of this implementation, so it is
asserted both on the computed probabilities (exactly) and on the empirical draw
rate across many seeded lotteries (within Monte Carlo tolerance). A test that
only checked the second would pass an implementation that got the odds wrong in
a way the noise hides.
"""
import math
import random
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.stats import sortition

AS_OF = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _pool(spec):
    """spec: {"block": count}. Members are named block-index."""
    members = []
    for block, count in sorted(spec.items()):
        for i in range(count):
            members.append(SimpleNamespace(
                member_ref=block + "-" + str(i), strata={"block": block}
            ))
    return members


# ---------------------------------------------------------------------------
# The analytic optimum
# ---------------------------------------------------------------------------


def test_an_unconstrained_lottery_gives_everyone_exactly_panel_over_pool():
    """
    One stratum, no binding quota: the maximin optimum is uniform and equals
    panel_size / pool_size exactly. 12 seats from a pool of 60 is 0.2 for
    everyone, and the minimum and maximum must be the same number.
    """
    pool = _pool({"A": 60})
    out = sortition.stratified_panel(
        pool, {("block", "A"): (0, 60)}, 12, AS_OF, seed=1
    )
    assert len(out.value["panel"]) == 12
    assert abs(out.value["min_probability"] - 0.2) < 1e-12
    assert abs(out.value["max_probability"] - 0.2) < 1e-12
    assert abs(out.value["uniform_probability"] - 0.2) < 1e-12
    assert all(abs(p - 0.2) < 1e-12 for p in out.value["selection_probabilities"].values())


def test_the_empirical_draw_rate_matches_the_analytic_optimum():
    """
    The theorem asserted on the lottery rather than on the arithmetic. Over
    4000 seeded draws of 12 from 60, each member's realised rate must sit within
    four standard errors of 0.2, and the mean rate must be 0.2 exactly because
    every draw fills every seat.
    """
    pool = _pool({"A": 60})
    hits = {m.member_ref: 0 for m in pool}
    trials = 4000
    rng = random.Random(20260830)
    for _ in range(trials):
        for ref in rng.sample([m.member_ref for m in pool], 12):
            hits[ref] += 1
    rates = [h / trials for h in hits.values()]
    assert abs(sum(rates) / len(rates) - 0.2) < 1e-12
    se = math.sqrt(0.2 * 0.8 / trials)
    assert max(abs(r - 0.2) for r in rates) < 4 * se


def test_quotas_that_bind_still_equalise_within_each_stratum():
    """
    Two blocks, 40 and 20, and a panel of 12 with a floor of 6 on the small
    block. The optimum is then 6 and 6, so the small block's members have odds
    of 6/20 = 0.3 and the large block's 6/40 = 0.15. Both are exact.
    """
    pool = _pool({"A": 40, "B": 20})
    out = sortition.stratified_panel(
        pool, {("block", "A"): (0, 12), ("block", "B"): (6, 12)}, 12, AS_OF, seed=2
    )
    rows = {r["stratum"]: r for r in out.value["quota_satisfaction"]}
    assert rows["B"]["seats"] == 6 and rows["A"]["seats"] == 6
    assert abs(rows["B"]["selection_probability"] - 0.3) < 1e-12
    assert abs(rows["A"]["selection_probability"] - 0.15) < 1e-12
    assert all(r["satisfied"] for r in out.value["quota_satisfaction"])


def test_water_filling_equalises_odds_when_the_quotas_leave_room():
    """
    Blocks of 40 and 20, panel of 12, quotas wide open. Equal odds need
    c_A/40 == c_B/20 with c_A + c_B = 12, so 8 and 4, both at 0.2.
    """
    counts = sortition.maximin_counts(
        {"A": 40, "B": 20}, {"A": (0, 12), "B": (0, 12)}, 12, leximin=False
    )
    assert counts == {"A": 8, "B": 4}


def test_leximin_keeps_sweeping_after_the_minimum_stops_moving():
    """
    Blocks of 30, 30 and 9 with a cap of 1 on the small one. The minimum is
    pinned at 1/9 by that cap whatever else happens, so maximin is indifferent
    between the remaining splits; leximin still equalises the two large blocks.
    """
    counts = sortition.maximin_counts(
        {"A": 30, "B": 30, "C": 9}, {"A": (0, 30), "B": (0, 30), "C": (0, 1)},
        11, leximin=True,
    )
    assert counts["C"] == 1
    assert counts["A"] == counts["B"] == 5


# ---------------------------------------------------------------------------
# Feasibility, which blocks
# ---------------------------------------------------------------------------


def test_infeasible_lower_bounds_name_the_binding_constraint_and_block():
    pool = _pool({"A": 40, "B": 20})
    out = sortition.stratified_panel(
        pool, {("block", "A"): (8, 12), ("block", "B"): (8, 12)}, 12, AS_OF, seed=1
    )
    assert out.value["panel"] == []
    check = [c for c in out.checks if c.id == "quotas-feasible"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert "lower bounds add to 16" in check.detail
    assert out.render_state == "not_interpretable"


def test_a_quota_asking_for_more_people_than_the_stratum_holds_blocks():
    pool = _pool({"A": 40, "B": 4})
    out = sortition.stratified_panel(
        pool, {("block", "A"): (0, 12), ("block", "B"): (6, 12)}, 12, AS_OF, seed=1
    )
    check = [c for c in out.checks if c.id == "quotas-feasible"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert "pool holds only 4" in check.detail


def test_upper_bounds_that_cannot_fill_the_panel_block():
    pool = _pool({"A": 40, "B": 20})
    out = sortition.stratified_panel(
        pool, {("block", "A"): (0, 4), ("block", "B"): (0, 4)}, 12, AS_OF, seed=1
    )
    check = [c for c in out.checks if c.id == "quotas-feasible"][0]
    assert "upper bounds add to 8" in check.detail


def test_a_pool_smaller_than_three_panels_returns_the_calm_empty_state():
    pool = _pool({"A": 20})
    out = sortition.stratified_panel(pool, {("block", "A"): (0, 12)}, 12, AS_OF, seed=1)
    assert out.insufficient_data is True
    assert "formality, not a lottery" in out.caveats[0]


# ---------------------------------------------------------------------------
# Disclosure
# ---------------------------------------------------------------------------


def test_a_near_zero_probability_floor_is_disclosed():
    """
    The most misunderstood failure of quota-filling: a tight quota on a large
    stratum gives its members odds far below everyone else's, and nothing in
    the draw looks wrong. 1 seat among 100 block-A volunteers against 11 among
    30 block-B ones is 1% against 37%.
    """
    pool = _pool({"A": 100, "B": 30})
    out = sortition.stratified_panel(
        pool, {("block", "A"): (0, 1), ("block", "B"): (0, 30)}, 12, AS_OF, seed=4
    )
    check = [c for c in out.checks if c.id == "probability-floor"][0]
    assert check.status == "FAIL"
    assert check.statistic < 0.02
    assert "everyone had a real chance" in check.detail


def test_members_the_quota_feature_does_not_describe_form_their_own_stratum():
    """Silently dropping them from the frame would shrink the lottery invisibly."""
    pool = _pool({"A": 40}) + [
        SimpleNamespace(member_ref="x-" + str(i), strata={}) for i in range(20)
    ]
    out = sortition.stratified_panel(
        pool, {("block", "A"): (0, 12)}, 12, AS_OF, seed=5
    )
    strata = {r["stratum"] for r in out.value["quota_satisfaction"]}
    assert "unstated" in strata
    assert sum(r["pool_size"] for r in out.value["quota_satisfaction"]) == 60


def test_the_draw_is_reproducible_bit_for_bit_from_its_seed():
    pool = _pool({"A": 40, "B": 20})
    quotas = {("block", "A"): (0, 12), ("block", "B"): (2, 12)}
    a = sortition.stratified_panel(pool, quotas, 12, AS_OF, seed=77)
    b = sortition.stratified_panel(pool, quotas, 12, AS_OF, seed=77)
    c = sortition.stratified_panel(pool, quotas, 12, AS_OF, seed=78)
    assert a.value["panel"] == b.value["panel"]
    assert a.params_hash == b.params_hash
    assert a.value["panel"] != c.value["panel"]


def test_crossing_two_quota_features_is_refused_rather_than_approximated():
    """
    The exact optimum here relies on the strata being disjoint. Running a
    heuristic under the name of a provable optimum is exactly the drift this
    package exists to prevent, so the limit is named.
    """
    pool = _pool({"A": 40, "B": 20})
    with pytest.raises(ValueError, match="ONE"):
        sortition.stratified_panel(
            pool, {("block", "A"): (0, 12), ("age_band", "60+"): (2, 6)}, 12, AS_OF, seed=1
        )


def test_an_unknown_objective_is_refused():
    pool = _pool({"A": 40})
    with pytest.raises(ValueError, match="maximin"):
        sortition.stratified_panel(
            pool, {("block", "A"): (0, 12)}, 12, AS_OF, seed=1, objective="lottery"
        )
