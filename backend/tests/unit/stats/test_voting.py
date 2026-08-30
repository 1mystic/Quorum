"""
Social choice against textbook cases, including a deliberate Condorcet cycle.

Three published fixtures carry this file.

The Tennessee state-capital example (Memphis 42, Nashville 26, Chattanooga 15,
Knoxville 17) is the standard worked case across the social-choice literature.
Its pairwise matrix is published and is asserted cell by cell, and Nashville is
its Condorcet winner.

The deliberate cycle, three voters with A>B>C, B>C>A, C>A>B, is the one that
matters and it is a hard requirement for shipping this pack. It must yield no
winner, a cycle naming all three options in order, and a Smith set of all three.

Schulze's own 45-voter, 5-candidate example carries the published strongest-path
matrix and the published final ranking E > A > C > B > D, asserted against the
whole path matrix rather than only the winner, because a wrong implementation
frequently gets the winner right by luck.
"""
from datetime import datetime, timezone

import pytest

from app.stats import voting
from app.stats.streams.decision import Ballot, DecisionOption, DecisionSpec
from app.stats.streams.member import RosterSnapshot

OPENED = datetime(2026, 6, 1, tzinfo=timezone.utc)
CLOSED = datetime(2026, 6, 15, tzinfo=timezone.utc)


def _spec(rule="schulze", **kwargs) -> DecisionSpec:
    return DecisionSpec(
        decision_ref="d1", kind=kwargs.pop("kind", "poll"), opened_at=OPENED,
        closed_at=CLOSED, declared_rule=rule, **kwargs,
    )


def _options(*refs) -> list[DecisionOption]:
    return [DecisionOption(option_ref=r, decision_ref="d1", label=r.title()) for r in refs]


def _ranked_ballots(groups, strata=None):
    """groups: iterable of (count, "a>b>c"). One Ballot per voter."""
    ballots = []
    index = 0
    for count, order in groups:
        tiers = tuple((part,) for part in order.split(">"))
        for _ in range(count):
            ballots.append(Ballot(
                ballot_ref="b" + str(index), decision_ref="d1",
                voter_ref="v" + str(index), cast_at=OPENED, ranking=tiers,
                strata=dict(strata or {}),
            ))
            index += 1
    return ballots


# ---------------------------------------------------------------------------
# Tennessee
# ---------------------------------------------------------------------------

TENNESSEE = (
    (42, "memphis>nashville>chattanooga>knoxville"),
    (26, "nashville>chattanooga>knoxville>memphis"),
    (15, "chattanooga>knoxville>nashville>memphis"),
    (17, "knoxville>chattanooga>nashville>memphis"),
)
TENNESSEE_OPTIONS = ("memphis", "nashville", "chattanooga", "knoxville")

# The published pairwise result. Read as: row beats column with this many votes.
TENNESSEE_PAIRWISE = {
    ("memphis", "nashville"): 42, ("nashville", "memphis"): 58,
    ("memphis", "chattanooga"): 42, ("chattanooga", "memphis"): 58,
    ("memphis", "knoxville"): 42, ("knoxville", "memphis"): 58,
    ("nashville", "chattanooga"): 68, ("chattanooga", "nashville"): 32,
    ("nashville", "knoxville"): 68, ("knoxville", "nashville"): 32,
    ("chattanooga", "knoxville"): 83, ("knoxville", "chattanooga"): 17,
}


def test_the_tennessee_pairwise_matrix_cell_by_cell():
    out = voting.pairwise_matrix(
        _ranked_ballots(TENNESSEE), _options(*TENNESSEE_OPTIONS), _spec()
    )
    refs = out.value["options"]
    matrix = out.value["matrix"]
    for (a, b), expected in TENNESSEE_PAIRWISE.items():
        assert matrix[refs.index(a)][refs.index(b)] == expected, (a, b)
    assert out.n == 100
    assert out.value["n_truncated"] == 0
    assert out.interval_kind == "none"


def test_nashville_is_the_tennessee_condorcet_winner_with_no_cycle():
    out = voting.condorcet_winner(
        _ranked_ballots(TENNESSEE), _options(*TENNESSEE_OPTIONS), _spec()
    )
    assert out.value["winner"] == "nashville"
    assert out.value["cycle"] is None
    assert out.value["smith_set"] == ["nashville"]
    cycle_check = [c for c in out.checks if c.id == "condorcet-cycle-present"][0]
    assert cycle_check.status == "PASS"


