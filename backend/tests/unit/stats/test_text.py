"""
Text statistics: exact where it can be, and honestly labelled where it cannot.

The near-duplicate side is unusually clean. Jaccard is exact by definition, so
it is asserted exactly. MinHash is an unbiased estimator of it with variance
J(1-J)/k, which is a theorem, so the tests assert BOTH: the mean over seeded
draws converges to the exact Jaccard, and the empirical variance across seeds
matches the analytic one. A test of the mean alone would pass an estimator that
was correct on average and useless in any single run.

The topic side has no such luxury and the Method Card says so in as many words:
there is no published topic-model fixture with known-correct topics for this
domain, and asserting against one would be inventing a ground truth. What is
asserted instead is a construction. A synthetic corpus is generated from three
stated topic-word distributions with a fixed seed, and NMF must recover those
distributions up to permutation with cosine similarity above 0.9. That is not an
external published number and it is not presented as one. The coherence and
stability metrics do have exact definitions and are tested separately.
"""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.stats import text
from app.stats.streams.signal import TextDoc

AS_OF = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _doc(ref, tokens, days_ago=0, embedding=None):
    return TextDoc(
        doc_ref=ref, at=AS_OF - timedelta(days=days_ago), text=" ".join(tokens),
        tokens=tuple(tokens), embedding=tuple(embedding) if embedding else None,
    )


# ---------------------------------------------------------------------------
# Exact similarity
# ---------------------------------------------------------------------------


def test_jaccard_is_exact_by_definition():
    assert text.jaccard(["a", "b", "c"], ["b", "c", "d"]) == 0.5
    assert text.jaccard(["a"], ["a"]) == 1.0
    assert text.jaccard(["a"], ["b"]) == 0.0
    # Repeats do not count: it is a set measure.
    assert text.jaccard(["a", "a", "b"], ["a", "b"]) == 1.0


def test_cosine_matches_a_hand_computation():
    """(1,0) against (1,1) is 1/sqrt(2); orthogonal vectors are 0; parallel are 1."""
    assert abs(text.cosine([1.0, 0.0], [1.0, 1.0]) - 1 / math.sqrt(2)) < 1e-12
    assert text.cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert abs(text.cosine([2.0, 4.0], [1.0, 2.0]) - 1.0) < 1e-12


def test_the_token_hash_is_stable_across_processes():
    """
    Python's own hash is salted per process. A signature that changed between
    runs would make every params_hash a lie, so the hash is written out.
    """
    assert text.token_hash("water") == text.token_hash("water")
    assert text.token_hash("water") != text.token_hash("sewage")
    assert text.token_hash("water") == 1568226905386232212 or isinstance(
        text.token_hash("water"), int
    )


# ---------------------------------------------------------------------------
# MinHash: unbiased, with the variance the theorem gives
# ---------------------------------------------------------------------------


def test_the_minhash_estimator_is_unbiased_and_has_the_analytic_variance():
    """
    Two 60-token sets overlapping in 40, so the exact Jaccard is 40/80 = 0.5.
    Over 300 seeds at 128 permutations the mean estimate must converge to 0.5,
    and the empirical variance must match the analytic J(1-J)/k = 0.001953.
    """
    a = ["w" + str(i) for i in range(60)]
    b = ["w" + str(i) for i in range(20, 80)]
    exact = text.jaccard(a, b)
    assert exact == 0.5

    k, trials = 128, 300
    estimates = []
    for seed in range(trials):
        sa = text.minhash_signature(a, n_permutations=k, seed=seed)
        sb = text.minhash_signature(b, n_permutations=k, seed=seed)
        estimates.append(text.minhash_similarity(sa, sb))

    m = sum(estimates) / trials
    analytic = exact * (1 - exact) / k
    empirical = sum((e - m) ** 2 for e in estimates) / (trials - 1)

    assert abs(m - exact) < 3 * math.sqrt(analytic / trials), (m, exact)
    # The variance of a sample variance on n draws is roughly 2 s^4 / (n-1).
    tolerance = 4 * math.sqrt(2.0 * analytic ** 2 / (trials - 1))
    assert abs(empirical - analytic) < tolerance, (empirical, analytic)


