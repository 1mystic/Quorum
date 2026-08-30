"""
Known answers for workload concentration and assignment.

The Gini coefficient has three exact closed forms, so no reference
implementation is needed at all. The Hungarian algorithm is checked against
exhaustive enumeration, which is an independent and exact oracle on small
matrices, plus the invariant that adding a constant to any row leaves the
optimal assignment unchanged.
"""
from __future__ import annotations

import itertools
import random

import pytest

from app.stats import fairness as f
from tests.unit.stats import datasets as ds


# ---------------------------------------------------------------------------
# Gini: three exact values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [5, 10, 37])
def test_gini_of_a_perfectly_equal_vector_is_zero(n):
    assert f.gini([7.0] * n) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("n", [5, 10, 37])
def test_gini_of_a_single_worker_carrying_everything_is_n_minus_one_over_n(n):
    assert f.gini([0.0] * (n - 1) + [1.0]) == pytest.approx((n - 1) / n, abs=1e-12)


@pytest.mark.parametrize("n", [5, 10, 37])
def test_gini_of_the_discrete_uniform_is_n_minus_one_over_three_n(n):
    assert f.gini(list(range(1, n + 1))) == pytest.approx((n - 1) / (3 * n), abs=1e-12)


def test_the_lorenz_curve_runs_from_zero_to_one_and_is_convex():
    values = [1.0, 2.0, 3.0, 10.0, 20.0]
    curve = f.lorenz(values)
    assert curve["cum_share_people"][0] == 0.0 and curve["cum_share_people"][-1] == 1.0
    assert curve["cum_share_work"][0] == 0.0 and curve["cum_share_work"][-1] == pytest.approx(1.0)
    gaps = [b - a for a, b in zip(curve["cum_share_work"], curve["cum_share_work"][1:])]
    assert gaps == sorted(gaps), "the Lorenz curve must be convex when loads are sorted"


def test_gini_rejects_negative_work():
    with pytest.raises(ValueError):
        f.gini([1.0, -2.0])


# ---------------------------------------------------------------------------
# The workload service
# ---------------------------------------------------------------------------


def workload(counts, *, categories=None):
    """counts maps a resolver to how many requests they hold."""
    spells = []
    index = 0
    for person, count in counts.items():
        for _ in range(count):
            spells.append(ds.spell(
                "w" + str(index), days=1.0 + (index % 5), observed=True,
                assignee_ref=person,
                category=(categories[person] if categories else "general"),
            ))
            index += 1
    return spells


def test_workload_gini_reports_the_coefficient_with_a_seeded_bootstrap_interval():
    counts = {("p" + str(i)): (i + 1) * 2 for i in range(12)}
    ev = f.workload_gini(workload(counts), ds.window_of(60), seed=4)
    assert ev.value["gini"] == pytest.approx(f.gini(list(counts.values())), abs=1e-12)
    assert ev.interval[0] <= ev.value["gini"] <= ev.interval[1]
    assert ev.interval_kind == "bootstrap-bca-95"
    repeat = f.workload_gini(workload(counts), ds.window_of(60), seed=4)
    assert repeat.interval == ev.interval


def test_small_per_person_rows_are_suppressed_but_the_aggregate_still_reports():
    counts = {("p" + str(i)): 10 for i in range(10)}
    counts["quiet"] = 2
    ev = f.workload_gini(workload(counts), ds.window_of(60), k_anonymity=5)
    check = next(c for c in ev.checks if c.id == "k-anonymity-rows")
    assert check.status == "FAIL" and check.blocking
    assert ev.value["gini"] is not None
    assert all(row["load"] is None for row in ev.value["rows"] if row["suppressed"])
    assert all(row["key"] == "suppressed" for row in ev.value["rows"] if row["suppressed"])


def test_whether_zero_workers_are_counted_is_declared_and_changes_the_answer():
    counts = {("p" + str(i)): 6 for i in range(10)}
    spells = workload(counts)
    roster = list(counts) + ["idle-" + str(i) for i in range(10)]
    without = f.workload_gini(spells, ds.window_of(60))
    with_zeros = f.workload_gini(spells, ds.window_of(60), include_zero_workers=True,
                                 roster=roster)
    assert without.value["gini"] == pytest.approx(0.0, abs=1e-12)
    assert with_zeros.value["gini"] > 0.4
    assert without.params_hash != with_zeros.params_hash
    assert "declared parameter" in next(
        c for c in with_zeros.checks if c.id == "zero-workers-included"
    ).detail


def test_a_lopsided_category_mix_warns_that_counts_are_not_comparable_work():
    counts = {("p" + str(i)): 8 for i in range(10)}
    categories = {p: ("plumbing" if i < 5 else "noise") for i, p in enumerate(counts)}
    ev = f.workload_gini(workload(counts, categories=categories), ds.window_of(60))
    check = next(c for c in ev.checks if c.id == "unequal-difficulty")
    assert check.status == "WARN"
    assert "hours-weighted" in check.detail


