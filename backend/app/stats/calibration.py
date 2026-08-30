"""
Calibration mappings and proper scoring rules.

These take score and label arrays produced by a risk service, not stream units.

The calibration gate governs the whole of Pack 3's risk half: no risk score is
served unless, after calibration on a held-out split, its Brier skill score
against climatology is positive and its expected calibration error is under the
pack threshold. AUC is reported but gates nothing. AUC measures ranking, and a
model that ranks perfectly while claiming 90% for events that happen 40% of the
time will get a committee to act on a number that is not true.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.
"""
import math
from typing import Sequence

from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import bootstrap_bca, mean, wilson_interval

MIN_ISOTONIC = 200
MIN_ISOTONIC_POSITIVES = 30
MIN_PLATT = 50
MIN_PLATT_POSITIVES = 10
MIN_SCORED = 100
MIN_SCORED_POSITIVES = 20
MIN_PER_BIN = 5
ECE_THRESHOLD = 0.05


def _validate(scores: Sequence[float], labels: Sequence[float]) -> None:
    if len(scores) != len(labels):
        raise ValueError("scores and labels differ in length")
    for label in labels:
        if label not in (0, 1, 0.0, 1.0, True, False):
            raise ValueError(
                "calibration takes binary labels; got " + repr(label)
                + ". A probability is calibrated against an outcome that happened or did not."
            )


# ---------------------------------------------------------------------------
# Pool adjacent violators
# ---------------------------------------------------------------------------


def pava(values: Sequence[float], weights: Sequence[float] | None = None) -> list[float]:
    """
    Pool adjacent violators: the unique least-squares non-decreasing fit.

    Exact and hand-computable, which is why it is the known-answer test for
    isotonic calibration. For `[1, 3, 2, 4]` with equal weights the answer is
    `[1, 2.5, 2.5, 4]`: the violating pair 3, 2 pools to its mean.

    Two invariants hold for any input and are asserted in the tests: the output
    is non-decreasing, and the weighted sum of the fitted values equals the
    weighted sum of the inputs, so pooling moves mass around without creating or
    destroying any.
    """
    n = len(values)
    if n == 0:
        return []
    w = [1.0] * n if weights is None else [float(x) for x in weights]
    if len(w) != n:
        raise ValueError("values and weights differ in length")
    # Each block is [weighted mean, total weight, run length].
    block_mean: list[float] = []
    block_weight: list[float] = []
    block_size: list[int] = []
    for i in range(n):
        block_mean.append(float(values[i]))
        block_weight.append(w[i])
        block_size.append(1)
        while len(block_mean) > 1 and block_mean[-2] > block_mean[-1]:
            total_weight = block_weight[-2] + block_weight[-1]
            pooled = (
                (block_mean[-2] * block_weight[-2] + block_mean[-1] * block_weight[-1])
                / total_weight if total_weight > 0 else
                0.5 * (block_mean[-2] + block_mean[-1])
            )
            size = block_size[-2] + block_size[-1]
            block_mean.pop(); block_weight.pop(); block_size.pop()
            block_mean[-1] = pooled
            block_weight[-1] = total_weight
            block_size[-1] = size
    out: list[float] = []
    for value, size in zip(block_mean, block_size):
        out.extend([value] * size)
    return out


def isotonic_map(scores: Sequence[float], labels: Sequence[float]) -> tuple[list[float], list[float]]:
    """
    Fit the isotonic calibration map and return it as a step function
    `(thresholds, values)`, ready to be applied to a new score.
    """
    order = sorted(range(len(scores)), key=lambda i: (scores[i], i))
    ordered_scores = [float(scores[i]) for i in order]
    ordered_labels = [float(labels[i]) for i in order]
    fitted = pava(ordered_labels)
    thresholds: list[float] = []
    values: list[float] = []
    for score, value in zip(ordered_scores, fitted):
        if thresholds and abs(values[-1] - value) < 1e-15:
            thresholds[-1] = score
            continue
        thresholds.append(score)
        values.append(value)
    return thresholds, values


def apply_isotonic(thresholds: Sequence[float], values: Sequence[float], score: float) -> float:
    """
    Apply a fitted step function, clamped at both ends.

    Clamping rather than extrapolating is deliberate: isotonic regression says
    nothing outside the range it saw, and inventing a slope there is how a
    calibration map produces a confident probability for a score it has no
    evidence about.
    """
    if not thresholds:
        return score
    if score <= thresholds[0]:
        return values[0]
    for i in range(len(thresholds)):
        if score <= thresholds[i]:
            return values[i]
    return values[-1]


