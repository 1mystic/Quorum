"""
Calibrated per-member risk.

The calibration gate governs this module: no risk score is served unless, after
calibration on a held-out split, its Brier skill score against climatology is
positive and its expected calibration error is under the pack threshold. AUC is
reported but gates nothing: it measures ranking, and a model that ranks
perfectly while claiming 90% for events that happen 40% of the time will get a
committee to act on a number that is not true.

Every function here is pure and returns an `Evidence` envelope, never a bare
value. Signatures and floors come from docs/STATS_CATALOG.md; the Method Card
for each id lives in app/stats/registry.py and a service without one does not
load.

**Individual risk scores are the highest-stakes output in the platform**,
because a committee will act on them against a named household. Every blocking
failure therefore suppresses the individual scores entirely and falls back to
per-stratum empirical rates with Wilson intervals, which is honest and often
almost as useful. Two further rules are policy and live in the Method Card
rather than in code: per-member scores are visible only to the roles the
vertical manifest names, and they are never included in an export or an LLM
prompt with an identifier attached.
"""
import math
import random
from typing import Any, Sequence

from app.stats.calibration import (
    ECE_THRESHOLD,
    MIN_ISOTONIC,
    MIN_ISOTONIC_POSITIVES,
    apply_isotonic,
    apply_platt,
    auc,
    brier,
    expected_calibration_error,
    isotonic_map,
    murphy_decomposition,
    platt_fit,
)
from app.stats.conformal import conformal_quantile
from app.stats.contracts import Check, Evidence, insufficient, params_hash
from app.stats.numeric import logistic_l2_fit, logistic_predict, mean, wilson_interval

MIN_ROWS = 300
MIN_POSITIVES = 40
MIN_OUTCOMES_PER_FEATURE = 10


class _Row:
    """One training row: an identifier, a feature vector, a label, and its stratum."""

    __slots__ = ("ref", "features", "label", "stratum", "feature_as_of", "horizon_start")

    def __init__(self, ref, features, label, stratum, feature_as_of, horizon_start):
        self.ref = ref
        self.features = features
        self.label = label
        self.stratum = stratum
        self.feature_as_of = feature_as_of
        self.horizon_start = horizon_start


def _feature_vector(features: Any) -> tuple[list[float], list[str]]:
    values = [
        float(getattr(features, "recency_days", 0.0)),
        float(getattr(features, "frequency_90d", 0)),
        float(getattr(features, "breadth", 0)),
        float(getattr(features, "volunteer_hours_365d", 0.0)),
        float(getattr(features, "tenure_days", 0.0)),
        float(getattr(features, "contribution_minor", 0)) / 100000.0,
    ]
    names = ["recency_days", "frequency_90d", "breadth", "volunteer_hours_365d",
             "tenure_days", "contribution_lakh"]
    return values, names


def _standardise(rows: Sequence[_Row]) -> tuple[list[float], list[float]]:
    """
    Centre and scale, so the L2 penalty means the same thing for every feature.

    Penalising an unstandardised design shrinks whichever coefficient happens to
    be attached to a large-valued column, which is an arbitrary choice dressed
    up as regularisation.
    """
    width = len(rows[0].features)
    centres, scales = [], []
    for j in range(width):
        column = [r.features[j] for r in rows]
        centre = mean(column)
        spread = math.sqrt(math.fsum((v - centre) ** 2 for v in column) / max(1, len(column) - 1))
        centres.append(centre)
        scales.append(spread if spread > 1e-12 else 1.0)
    return centres, scales


def _design(row: _Row, centres, scales) -> list[float]:
    return [1.0] + [(v - c) / s for v, c, s in zip(row.features, centres, scales)]


def _folds(n: int, folds: int, seed: int) -> list[list[int]]:
    """Deterministic k-fold assignment from an explicit seed."""
    index = list(range(n))
    random.Random(seed).shuffle(index)
    return [index[i::folds] for i in range(folds)]


def _out_of_fold_scores(rows: Sequence[_Row], centres, scales, *, folds: int, seed: int,
                        penalty: float) -> tuple[list[float], list[list[float]]]:
    """
    Out-of-fold linear scores, plus each fold's coefficients for the stability
    check.

    Out of fold is not optional. A calibration map fitted on the same rows the
    model was trained on reports the training error as if it were the future,
    and it is the single easiest way to ship a model that looks calibrated and
    is not.
    """
    n = len(rows)
    assignments = _folds(n, folds, seed)
    scores = [0.0] * n
    coefficients: list[list[float]] = []
    for held_out in assignments:
        held = set(held_out)
        train = [i for i in range(n) if i not in held]
        if not train or not held_out:
            continue
        design = [_design(rows[i], centres, scales) for i in train]
        labels = [rows[i].label for i in train]
        beta = logistic_l2_fit(design, labels, penalty=penalty)
        coefficients.append(beta)
        for i in held_out:
            scores[i] = math.fsum(
                b * x for b, x in zip(beta, _design(rows[i], centres, scales))
            )
    return scores, coefficients


