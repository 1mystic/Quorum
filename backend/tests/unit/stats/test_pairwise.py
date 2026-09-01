"""
Paired comparisons, checked against theorems rather than against another library.

Three kinds of ground truth are used here.

1. EXACT ARITHMETIC. Elo's update is a closed-form expression, so each step is
   asserted by hand, and total rating is conserved to the last bit.
2. ANALYTIC IDENTITIES. On a balanced round robin the fitted abilities must be a
   monotone function of win counts; the fixed point of the Elo recursion against a
   constant opponent equals the Bradley-Terry ability difference implied by the
   observed win rate; and Ford's condition says exactly when a finite maximum
   likelihood estimate exists at all.
3. RECOVERY. Comparisons simulated from known abilities at a fixed seed must
   return those abilities, and the profile intervals must cover them.

The catalog names the BradleyTerry2 package's printed worked examples as a fourth
ground truth. That package is not vendored here and there is no network access in
this environment, so it is NOT asserted against, and the Method Card has been
corrected to say what is asserted instead. Claiming a known answer that nothing
checks is worse than claiming none.
"""
import itertools
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.stats import pairwise
from app.stats.contracts import Evidence
from app.stats.streams.derived import PairwiseResult

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _result(winner, loser, index, *, drawn=False, first=None):
    return PairwiseResult(
        winner_ref=winner,
        loser_ref=loser,
        at=T0 + timedelta(hours=index),
        drawn=drawn,
        first_position_ref=first,
    )


def _check(evidence: Evidence, check_id: str):
    for c in evidence.checks:
        if c.id == check_id:
            return c
    raise AssertionError(check_id + " is not among " + repr([c.id for c in evidence.checks]))


def _simulated_ladder(abilities, *, games=10, seed=2026, first_bias=0.0):
    """A round robin drawn from known Bradley-Terry abilities, at a fixed seed."""
    rng = random.Random(seed)
    rows = []
    index = 0
    for i, j in itertools.combinations(sorted(abilities), 2):
        for _ in range(games):
            # Which of the two is listed first is drawn independently of ability.
            # It has to be: if the alphabetically-first item were always listed
            # first, and the alphabet happened to run down the ladder, then an
            # order effect would be indistinguishable from ability and the model
            # would be right to absorb it.
            first = i if rng.random() < 0.5 else j
            bonus = first_bias if first == i else -first_bias
            probability = 1.0 / (1.0 + math.exp(-(abilities[i] - abilities[j] + bonus)))
            winner, loser = (i, j) if rng.random() < probability else (j, i)
            rows.append(_result(winner, loser, index, first=first))
            index += 1
    return rows


# ---------------------------------------------------------------------------
# Bradley-Terry: recovery and the interval
# ---------------------------------------------------------------------------


TRUE_ABILITIES = {"a": 1.2, "b": 0.7, "c": 0.2, "d": -0.3, "e": -0.8, "f": -1.4}


def test_bradley_terry_recovers_known_abilities_and_its_intervals_cover_them():
    out = pairwise.bradley_terry(_simulated_ladder(TRUE_ABILITIES))
    rows = {r["item_ref"]: r for r in out.value}

    assert out.n == 150
    assert out.render_state == "estimate"
    assert rows["a"]["ability"] == 0.0 and rows["a"]["reference"] == "a"

    covered = 0
    for item, ability in TRUE_ABILITIES.items():
        truth = ability - TRUE_ABILITIES["a"]
        assert rows[item]["ability"] == pytest.approx(truth, abs=0.6)
        if item == "a":
            continue
        assert rows[item]["lo"] is not None and rows[item]["hi"] is not None
        if rows[item]["lo"] <= truth <= rows[item]["hi"]:
            covered += 1
    assert covered == 5


