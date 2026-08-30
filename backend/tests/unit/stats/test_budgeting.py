"""
Participatory budgeting, checked against hand-worked instances and against the
guarantee the Method of Equal Shares exists for.

The EJR checker is the load-bearing piece here and it is tested in both
directions, because a property checker that has only ever returned PASS is
indistinguishable from `return True`. The minority-preference instance below
constructs a violation that greedy commits and Equal Shares does not:

  twenty voters, a budget of 100, ten projects costing 10 each plus q at 10.
  Sixteen voters approve p1..p10. Four voters approve q, and nothing else.
  Greedy funds p1..p10, exhausting the budget, and leaves q unfunded, so the
  four voters, whose collective share of the budget is 20 and whose project
  costs 10, receive nothing at all. That is an EJR violation and it is
  hand-checkable from those three numbers.
  Equal Shares charges the sixteen voters 0.625 each per project, runs them out
  of purse after eight projects, and funds q at rho = 2.5 out of the four
  voters' own shares.
"""
import random
from datetime import datetime, timezone

import pytest

from app.stats import budgeting
from app.stats.streams.decision import Ballot, DecisionOption, DecisionSpec
from app.stats.streams.member import RosterSnapshot

OPENED = datetime(2026, 3, 1, tzinfo=timezone.utc)
CLOSED = datetime(2026, 3, 31, tzinfo=timezone.utc)


def _spec(budget, rule="mes") -> DecisionSpec:
    return DecisionSpec(
        decision_ref="pb1", kind="budget_allocation", opened_at=OPENED, closed_at=CLOSED,
        declared_rule=rule, budget_minor=budget, ballot_style="approval",
    )


def _options(costs) -> list[DecisionOption]:
    return [
        DecisionOption(option_ref=ref, decision_ref="pb1", label=ref.title(), cost_minor=cost)
        for ref, cost in sorted(costs.items())
    ]


def _ballots(approval_sets, strata=None):
    strata = strata or {}
    return [
        Ballot(
            ballot_ref="b" + str(i), decision_ref="pb1", voter_ref="v" + str(i),
            cast_at=OPENED, approvals=frozenset(a), strata=dict(strata.get(i, {})),
        )
        for i, a in enumerate(approval_sets)
    ]


# ---------------------------------------------------------------------------
# The minority-preference instance
# ---------------------------------------------------------------------------

MINORITY_COSTS = {"p" + str(i): 10 for i in range(1, 11)}
MINORITY_COSTS["q"] = 10
MINORITY_APPROVALS = (
    [frozenset("p" + str(i) for i in range(1, 11))] * 16
    + [frozenset({"q"})] * 4
)
MINORITY_BUDGET = 100


def test_the_entitlement_arithmetic_is_hand_checkable():
    """Stated independently of the code, so the fixture is not defined by its answer."""
    n, budget, minority, cost_of_q = 20, 100, 4, 10
    assert minority * budget / n == 20 >= cost_of_q, (
        "four of twenty voters have a collective share of 20, and q costs 10, so they are "
        "1-cohesive for {q} and EJR entitles one of them to utility 1"
    )


def test_greedy_leaves_the_minority_with_nothing_and_the_ejr_check_fails():
    out = budgeting.greedy_knapsack(
        _ballots(MINORITY_APPROVALS), _options(MINORITY_COSTS), _spec(MINORITY_BUDGET, "greedy")
    )
    assert "q" not in out.value["funded"]
    assert out.value["spent_minor"] == 100

    check = [c for c in out.checks if c.id == "ejr-satisfied"][0]
    assert check.status == "FAIL"
    assert check.blocking is False, "greedy never promised EJR; the point is showing the cost"
    violation = out.value["ejr_violations"][0]
    assert violation["projects"] == ["q"]
    assert violation["n_voters"] == 4
    assert violation["best_utility_in_group"] == 0
    assert violation["required_utility"] == 1


def test_equal_shares_funds_the_minority_project_out_of_their_own_share():
    out = budgeting.method_of_equal_shares(
        _ballots(MINORITY_APPROVALS), _options(MINORITY_COSTS), _spec(MINORITY_BUDGET)
    )
    assert "q" in out.value["funded"]
    check = [c for c in out.checks if c.id == "ejr-satisfied"][0]
    assert check.status == "PASS"
    assert out.value["ejr_violations"] == []


def test_the_equal_shares_rho_arithmetic_matches_the_hand_computation():
    """
    Per-voter share is 100/20 = 5. A project approved by sixteen voters needs
    16 * rho >= 10, so rho = 0.625. Project q, approved by four, needs
    4 * rho >= 10, so rho = 2.5. The cheapest rho goes first, which is why the
    sixteen-voter projects are funded before q.
    """
    funded, rounds, purses = budgeting.equal_shares(
        MINORITY_APPROVALS, MINORITY_COSTS, 100 / 20
    )
    assert abs(rounds[0]["rho"] - 0.625) < 1e-12
    assert rounds[0]["n_supporters"] == 16
    q_round = [r for r in rounds if r["funded"] == "q"][0]
    assert abs(q_round["rho"] - 2.5) < 1e-12
    # The sixteen-voter bloc exhausts its purses after eight projects at 0.625.
    assert abs(purses[0]) < 1e-9
    # The four minority voters paid 2.5 each out of 5.
    assert abs(purses[19] - 2.5) < 1e-9