def _calibrate_out_of_fold(scores: Sequence[float], labels: Sequence[float], choice: str,
                           *, folds: int, seed: int) -> tuple[list[float], str]:
    """
    Calibrate each fold with a map fitted on the OTHER folds.

    This is not fussiness. Fitting the calibration map on the same scores it is
    then scored against drives the expected calibration error to approximately
    zero by construction, especially for isotonic regression, which is flexible
    enough to absorb the noise. The first version of this module did exactly
    that and reported an ECE of 0.0000, which is the number a gate produces when
    it is measuring nothing. The gate has to see genuinely held-out
    probabilities or it is not a gate.
    """
    n = len(scores)
    positives = sum(1 for y in labels if y)
    use_isotonic = (
        choice == "isotonic"
        or (choice == "auto" and n >= MIN_ISOTONIC and positives >= MIN_ISOTONIC_POSITIVES)
    )
    name = "isotonic" if use_isotonic else "platt"
    assignments = _folds(n, folds, seed + 977)
    calibrated = [0.0] * n
    for held_out in assignments:
        held = set(held_out)
        train = [i for i in range(n) if i not in held]
        if not train or not held_out:
            continue
        train_scores = [scores[i] for i in train]
        train_labels = [labels[i] for i in train]
        if len({y for y in train_labels}) < 2:
            for i in held_out:
                calibrated[i] = mean(train_labels) if train_labels else 0.5
            continue
        if use_isotonic:
            thresholds, values = isotonic_map(train_scores, train_labels)
            for i in held_out:
                calibrated[i] = apply_isotonic(thresholds, values, scores[i])
        else:
            a, b = platt_fit(train_scores, train_labels)
            for i in held_out:
                calibrated[i] = apply_platt(a, b, scores[i])
    return calibrated, name


def _stratum_rates(rows: Sequence[_Row], k: int = 5) -> list[dict]:
    """
    The fallback: empirical rates per stratum with Wilson intervals.

    This is what is served whenever a blocking check fails. It is honest, it is
    often almost as useful as the model, and crucially it says nothing about any
    individual household. Strata below k are pooled into "other", never shown
    thin.
    """
    groups: dict[str, list[_Row]] = {}
    for row in rows:
        groups.setdefault(row.stratum or "unstated", []).append(row)
    small = [name for name, members in groups.items() if len(members) < k]
    pooled: list[_Row] = []
    for name in small:
        pooled.extend(groups.pop(name))
    if pooled:
        groups.setdefault("other", []).extend(pooled)
    out = []
    for name in sorted(groups):
        members = groups[name]
        successes = sum(1 for r in members if r.label)
        lo, hi = wilson_interval(successes, len(members))
        out.append({
            "stratum": name,
            "rate": successes / len(members),
            "lo": lo,
            "hi": hi,
            "n": len(members),
        })
    return out


def _leakage_free(rows: Sequence[_Row]) -> tuple[bool, int]:
    """
    Every feature must be known BEFORE the horizon it predicts.

    Counted rather than assumed. Temporal leakage produces a model that looks
    excellent in backtest and is useless in production, and it is invisible
    unless it is checked.
    """
    violations = 0
    for row in rows:
        if row.feature_as_of is None or row.horizon_start is None:
            continue
        if row.feature_as_of > row.horizon_start:
            violations += 1
    return violations == 0, violations