def test_the_profile_interval_is_a_profile_and_not_a_flat_line():
    """
    A regression test for a real bug, named so it cannot come back.

    The first implementation pinned only the item being profiled and re-fitted
    everything else. Bradley-Terry is invariant to rescaling every ability at
    once, so that re-fit simply rescaled the rest and the profile log-likelihood
    came out EXACTLY FLAT: every interval was reported as None, which at least
    failed loudly, but the same mistake with a Wald fallback would have printed a
    confident interval of the wrong width. The profile must pin the reference as
    well as the item, which makes it an interval on the difference, which is the
    only quantity the model identifies.
    """
    rows = _simulated_ladder(TRUE_ABILITIES)
    triples = [(r.winner_ref, r.loser_ref, False, None, r.at) for r in rows]
    items = sorted(TRUE_ABILITIES)
    wins, counts = pairwise._tallies(triples, items)
    free = pairwise._mm_fit(items, wins, counts, penalizer=0.0)
    peak = pairwise._loglik(triples, free, penalizer=0.0)

    centre = math.log(free["b"]) - math.log(free["a"])
    one_pin = pairwise._mm_fit(items, wins, counts, penalizer=0.0, fixed={"b": centre - 1.0})
    two_pin = pairwise._mm_fit(
        items, wins, counts, penalizer=0.0, fixed={"a": 0.0, "b": centre - 1.0}
    )
    # Pinning one item constrains nothing at all.
    assert pairwise._loglik(triples, one_pin, penalizer=0.0) == pytest.approx(peak, abs=1e-6)
    # Pinning the reference too costs likelihood, which is what a profile is.
    assert peak - pairwise._loglik(triples, two_pin, penalizer=0.0) > 0.5


def test_a_wider_interval_belongs_to_the_item_with_fewer_comparisons():
    rows = _simulated_ladder(TRUE_ABILITIES, games=10)
    # One extra item that has played only a handful of games, against everyone,
    # so the graph stays connected and Ford's condition still holds.
    thin = ["a", "b", "c", "d", "e", "f"]
    for k, opponent in enumerate(thin):
        rows.append(_result("g", opponent, 900 + k) if k % 2 else _result(opponent, "g", 900 + k))
    out = pairwise.bradley_terry(rows)
    widths = {
        r["item_ref"]: (r["hi"] - r["lo"])
        for r in out.value
        if r["lo"] is not None and r["hi"] is not None and r["item_ref"] != r["reference"]
    }
    assert widths["g"] > max(w for ref, w in widths.items() if ref != "g")


def test_abilities_are_monotone_in_wins_on_a_balanced_round_robin():
    """
    An exact property, not an approximation: when every pair plays the same
    number of games, the fitted ability order must be the win-count order.
    """
    out = pairwise.bradley_terry(_simulated_ladder(TRUE_ABILITIES, games=12, seed=7))
    ranked = [r for r in out.value if r["ability"] is not None]
    for earlier, later in zip(ranked, ranked[1:]):
        assert earlier["ability"] >= later["ability"]
        assert earlier["wins"] >= later["wins"]


def test_the_fitted_abilities_satisfy_the_likelihood_equations_exactly():
    """
    The exact stationarity condition of the Bradley-Terry MLE, which is a theorem
    and needs no tolerance to speak of: for every item, the number of wins the
    fitted abilities PREDICT equals the number of wins actually observed,

        sum_j n_ij * p_i / (p_i + p_j) = w_i.

    Asserting the per-pair win rates instead would be wrong, and it is worth
    saying why: Bradley-Terry is a constrained model with one parameter per item,
    so it deliberately does not reproduce each pair's observed rate, and a test
    demanding that would be testing a saturated model this is not.
    """
    rows = _simulated_ladder(TRUE_ABILITIES, games=40, seed=5)
    out = pairwise.bradley_terry(rows)
    strength = {r["item_ref"]: math.exp(r["ability"]) for r in out.value}
    observed = {r["item_ref"]: r["wins"] for r in out.value}

    played = {}
    for r in rows:
        played.setdefault(r.winner_ref, {}).setdefault(r.loser_ref, 0)
        played.setdefault(r.loser_ref, {}).setdefault(r.winner_ref, 0)
        played[r.winner_ref][r.loser_ref] += 1
        played[r.loser_ref][r.winner_ref] += 1

    for item, opponents in played.items():
        predicted = sum(
            count * strength[item] / (strength[item] + strength[other])
            for other, count in opponents.items()
        )
        assert predicted == pytest.approx(observed[item], abs=1e-6)


# ---------------------------------------------------------------------------
# The blocking checks
# ---------------------------------------------------------------------------


