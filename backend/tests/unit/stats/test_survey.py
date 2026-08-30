"""
Survey analysis: exact identities, a recovered simulation, and a gate that blocks.

Where the known answer is an identity it is asserted exactly. Cliff's delta has
a closed form as a count of dominance pairs and its relationship to the
Mann-Whitney U statistic, delta = 2U/(mn) - 1, is an algebraic identity, so both
are checked to machine precision. Iterative proportional fitting converging to
the declared margins is a theorem (Deming and Stephan 1940) and is asserted to
the declared tolerance. Kish's design effect is a closed form and is asserted to
1e-12, including the case where it is exactly 1.

The proportional-odds model has no published fixture vendored here, so it is
validated three ways instead, all of which the tests actually check: parameter
recovery from a simulation with known truth, the reduction to ordinary logistic
regression when the response has two levels, and the Brant test run in BOTH
directions. The last is the gate: on data generated with a cutpoint-varying
effect, the Brant test must fail and must empty the row.
"""
import math
import random
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.stats import survey
from app.stats.streams.signal import OrdinalResponse

AS_OF = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _responses(values, *, item_id="satisfaction", scale=(1, 5), strata=None, covariates=None):
    out = []
    for i, v in enumerate(values):
        out.append(OrdinalResponse(
            response_ref="r" + str(i), at=AS_OF, item_id=item_id,
            scale_min=scale[0], scale_max=scale[1], value=int(v),
            respondent_ref="p" + str(i),
            strata=dict((strata or {}).get(i, {})),
            covariates=dict((covariates or {}).get(i, {})),
        ))
    return out


# ---------------------------------------------------------------------------
# Cliff's delta, exactly
# ---------------------------------------------------------------------------


def test_cliffs_delta_on_a_hand_countable_pair_of_vectors():
    """
    a = (1, 2, 3), b = (2, 2). Nine pairs? No, six. a > b in two of them
    (3 > 2 twice), a < b in two (1 < 2 twice), and two are ties.
    delta = (2 - 2) / 6 = 0.
    """
    assert survey.cliffs_delta([1, 2, 3], [2, 2]) == 0.0
    # Complete dominance in each direction.
    assert survey.cliffs_delta([5, 5], [1, 1]) == 1.0
    assert survey.cliffs_delta([1, 1], [5, 5]) == -1.0


def test_the_cliffs_delta_mann_whitney_identity_holds_exactly():
    """delta = 2U/(mn) - 1 is algebra, so it must hold on every input."""
    rng = random.Random(20260830)
    for _ in range(300):
        m, n = rng.randint(2, 9), rng.randint(2, 9)
        a = [rng.randint(1, 5) for _ in range(m)]
        b = [rng.randint(1, 5) for _ in range(n)]
        u = survey.mann_whitney_u(a, b)
        assert abs(survey.cliffs_delta(a, b) - (2 * u / (m * n) - 1)) < 1e-12


# ---------------------------------------------------------------------------
# The Likert distribution and the mean that does not exist
# ---------------------------------------------------------------------------


def test_the_likert_structure_has_no_field_a_mean_could_live_in():
    """
    Prevention by type, not by discipline. A reviewer cannot forget a rule the
    shape does not permit breaking.
    """
    out = survey.likert_distribution(_responses([3] * 20 + [4] * 20), AS_OF,
                                     item_id="satisfaction", seed=1)
    assert "mean" not in out.value
    assert not any("mean" in key for key in out.value)
    assert any("no mean here and there cannot be" in c for c in out.caveats)


def test_the_likert_counts_and_median_are_exact():
    values = [1] * 5 + [2] * 5 + [4] * 15 + [5] * 15
    out = survey.likert_distribution(_responses(values), AS_OF, item_id="satisfaction", seed=1)
    assert out.value["counts_by_level"] == {1: 5, 2: 5, 3: 0, 4: 15, 5: 15}
    assert out.value["proportions"][4] == 0.375
    assert out.value["median"] == 4.0
    assert out.value["top_box"] == 0.375
    assert out.value["bottom_box"] == 0.125
    assert out.n == 40