def test_tennessee_borda_agrees_with_condorcet_while_plurality_does_not():
    """
    The real sensitivity finding in the Tennessee example, and the reason it is
    the standard fixture: the FIRST-PREFERENCE winner is Memphis with 42%, while
    every rule that reads the whole ballot picks Nashville.

    Borda points, hand-computed on the 3/2/1/0 scale:
      Nashville   42*2 + 26*3 + 15*1 + 17*1 = 194
      Chattanooga 42*1 + 26*2 + 15*3 + 17*2 = 173
      Memphis     42*3                      = 126
      Knoxville          26*1 + 15*2 + 17*3 = 107
    """
    out = voting.borda(_ranked_ballots(TENNESSEE), _options(*TENNESSEE_OPTIONS), _spec())
    points = {row["option"]: row["points"] for row in out.value}
    assert points == {"nashville": 194.0, "chattanooga": 173.0,
                      "memphis": 126.0, "knoxville": 107.0}
    assert out.value[0]["option"] == "nashville"

    first_preferences = {"memphis": 42, "nashville": 26, "chattanooga": 15, "knoxville": 17}
    assert max(first_preferences, key=first_preferences.get) == "memphis"


def test_tennessee_approval_under_a_declared_top_two_rule():
    """
    The Tennessee case publishes rankings, not approval sets, so an approval
    result for it only exists under a stated derivation. Here every voter
    approves their top two, which is stated in the test rather than presented as
    a published figure: Memphis 42, Nashville 68, Chattanooga 58, Knoxville 32.
    """
    ballots = []
    index = 0
    for count, order in TENNESSEE:
        top_two = frozenset(order.split(">")[:2])
        for _ in range(count):
            ballots.append(Ballot(
                ballot_ref="b" + str(index), decision_ref="d1", voter_ref="v" + str(index),
                cast_at=OPENED, approvals=top_two,
            ))
            index += 1
    out = voting.approval(ballots, _options(*TENNESSEE_OPTIONS), _spec(rule="approval"))
    counts = {row["option"]: row["approvals"] for row in out.value}
    assert counts == {"memphis": 42, "nashville": 68, "chattanooga": 58, "knoxville": 32}
    assert out.value[0]["option"] == "nashville"


# ---------------------------------------------------------------------------
# The deliberate cycle. docs/RULES.md section 7 makes this a shipping gate.
# ---------------------------------------------------------------------------

CYCLE = ((1, "a>b>c"), (1, "b>c>a"), (1, "c>a>b"))


def test_the_deliberate_condorcet_cycle_yields_no_winner():
    """
    Three voters: A>B>C, B>C>A, C>A>B. A beats B two to one, B beats C two to
    one, C beats A two to one. No option beats every other, and a tool that
    names a winner here is lying about what the ballots say.
    """
    out = voting.condorcet_winner(_ranked_ballots(CYCLE), _options("a", "b", "c"), _spec())

    refs = ["a", "b", "c"]
    matrix = voting.pairwise_counts(
        [{"a": 0, "b": 1, "c": 2}, {"b": 0, "c": 1, "a": 2}, {"c": 0, "a": 1, "b": 2}], refs
    )
    assert matrix[0][1] == 2 and matrix[1][0] == 1, "a beats b two to one"
    assert matrix[1][2] == 2 and matrix[2][1] == 1, "b beats c two to one"
    assert matrix[2][0] == 2 and matrix[0][2] == 1, "c beats a two to one"

    assert out.value["winner"] is None
    assert out.value["smith_set"] == ["a", "b", "c"]
    assert set(out.value["cycle"]) == {"a", "b", "c"}
    assert len(out.value["cycle"]) == 3


