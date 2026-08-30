"""
Community structure against Zachary's karate club and against closed forms.

The karate club is the standard benchmark for exactly this and its answer is
known from outside the mathematics: Zachary recorded which faction each of the
34 members actually joined when the club split. Three published facts are
asserted, as the Method Card says: Louvain finds four communities, modularity
sits around 0.42, and the partition separates the instructor (node 0) from the
administrator (node 33) along the recorded faction line.

Betweenness gets a stronger treatment because it has exact analytic answers on
two graphs. On a path of n nodes the betweenness of node i is i(n-1-i); on a
star the centre is exactly 1 normalised and every leaf exactly 0. Both are
asserted to machine precision, and the karate values are asserted against the
published figures to five decimal places, which no coincidence survives.

The negative control is the one that makes the null check meaningful: a seeded
Erdos-Renyi graph has no community structure, Louvain partitions it anyway and
reports a respectable modularity for it, and the service must refuse to publish
that partition.
"""
import math
import pathlib
import random
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from app.stats import network
from app.stats.streams.participation import InteractionEdge
from app.stats.streams.window import StreamWindow

sys.path.insert(0, str(pathlib.Path(__file__).parent / "data"))
import karate  # noqa: E402

WINDOW = StreamWindow(
    start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    end=datetime(2026, 8, 30, tzinfo=timezone.utc),
    timezone="UTC",
    complete_through=datetime(2026, 8, 30, tzinfo=timezone.utc),
)


def _ref(node: int) -> str:
    return "m" + str(node).zfill(2)


def _karate_edges():
    return [
        InteractionEdge(a_ref=_ref(min(a, b)), b_ref=_ref(max(a, b)),
                        weight=1.0, basis="co_attendance")
        for a, b in karate.EDGES
    ]


# ---------------------------------------------------------------------------
# The fixture itself, before it is used for anything
# ---------------------------------------------------------------------------


def test_the_vendored_karate_club_matches_its_published_shape():
    """
    A transcription error in the edge list would look exactly like an algorithm
    result, so the fixture is checked against published facts first: 34 nodes,
    78 edges, and the degrees of the three hubs.
    """
    nodes, adjacency = network.build_graph(_karate_edges())
    assert len(nodes) == karate.N_NODES == 34
    assert sum(len(v) for v in adjacency.values()) // 2 == karate.N_EDGES == 78
    assert len(adjacency[_ref(0)]) == 16, "the instructor has 16 ties"
    assert len(adjacency[_ref(33)]) == 17, "the administrator has 17"
    assert len(adjacency[_ref(32)]) == 12
    assert len(karate.MR_HI_FACTION | karate.OFFICER_FACTION) == 34
    assert not (karate.MR_HI_FACTION & karate.OFFICER_FACTION)


# ---------------------------------------------------------------------------
# Modularity, from its definition
# ---------------------------------------------------------------------------


def test_modularity_matches_a_hand_computation_on_two_triangles():
    """
    Two disjoint triangles, six edges, 2m = 12. Each community has internal
    weight 6 (each of its three edges counted twice) and total degree 6, so
    Q = 2 * (6/12 - (6/12)^2) = 2 * (0.5 - 0.25) = 0.5.
    """
    edges = [("a", "b"), ("b", "c"), ("a", "c"), ("x", "y"), ("y", "z"), ("x", "z")]
    _, adjacency = network.build_graph(edges)
    partition = {"a": 0, "b": 0, "c": 0, "x": 1, "y": 1, "z": 1}
    assert abs(network.modularity(adjacency, partition) - 0.5) < 1e-12


def test_modularity_of_the_all_in_one_partition_is_exactly_zero():
    """Q = 1 - 1 = 0 for a single community, whatever the graph. A useful invariant."""
    _, adjacency = network.build_graph(_karate_edges())
    everyone = {node: 0 for node in adjacency}
    assert abs(network.modularity(adjacency, everyone)) < 1e-12