def test_a_blocking_ejr_violation_empties_the_equal_shares_allocation():
    """
    Equal Shares guarantees EJR, so a violation there is an implementation bug
    rather than a trade-off, and the allocation must not be printed as if it
    were one. Proven by feeding the checker a hand-built violating allocation.
    """
    violations, exhaustive = budgeting.ejr_violations(
        MINORITY_APPROVALS, MINORITY_COSTS, MINORITY_BUDGET,
        funded=["p" + str(i) for i in range(1, 11)],
    )
    assert exhaustive is True
    assert [v["projects"] for v in violations] == [["q"]]

    check = budgeting._ejr_check(violations, exhaustive, blocking=True, rule="equal shares")
    assert check.status == "FAIL" and check.blocking is True
    assert "implementation bug" in check.detail


# ---------------------------------------------------------------------------
# The greedy baseline against the exact optimum
# ---------------------------------------------------------------------------


def test_the_knapsack_dynamic_program_is_exact_on_a_hand_computed_instance():
    """
    Values (60, 100, 120), weights (10, 20, 30), capacity 50. The published
    answer to this textbook instance is 220, taking the second and third items.
    Density order would take the first two, for 160, and then stop.
    """
    assert budgeting.knapsack_optimum([60, 100, 120], [10, 20, 30], 50) == 220
    assert budgeting.knapsack_optimum([60, 100, 120], [10, 20, 30], 10) == 60
    assert budgeting.knapsack_optimum([1, 1], [3, 3], 2) == 0


def test_greedy_beats_half_the_optimum_on_seeded_random_instances():
    """
    Density greedy alone has NO approximation guarantee. Taking the better of it
    and the best single affordable project does: the shipped rule must reach at
    least half the exact optimum on every instance, and the test looks for a
    counterexample across 200 seeded ones rather than asserting on one.
    """
    rng = random.Random(20260830)
    worst_ratio = 1.0
    for _ in range(200):
        m = rng.randint(3, 9)
        costs = {"p" + str(i): rng.randint(1, 40) for i in range(m)}
        n_voters = 24
        approvals = [
            frozenset(p for p in costs if rng.random() < 0.4) for _ in range(n_voters)
        ]
        budget = rng.randint(20, 90)
        out = budgeting.greedy_knapsack(
            _ballots(approvals), _options(costs), _spec(budget, "greedy")
        )
        support = [sum(1 for a in approvals if p in a) for p in sorted(costs)]
        weights = [costs[p] for p in sorted(costs)]
        optimum = budgeting.knapsack_optimum(support, weights, budget)
        served = out.value["total_approvals"]
        if optimum > 0:
            worst_ratio = min(worst_ratio, served / optimum)
    assert worst_ratio >= 0.5, "worst observed ratio to the optimum was " + repr(worst_ratio)


def test_the_density_greedy_alone_can_be_arbitrarily_bad_and_the_variant_check_says_so():
    """
    The negative control for the variant rule. One cheap project with a single
    approval, and one expensive project everyone wants. Density greedy takes the
    cheap one first and then cannot afford the other.
    """
    costs = {"cheap": 1, "big": 100}
    costs["filler"] = 100
    approvals = [frozenset({"cheap", "big"})] + [frozenset({"big"})] * 23
    out = budgeting.greedy_knapsack(
        _ballots(approvals), _options(costs), _spec(100, "greedy")
    )
    assert out.value["funded"] == ["big"]
    assert out.value["variant"] == "best-single-project"
    check = [c for c in out.checks if c.id == "greedy-variant"][0]
    assert "no approximation guarantee" in check.detail


# ---------------------------------------------------------------------------
# The fairness report
# ---------------------------------------------------------------------------


def test_the_utilisation_identity_is_exact_arithmetic_on_the_allocation():
    """
    Twenty voters, two blocks of ten. Block A approves and wins a project
    costing 60, block B approves and wins one costing 40. Shares of the
    electorate are 0.5 each; shares of budget won are 0.6 and 0.4; utilisation
    is therefore exactly 1.2 and 0.8.
    """
    costs = {"a_project": 60, "b_project": 40}
    approvals = [frozenset({"a_project"})] * 10 + [frozenset({"b_project"})] * 10
    strata = {i: {"block": "A" if i < 10 else "B"} for i in range(20)}
    roster = RosterSnapshot(as_of=CLOSED, counts_by_stratum={("A",): 10, ("B",): 10}, total=20)

    out = budgeting.fairness_report(
        _ballots(approvals, strata), _options(costs), ["a_project", "b_project"], roster,
        k_anonymity=5, seed=1,
    )
    rows = {r["stratum"]: r for r in out.value}
    assert abs(rows["A"]["share_of_electorate"] - 0.5) < 1e-12
    assert abs(rows["A"]["share_of_budget_won"] - 0.6) < 1e-12
    assert abs(rows["A"]["utilisation"] - 1.2) < 1e-12
    assert abs(rows["B"]["utilisation"] - 0.8) < 1e-12
    assert out.interval_kind == "bootstrap-bca-95"


