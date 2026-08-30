"""
Tests for the calibrated risk services.

**These services are gated, not validated, and that distinction is the point.**
There is no external published ground truth for "how likely is this household to
pay late", and inventing a benchmark would be exactly the dishonesty the catalog
exists to prevent. What is externally grounded is every component: the
calibration map, the Brier decomposition, the conformal interval and the drift
statistic each have their own known-answer tests in their own modules.

So what is asserted here is:

1. **Recovery from a known generating process.** A synthetic logistic model with
   stated coefficients must be recovered in the sense that matters for a ranking
   product: the features that drive the outcome come out on top, and the model
   beats climatology on Brier skill. This is a construction, not an external
   truth, and it is labelled as one.
2. **The gates fire.** Every blocking check is tested in its failing direction,
   because a gate only tested when it passes is not a gate.
3. **The failure mode is conservative.** Any blocking failure suppresses the
   individual scores entirely and falls back to per-stratum empirical rates.
   A committee will act on an individual score against a named household.
"""
import math
import random
from datetime import datetime, timedelta, timezone

import pytest

from app.stats import risk
from app.stats.calibration import auc, brier, expected_calibration_error
from app.stats.contracts import Evidence
from app.stats.streams import (
    DueSpell,
    EngagementFeatures,
    MemberSpell,
    StreamWindow,
)

START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2025, 1, 1, tzinfo=timezone.utc)
WINDOW = StreamWindow(start=START, end=END, timezone="Asia/Kolkata", complete_through=END)


def logistic_dues(n=900, seed=5, *, signal=True, blocks=4):
    """
    A known logistic generating process:

        logit(p) = -1.0 + 0.020 * recency_days - 0.10 * frequency_90d

    so `recency_days` and `frequency_90d` are the two features that matter and
    the rest are noise. With `signal=False` the label is independent of every
    feature, which is the fixture the gate has to reject.
    """
    rng = random.Random(seed)
    dues, features = [], []
    for i in range(n):
        recency = rng.uniform(0.0, 120.0)
        frequency = rng.randint(0, 20)
        tenure = rng.uniform(30.0, 2000.0)
        if signal:
            eta = -1.0 + 0.020 * recency - 0.10 * frequency
            p = 1.0 / (1.0 + math.exp(-eta))
        else:
            p = 0.3
        late = rng.random() < p
        due_at = START + timedelta(days=30 + (i % 300))
        strata = {"block": "B" + str(i % blocks)}
        features.append(EngagementFeatures(
            member_ref="m" + str(i), recency_days=recency, frequency_90d=frequency,
            breadth=2, volunteer_hours_365d=0.0, tenure_days=tenure,
            contribution_minor=100000, strata=strata,
        ))
        dues.append(DueSpell(
            due_ref="d" + str(i), member_ref="m" + str(i), issued_at=START, due_at=due_at,
            amount_minor=1000, at_risk_from=START,
            settled_at=due_at + timedelta(days=5 if late else -2),
            duration_days=5.0 if late else -2.0, event_observed=True, censoring="none",
            strata=strata,
        ))
    return dues, features


def _report(evidence) -> dict:
    """Pull the calibration figures back out of the caveat the service writes."""
    for caveat in evidence.caveats:
        if caveat.startswith("calibration report: "):
            out = {}
            for part in caveat.replace("calibration report: ", "").split(", "):
                if part.startswith("Brier "):
                    out["brier"] = float(part.split()[1])
                elif part.startswith("skill score "):
                    out["skill"] = float(part.split()[-1])
                elif part.startswith("expected calibration error "):
                    out["ece"] = float(part.split()[-1])
                elif part.startswith("AUC "):
                    out["auc"] = float(part.split()[1])
            return out
    return {}


# ---------------------------------------------------------------------------
# Recovery from a known generating process (a construction, labelled as one)
# ---------------------------------------------------------------------------


def test_the_model_recovers_the_features_that_drive_the_known_generator():
    """
    The generating process makes `recency_days` and `frequency_90d` the only
    features that matter. A model that ranks households must find them.
    """
    dues, features = logistic_dues()
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    assert evidence.render_state == "estimate"
    top = evidence.value[0]["top_features"]
    assert "recency_days" in top
    assert "frequency_90d" in top


