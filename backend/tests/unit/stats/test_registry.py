"""
Registry invariants, from docs/STATS_API.md section 7.

The load-bearing one is the last: **the catalog and the code cannot drift.**
Every service named in `docs/STATS_CATALOG.md` is in the registry and every
registered service is named there. A platform whose claim is honesty cannot have
a specification that quietly disagrees with its implementation.

Most of the other invariants are enforced at import by `ServiceSpec.__post_init__`
and by `MethodCard.__post_init__`, so this file also asserts that those guards
actually fire, rather than trusting that they would.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from app.stats import registry as R
from app.stats.contracts import Evidence, MethodCard
from app.stats.streams import STREAM_IDS, UNIT_NAMES

CATALOG = pathlib.Path(__file__).resolve().parents[3].parent / "docs" / "STATS_CATALOG.md"

_MODULE_HEADING = re.compile(r"^## `([a-z_]+)\.py`", re.MULTILINE)
_BACKTICKED = re.compile(r"`([a-z_][a-z_0-9]*\.[a-z_][a-z_0-9]*)`")


def catalog_text() -> str:
    return CATALOG.read_text(encoding="utf-8")


def catalog_modules() -> set[str]:
    return set(_MODULE_HEADING.findall(catalog_text()))


def catalog_service_ids() -> set[str]:
    """
    Every `module.function` token in the catalog whose module is one of the
    catalog's own module headings.

    Scoping to declared modules keeps references like `scipy.stats.beta` and
    `equalshares.net` out, and the separate module-set assertion below is what
    catches a whole module appearing in one place and not the other.
    """
    modules = catalog_modules()
    found = set()
    for token in _BACKTICKED.findall(catalog_text()):
        module, _, name = token.partition(".")
        if module in modules and name != "py":
            found.add(token)
    return found


# ---------------------------------------------------------------------------
# The invariants
# ---------------------------------------------------------------------------


def test_catalog_file_is_readable():
    """If this path breaks, every parity assertion below passes vacuously."""
    assert CATALOG.exists(), "expected the catalog at " + str(CATALOG)
    assert len(catalog_modules()) == 24


def test_registry_modules_match_the_catalog_modules():
    registered = {spec.module for spec in R.REGISTRY.values()}
    assert registered == catalog_modules()


def test_every_catalogued_service_is_registered():
    missing = sorted(catalog_service_ids() - set(R.REGISTRY))
    assert not missing, (
        "docs/STATS_CATALOG.md names services that app/stats/registry.py does not: "
        + ", ".join(missing)
    )


def test_every_registered_service_is_in_the_catalog():
    extra = sorted(set(R.REGISTRY) - catalog_service_ids())
    assert not extra, (
        "app/stats/registry.py registers services the catalog does not name: "
        + ", ".join(extra)
        + ". A service without a catalog entry has no known-answer test."
    )


@pytest.mark.parametrize("service_id", sorted(R.REGISTRY))
def test_every_service_has_a_complete_method_card(service_id: str):
    card = R.method_card(service_id)
    assert card.id == service_id
    assert card.assumes and card.wrong_when and card.references
    assert card.interval_meaning
    assert card.one_liner
    assert card.known_answer, (
        service_id + " has no known-answer statement. Where no external ground truth exists the "
        "card must say so, as the catalog's appendix does, rather than leaving the field blank."
    )


@pytest.mark.parametrize("service_id", sorted(R.REGISTRY))
def test_min_n_matches_the_method_card(service_id: str):
    spec = R.get(service_id)
    assert spec.min_n == spec.method_card.min_n


@pytest.mark.parametrize("service_id", sorted(R.REGISTRY))
def test_every_function_returns_evidence(service_id: str):
    spec = R.get(service_id)
    assert spec.fn.__annotations__.get("return") is Evidence, (
        spec.id + " is bound to a function that is not annotated to return Evidence"
    )


@pytest.mark.parametrize("service_id", sorted(R.REGISTRY))
def test_declared_streams_and_units_exist(service_id: str):
    spec = R.get(service_id)
    assert spec.required_streams <= STREAM_IDS
    assert spec.required_units <= UNIT_NAMES
    assert spec.default_cadence in R.CADENCES
    assert spec.value_shape in ("scalar", "series", "table", "structure")


@pytest.mark.parametrize("service_id", sorted(R.REGISTRY))
def test_soft_dependencies_are_registered(service_id: str):
    spec = R.get(service_id)
    for dependency in spec.soft_depends_on:
        assert dependency in R.REGISTRY, spec.id + " depends on unregistered " + dependency
        assert dependency != spec.id


@pytest.mark.parametrize("service_id", sorted(R.REGISTRY))
def test_function_name_matches_the_service_id(service_id: str):
    spec = R.get(service_id)
    assert spec.fn.__name__ == service_id.split(".", 1)[1]
    assert spec.fn.__module__ == "app.stats." + spec.module


def test_every_pack_has_services_and_every_service_has_a_pack():
    for pack_id in R.PACKS:
        assert R.for_pack(pack_id), pack_id + " has no services"
    assert all(spec.pack in R.PACKS for spec in R.REGISTRY.values())


# Availability is decided per service, not per pack: a pack's declared streams
# are the ones it needs to be worth opening, while an individual service may need
# fewer (bayes.* runs on request_flow alone even though the pack also lists the
# ledger) or more (forecast.attendance needs a roster to bound itself by). The
# checks below therefore test the per-service resolution rather than trying to
# make the two levels agree.

# The services that legitimately declare no stream at all. Each takes arrays the
# caller produced: scores and labels from a risk model, or a reference
# distribution that is an artifact of a previous fit rather than stream data
# (spine section 8). They are listed rather than inferred so that a new
# stream-less service is a deliberate addition to this list.
ARRAY_TAKING = frozenset(
    {
        "calibration.isotonic_calibrate",
        "calibration.platt_calibrate",
        "calibration.brier_decomposition",
        "calibration.reliability_diagram",
        "conformal.split_conformal_interval",
        "drift.psi",
        "drift.ks_test",
        "drift.label_shift",
        "privacy.k_anonymity_suppress",
        "privacy.laplace_noise",
    }
)


def test_only_array_taking_services_declare_no_stream():
    stream_less = {spec.id for spec in R.REGISTRY.values() if not spec.required_streams}
    assert stream_less == ARRAY_TAKING


def test_availability_is_resolved_per_service():
    """A tenant with only request_flow gets Pack 1's core and nothing that needs a ballot."""
    available = {spec.id for spec in R.available_for_streams(frozenset({"request_flow"}))}
    assert "survival.km_resolution_curve" in available
    assert "survival.churn_curve" not in available       # needs member_lifecycle
    assert "voting.schulze" not in available             # needs decision
    assert R.missing_streams("voting.schulze", frozenset({"request_flow"})) == frozenset({"decision"})