def _fit_and_gate(rows: Sequence[_Row], method: str, as_of, *, seed: int, folds: int,
                  calibrator: str, phash: str, feature_names: Sequence[str],
                  censored: int, extra_checks: Sequence[Check] = (),
                  extra_assumptions: Sequence[str] = (),
                  extra_caveats: Sequence[str] = ()) -> Evidence:
    """
    The shared body of both risk services: fit out of fold, calibrate, gate, and
    fall back to stratum rates on any blocking failure.

    Written once so the two services cannot drift apart on the thing that
    matters most about them, which is what they refuse to publish.
    """
    n = len(rows)
    positives = sum(1 for r in rows if r.label)
    checks: list[Check] = list(extra_checks)

    leak_ok, violations = _leakage_free(rows)
    checks.append(Check(
        id="leakage-temporal",
        label="Every feature was known before the period it predicts",
        status="PASS" if leak_ok else "FAIL",
        statistic=float(violations),
        blocking=not leak_ok,
        detail="" if leak_ok else
        str(violations) + " row(s) carry a feature timestamped after the outcome window opened. "
        "A model trained on these looks excellent in backtest and is useless in production, so "
        "the individual scores are suppressed and the per-stratum rates are shown instead",
    ))
    balanced = positives >= MIN_POSITIVES
    checks.append(Check(
        id="class-balance",
        label="Enough outcomes of the kind being predicted",
        status="PASS" if balanced else "FAIL",
        statistic=float(positives),
        blocking=not balanced,
        detail="" if balanced else
        "fewer than " + str(MIN_POSITIVES) + " positive outcomes, so no individual model is "
        "fitted; the per-stratum empirical rates are shown instead",
    ))
    per_feature = positives / max(1, len(feature_names))
    checks.append(Check(
        id="outcomes-per-feature",
        label="Enough outcomes per feature for the coefficients to mean anything",
        status="PASS" if per_feature >= MIN_OUTCOMES_PER_FEATURE else "WARN",
        statistic=per_feature,
        detail="" if per_feature >= MIN_OUTCOMES_PER_FEATURE else
        "fewer than " + str(MIN_OUTCOMES_PER_FEATURE) + " outcomes per feature; the "
        "coefficients are unstable even where the calibration passes",
    ))

    fallback = _stratum_rates(rows)
    if not balanced or not leak_ok:
        return _suppressed(method, as_of, n, positives, censored, checks, fallback, phash,
                           extra_assumptions, extra_caveats)

    centres, scales = _standardise(rows)
    scores, coefficients = _out_of_fold_scores(
        rows, centres, scales, folds=folds, seed=seed, penalty=1.0,
    )
    labels = [r.label for r in rows]
    try:
        probabilities, calibrator_used = _calibrate_out_of_fold(
            scores, labels, calibrator, folds=folds, seed=seed,
        )
    except ValueError:
        return _suppressed(method, as_of, n, positives, censored, checks, fallback, phash,
                           extra_assumptions, extra_caveats)

    edges_rows = _binned(probabilities, labels)
    decomposition = murphy_decomposition(probabilities, labels, edges_rows)
    ece, mce = expected_calibration_error(edges_rows, n)
    skill = decomposition["brier_skill_score"]
    area = auc(probabilities, labels)

    calibrated = skill > 0.0 and ece < ECE_THRESHOLD
    checks.append(Check(
        id="calibration-gate",
        label="The probabilities are worth more than the average, and mean what they say",
        status="PASS" if calibrated else "FAIL",
        statistic=skill,
        blocking=not calibrated,
        detail="" if calibrated else
        "Brier skill score " + ("%.3f" % skill) + " and expected calibration error "
        + ("%.3f" % ece) + " against a threshold of " + ("%.2f" % ECE_THRESHOLD)
        + "; the individual scores are suppressed entirely and the per-stratum empirical rates "
        "are shown instead",
    ))

    # Coefficient sign stability across folds.
    flips = 0
    if len(coefficients) > 1:
        for j in range(1, len(coefficients[0])):
            signs = {1 if beta[j] > 0 else (-1 if beta[j] < 0 else 0) for beta in coefficients}
            if len({s for s in signs if s}) > 1:
                flips += 1
    checks.append(Check(
        id="stability-across-folds",
        label="No coefficient changes sign between folds",
        status="PASS" if flips == 0 else "WARN",
        statistic=float(flips),
        detail="" if flips == 0 else
        str(flips) + " coefficient(s) flip sign across folds, so the per-member explanations "
        "are less stable than the probability itself",
    ))

    # Calibration measured separately per stratum: a model well calibrated
    # overall can be badly miscalibrated for one block, and that block is a
    # named set of households.
    worst_stratum, worst_ece = "", 0.0
    groups: dict[str, list[int]] = {}
    for i, row in enumerate(rows):
        groups.setdefault(row.stratum or "unstated", []).append(i)
    for name, members in groups.items():
        if len(members) < 30:
            continue
        gap = abs(mean([probabilities[i] for i in members]) - mean([labels[i] for i in members]))
        if gap > worst_ece:
            worst_ece, worst_stratum = gap, name
    checks.append(Check(
        id="protected-strata-parity",
        label="The model is as well calibrated for each stratum as it is overall",
        status="PASS" if worst_ece < ECE_THRESHOLD else "WARN",
        statistic=worst_ece,
        detail="" if worst_ece < ECE_THRESHOLD else
        "stratum " + worst_stratum + " is miscalibrated by " + ("%.3f" % worst_ece)
        + " while the model passes overall; always reported, because the people in that "
        "stratum are the ones who would be acted against",
    ))

    if not calibrated:
        return _suppressed(method, as_of, n, positives, censored, checks, fallback, phash,
                           extra_assumptions, extra_caveats,
                           report={"brier": decomposition["brier"], "ece": ece, "auc": area,
                                   "brier_skill_score": skill, "calibrator": calibrator_used})

    # A conformal interval on the individual PROBABILITY, from how much the
    # fold models disagree about each member.
    #
    # The obvious alternative, conformalising the absolute residual
    # |y - p|, is valid but nearly useless here: for a binary outcome those
    # residuals cluster at 0 and 1, so the 90% interval on a member scored at
    # 0.8 comes out as roughly [0.08, 1.0]. That interval is about the OUTCOME,
    # not about the estimate, and a reader asking "how sure are we of this 0.8"
    # is not asking about the coin flip. Fold disagreement answers the question
    # actually being asked, and the caveat says exactly which uncertainty it
    # covers so nobody reads it as the other one.
    disagreement: list[float] = []
    per_row_spread = [0.0] * n
    if len(coefficients) > 1:
        for i, row in enumerate(rows):
            design = _design(row, centres, scales)
            fold_scores = [
                math.fsum(b * x for b, x in zip(beta, design)) for beta in coefficients
            ]
            centre = mean(fold_scores)
            spread = max(abs(s - centre) for s in fold_scores)
            # Convert the score spread to a probability spread locally.
            slope = probabilities[i] * (1.0 - probabilities[i])
            per_row_spread[i] = spread * max(slope, 0.02)
            disagreement.append(per_row_spread[i])
    q = conformal_quantile(disagreement, 0.1) if disagreement else 0.0
    table = []
    important = sorted(
        range(len(feature_names)),
        key=lambda j: -abs(mean([beta[j + 1] for beta in coefficients])) if coefficients else 0.0,
    )[:3]
    top_features = [feature_names[j] for j in important]
    for i, row in enumerate(rows):
        lo = max(0.0, probabilities[i] - q) if math.isfinite(q) else 0.0
        hi = min(1.0, probabilities[i] + q) if math.isfinite(q) else 1.0
        table.append({
            "member_ref": row.ref,
            "probability": probabilities[i],
            "lo": lo,
            "hi": hi,
            "n": 1,
            "top_features": top_features,
        })
    table.sort(key=lambda r: -r["probability"])
    return Evidence(
        value=table,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="conformal-90",
        assumptions=tuple(extra_assumptions) + (
            "A fixed prediction horizon, identical for every row.",
            "Features are known before the outcome window opens.",
            "Calibration transfers from the held-out fold to the present.",
        ),
        checks=tuple(checks),
        caveats=tuple(extra_caveats) + (
            "calibration report: Brier " + ("%.4f" % decomposition["brier"]) + ", skill score "
            + ("%.3f" % skill) + ", expected calibration error " + ("%.4f" % ece)
            + ", AUC " + ("%.3f" % area) + " via " + calibrator_used + " calibration",
            "AUC is reported and gates nothing; the gate is the skill score and the calibration "
            "error",
            "a probability is a rate over similar rows, never a statement about a person",
            "the interval is a 90% conformal interval on the individual PROBABILITY, built from "
            "how much the fold models disagree about that member. It covers uncertainty in the "
            "estimate, not the coin flip: a member at 0.30 will still often not pay late, and "
            "that is the model being right rather than wrong",
        ),
        unit="probability",
        n_censored=censored,
        params_hash=phash,
    )