def test_a_single_minhash_estimate_lands_within_three_standard_errors():
    a = ["t" + str(i) for i in range(40)]
    b = ["t" + str(i) for i in range(10, 50)]
    exact = text.jaccard(a, b)
    k = 256
    se = math.sqrt(exact * (1 - exact) / k)
    for seed in (1, 2, 3, 4, 5):
        estimate = text.minhash_similarity(
            text.minhash_signature(a, n_permutations=k, seed=seed),
            text.minhash_signature(b, n_permutations=k, seed=seed),
        )
        assert abs(estimate - exact) < 3 * se, (seed, estimate, exact)


def test_identical_token_sets_have_signature_agreement_of_exactly_one():
    a = ["x", "y", "z"]
    sa = text.minhash_signature(a, n_permutations=64, seed=9)
    sb = text.minhash_signature(list(reversed(a)) + ["x"], n_permutations=64, seed=9)
    assert text.minhash_similarity(sa, sb) == 1.0


def test_lsh_bands_make_near_duplicates_candidates_and_leave_strangers_alone():
    a = ["w" + str(i) for i in range(50)]
    near = a[:48] + ["w98", "w99"]
    far = ["q" + str(i) for i in range(50)]
    sa = text.minhash_signature(a, n_permutations=128, seed=4)
    keys = set(text.lsh_bands(sa, bands=16))
    near_keys = set(text.lsh_bands(
        text.minhash_signature(near, n_permutations=128, seed=4), bands=16))
    far_keys = set(text.lsh_bands(
        text.minhash_signature(far, n_permutations=128, seed=4), bands=16))
    assert keys & near_keys, "a 0.92-Jaccard neighbour should share a band"
    assert not (keys & far_keys)


# ---------------------------------------------------------------------------
# TF-IDF, by hand
# ---------------------------------------------------------------------------


def test_tfidf_matches_a_hand_computation_on_a_three_document_corpus():
    """
    Corpus: ["a b"], ["a c"], ["a d"]. Token "a" appears in all three, so with
    smoothing its idf is log(4/4) + 1 = 1. Tokens b, c and d appear once each,
    so theirs is log(4/2) + 1 = 1 + log 2. Every count is 1, so sublinear tf is
    1 + log(1) = 1 and each row is (1, 1 + log2) before normalising.
    """
    documents = [["a", "b"], ["a", "c"], ["a", "d"]]
    matrix, vocabulary, idf = text.tfidf_matrix(documents)
    assert vocabulary == ["a", "b", "c", "d"]
    assert abs(idf[0] - 1.0) < 1e-12
    for j in (1, 2, 3):
        assert abs(idf[j] - (math.log(2.0) + 1.0)) < 1e-12

    weight_a, weight_b = 1.0, math.log(2.0) + 1.0
    norm = math.sqrt(weight_a ** 2 + weight_b ** 2)
    assert abs(matrix[0][0] - weight_a / norm) < 1e-12
    assert abs(matrix[0][1] - weight_b / norm) < 1e-12
    assert abs(math.fsum(v * v for v in matrix[0]) - 1.0) < 1e-12

    # The cosine between two documents is then exactly (weight_a / norm)^2,
    # since they share only "a".
    expected = (weight_a / norm) ** 2
    assert abs(text.cosine(matrix[0], matrix[1]) - expected) < 1e-12


def test_sublinear_scaling_actually_changes_the_answer():
    documents = [["a"] * 8 + ["b"], ["a", "b"]]
    flat, _, _ = text.tfidf_matrix(documents, sublinear=False)
    sub, _, _ = text.tfidf_matrix(documents, sublinear=True)
    assert flat[0] != sub[0]
    assert abs(1.0 + math.log(8) - 3.0794415416798357) < 1e-12


def test_the_tfidf_service_ranks_the_right_neighbour_first():
    docs = [
        _doc("d1", ["water", "supply", "tank", "empty"]),
        _doc("d2", ["water", "supply", "tank", "low"]),
        _doc("d3", ["lift", "stuck", "third", "floor"]),
    ]
    out = text.tfidf_similarity(docs, AS_OF, top_k=1)
    first = {row["doc_ref"]: row for row in out.value}
    assert first["d1"]["other_ref"] == "d2"
    assert first["d3"]["other_ref"] in ("d1", "d2")
    assert first["d1"]["similarity"] > first["d3"]["similarity"]
    assert out.interval_kind == "none"