# ---------------------------------------------------------------------------
# Platt scaling
# ---------------------------------------------------------------------------


def platt_fit(scores: Sequence[float], labels: Sequence[float], *, max_iter: int = 200
              ) -> tuple[float, float]:
    """
    Platt (1999) scaling: a one-dimensional logistic regression of the label on
    the score, fitted to Platt's CORRECTED targets rather than to 0 and 1.

    The correction, `t+ = (N+ + 1) / (N+ + 2)` and `t- = 1 / (N- + 2)`, is not a
    detail. Fitting to hard 0/1 targets at small n drives the slope to infinity
    whenever the classes are separable, producing a map that returns exactly 0
    and exactly 1, which are the two probabilities no honest model ever emits.

    Returns `(a, b)` for `p = 1 / (1 + exp(a * s + b))`, in Platt's own
    parameterisation.
    """
    n_pos = sum(1 for y in labels if y)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        raise ValueError("Platt scaling needs both outcomes present")
    hi = (n_pos + 1.0) / (n_pos + 2.0)
    lo = 1.0 / (n_neg + 2.0)
    targets = [hi if y else lo for y in labels]

    a, b = 0.0, math.log((n_neg + 1.0) / (n_pos + 1.0))
    for _ in range(max_iter):
        grad_a = grad_b = 0.0
        h11 = h22 = h12 = 0.0
        for score, target in zip(scores, targets):
            s = float(score)
            eta = a * s + b
            eta = max(-35.0, min(35.0, eta))
            p = 1.0 / (1.0 + math.exp(eta))
            weight = max(p * (1.0 - p), 1e-12)
            difference = p - target
            grad_a += s * difference
            grad_b += difference
            h11 += s * s * weight
            h22 += weight
            h12 += s * weight
        h11 += 1e-10
        h22 += 1e-10
        determinant = h11 * h22 - h12 * h12
        if abs(determinant) < 1e-18:
            break
        step_a = (h22 * grad_a - h12 * grad_b) / determinant
        step_b = (-h12 * grad_a + h11 * grad_b) / determinant
        a += step_a
        b += step_b
        if max(abs(step_a), abs(step_b)) < 1e-12:
            break
    return a, b


def apply_platt(a: float, b: float, score: float) -> float:
    eta = max(-35.0, min(35.0, a * float(score) + b))
    return 1.0 / (1.0 + math.exp(eta))


def platt_score_equations(scores: Sequence[float], labels: Sequence[float],
                          a: float, b: float) -> tuple[float, float]:
    """
    The two score equations at the fitted point.

    Used as the known-answer test instead of comparing against another library:
    at the maximum of a strictly concave likelihood the gradient is zero, and
    that is an exact mathematical statement rather than agreement with a second
    implementation that could be wrong in the same way.
    """
    n_pos = sum(1 for y in labels if y)
    n_neg = len(labels) - n_pos
    hi = (n_pos + 1.0) / (n_pos + 2.0)
    lo = 1.0 / (n_neg + 2.0)
    grad_a = grad_b = 0.0
    for score, label in zip(scores, labels):
        s = float(score)
        target = hi if label else lo
        p = apply_platt(a, b, s)
        grad_a += s * (p - target)
        grad_b += (p - target)
    return grad_a, grad_b


# ---------------------------------------------------------------------------
# Binning
# ---------------------------------------------------------------------------


def _bin_edges(probabilities: Sequence[float], bins: int, binning: str) -> list[float]:
    if binning == "equal_width":
        return [i / bins for i in range(bins + 1)]
    if binning != "equal_count":
        raise ValueError("binning must be 'equal_width' or 'equal_count', got " + repr(binning))
    ordered = sorted(float(p) for p in probabilities)
    edges = [0.0]
    n = len(ordered)
    for i in range(1, bins):
        edges.append(ordered[min(n - 1, int(round(i * n / bins)))])
    edges.append(1.0)
    # Collapse duplicate edges, which happen when a score is heavily tied.
    deduplicated = [edges[0]]
    for edge in edges[1:]:
        if edge > deduplicated[-1] + 1e-12:
            deduplicated.append(edge)
    if len(deduplicated) < 2:
        deduplicated = [0.0, 1.0]
    return deduplicated