def test_the_model_beats_climatology_on_the_known_generator():
    """
    The gate metric, on a fixture where a real signal exists. Brier skill has to
    be positive and the calibration error under the pack threshold.
    """
    dues, features = logistic_dues()
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    gate = next(c for c in evidence.checks if c.id == "calibration-gate")
    assert gate.status == "PASS"
    report = _report(evidence)
    assert report["skill"] > 0.05
    assert report["ece"] < 0.05
    assert report["auc"] > 0.65


def test_the_calibration_error_is_measured_out_of_fold_and_is_not_zero():
    """
    Regression test for a real bug found while building this module.

    The first version fitted the calibration map on the same out-of-fold scores
    it then scored against. Isotonic regression is flexible enough to absorb the
    noise, so the expected calibration error came out as exactly 0.0000, which
    is the number a gate reports when it is measuring nothing. The map is now
    fitted on the other folds, and a genuine held-out calibration error is
    small but never identically zero.
    """
    dues, features = logistic_dues()
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    report = _report(evidence)
    assert report["ece"] > 0.0
    assert report["ece"] < 0.05


# ---------------------------------------------------------------------------
# The gates, in their failing direction
# ---------------------------------------------------------------------------


def test_a_model_with_no_signal_is_suppressed_and_the_stratum_rates_are_shown():
    """
    The calibration gate. When the label is independent of every feature, the
    model cannot beat "everyone is at the average risk", so no individual score
    is published at all.
    """
    dues, features = logistic_dues(signal=False, seed=9)
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    gate = next(c for c in evidence.checks if c.id == "calibration-gate")
    assert gate.status == "FAIL"
    assert gate.blocking is True
    # What is served is per-stratum rates, and nothing names an individual.
    assert all("stratum" in row for row in evidence.value)
    assert not any("member_ref" in row for row in evidence.value)
    assert evidence.render_state == "not_interpretable"


def test_temporal_leakage_blocks_the_individual_scores():
    """
    `leakage-temporal`. A feature timestamped after the outcome window opened
    makes a model that looks excellent in backtest and is useless in production.
    """
    dues, features = logistic_dues(n=600)
    # Stamp every feature well after its due date.
    leaked = [
        EngagementFeatures(
            member_ref=f.member_ref, recency_days=f.recency_days,
            frequency_90d=f.frequency_90d, breadth=f.breadth,
            volunteer_hours_365d=f.volunteer_hours_365d, tenure_days=f.tenure_days,
            contribution_minor=f.contribution_minor, strata=f.strata,
        ) for f in features
    ]
    for f in leaked:
        object.__setattr__(f, "as_of", END)
    evidence = risk.late_payment_risk(dues, leaked, WINDOW, seed=1)
    check = next(c for c in evidence.checks if c.id == "leakage-temporal")
    assert check.status == "FAIL"
    assert check.blocking is True
    assert check.statistic > 0
    assert all("stratum" in row for row in evidence.value)


def test_too_few_late_outcomes_blocks_the_model():
    """`class-balance`: fewer than 40 positives and no individual model is fitted."""
    rng = random.Random(3)
    dues, features = [], []
    for i in range(500):
        late = i < 15
        due_at = START + timedelta(days=30 + (i % 200))
        features.append(EngagementFeatures(
            member_ref="m" + str(i), recency_days=rng.uniform(0, 100), frequency_90d=3,
            breadth=1, volunteer_hours_365d=0.0, tenure_days=500.0,
            contribution_minor=100000, strata={"block": "B" + str(i % 3)},
        ))
        dues.append(DueSpell(
            due_ref="d" + str(i), member_ref="m" + str(i), issued_at=START, due_at=due_at,
            amount_minor=1000, at_risk_from=START,
            settled_at=due_at + timedelta(days=5 if late else -2),
            duration_days=5.0 if late else -2.0, event_observed=True, censoring="none",
            strata={"block": "B" + str(i % 3)},
        ))
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    check = next(c for c in evidence.checks if c.id == "class-balance")
    assert check.status == "FAIL"
    assert check.blocking is True
    assert all("stratum" in row for row in evidence.value)


