"""
Known-answer tests for calibration and the proper scoring rules.

Almost everything here is checked against an exact identity or an analytically
computable number, which is unusual and is the reason this module is the
foundation the risk services are gated on:

- Pool adjacent violators has a unique, hand-computable solution.
- Murphy's decomposition is an algebraic identity and must hold to machine
  precision, not to a tolerance.
- `uncertainty = base_rate * (1 - base_rate)` exactly.
- A perfectly calibrated generator has an ECE that shrinks at O(1/sqrt(n)), and
  a generator that halves its probabilities has an ECE of analytically 0.25.
- Platt's score equations are exactly zero at the fitted optimum.

The one place a reference implementation was originally named as ground truth
(`sklearn.linear_model.LogisticRegression`) has been replaced, because sklearn
is not a dependency of this package. The replacement is stronger, not weaker:
the gradient of a strictly concave log-likelihood is zero at its maximum, which
is a theorem, whereas agreement with another library is only evidence that two
implementations share their mistakes.
"""
import math
import random
from datetime import datetime, timezone

import pytest

from app.stats import calibration
from app.stats.contracts import Evidence

AS_OF = datetime(2026, 1, 1, tzinfo=timezone.utc)


def perfectly_calibrated(n=10000, seed=1):
    """p ~ Uniform(0, 1), y ~ Bernoulli(p). Calibrated by construction."""
    rng = random.Random(seed)
    probabilities = [rng.random() for _ in range(n)]
    labels = [1 if rng.random() < p else 0 for p in probabilities]
    return probabilities, labels


# ---------------------------------------------------------------------------
# Pool adjacent violators: exact
# ---------------------------------------------------------------------------


def test_pava_matches_the_hand_computed_solution():
    """
    The catalog's stated known answer, asserted exactly.

    `[1, 3, 2, 4]` violates monotonicity at the pair (3, 2), which pools to its
    mean 2.5. Nothing else moves.
    """
    assert calibration.pava([1.0, 3.0, 2.0, 4.0]) == [1.0, 2.5, 2.5, 4.0]


@pytest.mark.parametrize("values,expected", [
    ([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]),      # already monotone: unchanged
    ([4.0, 3.0, 2.0, 1.0], [2.5, 2.5, 2.5, 2.5]),      # fully reversed: one flat block
    ([1.0, 1.0, 1.0], [1.0, 1.0, 1.0]),
    ([2.0, 1.0], [1.5, 1.5]),
])
def test_pava_on_further_hand_computable_vectors(values, expected):
    assert calibration.pava(values) == expected


def test_pava_invariants_hold_on_arbitrary_seeded_input():
    """
    Two invariants of the least-squares isotonic fit: the output never
    decreases, and pooling conserves the total. Pooling that changed the sum
    would be inventing or destroying outcomes.
    """
    rng = random.Random(5)
    for _ in range(50):
        values = [rng.gauss(0.0, 1.0) for _ in range(rng.randint(2, 40))]
        fitted = calibration.pava(values)
        assert all(fitted[i] <= fitted[i + 1] + 1e-12 for i in range(len(fitted) - 1))
        assert math.fsum(fitted) == pytest.approx(math.fsum(values), abs=1e-9)


def test_isotonic_map_is_clamped_rather_than_extrapolated():
    """
    Outside the score range it saw, isotonic regression has no evidence, so the
    map is clamped. Extrapolating a slope there is how a calibration map invents
    a confident probability.
    """
    scores = [0.1, 0.2, 0.3, 0.4]
    labels = [0, 0, 1, 1]
    thresholds, values = calibration.isotonic_map(scores, labels)
    assert calibration.apply_isotonic(thresholds, values, -5.0) == values[0]
    assert calibration.apply_isotonic(thresholds, values, 5.0) == values[-1]


# ---------------------------------------------------------------------------
# Murphy's decomposition: exact identities
# ---------------------------------------------------------------------------