def test_the_cycle_is_disclosed_as_a_named_sequence_not_a_boolean():
    """
    "There is a cycle" is not a disclosure. The check has to say which options,
    in which order, because that is the sentence a committee can act on.
    """
    out = voting.condorcet_winner(_ranked_ballots(CYCLE), _options("a", "b", "c"), _spec())
    check = [c for c in out.checks if c.id == "condorcet-cycle-present"][0]
    assert check.status == "FAIL"
    assert check.blocking is False, "a cycle is a finding about the ballots, not a broken count"

    cycle = out.value["cycle"]
    # The detail spells the cycle out and closes the loop back to the start.
    for option in cycle:
        assert option in check.detail
    written = " beats ".join(cycle + [cycle[0]])
    assert written in check.detail, "the cycle must close back to where it started"
    assert "no Condorcet winner" in check.detail
    assert "completion rule" in check.detail

    # And the envelope is qualified, so no client renders it as a plain estimate.
    assert out.render_state == "qualified"


def test_schulze_resolves_the_cycle_but_labels_it_as_a_resolution():
    """
    Schulze does produce a winner on a cycle, which is what it is for. What it
    must not do is present that winner as a Condorcet winner. The distinction is
    the entire point of shipping both services.
    """
    out = voting.schulze(_ranked_ballots(CYCLE), _options("a", "b", "c"), _spec())
    assert out.value["winner"] is not None
    assert out.value["is_condorcet_winner"] is False
    assert out.value["cycle_disclosed"] is not None
    assert any("RESOLUTION OF A CYCLE" in c for c in out.caveats)
    assert [c for c in out.checks if c.id == "condorcet-cycle-present"][0].status == "FAIL"


def test_schulze_on_a_cycle_free_decision_claims_the_condorcet_winner():
    """The negative control: the label must not always say cycle."""
    out = voting.schulze(
        _ranked_ballots(TENNESSEE), _options(*TENNESSEE_OPTIONS), _spec()
    )
    assert out.value["winner"] == "nashville"
    assert out.value["is_condorcet_winner"] is True
    assert out.value["cycle_disclosed"] is None
    assert out.render_state == "estimate"


def test_a_four_option_cycle_names_the_shortest_cycle_not_the_whole_smith_set():
    """
    Smith set and cycle are different objects. A decision can have a large top
    group whose actual cycle is a triangle inside it, and the disclosure should
    be the triangle, which a person can hold in their head.
    """
    # a > b > c > a with d beaten by all three.
    groups = ((1, "a>b>c>d"), (1, "b>c>a>d"), (1, "c>a>b>d"))
    out = voting.condorcet_winner(
        _ranked_ballots(groups), _options("a", "b", "c", "d"), _spec()
    )
    assert out.value["winner"] is None
    assert out.value["smith_set"] == ["a", "b", "c"]
    assert len(out.value["cycle"]) == 3
    assert "d" not in out.value["cycle"]


# ---------------------------------------------------------------------------
# Schulze's published example
# ---------------------------------------------------------------------------

SCHULZE_45 = (
    (5, "a>c>b>e>d"),
    (5, "a>d>e>c>b"),
    (8, "b>e>d>a>c"),
    (3, "c>a>b>e>d"),
    (7, "c>a>e>b>d"),
    (2, "c>b>a>d>e"),
    (7, "d>c>e>b>a"),
    (8, "e>b>a>d>c"),
)
SCHULZE_LETTERS = ("a", "b", "c", "d", "e")

# Published pairwise matrix, d[row][column].
SCHULZE_D = [
    [0, 20, 26, 30, 22],
    [25, 0, 16, 33, 18],
    [19, 29, 0, 17, 24],
    [15, 12, 28, 0, 14],
    [23, 27, 21, 31, 0],
]

# Published strongest-path matrix, p[row][column].
SCHULZE_P = [
    [0, 28, 28, 30, 24],
    [25, 0, 28, 33, 24],
    [25, 29, 0, 29, 24],
    [25, 28, 28, 0, 24],
    [25, 28, 28, 31, 0],
]


def test_the_schulze_paper_example_reproduces_the_published_pairwise_matrix():
    out = voting.pairwise_matrix(
        _ranked_ballots(SCHULZE_45), _options(*SCHULZE_LETTERS), _spec()
    )
    assert out.n == 45
    assert out.value["matrix"] == SCHULZE_D


def test_the_schulze_paper_example_reproduces_the_published_path_matrix():
    """
    Asserted against the whole path matrix, not only the winner. A wrong widest
    path implementation lands on the right winner far more often than it lands
    on all twenty off-diagonal strengths.
    """
    out = voting.schulze(_ranked_ballots(SCHULZE_45), _options(*SCHULZE_LETTERS), _spec())
    assert out.value["strongest_paths"] == SCHULZE_P