def test_a_disconnected_comparison_graph_blocks_and_ranks_within_components_only():
    """
    Two leagues that never played each other. Every implementation that skips
    this check prints one ranking across both.
    """
    left = _simulated_ladder({"a": 1.0, "b": 0.4, "c": -0.5}, games=8, seed=11)
    right = _simulated_ladder({"x": 1.0, "y": 0.4, "z": -0.5}, games=8, seed=12)
    out = pairwise.bradley_terry(left + [_result(r.winner_ref, r.loser_ref, 500 + i)
                                          for i, r in enumerate(right)])
    check = _check(out, "connectivity")
    assert check.status == "FAIL" and check.blocking is True
    assert check.statistic == 2.0
    assert out.render_state == "not_interpretable"

    components = {r["item_ref"]: r["component"] for r in out.value}
    assert components["a"] == components["b"] == components["c"]
    assert components["x"] == components["y"] == components["z"]
    assert components["a"] != components["x"]
    # Each component has its own reference, because the two scales are unrelated.
    references = {r["reference"] for r in out.value}
    assert len(references) == 2


def test_a_perfectly_transitive_ladder_has_no_finite_abilities_and_says_so():
    """
    Ford's condition, and a correction to what the catalog asked for.

    The catalog's known answer says that on a perfectly transitive result set the
    fitted ORDERING must match exactly. It does, and it is asserted below. But
    the abilities themselves do not exist: when the stronger item wins every
    single game, no finite set of abilities maximises the likelihood, and any
    number printed for them is the optimiser's stopping rule rather than an
    estimate. The service reports the tier order, which the data determines, and
    withholds the numbers, which it does not.
    """
    order = ["a", "b", "c", "d", "e", "f"]
    rows = []
    index = 0
    for i, j in itertools.combinations(range(6), 2):
        for _ in range(4):
            rows.append(_result(order[i], order[j], index))
            index += 1
    out = pairwise.bradley_terry(rows)

    check = _check(out, "separation")
    assert check.status == "FAIL"
    assert check.statistic == 6.0
    assert "Ford's condition fails" in check.detail

    assert all(r["ability"] is None for r in out.value)
    assert [r["item_ref"] for r in out.value] == order       # the ordering IS delivered
    assert [r["tier"] for r in out.value] == [0, 1, 2, 3, 4, 5]
    assert _check(out, "connectivity").status == "PASS"      # connected, just separated


def test_one_undefeated_item_separates_only_itself():
    """The common case: everyone else is fitted normally, the undefeated item is not."""
    rows = _simulated_ladder({"b": 0.5, "c": 0.1, "d": -0.2, "e": -0.6}, games=10, seed=4)
    index = 800
    for opponent in ("b", "c", "d", "e"):
        for _ in range(4):
            rows.append(_result("a", opponent, index))
            index += 1
    out = pairwise.bradley_terry(rows)
    rows_by_ref = {r["item_ref"]: r for r in out.value}

    assert _check(out, "separation").status == "FAIL"
    assert rows_by_ref["a"]["ability"] is None
    assert "no finite ability" in rows_by_ref["a"]["label"]
    assert rows_by_ref["a"]["tier"] == 0
    assert rows_by_ref["a"]["wins"] == 16.0
    # The other four are one tier and are still fitted against each other.
    assert {rows_by_ref[i]["tier"] for i in ("b", "c", "d", "e")} == {1}
    assert all(rows_by_ref[i]["ability"] is not None for i in ("b", "c", "d", "e"))


def test_a_penalizer_buys_finite_numbers_and_the_check_says_who_paid():
    rows = _simulated_ladder({"b": 0.5, "c": 0.1, "d": -0.2, "e": -0.6}, games=10, seed=4)
    index = 800
    for opponent in ("b", "c", "d", "e"):
        for _ in range(4):
            rows.append(_result("a", opponent, index))
            index += 1
    out = pairwise.bradley_terry(rows, penalizer=1.0)
    check = _check(out, "separation")
    assert check.status == "WARN"
    assert "the penalty speaking, not the data" in check.detail
    assert all(r["ability"] is not None for r in out.value)


def test_a_cyclic_result_set_is_disclosed_rather_than_ranked_quietly():
    """
    The same disclosure discipline as a Condorcet cycle in the governance pack.
    Rock, paper and scissors have no one-dimensional strength.
    """
    rows = []
    index = 0
    cycle = [("a", "b"), ("b", "c"), ("c", "a"), ("d", "e"), ("e", "f"), ("f", "d"),
             ("a", "d"), ("b", "e"), ("c", "f"), ("d", "a"), ("e", "b"), ("f", "c")]
    for _ in range(4):
        for winner, loser in cycle:
            rows.append(_result(winner, loser, index))
            index += 1
    out = pairwise.bradley_terry(rows)
    check = _check(out, "transitivity")
    assert check.status == "WARN"
    assert check.statistic > 0.1
    assert "Condorcet cycle" in check.detail