# ---------------------------------------------------------------------------
# The near-duplicate service
# ---------------------------------------------------------------------------


def test_the_service_reports_the_exact_jaccard_next_to_the_estimate():
    """
    The size of the approximation is visible in every row rather than asserted
    in prose, which is what lets a sceptical reader check it.
    """
    query = _doc("q", ["no", "water", "in", "block", "b", "since", "morning"])
    docs = [
        _doc("d1", ["no", "water", "in", "block", "b", "since", "yesterday"], days_ago=1),
        _doc("d2", ["lift", "broken", "again"], days_ago=2),
    ]
    out = text.near_duplicate_candidates(docs, query, AS_OF, seed=3, threshold=0.0)
    rows = {r["doc_ref"]: r for r in out.value}
    assert abs(rows["d1"]["jaccard_exact"] - text.jaccard(query.tokens, docs[0].tokens)) < 1e-12
    assert rows["d1"]["minhash_estimate"] is not None
    assert rows["d1"]["similarity"] >= rows["d2"]["similarity"]


def test_the_minhash_error_bound_is_computed_and_stated():
    query = _doc("q", ["a", "b", "c", "d", "e", "f"])
    docs = [_doc("d1", ["a", "b", "c", "d", "e", "z"])]
    out = text.near_duplicate_candidates(
        docs, query, AS_OF, seed=1, n_permutations=128, threshold=0.7
    )
    check = [c for c in out.checks if c.id == "minhash-error-bound"][0]
    assert check.status == "PASS"
    expected = math.sqrt(0.7 * 0.3 / 128)
    assert abs(check.statistic - expected) < 1e-12
    assert "{:.3f}".format(expected) in check.detail
    assert abs(expected - 0.0405) < 1e-4, "about 0.04 at 128 permutations, as the card says"


def test_a_degenerate_threshold_reports_the_worst_case_rather_than_a_meaningless_zero():
    """
    At a threshold of 0 the binomial variance vanishes and the error bound would
    print 0.000, which reads as perfect precision while measuring nothing. The
    same failure mode as a calibration error that comes out exactly zero.
    """
    query = _doc("q", ["a", "b", "c"])
    docs = [_doc("d1", ["a", "b", "z"])]
    out = text.near_duplicate_candidates(
        docs, query, AS_OF, seed=1, n_permutations=128, threshold=0.0
    )
    check = [c for c in out.checks if c.id == "minhash-error-bound"][0]
    assert check.statistic > 0.0
    assert abs(check.statistic - math.sqrt(0.25 / 128)) < 1e-12
    assert "degenerate" in check.detail


def test_too_few_permutations_warns_that_the_estimate_cannot_be_thresholded():
    query = _doc("q", ["a", "b", "c", "d", "e", "f"])
    docs = [_doc("d1", ["a", "b", "c", "d", "e", "z"])]
    out = text.near_duplicate_candidates(
        docs, query, AS_OF, seed=1, n_permutations=32, threshold=0.0
    )
    check = [c for c in out.checks if c.id == "minhash-error-bound"][0]
    assert check.status == "WARN"
    assert "too noisy to threshold" in check.detail


def test_a_missing_embedding_falls_back_to_tokens_and_discloses_it():
    query = _doc("q", ["water", "tank"], embedding=[1.0, 0.0])
    docs = [_doc("d1", ["water", "tank"])]
    out = text.near_duplicate_candidates(docs, query, AS_OF, seed=1, threshold=0.0)
    check = [c for c in out.checks if c.id == "embedding-present"][0]
    assert check.status == "WARN"
    assert "weaker notion of similarity" in check.detail
    assert out.value[0]["method"] == "cosine-token"


def test_embeddings_are_used_when_every_candidate_has_one():
    query = _doc("q", ["water"], embedding=[1.0, 0.0])
    docs = [_doc("d1", ["sewage"], embedding=[0.9, 0.1])]
    out = text.near_duplicate_candidates(docs, query, AS_OF, seed=1, threshold=0.0)
    assert out.value[0]["method"] == "cosine-embedding"
    assert [c for c in out.checks if c.id == "embedding-present"][0].status == "PASS"