def test_the_schulze_paper_example_reproduces_the_published_ranking():
    out = voting.schulze(_ranked_ballots(SCHULZE_45), _options(*SCHULZE_LETTERS), _spec())
    assert out.value["ranking"] == ["e", "a", "c", "b", "d"]
    assert out.value["winner"] == "e"
    # This example has no Condorcet winner: it is a genuine cycle example.
    assert out.value["is_condorcet_winner"] is False
    assert out.value["cycle_disclosed"] is not None


def test_the_schulze_tie_break_seed_is_disclosed_and_reproducible():
    ballots = _ranked_ballots(((1, "a>b"), (1, "b>a")))
    first = voting.schulze(ballots, _options("a", "b"), _spec(), tie_break_seed=7)
    again = voting.schulze(ballots, _options("a", "b"), _spec(), tie_break_seed=7)
    assert first.value["ranking"] == again.value["ranking"]
    tie = [c for c in first.checks if c.id == "schulze-tie"][0]
    assert tie.status == "WARN" and "seed 7" in tie.detail


# ---------------------------------------------------------------------------
# Borda, score and ballot handling
# ---------------------------------------------------------------------------


def test_borda_gives_a_tied_tier_half_a_point_each():
    """
    Two options tied on one ballot each score half. On a strict ballot the
    tournament rule reduces exactly to the classic m-1, m-2, ... scale, which
    the Tennessee test already pins.
    """
    ballots = [Ballot(ballot_ref="b0", decision_ref="d1", voter_ref="v0", cast_at=OPENED,
                      ranking=(("a", "b"), ("c",)))]
    out = voting.borda(ballots, _options("a", "b", "c"), _spec(rule="borda"))
    points = {row["option"]: row["points"] for row in out.value}
    assert points == {"a": 1.5, "b": 1.5, "c": 0.0}


def test_an_invalid_ballot_is_excluded_and_counted_never_repaired():
    ballots = _ranked_ballots(((3, "a>b"),))
    ballots.append(Ballot(ballot_ref="bad", decision_ref="d1", voter_ref="vx",
                          cast_at=OPENED, ranking=(("ghost",), ("a",))))
    out = voting.pairwise_matrix(ballots, _options("a", "b"), _spec())
    assert out.n == 3
    assert out.n_excluded == 1
    assert out.exclusion_reason
    assert [c for c in out.checks if c.id == "ballot-validity"][0].status == "WARN"


def test_the_unranked_policy_changes_the_matrix_and_the_params_hash():
    ballots = _ranked_ballots(((10, "a"), (4, "b>a")))
    last = voting.pairwise_matrix(ballots, _options("a", "b"), _spec(), unranked="last")
    dropped = voting.pairwise_matrix(ballots, _options("a", "b"), _spec(), unranked="excluded")
    refs = last.value["options"]
    i, j = refs.index("a"), refs.index("b")
    assert last.value["matrix"][i][j] == 10, "under 'last', a bullet vote for a beats b"
    assert dropped.value["matrix"][i][j] == 0, "under 'excluded', it expresses no preference"
    assert last.params_hash != dropped.params_hash


def test_score_reports_both_readings_of_an_unscored_option():
    ballots = [
        Ballot(ballot_ref="b0", decision_ref="d1", voter_ref="v0", cast_at=OPENED,
               scores={"a": 5, "b": 1}),
        Ballot(ballot_ref="b1", decision_ref="d1", voter_ref="v1", cast_at=OPENED,
               scores={"a": 5}),
    ]
    out = voting.score(ballots, _options("a", "b"), _spec(rule="score"))
    rows = {row["option"]: row for row in out.value}
    assert rows["b"]["mean_score_of_scorers"] == 1.0
    assert rows["b"]["mean_score_of_all_ballots"] == 0.5
    assert [c for c in out.checks if c.id == "partial-scoring"][0].status == "WARN"


# ---------------------------------------------------------------------------
# STV
# ---------------------------------------------------------------------------