def test_pooling_two_scales_blocks_and_publishes_nothing():
    """Happens constantly in real survey data, and a 4 out of 5 is not a 4 out of 7."""
    five = _responses([4] * 15)
    seven = [
        OrdinalResponse(response_ref="s" + str(i), at=AS_OF, item_id="satisfaction",
                        scale_min=1, scale_max=7, value=4, respondent_ref="q" + str(i))
        for i in range(15)
    ]
    out = survey.likert_distribution(five + seven, AS_OF, item_id="satisfaction", seed=1)
    check = [c for c in out.checks if c.id == "scale-consistent"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert out.value["counts_by_level"] == {}
    assert out.render_state == "not_interpretable"


def test_a_ceiling_item_is_flagged_as_unable_to_discriminate():
    out = survey.likert_distribution(_responses([5] * 30 + [4] * 5), AS_OF,
                                     item_id="satisfaction", seed=1)
    check = [c for c in out.checks if c.id == "floor-ceiling"][0]
    assert check.status == "WARN"
    assert "cannot discriminate" in check.detail


def test_a_group_below_k_is_emptied_in_the_likert_breakdown():
    values = [4] * 30 + [2] * 3
    strata = {i: {"block": "A" if i < 30 else "C"} for i in range(33)}
    out = survey.likert_distribution(
        _responses(values, strata=strata), AS_OF, item_id="satisfaction",
        group_by="block", k_anonymity=5, seed=1,
    )
    rows = {r["group"]: r for r in out.value["cliffs_delta_vs_reference"]}
    assert rows["C"]["suppressed"] is True and rows["C"]["delta"] is None
    assert rows["A"]["delta"] is not None
    assert [c for c in out.checks if c.id == "k-anonymity-cells"][0].status == "FAIL"


def test_below_twenty_responses_the_likert_item_returns_the_calm_empty_state():
    out = survey.likert_distribution(_responses([3] * 11), AS_OF, item_id="satisfaction", seed=1)
    assert out.insufficient_data is True and out.n == 11


# ---------------------------------------------------------------------------
# Ordinal logistic: recovery, reduction, and the Brant gate
# ---------------------------------------------------------------------------


def _simulate_ordinal(n, betas_by_cut, theta, seed):
    """
    Draw from P(Y <= j | x) = logistic(theta_j - x'beta_j).

    With one beta repeated the proportional-odds assumption holds by
    construction; with a different beta per cutpoint it is violated by
    construction, which is what makes the negative control a real one.
    """
    rng = random.Random(seed)
    design, y = [], []
    for _ in range(n):
        x1 = rng.gauss(0.0, 1.0)
        x2 = 1.0 if rng.random() < 0.4 else 0.0
        u = rng.random()
        level = len(theta)
        for j, cut in enumerate(theta):
            beta = betas_by_cut[j]
            eta = x1 * beta[0] + x2 * beta[1]
            if u < 1.0 / (1.0 + math.exp(-(cut - eta))):
                level = j
                break
        design.append([x1, x2])
        y.append(level)
    return design, y


TRUE_THETA = [-1.0, 0.5, 1.8]
TRUE_BETA = [0.8, -0.5]


def test_the_fit_recovers_the_parameters_it_was_generated_from():
    """
    1200 draws from a known proportional-odds model. Every coefficient and every
    cutpoint must land within three standard errors of the truth, which is a
    statement about the estimator rather than about our arithmetic.
    """
    design, y = _simulate_ordinal(1200, [TRUE_BETA] * 3, TRUE_THETA, seed=7)
    theta, beta, covariance, loglik = survey.polr_fit(design, y, 4)

    for j, truth in enumerate(TRUE_BETA):
        se = math.sqrt(covariance[j][j])
        assert abs(beta[j] - truth) < 3 * se, (j, beta[j], truth, se)
    for j, truth in enumerate(TRUE_THETA):
        assert abs(theta[j] - truth) < 0.15, (j, theta[j], truth)
    assert theta == sorted(theta), "cutpoints must come out strictly increasing"
    assert loglik < 0


def test_with_two_response_levels_the_model_reduces_to_logistic_regression():
    """
    A second, independent oracle already in this codebase. With J = 2 the
    proportional-odds model IS logistic regression, so the fitted slope must
    equal the one from `numeric.logistic_l2_fit` up to the sign convention
    (the cumulative model puts the linear predictor on the other side).
    """
    from app.stats.numeric import logistic_l2_fit

    rng = random.Random(3)
    design, y = [], []
    for _ in range(800):
        x = rng.gauss(0.0, 1.0)
        p = 1.0 / (1.0 + math.exp(-(0.4 + 1.1 * x)))
        design.append([x])
        y.append(1 if rng.random() < p else 0)

    # Y = 1 - z, so "Y <= 0" is exactly "z = 1". The cumulative model then reads
    # P(z = 1) = logistic(theta_0 - x'beta) against the logistic regression's
    # logistic(a + x'b), giving theta_0 = a and beta = -b.
    theta, beta, _, _ = survey.polr_fit(design, [1 - v for v in y], 2)
    reference = logistic_l2_fit([[1.0, row[0]] for row in design], [float(v) for v in y],
                                penalty=1e-9)
    assert abs(beta[0] - (-reference[1])) < 1e-6, (beta[0], reference[1])
    assert abs(theta[0] - reference[0]) < 1e-6, (theta[0], reference[0])


def test_the_brant_test_passes_when_proportional_odds_actually_holds():
    """The positive control. A test that always fails is not a test either."""
    design, y = _simulate_ordinal(1200, [TRUE_BETA] * 3, TRUE_THETA, seed=7)
    stat, df, p, per_covariate, slopes = survey.brant_test(design, y, 4)
    assert stat > 0, "a Wald statistic cannot be negative; a negative one is a covariance bug"
    assert df == 4, "two covariates times two spare cutpoints"
    assert p > 0.05, p
    assert all(c["p_value"] > 0.05 for c in per_covariate)


def test_the_brant_test_fails_on_a_cutpoint_varying_effect():
    """
    The negative control. x1's effect is generated as 1.6, 0.8 and 0.0 at the
    three cutpoints, exactly the satisfaction-data pattern the Method Card
    names: a covariate that moves people out of the bottom of the scale and
    does nothing at the top. x2's effect is constant and must survive.
    """
    design, y = _simulate_ordinal(
        1500, [[1.6, -0.5], [0.8, -0.5], [0.0, -0.5]], TRUE_THETA, seed=11
    )
    stat, df, p, per_covariate, slopes = survey.brant_test(design, y, 4)
    assert p < 0.001, p
    assert per_covariate[0]["p_value"] < 0.001, "x1 varies across cutpoints"
    assert per_covariate[1]["p_value"] > 0.05, "x2 does not, and must not be condemned with it"

    # And the per-cutpoint slopes recover the generating pattern.
    recovered = [-s[0] for s in slopes]
    assert recovered[0] > recovered[1] > recovered[2]
    assert abs(recovered[0] - 1.6) < 0.4 and abs(recovered[2] - 0.0) < 0.4


def _ordinal_responses(design, y, n_levels=4):
    return [
        OrdinalResponse(
            response_ref="r" + str(i), at=AS_OF, item_id="satisfaction",
            scale_min=1, scale_max=n_levels, value=y[i] + 1, respondent_ref="p" + str(i),
            covariates={"tenure": design[i][0], "owner": design[i][1]},
        )
        for i in range(len(y))
    ]


def test_a_proportional_odds_failure_blocks_the_row_and_replaces_it():
    """
    The gate, at the service level. A failing covariate's odds ratio must not be
    in the envelope at all, the check must be blocking, and the per-cutpoint
    effects must be there in its place.
    """
    design, y = _simulate_ordinal(
        1500, [[1.6, -0.5], [0.8, -0.5], [0.0, -0.5]], TRUE_THETA, seed=11
    )
    out = survey.ordinal_logistic(
        _ordinal_responses(design, y), AS_OF, item_id="satisfaction",
        covariates=("tenure", "owner"),
    )
    rows = {r["covariate"]: r for r in out.value if r["kind"] == "covariate"}

    tenure = rows["tenure"]
    assert tenure["suppressed"] is True
    assert tenure["coef"] is None and tenure["odds_ratio"] is None
    assert tenure["per_cutpoint"] is not None and len(tenure["per_cutpoint"]) == 3
    coefficients = [c["coef"] for c in tenure["per_cutpoint"]]
    assert coefficients[0] > coefficients[-1], "the effect fades up the scale, as generated"

    check = [c for c in out.checks if c.id == "proportional-odds:tenure"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert "single odds ratio would be misleading" in check.detail
    assert out.render_state == "not_interpretable"

    # The covariate that did not violate the assumption keeps its number.
    assert rows["owner"]["odds_ratio"] is not None
    assert [c for c in out.checks if c.id == "proportional-odds:owner"][0].status == "PASS"


def test_a_clean_fit_reports_odds_ratios_with_intervals_and_cutpoints():
    design, y = _simulate_ordinal(1200, [TRUE_BETA] * 3, TRUE_THETA, seed=7)
    out = survey.ordinal_logistic(
        _ordinal_responses(design, y), AS_OF, item_id="satisfaction",
        covariates=("tenure", "owner"),
    )
    rows = {r["covariate"]: r for r in out.value if r["kind"] == "covariate"}
    tenure = rows["tenure"]
    assert abs(tenure["odds_ratio"] - math.exp(TRUE_BETA[0])) < 0.2
    assert tenure["lo"] < tenure["odds_ratio"] < tenure["hi"]
    assert tenure["p_value"] < 0.001

    cutpoints = [r for r in out.value if r["kind"] == "cutpoint"]
    assert len(cutpoints) == 3
    assert [c["coef"] for c in cutpoints] == sorted(c["coef"] for c in cutpoints)
    assert out.render_state in ("estimate", "qualified")
    assert out.unit == "proportional odds ratio"


def test_separation_blocks_the_offending_row():
    """A covariate that perfectly predicts a level has an infinite coefficient."""
    design, y = _simulate_ordinal(600, [TRUE_BETA] * 3, TRUE_THETA, seed=5)
    # Force perfect separation: everyone in the top level, and only them, is an owner.
    for i in range(len(y)):
        design[i][1] = 1.0 if y[i] == 3 else 0.0
    out = survey.ordinal_logistic(
        _ordinal_responses(design, y), AS_OF, item_id="satisfaction",
        covariates=("tenure", "owner"),
    )
    check = [c for c in out.checks if c.id == "separation"][0]
    assert check.status == "FAIL" and check.blocking is True
    owner = [r for r in out.value if r["covariate"] == "owner"][0]
    assert owner["coef"] is None


def test_a_non_logit_link_is_refused_rather_than_relabelled():
    with pytest.raises(ValueError, match="LOGIT"):
        survey.ordinal_logistic([], AS_OF, item_id="x", covariates=("a",), link="probit")


def test_below_a_hundred_responses_the_ordinal_model_returns_the_calm_empty_state():
    design, y = _simulate_ordinal(40, [TRUE_BETA] * 3, TRUE_THETA, seed=1)
    out = survey.ordinal_logistic(
        _ordinal_responses(design, y), AS_OF, item_id="satisfaction", covariates=("tenure",)
    )
    assert out.insufficient_data is True
    assert "sparsest cutpoint" in out.caveats[0]


# ---------------------------------------------------------------------------
# Raking
# ---------------------------------------------------------------------------


def _strata(spec):
    """spec: list of (count, {"block": ..., "tenure": ...})"""
    out = []
    for count, cell in spec:
        out.extend([dict(cell)] * count)
    return out


def test_one_variable_raking_reproduces_the_post_stratification_weights_exactly():
    """
    With a single margin, IPF converges in one pass to the closed-form
    post-stratification weight N_h/n_h, rescaled to n. 60 respondents, 40 from
    block A and 20 from block B, against a population that is half and half:
    A's weight is 30/40 = 0.75 and B's is 30/20 = 1.5.
    """
    strata = _strata([(40, {"block": "A"}), (20, {"block": "B"})])
    out = survey.raking_weights(strata, {"block": {"A": 0.5, "B": 0.5}}, AS_OF)
    weights = [r["weight"] for r in out.value if r["kind"] == "weight"]
    assert all(abs(w - 0.75) < 1e-9 for w in weights[:40])
    assert all(abs(w - 1.5) < 1e-9 for w in weights[40:])
    assert abs(math.fsum(weights) - 60) < 1e-9


def test_iterative_proportional_fitting_reaches_the_declared_margins():
    """
    Deming and Stephan's theorem: on a consistent table IPF converges to the
    margins exactly. Asserted on several seeded random tables, since one table
    could be a coincidence.
    """
    rng = random.Random(4242)
    for trial in range(8):
        strata = []
        for block in "ABC":
            for tenure in ("owner", "tenant"):
                for _ in range(rng.randint(8, 25)):
                    strata.append({"block": block, "tenure": tenure})
        margins = {
            "block": {b: rng.uniform(0.2, 0.5) for b in "ABC"},
            "tenure": {"owner": rng.uniform(0.3, 0.7), "tenant": rng.uniform(0.3, 0.7)},
        }
        out = survey.raking_weights(strata, margins, AS_OF, tol=1e-9, trim=(0.0, 1e9))
        for row in out.value:
            if row["kind"] == "margin":
                assert abs(row["achieved"] - row["target"]) < 1e-6, (trial, row)
        assert [c for c in out.checks if c.id == "convergence"][0].status == "PASS"


def test_an_empty_cell_is_named_rather_than_the_margin_silently_dropped():
    strata = _strata([(40, {"block": "A"}), (20, {"block": "B"})])
    out = survey.raking_weights(
        strata, {"block": {"A": 0.4, "B": 0.4, "C": 0.2}}, AS_OF
    )
    check = [c for c in out.checks if c.id == "empty-cells"][0]
    assert check.status == "FAIL" and check.blocking is True
    assert "block=C" in check.detail
    assert out.value == []
    assert out.render_state == "not_interpretable"


def test_extreme_weights_are_trimmed_and_the_price_is_stated():
    """
    Two block-B respondents standing in for a third of the community would each
    carry a weight around 10. Trimming caps it, and the cost is that the margin
    is no longer met exactly, which the check says out loud.
    """
    strata = _strata([(58, {"block": "A"}), (2, {"block": "B"})])
    out = survey.raking_weights(
        strata, {"block": {"A": 0.65, "B": 0.35}}, AS_OF, trim=(0.2, 5.0)
    )
    weights = [r["weight"] for r in out.value if r["kind"] == "weight"]
    assert max(weights) <= 5.0 + 1e-9
    check = [c for c in out.checks if c.id == "extreme-weights"][0]
    assert check.status == "WARN"
    assert "speaking for forty" in check.detail
    assert "price of that cap" in check.detail


def test_below_fifty_respondents_raking_returns_the_calm_empty_state():
    out = survey.raking_weights(
        _strata([(20, {"block": "A"})]), {"block": {"A": 1.0}}, AS_OF
    )
    assert out.insufficient_data is True


# ---------------------------------------------------------------------------
# The design effect
# ---------------------------------------------------------------------------


def test_the_design_effect_is_exactly_one_for_uniform_weights():
    out = survey.design_effect([1.0] * 40, AS_OF)
    assert abs(out.value - 1.0) < 1e-12
    assert [c for c in out.checks if c.id == "uniform-weights"][0].statistic == 1.0
    # Any constant works, not only 1.
    assert abs(survey.design_effect([3.7] * 12, AS_OF).value - 1.0) < 1e-12


def test_the_design_effect_matches_its_closed_form_by_hand():
    """
    Weights (1, 1, 1, 3): n = 4, sum = 6, sum of squares = 12.
    deff = 4 * 12 / 36 = 4/3, so the effective sample size is exactly 3.
    """
    out = survey.design_effect([1.0, 1.0, 1.0, 3.0], AS_OF)
    assert abs(out.value - 4.0 / 3.0) < 1e-12
    assert abs(out.n / out.value - 3.0) < 1e-12


def test_the_design_effect_is_the_number_that_should_be_in_the_readers_head():
    """340 residents, weighted, is not 340 residents."""
    rng = random.Random(9)
    weights = [rng.choice([0.4, 0.4, 0.4, 4.0]) for _ in range(340)]
    out = survey.design_effect(weights, AS_OF)
    assert out.value > 2.0
    assert [c for c in out.checks if c.id == "design-effect-acceptable"][0].status == "WARN"
    assert "carry the precision of about" in out.caveats[0]


def test_the_design_effect_agrees_with_what_raking_reported():
    """One number, computed once. Two definitions drifting apart is the bug."""
    strata = _strata([(40, {"block": "A"}), (20, {"block": "B"})])
    raked = survey.raking_weights(strata, {"block": {"A": 0.5, "B": 0.5}}, AS_OF)
    weights = [r["weight"] for r in raked.value if r["kind"] == "weight"]
    reported = [c.statistic for c in raked.checks if c.id == "design-effect-acceptable"][0]
    assert abs(survey.design_effect(weights, AS_OF).value - reported) < 1e-12
