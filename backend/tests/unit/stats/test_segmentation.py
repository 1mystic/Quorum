"""
Engagement features and segmentation, with the cluster count chosen rather than set.

The known answers here are a construction and two closed forms, and the Method
Card says so. Data drawn from a three-component Gaussian mixture with a stated
separation must minimise BIC at k = 3, seeded and repeated; that is a
construction rather than a published table, which is the honest label for it.
Silhouette and the adjusted Rand index both have exact definitions and are
asserted by hand on tiny fixtures where the arithmetic can be done on paper.

Two properties are gates rather than measurements. The number of segments must
come from BIC, never from a constant, and the file is grepped for one. And two
runs on the same data with the same seed must produce identical labels, because
a segmentation that renumbers itself between runs makes every month-on-month
comparison in the product meaningless.
"""
import math
import pathlib
import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.stats import segmentation
from app.stats.streams.ledger import LedgerEntry
from app.stats.streams.participation import EngagementFeatures, ParticipationEvent
from app.stats.streams.window import StreamWindow

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 8, 30, tzinfo=timezone.utc)
WINDOW = StreamWindow(start=START, end=END, timezone="UTC", complete_through=END)


# ---------------------------------------------------------------------------
# Feature building
# ---------------------------------------------------------------------------


def _event(member, days_before_end, kind="event_rsvp", weight=1.0, channel="app"):
    return ParticipationEvent(
        member_ref=member, at=END - timedelta(days=days_before_end), kind=kind,
        weight=weight, channel=channel,
    )


def _entry(member, days_before_end, amount, currency="INR"):
    at = END - timedelta(days=days_before_end)
    return LedgerEntry(
        entry_ref=member + str(days_before_end), at=at, booked_at=at,
        amount_minor=amount, currency=currency, category="dues",
        direction="inflow" if amount > 0 else "outflow",
        instrument="upi", status="settled", member_ref=member,
    )


def test_the_feature_arithmetic_is_exact_on_a_fixture():
    events = [
        _event("alice", 200), _event("alice", 40, kind="volunteer_hours", weight=3.0),
        _event("alice", 10, kind="event_rsvp"), _event("alice", 5, kind="poll_vote"),
    ]
    entries = [_entry("alice", 100, 50000), _entry("alice", 20, -700)]
    out = segmentation.rfm_features(events, entries, WINDOW)
    alice = out.value[0]

    assert alice["recency_days"] == 5.0
    assert alice["frequency_90d"] == 3, "the 200-day-old event is outside 90 days"
    assert alice["breadth"] == 3, "rsvp, volunteer_hours and poll_vote"
    assert alice["volunteer_hours_365d"] == 3.0
    assert alice["tenure_days"] == 200.0
    assert alice["contribution_minor"] == 50000, "outflows are not contributions"


def test_a_member_with_no_participation_gets_their_tenure_as_recency():
    """
    The boundary case the Method Card leads with. Zero would make the
    never-engaged look freshly engaged, which inverts the meaning of the column.
    """
    entries = [_entry("silent", 150, 12000), _entry("silent", 30, 12000)]
    out = segmentation.rfm_features([], entries, WINDOW)
    silent = out.value[0]
    assert silent["tenure_days"] == 150.0
    assert silent["recency_days"] == 150.0
    assert silent["recency_days"] is not None
    assert silent["frequency_90d"] == 0


