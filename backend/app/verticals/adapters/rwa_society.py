"""
The `rwa_society` adapter: resident welfare association or apartment society.

The design reference vertical, and the one the interview evidence in
`RWA_Master_Context.md` actually describes. A complaint is a `RequestEvent`, a
resident is a `member_ref`, a maintenance payment would be a `LedgerEntry`.

Row mapping lives in `PortedSchemaAdapter`, which both shipped verticals share
along with its TODOs for the four streams the ported schema cannot supply. What
is here is this vertical's vocabulary, its privacy floor, and the two gaps that
matter more here than anywhere else.
"""
from __future__ import annotations

from typing import Any, Literal, Mapping

from app.verticals.adapters.base import PortedSchemaAdapter


class RwaSocietyAdapter(PortedSchemaAdapter):
    vertical_id = "rwa_society"

    request_categories = (
        "water_supply",
        "sewage_stp",
        "electrical",
        "lift",
        "security",
        "housekeeping",
        "parking",
        "common_area",
        "pest_control",
        "noise_nuisance",
        "builder_defect",
        "other",
    )
    request_priorities = ("routine", "urgent", "safety")
    ledger_categories = (
        "maintenance_dues",
        "corpus_fund",
        "sinking_fund",
        "stp_maintenance",
        "lift_amc",
        "security_wages",
        "housekeeping_wages",
        "electricity_common",
        "water_tanker",
        "festival_fund",
        "repairs_capex",
        "penalty_late_fee",
        "misc",
    )
    participation_kinds = (
        "attend",
        "rsvp",
        "no_show",
        "volunteer_hours",
        "post",
        "comment",
        "upvote",
    )
    exit_reasons = ("sold_unit", "tenancy_ended", "deceased", "removed", "unknown")
    strata_schema: Mapping[str, tuple[str, ...]] = {
        "block": ("a", "b", "c", "d", "e", "f", "g", "h"),
        "floor_band": ("ground", "1-3", "4-7", "8+"),
        "unit_type": ("1bhk", "2bhk", "3bhk", "4bhk+"),
        "ownership": ("owner", "tenant"),
        "tenure_band": ("<1y", "1-3y", "3-7y", "7y+"),
    }

    # Complaints are per-block and blocks are small. This is the vertical that
    # made privacy.py non-optional, and the floor cannot be lowered at runtime.
    k_anonymity_threshold = 5
    # A recurring water complaint is a new event, not a longer one.
    reopen_policy: Literal["new_spell", "extend"] = "new_spell"
    # A resident waiting for water does not care that the vendor was on hold.
    sla_clock: Literal["wall", "active"] = "wall"
    currency = "INR"

    # Card C.8: `Request.category` is no longer bound to the ported Campus
    # Connect enum (EVENT, GROUP, CERTIFICATE, TECHNICAL, GENERAL) - it is a
    # plain string, validated at the service layer against this vertical's own
    # `request_categories` above. A society complaint written through the API
    # today already lands in the declared vocabulary directly (`water_supply`,
    # `sewage_stp`, ...), so this map stays empty: there is nothing legacy to
    # translate. It only stays non-removed as the place a future bulk-import of
    # pre-C.8 rows (which still hold the old enum strings) would register its
    # translation, so an old row is counted as unmapped rather than guessed at,
    # per the adapter's obligation 1. survival.logrank_compare and
    # survival.cox_hazard_ratios by category are unblocked for any request
    # written after this card.
    legacy_request_categories: Mapping[str, str] = {}

    def member_strata(self, row: Any) -> dict[str, str]:
        """
        TODO(missing model): none of this vertical's strata (block, floor_band,
        unit_type, ownership, tenure_band) has a column. `Member` carries
        roll_no, branch and year, which are campus fields. Post-stratification,
        sortition, the fairness report and every k-anonymity cell here depend on
        these, so this is the highest-value gap in the whole adapter: without
        `block`, the privacy machinery has nothing to protect and the fairness
        machinery has nothing to compare.
        """
        return {}


__all__ = ["RwaSocietyAdapter"]