def _rows_for(probabilities, labels, bins=10):
    edges = calibration._bin_edges(probabilities, bins, "equal_count")
    rows = calibration._grouped(probabilities, labels, edges)
    rows, _ = calibration._merge_sparse(rows, calibration.MIN_PER_BIN)
    return calibration._recompute(rows, probabilities, labels)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_murphy_decomposition_is_an_exact_identity(seed):
    """
    Brier = reliability - resolution + uncertainty + within_bin, to machine
    precision, on arbitrary seeded input.

    The catalog originally stated the three-term form on arbitrary inputs. That
    is false for a continuous forecast: the three-term identity holds only when
    the forecast is constant within each bin. The catalog was corrected and the
    fourth term is reported in the envelope so the arithmetic can be checked by
    a reader rather than trusted.
    """
    probabilities, labels = perfectly_calibrated(n=2000, seed=seed)
    rows = _rows_for(probabilities, labels)
    d = calibration.murphy_decomposition(probabilities, labels, rows)
    reconstructed = d["reliability"] - d["resolution"] + d["uncertainty"] + d["within_bin"]
    assert abs(d["brier"] - reconstructed) < 1e-12


def test_the_three_term_identity_holds_exactly_when_the_forecast_is_binned():
    """
    The within-bin term vanishes identically when the forecast is constant
    inside each bin, which recovers the familiar three-term Murphy identity
    exactly. This is what makes the fourth term a correction rather than a fudge.
    """
    rng = random.Random(11)
    levels = [0.05, 0.25, 0.45, 0.65, 0.85]
    probabilities, labels = [], []
    for level in levels:
        for _ in range(400):
            probabilities.append(level)
            labels.append(1 if rng.random() < level else 0)
    # Equal-width bins of 0.2 put each of the five levels in a bin of its own,
    # which is the condition under which the fourth term is identically zero.
    edges = calibration._bin_edges(probabilities, 5, "equal_width")
    rows = calibration._recompute(
        calibration._grouped(probabilities, labels, edges), probabilities, labels
    )
    assert len(rows) == len(levels)
    d = calibration.murphy_decomposition(probabilities, labels, rows)
    assert abs(d["within_bin"]) < 1e-12
    assert abs(d["brier"] - (d["reliability"] - d["resolution"] + d["uncertainty"])) < 1e-12


def test_uncertainty_is_exactly_the_base_rate_variance():
    probabilities, labels = perfectly_calibrated(n=3000, seed=4)
    rows = _rows_for(probabilities, labels)
    d = calibration.murphy_decomposition(probabilities, labels, rows)
    base = d["base_rate"]
    assert d["uncertainty"] == pytest.approx(base * (1.0 - base), abs=1e-15)


def test_a_perfectly_calibrated_constant_forecaster_has_zero_reliability():
    """
    Exact: a forecaster that always says the true base rate is perfectly
    reliable, so the reliability term is 0 to machine precision.
    """
    n = 1000
    positives = 300
    labels = [1] * positives + [0] * (n - positives)
    base = positives / n
    probabilities = [base] * n
    rows = _rows_for(probabilities, labels, bins=1)
    d = calibration.murphy_decomposition(probabilities, labels, rows)
    assert abs(d["reliability"]) < 1e-15
    assert d["brier_skill_score"] == pytest.approx(0.0, abs=1e-12)


def test_brier_score_of_a_perfect_forecaster_is_zero():
    labels = [1, 0, 1, 1, 0]
    assert calibration.brier([1.0, 0.0, 1.0, 1.0, 0.0], labels) == 0.0
    assert calibration.brier([0.0, 1.0, 0.0, 0.0, 1.0], labels) == 1.0


# ---------------------------------------------------------------------------
# Expected calibration error: analytic targets
# ---------------------------------------------------------------------------