# The standard food-election worked example: 20 ballots, 3 seats, Droop quota 6.
FOOD = (
    (4, "oranges"),
    (2, "pears>oranges"),
    (8, "chocolate>strawberries"),
    (4, "chocolate>sweets"),
    (1, "strawberries"),
    (1, "sweets"),
)
FOOD_OPTIONS = ("oranges", "pears", "chocolate", "strawberries", "sweets")


def test_the_stv_food_election_round_by_round():
    """
    Asserted round by round rather than on the final seats, because a wrong
    transfer rule lands on the right three winners far more often than it
    reproduces the intermediate counts.
    """
    out = voting.stv(
        _ranked_ballots(FOOD), _options(*FOOD_OPTIONS), _spec(rule="stv"),
        seats=3, tie_break_seed=1,
    )
    assert out.value["quota"] == 6, "Droop quota is floor(20/4) + 1"
    rounds = out.value["rounds"]

    first = rounds[0]["counts"]
    assert first == {"chocolate": 12.0, "oranges": 4.0, "pears": 2.0,
                     "strawberries": 1.0, "sweets": 1.0}
    assert rounds[0]["elected_this_round"] == ["chocolate"]
    assert rounds[0]["transfers"]["surplus"] == 6.0
    assert abs(rounds[0]["transfers"]["ratio"] - 0.5) < 1e-12

    # Chocolate's surplus of 6 splits 8:4, so 4 to strawberries and 2 to sweets.
    second = rounds[1]["counts"]
    assert abs(second["strawberries"] - 5.0) < 1e-9
    assert abs(second["sweets"] - 3.0) < 1e-9
    assert second["oranges"] == 4.0 and second["pears"] == 2.0
    assert rounds[1]["eliminated"] == "pears", "nobody reached quota, the lowest goes"

    # Pears' two votes carry to oranges, which reaches the quota exactly.
    third = rounds[2]["counts"]
    assert third["oranges"] == 6.0
    assert rounds[2]["elected_this_round"] == ["oranges"]

    assert out.value["elected"] == ["chocolate", "oranges", "strawberries"]


def test_the_last_stv_seat_is_labelled_when_it_is_filled_below_quota():
    out = voting.stv(
        _ranked_ballots(FOOD), _options(*FOOD_OPTIONS), _spec(rule="stv"),
        seats=3, tie_break_seed=1,
    )
    check = [c for c in out.checks if c.id == "quota-reached"][0]
    assert check.status == "WARN"
    assert "strawberries" in check.detail


def test_stv_reports_the_exhausted_ballot_share():
    out = voting.stv(
        _ranked_ballots(FOOD), _options(*FOOD_OPTIONS), _spec(rule="stv"),
        seats=3, tie_break_seed=1,
    )
    check = [c for c in out.checks if c.id == "exhausted-ballots"][0]
    assert check.statistic > 0.0, "bullet votes for oranges exhaust once oranges is elected"


def test_stv_is_reproducible_from_its_tie_break_seed():
    a = voting.stv(_ranked_ballots(FOOD), _options(*FOOD_OPTIONS), _spec(rule="stv"),
                   seats=3, tie_break_seed=99)
    b = voting.stv(_ranked_ballots(FOOD), _options(*FOOD_OPTIONS), _spec(rule="stv"),
                   seats=3, tie_break_seed=99)
    assert a.value["elected"] == b.value["elected"]
    assert a.params_hash == b.params_hash


def test_stv_refuses_meek_rather_than_running_gregory_under_its_name():
    with pytest.raises(ValueError, match="Meek"):
        voting.stv(_ranked_ballots(FOOD), _options(*FOOD_OPTIONS), _spec(rule="stv"),
                   seats=3, tie_break_seed=1, transfer="meek")


# ---------------------------------------------------------------------------
# Turnout and representativeness
# ---------------------------------------------------------------------------


def _turnout_case(voted_by_block, eligible_by_block):
    ballots = []
    index = 0
    for block, count in voted_by_block.items():
        for _ in range(count):
            ballots.append(Ballot(
                ballot_ref="b" + str(index), decision_ref="d1", voter_ref="v" + str(index),
                cast_at=OPENED, ranking=(("yes",),), strata={"block": block},
            ))
            index += 1
    eligible = {(block,): n for block, n in eligible_by_block.items()}
    roster = RosterSnapshot(as_of=CLOSED, counts_by_stratum=eligible,
                            total=sum(eligible_by_block.values()))
    return ballots, roster, eligible