def _assign_bins(probabilities: Sequence[float], edges: Sequence[float]) -> list[int]:
    assignments = []
    last = len(edges) - 2
    for p in probabilities:
        value = float(p)
        index = last
        for i in range(len(edges) - 1):
            if value <= edges[i + 1] or i == last:
                index = i
                break
        assignments.append(index)
    return assignments


def _grouped(probabilities, labels, edges) -> list[dict]:
    assignments = _assign_bins(probabilities, edges)
    groups: dict[int, list[int]] = {}
    for i, b in enumerate(assignments):
        groups.setdefault(b, []).append(i)
    rows = []
    for b in sorted(groups):
        members = groups[b]
        rows.append({
            "bin": b,
            "bin_lo": edges[b],
            "bin_hi": edges[b + 1],
            "indices": members,
            "n": len(members),
            "predicted_mean": mean([float(probabilities[i]) for i in members]),
            "observed_rate": mean([float(labels[i]) for i in members]),
        })
    return rows


def _merge_sparse(rows: list[dict], floor: int) -> tuple[list[dict], int]:
    """
    Merge any bin below the floor into its neighbour, and report how many merges
    happened. A bin of three households is a disclosure, not a data point.
    """
    merged = 0
    working = [dict(r) for r in rows]
    changed = True
    while changed and len(working) > 1:
        changed = False
        for i, row in enumerate(working):
            if row["n"] >= floor:
                continue
            partner = i + 1 if i == 0 else i - 1
            if partner >= len(working):
                partner = i - 1
            a, b = (i, partner) if i < partner else (partner, i)
            combined_indices = working[a]["indices"] + working[b]["indices"]
            combined = {
                "bin": working[a]["bin"],
                "bin_lo": working[a]["bin_lo"],
                "bin_hi": working[b]["bin_hi"],
                "indices": combined_indices,
                "n": len(combined_indices),
                "predicted_mean": 0.0,
                "observed_rate": 0.0,
            }
            working = working[:a] + [combined] + working[b + 1:]
            merged += 1
            changed = True
            break
    return working, merged


def _recompute(rows, probabilities, labels) -> list[dict]:
    out = []
    for row in rows:
        members = row["indices"]
        out.append({
            **row,
            "predicted_mean": mean([float(probabilities[i]) for i in members]),
            "observed_rate": mean([float(labels[i]) for i in members]),
        })
    return out


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------


def brier(probabilities: Sequence[float], labels: Sequence[float]) -> float:
    return math.fsum((float(p) - float(y)) ** 2 for p, y in zip(probabilities, labels)) / len(labels)


def murphy_decomposition(probabilities: Sequence[float], labels: Sequence[float],
                         rows: Sequence[dict]) -> dict:
    """
    Murphy's (1973) three-component decomposition, with the within-bin term
    written out rather than swept under the rug.

    The familiar identity `Brier = reliability - resolution + uncertainty` is
    exact only when the forecast is CONSTANT within each bin. With continuous
    probabilities there is a fourth term, and the exact identity is

        Brier = reliability - resolution + uncertainty + within_bin

    with `within_bin = mean(d_i^2 - 2 * d_i * y_i)` where `d_i` is the deviation
    of a forecast from its own bin's mean. It vanishes identically when the
    forecast is constant within bins, which is why the three-term form is the
    one everybody quotes.

    `docs/STATS_CATALOG.md` originally asserted the three-term identity on
    arbitrary inputs. That is false for continuous forecasts, so the catalog was
    corrected rather than the test being loosened to hide it. Both forms are
    asserted in the tests: four terms on arbitrary input, three on binned input.
    """
    n = len(labels)
    base_rate = mean([float(y) for y in labels])
    uncertainty = base_rate * (1.0 - base_rate)
    reliability = math.fsum(
        row["n"] * (row["predicted_mean"] - row["observed_rate"]) ** 2 for row in rows
    ) / n
    resolution = math.fsum(
        row["n"] * (row["observed_rate"] - base_rate) ** 2 for row in rows
    ) / n
    within = 0.0
    for row in rows:
        centre = row["predicted_mean"]
        for i in row["indices"]:
            d = float(probabilities[i]) - centre
            within += d * d - 2.0 * d * float(labels[i])
    within /= n
    score = brier(probabilities, labels)
    skill = 1.0 - score / uncertainty if uncertainty > 0.0 else 0.0
    return {
        "brier": score,
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
        "within_bin": within,
        "brier_skill_score": skill,
        "base_rate": base_rate,
    }