# ---------------------------------------------------------------------------
# Betweenness, against closed forms
# ---------------------------------------------------------------------------


def test_path_graph_betweenness_matches_the_closed_form():
    """On a path of n nodes the betweenness of node i is exactly i(n-1-i)."""
    n = 10
    edges = [(str(i).zfill(2), str(i + 1).zfill(2)) for i in range(n - 1)]
    _, adjacency = network.build_graph(edges)
    scores = network.betweenness(adjacency, normalised=False)
    for i in range(n):
        assert abs(scores[str(i).zfill(2)] - i * (n - 1 - i)) < 1e-12, i


def test_star_graph_betweenness_is_exactly_one_at_the_centre_and_zero_at_every_leaf():
    edges = [("centre", "leaf" + str(i)) for i in range(9)]
    _, adjacency = network.build_graph(edges)
    scores = network.betweenness(adjacency)
    assert abs(scores["centre"] - 1.0) < 1e-12
    for i in range(9):
        assert abs(scores["leaf" + str(i)]) < 1e-12


def test_the_published_karate_club_betweenness_values():
    """
    The published normalised betweenness of the karate club, to five decimals.
    Node 0 (the instructor) is highest and node 33 (the administrator) second,
    which is the documented result and is what makes this a benchmark rather
    than a fixture.
    """
    _, adjacency = network.build_graph(_karate_edges())
    scores = network.betweenness(adjacency)
    expected = {0: 0.43764, 33: 0.30407, 32: 0.14525, 2: 0.14366, 31: 0.13828}
    for node, published in expected.items():
        assert abs(scores[_ref(node)] - published) < 1e-5, (node, scores[_ref(node)])
    ordered = sorted(scores, key=lambda k: -scores[k])
    assert ordered[0] == _ref(0)
    assert ordered[1] == _ref(33)


def test_the_betweenness_service_returns_the_top_connectors_with_k_anonymity():
    out = network.betweenness_centrality(_karate_edges(), WINDOW, top_m=5, k_anonymity=3)
    assert out.value[0]["member_ref"] == _ref(0)
    assert abs(out.value[0]["betweenness"] - 0.43764) < 1e-5
    assert out.value[1]["member_ref"] == _ref(33)
    assert out.n == 34
    assert any("foreseeable harm" in c for c in out.caveats)


def test_a_thinly_connected_member_is_suppressed_from_the_connector_table():
    """
    Someone with two ties who happens to bridge two clusters would otherwise be
    named on the strength of two relationships.
    """
    out = network.betweenness_centrality(_karate_edges(), WINDOW, top_m=34, k_anonymity=10)
    suppressed = [r for r in out.value if r["suppressed"]]
    assert suppressed, "with k = 10 most of the club should be unnameable"
    assert all(r["member_ref"] is None and r["betweenness"] is None for r in suppressed)
    check = [c for c in out.checks if c.id == "k-anonymity-rows"][0]
    assert check.status == "FAIL"


# ---------------------------------------------------------------------------
# Louvain on the karate club
# ---------------------------------------------------------------------------


def test_louvain_finds_four_communities_on_the_karate_club():
    out = network.louvain_communities(_karate_edges(), WINDOW, seed=3, k_anonymity=3)
    assert out.value["n_communities"] == 4
    assert 0.41 < out.value["modularity"] < 0.43, out.value["modularity"]
    assert sum(out.value["sizes"]) == 34


def test_louvain_separates_the_instructor_from_the_administrator():
    """The recorded split. Nodes 0 and 33 led opposite factions and must not share a community."""
    out = network.louvain_communities(_karate_edges(), WINDOW, seed=3, k_anonymity=3)
    labels = out.value["labels"]
    assert labels[_ref(0)] != labels[_ref(33)]