def test_a_transitive_ladder_does_not_trip_the_cycle_disclosure():
    """The negative control. A check that always fires is not a check."""
    out = pairwise.bradley_terry(_simulated_ladder(TRUE_ABILITIES, games=20, seed=8))
    assert _check(out, "transitivity").status == "PASS"


def test_an_order_effect_is_measured_when_the_positions_are_recorded():
    """
    Being listed first should not predict winning once ability is accounted for.
    A fixture with a deliberate first-position advantage must be caught, and one
    without must not be.
    """
    biased = pairwise.bradley_terry(
        _simulated_ladder(TRUE_ABILITIES, games=30, seed=21, first_bias=1.2)
    )
    assert _check(biased, "home-advantage").status == "WARN"
    assert _check(biased, "home-advantage").p_value < 0.05

    clean = pairwise.bradley_terry(_simulated_ladder(TRUE_ABILITIES, games=30, seed=21))
    assert _check(clean, "home-advantage").status == "PASS"


def test_too_few_items_or_comparisons_is_insufficient_data():
    rows = _simulated_ladder({"a": 1.0, "b": 0.0, "c": -1.0}, games=4)
    out = pairwise.bradley_terry(rows)
    assert out.insufficient_data is True
    assert out.render_state == "not_enough_data"


def test_draws_are_carried_rather_than_dropped_or_counted_as_wins():
    rows = _simulated_ladder(TRUE_ABILITIES, games=8, seed=3)
    drawn = [_result("a", "f", 700 + i, drawn=True) for i in range(6)]
    out = pairwise.bradley_terry(rows + drawn)
    rows_by_ref = {r["item_ref"]: r for r in out.value}
    # Six draws add three wins to each side, not six to one and none to the other.
    plain = pairwise.bradley_terry(rows)
    plain_by_ref = {r["item_ref"]: r for r in plain.value}
    assert rows_by_ref["f"]["wins"] - plain_by_ref["f"]["wins"] == pytest.approx(3.0)
    assert rows_by_ref["a"]["wins"] - plain_by_ref["a"]["wins"] == pytest.approx(3.0)
    assert out.n == plain.n + 6


# ---------------------------------------------------------------------------
# Elo
# ---------------------------------------------------------------------------


def test_the_elo_update_is_the_textbook_arithmetic_to_the_last_decimal():
    """Two items at 1500, K = 32. The winner gains exactly 16 and the loser loses 16."""
    rows = [_result("a", "b", 0)]
    out = pairwise.elo_update(rows, k_factor=32.0, initial=1500.0)
    ratings = {r["item_ref"]: r["rating"] for r in out.value["ratings"]}
    assert ratings["a"] == pytest.approx(1516.0, abs=1e-12)
    assert ratings["b"] == pytest.approx(1484.0, abs=1e-12)
    step = out.value["trajectory"][0]
    assert step["expected_winner"] == pytest.approx(0.5, abs=1e-15)
    assert step["delta"] == pytest.approx(16.0, abs=1e-12)


def test_a_draw_between_equals_moves_nothing_and_a_draw_against_a_favourite_moves_a_lot():
    equal = pairwise.elo_update([_result("a", "b", 0, drawn=True)])
    assert equal.value["trajectory"][0]["delta"] == pytest.approx(0.0, abs=1e-12)

    rows = [_result("a", "b", i) for i in range(10)] + [_result("a", "b", 10, drawn=True)]
    out = pairwise.elo_update(rows)
    last = out.value["trajectory"][-1]
    # 'a' is far ahead by now, so a draw costs it rating.
    assert last["delta"] < -5.0


def test_total_rating_is_conserved_exactly():
    rng = random.Random(17)
    items = ["a", "b", "c", "d", "e"]
    rows = []
    for i in range(400):
        x, y = rng.sample(items, 2)
        rows.append(_result(x, y, i, drawn=(i % 7 == 0)))
    out = pairwise.elo_update(rows, k_factor=24.0, initial=1200.0)
    total = sum(r["rating"] for r in out.value["ratings"])
    assert total == pytest.approx(1200.0 * len(items), abs=1e-9)
    assert _check(out, "zero-sum").status == "PASS"