def test_the_fallback_rows_each_carry_their_own_n_and_wilson_interval():
    """
    The Evidence contract's table rule survives the fallback: a stratum resting
    on eleven households must not look like one resting on two hundred.
    """
    dues, features = logistic_dues(signal=False, seed=11)
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    for row in evidence.value:
        assert row["n"] > 0
        assert row["lo"] <= row["rate"] <= row["hi"]
        assert 0.0 <= row["lo"] and row["hi"] <= 1.0
    assert sum(row["n"] for row in evidence.value) == evidence.n


def test_thin_strata_are_pooled_rather_than_published():
    """A per-block figure over three households is a disclosure, not a statistic."""
    rng = random.Random(21)
    dues, features = [], []
    for i in range(400):
        block = "B0" if i < 396 else "tiny" + str(i)
        due_at = START + timedelta(days=30 + (i % 200))
        strata = {"block": block}
        features.append(EngagementFeatures(
            member_ref="m" + str(i), recency_days=rng.uniform(0, 100), frequency_90d=2,
            breadth=1, volunteer_hours_365d=0.0, tenure_days=400.0,
            contribution_minor=100000, strata=strata,
        ))
        dues.append(DueSpell(
            due_ref="d" + str(i), member_ref="m" + str(i), issued_at=START, due_at=due_at,
            amount_minor=1000, at_risk_from=START,
            settled_at=due_at + timedelta(days=-1), duration_days=-1.0,
            event_observed=True, censoring="none", strata=strata,
        ))
    rows = risk._stratum_rates(risk._due_rows(dues, features, WINDOW, 30.0)[0], k=5)
    names = {row["stratum"] for row in rows}
    assert not any(name.startswith("tiny") for name in names)
    assert all(row["n"] >= 4 for row in rows)


# ---------------------------------------------------------------------------
# Censoring: the rule this whole platform exists to get right
# ---------------------------------------------------------------------------


def test_a_due_unpaid_inside_the_horizon_is_censored_not_called_paid_on_time():
    """
    Spine rule L1, and the check the catalog names explicitly.

    Labelling an unresolved due "paid on time" is the same defect as dropping
    open tickets: it biases the model towards optimism by exactly the amount
    that matters. The rows are censored out of the training set and counted.
    """
    dues, features = logistic_dues(n=600, seed=13)
    unresolved = []
    for i, due in enumerate(dues):
        if i % 3 == 0:
            # Unpaid, and its due date is inside the horizon of the window end.
            unresolved.append(DueSpell(
                due_ref=due.due_ref, member_ref=due.member_ref, issued_at=due.issued_at,
                due_at=END - timedelta(days=5), amount_minor=due.amount_minor,
                at_risk_from=due.at_risk_from, settled_at=None, duration_days=5.0,
                event_observed=False, censoring="right", strata=due.strata,
            ))
        else:
            unresolved.append(due)
    rows, censored = risk._due_rows(unresolved, features, WINDOW, 30.0)
    assert censored == 200
    assert len(rows) == 400
    evidence = risk.late_payment_risk(unresolved, features, WINDOW, seed=1)
    assert evidence.n_censored == 200
    check = next(c for c in evidence.checks if c.id == "censoring-handled")
    assert check.status == "PASS"
    assert check.statistic == 200.0


def test_an_unpaid_due_past_the_horizon_is_a_genuine_late_outcome():
    """
    Past the horizon the outcome IS known: it was not paid. Censoring is about
    what has not been observed yet, not about everything unresolved.
    """
    _, features = logistic_dues(n=300, seed=14)
    dues = [
        DueSpell(
            due_ref="d" + str(i), member_ref="m" + str(i), issued_at=START,
            due_at=START + timedelta(days=10), amount_minor=1000, at_risk_from=START,
            settled_at=None, duration_days=300.0, event_observed=False, censoring="right",
            strata={"block": "B0"},
        ) for i in range(300)
    ]
    rows, censored = risk._due_rows(dues, features, WINDOW, 30.0)
    assert censored == 0
    assert len(rows) == 300
    assert all(row.label == 1.0 for row in rows)


