"""
Text statistics over TextDoc.

TextDoc has no identity field, so nothing here can leak an author: it was never handed
one. Embeddings arrive precomputed; this module never calls a model.

The near-duplicate service is the one that earns its keep on day one, and its
honesty rests on one number. MinHash is an ESTIMATE of Jaccard similarity with
standard error sqrt(J(1-J)/k), about 0.04 at 128 permutations, so a threshold of
0.70 is really a threshold of 0.70 plus or minus 0.08. That figure is computed
and returned rather than described, and below 64 permutations the check warns
that the estimate is too noisy to threshold at all.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import hashlib
import math
import random
from typing import Any, Mapping, Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import mean

MIN_DOCS_TFIDF = 2
MIN_DOCS_NMF = 200
MIN_DOCS_PER_TOPIC = 30
NOISY_PERMUTATIONS = 64
SHORT_DOC_TOKENS = 5

# A Mersenne prime, comfortably above any 32-bit token hash, so the affine
# hash family h(x) = (a x + b) mod p is a genuine near-universal family.
MINHASH_PRIME = (1 << 61) - 1


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------


def jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    """Exact Jaccard by definition, so MinHash has something true to be judged against."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = len(sa | sb)
    return len(sa & sb) / union if union else 0.0


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine on two dense vectors. Exact, hence no interval anywhere near it."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = math.fsum(x * y for x, y in zip(a, b))
    na = math.sqrt(math.fsum(x * x for x in a))
    nb = math.sqrt(math.fsum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def token_hash(token: str) -> int:
    """
    A stable integer per token.

    Python's own `hash` is salted per process, so a signature computed today
    would not match one computed tomorrow. This module is required to be
    deterministic, so the hash is written out.
    """
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % MINHASH_PRIME


def minhash_signature(tokens: Sequence[str], *, n_permutations: int, seed: int) -> list[int]:
    """
    One signature: the minimum of h_i(t) over the token set, for each of the
    n_permutations seeded affine hashes.

    The estimator is unbiased for the Jaccard similarity, because for any pair
    of sets the probability that two signatures agree in a given position is
    exactly J. That is the theorem the tests check, both in expectation and in
    variance.
    """
    unique = sorted(set(tokens))
    if not unique:
        return [MINHASH_PRIME] * n_permutations
    rng = random.Random(seed)
    hashes = [token_hash(t) for t in unique]
    signature = []
    for _ in range(n_permutations):
        a = rng.randrange(1, MINHASH_PRIME)
        b = rng.randrange(0, MINHASH_PRIME)
        signature.append(min((a * h + b) % MINHASH_PRIME for h in hashes))
    return signature


def minhash_similarity(left: Sequence[int], right: Sequence[int]) -> float:
    """The share of signature positions that agree. An estimate, never exact."""
    if not left or len(left) != len(right):
        return 0.0
    return sum(1 for a, b in zip(left, right) if a == b) / len(left)


def lsh_bands(signature: Sequence[int], *, bands: int) -> list[tuple[int, str]]:
    """
    Banded locality-sensitive hashing keys.

    Two documents become candidates when any band matches, which is what stops
    a submission-time check being a scan of every complaint ever filed. The band
    count is a declared parameter because it sets the probability curve, and it
    enters params_hash.
    """
    if bands <= 0 or not signature:
        return []
    rows = max(1, len(signature) // bands)
    keys = []
    for band in range(bands):
        chunk = signature[band * rows:(band + 1) * rows]
        if not chunk:
            continue
        digest = hashlib.blake2b(
            ",".join(str(v) for v in chunk).encode("utf-8"), digest_size=8
        ).hexdigest()
        keys.append((band, digest))
    return keys


# ---------------------------------------------------------------------------
# TF-IDF
# ---------------------------------------------------------------------------


def tfidf_matrix(documents: Sequence[Sequence[str]], *, sublinear: bool = True,
                 smooth_idf: bool = True, vocabulary: Sequence[str] | None = None):
    """
    L2-normalised TF-IDF with the conventions stated rather than assumed.

    tf is 1 + log(count) under sublinear scaling and the raw count otherwise.
    idf is log((1 + N) / (1 + df)) + 1 when smoothed and log(N / df) + 1 when
    not. Both conventions change the numbers, so both are parameters and both
    are in params_hash.
    """
    n = len(documents)
    if vocabulary is None:
        vocabulary = sorted({token for document in documents for token in document})
    index = {token: j for j, token in enumerate(vocabulary)}

    document_frequency = [0] * len(vocabulary)
    for document in documents:
        for token in set(document):
            if token in index:
                document_frequency[index[token]] += 1

    idf = []
    for df in document_frequency:
        if smooth_idf:
            idf.append(math.log((1.0 + n) / (1.0 + df)) + 1.0)
        else:
            idf.append((math.log(n / df) + 1.0) if df else 0.0)

    rows = []
    for document in documents:
        counts: dict[int, int] = {}
        for token in document:
            if token in index:
                counts[index[token]] = counts.get(index[token], 0) + 1
        vector = [0.0] * len(vocabulary)
        for j, count in counts.items():
            tf = (1.0 + math.log(count)) if sublinear else float(count)
            vector[j] = tf * idf[j]
        norm = math.sqrt(math.fsum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        rows.append(vector)
    return rows, list(vocabulary), idf


def tfidf_similarity(docs, as_of, *, top_k=10, sublinear=True, smooth_idf=True) -> Evidence:
    """text.tfidf_similarity. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "text.tfidf_similarity"
    phash = params_hash(method, 1, {
        "top_k": top_k, "sublinear": sublinear, "smooth_idf": smooth_idf,
    })

    documents = [list(getattr(d, "tokens", ()) or ()) for d in docs]
    refs = [str(getattr(d, "doc_ref", i)) for i, d in enumerate(docs)]
    n = len(documents)
    if n < MIN_DOCS_TFIDF:
        return insufficient(
            method, n=n, as_of=as_of, params_hash=phash, empty_value=[], unit="cosine",
            caveats=("Similarity needs at least two documents; has " + str(n) + ".",),
        )

    matrix, vocabulary, _ = tfidf_matrix(
        documents, sublinear=sublinear, smooth_idf=smooth_idf
    )
    rows = []
    for i in range(n):
        scored = sorted(
            ((cosine(matrix[i], matrix[j]), refs[j]) for j in range(n) if j != i),
            key=lambda pair: (-pair[0], pair[1]),
        )
        for rank, (score, other) in enumerate(scored[:top_k], start=1):
            rows.append({
                "doc_ref": refs[i], "other_ref": other, "similarity": score,
                "rank": rank, "n": len(vocabulary),
            })

    short = sum(1 for d in documents if len(set(d)) < SHORT_DOC_TOKENS)
    return Evidence(
        value=rows,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Sublinear term scaling is " + ("on" if sublinear else "off") + " and idf smoothing "
            "is " + ("on" if smooth_idf else "off") + ". Both change the numbers, so both are "
            "declared and both are in params_hash.",
            "Lexical overlap approximates topical similarity.",
        ),
        checks=(
            Check(
                id="short-documents",
                label="Documents too short for lexical similarity to mean much",
                status="WARN" if short else "PASS",
                statistic=float(short),
                detail=(
                    str(short) + " documents have fewer than " + str(SHORT_DOC_TOKENS)
                    + " distinct tokens, so their similarity is dominated by one or two words."
                ) if short else "",
            ),
            Check(
                id="vocabulary-size",
                label="The vocabulary the comparison rests on",
                status="PASS",
                statistic=float(len(vocabulary)),
            ),
        ),
        caveats=(
            "Cosine similarity here is exact, not estimated, so there is no interval on it.",
            "Two complaints about different flats can be lexically identical. Similarity is "
            "not sameness and this service does not claim it is.",
        ),
        unit="cosine",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# text.near_duplicate_candidates
# ---------------------------------------------------------------------------


def near_duplicate_candidates(docs, query_doc, as_of, *, seed, threshold=0.7, method="both",
                              n_permutations=128, window_days=30) -> Evidence:
    """text.near_duplicate_candidates. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    service = "text.near_duplicate_candidates"
    phash = params_hash(service, 1, {
        "seed": seed, "threshold": threshold, "method": method,
        "n_permutations": n_permutations, "window_days": window_days,
    })
    if method not in ("minhash", "cosine", "both"):
        raise ValueError(
            "text.near_duplicate_candidates method must be 'minhash', 'cosine' or 'both', got "
            + repr(method)
        )

    query_at = getattr(query_doc, "at", None)
    query_ref = str(getattr(query_doc, "doc_ref", "query"))
    horizon = window_days * 86400.0
    candidates = [
        d for d in docs
        if str(getattr(d, "doc_ref", "")) != query_ref
        and (query_at is None or abs((query_at - d.at).total_seconds()) <= horizon)
    ]
    n = len(candidates)
    if n < 1:
        return insufficient(
            service, n=0, as_of=as_of, params_hash=phash, empty_value=[], unit="similarity",
            caveats=(
                "No other document falls inside the " + str(window_days) + " day window, so "
                "there is nothing to compare against. On day one that is the honest answer.",
            ),
        )

    query_tokens = list(getattr(query_doc, "tokens", ()) or ())
    query_embedding = getattr(query_doc, "embedding", None)

    use_minhash = method in ("minhash", "both")
    use_cosine = method in ("cosine", "both")
    embeddings_present = query_embedding is not None and all(
        getattr(d, "embedding", None) is not None for d in candidates
    )

    query_signature = (
        minhash_signature(query_tokens, n_permutations=n_permutations, seed=seed)
        if use_minhash else []
    )
    query_bands = set(lsh_bands(query_signature, bands=max(1, n_permutations // 8)))

    rows = []
    for d in candidates:
        tokens = list(getattr(d, "tokens", ()) or ())
        entry = {
            "doc_ref": str(getattr(d, "doc_ref", "")),
            "at": d.at.isoformat().replace("+00:00", "Z"),
            "similarity": None,
            "method": "",
            "jaccard_exact": jaccard(query_tokens, tokens),
            "minhash_estimate": None,
            "cosine": None,
            "lsh_candidate": None,
            "n": len(set(tokens)),
        }
        if use_minhash:
            signature = minhash_signature(tokens, n_permutations=n_permutations, seed=seed)
            entry["minhash_estimate"] = minhash_similarity(query_signature, signature)
            entry["lsh_candidate"] = bool(
                query_bands & set(lsh_bands(signature, bands=max(1, n_permutations // 8)))
            )
        if use_cosine:
            if embeddings_present:
                entry["cosine"] = cosine(query_embedding, getattr(d, "embedding"))
            else:
                # Fall back to token cosine, disclosed rather than substituted.
                matrix, _, _ = tfidf_matrix([query_tokens, tokens])
                entry["cosine"] = cosine(matrix[0], matrix[1])

        if use_cosine and entry["cosine"] is not None and (
            not use_minhash or entry["cosine"] >= (entry["minhash_estimate"] or 0.0)
        ):
            entry["similarity"] = entry["cosine"]
            entry["method"] = "cosine-embedding" if embeddings_present else "cosine-token"
        else:
            entry["similarity"] = entry["minhash_estimate"]
            entry["method"] = "minhash"
        rows.append(entry)

    rows = [r for r in rows if r["similarity"] is not None and r["similarity"] >= threshold]
    rows.sort(key=lambda r: (-r["similarity"], r["doc_ref"]))

    # The estimator's standard error is sqrt(J(1-J)/k), evaluated at the
    # threshold, since that is where a misestimate changes a decision. At a
    # threshold of 0 or 1 the binomial variance vanishes and the figure would
    # print as 0.000, which reads as perfect precision and measures nothing, so
    # the worst case J = 0.5 is used instead and the detail says which.
    at_threshold = 0.05 < threshold < 0.95
    basis = threshold if at_threshold else 0.5
    standard_error = math.sqrt(basis * (1.0 - basis) / max(n_permutations, 1))
    short_query = len(set(query_tokens)) < SHORT_DOC_TOKENS

    checks = [
        Check(
            id="minhash-error-bound",
            label="How precise the MinHash similarity estimate is",
            status=("SKIPPED" if not use_minhash else
                    ("WARN" if n_permutations < NOISY_PERMUTATIONS else "PASS")),
            statistic=standard_error,
            detail=(
                "At " + str(n_permutations) + " permutations the standard error of the "
                "estimate is " + "{:.3f}".format(standard_error) + " near a similarity of "
                + "{:.2f}".format(basis) + ", so a score there is really that plus or minus "
                "about " + "{:.2f}".format(2 * standard_error) + ". Below "
                + str(NOISY_PERMUTATIONS) + " permutations the estimate is too noisy to "
                "threshold at all."
                + ("" if at_threshold else
                   " The declared threshold of " + "{:.2f}".format(threshold) + " is degenerate "
                   "for this bound, where the variance vanishes and the figure would mean "
                   "nothing, so the worst case is quoted instead.")
                if use_minhash else "MinHash was not used for this query."
            ),
        ),
        Check(
            id="embedding-present",
            label="Whether a real embedding was available or token overlap stood in for one",
            status="PASS" if embeddings_present else "WARN",
            statistic=1.0 if embeddings_present else 0.0,
            detail=(
                "No precomputed embedding was available for every candidate, so cosine was "
                "computed on token vectors instead. That is a weaker notion of similarity and "
                "it is the one being reported."
            ) if not embeddings_present else "",
        ),
        Check(
            id="short-query",
            label="Whether the query is long enough for similarity to mean anything",
            status="WARN" if short_query else "PASS",
            statistic=float(len(set(query_tokens))),
            detail=(
                "The query has " + str(len(set(query_tokens))) + " distinct tokens. Below "
                + str(SHORT_DOC_TOKENS) + ", one shared word dominates the score."
            ) if short_query else "",
        ),
        Check(
            id="k-anonymity-authors",
            label="Only the count of similar reports leaves this service, never who wrote them",
            status="PASS",
            statistic=float(len(rows)),
            detail=(
                "TextDoc carries no author field, so this service was never handed one to leak. "
                "Re-attaching identities above the tenant's k is the service layer's decision "
                "and its risk, not this function's."
            ),
        ),
        Check(
            id="location-not-filtered-here",
            label="Whether the location filter was applied before similarity",
            status="WARN",
            statistic=float(n),
            detail=(
                "'No water in B-402' and 'no water in C-101' are lexically near identical and "
                "are different problems. Location must be a HARD FILTER on the candidate set "
                "before this function is called, not a ranking feature inside it, and TextDoc "
                "carries no location field for this function to filter on."
            ),
        ),
    ]

    return Evidence(
        value=rows,
        n=n,
        method=service,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Lexical or embedding similarity approximates semantic duplication.",
            "Candidates were restricted to the " + str(window_days) + " days around the query.",
        ),
        checks=tuple(checks),
        caveats=(
            "The exact Jaccard is in every row next to the MinHash estimate, so the size of the "
            "approximation is visible rather than asserted.",
            "A recurring seasonal complaint looks exactly like a duplicate of last year's. The "
            "window is what limits that, and it is a declared parameter.",
        ),
        unit="similarity",
        params_hash=phash,
    )


# ---------------------------------------------------------------------------
# NMF topics
# ---------------------------------------------------------------------------


def _top_singular(matrix, k, *, iterations=200):
    """
    The top-k singular triplets by deterministic power iteration with deflation.

    Deterministic because NNDSVD initialisation must be reproducible: a random
    start would make the topics depend on the seed in a way the stability check
    could not distinguish from genuine instability.
    """
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    work = [list(row) for row in matrix]
    triplets = []
    for component in range(k):
        v = [1.0 / math.sqrt(cols) if (j % (component + 2)) else -1.0 / math.sqrt(cols)
             for j in range(cols)]
        norm = math.sqrt(math.fsum(x * x for x in v)) or 1.0
        v = [x / norm for x in v]
        sigma = 0.0
        u = [0.0] * rows
        for _ in range(iterations):
            u = [math.fsum(work[i][j] * v[j] for j in range(cols)) for i in range(rows)]
            norm_u = math.sqrt(math.fsum(x * x for x in u))
            if norm_u < 1e-12:
                break
            u = [x / norm_u for x in u]
            v = [math.fsum(work[i][j] * u[i] for i in range(rows)) for j in range(cols)]
            norm_v = math.sqrt(math.fsum(x * x for x in v))
            if norm_v < 1e-12:
                break
            v = [x / norm_v for x in v]
            if abs(norm_v - sigma) < 1e-12:
                sigma = norm_v
                break
            sigma = norm_v
        triplets.append((sigma, u, v))
        for i in range(rows):
            for j in range(cols):
                work[i][j] -= sigma * u[i] * v[j]
    return triplets


def _nndsvd(matrix, k):
    """
    Boutsidis and Gallopoulos (2008): non-negative double singular value
    decomposition. Splits each singular vector into positive and negative parts
    and keeps whichever carries more energy, so the initialisation is already
    non-negative and structurally informative.
    """
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    triplets = _top_singular(matrix, k)
    w = [[0.0] * k for _ in range(rows)]
    h = [[0.0] * cols for _ in range(k)]
    for c, (sigma, u, v) in enumerate(triplets):
        up = [max(x, 0.0) for x in u]
        un = [max(-x, 0.0) for x in u]
        vp = [max(x, 0.0) for x in v]
        vn = [max(-x, 0.0) for x in v]
        nup = math.sqrt(math.fsum(x * x for x in up))
        nun = math.sqrt(math.fsum(x * x for x in un))
        nvp = math.sqrt(math.fsum(x * x for x in vp))
        nvn = math.sqrt(math.fsum(x * x for x in vn))
        if nup * nvp >= nun * nvn:
            scale = math.sqrt(max(sigma, 0.0) * nup * nvp)
            u_part = [x / nup * scale for x in up] if nup > 0 else [0.0] * rows
            v_part = [x / nvp * scale for x in vp] if nvp > 0 else [0.0] * cols
        else:
            scale = math.sqrt(max(sigma, 0.0) * nun * nvn)
            u_part = [x / nun * scale for x in un] if nun > 0 else [0.0] * rows
            v_part = [x / nvn * scale for x in vn] if nvn > 0 else [0.0] * cols
        for i in range(rows):
            w[i][c] = max(u_part[i], 1e-8)
        for j in range(cols):
            h[c][j] = max(v_part[j], 1e-8)
    return w, h


def nmf(matrix, k, *, seed, init="nndsvd", max_iter=300):
    """
    Lee and Seung multiplicative updates for the Frobenius objective.

    `init="nndsvd"` is deterministic; `init="random"` exists only so the
    stability check has genuinely different starting points to compare.
    """
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    if init == "nndsvd":
        w, h = _nndsvd(matrix, k)
    else:
        rng = random.Random(seed)
        w = [[rng.random() + 1e-6 for _ in range(k)] for _ in range(rows)]
        h = [[rng.random() + 1e-6 for _ in range(cols)] for _ in range(k)]

    for _ in range(max_iter):
        # H update: H *= (W'V) / (W'WH)
        wtv = [[math.fsum(w[i][c] * matrix[i][j] for i in range(rows)) for j in range(cols)]
               for c in range(k)]
        wtw = [[math.fsum(w[i][a] * w[i][b] for i in range(rows)) for b in range(k)]
               for a in range(k)]
        for c in range(k):
            for j in range(cols):
                denominator = math.fsum(wtw[c][b] * h[b][j] for b in range(k)) + 1e-10
                h[c][j] *= wtv[c][j] / denominator
        # W update: W *= (VH') / (WHH')
        vht = [[math.fsum(matrix[i][j] * h[c][j] for j in range(cols)) for c in range(k)]
               for i in range(rows)]
        hht = [[math.fsum(h[a][j] * h[b][j] for j in range(cols)) for b in range(k)]
               for a in range(k)]
        for i in range(rows):
            for c in range(k):
                denominator = math.fsum(w[i][b] * hht[b][c] for b in range(k)) + 1e-10
                w[i][c] *= vht[i][c] / denominator

    error = math.sqrt(math.fsum(
        (matrix[i][j] - math.fsum(w[i][c] * h[c][j] for c in range(k))) ** 2
        for i in range(rows) for j in range(cols)
    ))
    return w, h, error


def npmi_coherence(topic_terms: Sequence[int], documents: Sequence[set], *,
                   epsilon: float = 1e-12) -> float:
    """
    Bouma (2009) normalised pointwise mutual information, averaged over pairs.

    NPMI is in [-1, 1] with 1 meaning the terms always co-occur. Chosen over raw
    PMI because it is bounded, so a threshold means the same thing on a corpus
    of 200 documents as on one of 20,000.
    """
    n = len(documents)
    if n == 0 or len(topic_terms) < 2:
        return 0.0
    scores = []
    for a_index in range(len(topic_terms)):
        for b_index in range(a_index + 1, len(topic_terms)):
            a, b = topic_terms[a_index], topic_terms[b_index]
            pa = sum(1 for d in documents if a in d) / n
            pb = sum(1 for d in documents if b in d) / n
            pab = sum(1 for d in documents if a in d and b in d) / n
            if pa <= 0 or pb <= 0:
                continue
            if pab <= 0:
                scores.append(-1.0)
                continue
            pmi = math.log(pab / (pa * pb) + epsilon)
            scores.append(pmi / (-math.log(pab)))
    return mean(scores) if scores else 0.0


def _topic_alignment(a_topics, b_topics) -> float:
    """Best-match mean cosine between two sets of topic-term vectors."""
    if not a_topics or not b_topics:
        return 0.0
    used = set()
    scores = []
    for topic in a_topics:
        best, best_index = -1.0, None
        for index, other in enumerate(b_topics):
            if index in used:
                continue
            score = cosine(topic, other)
            if score > best:
                best, best_index = score, index
        if best_index is not None:
            used.add(best_index)
            scores.append(best)
    return mean(scores) if scores else 0.0


def nmf_topics(docs, as_of, *, seed, n_topics="auto", max_features=5000, init="nndsvd",
               k_anonymity=5) -> Evidence:
    """text.nmf_topics. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    service = "text.nmf_topics"
    phash = params_hash(service, 1, {
        "seed": seed, "n_topics": n_topics, "max_features": max_features, "init": init,
        "k_anonymity": k_anonymity,
    })

    documents = [list(getattr(d, "tokens", ()) or ()) for d in docs]
    refs = [str(getattr(d, "doc_ref", i)) for i, d in enumerate(docs)]
    n = len(documents)
    empty = {"topics": [], "reconstruction_error": None, "coherence": None}

    if n < MIN_DOCS_NMF:
        return insufficient(
            service, n=n, as_of=as_of, params_hash=phash, empty_value=empty, unit="topics",
            caveats=(
                "Needs " + str(MIN_DOCS_NMF) + " documents; has " + str(n) + ". NMF on forty "
                "complaint texts produces topics that are single documents with a label on "
                "them.",
            ),
        )

    frequency: dict[str, int] = {}
    for document in documents:
        for token in set(document):
            frequency[token] = frequency.get(token, 0) + 1
    vocabulary = [
        token for token in sorted(frequency, key=lambda t: (-frequency[t], t))[:max_features]
    ]
    vocabulary.sort()
    matrix, vocabulary, _ = tfidf_matrix(documents, vocabulary=vocabulary)
    token_sets = [set(t for t in document if t in set(vocabulary)) for document in documents]
    index_of = {token: j for j, token in enumerate(vocabulary)}
    document_indices = [{index_of[t] for t in s} for s in token_sets]

    if n_topics == "auto":
        ceiling = max(2, min(8, n // MIN_DOCS_PER_TOPIC))
        curve = {}
        for k in range(2, ceiling + 1):
            _, h, _ = nmf(matrix, k, seed=seed, init=init)
            curve[k] = mean([
                npmi_coherence(
                    sorted(range(len(vocabulary)), key=lambda j: -h[c][j])[:10],
                    document_indices,
                )
                for c in range(k)
            ])
        chosen = max(curve, key=lambda k: (curve[k], -k)) if curve else 2
    else:
        chosen = int(n_topics)
        curve = {}

    w, h, error = nmf(matrix, chosen, seed=seed, init=init)

    # Stability across genuinely different starting points, matched by cosine.
    reference = [list(row) for row in h]
    alignments = []
    for replicate in range(3):
        _, other, _ = nmf(matrix, chosen, seed=seed + 1 + replicate, init="random")
        alignments.append(_topic_alignment(reference, other))
    stability = mean(alignments) if alignments else 0.0

    assignments = [max(range(chosen), key=lambda c: w[i][c]) for i in range(n)]
    topics = []
    thin_topics = 0
    for c in range(chosen):
        order = sorted(range(len(vocabulary)), key=lambda j: (-h[c][j], j))[:10]
        members = [i for i in range(n) if assignments[i] == c]
        coherence = npmi_coherence(order, document_indices)
        # A topic covering fewer than k distinct documents cannot show examples
        # without showing whose complaints they are.
        showable = len(members) >= k_anonymity
        thin_topics += 0 if showable else 1
        topics.append({
            "topic": c,
            "terms": [vocabulary[j] for j in order],
            "weights": [h[c][j] for j in order],
            "n_docs": len(members),
            "coherence": coherence,
            "example_refs": [refs[i] for i in members[:3]] if showable else None,
            "suppressed_examples": not showable,
        })

    mean_coherence = mean([t["coherence"] for t in topics]) if topics else 0.0
    incoherent = [t for t in topics if t["coherence"] < 0.0]
    for topic in incoherent:
        # An incoherent topic list destroys trust in everything next to it.
        topic["terms"] = []
        topic["weights"] = []
        topic["suppressed_terms"] = True

    checks = [
        Check(
            id="topic-stability",
            label="Whether the same topics come back from a different starting point",
            status="PASS" if stability >= 0.7 else (
                "WARN" if stability >= 0.5 else "FAIL"
            ),
            statistic=stability,
            blocking=stability < 0.5,
            detail=(
                "Best-match cosine across restarts is " + "{:.2f}".format(stability)
                + ", below 0.5. These topics are an artefact of where the optimiser started, "
                "so they are not published."
            ) if stability < 0.5 else "",
        ),
        Check(
            id="topic-coherence",
            label="Whether each topic's words actually go together",
            status="WARN" if incoherent else "PASS",
            statistic=mean_coherence,
            detail=(
                str(len(incoherent)) + " topics scored below zero on NPMI coherence, meaning "
                "their top words co-occur less than chance. Their term lists are hidden: an "
                "incoherent topic destroys trust in the coherent ones beside it."
            ) if incoherent else "",
        ),
        Check(
            id="k-anonymity-examples",
            label="Example documents are shown only for topics covering enough people",
            status="FAIL" if thin_topics else "PASS",
            statistic=float(k_anonymity),
            blocking=False,
            detail=(
                str(thin_topics) + " topics cover fewer than " + str(k_anonymity)
                + " documents, so their examples are withheld. A topic of two is two people."
            ) if thin_topics else "",
        ),
        Check(
            id="n-topics-selected",
            label="How the number of topics was chosen",
            status="PASS",
            statistic=float(chosen),
            detail=(
                "Chosen by maximising mean NPMI coherence over k in 2.." + str(max(curve))
                + "; the whole curve is returned so the choice is visible: "
                + ", ".join(str(k) + ": " + "{:.3f}".format(v) for k, v in sorted(curve.items()))
                if curve else "The caller declared " + str(chosen) + " topics."
            ),
        ),
    ]

    value = {
        "topics": topics,
        "reconstruction_error": error,
        "coherence": mean_coherence,
        "n_topics": chosen,
        "selection_curve": curve,
        "stability": stability,
        "vocabulary_size": len(vocabulary),
    }
    if stability < 0.5:
        value = {**value, "topics": []}

    return Evidence(
        value=value,
        n=n,
        method=service,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Documents are mixtures of a small number of additive term distributions.",
            "The initialisation is NNDSVD, which is deterministic, so a change in the topics "
            "between runs is a change in the corpus and not in the seed.",
        ),
        checks=tuple(checks),
        caveats=(
            "There is no interval on a topic. Coherence and stability are the quality "
            "statements and both are always shown.",
            "A corpus dominated by one category splits into near-duplicates of itself. The "
            "coherence numbers are what makes that visible.",
        ),
        unit="topics",
        params_hash=phash,
    )


__all__ = [
    "cosine",
    "jaccard",
    "lsh_bands",
    "minhash_signature",
    "minhash_similarity",
    "near_duplicate_candidates",
    "nmf",
    "nmf_topics",
    "npmi_coherence",
    "token_hash",
    "tfidf_matrix",
    "tfidf_similarity",
]