def test_ece_of_a_perfectly_calibrated_generator_converges_at_the_stated_rate():
    """
    The catalog's known answer: ECE converges to 0 at O(1/sqrt(n)), asserted
    within a tolerance derived from that rate at n = 10,000.

    The tolerance is 2 / sqrt(n), which is the rate with a constant, not a
    number chosen after seeing the output.
    """
    n = 10000
    probabilities, labels = perfectly_calibrated(n=n, seed=1)
    rows = _rows_for(probabilities, labels)
    ece, _ = calibration.expected_calibration_error(rows, n)
    assert ece < 2.0 / math.sqrt(n)


def test_a_deliberately_miscalibrated_generator_gives_the_analytic_ece():
    """
    Report p/2 when the truth is p. The expected gap is E|p - p/2| = E[p/2],
    which for p uniform on (0, 1) is exactly 0.25. Measured against that number,
    not against a previous run.
    """
    n = 10000
    probabilities, labels = perfectly_calibrated(n=n, seed=1)
    halved = [p / 2.0 for p in probabilities]
    rows = _rows_for(halved, labels)
    ece, _ = calibration.expected_calibration_error(rows, n)
    assert ece == pytest.approx(0.25, abs=0.02)


# ---------------------------------------------------------------------------
# Platt scaling
# ---------------------------------------------------------------------------


def test_platt_score_equations_are_zero_at_the_fitted_optimum():
    """
    The replacement for the catalog's original "agrees with sklearn" claim.

    At the maximum of a strictly concave log-likelihood the gradient is exactly
    zero. That is a theorem about the objective, and it is a stronger check than
    agreement with a second implementation.
    """
    rng = random.Random(9)
    n = 4000
    scores = [rng.gauss(0.0, 1.0) for _ in range(n)]
    labels = [1 if rng.random() < 1.0 / (1.0 + math.exp(-(1.5 * s - 0.3))) else 0
              for s in scores]
    a, b = calibration.platt_fit(scores, labels)
    grad_a, grad_b = calibration.platt_score_equations(scores, labels, a, b)
    assert abs(grad_a) < 1e-8
    assert abs(grad_b) < 1e-8


def test_platt_recovers_a_known_logistic_generator():
    """
    Parametric recovery. Platt's parameterisation is p = 1 / (1 + exp(a s + b)),
    so a generator p = sigmoid(1.5 s - 0.3) must be recovered as a = -1.5,
    b = +0.3.
    """
    rng = random.Random(9)
    n = 4000
    scores = [rng.gauss(0.0, 1.0) for _ in range(n)]
    labels = [1 if rng.random() < 1.0 / (1.0 + math.exp(-(1.5 * s - 0.3))) else 0
              for s in scores]
    a, b = calibration.platt_fit(scores, labels)
    assert a == pytest.approx(-1.5, abs=0.12)
    assert b == pytest.approx(0.3, abs=0.12)


def test_platt_maps_an_already_calibrated_input_to_approximately_the_identity():
    """The exact property the catalog names: calibrating calibrated input changes little."""
    rng = random.Random(21)
    n = 4000
    scores = [rng.gauss(0.0, 1.0) for _ in range(n)]
    truth = [1.0 / (1.0 + math.exp(-s)) for s in scores]
    labels = [1 if rng.random() < p else 0 for p in truth]
    a, b = calibration.platt_fit(scores, labels)
    calibrated = [calibration.apply_platt(a, b, s) for s in scores]
    assert max(abs(c - t) for c, t in zip(calibrated, truth)) < 0.05


def test_platt_target_correction_keeps_a_separable_fit_finite():
    """
    Without Platt's prior correction, perfectly separable classes drive the
    slope to infinity and the map returns exactly 0 and exactly 1, which are the
    two probabilities no honest model emits.
    """
    scores = [float(i) for i in range(100)]
    labels = [0] * 50 + [1] * 50
    a, b = calibration.platt_fit(scores, labels)
    calibrated = [calibration.apply_platt(a, b, s) for s in scores]
    assert all(0.0 < p < 1.0 for p in calibrated)
    assert math.isfinite(a) and math.isfinite(b)


# ---------------------------------------------------------------------------
# AUC measures ranking, which is exactly why it gates nothing
# ---------------------------------------------------------------------------