def expected_calibration_error(rows: Sequence[dict], n: int) -> tuple[float, float]:
    """Weighted mean and maximum absolute gap between claimed and observed rates."""
    ece = math.fsum(
        row["n"] * abs(row["predicted_mean"] - row["observed_rate"]) for row in rows
    ) / n
    mce = max((abs(row["predicted_mean"] - row["observed_rate"]) for row in rows), default=0.0)
    return ece, mce


def auc(probabilities: Sequence[float], labels: Sequence[float]) -> float:
    """
    Area under the ROC curve, by the Mann-Whitney form with ties at half.

    Reported everywhere and gating nothing, on purpose. It is invariant to any
    monotone transform of the score, so a model can have an AUC of 0.95 and be
    wildly miscalibrated, and that combination is exactly what this module
    exists to catch.
    """
    positives = [float(p) for p, y in zip(probabilities, labels) if y]
    negatives = [float(p) for p, y in zip(probabilities, labels) if not y]
    if not positives or not negatives:
        return 0.5
    ordered = sorted(range(len(probabilities)), key=lambda i: float(probabilities[i]))
    ranks = [0.0] * len(probabilities)
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and float(probabilities[ordered[j + 1]]) == float(
            probabilities[ordered[i]]
        ):
            j += 1
        average = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[ordered[k]] = average
        i = j + 1
    rank_sum = math.fsum(ranks[i] for i in range(len(labels)) if labels[i])
    n_pos = len(positives)
    n_neg = len(negatives)
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def isotonic_calibrate(scores, labels, as_of, *, out_of_fold=True) -> Evidence:
    """calibration.isotonic_calibrate. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "calibration.isotonic_calibrate"
    _validate(scores, labels)
    n = len(scores)
    positives = sum(1 for y in labels if y)
    phash = params_hash(method, 1, {"out_of_fold": bool(out_of_fold), "n": n})
    if n < MIN_ISOTONIC or positives < MIN_ISOTONIC_POSITIVES:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=(
                "isotonic regression needs " + str(MIN_ISOTONIC) + " observations with "
                + str(MIN_ISOTONIC_POSITIVES) + " positives, has " + str(n) + " with "
                + str(positives) + "; below this it overfits and produces a calibration map "
                "that is itself miscalibrated out of sample, so the pack uses Platt scaling "
                "instead and discloses the switch",
            ),
        )
    thresholds, values = isotonic_map(scores, labels)
    calibrated = [apply_isotonic(thresholds, values, float(s)) for s in scores]
    monotone = all(values[i] <= values[i + 1] + 1e-12 for i in range(len(values) - 1))
    checks = [
        Check(
            id="positives-sufficient",
            label="Enough positive outcomes to fit a non-parametric map",
            status="PASS",
            statistic=float(positives),
        ),
        Check(
            id="monotone-output",
            label="The fitted map never decreases",
            status="PASS" if monotone else "FAIL",
            blocking=not monotone,
            detail="" if monotone else
            "the fitted map decreases somewhere, which is an implementation fault: isotonic "
            "regression cannot produce this and nothing here can be used",
        ),
        Check(
            id="out-of-fold",
            label="The map was fitted out of fold",
            status="PASS" if out_of_fold else "WARN",
            detail="" if out_of_fold else
            "fitted on the same data it calibrates, which makes the calibration look better "
            "than it is; the pack always fits out of fold and this check exists so a future "
            "caller cannot quietly skip it",
        ),
    ]
    return Evidence(
        value={
            "thresholds": thresholds,
            "values": values,
            "calibrated": calibrated,
            "n_steps": len(values),
        },
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "The true relationship between score and probability is monotone.",
            "The map is fitted out of fold.",
        ),
        checks=tuple(checks),
        caveats=(
            "the mapping is a fit and carries no interval of its own; its uncertainty is "
            "reported by calibration.brier_decomposition rather than pretended here",
        ),
        unit="probability",
        params_hash=phash,
    )


def platt_calibrate(scores, labels, as_of, *, out_of_fold=True) -> Evidence:
    """calibration.platt_calibrate. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "calibration.platt_calibrate"
    _validate(scores, labels)
    n = len(scores)
    positives = sum(1 for y in labels if y)
    phash = params_hash(method, 1, {"out_of_fold": bool(out_of_fold), "n": n})
    if n < MIN_PLATT or positives < MIN_PLATT_POSITIVES or positives == n:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=(
                "Platt scaling needs " + str(MIN_PLATT) + " observations with "
                + str(MIN_PLATT_POSITIVES) + " of each outcome, has " + str(n) + " with "
                + str(positives) + " positive",
            ),
        )
    a, b = platt_fit(scores, labels)
    calibrated = [apply_platt(a, b, float(s)) for s in scores]
    grad_a, grad_b = platt_score_equations(scores, labels, a, b)
    converged = max(abs(grad_a), abs(grad_b)) < 1e-6
    checks = [
        Check(
            id="positives-sufficient",
            label="Both outcomes are present in useful numbers",
            status="PASS",
            statistic=float(positives),
        ),
        Check(
            id="fit-converged",
            label="The logistic fit reached its optimum",
            status="PASS" if converged else "WARN",
            statistic=max(abs(grad_a), abs(grad_b)),
            detail="" if converged else
            "the score equations are not zero at the reported parameters, so the map is "
            "approximate; read the calibration report before using it",
        ),
        Check(
            id="out-of-fold",
            label="The map was fitted out of fold",
            status="PASS" if out_of_fold else "WARN",
            detail="" if out_of_fold else
            "fitted on the same data it calibrates, which flatters the calibration",
        ),
    ]
    return Evidence(
        value={"a": a, "b": b, "calibrated": calibrated},
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "A sigmoid relationship between score and probability.",
            "Platt's prior correction to the target labels, which prevents the slope running "
            "to infinity when the classes separate.",
            "Fitted out of fold.",
        ),
        checks=tuple(checks),
        caveats=(
            "the mapping carries no interval; the Brier decomposition carries the uncertainty",
        ),
        unit="probability",
        params_hash=phash,
    )