def test_the_louvain_partition_refines_zacharys_recorded_factions():
    """
    The stronger published claim, and the reason this benchmark is worth having:
    the four communities are each almost entirely inside one recorded faction,
    so collapsing them onto the side their majority sits on reproduces the real
    split of the club to within a couple of members.
    """
    out = network.louvain_communities(_karate_edges(), WINDOW, seed=3, k_anonymity=3)
    labels = out.value["labels"]
    mr_hi = {_ref(n) for n in karate.MR_HI_FACTION}

    sides: dict[int, list[bool]] = {}
    for node, community in labels.items():
        sides.setdefault(community, []).append(node in mr_hi)

    for community, flags in sides.items():
        purity = max(sum(flags), len(flags) - sum(flags)) / len(flags)
        assert purity >= 0.9, "community " + str(community) + " straddles the split"

    correct = sum(
        max(sum(flags), len(flags) - sum(flags)) for flags in sides.values()
    )
    assert correct >= 32, "recovered " + str(correct) + " of 34 faction memberships"


def test_the_karate_club_partition_beats_a_degree_preserving_null():
    out = network.louvain_communities(_karate_edges(), WINDOW, seed=3, k_anonymity=3)
    check = [c for c in out.checks if c.id == "modularity-vs-null"][0]
    assert check.status == "PASS"
    assert out.value["z_score"] > 4.0, out.value["z_score"]
    assert out.value["null_modularity_mean"] < out.value["modularity"]


def test_the_karate_club_partition_is_stable_across_seeded_restarts():
    out = network.louvain_communities(_karate_edges(), WINDOW, seed=3, k_anonymity=3)
    assert out.value["stability"] > 0.7
    assert [c for c in out.checks if c.id == "partition-stability"][0].status == "PASS"


# ---------------------------------------------------------------------------
# The negative control. A gate tested one way is not a gate.
# ---------------------------------------------------------------------------