def _binned(probabilities: Sequence[float], labels: Sequence[float], bins: int = 10) -> list[dict]:
    from app.stats.calibration import _bin_edges, _grouped, _merge_sparse, _recompute, MIN_PER_BIN
    edges = _bin_edges(probabilities, bins, "equal_count")
    rows = _grouped(probabilities, labels, edges)
    rows, _ = _merge_sparse(rows, MIN_PER_BIN)
    return _recompute(rows, probabilities, labels)


def _suppressed(method, as_of, n, positives, censored, checks, fallback, phash,
                extra_assumptions, extra_caveats, report=None) -> Evidence:
    """
    The conservative failure mode.

    Individual scores vanish; the per-stratum empirical rates with Wilson
    intervals take their place. Every row still carries its own n and interval,
    per the Evidence contract's table rule.
    """
    caveats = list(extra_caveats) + [
        "individual risk scores are suppressed; what is shown is the empirical rate per "
        "stratum with a Wilson interval, which is honest and often almost as useful",
        "a committee will act on an individual score against a named household, so the bar to "
        "publish one is the highest in the catalog and the failure mode is deliberately "
        "conservative",
    ]
    if report:
        caveats.append(
            "calibration report from the attempted fit: Brier " + ("%.4f" % report["brier"])
            + ", skill score " + ("%.3f" % report["brier_skill_score"])
            + ", expected calibration error " + ("%.4f" % report["ece"])
            + ", AUC " + ("%.3f" % report["auc"])
        )
    return Evidence(
        value=fallback,
        n=n,
        method=method,
        as_of=as_of,
        interval_kind="none",
        assumptions=tuple(extra_assumptions),
        checks=tuple(checks),
        caveats=tuple(caveats),
        unit="probability",
        n_censored=censored,
        params_hash=phash,
    )