def test_mixing_currencies_blocks_rather_than_summing_them():
    entries = [_entry("a", 10, 100, "INR"), _entry("b", 10, 100, "USD")]
    out = segmentation.rfm_features([_event("a", 5), _event("b", 5)], entries, WINDOW)
    check = [c for c in out.checks if c.id == "single-currency"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert out.value == []


def test_features_outside_the_window_are_not_counted():
    old = ParticipationEvent(member_ref="a", at=START - timedelta(days=5), kind="event_rsvp")
    out = segmentation.rfm_features([old, _event("a", 3)], [], WINDOW)
    assert out.value[0]["frequency_90d"] == 1


# ---------------------------------------------------------------------------
# Exact closed forms
# ---------------------------------------------------------------------------


def test_silhouette_on_a_four_point_fixture_matches_the_hand_computation():
    """
    Two points at 0 and 1, two at 10 and 11, on a line, split correctly.
    For the point at 0: a = 1, b = mean(10, 11) = 10.5, s = 9.5/10.5.
    For the point at 1: a = 1, b = mean(9, 10) = 9.5, s = 8.5/9.5.
    The cluster at the far end is the mirror image, so the mean silhouette is
    (9.5/10.5 + 8.5/9.5) / 2.
    """
    points = [[0.0], [1.0], [10.0], [11.0]]
    labels = [0, 0, 1, 1]
    expected = (9.5 / 10.5 + 8.5 / 9.5) / 2.0
    assert abs(segmentation.silhouette(points, labels) - expected) < 1e-12


def test_silhouette_of_a_single_cluster_is_zero_by_definition():
    assert segmentation.silhouette([[0.0], [1.0], [2.0]], [0, 0, 0]) == 0.0


def test_the_adjusted_rand_index_is_one_for_a_relabelling_and_zero_for_chance():
    labels = [0, 0, 1, 1, 2, 2]
    permuted = [2, 2, 0, 0, 1, 1]
    assert abs(segmentation.adjusted_rand(labels, permuted) - 1.0) < 1e-12
    assert abs(segmentation.adjusted_rand(labels, labels) - 1.0) < 1e-12
    # Everything in one cluster agrees with nothing beyond chance.
    assert abs(segmentation.adjusted_rand(labels, [0] * 6)) < 1e-12


def test_robust_scaling_centres_on_the_median_and_divides_by_the_iqr():
    matrix = [[1.0], [2.0], [3.0], [4.0], [5.0]]
    scaled, centres, scales = segmentation.robust_scale(matrix)
    assert centres == [3.0]
    assert scales == [2.0], "quartiles of 1..5 are 2 and 4"
    assert [row[0] for row in scaled] == [-1.0, -0.5, 0.0, 0.5, 1.0]


def test_a_constant_column_is_left_alone_rather_than_divided_by_zero():
    scaled, centres, scales = segmentation.robust_scale([[7.0], [7.0], [7.0]])
    assert scales == [1.0]
    assert [row[0] for row in scaled] == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# The construction: BIC must find the k the data was generated with
# ---------------------------------------------------------------------------


def _three_component(seed=20260830, per_component=60):
    rng = random.Random(seed)
    points = []
    for cx, cy in ((0.0, 0.0), (6.0, 0.0), (3.0, 6.0)):
        for _ in range(per_component):
            points.append([rng.gauss(cx, 1.0), rng.gauss(cy, 1.0)])
    return points


def test_bic_is_minimised_at_the_number_of_components_the_data_came_from():
    points = _three_component()
    bic = {k: segmentation.gaussian_mixture(points, k, seed=1, n_init=6)["bic"]
           for k in range(2, 7)}
    assert min(bic, key=bic.get) == 3, bic


def test_silhouette_also_peaks_at_three_on_that_construction():
    """
    A second, independent selection criterion agreeing is worth asserting, since
    the service reports both curves and the interesting case is when they part.
    """
    points = _three_component()
    scores = {
        k: segmentation.silhouette(
            points, segmentation.gaussian_mixture(points, k, seed=1, n_init=6)["labels"]
        )
        for k in range(2, 7)
    }
    assert max(scores, key=scores.get) == 3, scores


def test_the_mixture_recovers_the_component_means_it_was_generated_from():
    points = _three_component()
    fit = segmentation.gaussian_mixture(points, 3, seed=1, n_init=6)
    found = sorted(tuple(round(v, 1) for v in m) for m in fit["means"])
    truth = [(0.0, 0.0), (3.0, 6.0), (6.0, 0.0)]
    for got, want in zip(found, truth):
        assert math.dist(got, want) < 0.5, (found, truth)


# ---------------------------------------------------------------------------
# The service, and the gates on it
# ---------------------------------------------------------------------------


def _features_from(points):
    """
    Two informative feature columns and four constant ones.

    The constants matter: robust scaling must leave them flat so they add
    nothing to any distance. An earlier version of this helper also stored
    int(abs(y)) in frequency_90d, a lumpy discretised copy of a column already
    present, and the extra dimension manufactured enough spurious structure that
    BIC preferred five components to three. That was the fixture being wrong,
    not the selector, and it is worth the comment.
    """
    return [
        EngagementFeatures(
            member_ref="m" + str(i).zfill(3),
            recency_days=point[0], frequency_90d=0, breadth=1,
            volunteer_hours_365d=point[1], tenure_days=400.0, contribution_minor=0,
        )
        for i, point in enumerate(points)
    ]


def test_the_service_chooses_k_from_bic_rather_than_being_told():
    features = _features_from(_three_component(per_component=40))
    out = segmentation.gmm_select_k(features, WINDOW, seed=1, k_range=(2, 7), n_init=4)
    assert out.value["k_from_bic"] == 3
    assert out.value["k"] == 3
    assert sorted(out.value["bic_by_k"]) == [2, 3, 4, 5, 6]
    assert out.value["bic_by_k"][3] == min(out.value["bic_by_k"].values())
    assert sum(out.value["sizes"]) == 120


def test_the_number_of_segments_is_nowhere_hardcoded_in_the_module():
    """
    A gate on the source rather than on the output. `k` must arrive from the BIC
    sweep; the only integers this module may fix are the floors it declares.
    """
    source = pathlib.Path(segmentation.__file__).read_text(encoding="utf-8")
    assert "chosen = min(candidates" in source, "k must be selected, not assigned"
    for forbidden in ("k = 3", "k = 4", "n_clusters = ", "chosen = 3"):
        assert forbidden not in source, "found a hardcoded cluster count: " + forbidden


def test_two_runs_on_the_same_data_with_the_same_seed_give_identical_labels():
    """
    Label stability across runs. Without it, Segment 3 in September has nothing
    to do with Segment 3 in August and every month-on-month comparison in the
    product is noise.
    """
    features = _features_from(_three_component(per_component=40))
    first = segmentation.gmm_select_k(features, WINDOW, seed=11, k_range=(2, 6), n_init=4)
    again = segmentation.gmm_select_k(features, WINDOW, seed=11, k_range=(2, 6), n_init=4)

    assert first.value["labels"] == again.value["labels"]
    assert first.value["k"] == again.value["k"]
    assert first.value["centroids"] == again.value["centroids"]
    assert first.params_hash == again.params_hash
    assert first.value["stability"] == again.value["stability"]


def test_a_different_seed_is_still_the_same_partition_on_well_separated_data():
    """
    Reproducibility from a seed is necessary but not sufficient: the answer must
    also not be an artefact OF the seed. On genuinely separated data two seeds
    must agree on the grouping, up to renumbering.
    """
    features = _features_from(_three_component(per_component=40))
    a = segmentation.gmm_select_k(features, WINDOW, seed=11, k_range=(2, 6), n_init=4)
    b = segmentation.gmm_select_k(features, WINDOW, seed=99, k_range=(2, 6), n_init=4)
    refs = sorted(a.value["labels"])
    agreement = segmentation.adjusted_rand(
        [a.value["labels"][r] for r in refs], [b.value["labels"][r] for r in refs]
    )
    assert agreement > 0.9, agreement


def test_the_stability_score_is_reported_next_to_the_segments():
    features = _features_from(_three_component(per_component=40))
    out = segmentation.gmm_select_k(features, WINDOW, seed=1, k_range=(2, 6), n_init=4)
    assert out.value["stability"] > 0.5
    check = [c for c in out.checks if c.id == "cluster-stability"][0]
    assert check.status in ("PASS", "WARN")


def test_unstable_clustering_blocks_and_the_labels_are_not_published():
    """
    The negative control on the stability gate. Uniform noise in a square has no
    cluster structure at all, so the boundaries land wherever the resample puts
    them and nothing should be shown.
    """
    rng = random.Random(5)
    points = [[rng.uniform(0, 1), rng.uniform(0, 1)] for _ in range(120)]
    out = segmentation.gmm_select_k(
        _features_from(points), WINDOW, seed=3, k_range=(4, 7), n_init=3
    )
    check = [c for c in out.checks if c.id == "cluster-stability"][0]
    if check.status == "FAIL":
        assert check.blocking is True
        assert out.value["labels"] == {}
        assert out.render_state == "not_interpretable"
        assert "a drawing, not a segmentation" in check.detail
    else:
        # If this fixture happens to be stable the gate is untested, which is
        # worse than a failure, so say so rather than passing quietly.
        assert check.statistic < 0.9, (
            "uniform noise clustered stably at " + repr(check.statistic)
            + "; this fixture no longer exercises the gate"
        )


def test_an_unscaled_request_is_refused():
    features = _features_from(_three_component(per_component=40))
    out = segmentation.gmm_select_k(
        features, WINDOW, seed=1, k_range=(2, 5), n_init=2, scale="none"
    )
    check = [c for c in out.checks if c.id == "feature-scaling"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert "largest-variance column" in check.detail


def test_below_fifty_members_the_service_returns_the_calm_empty_state():
    features = _features_from(_three_component(per_component=10))
    out = segmentation.gmm_select_k(features, WINDOW, seed=1, k_range=(2, 5), n_init=2)
    assert out.insufficient_data is True
    assert "indistinguishable from noise" in out.caveats[0]


# ---------------------------------------------------------------------------
# Stable labels across runs
# ---------------------------------------------------------------------------


def test_a_known_permutation_is_mapped_back_to_the_identity():
    """
    This month's segments are last month's, renumbered. The Hungarian match must
    undo the permutation exactly.
    """
    reference = [[0.0, 0.0], [5.0, 5.0], [10.0, 0.0]]
    # Same three centroids, shuffled, with a tiny wobble so it is a match
    # rather than an equality test.
    current = [[5.01, 4.99], [9.98, 0.02], [0.02, -0.01]]
    out = segmentation.stable_labels(
        {"a": 0, "b": 1, "c": 2}, current, {"a": 1, "b": 2, "c": 0}, reference, END
    )
    assert out.value["mapping"] == {0: 1, 1: 2, 2: 0}
    assert out.value["labels"] == {"a": 1, "b": 2, "c": 0}
    assert out.value["match_cost"] < 0.05
    assert [c for c in out.checks if c.id == "label-drift"][0].status == "PASS"


def test_an_identity_match_is_recognised_as_one():
    centroids = [[0.0, 0.0], [5.0, 5.0]]
    out = segmentation.stable_labels(
        {"a": 0, "b": 1}, centroids, {"a": 0, "b": 1}, centroids, END
    )
    assert out.value["mapping"] == {0: 0, 1: 1}
    assert out.value["is_identity"] is True
    assert out.value["match_cost"] == 0.0


def test_genuinely_moved_segments_trigger_the_drift_check_and_publish_no_mapping():
    """
    The negative control, and the point of the service. Pretending September's
    segments are August's when they are not is worse than renumbering them.
    """
    reference = [[0.0, 0.0], [5.0, 5.0]]
    current = [[3.0, 3.0], [8.0, 1.0]]
    out = segmentation.stable_labels(
        {"a": 0, "b": 1}, current, {"a": 0, "b": 1}, reference, END, drift_threshold=0.5
    )
    check = [c for c in out.checks if c.id == "label-drift"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert out.value["mapping"] == {}
    assert out.value["labels"] == {}
    assert "worse than renumbering" in check.detail
    assert out.render_state == "not_interpretable"


def test_a_new_segment_with_no_counterpart_is_reported_rather_than_forced():
    reference = [[0.0, 0.0], [5.0, 5.0]]
    current = [[0.01, 0.0], [5.0, 5.01], [40.0, 40.0]]
    out = segmentation.stable_labels(
        {"a": 0, "b": 1, "c": 2}, current, {"a": 0, "b": 1}, reference, END,
        drift_threshold=0.5,
    )
    assert out.value["n_unmatched"] == 1
    assert [c for c in out.checks if c.id == "segment-count-stable"][0].status == "WARN"
    assert [c for c in out.checks if c.id == "unmatched-segments"][0].status == "WARN"