def test_auc_is_blind_to_miscalibration_which_is_why_it_gates_nothing():
    """
    The argument for the whole module, made as a test.

    Halving every probability is a monotone transform, so AUC is unchanged to
    machine precision, while the Brier score and the ECE both get worse. A
    platform that gated on AUC would ship the halved model.
    """
    probabilities, labels = perfectly_calibrated(n=4000, seed=2)
    halved = [p / 2.0 for p in probabilities]
    assert calibration.auc(halved, labels) == pytest.approx(
        calibration.auc(probabilities, labels), abs=1e-12
    )
    assert calibration.brier(halved, labels) > calibration.brier(probabilities, labels)


def test_auc_of_a_perfect_ranker_is_one_and_of_a_coin_flip_is_a_half():
    assert calibration.auc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert calibration.auc([0.5, 0.5, 0.5, 0.5], [1, 1, 0, 0]) == 0.5


# ---------------------------------------------------------------------------
# The services and their gates
# ---------------------------------------------------------------------------


def test_brier_decomposition_service_reports_the_identity_it_claims():
    probabilities, labels = perfectly_calibrated(n=2000, seed=6)
    evidence = calibration.brier_decomposition(probabilities, labels, AS_OF, seed=3)
    assert isinstance(evidence, Evidence)
    value = evidence.value
    reconstructed = (value["reliability"] - value["resolution"] + value["uncertainty"]
                     + value["within_bin"])
    assert abs(value["brier"] - reconstructed) < 1e-12
    assert evidence.interval is not None
    assert evidence.interval[0] <= value["brier"] <= evidence.interval[1]
    assert evidence.interval_kind == "bootstrap-bca-95"


def test_a_negative_brier_skill_score_suppresses_the_figure():
    """
    The gate: a model worse than saying "everyone is at the average risk" does
    not ship, and the blocking failure empties the value rather than merely
    flagging it.
    """
    rng = random.Random(8)
    n = 2000
    labels = [1 if rng.random() < 0.3 else 0 for _ in range(n)]
    # Deliberately anti-informative: high probability exactly when the outcome did not happen.
    probabilities = [0.05 if y else 0.95 for y in labels]
    evidence = calibration.brier_decomposition(probabilities, labels, AS_OF, seed=1)
    gate = next(c for c in evidence.checks if c.id == "bss-positive")
    assert gate.status == "FAIL"
    assert gate.blocking is True
    assert evidence.value["brier_skill_score"] is None
    assert evidence.render_state == "not_interpretable"


def test_a_well_calibrated_informative_model_passes_the_gate():
    probabilities, labels = perfectly_calibrated(n=4000, seed=12)
    evidence = calibration.brier_decomposition(probabilities, labels, AS_OF, seed=1)
    gate = next(c for c in evidence.checks if c.id == "bss-positive")
    assert gate.status == "PASS"
    assert evidence.value["brier_skill_score"] > 0.0


def test_reliability_diagram_rows_each_carry_their_own_n_and_interval():
    """The Evidence contract's table rule, asserted rather than assumed."""
    probabilities, labels = perfectly_calibrated(n=4000, seed=13)
    evidence = calibration.reliability_diagram(probabilities, labels, AS_OF)
    assert evidence.value, "a calibrated model should produce a readable diagram"
    for row in evidence.value:
        assert row["n"] >= calibration.MIN_PER_BIN
        assert row["lo"] <= row["observed_rate"] <= row["hi"]
        assert 0.0 <= row["lo"] <= 1.0 and 0.0 <= row["hi"] <= 1.0
    assert sum(row["n"] for row in evidence.value) == len(labels)


