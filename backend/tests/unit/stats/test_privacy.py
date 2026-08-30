"""
Disclosure control, checked against exact rules and against a theorem.

Two things are asserted here that the rest of Pack 4 leans on.

k-anonymity must genuinely EMPTY a small row. A row that is flagged but still
carries its number is not suppressed, it is annotated, and every one of the
consumers in this pack passes its table through here as the last step.

The Laplace mechanism must match Laplace(0, sensitivity/epsilon). Its
correctness is a theorem rather than a published table, so the tests check the
theorem: the empirical distribution against the analytic CDF by KS, the
unbiasedness at the known rate, exact composition, and reproducibility.
"""
import math
from datetime import datetime, timezone

from app.stats import privacy
from app.stats.contracts import Evidence

AS_OF = datetime(2026, 8, 30, tzinfo=timezone.utc)


def _table(rows, n) -> Evidence:
    return Evidence(value=list(rows), n=n, method="test.table", as_of=AS_OF)


# ---------------------------------------------------------------------------
# k-anonymity
# ---------------------------------------------------------------------------


def test_a_row_below_k_is_emptied_not_merely_flagged():
    """
    The gate. A suppressed row must not still contain the figure, because a CSV
    export, a mis-wired client or an agent tool would read it straight out.
    """
    rows = [
        {"stratum": "Block A", "n_voters": 40, "share": 0.40},
        {"stratum": "Block B", "n_voters": 57, "share": 0.57},
        {"stratum": "Block C", "n_voters": 3, "share": 0.03},
    ]
    out = privacy.k_anonymity_suppress(_table(rows, 100), k=5, cell_counts=[40, 57, 3])

    block_c = [r for r in out.value if r["stratum"] == "Block C"][0]
    assert block_c["suppressed"] is True
    assert block_c["n_voters"] is None
    assert block_c["share"] is None
    # The label survives. Hiding which stratum vanished helps the household not
    # at all and costs the reader the ability to see that one did.
    assert block_c["stratum"] == "Block C"

    check = [c for c in out.checks if c.id == "k-anonymity-rows"][0]
    assert check.status == "FAIL"


def test_secondary_suppression_fires_because_the_envelope_publishes_n():
    """
    Counts (40, 57, 3) with a published total of 100. Hiding only Block C hides
    nothing: 100 - 40 - 57 = 3. A second row must go.
    """
    rows = [
        {"stratum": "A", "value": 1.0},
        {"stratum": "B", "value": 2.0},
        {"stratum": "C", "value": 3.0},
    ]
    out = privacy.k_anonymity_suppress(_table(rows, 100), k=5, cell_counts=[40, 57, 3])
    hidden = [r["stratum"] for r in out.value if r["suppressed"]]
    assert len(hidden) >= 2
    assert "C" in hidden
    # The cheapest extra row to lose is the smallest published one.
    assert "A" in hidden

    note = [c for c in out.checks if c.id == "complementary-suppression"][0]
    assert note.status == "PASS"
    assert note.statistic == 1.0


def test_the_leak_fixture_two_hidden_cells_are_not_automatically_safe():
    """
    The test that matters, and the one a naive implementation fails.

    Counts (20, 4, 4), k = 5, published total 28. Both small cells are hidden,
    so a rule of "at least two suppressed cells" declares victory. It is wrong:
    the residual is 8, an attacker knows each hidden cell is below 5, and
    8 = 4 + 4 is the only split. Both cells are recovered exactly.
    """
    counts = [20, 4, 4]
    rows = [{"stratum": s, "value": float(c)} for s, c in zip("ABC", counts)]

    # First, the arithmetic that makes it a leak, stated independently of the code.
    residual = 28 - 20
    assert residual == 8
    assert 8 - (5 - 1) == 4, "the other cell's bound pins this one at exactly 4"

    out = privacy.k_anonymity_suppress(_table(rows, 28), k=5, cell_counts=counts)
    hidden = {r["stratum"] for r in out.value if r["suppressed"]}
    assert hidden == {"A", "B", "C"}, (
        "with only three strata the large one has to go too, otherwise both small "
        "cells are readable by subtraction"
    )
    note = [c for c in out.checks if c.id == "complementary-suppression"][0]
    assert note.statistic == 1.0