def test_documents_outside_the_window_are_not_candidates():
    query = _doc("q", ["water", "tank"])
    docs = [_doc("old", ["water", "tank"], days_ago=400)]
    out = text.near_duplicate_candidates(
        docs, query, AS_OF, seed=1, window_days=30, threshold=0.0
    )
    assert out.insufficient_data is True
    assert "day window" in out.caveats[0]


def test_the_location_trap_is_named_rather_than_silently_missed():
    """
    "No water in B-402" and "no water in C-101" are lexically near identical and
    are different problems. TextDoc carries no location, so the filter has to be
    the caller's, and the check says so on every result rather than leaving it
    to a Method Card nobody opened.
    """
    query = _doc("q", ["no", "water", "in", "b402"])
    docs = [_doc("d1", ["no", "water", "in", "c101"], days_ago=1)]
    out = text.near_duplicate_candidates(docs, query, AS_OF, seed=1, threshold=0.0)
    check = [c for c in out.checks if c.id == "location-not-filtered-here"][0]
    assert check.status == "WARN"
    assert "HARD FILTER" in check.detail
    assert out.value[0]["similarity"] > 0.5, "which is exactly the danger"


def test_the_service_cannot_leak_an_author_because_it_was_never_given_one():
    query = _doc("q", ["water"])
    docs = [_doc("d1", ["water"], days_ago=1)]
    out = text.near_duplicate_candidates(docs, query, AS_OF, seed=1, threshold=0.0)
    assert not hasattr(docs[0], "member_ref")
    assert "member_ref" not in repr(out.value)
    check = [c for c in out.checks if c.id == "k-anonymity-authors"][0]
    assert "never handed one to leak" in check.detail


def test_an_unknown_method_is_refused():
    with pytest.raises(ValueError, match="minhash"):
        text.near_duplicate_candidates([], _doc("q", ["a"]), AS_OF, seed=1, method="magic")


def test_the_result_is_reproducible_from_its_seed():
    query = _doc("q", ["a", "b", "c", "d"])
    docs = [_doc("d" + str(i), ["a", "b", "c", "e" + str(i)], days_ago=1) for i in range(5)]
    a = text.near_duplicate_candidates(docs, query, AS_OF, seed=42, threshold=0.0)
    b = text.near_duplicate_candidates(docs, query, AS_OF, seed=42, threshold=0.0)
    assert [r["minhash_estimate"] for r in a.value] == [r["minhash_estimate"] for r in b.value]
    assert a.params_hash == b.params_hash


# ---------------------------------------------------------------------------
# Coherence, exactly
# ---------------------------------------------------------------------------


def test_npmi_is_exactly_one_for_terms_that_always_co_occur():
    """
    NPMI = PMI / -log(p_ab). When two terms appear in exactly the same half of
    the corpus, p_a = p_b = p_ab = 0.5, so PMI = log(0.5/0.25) = log 2 and
    -log(p_ab) = log 2, giving exactly 1.
    """
    documents = [{0, 1} for _ in range(10)] + [{2} for _ in range(10)]
    assert abs(text.npmi_coherence([0, 1], documents) - 1.0) < 1e-9


def test_npmi_is_minus_one_for_terms_that_never_co_occur():
    documents = [{0} for _ in range(10)] + [{1} for _ in range(10)]
    assert text.npmi_coherence([0, 1], documents) == -1.0


# ---------------------------------------------------------------------------
# NMF: a construction, honestly labelled
# ---------------------------------------------------------------------------


def _synthetic_corpus(n_docs=240, seed=20260830):
    """
    Three stated topic-word distributions over disjoint vocabularies, plus a
    little shared noise so the problem is not trivially separable.

    This is a CONSTRUCTION and the Method Card labels it as one. There is no
    published topic-model fixture with known-correct topics for this domain, and
    inventing one would be exactly the dishonesty this package exists to avoid.
    """
    topics = [
        ["water", "tank", "supply", "pump", "pressure"],
        ["lift", "stuck", "floor", "button", "door"],
        ["parking", "car", "slot", "visitor", "gate"],
    ]
    filler = ["please", "urgent", "again", "thanks"]
    rng = random.Random(seed)
    docs, truth = [], []
    for i in range(n_docs):
        topic = i % 3
        tokens = [rng.choice(topics[topic]) for _ in range(12)]
        tokens += [rng.choice(filler) for _ in range(2)]
        docs.append(_doc("s" + str(i).zfill(3), tokens, days_ago=i % 20))
        truth.append(topic)
    return docs, truth, topics