def test_nothing_is_registered_twice():
    assert len(R.REGISTRY) == len(set(R.REGISTRY))
    assert len({spec.method_card.id for spec in R.REGISTRY.values()}) == len(R.REGISTRY)


def test_the_flagship_services_are_present():
    """
    The services the product's claims rest on, named explicitly so that deleting
    one is a deliberate act rather than a diff nobody read.
    """
    for service_id in (
        "survival.naive_vs_km_gap",
        "survival.km_resolution_curve",
        "bayes.rank_by_posterior_lower_bound",
        "conformal.survival_eta_bound",
        "forecast.rolling_origin_backtest",
        "voting.condorcet_winner",
        "privacy.k_anonymity_suppress",
        "calibration.brier_decomposition",
    ):
        assert service_id in R.REGISTRY


def test_nothing_is_a_stub_any_more():
    """
    The successor to `test_stub_services_raise_rather_than_return_a_number`,
    which held while the four packs were landing and required that anything not
    yet implemented raise loudly rather than return a plausible-looking zero.
    Pack 2's `bayes.*` and `pairwise.*` were the last stubs it named, so the test
    it was written to enforce has been discharged and is replaced by its own
    stopping condition: every registered service now has a body.

    If a service is ever added ahead of its mathematics, this fails on the same
    commit and the read surface stops advertising it.
    """
    unimplemented = sorted(
        spec.id for spec in R.REGISTRY.values() if not spec.implemented
    )
    assert unimplemented == []
    assert len(R.implemented_ids()) == len(R.REGISTRY) == 81