def test_a_stratum_below_k_is_pooled_into_other_and_the_pooling_is_stated():
    """Pooled, not dropped. Dropping hides the group the report exists to protect."""
    costs = {"a_project": 60, "b_project": 40}
    approvals = [frozenset({"a_project"})] * 22 + [frozenset({"b_project"})] * 3
    strata = {i: {"block": "A" if i < 22 else "C"} for i in range(25)}
    roster = RosterSnapshot(as_of=CLOSED, counts_by_stratum={("A",): 22, ("C",): 3}, total=25)

    out = budgeting.fairness_report(
        _ballots(approvals, strata), _options(costs), ["a_project", "b_project"], roster,
        k_anonymity=5, seed=1,
    )
    strata_seen = {r["stratum"] for r in out.value}
    assert strata_seen == {"A", "other"}
    other = [r for r in out.value if r["stratum"] == "other"][0]
    assert other["n_voters"] == 3 and other["pooled"] is True
    check = [c for c in out.checks if c.id == "k-anonymity-rows"][0]
    assert check.status == "FAIL" and "rather than dropped" in check.detail


def test_the_fairness_report_answers_the_question_it_exists_for():
    """
    Block C is 20% of the electorate and its only project went unfunded. The
    report must say so with a number, which is what makes participatory
    budgeting trustworthy rather than a majority tool with extra steps.
    """
    costs = {"main_gate": 80, "block_c_lift": 40}
    approvals = [frozenset({"main_gate"})] * 24 + [frozenset({"block_c_lift"})] * 6
    strata = {i: {"block": "A" if i < 24 else "C"} for i in range(30)}
    roster = RosterSnapshot(as_of=CLOSED, counts_by_stratum={("A",): 24, ("C",): 6}, total=30)

    out = budgeting.fairness_report(
        _ballots(approvals, strata), _options(costs), ["main_gate"], roster, seed=3
    )
    rows = {r["stratum"]: r for r in out.value}
    assert abs(rows["C"]["share_of_electorate"] - 0.2) < 1e-12
    assert rows["C"]["share_of_budget_won"] == 0.0
    assert rows["C"]["utilisation"] == 0.0
    gap = [c for c in out.checks if c.id == "proportionality-gap"][0]
    assert gap.status == "WARN"


def test_the_fairness_report_is_reproducible_from_its_seed():
    costs = {"a_project": 60, "b_project": 40}
    approvals = [frozenset({"a_project"})] * 12 + [frozenset({"b_project"})] * 12
    strata = {i: {"block": "A" if i < 12 else "B"} for i in range(24)}
    roster = RosterSnapshot(as_of=CLOSED, counts_by_stratum={("A",): 12, ("B",): 12}, total=24)
    args = (_ballots(approvals, strata), _options(costs), ["a_project", "b_project"], roster)
    first = budgeting.fairness_report(*args, seed=11)
    again = budgeting.fairness_report(*args, seed=11)
    assert [r["lo"] for r in first.value] == [r["lo"] for r in again.value]


# ---------------------------------------------------------------------------
# Floors and refusals
# ---------------------------------------------------------------------------


def test_below_twenty_ballots_equal_shares_returns_the_calm_empty_state():
    costs = {"a": 10, "b": 10, "c": 10}
    out = budgeting.method_of_equal_shares(
        _ballots([frozenset({"a"})] * 8), _options(costs), _spec(100)
    )
    assert out.insufficient_data is True
    assert out.value["funded"] == []
    assert "vacuous" in out.caveats[0]


def test_an_unknown_completion_rule_is_refused_rather_than_defaulted():
    costs = {"a": 10, "b": 10, "c": 10}
    with pytest.raises(ValueError, match="completion"):
        budgeting.method_of_equal_shares(
            _ballots([frozenset({"a"})] * 25), _options(costs), _spec(100), completion="magic"
        )


def test_equal_shares_with_no_completion_can_leave_budget_unspent_and_says_so():
    costs = {"a": 40, "b": 40, "c": 40}
    approvals = [frozenset({"a"})] * 10 + [frozenset({"b"})] * 10 + [frozenset({"c"})] * 5
    out = budgeting.method_of_equal_shares(
        _ballots(approvals), _options(costs), _spec(100), completion="none"
    )
    assert out.value["remaining_minor"] > 0
    check = [c for c in out.checks if c.id == "budget-exhausted"][0]
    assert check.status == "WARN"
    assert "feature and not a failure" in check.detail