# ---------------------------------------------------------------------------
# AUC gates nothing
# ---------------------------------------------------------------------------


def test_auc_is_reported_but_never_gates():
    """
    The rule stated in the module docstring, asserted on the envelope: the AUC
    appears in the calibration report, and no check has AUC as its statistic.
    """
    dues, features = logistic_dues()
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    report = _report(evidence)
    assert "auc" in report
    assert any("AUC is reported and gates nothing" in c for c in evidence.caveats)
    gate = next(c for c in evidence.checks if c.id == "calibration-gate")
    assert gate.statistic == pytest.approx(report["skill"], abs=1e-3)


# ---------------------------------------------------------------------------
# The interval
# ---------------------------------------------------------------------------


def test_each_member_row_carries_a_bounded_interval_on_its_probability():
    dues, features = logistic_dues()
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    assert evidence.interval_kind == "conformal-90"
    for row in evidence.value:
        assert 0.0 <= row["lo"] <= row["probability"] <= row["hi"] <= 1.0
    widths = sorted(row["hi"] - row["lo"] for row in evidence.value)
    median_width = widths[len(widths) // 2]
    # Wide enough to be honest, narrow enough to be worth showing.
    assert 0.0 < median_width < 0.5
    assert any("uncertainty in the estimate, not the coin flip" in c for c in evidence.caveats)


def test_the_rows_are_ranked_by_probability():
    dues, features = logistic_dues()
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    probabilities = [row["probability"] for row in evidence.value]
    assert probabilities == sorted(probabilities, reverse=True)


# ---------------------------------------------------------------------------
# Determinism, floors and refusals
# ---------------------------------------------------------------------------


def test_the_service_is_deterministic_given_its_seed():
    dues, features = logistic_dues()
    first = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    second = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    assert first.params_hash == second.params_hash
    assert [r["probability"] for r in first.value] == [r["probability"] for r in second.value]


def test_below_the_row_floor_no_model_is_fitted():
    dues, features = logistic_dues(n=120)
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    assert evidence.insufficient_data is True
    assert evidence.render_state == "not_enough_data"
    assert any("per-stratum empirical rates" in c for c in evidence.caveats)


def test_a_model_this_engine_cannot_fit_is_named_rather_than_substituted():
    dues, features = logistic_dues(n=400)
    with pytest.raises(ValueError) as error:
        risk.late_payment_risk(dues, features, WINDOW, seed=1, model="gbdt")
    assert "logistic_l2" in str(error.value)


def test_an_unknown_calibrator_is_refused():
    dues, features = logistic_dues(n=400)
    with pytest.raises(ValueError):
        risk.late_payment_risk(dues, features, WINDOW, seed=1, calibrator="beta")


# ---------------------------------------------------------------------------
# Disengagement risk and the cross-service invariant
# ---------------------------------------------------------------------------


def member_spells(n=800, seed=17, *, signal=True):
    rng = random.Random(seed)
    spells, features = [], []
    for i in range(n):
        recency = rng.uniform(0.0, 200.0)
        frequency = rng.randint(0, 15)
        eta = -0.8 + 0.012 * recency - 0.12 * frequency if signal else -0.8
        p = 1.0 / (1.0 + math.exp(-eta))
        lapsed = rng.random() < p
        strata = {"cohort": "C" + str(i % 3)}
        features.append(EngagementFeatures(
            member_ref="u" + str(i), recency_days=recency, frequency_90d=frequency,
            breadth=2, volunteer_hours_365d=rng.uniform(0, 20), tenure_days=rng.uniform(60, 3000),
            contribution_minor=50000, strata=strata,
        ))
        spells.append(MemberSpell(
            member_ref="u" + str(i), entered_at=START, at_risk_from=START,
            left_truncated=False,
            exited_at=START + timedelta(days=40) if lapsed else None,
            exit_kind="lapse" if lapsed else None,
            event_observed=lapsed,
            duration_days=40.0 if lapsed else 200.0,
            strata_at_entry=strata,
        ))
    return spells, features


def test_disengagement_risk_recovers_its_known_generator():
    spells, features = member_spells(n=2000)
    evidence = risk.member_disengagement_risk(spells, features, WINDOW, seed=2)
    assert isinstance(evidence, Evidence)
    gate = next(c for c in evidence.checks if c.id == "calibration-gate")
    assert gate.status == "PASS"
    assert evidence.value[0]["probability"] >= evidence.value[-1]["probability"]
    report = _report(evidence)
    assert report["skill"] > 0.05
    assert report["auc"] > 0.65


def test_the_gate_refuses_a_real_signal_it_cannot_yet_calibrate():
    """
    The conservative failure mode, documented rather than tuned away.

    At n = 800 this generator carries a genuine signal (Brier skill about 0.12,
    AUC about 0.70) but the out-of-fold isotonic map is still noisy enough that
    the expected calibration error lands just over the 0.05 threshold. The gate
    refuses to publish individual scores.

    That is the intended behaviour and the threshold was NOT loosened to make it
    pass. The calibration error falls to about 0.015 by n = 3000, so the service
    starts publishing once it can actually demonstrate calibration. A committee
    acting on a named household deserves the stricter reading.
    """
    spells, features = member_spells(n=800, seed=17)
    evidence = risk.member_disengagement_risk(spells, features, WINDOW, seed=2)
    gate = next(c for c in evidence.checks if c.id == "calibration-gate")
    assert gate.status == "FAIL"
    assert gate.blocking is True
    assert all("stratum" in row for row in evidence.value)
    # And with more history the same generator passes.
    bigger, bigger_features = member_spells(n=3000, seed=17)
    passing = risk.member_disengagement_risk(bigger, bigger_features, WINDOW, seed=2)
    assert next(c for c in passing.checks if c.id == "calibration-gate").status == "PASS"


def test_disengagement_risk_is_suppressed_when_there_is_no_signal():
    spells, features = member_spells(signal=False, seed=23)
    evidence = risk.member_disengagement_risk(spells, features, WINDOW, seed=2)
    gate = next(c for c in evidence.checks if c.id == "calibration-gate")
    assert gate.status == "FAIL"
    assert all("stratum" in row for row in evidence.value)


def test_survival_consistency_warns_when_two_of_our_services_disagree():
    """
    The cross-service invariant. This is an internal check rather than external
    truth and is labelled so in the Method Card: two of our own services
    disagreeing is a bug, and a platform whose selling point is correctness
    should catch it automatically rather than wait for a reader to notice.
    """
    agreeing = risk.survival_consistency_check(0.22, 0.20, 0.17, 0.24)
    assert agreeing.status == "PASS"
    disagreeing = risk.survival_consistency_check(0.45, 0.20, 0.17, 0.24)
    assert disagreeing.status == "WARN"
    assert "churn curve" in disagreeing.detail
    assert disagreeing.blocking is False


def test_per_stratum_calibration_is_always_reported():
    """
    A model well calibrated overall can be badly miscalibrated for one block,
    and the people in that block are the ones who would be acted against.
    """
    dues, features = logistic_dues()
    evidence = risk.late_payment_risk(dues, features, WINDOW, seed=1)
    check = next(c for c in evidence.checks if c.id == "protected-strata-parity")
    assert check.statistic is not None
    assert check.status in ("PASS", "WARN")


def test_both_risk_services_return_envelopes_that_never_leak_a_bare_number():
    dues, features = logistic_dues(n=400)
    spells, member_features = member_spells(n=400)
    envelopes = [
        risk.late_payment_risk(dues, features, WINDOW, seed=1),
        risk.member_disengagement_risk(spells, member_features, WINDOW, seed=1),
    ]
    for evidence in envelopes:
        assert isinstance(evidence, Evidence)
        assert evidence.method.startswith("risk.")
        assert evidence.params_hash
        assert evidence.unit == "probability"
        assert any("never a statement about a person" in c for c in evidence.caveats) or \
            evidence.render_state in ("not_interpretable", "not_enough_data")