def _due_rows(dues, features, window, horizon_days: float) -> tuple[list[_Row], int]:
    by_member = {}
    for f in features or ():
        by_member[getattr(f, "member_ref", None)] = f
    end = getattr(window, "end", None)
    rows: list[_Row] = []
    censored = 0
    for due in dues or ():
        member = getattr(due, "member_ref", None)
        feature = by_member.get(member)
        if feature is None:
            continue
        settled = getattr(due, "settled_at", None)
        due_at = getattr(due, "due_at", None)
        observed = bool(getattr(due, "event_observed", False))
        if settled is None:
            # Rule L1 and the censoring rule the catalog names explicitly: a due
            # unpaid at the boundary within the horizon is RIGHT-CENSORED, not
            # labelled "paid on time". Labelling it paid is the same defect as
            # dropping open tickets and it biases the model towards optimism.
            if end is not None and due_at is not None:
                elapsed = (end - due_at).total_seconds() / 86400.0
                if elapsed < horizon_days:
                    censored += 1
                    continue
            label = 1.0
        else:
            late_by = (settled - due_at).total_seconds() / 86400.0 if due_at else 0.0
            label = 1.0 if late_by > 0.0 else 0.0
            if not observed:
                censored += 1
                continue
        values, names = _feature_vector(feature)
        stratum = ""
        strata = getattr(due, "strata", None) or getattr(feature, "strata", None) or {}
        if strata:
            stratum = str(sorted(strata.items())[0][1])
        rows.append(_Row(member, values, label, stratum,
                         getattr(feature, "as_of", None), due_at))
    return rows, censored