def test_the_leak_fixture_is_solved_by_one_unbounded_row_when_one_is_available():
    """
    The same leak with a fourth stratum. Hiding one large cell removes the upper
    bound that did the pinning, so the whole table need not go.
    """
    counts = [20, 30, 4, 4]
    rows = [{"stratum": s, "value": float(c)} for s, c in zip("ABCD", counts)]
    out = privacy.k_anonymity_suppress(_table(rows, 58), k=5, cell_counts=counts)
    hidden = {r["stratum"] for r in out.value if r["suppressed"]}
    assert hidden == {"A", "C", "D"}
    assert not out.blocking_failures, "the table is publishable, just smaller"


def test_a_single_row_table_below_k_is_suppressed_entirely_and_blocks():
    rows = [{"stratum": "only", "value": 9.0}]
    out = privacy.k_anonymity_suppress(_table(rows, 3), k=5, cell_counts=[3])
    assert out.value[0]["value"] is None
    note = [c for c in out.checks if c.id == "complementary-suppression"][0]
    assert note.status == "FAIL" and note.blocking is True
    assert out.render_state == "not_interpretable"


def test_a_table_that_clears_k_everywhere_passes_through_unchanged():
    rows = [{"stratum": "A", "value": 1.0}, {"stratum": "B", "value": 2.0}]
    out = privacy.k_anonymity_suppress(_table(rows, 100), k=5, cell_counts=[60, 40])
    assert [r["value"] for r in out.value] == [1.0, 2.0]
    assert all(r["suppressed"] is False for r in out.value)
    assert out.worst_status == "PASS"


def test_existing_checks_and_caveats_survive_the_filter():
    """It is a filter on top of an estimate, not a replacement for it."""
    from app.stats.contracts import Check

    inner = Evidence(
        value=[{"stratum": "A", "value": 1.0}, {"stratum": "B", "value": 2.0}],
        n=100,
        method="test.table",
        as_of=AS_OF,
        checks=(Check(id="upstream", label="Something the estimator measured", status="WARN"),),
        caveats=("an upstream caveat",),
        unit="share",
    )
    out = privacy.k_anonymity_suppress(inner, k=5, cell_counts=[60, 40])
    assert any(c.id == "upstream" for c in out.checks)
    assert "an upstream caveat" in out.caveats
    assert out.unit == "share"


def test_a_wrapped_table_keeps_its_structure_and_gains_a_suppression_record():
    inner = Evidence(
        value={"rows": [{"stratum": "A", "value": 1.0}, {"stratum": "B", "value": 2.0}],
               "total": 100},
        n=100,
        method="test.table",
        as_of=AS_OF,
    )
    out = privacy.k_anonymity_suppress(inner, k=5, cell_counts=[97, 3])
    assert out.value["total"] == 100
    assert out.value["suppression"]["n_primary"] == 1
    assert out.value["suppression"]["n_suppressed"] == 2


# ---------------------------------------------------------------------------
# The Laplace mechanism
# ---------------------------------------------------------------------------


def test_an_undeclared_sensitivity_blocks_and_publishes_nothing():
    """
    A wrong sensitivity means no guarantee at all, so an absent one must not be
    guessed. The value is None, not the true figure with a reassuring caveat.
    """
    out = privacy.laplace_noise(1234.0, AS_OF, sensitivity=None, epsilon=1.0, seed=7)
    assert out.value is None
    assert out.render_state == "not_interpretable"
    check = [c for c in out.checks if c.id == "sensitivity-declared"][0]
    assert check.status == "FAIL" and check.blocking is True


def test_a_nonpositive_epsilon_blocks():
    out = privacy.laplace_noise(1.0, AS_OF, sensitivity=1.0, epsilon=0.0, seed=7)
    assert out.value is None and out.render_state == "not_interpretable"