def test_reliability_diagram_blocks_above_the_ece_threshold():
    """
    ECE above the pack threshold of 0.05 blocks a served risk score entirely.
    The halved generator has an ECE of about 0.25, five times the threshold.
    """
    probabilities, labels = perfectly_calibrated(n=4000, seed=14)
    halved = [p / 2.0 for p in probabilities]
    evidence = calibration.reliability_diagram(halved, labels, AS_OF)
    check = next(c for c in evidence.checks if c.id == "ece-threshold")
    assert check.status == "FAIL"
    assert check.blocking is True
    assert check.statistic > calibration.ECE_THRESHOLD
    assert evidence.value == []
    assert evidence.render_state == "not_interpretable"


def test_thin_bins_are_merged_rather_than_shown():
    """k-anonymity is a floor, not a setting: a bin of three households is a disclosure."""
    rng = random.Random(15)
    n = 400
    probabilities = [0.5 for _ in range(n - 3)] + [0.999, 0.998, 0.997]
    labels = [1 if rng.random() < p else 0 for p in probabilities]
    evidence = calibration.reliability_diagram(probabilities, labels, AS_OF, k_anonymity=25)
    assert all(row["n"] >= 25 for row in evidence.value)


def test_isotonic_below_its_floor_returns_the_calm_empty_state():
    rng = random.Random(2)
    n = 150
    scores = [rng.random() for _ in range(n)]
    labels = [1 if rng.random() < s else 0 for s in scores]
    evidence = calibration.isotonic_calibrate(scores, labels, AS_OF)
    assert evidence.insufficient_data is True
    assert evidence.render_state == "not_enough_data"
    assert any("Platt" in c for c in evidence.caveats)


def test_isotonic_service_produces_a_monotone_map():
    rng = random.Random(3)
    n = 800
    scores = [rng.random() for _ in range(n)]
    labels = [1 if rng.random() < s else 0 for s in scores]
    evidence = calibration.isotonic_calibrate(scores, labels, AS_OF)
    assert evidence.insufficient_data is False
    values = evidence.value["values"]
    assert all(values[i] <= values[i + 1] + 1e-12 for i in range(len(values) - 1))
    monotone = next(c for c in evidence.checks if c.id == "monotone-output")
    assert monotone.status == "PASS"


def test_fitting_in_fold_is_flagged_rather_than_silently_allowed():
    rng = random.Random(4)
    n = 800
    scores = [rng.random() for _ in range(n)]
    labels = [1 if rng.random() < s else 0 for s in scores]
    evidence = calibration.isotonic_calibrate(scores, labels, AS_OF, out_of_fold=False)
    check = next(c for c in evidence.checks if c.id == "out-of-fold")
    assert check.status == "WARN"
    assert evidence.render_state == "qualified"


def test_isotonic_calibration_actually_improves_calibration():
    """
    The point of the map, measured: applying it to a miscalibrated score must
    reduce the Brier score. A calibration step that does not improve calibration
    is decoration.
    """
    rng = random.Random(31)
    n = 4000
    scores = [rng.random() for _ in range(n)]
    labels = [1 if rng.random() < s else 0 for s in scores]
    distorted = [s ** 2 for s in scores]
    thresholds, values = calibration.isotonic_map(distorted, labels)
    calibrated = [calibration.apply_isotonic(thresholds, values, s) for s in distorted]
    assert calibration.brier(calibrated, labels) < calibration.brier(distorted, labels)


def test_non_binary_labels_are_refused():
    with pytest.raises(ValueError):
        calibration.brier_decomposition([0.5] * 200, [0.5] * 200, AS_OF)


def test_every_calibration_service_returns_an_envelope():
    probabilities, labels = perfectly_calibrated(n=1000, seed=17)
    envelopes = [
        calibration.isotonic_calibrate(probabilities, labels, AS_OF),
        calibration.platt_calibrate(probabilities, labels, AS_OF),
        calibration.brier_decomposition(probabilities, labels, AS_OF),
        calibration.reliability_diagram(probabilities, labels, AS_OF),
    ]
    for evidence in envelopes:
        assert isinstance(evidence, Evidence)
        assert evidence.method.startswith("calibration.")
        assert evidence.params_hash
        assert evidence.n == 1000