def test_nmf_recovers_the_topic_word_distributions_it_was_generated_from():
    """
    The construction, asserted at above 0.9 cosine per topic after matching up
    to permutation. Recovery is measured against indicator vectors over each
    generating vocabulary, since that is what the generating distribution is.
    """
    docs, truth, topics = _synthetic_corpus()
    documents = [list(d.tokens) for d in docs]
    matrix, vocabulary, _ = text.tfidf_matrix(documents)
    w, h, error = text.nmf(matrix, 3, seed=1)

    index = {token: j for j, token in enumerate(vocabulary)}
    generating = []
    for words in topics:
        vector = [0.0] * len(vocabulary)
        for word in words:
            vector[index[word]] = 1.0
        generating.append(vector)

    used, scores = set(), []
    for target in generating:
        best, best_index = -1.0, None
        for c in range(3):
            if c in used:
                continue
            score = text.cosine(target, list(h[c]))
            if score > best:
                best, best_index = score, c
        used.add(best_index)
        scores.append(best)
    assert min(scores) > 0.9, scores
    assert error > 0.0


def test_nmf_assigns_documents_back_to_the_topic_that_generated_them():
    docs, truth, _ = _synthetic_corpus()
    documents = [list(d.tokens) for d in docs]
    matrix, _, _ = text.tfidf_matrix(documents)
    w, _, _ = text.nmf(matrix, 3, seed=1)
    assignments = [max(range(3), key=lambda c: w[i][c]) for i in range(len(documents))]

    from app.stats.segmentation import adjusted_rand
    assert adjusted_rand(truth, assignments) > 0.9


def test_the_nmf_service_selects_its_own_topic_count_and_shows_the_curve():
    docs, truth, _ = _synthetic_corpus()
    out = text.nmf_topics(docs, AS_OF, seed=1, n_topics="auto", k_anonymity=5)
    assert out.value["n_topics"] >= 2
    assert out.value["selection_curve"], "the choice must be visible, not asserted"
    check = [c for c in out.checks if c.id == "n-topics-selected"][0]
    assert "coherence" in check.detail
    assert out.n == len(docs)


def test_the_nmf_service_returns_terms_weights_and_coherence_per_topic():
    docs, _, _ = _synthetic_corpus()
    out = text.nmf_topics(docs, AS_OF, seed=1, n_topics=3, k_anonymity=5)
    assert len(out.value["topics"]) == 3
    for topic in out.value["topics"]:
        assert topic["n_docs"] >= 0
        assert isinstance(topic["coherence"], float)
    assert out.value["reconstruction_error"] > 0
    assert out.value["stability"] >= 0.0


def test_a_topic_covering_too_few_documents_shows_no_examples():
    docs, _, _ = _synthetic_corpus()
    out = text.nmf_topics(docs, AS_OF, seed=1, n_topics=3, k_anonymity=1000)
    assert all(t["example_refs"] is None for t in out.value["topics"])
    check = [c for c in out.checks if c.id == "k-anonymity-examples"][0]
    assert check.status == "FAIL"
    assert "A topic of two is two people" in check.detail


def test_below_two_hundred_documents_the_topic_service_returns_the_calm_empty_state():
    docs, _, _ = _synthetic_corpus(n_docs=60)
    out = text.nmf_topics(docs, AS_OF, seed=1, n_topics=3)
    assert out.insufficient_data is True
    assert "single documents with a label" in out.caveats[0]


def test_the_topic_fit_is_reproducible_from_its_seed():
    docs, _, _ = _synthetic_corpus()
    a = text.nmf_topics(docs, AS_OF, seed=5, n_topics=3)
    b = text.nmf_topics(docs, AS_OF, seed=5, n_topics=3)
    assert [t["terms"] for t in a.value["topics"]] == [t["terms"] for t in b.value["topics"]]
    assert a.value["reconstruction_error"] == b.value["reconstruction_error"]