def late_payment_risk(dues, features, window, *, seed, horizon_days=30, model="logistic_l2",
                      calibrator="auto", folds=5) -> Evidence:
    """risk.late_payment_risk. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "risk.late_payment_risk"
    if model != "logistic_l2":
        raise ValueError(
            "only 'logistic_l2' is available in this engine: a gradient-boosted model would "
            "need the scientific stack, which PLAN.md deliberately keeps off the light tier. "
            "Naming the limit beats silently fitting something else"
        )
    if calibrator not in ("isotonic", "platt", "auto"):
        raise ValueError("calibrator must be 'isotonic', 'platt' or 'auto', got " + repr(calibrator))
    as_of = getattr(window, "end", None)
    rows, censored = _due_rows(dues, features, window, float(horizon_days))
    n = len(rows)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": as_of,
        "horizon_days": horizon_days, "model": model, "calibrator": calibrator,
        "folds": folds, "seed": seed,
    })
    if n < MIN_ROWS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash, n_censored=censored,
            caveats=(
                "needs " + str(MIN_ROWS) + " due spells, has " + str(n) + "; below the floor "
                "the pack does not fit a model and the per-stratum empirical rates are the "
                "honest answer",
            ),
        )
    _, names = _feature_vector(features[0])
    censoring_check = Check(
        id="censoring-handled",
        label="A due still unpaid inside the horizon is censored, not called paid on time",
        status="PASS",
        statistic=float(censored),
        detail="" if censored == 0 else
        str(censored) + " due(s) were still unresolved inside the horizon and were censored "
        "rather than labelled paid on time",
    )
    return _fit_and_gate(
        rows, method, as_of, seed=int(seed), folds=int(folds), calibrator=calibrator,
        phash=phash, feature_names=names, censored=censored,
        extra_checks=(censoring_check,),
        extra_assumptions=(
            "A due unpaid at the window boundary within the horizon is right-censored, not "
            "labelled paid on time (spine rule L1).",
        ),
        extra_caveats=(
            "if the reminder policy changed, this model will learn that people who got "
            "reminders pay late and invert the causal direction; reminders are a treatment",
        ),
    )


def _member_rows(spells, features, window, horizon_days: float) -> tuple[list[_Row], int]:
    by_member = {}
    for f in features or ():
        by_member[getattr(f, "member_ref", None)] = f
    rows: list[_Row] = []
    censored = 0
    for spell in spells or ():
        member = getattr(spell, "member_ref", None)
        feature = by_member.get(member)
        if feature is None:
            continue
        observed = bool(getattr(spell, "event_observed", False))
        duration = float(getattr(spell, "duration_days", 0.0))
        if not observed and duration < horizon_days:
            # Still active and not observed long enough to know: censored, not
            # a retention success.
            censored += 1
            continue
        label = 1.0 if (observed and duration <= horizon_days) else 0.0
        values, names = _feature_vector(feature)
        strata = getattr(spell, "strata_at_entry", None) or getattr(feature, "strata", None) or {}
        stratum = str(sorted(strata.items())[0][1]) if strata else ""
        rows.append(_Row(member, values, label, stratum,
                         getattr(feature, "as_of", None), getattr(spell, "at_risk_from", None)))
    return rows, censored


def member_disengagement_risk(spells, features, window, *, seed, horizon_days=90,
                              model="logistic_l2", calibrator="auto", folds=5) -> Evidence:
    """risk.member_disengagement_risk. See docs/STATS_CATALOG.md and its Method Card in registry.py."""
    method = "risk.member_disengagement_risk"
    if model != "logistic_l2":
        raise ValueError(
            "only 'logistic_l2' is available in this engine; see risk.late_payment_risk for why"
        )
    as_of = getattr(window, "end", None)
    rows, censored = _member_rows(spells, features, window, float(horizon_days))
    n = len(rows)
    phash = params_hash(method, 1, {
        "window_start": getattr(window, "start", None), "window_end": as_of,
        "horizon_days": horizon_days, "model": model, "calibrator": calibrator,
        "folds": folds, "seed": seed,
    })
    if n < MIN_ROWS:
        return insufficient(
            method, n=n, as_of=as_of, empty_value=[], params_hash=phash, n_censored=censored,
            caveats=("needs " + str(MIN_ROWS) + " member spells, has " + str(n),),
        )
    _, names = _feature_vector(features[0])
    evidence = _fit_and_gate(
        rows, method, as_of, seed=int(seed), folds=int(folds), calibrator=calibrator,
        phash=phash, feature_names=names, censored=censored,
        extra_assumptions=(
            "A member still active and not observed for the full horizon is censored, not "
            "counted as retained.",
        ),
        extra_caveats=(
            "a structural exit, graduation for instance, is not disengagement, and this model "
            "cannot tell them apart",
        ),
    )
    return evidence


def survival_consistency_check(predicted_rate: float, km_rate: float, km_lo: float,
                               km_hi: float) -> Check:
    """
    The cross-service invariant: the model's aggregate predicted lapse rate must
    agree with `survival.churn_curve` at the same horizon, within its Greenwood
    band.

    Two of our own services disagreeing is a bug, and a platform whose selling
    point is correctness should catch that automatically. Non-blocking, since a
    genuine covariate effect can create a legitimate gap, but always shown. This
    is an internal invariant rather than external truth and is labelled so.
    """
    agrees = km_lo <= predicted_rate <= km_hi
    return Check(
        id="survival-consistency",
        label="The model agrees with the Kaplan-Meier churn curve at the same horizon",
        status="PASS" if agrees else "WARN",
        statistic=predicted_rate - km_rate,
        detail="" if agrees else (
            "the model predicts an aggregate lapse rate of "
            + ("%.1f%%" % (100 * predicted_rate)) + " where the churn curve says "
            + ("%.1f%%" % (100 * km_rate)) + " with a band of "
            + ("%.1f%%" % (100 * km_lo)) + " to " + ("%.1f%%" % (100 * km_hi))
            + "; two of our own services disagreeing is worth reading before either is trusted"
        ),
    )


__all__ = [
    "late_payment_risk",
    "member_disengagement_risk",
    "survival_consistency_check",
]