def test_workload_gini_needs_ten_resolvers_and_fifty_requests():
    ev = f.workload_gini(workload({"a": 30, "b": 30}), ds.window_of(60))
    assert ev.insufficient_data
    assert ev.value["gini"] is None
    assert "description of three people" in ev.caveats[0]


# ---------------------------------------------------------------------------
# Assignment
# ---------------------------------------------------------------------------


def brute_force(matrix):
    n = len(matrix)
    return min(sum(matrix[i][p[i]] for i in range(n)) for p in itertools.permutations(range(n)))


def test_hungarian_matches_exhaustive_enumeration_on_seeded_random_matrices():
    rng = random.Random(1)
    for _ in range(40):
        n = rng.randint(2, 6)
        matrix = [[float(rng.randint(0, 20)) for _ in range(n)] for _ in range(n)]
        assignment = f.hungarian(matrix)
        cost = sum(matrix[i][assignment[i]] for i in range(n))
        assert cost == pytest.approx(brute_force(matrix))
        assert sorted(assignment) == list(range(n))


def test_hungarian_beats_the_greedy_choice_on_a_three_by_three_instance():
    """
    The instance that shows why this is not a sort. Taking each row's cheapest
    column in turn gives 8 + 10 + 16 = 34; the optimal assignment costs 33.
    """
    matrix = [[10.0, 19.0, 8.0], [10.0, 18.0, 7.0], [13.0, 16.0, 9.0]]
    assignment = f.hungarian(matrix)
    cost = sum(matrix[i][assignment[i]] for i in range(3))
    assert cost == pytest.approx(brute_force(matrix))
    assert cost == pytest.approx(33.0)
    assert cost < 34.0


def test_adding_a_constant_to_a_row_leaves_the_optimal_assignment_unchanged():
    rng = random.Random(9)
    matrix = [[float(rng.randint(0, 30)) for _ in range(5)] for _ in range(5)]
    before = f.hungarian(matrix)
    shifted = [list(row) for row in matrix]
    shifted[2] = [v + 100.0 for v in shifted[2]]
    assert f.hungarian(shifted) == before


def open_request(ref, category="plumbing"):
    return ds.spell(ref, days=2.0, observed=False, category=category)


def test_balanced_assignment_sends_work_to_the_least_loaded_capable_resolver():
    requests = [open_request("r1"), open_request("r2"), open_request("r3")]
    resolvers = [
        {"ref": "busy", "skills": ["plumbing"], "current_load": 9.0},
        {"ref": "free", "skills": ["plumbing"], "current_load": 0.0},
        {"ref": "spare", "skills": ["plumbing"], "current_load": 1.0},
    ]
    ev = f.balanced_assignment(requests, resolvers,
                               capacity={"busy": 2, "free": 2, "spare": 2})
    picked = {row["request_ref"]: row["suggested_assignee_ref"] for row in ev.value}
    assert sorted(picked.values()) == ["free", "free", "spare"]
    assert ev.interval is None and ev.interval_kind == "none"
    assert all(row["reason"] for row in ev.value)


def test_capacity_below_demand_returns_the_partial_assignment_and_the_shortfall():
    requests = [open_request("r" + str(i)) for i in range(4)]
    resolvers = [
        {"ref": "a", "skills": ["plumbing"], "current_load": 0.0},
        {"ref": "b", "skills": ["plumbing"], "current_load": 0.0},
    ]
    ev = f.balanced_assignment(requests, resolvers, capacity={"a": 1, "b": 1})
    check = next(c for c in ev.checks if c.id == "capacity-feasible")
    assert check.status == "FAIL" and check.blocking
    unassigned = [row for row in ev.value if row["suggested_assignee_ref"] is None]
    assert len(unassigned) == 2
    assert "shortfall of 2" in check.detail


def test_a_category_nobody_can_take_is_surfaced_not_silently_assigned():
    requests = [open_request("r1", category="sewage"), open_request("r2")]
    resolvers = [
        {"ref": "a", "skills": ["plumbing"], "current_load": 0.0},
        {"ref": "b", "skills": ["plumbing"], "current_load": 0.0},
    ]
    ev = f.balanced_assignment(requests, resolvers, capacity={"a": 2, "b": 2})
    check = next(c for c in ev.checks if c.id == "skill-coverage")
    assert check.status == "WARN"
    assert "sewage" in check.detail
    row = next(r for r in ev.value if r["request_ref"] == "r1")
    assert "outside the declared skill set" in row["reason"]


def test_the_suggestion_reports_what_it_does_to_concentration():
    requests = [open_request("r" + str(i)) for i in range(6)]
    resolvers = [
        {"ref": "a", "skills": [], "current_load": 12.0},
        {"ref": "b", "skills": [], "current_load": 0.0},
        {"ref": "c", "skills": [], "current_load": 0.0},
    ]
    ev = f.balanced_assignment(requests, resolvers, capacity={"a": 3, "b": 3, "c": 3})
    check = next(c for c in ev.checks if c.id == "balance-improved")
    assert check.status == "PASS"
    assert check.statistic < 0.0
    assert "Gini scale" in check.detail