def test_a_random_graph_is_refused_rather_than_partitioned():
    """
    The documented pathology: Louvain returns a partition of an Erdos-Renyi
    graph without complaint, with a modularity that looks respectable, and a
    dashboard that prints it is showing fiction. The blocking check must fire
    and the communities must not be in the value at all.
    """
    rng = random.Random(20260830)
    nodes = ["n" + str(i).zfill(2) for i in range(60)]
    edges = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            if rng.random() < 0.10:
                edges.append(InteractionEdge(a_ref=a, b_ref=b, weight=1.0,
                                             basis="co_attendance"))
    assert len(edges) >= 60

    out = network.louvain_communities(edges, WINDOW, seed=5, k_anonymity=3)
    check = [c for c in out.checks if c.id == "modularity-vs-null"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert out.value["modularity"] > 0.15, (
        "the point is that the raw number looks plausible: " + repr(out.value["modularity"])
    )
    assert out.value["communities"] == [], "the partition must not be published"
    assert out.value["labels"] == {}
    assert out.render_state == "not_interpretable"


def test_a_graph_below_the_floor_returns_the_calm_empty_state():
    edges = [InteractionEdge(a_ref="a" + str(i), b_ref="b" + str(i), weight=1.0,
                             basis="co_attendance") for i in range(10)]
    out = network.louvain_communities(edges, WINDOW, seed=1)
    assert out.insufficient_data is True
    assert "documented pathology" in out.caveats[0]


def test_a_tiny_community_is_counted_but_not_listed():
    out = network.louvain_communities(_karate_edges(), WINDOW, seed=3, k_anonymity=8)
    hidden = [c for c in out.value["communities"] if c["suppressed"]]
    assert hidden, "with k = 8 the small karate communities cannot be named"
    assert all(c["members"] is None and c["size"] for c in hidden)
    assert [c for c in out.checks if c.id == "k-anonymity-communities"][0].status == "FAIL"


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def _roster(members):
    return [SimpleNamespace(member_ref=ref, strata=strata) for ref, strata in members]


def test_the_isolated_share_and_its_wilson_interval_are_exact():
    """
    40 members, 8 of whom appear in no edge. The share is exactly 0.2 and the
    interval is the Wilson closed form on 8 of 40.
    """
    connected = [("m" + str(i).zfill(2), {"block": "A"}) for i in range(32)]
    alone = [("z" + str(i).zfill(2), {"block": "A"}) for i in range(8)]
    edges = [
        InteractionEdge(a_ref=connected[i][0], b_ref=connected[i + 1][0], weight=1.0,
                        basis="co_attendance")
        for i in range(31)
    ]
    out = network.isolation_report(edges, _roster(connected + alone), WINDOW, k_anonymity=5)
    assert out.value["n_isolated"] == 8
    assert abs(out.value["isolated_share"] - 0.2) < 1e-12

    x, n, z = 8, 40, 1.959963984540054
    centre = (x + z * z / 2) / (n + z * z)
    half = z * math.sqrt(x * (n - x) / n + z * z / 4) / (n + z * z)
    assert abs(out.interval[0] - (centre - half)) < 1e-9
    assert abs(out.interval[1] - (centre + half)) < 1e-9


def test_the_isolation_report_cannot_name_an_individual():
    """
    The design decision, asserted as a property of the shape rather than trusted
    as a discipline. There is no key anywhere in the returned value that holds a
    member reference.
    """
    connected = [("m" + str(i).zfill(2), {"block": "A"}) for i in range(32)]
    alone = [("z" + str(i).zfill(2), {"block": "D"}) for i in range(8)]
    edges = [
        InteractionEdge(a_ref=connected[i][0], b_ref=connected[i + 1][0], weight=1.0,
                        basis="co_attendance")
        for i in range(31)
    ]
    out = network.isolation_report(edges, _roster(connected + alone), WINDOW, k_anonymity=5)

    rendered = repr(out.value)
    for ref, _ in alone:
        assert ref not in rendered, "an isolated member's reference reached the output"
    rows = {r["stratum"]: r for r in out.value["by_stratum"]}
    assert abs(rows["D"]["isolated_share"] - 1.0) < 1e-12
    assert rows["D"]["n"] == 8
    assert any("NEVER returned" in c for c in out.caveats)


def test_a_stratum_below_k_is_emptied_in_the_isolation_report():
    members = (
        [("m" + str(i).zfill(2), {"block": "A"}) for i in range(35)]
        + [("s" + str(i), {"block": "S"}) for i in range(3)]
    )
    edges = [
        InteractionEdge(a_ref="m00", b_ref="m" + str(i).zfill(2), weight=1.0,
                        basis="co_attendance")
        for i in range(1, 35)
    ]
    out = network.isolation_report(edges, _roster(members), WINDOW, k_anonymity=5)
    rows = {r["stratum"]: r for r in out.value["by_stratum"]}
    assert rows["S"]["suppressed"] is True
    assert rows["S"]["n_isolated"] is None and rows["S"]["isolated_share"] is None


def test_a_counts_only_roster_gives_the_aggregate_and_says_why_there_are_no_rows():
    """
    The honest degrade. A RosterSnapshot carries headcounts, not member records,
    so who is isolated cannot be matched to a stratum. The breakdown is empty
    rather than invented, and the check says which.
    """
    from app.stats.streams.member import RosterSnapshot

    edges = [
        InteractionEdge(a_ref="m00", b_ref="m" + str(i).zfill(2), weight=1.0,
                        basis="co_attendance")
        for i in range(1, 30)
    ]
    roster = RosterSnapshot(
        as_of=WINDOW.end, counts_by_stratum={("A",): 30, ("B",): 10}, total=40
    )
    out = network.isolation_report(edges, roster, WINDOW)
    assert out.value["n_isolated"] == 10
    assert out.value["by_stratum"] == []
    check = [c for c in out.checks if c.id == "strata-available"][0]
    assert check.status == "SKIPPED"
    assert "rather than guessed" in check.detail