def test_the_wilson_turnout_interval_matches_the_closed_form():
    """
    Wilson (1927) has a closed form, so the known answer is arithmetic rather
    than a table: for x successes in n trials the centre is (x + z^2/2)/(n + z^2)
    and the half-width is z*sqrt(x(n-x)/n + z^2/4)/(n + z^2).
    """
    import math

    ballots, roster, eligible = _turnout_case({"a": 60, "b": 60}, {"a": 100, "b": 100})
    out = voting.turnout_representativeness(
        ballots, _spec(eligible_strata=eligible), roster
    )
    x, n = 120, 200
    z = 1.959963984540054
    centre = (x + z * z / 2) / (n + z * z)
    half = z * math.sqrt(x * (n - x) / n + z * z / 4) / (n + z * z)
    assert abs(out.value["turnout"] - 0.6) < 1e-12
    assert abs(out.interval[0] - (centre - half)) < 1e-9
    assert abs(out.interval[1] - (centre + half)) < 1e-9


def test_the_representativeness_chi_square_is_hand_computable():
    """
    120 of 200 voted, so the expected count in each block of 100 is 60. Block A
    cast 90 and Block B cast 30: chi-square = 2 * 30^2 / 60 = 30.0 on 1 df.
    """
    ballots, roster, eligible = _turnout_case({"a": 90, "b": 30}, {"a": 100, "b": 100})
    out = voting.turnout_representativeness(
        ballots, _spec(eligible_strata=eligible), roster
    )
    assert abs(out.value["chi_square"] - 30.0) < 1e-9
    assert out.value["df"] == 1
    check = [c for c in out.checks if c.id == "strata-representative"][0]
    assert check.status == "FAIL"


def test_low_turnout_refuses_the_generalisation_while_still_showing_the_count():
    """
    The single most common misuse of a community poll. The tabulation stays,
    because it is correct; the sentence "the community wants X" is what goes.
    """
    ballots, roster, eligible = _turnout_case({"a": 40, "b": 5}, {"a": 300, "b": 300})
    out = voting.turnout_representativeness(
        ballots, _spec(eligible_strata=eligible), roster
    )
    assert abs(out.value["turnout"] - 45 / 600) < 1e-12
    check = [c for c in out.checks if c.id == "low-turnout-generalisation"][0]
    assert check.status == "FAIL"
    assert "must not be phrased as a community preference" in check.detail
    assert out.value["turnout"] is not None, "the tabulation is still shown"
    assert out.render_state == "qualified"


def test_a_stratum_row_below_k_is_emptied():
    ballots, roster, eligible = _turnout_case(
        {"a": 60, "b": 40, "c": 3}, {"a": 100, "b": 100, "c": 100}
    )
    out = voting.turnout_representativeness(
        ballots, _spec(eligible_strata=eligible), roster, k_anonymity=5
    )
    rows = {row["stratum"]: row for row in out.value["by_stratum"]}
    assert rows["c"]["suppressed"] is True
    assert rows["c"]["n_voted"] is None and rows["c"]["turnout"] is None
    assert rows["a"]["n_voted"] == 60
    check = [c for c in out.checks if c.id == "k-anonymity-cells"][0]
    assert check.status == "FAIL" and "no admin override" in check.detail


def test_a_missed_quorum_is_stated_without_deleting_the_tabulation():
    ballots, roster, eligible = _turnout_case({"a": 40}, {"a": 300})
    out = voting.turnout_representativeness(
        ballots, _spec(eligible_strata=eligible, quorum_rule="fraction:0.25"), roster
    )
    check = [c for c in out.checks if c.id == "quorum-met"][0]
    assert check.status == "FAIL"
    assert "still correct" in check.detail
    assert out.value["turnout"] is not None


def test_turnout_below_thirty_ballots_returns_the_calm_empty_state():
    ballots, roster, eligible = _turnout_case({"a": 12}, {"a": 100})
    out = voting.turnout_representativeness(
        ballots, _spec(eligible_strata=eligible), roster
    )
    assert out.insufficient_data is True
    assert out.render_state == "not_enough_data"
    assert out.value["turnout"] is None
    assert out.n == 12
