"""
The `campus_club` adapter: a student club, society or chapter inside a college.

Closest to the Campus Connect source, so the port lands here with the least
adaptation and this is the one vertical whose `Request` rows already carry
something that maps onto a declared category.

Row mapping lives in `PortedSchemaAdapter`, which both shipped verticals share
along with its TODOs for the streams the ported schema cannot supply.
"""
from __future__ import annotations

from typing import Any, Literal, Mapping

from app.verticals.adapters.base import PortedSchemaAdapter


class CampusClubAdapter(PortedSchemaAdapter):
    vertical_id = "campus_club"

    request_categories = (
        "venue_booking",
        "equipment",
        "funding_request",
        "permissions",
        "event_logistics",
        "membership_query",
        "grievance",
        "other",
    )
    request_priorities = ("low", "normal", "deadline_bound")
    ledger_categories = (
        "membership_fee",
        "college_grant",
        "sponsorship",
        "ticket_sales",
        "event_expense",
        "equipment_purchase",
        "printing",
        "refreshments",
        "travel",
        "misc",
    )
    participation_kinds = (
        "rsvp",
        "attend",
        "no_show",
        "volunteer_hours",
        "post",
        "comment",
        "upvote",
        "training_complete",
    )
    exit_reasons = ("graduated", "left_college", "inactive", "resigned", "removed")
    strata_schema: Mapping[str, tuple[str, ...]] = {
        "year": ("1", "2", "3", "4", "pg"),
        # TODO(manifest): docs/VERTICALS.md declares `department` as a
        # manifest-declared list, and the backend's provisional manifests
        # (app/verticals/manifests/*.json) do not carry one yet. This placeholder
        # exists so the low-cardinality contract is enforced rather than skipped;
        # anything outside it is counted as unmapped, loudly, rather than
        # widening the stratum until it re-identifies people. Replace it by
        # reading the manifest once the manifest shape is reconciled with
        # docs/VERTICALS.md.
        "department": ("cse", "ece", "eee", "mech", "civil", "chem", "maths", "physics", "other"),
        "role_track": ("core", "active", "general"),
    }

    k_anonymity_threshold = 5
    # An unresolved venue booking is one ongoing problem, not a series of them.
    reopen_policy: Literal["new_spell", "extend"] = "extend"
    # A request blocked on the college administration is genuinely paused, and
    # the club is judged on its own responsiveness.
    sla_clock: Literal["wall", "active"] = "active"
    currency = "INR"

    # The ported Campus Connect `RequestCategory` enum, mapped into the declared
    # vocabulary. This is the one vertical where the legacy values mean something.
    # CERTIFICATE maps to "permissions" as the nearest declared category: a
    # certificate request is an administrative document request. The choice is
    # recorded here rather than made silently at read time, and if it turns out
    # clubs use it differently the fix is one line in one place.
    legacy_request_categories: Mapping[str, str] = {
        "EVENT": "event_logistics",
        "GROUP": "membership_query",
        "CERTIFICATE": "permissions",
        "TECHNICAL": "equipment",
        "GENERAL": "other",
    }

    def member_strata(self, row: Any) -> dict[str, str]:
        """
        `Member.year` and `Member.branch` are the two campus fields the port
        already carries, so this vertical has real strata on day one.

        TODO(missing model): `role_track` (core, active, general) is a property
        of a `Membership`, not of a `Member`, and this method is handed member
        rows. `join_cohort`, the academic year of joining, has no column either;
        deriving it from `created_at` would be wrong for anyone imported from a
        previous system.
        """
        values: dict[str, Any] = {}
        year = getattr(row, "year", None)
        if year is not None:
            values["year"] = str(year)
        branch = getattr(row, "branch", None)
        if branch is not None:
            values["department"] = branch
        return self.strata(values)


__all__ = ["CampusClubAdapter"]