def test_pack_one_is_marked_implemented():
    """
    `implemented` is what the read surface uses to decide whether to offer a
    service at all, so it must track the code rather than an intention. Pack 1
    landed with card C.9; if one of these is flipped back, the packs endpoint
    must stop advertising it on the same commit.
    """
    for service_id in (
        "survival.km_resolution_curve",
        "survival.median_resolution_days",
        "survival.cox_hazard_ratios",
        "survival.naive_vs_km_gap",
        "spc.ewma_chart",
        "spc.cusum_chart",
        "spc.poisson_rate_chart",
        "changepoint.detect_level_shifts",
        "queueing.little_law_wait",
        "queueing.erlang_c_staffing",
        "fairness.workload_gini",
        "fairness.balanced_assignment",
    ):
        assert R.get(service_id).implemented, service_id + " is implemented but not declared so"


# ---------------------------------------------------------------------------
# The guards themselves
# ---------------------------------------------------------------------------


def _card(**overrides) -> dict:
    base = dict(
        id="survival.fake",
        name="Fake",
        one_liner="A card for testing the guards.",
        assumes=("something",),
        wrong_when=("something else",),
        min_n=10,
        interval_meaning="a test",
        references=("nobody (1900)",),
    )
    base.update(overrides)
    return base


def test_a_card_without_assumptions_does_not_load():
    with pytest.raises(ValueError, match="no assumptions"):
        MethodCard(**_card(assumes=()))


def test_a_card_without_failure_modes_does_not_load():
    with pytest.raises(ValueError, match="when it is wrong"):
        MethodCard(**_card(wrong_when=()))


def test_a_card_without_references_does_not_load():
    with pytest.raises(ValueError, match="no references"):
        MethodCard(**_card(references=()))


def _fn(x=None) -> Evidence:  # pragma: no cover - never called
    raise NotImplementedError


def _spec(**overrides) -> R.ServiceSpec:
    base = dict(
        id="survival.fake",
        pack=R.RELIABILITY,
        fn=_fn,
        required_streams=frozenset({"request_flow"}),
        required_units=frozenset({"RequestSpell"}),
        value_shape="scalar",
        min_n=10,
        default_cadence="nightly",
        scope_dimensions=(),
        method_card=MethodCard(**_card()),
    )
    base.update(overrides)
    return R.ServiceSpec(**base)


def test_a_spec_whose_min_n_disagrees_with_its_card_does_not_load():
    with pytest.raises(ValueError, match="one floor, stated once"):
        _spec(min_n=42)


def test_a_spec_bound_to_a_function_returning_a_float_does_not_load():
    def returns_a_float(x=None) -> float:  # pragma: no cover
        return 1.0

    with pytest.raises(ValueError, match="not annotated to return Evidence"):
        _spec(fn=returns_a_float)


def test_a_spec_with_a_typo_in_a_stream_name_does_not_load():
    with pytest.raises(ValueError, match="unknown streams"):
        _spec(required_streams=frozenset({"request_flows"}))


def test_a_spec_carrying_someone_elses_card_does_not_load():
    with pytest.raises(ValueError, match="the card and the service must be the same thing"):
        _spec(method_card=MethodCard(**_card(id="survival.other")))