def test_the_noise_matches_laplace_by_kolmogorov_smirnov():
    """
    The known answer is the mechanism's definition: draws must be Laplace with
    scale sensitivity/epsilon. Compared against the analytic CDF, not against
    another sample, so nothing can be wrong in the same direction twice.
    """
    import random

    scale = 2.0 / 0.5  # sensitivity 2, epsilon 0.5
    rng = random.Random(20260830)
    draws = sorted(privacy.laplace_sample(rng, scale) for _ in range(20000))
    n = len(draws)
    d = 0.0
    for i, x in enumerate(draws):
        f = privacy.laplace_cdf(x, scale)
        d = max(d, abs((i + 1) / n - f), abs(f - i / n))
    # Kolmogorov 95% critical value is 1.358/sqrt(n) for a fully specified null.
    critical = 1.358 / math.sqrt(n)
    assert d < critical, "KS statistic " + repr(d) + " against critical " + repr(critical)


def test_the_mechanism_is_unbiased_at_the_known_rate():
    """
    Laplace has mean 0 and variance 2b^2, so the mean of m draws has standard
    error b*sqrt(2/m). The test asserts the sample mean sits inside three of
    those, which is a statement about the estimator rather than about our
    arithmetic.
    """
    import random

    scale, m = 3.0, 40000
    rng = random.Random(11)
    draws = [privacy.laplace_sample(rng, scale) for _ in range(m)]
    se = scale * math.sqrt(2.0 / m)
    assert abs(math.fsum(draws) / m) < 3.0 * se


def test_the_noised_figure_is_reproducible_from_its_seed():
    a = privacy.laplace_noise(500.0, AS_OF, sensitivity=1.0, epsilon=0.5, seed=42)
    b = privacy.laplace_noise(500.0, AS_OF, sensitivity=1.0, epsilon=0.5, seed=42)
    c = privacy.laplace_noise(500.0, AS_OF, sensitivity=1.0, epsilon=0.5, seed=43)
    assert a.value == b.value
    assert a.params_hash == b.params_hash
    assert a.value != c.value


def test_the_interval_is_the_noise_and_says_so():
    out = privacy.laplace_noise(100.0, AS_OF, sensitivity=1.0, epsilon=0.1, seed=3)
    lo, hi = out.interval
    scale = 1.0 / 0.1
    assert out.interval_kind == "dp-noise-95"
    assert abs((hi - lo) / 2.0 - scale * math.log(20.0)) < 1e-9
    assert any("noise, not sampling uncertainty" in c for c in out.caveats)


def test_a_smaller_epsilon_makes_a_wider_interval():
    tight = privacy.laplace_noise(100.0, AS_OF, sensitivity=1.0, epsilon=1.0, seed=1)
    loose = privacy.laplace_noise(100.0, AS_OF, sensitivity=1.0, epsilon=0.05, seed=1)
    assert (loose.interval[1] - loose.interval[0]) > 10 * (tight.interval[1] - tight.interval[0])


def test_epsilon_composes_by_addition_exactly():
    assert privacy.compose_epsilon([0.1, 0.2, 0.3]) == 0.6000000000000001 or (
        abs(privacy.compose_epsilon([0.1, 0.2, 0.3]) - 0.6) < 1e-12
    )
    assert abs(privacy.compose_epsilon([0.5, 0.5]) - 1.0) < 1e-12
    spent = [c.statistic for c in
             privacy.laplace_noise(1.0, AS_OF, sensitivity=1.0, epsilon=0.25, seed=1).checks
             if c.id == "budget-accounting"]
    assert spent == [0.25]


def test_clamping_is_disclosed_rather_than_silent():
    out = privacy.laplace_noise(
        0.5, AS_OF, sensitivity=1.0, epsilon=0.01, seed=5, clamp=(0.0, 1.0)
    )
    assert 0.0 <= out.value <= 1.0
    clamped = [c for c in out.checks if c.id == "clamped"][0]
    # At epsilon 0.01 the noise scale is 100, so a clip is all but certain.
    assert clamped.status == "WARN"