def brier_decomposition(probabilities, labels, as_of, *, bins=10, binning="equal_count",
                        seed=0) -> Evidence:
    """calibration.brier_decomposition. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "calibration.brier_decomposition"
    _validate(probabilities, labels)
    n = len(probabilities)
    positives = sum(1 for y in labels if y)
    phash = params_hash(method, 1, {"bins": bins, "binning": binning, "seed": seed, "n": n})
    if n < MIN_SCORED or positives < MIN_SCORED_POSITIVES:
        return insufficient(
            method, n=n, as_of=as_of, empty_value={}, params_hash=phash,
            caveats=(
                "needs " + str(MIN_SCORED) + " observations with " + str(MIN_SCORED_POSITIVES)
                + " positives, has " + str(n) + " with " + str(positives),
            ),
        )
    edges = _bin_edges(probabilities, int(bins), binning)
    rows = _grouped(probabilities, labels, edges)
    rows, merges = _merge_sparse(rows, MIN_PER_BIN)
    rows = _recompute(rows, probabilities, labels)
    decomposition = murphy_decomposition(probabilities, labels, rows)
    skill = decomposition["brier_skill_score"]

    pairs = list(zip([float(p) for p in probabilities], [float(y) for y in labels]))
    interval = bootstrap_bca(
        pairs, lambda sample: math.fsum((p - y) ** 2 for p, y in sample) / len(sample),
        seed=seed, n_boot=800,
    )
    checks = [
        Check(
            id="bins-populated",
            label="Every bin holds enough observations for its rate to mean something",
            status="PASS" if merges == 0 else "WARN",
            statistic=float(merges),
            detail="" if merges == 0 else
            str(merges) + " sparse bin(s) were merged into a neighbour; the merge is disclosed "
            "rather than the thin bin being shown",
        ),
        Check(
            id="bss-positive",
            label="The probability is worth more than saying everyone is average",
            status="PASS" if skill > 0.0 else "FAIL",
            statistic=skill,
            blocking=skill <= 0.0,
            detail="" if skill > 0.0 else
            "the Brier skill score against climatology is not positive, so this model is no "
            "better than predicting the base rate for everyone; the score is suppressed",
        ),
        Check(
            id="sample-size-for-bins",
            label="Enough observations for the requested number of bins",
            status="PASS" if n >= MIN_PER_BIN * len(rows) else "WARN",
            statistic=float(n) / max(1, len(rows)),
            detail="" if n >= MIN_PER_BIN * len(rows) else
            "fewer than five observations per bin on average, so the per-bin rates are noisy",
        ),
    ]
    value = {
        key: decomposition[key] for key in
        ("brier", "reliability", "resolution", "uncertainty", "within_bin",
         "brier_skill_score", "base_rate")
    }
    value["auc"] = auc(probabilities, labels)
    value["n_bins"] = len(rows)
    value["binning"] = binning
    if skill <= 0.0:
        # A blocking failure empties the figure rather than merely flagging it.
        value["brier_skill_score"] = None
    return Evidence(
        value=value,
        n=n,
        method=method,
        as_of=as_of,
        interval=interval,
        interval_kind="bootstrap-bca-95",
        assumptions=(
            "The labels are the outcome the probability referred to, over the same horizon. "
            "Half of all calibration failures in practice are a horizon mismatch rather than a "
            "modelling failure.",
            "The binning is a declared parameter, since the decomposition is exact only given "
            "a binning.",
        ),
        checks=tuple(checks),
        caveats=(
            "the exact identity is brier = reliability - resolution + uncertainty + within_bin; "
            "the familiar three-term form holds only when the forecast is constant inside each "
            "bin, and within_bin is reported so the arithmetic can be checked",
            "AUC is reported and gates nothing: it measures ranking, not honesty",
        ),
        unit="brier",
        params_hash=phash,
    )


def reliability_diagram(probabilities, labels, as_of, *, bins=10, binning="equal_count",
                        k_anonymity=5) -> Evidence:
    """calibration.reliability_diagram. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "calibration.reliability_diagram"
    _validate(probabilities, labels)
    n = len(probabilities)
    positives = sum(1 for y in labels if y)
    phash = params_hash(method, 1, {
        "bins": bins, "binning": binning, "k_anonymity": k_anonymity, "n": n,
    })
    if n < MIN_SCORED or positives < MIN_SCORED_POSITIVES:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash,
            caveats=(
                "needs " + str(MIN_SCORED) + " observations with " + str(MIN_SCORED_POSITIVES)
                + " positives, has " + str(n) + " with " + str(positives),
            ),
        )
    edges = _bin_edges(probabilities, int(bins), binning)
    rows = _grouped(probabilities, labels, edges)
    floor = max(int(k_anonymity), MIN_PER_BIN)
    rows, merges = _merge_sparse(rows, floor)
    rows = _recompute(rows, probabilities, labels)
    ece, mce = expected_calibration_error(rows, n)

    table = []
    for row in rows:
        successes = int(round(row["observed_rate"] * row["n"]))
        lo, hi = wilson_interval(successes, row["n"])
        table.append({
            "bin_lo": row["bin_lo"],
            "bin_hi": row["bin_hi"],
            "predicted_mean": row["predicted_mean"],
            "observed_rate": row["observed_rate"],
            "n": row["n"],
            "lo": lo,
            "hi": hi,
        })
    checks = [
        Check(
            id="ece-threshold",
            label="Claimed probabilities match observed rates closely enough to act on",
            status="PASS" if ece < ECE_THRESHOLD else "FAIL",
            statistic=ece,
            blocking=ece >= ECE_THRESHOLD,
            detail="" if ece < ECE_THRESHOLD else
            "the expected calibration error is " + ("%.3f" % ece) + ", above the pack "
            "threshold of " + ("%.2f" % ECE_THRESHOLD) + "; a risk score this miscalibrated is "
            "not served, because a committee would act on a number that is not true",
        ),
        Check(
            id="k-anonymity-bins",
            label="No bin is thin enough to identify the people in it",
            status="PASS" if merges == 0 else "WARN",
            statistic=float(merges),
            detail="" if merges == 0 else
            str(merges) + " bin(s) below k = " + str(floor) + " were merged, not shown",
        ),
    ]
    return Evidence(
        value=[] if ece >= ECE_THRESHOLD else table,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=(
            "Each bin holds enough observations for its rate to mean anything; sparse bins are "
            "merged and the merge is disclosed.",
            "Every row carries its own n and interval, per the Evidence contract's table rule.",
        ),
        checks=tuple(checks),
        caveats=(
            "expected calibration error " + ("%.4f" % ece) + ", maximum bin gap "
            + ("%.4f" % mce),
            "bins are not equally precise; the Wilson interval on each row shows which ones "
            "rest on very little",
        ),
        unit="probability",
        params_hash=phash,
    )


__all__ = [
    "apply_isotonic",
    "apply_platt",
    "auc",
    "brier",
    "brier_decomposition",
    "expected_calibration_error",
    "isotonic_calibrate",
    "isotonic_map",
    "murphy_decomposition",
    "pava",
    "platt_calibrate",
    "platt_fit",
    "platt_score_equations",
    "reliability_diagram",
]