def test_the_elo_fixed_point_equals_the_bradley_terry_ability_difference():
    """
    The analytic identity that links the two services, and the catalog's own
    stated known answer for this one.

    Iterate the update against an opponent held at a constant rating and the
    rating converges to the point where the expected score equals the observed
    win rate w. At that point the Elo difference d satisfies
    1/(1 + 10^(-d/400)) = w, so d = 400 * log10(w / (1-w)); and the Bradley-Terry
    ability difference implied by the same win rate is log(w / (1-w)). The two
    are the same statement on two scales, related by ln(10)/400.

    The recursion is written here rather than in the service because the service
    is zero sum: it moves the opponent too, by construction, so a constant
    opponent is a property of the update rule and not of a real ladder.
    """
    for win_rate in (0.6, 0.75, 0.9):
        rating = 1500.0
        for _ in range(20000):
            rating += 4.0 * (win_rate - pairwise.elo_expected(rating, 1500.0))
        difference = rating - 1500.0

        expected_difference = 400.0 * math.log10(win_rate / (1.0 - win_rate))
        assert difference == pytest.approx(expected_difference, abs=1e-6)

        bradley_terry_difference = math.log(win_rate / (1.0 - win_rate))
        assert difference * math.log(10.0) / 400.0 == pytest.approx(
            bradley_terry_difference, abs=1e-9
        )


def test_elo_and_bradley_terry_agree_on_the_same_ladder():
    """Not an identity, but they must not disagree about who is strongest."""
    rows = _simulated_ladder(TRUE_ABILITIES, games=30, seed=13)
    bt = pairwise.bradley_terry(rows)
    elo = pairwise.elo_update(rows, k_factor=16.0)
    bt_order = [r["item_ref"] for r in bt.value]
    elo_order = [r["item_ref"] for r in elo.value["ratings"]]
    assert bt_order[0] == elo_order[0]
    assert bt_order[-1] == elo_order[-1]


def test_comparisons_out_of_time_order_are_sorted_and_the_reordering_is_disclosed():
    """Elo is path dependent, so the order it was applied in is part of the answer."""
    ordered = [_result("a", "b", i) for i in range(5)] + [_result("b", "a", 5 + i) for i in range(5)]
    shuffled = list(reversed(ordered))

    straight = pairwise.elo_update(ordered)
    reordered = pairwise.elo_update(shuffled)
    assert _check(straight, "time-ordered").status == "PASS"
    assert _check(reordered, "time-ordered").status == "WARN"
    # Sorted before updating, so the same events give the same ratings.
    assert [r["rating"] for r in straight.value["ratings"]] == [
        r["rating"] for r in reordered.value["ratings"]
    ]


def test_a_rating_from_a_handful_of_games_is_labelled_provisional():
    rows = [_result("a", "b", i) for i in range(20)] + [_result("c", "a", 100)]
    out = pairwise.elo_update(rows)
    by_ref = {r["item_ref"]: r for r in out.value["ratings"]}
    assert "provisional" in by_ref["c"]["label"]
    assert by_ref["a"]["label"] == ""
    assert _check(out, "thin-history").status == "WARN"


def test_elo_carries_no_interval_and_says_why():
    out = pairwise.elo_update([_result("a", "b", i) for i in range(12)])
    assert out.interval is None
    assert out.interval_kind == "none"
    assert any("Elo is a filter" in c for c in out.caveats)


def test_the_k_factor_is_in_the_params_hash():
    rows = [_result("a", "b", i) for i in range(12)]
    assert (
        pairwise.elo_update(rows, k_factor=16.0).params_hash
        != pairwise.elo_update(rows, k_factor=32.0).params_hash
    )


# ---------------------------------------------------------------------------
# Envelope hygiene
# ---------------------------------------------------------------------------


def test_both_services_return_an_envelope_with_a_method_and_a_hash():
    rows = _simulated_ladder(TRUE_ABILITIES, games=10)
    for evidence, method in (
        (pairwise.bradley_terry(rows), "pairwise.bradley_terry"),
        (pairwise.elo_update(rows), "pairwise.elo_update"),
    ):
        assert isinstance(evidence, Evidence)
        assert evidence.method == method
        assert evidence.params_hash
        assert evidence.as_of.tzinfo is not None
        assert evidence.checks


def test_bradley_terry_is_reproducible_on_the_same_input():
    rows = _simulated_ladder(TRUE_ABILITIES, games=10)
    assert pairwise.bradley_terry(rows).value == pairwise.bradley_terry(rows).value
