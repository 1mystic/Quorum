"""
Local demo seed. Run: uv run python scripts/seed_demo.py

Builds two demo tenants end to end so a fresh checkout has something real to
look at: `vaikunth-heights` (vertical `rwa_society`) and `aavartan-robotics`
(vertical `campus_club`), matching the names already used in
`design/samples/quorum/dashboard.html` and the frontend fixtures.

Idempotent by rebuild, not by skip: if a tenant with the target slug already
exists, every row it owns is deleted first (in FK-safe order, through the
same RLS the app enforces) and rebuilt from scratch. That is simpler to keep
correct than a per-row upsert across a dozen tables, and it means re-running
this script after a schema change always leaves both demo tenants in the
same, fully-described state rather than half old rows plus half new ones.

After both tenants are built, `InsightMaterializer.materialize_all` is run
for each one for real, against this same database, and a summary of which
services produced a genuine reading versus `insufficient_data` (and why) is
printed at the end. Nothing here computes a statistic itself: this script
fetches and writes rows exactly the way a real request would, and the worker
does the rest.
"""
from __future__ import annotations

import asyncio
import math
import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.core.database import SessionLocal
from app.core.tenancy import set_tenant_context
from app.utils.hashing import hash_password
from app.models import (
    Tenant, User, UserRole, TenantAdmin,
    Member, Group, GroupType, GroupStatus,
    Membership, MembershipRole, MembershipStatus,
    Request, RequestStatus, RequestEventLog, RequestEventKind,
    Due, DueStatus, Payment, Receipt, Contribution, ContributionKind, Expense,
    LedgerInstrument, LedgerStatus,
    ParticipationEventLog, ParticipationKind,
    Decision, DecisionKind, DecisionOption, Ballot, BallotStyle, DecisionStatus,
    Event, EventStatus, EventRegistration, RegistrationResult,
    Announcement, AnnouncementCategory, AnnouncementStatus,
)
from app.repository import TenantRepository
from app.verticals import get_manifest
from app.services.insight_materializer import InsightMaterializer, default_window
from app.stats import registry

ANCHOR = datetime.now(timezone.utc)
DEMO_PASSWORD = "Demo12345!"

# Tables that carry tenant_id, in an order safe to DELETE FROM without
# tripping a foreign key still pointing at a row not yet removed. Two tables
# with a self-reference (requests.merged_into_id, insight_runs.superseded_by)
# get that column nulled out first; everything else is a straight child-first
# ordering of the schema in app/models/.
_WIPE_ORDER = [
    "ballots", "decision_options", "decisions",
    "participation_events",
    "certificates", "event_registrations",
    "request_events",
    "receipts", "payments", "dues",
    "contributions", "expenses", "idempotency_records",
    "notifications",
    "announcements",
    "requests",
    "events",
    "memberships", "groups",
    "members",
    "insight_runs",
]


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm. No numpy in this dependency set (pyproject.toml), and
    a demo seed script has no business adding one."""
    if lam <= 0:
        return 0
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


def lognormal_days(rng: random.Random, median_days: float, sigma: float,
                    lo: float = 0.05, hi: float = 90.0) -> float:
    value = math.exp(rng.gauss(math.log(median_days), sigma))
    return max(lo, min(hi, value))


async def wipe_tenant(db, tenant_id: int) -> None:
    await set_tenant_context(db, tenant_id)
    await db.execute(text("UPDATE requests SET merged_into_id = NULL WHERE tenant_id = :t"),
                      {"t": tenant_id})
    await db.execute(text("UPDATE insight_runs SET superseded_by = NULL WHERE tenant_id = :t"),
                      {"t": tenant_id})
    # group_links has no tenant_id of its own (only group_id); this script
    # never seeds one, but a real deployment might, so clear it via the
    # tenant's groups before groups themselves are deleted.
    await db.execute(
        text("DELETE FROM group_links WHERE group_id IN (SELECT id FROM groups WHERE tenant_id = :t)"),
        {"t": tenant_id},
    )
    for table in _WIPE_ORDER:
        await db.execute(text(f"DELETE FROM {table} WHERE tenant_id = :t"), {"t": tenant_id})
    await db.execute(text("DELETE FROM tenant_admins WHERE tenant_id = :t"), {"t": tenant_id})
    await db.execute(text("DELETE FROM users WHERE tenant_id = :t"), {"t": tenant_id})
    await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tenant_id})


class Counts(dict):
    def bump(self, key: str, n: int = 1) -> None:
        self[key] = self.get(key, 0) + n


class Builder:
    """One tenant's worth of demo data. Holds the rng and the row counters;
    every `_make_*` method below adds ORM rows (flush happens in batches, not
    per row, since this script writes thousands of rows) and every write
    happens after `set_tenant_context` so it lands under the same RLS
    enforcement a real request would hit."""

    def __init__(self, db, seed: int):
        self.db = db
        self.rng = random.Random(seed)
        self.counts = Counts()
        self.tenant: Tenant | None = None
        self._pending = 0

    async def flush(self, force: bool = False) -> None:
        self._pending += 1
        if force or self._pending >= 200:
            await self.db.flush()
            self._pending = 0

    async def make_tenant(self, name: str, slug: str, vertical: str, description: str) -> Tenant:
        repo = TenantRepository(self.db)
        existing = await repo.get_by_slug(slug)
        if existing is not None:
            await wipe_tenant(self.db, existing.id)
            await self.db.flush()
        tenant = await repo.create_tenant(name=name, slug=slug, vertical=vertical,
                                           description=description)
        manifest = get_manifest(vertical)
        tenant.enabled_packs = list(manifest.default_packs)
        tenant.timezone = "Asia/Kolkata"
        await self.db.flush()
        await set_tenant_context(self.db, tenant.id)
        self.tenant = tenant
        return tenant

    async def make_admin(self, email: str, full_name: str) -> User:
        user = User(tenant_id=self.tenant.id, email=email,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    full_name=full_name, role=UserRole.TENANT_ADMIN)
        self.db.add(user)
        await self.db.flush()
        self.db.add(TenantAdmin(tenant_id=self.tenant.id, user_id=user.id))
        await self.flush(force=True)
        return user

    async def make_member(self, email: str, full_name: str, *, branch: str | None = None,
                           year: int | None = None, joined_at: datetime | None = None) -> Member:
        user = User(tenant_id=self.tenant.id, email=email,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    full_name=full_name, role=UserRole.MEMBER)
        self.db.add(user)
        await self.db.flush()
        member = Member(tenant_id=self.tenant.id, user_id=user.id, branch=branch, year=year)
        if joined_at is not None:
            member.created_at = joined_at
        self.db.add(member)
        await self.flush()
        self.counts.bump("members")
        return member

    async def make_group(self, head: Member, name: str, description: str, category: str,
                          type_: GroupType = GroupType.OFFICIAL) -> Group:
        group = Group(tenant_id=self.tenant.id, group_head=head.id, name=name,
                       description=description, category=category, type=type_,
                       status=GroupStatus.ACTIVE)
        self.db.add(group)
        await self.db.flush()
        self.counts.bump("groups")
        return group

    async def make_membership(self, member: Member, group: Group,
                               role: MembershipRole = MembershipRole.MEMBER) -> Membership:
        m = Membership(tenant_id=self.tenant.id, member_id=member.id, group_id=group.id,
                        role=role, status=MembershipStatus.APPROVED)
        self.db.add(m)
        await self.flush()
        return m

    # ---- request_flow ---------------------------------------------------

    async def make_requests(self, *, group: Group, raisers: list[Member],
                             resolvers: list[Member], resolver_weights: list[float],
                             categories: list[str], category_weights: list[float],
                             priorities: list[str], priority_weights: list[float],
                             history_days: int, changepoint_day: int | None,
                             baseline_per_week: float, stepped_per_week: float,
                             median_resolution_days: float, escalate_p: float = 0.03,
                             withdraw_p: float = 0.02) -> None:
        """
        One row per day of history, Poisson-distributed arrivals at a rate that
        steps up at `changepoint_day` (days before ANCHOR; None means no step),
        so `changepoint.detect_level_shifts` has a genuine level shift to find
        and `spc.*`/`survival.*` have real, unevenly-spread volume instead of a
        flat synthetic rate. Resolution time is lognormal so most requests
        close quickly and a few take much longer, and a request opened in the
        last few days is deliberately left open more often than not - that is
        the censoring story the demo exists to tell, not an accident of the
        random draw.
        """
        title_words = categories
        for day in range(history_days, -1, -1):
            opened_date = ANCHOR - timedelta(days=day)
            if changepoint_day is not None and day < changepoint_day:
                rate = stepped_per_week / 7.0
            else:
                rate = baseline_per_week / 7.0
            n_today = poisson(self.rng, rate)
            for _ in range(n_today):
                opened_at = opened_date - timedelta(
                    hours=self.rng.uniform(0, 23), minutes=self.rng.uniform(0, 59)
                )
                category = self.rng.choices(categories, weights=category_weights, k=1)[0]
                priority = self.rng.choices(priorities, weights=priority_weights, k=1)[0]
                raiser = self.rng.choice(raisers)
                req = Request(
                    tenant_id=self.tenant.id, member_id=raiser.id, group_id=group.id,
                    category=category, subcategory=None, priority=priority,
                    channel=self.rng.choice(["whatsapp", "app", "phone", "in_person"]),
                    location_ref=None,
                    status=RequestStatus.OPEN,
                    title=f"{category.replace('_', ' ').title()} issue",
                    description=f"Reported via demo seed on {opened_at.date().isoformat()}.",
                    created_at=opened_at,
                )
                self.db.add(req)
                await self.db.flush()
                self.db.add(RequestEventLog(
                    tenant_id=self.tenant.id, request_id=req.id, kind=RequestEventKind.OPENED,
                    at=opened_at, actor_id=raiser.id, category=category, priority=priority,
                    channel=req.channel, group_id=group.id,
                ))

                resolver = self.rng.choices(resolvers, weights=resolver_weights, k=1)[0]
                # A request opened very recently is deliberately more likely to
                # still be open at window end: that is real right-censoring,
                # not a special case in the generator.
                recency_open_bias = max(0.0, 1.0 - day / 10.0) if day < 10 else 0.0
                will_stay_open = self.rng.random() < recency_open_bias
                res_days = lognormal_days(self.rng, median_resolution_days, 0.9)
                resolved_at = opened_at + timedelta(days=res_days)

                if not will_stay_open and resolved_at < ANCHOR:
                    first_response_at = opened_at + timedelta(days=res_days * self.rng.uniform(0.1, 0.5))
                    req.responded_by = resolver.id
                    req.responded_at = first_response_at
                    req.response_body = "Assigned and being worked on."
                    self.db.add(RequestEventLog(
                        tenant_id=self.tenant.id, request_id=req.id,
                        kind=RequestEventKind.ACKNOWLEDGED, at=first_response_at,
                        actor_id=resolver.id, assignee_id=resolver.id, category=category,
                        group_id=group.id,
                    ))
                    outcome_roll = self.rng.random()
                    if outcome_roll < escalate_p:
                        req.status = RequestStatus.ESCALATED
                        req.outcome = "escalated"
                        kind = RequestEventKind.ESCALATED
                    elif outcome_roll < escalate_p + withdraw_p:
                        req.status = RequestStatus.WITHDRAWN
                        req.outcome = "withdrawn"
                        kind = RequestEventKind.WITHDRAWN
                    else:
                        req.status = RequestStatus.RESOLVED
                        req.outcome = "resolved"
                        req.resolved_at = resolved_at
                        kind = RequestEventKind.RESOLVED
                    req.terminal_at = resolved_at
                    self.db.add(RequestEventLog(
                        tenant_id=self.tenant.id, request_id=req.id, kind=kind, at=resolved_at,
                        actor_id=resolver.id, category=category, group_id=group.id,
                    ))
                    self.counts.bump("requests_terminal")
                else:
                    # Still open at window end. Some of these have at least
                    # been acknowledged, most have not - a realistic backlog,
                    # not a queue where everything has been touched.
                    if self.rng.random() < 0.4:
                        first_response_at = opened_at + timedelta(days=self.rng.uniform(0.2, 2.0))
                        if first_response_at < ANCHOR:
                            req.responded_by = resolver.id
                            req.responded_at = first_response_at
                            req.response_body = "Looking into this."
                            req.status = RequestStatus.IN_PROGRESS
                            self.db.add(RequestEventLog(
                                tenant_id=self.tenant.id, request_id=req.id,
                                kind=RequestEventKind.ACKNOWLEDGED, at=first_response_at,
                                actor_id=resolver.id, assignee_id=resolver.id, category=category,
                                group_id=group.id,
                            ))
                    self.counts.bump("requests_open")
                self.counts.bump("requests")
                await self.flush()
        await self.flush(force=True)

    # ---- ledger -----------------------------------------------------------

    async def make_due_cycle(self, *, members: list[Member], category: str, amount_minor: int,
                              issued_at: datetime, due_at: datetime, pay_rate: float = 0.85,
                              receipt_collect_rate: float = 0.82,
                              instrument_weights: dict[str, float] | None = None) -> None:
        instrument_weights = instrument_weights or {
            "upi": 0.45, "bank_transfer": 0.2, "cash": 0.25, "cheque": 0.1,
        }
        instruments = list(instrument_weights.keys())
        weights = list(instrument_weights.values())
        for member in members:
            due = Due(
                tenant_id=self.tenant.id, member_id=member.id, category=category,
                amount_minor=amount_minor, issued_at=issued_at, due_at=due_at,
                status=DueStatus.OPEN,
            )
            self.db.add(due)
            await self.db.flush()
            self.counts.bump("dues")

            if issued_at > ANCHOR:
                await self.flush()
                continue
            if self.rng.random() >= pay_rate:
                # Genuinely unpaid, especially plausible for the most recent cycle.
                await self.flush()
                continue

            lag_days = lognormal_days(self.rng, 6.0, 1.0, lo=0.02, hi=75.0)
            pay_at = due_at + timedelta(days=self.rng.uniform(-3, 2)) if self.rng.random() < 0.5 \
                else issued_at + timedelta(days=self.rng.uniform(0, 10))
            pay_at = min(pay_at, ANCHOR - timedelta(hours=1))
            instrument = LedgerInstrument(self.rng.choices(instruments, weights=weights, k=1)[0])
            payment = Payment(
                tenant_id=self.tenant.id, due_id=due.id, member_id=member.id,
                category=category, amount_minor=amount_minor, currency="INR",
                instrument=instrument, status=LedgerStatus.PENDING, at=pay_at,
                booked_at=pay_at,
            )
            self.db.add(payment)
            await self.db.flush()
            self.counts.bump("payments")

            verify_at = pay_at + timedelta(days=lag_days)
            if verify_at < ANCHOR:
                payment.verified_at = verify_at
                payment.status = LedgerStatus.SETTLED
                payment.settled_at = verify_at
                payment.reconciled = self.rng.random() < 0.9
                due.status = DueStatus.PAID

                receipt = Receipt(
                    tenant_id=self.tenant.id, payment_id=payment.id, issued_at=verify_at,
                )
                if self.rng.random() < receipt_collect_rate:
                    receipt.collected_at = verify_at + timedelta(
                        days=lognormal_days(self.rng, 3.0, 1.1, lo=0.01, hi=40.0)
                    )
                    if receipt.collected_at > ANCHOR:
                        receipt.collected_at = None
                self.db.add(receipt)
                self.counts.bump("receipts")
            else:
                # Paid but not yet verified as of the window end: the exact
                # "screenshot sent, treasurer hasn't confirmed it" gap.
                due.status = DueStatus.PARTIAL
            await self.flush()
        await self.flush(force=True)

    async def make_contribution(self, *, members: list[Member], kind: ContributionKind,
                                 category: str, at: datetime, campaign_ref: str,
                                 amount_range: tuple[int, int]) -> None:
        for member in members:
            self.db.add(Contribution(
                tenant_id=self.tenant.id, member_id=member.id, campaign_ref=campaign_ref,
                kind=kind, category=category,
                amount_minor=self.rng.randint(*amount_range) if kind == ContributionKind.CASH else 0,
                at=at, description=f"{campaign_ref} contribution",
            ))
            self.counts.bump("contributions")
        await self.flush(force=True)

    async def make_expense(self, *, category: str, amount_minor: int, at: datetime,
                            counterparty_ref: str | None = None) -> None:
        self.db.add(Expense(
            tenant_id=self.tenant.id, category=category, amount_minor=amount_minor,
            instrument=LedgerInstrument.BANK_TRANSFER, status=LedgerStatus.SETTLED,
            at=at, settled_at=at, counterparty_ref=counterparty_ref,
        ))
        self.counts.bump("expenses")
        await self.flush()

    # ---- participation ------------------------------------------------

    async def make_attendance(self, *, members: list[Member], event: Event, rsvp_rate: float,
                               attend_given_rsvp: float, no_show_kind: bool = True) -> None:
        for member in members:
            if self.rng.random() >= rsvp_rate:
                continue
            rsvp_at = event.starts_at - timedelta(days=self.rng.uniform(1, 10))
            if rsvp_at > ANCHOR:
                continue
            self.db.add(ParticipationEventLog(
                tenant_id=self.tenant.id, member_id=member.id, at=rsvp_at,
                kind=ParticipationKind.RSVP, object_type="event", object_id=event.id,
                group_id=event.group_id,
            ))
            self.counts.bump("participation_events")
            attended = self.rng.random() < attend_given_rsvp
            if event.starts_at > ANCHOR:
                continue
            reg = EventRegistration(
                tenant_id=self.tenant.id, event_id=event.id, member_id=member.id,
                checked_in=attended,
                checked_in_at=event.starts_at + timedelta(minutes=self.rng.uniform(0, 30))
                if attended else None,
                result=RegistrationResult.PARTICIPANT if attended else RegistrationResult.REGISTRANT,
            )
            self.db.add(reg)
            if attended:
                self.db.add(ParticipationEventLog(
                    tenant_id=self.tenant.id, member_id=member.id, at=reg.checked_in_at,
                    kind=ParticipationKind.ATTEND, object_type="event", object_id=event.id,
                    group_id=event.group_id,
                ))
            elif no_show_kind:
                self.db.add(ParticipationEventLog(
                    tenant_id=self.tenant.id, member_id=member.id, at=event.ends_at,
                    kind=ParticipationKind.NO_SHOW, object_type="event", object_id=event.id,
                    group_id=event.group_id,
                ))
            self.counts.bump("participation_events")
            await self.flush()
        await self.flush(force=True)

    async def make_nudge_experiment(self, *, members: list[Member], campaign_ref: str,
                                     start_at: datetime, arms: dict[str, float]) -> None:
        """
        A payment-reminder A/B test over the exposure log: `arm_ref` carries
        the channel/send-hour arm, and `arms` maps arm name to its true
        action-rate so the two arms genuinely differ, the way Pack 2's
        `experiments.*`/`bandits.*` exist to detect.
        """
        arm_names = list(arms.keys())
        for i, member in enumerate(members):
            arm = arm_names[i % len(arm_names)]
            sent_at = start_at + timedelta(hours=self.rng.uniform(0, 72))
            if sent_at > ANCHOR:
                continue
            self.db.add(ParticipationEventLog(
                tenant_id=self.tenant.id, member_id=member.id, at=sent_at,
                kind=ParticipationKind.NUDGE_SENT, object_type="campaign", object_id=None,
                arm_ref=arm, channel=arm,
            ))
            self.counts.bump("participation_events")
            delivered_at = sent_at + timedelta(minutes=self.rng.uniform(1, 30))
            if delivered_at > ANCHOR:
                await self.flush()
                continue
            self.db.add(ParticipationEventLog(
                tenant_id=self.tenant.id, member_id=member.id, at=delivered_at,
                kind=ParticipationKind.NUDGE_DELIVERED, object_type="campaign", object_id=None,
                arm_ref=arm, channel=arm,
            ))
            self.counts.bump("participation_events")
            if self.rng.random() < 0.7:
                opened_at = delivered_at + timedelta(minutes=self.rng.uniform(1, 240))
                if opened_at < ANCHOR:
                    self.db.add(ParticipationEventLog(
                        tenant_id=self.tenant.id, member_id=member.id, at=opened_at,
                        kind=ParticipationKind.NUDGE_OPENED, object_type="campaign", object_id=None,
                        arm_ref=arm, channel=arm,
                    ))
                    self.counts.bump("participation_events")
                    if self.rng.random() < arms[arm]:
                        acted_at = opened_at + timedelta(minutes=self.rng.uniform(1, 600))
                        if acted_at < ANCHOR:
                            self.db.add(ParticipationEventLog(
                                tenant_id=self.tenant.id, member_id=member.id, at=acted_at,
                                kind=ParticipationKind.NUDGE_ACTED, object_type="campaign",
                                object_id=None, arm_ref=arm, channel=arm,
                            ))
                            self.counts.bump("participation_events")
            await self.flush()
        await self.flush(force=True)

    # ---- decisions ------------------------------------------------------

    async def make_decision(self, *, title: str, description: str, group: Group | None,
                             kind: DecisionKind, declared_rule: str, ballot_style: BallotStyle,
                             options: list[str], opened_at: datetime, admin: User,
                             seats: int = 1, budget_minor: int | None = None,
                             option_costs: list[int] | None = None) -> tuple[Decision, list[DecisionOption]]:
        decision = Decision(
            tenant_id=self.tenant.id, group_id=group.id if group else None, title=title,
            description=description, kind=kind, declared_rule=declared_rule, seats=seats,
            budget_minor=budget_minor, ballot_style=ballot_style,
            status=DecisionStatus.OPEN, submitted_at=opened_at - timedelta(days=3),
            approved_by=admin.id, approved_at=opened_at, opened_at=opened_at,
            eligible_strata=[],
        )
        self.db.add(decision)
        await self.db.flush()
        opts = []
        for i, label in enumerate(options):
            opt = DecisionOption(
                tenant_id=self.tenant.id, decision_id=decision.id, label=label,
                cost_minor=option_costs[i] if option_costs else None,
            )
            self.db.add(opt)
            opts.append(opt)
        await self.db.flush()
        self.counts.bump("decisions")
        return decision, opts

    async def cast_ranked_ballot(self, decision: Decision, voter: Member, ranking: list[list[int]],
                                  cast_at: datetime) -> None:
        self.db.add(Ballot(
            tenant_id=self.tenant.id, decision_id=decision.id, voter_id=voter.id,
            ranking=ranking, cast_at=cast_at,
        ))
        self.counts.bump("ballots")
        await self.flush()

    async def cast_allocation_ballot(self, decision: Decision, voter: Member,
                                      allocation: dict[str, int], cast_at: datetime) -> None:
        self.db.add(Ballot(
            tenant_id=self.tenant.id, decision_id=decision.id, voter_id=voter.id,
            allocation=allocation, cast_at=cast_at,
        ))
        self.counts.bump("ballots")
        await self.flush()

    # ---- events / announcements ------------------------------------------

    async def make_event(self, *, group: Group, creator: Member, title: str, description: str,
                          venue: str, starts_at: datetime, ends_at: datetime,
                          status: EventStatus, admin: User | None = None,
                          rejection_reason: str | None = None, capacity: int | None = None) -> Event:
        event = Event(
            tenant_id=self.tenant.id, group_id=group.id, created_by=creator.id, title=title,
            description=description, venue=venue, starts_at=starts_at, ends_at=ends_at,
            capacity=capacity, status=EventStatus.DRAFT,
            created_at=starts_at - timedelta(days=21),
        )
        self.db.add(event)
        await self.db.flush()
        if status != EventStatus.DRAFT:
            event.status = EventStatus.SUBMITTED
            event.submitted_at = starts_at - timedelta(days=18)
        if status == EventStatus.PUBLISHED:
            event.status = EventStatus.PUBLISHED
            event.approved_by = admin.id
            event.approved_at = starts_at - timedelta(days=17)
        elif status == EventStatus.REJECTED:
            event.status = EventStatus.REJECTED
            event.rejected_by = admin.id
            event.rejected_at = starts_at - timedelta(days=17)
            event.rejection_reason = rejection_reason
        self.counts.bump("events")
        await self.flush()
        return event

    async def make_announcement(self, *, group: Group, author: Member, title: str, body: str,
                                 category: AnnouncementCategory, created_at: datetime,
                                 status: AnnouncementStatus, admin: User | None = None,
                                 rejection_reason: str | None = None) -> Announcement:
        ann = Announcement(
            tenant_id=self.tenant.id, group_id=group.id, author_id=author.id, title=title,
            body=body, category=category, status=AnnouncementStatus.DRAFT, created_at=created_at,
        )
        self.db.add(ann)
        await self.db.flush()
        if status != AnnouncementStatus.DRAFT:
            ann.status = AnnouncementStatus.SUBMITTED
            ann.submitted_at = created_at + timedelta(hours=1)
        if status == AnnouncementStatus.PUBLISHED:
            ann.status = AnnouncementStatus.PUBLISHED
            ann.approved_by = admin.id
            ann.approved_at = created_at + timedelta(hours=6)
        elif status == AnnouncementStatus.REJECTED:
            ann.status = AnnouncementStatus.REJECTED
            ann.rejected_by = admin.id
            ann.rejected_at = created_at + timedelta(hours=6)
            ann.rejection_reason = rejection_reason
        self.counts.bump("announcements")
        await self.flush()
        return ann


# ===========================================================================
# vaikunth-heights (rwa_society)
# ===========================================================================

RWA_BLOCKS = list("ABCDEFGH")
RWA_CATEGORIES = ["water_supply", "sewage_stp", "electrical", "lift", "security",
                   "housekeeping", "parking", "common_area", "pest_control",
                   "noise_nuisance", "builder_defect", "other"]
RWA_CATEGORY_WEIGHTS = [18, 12, 14, 8, 9, 10, 7, 6, 6, 5, 3, 2]
RWA_PRIORITIES = ["routine", "urgent", "safety"]
RWA_PRIORITY_WEIGHTS = [70, 25, 5]
RWA_HISTORY_DAYS = 430
RWA_CHANGEPOINT_DAY = 150  # a real level shift ~5 months before window end


async def build_rwa_society(db) -> Builder:
    b = Builder(db, seed=20260901)
    rng = b.rng
    await b.make_tenant(
        name="Vaikunth Heights", slug="vaikunth-heights", vertical="rwa_society",
        description="A 340-flat residential society across 8 blocks, demo-seeded.",
    )
    admin = await b.make_admin("admin@vaikunth-heights.demo", "Radha Krishnan (President)")

    residents: list[Member] = []
    for i in range(60):
        block = RWA_BLOCKS[i % len(RWA_BLOCKS)]
        unit = 101 + (i // len(RWA_BLOCKS)) * 100 + (i % 7)
        joined_at = ANCHOR - timedelta(days=rng.uniform(60, RWA_HISTORY_DAYS + 200))
        member = await b.make_member(
            email=f"resident{i+1}@vaikunth-heights.demo",
            full_name=f"Resident {block}-{unit}",
            joined_at=joined_at,
        )
        residents.append(member)

    committee = await b.make_group(
        head=residents[0], name="Managing Committee",
        description="Elected residents who triage and resolve society complaints.",
        category="governance",
    )
    leaders = residents[:12]
    for m in leaders:
        await b.make_membership(m, committee, role=MembershipRole.LEADER)
    for m in residents[12:]:
        await b.make_membership(m, committee, role=MembershipRole.MEMBER)

    resolver_weights = [8, 7, 6, 6, 5, 4, 3, 3, 2, 2, 1, 1]

    await b.make_requests(
        group=committee, raisers=residents, resolvers=leaders,
        resolver_weights=resolver_weights,
        categories=RWA_CATEGORIES, category_weights=RWA_CATEGORY_WEIGHTS,
        priorities=RWA_PRIORITIES, priority_weights=RWA_PRIORITY_WEIGHTS,
        history_days=RWA_HISTORY_DAYS, changepoint_day=RWA_CHANGEPOINT_DAY,
        baseline_per_week=7.0, stepped_per_week=15.0,
        median_resolution_days=4.0, escalate_p=0.05, withdraw_p=0.02,
    )

    # ---- ledger: 14 monthly maintenance-due cycles -----------------------
    months_back = RWA_HISTORY_DAYS // 30
    for m in range(months_back, -1, -1):
        issued_at = (ANCHOR.replace(day=1) - timedelta(days=30 * m)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        due_at = issued_at + timedelta(days=10)
        # A later cycle has a thinner pay rate simply because less time has
        # passed to pay it - genuine right-censoring on the ledger side too.
        pay_rate = 0.92 if m > 1 else 0.55
        await b.make_due_cycle(
            members=residents, category="maintenance_dues", amount_minor=250000,
            issued_at=issued_at, due_at=due_at, pay_rate=pay_rate,
            receipt_collect_rate=0.82,
        )

    diwali_at = ANCHOR - timedelta(days=RWA_HISTORY_DAYS - 40)
    await b.make_contribution(
        members=rng.sample(residents, 40), kind=ContributionKind.CASH,
        category="festival_fund", at=diwali_at, campaign_ref="diwali-drive",
        amount_range=(50000, 500000),
    )
    for m in range(months_back, -1, -1):
        at = ANCHOR - timedelta(days=30 * m)
        await b.make_expense(category="stp_maintenance", amount_minor=5000000,
                              at=at, counterparty_ref="vendor_stp_care")
        await b.make_expense(category="security_wages", amount_minor=18000000, at=at,
                              counterparty_ref="vendor_secure_force")
        await b.make_expense(category="housekeeping_wages", amount_minor=12000000, at=at,
                              counterparty_ref="vendor_clean_co")
        await b.make_expense(category="electricity_common", amount_minor=3500000, at=at,
                              counterparty_ref="state_electricity_board")
        if m % 3 == 0:
            await b.make_expense(category="lift_amc", amount_minor=4000000, at=at,
                                  counterparty_ref="vendor_lift_amc")
    await b.make_expense(category="repairs_capex", amount_minor=25000000,
                          at=ANCHOR - timedelta(days=60), counterparty_ref="vendor_civil_works")

    # ---- participation: general body meetings + nudge experiment --------
    gbm1 = await b.make_event(
        group=committee, creator=leaders[0], title="Annual General Body Meeting",
        description="Budget review and committee updates.", venue="Community Hall",
        starts_at=ANCHOR - timedelta(days=200), ends_at=ANCHOR - timedelta(days=200) + timedelta(hours=2),
        status=EventStatus.PUBLISHED, admin=admin,
    )
    gbm2 = await b.make_event(
        group=committee, creator=leaders[0], title="Half-Yearly General Body Meeting",
        description="STP upgrade proposal and elections.", venue="Community Hall",
        starts_at=ANCHOR - timedelta(days=30), ends_at=ANCHOR - timedelta(days=30) + timedelta(hours=2),
        status=EventStatus.PUBLISHED, admin=admin,
    )
    festival = await b.make_event(
        group=committee, creator=leaders[1], title="Diwali Mela", description="Society festival celebration.",
        venue="Central Lawn", starts_at=diwali_at, ends_at=diwali_at + timedelta(hours=4),
        status=EventStatus.PUBLISHED, admin=admin, capacity=300,
    )
    await b.make_event(
        group=committee, creator=leaders[2], title="Terrace New Year Party",
        description="Proposed rooftop gathering.", venue="Terrace",
        starts_at=ANCHOR + timedelta(days=20), ends_at=ANCHOR + timedelta(days=20, hours=5),
        status=EventStatus.REJECTED, admin=admin,
        rejection_reason="Terrace access is not licensed for events of this size; noise complaints from a prior gathering are on record.",
    )
    upcoming = await b.make_event(
        group=committee, creator=leaders[0], title="Annual General Body Meeting FY27",
        description="Pending admin review before residents are notified.",
        venue="Community Hall", starts_at=ANCHOR + timedelta(days=25),
        ends_at=ANCHOR + timedelta(days=25, hours=2), status=EventStatus.SUBMITTED,
    )

    await b.make_attendance(members=residents, event=gbm1, rsvp_rate=0.55, attend_given_rsvp=0.75)
    await b.make_attendance(members=residents, event=gbm2, rsvp_rate=0.5, attend_given_rsvp=0.7)
    await b.make_attendance(members=residents, event=festival, rsvp_rate=0.7, attend_given_rsvp=0.85)

    await b.make_nudge_experiment(
        members=residents, campaign_ref="due-reminder-2026",
        start_at=ANCHOR - timedelta(days=45),
        arms={"whatsapp_evening": 0.42, "email_morning": 0.24},
    )

    # ---- announcements -----------------------------------------------
    await b.make_announcement(
        group=committee, author=leaders[0], title="Water tanker schedule this week",
        body="Tankers will supply blocks A-D on Monday and E-H on Wednesday.",
        category=AnnouncementCategory.GENERAL, created_at=ANCHOR - timedelta(days=5),
        status=AnnouncementStatus.PUBLISHED, admin=admin,
    )
    await b.make_announcement(
        group=committee, author=leaders[1], title="STP shutdown for maintenance",
        body="The STP will be offline for 4 hours on Saturday for scheduled maintenance.",
        category=AnnouncementCategory.URGENT, created_at=ANCHOR - timedelta(days=12),
        status=AnnouncementStatus.PUBLISHED, admin=admin,
    )
    await b.make_announcement(
        group=committee, author=leaders[2], title="Lift AMC vendor changed",
        body="Effective this month, lift maintenance moves to a new vendor.",
        category=AnnouncementCategory.RESOURCE, created_at=ANCHOR - timedelta(days=40),
        status=AnnouncementStatus.PUBLISHED, admin=admin,
    )
    await b.make_announcement(
        group=committee, author=leaders[0], title="Proposed gym equipment upgrade",
        body="Awaiting admin sign-off before residents are notified.",
        category=AnnouncementCategory.GENERAL, created_at=ANCHOR - timedelta(days=2),
        status=AnnouncementStatus.SUBMITTED,
    )
    await b.make_announcement(
        group=committee, author=leaders[1], title="Open rooftop access to all residents",
        body="Proposal to keep the terrace unlocked at all hours.",
        category=AnnouncementCategory.GENERAL, created_at=ANCHOR - timedelta(days=18),
        status=AnnouncementStatus.REJECTED, admin=admin,
        rejection_reason="Conflicts with the terrace safety policy; see the rejected Terrace New Year Party event for the same underlying concern.",
    )

    # ---- decisions --------------------------------------------------
    cycle_decision, cycle_opts = await b.make_decision(
        title="FY26 Annual Budget: which capex item first?",
        description="Residents rank the three competing capex priorities for next year.",
        group=committee, kind=DecisionKind.POLL, declared_rule="schulze",
        ballot_style=BallotStyle.RANKED,
        options=["Lift modernisation", "STP capacity upgrade", "Facade repainting"],
        opened_at=ANCHOR - timedelta(days=60), admin=admin,
    )
    a, s, f = (o.id for o in cycle_opts)
    cyclic_orders = [
        [[a], [s], [f]],
        [[s], [f], [a]],
        [[f], [a], [s]],
    ]
    voters = rng.sample(residents, 45)
    for i, voter in enumerate(voters):
        order = cyclic_orders[i % 3]
        await b.cast_ranked_ballot(cycle_decision, voter, order,
                                    ANCHOR - timedelta(days=rng.uniform(1, 55)))

    clean_decision, clean_opts = await b.make_decision(
        title="Elect Society Secretary",
        description="Annual secretary election.",
        group=committee, kind=DecisionKind.ELECTION, declared_rule="schulze",
        ballot_style=BallotStyle.RANKED,
        options=["Anjali Rao", "Vikram Shah", "Meera Iyer"],
        opened_at=ANCHOR - timedelta(days=90), admin=admin,
    )
    x, y, z = (o.id for o in clean_opts)
    clean_orders = [[[x], [y], [z]]] * 6 + [[[x], [z], [y]]] * 2 + [[[y], [x], [z]]] * 3 \
        + [[[z], [y], [x]]] * 2
    voters2 = rng.sample(residents, 40)
    for i, voter in enumerate(voters2):
        order = clean_orders[i % len(clean_orders)]
        await b.cast_ranked_ballot(clean_decision, voter, order,
                                    ANCHOR - timedelta(days=rng.uniform(1, 85)))

    budget_options = ["New gym equipment", "Children's play area upgrade", "Solar panels for common areas",
                       "EV charging points", "Landscaped garden redesign", "Clubhouse Wi-Fi upgrade"]
    budget_costs = [x * 100 for x in [400000, 250000, 350000, 300000, 200000, 100000]]
    budget_decision, budget_opts = await b.make_decision(
        title="Participatory budget: common amenities (Rs 12,00,000)",
        description="Allocate the annual amenities budget across proposed upgrades.",
        group=committee, kind=DecisionKind.BUDGET_ALLOCATION, declared_rule="mes",
        ballot_style=BallotStyle.ALLOCATION, options=budget_options,
        opened_at=ANCHOR - timedelta(days=30), admin=admin,
        budget_minor=120000000, option_costs=budget_costs,
    )
    voters3 = rng.sample(residents, 50)
    for voter in voters3:
        picks = rng.sample(budget_opts, k=rng.randint(1, 3))
        allocation = {str(o.id): rng.randint(20000, o.cost_minor // 2 or 20000) for o in picks}
        await b.cast_allocation_ballot(budget_decision, voter, allocation,
                                        ANCHOR - timedelta(days=rng.uniform(1, 25)))

    await b.flush(force=True)
    return b


# ===========================================================================
# aavartan-robotics (campus_club)
# ===========================================================================

CAMPUS_CATEGORIES = ["venue_booking", "equipment", "funding_request", "permissions",
                      "event_logistics", "membership_query", "grievance", "other"]
CAMPUS_CATEGORY_WEIGHTS = [16, 20, 12, 8, 18, 12, 8, 6]
CAMPUS_PRIORITIES = ["low", "normal", "deadline_bound"]
CAMPUS_PRIORITY_WEIGHTS = [30, 45, 25]
CAMPUS_HISTORY_DAYS = 330
CAMPUS_BRANCHES = ["cse", "ece", "eee", "mech", "civil", "chem"]


async def build_campus_club(db) -> Builder:
    b = Builder(db, seed=20260902)
    rng = b.rng
    await b.make_tenant(
        name="Aavartan Robotics", slug="aavartan-robotics", vertical="campus_club",
        description="A student robotics club, demo-seeded.",
    )
    admin = await b.make_admin("admin@aavartan-robotics.demo", "Faculty Advisor")

    members: list[Member] = []
    for i in range(90):
        year = 1 + (i % 4)
        branch = CAMPUS_BRANCHES[i % len(CAMPUS_BRANCHES)]
        joined_at = ANCHOR - timedelta(days=rng.uniform(20, CAMPUS_HISTORY_DAYS + 120))
        member = await b.make_member(
            email=f"member{i+1}@aavartan-robotics.demo", full_name=f"Member {i+1}",
            branch=branch, year=year, joined_at=joined_at,
        )
        members.append(member)

    core = await b.make_group(
        head=members[0], name="Core Team", description="Club officers and leads.",
        category="official", type_=GroupType.OFFICIAL,
    )
    outreach = await b.make_group(
        head=members[1], name="Outreach Wing", description="Workshops and school outreach.",
        category="unofficial", type_=GroupType.UNOFFICIAL,
    )
    leaders = members[:8]
    for m in leaders:
        await b.make_membership(m, core, role=MembershipRole.LEADER)
    for m in members[8:70]:
        await b.make_membership(m, core, role=MembershipRole.MEMBER)
    for m in members[60:]:
        await b.make_membership(m, outreach, role=MembershipRole.MEMBER)
    await b.make_membership(members[1], outreach, role=MembershipRole.LEADER)

    resolver_weights = [7, 6, 6, 5, 4, 3, 2, 2]
    await b.make_requests(
        group=core, raisers=members, resolvers=leaders, resolver_weights=resolver_weights,
        categories=CAMPUS_CATEGORIES, category_weights=CAMPUS_CATEGORY_WEIGHTS,
        priorities=CAMPUS_PRIORITIES, priority_weights=CAMPUS_PRIORITY_WEIGHTS,
        history_days=CAMPUS_HISTORY_DAYS, changepoint_day=None,
        baseline_per_week=6.0, stepped_per_week=6.0,
        median_resolution_days=3.0, escalate_p=0.02, withdraw_p=0.04,
    )

    # ---- ledger: 3 semester membership-fee cycles ------------------------
    for k in range(3):
        issued_at = ANCHOR - timedelta(days=CAMPUS_HISTORY_DAYS - k * 110)
        if issued_at > ANCHOR:
            continue
        due_at = issued_at + timedelta(days=14)
        await b.make_due_cycle(
            members=members, category="membership_fee", amount_minor=30000,
            issued_at=issued_at, due_at=due_at,
            pay_rate=0.9 if k < 2 else 0.6, receipt_collect_rate=0.7,
            instrument_weights={"upi": 0.6, "cash": 0.3, "bank_transfer": 0.1},
        )
    b.db.add(Contribution(
        tenant_id=b.tenant.id, kind=ContributionKind.CASH, category="college_grant",
        amount_minor=15000000, at=ANCHOR - timedelta(days=200), campaign_ref="annual-grant",
        description="Annual college grant.",
    ))
    b.db.add(Contribution(
        tenant_id=b.tenant.id, kind=ContributionKind.CASH, category="sponsorship",
        amount_minor=5000000, at=ANCHOR - timedelta(days=90), campaign_ref="techfest-sponsor",
        description="Robotics kit sponsor for TechFest.",
    ))
    b.counts.bump("contributions", 2)
    await b.flush(force=True)

    for k in range(6):
        at = ANCHOR - timedelta(days=CAMPUS_HISTORY_DAYS - k * 55)
        if at > ANCHOR:
            continue
        await b.make_expense(category="equipment_purchase", amount_minor=800000, at=at,
                              counterparty_ref="vendor_robotics_parts")
        await b.make_expense(category="printing", amount_minor=150000, at=at)
    await b.make_expense(category="event_expense", amount_minor=4000000,
                          at=ANCHOR - timedelta(days=90), counterparty_ref="vendor_techfest")

    # ---- events + participation ------------------------------------------
    workshop1 = await b.make_event(
        group=core, creator=leaders[0], title="Intro to ROS Workshop",
        description="Hands-on workshop for first-years.", venue="Robotics Lab",
        starts_at=ANCHOR - timedelta(days=150), ends_at=ANCHOR - timedelta(days=150) + timedelta(hours=3),
        status=EventStatus.PUBLISHED, admin=admin, capacity=60,
    )
    techfest = await b.make_event(
        group=core, creator=leaders[1], title="TechFest Robotics Showcase",
        description="Annual showcase of club projects.", venue="Main Auditorium",
        starts_at=ANCHOR - timedelta(days=90), ends_at=ANCHOR - timedelta(days=90) + timedelta(hours=5),
        status=EventStatus.PUBLISHED, admin=admin, capacity=200,
    )
    workshop2 = await b.make_event(
        group=outreach, creator=leaders[1], title="School Outreach: Robotics for Kids",
        description="Community outreach session.", venue="Seminar Hall",
        starts_at=ANCHOR - timedelta(days=40), ends_at=ANCHOR - timedelta(days=40) + timedelta(hours=2),
        status=EventStatus.PUBLISHED, admin=admin, capacity=80,
    )
    await b.make_event(
        group=core, creator=leaders[2], title="Off-campus Hackathon Trip",
        description="Proposed inter-college hackathon trip.", venue="Off-campus",
        starts_at=ANCHOR + timedelta(days=30), ends_at=ANCHOR + timedelta(days=32),
        status=EventStatus.REJECTED, admin=admin,
        rejection_reason="No faculty chaperone confirmed and the budget request exceeds the semester's travel allocation.",
    )
    upcoming = await b.make_event(
        group=core, creator=leaders[0], title="Annual General Meeting + Elections",
        description="Committee elections for next term. Pending admin review.",
        venue="Seminar Hall", starts_at=ANCHOR + timedelta(days=15),
        ends_at=ANCHOR + timedelta(days=15, hours=2), status=EventStatus.SUBMITTED,
    )

    await b.make_attendance(members=members, event=workshop1, rsvp_rate=0.6, attend_given_rsvp=0.7)
    await b.make_attendance(members=members, event=techfest, rsvp_rate=0.75, attend_given_rsvp=0.8)
    await b.make_attendance(members=members[60:], event=workshop2, rsvp_rate=0.5, attend_given_rsvp=0.65)

    await b.make_nudge_experiment(
        members=members, campaign_ref="event-rsvp-reminder",
        start_at=ANCHOR - timedelta(days=95),
        arms={"app_push": 0.35, "email": 0.18},
    )

    # ---- announcements -----------------------------------------------
    await b.make_announcement(
        group=core, author=leaders[0], title="TechFest results are out",
        body="Congratulations to the winning teams! Results posted on the noticeboard.",
        category=AnnouncementCategory.ACHIEVEMENT, created_at=ANCHOR - timedelta(days=85),
        status=AnnouncementStatus.PUBLISHED, admin=admin,
    )
    await b.make_announcement(
        group=core, author=leaders[1], title="New 3D printer available for bookings",
        body="The lab's new 3D printer is available; book slots via the equipment request form.",
        category=AnnouncementCategory.RESOURCE, created_at=ANCHOR - timedelta(days=30),
        status=AnnouncementStatus.PUBLISHED, admin=admin,
    )
    await b.make_announcement(
        group=core, author=leaders[2], title="Elections nomination window open",
        body="Awaiting admin approval before this goes out to all members.",
        category=AnnouncementCategory.GENERAL, created_at=ANCHOR - timedelta(days=3),
        status=AnnouncementStatus.SUBMITTED,
    )
    await b.make_announcement(
        group=core, author=leaders[0], title="Move all meetings online",
        body="Proposal to move all club meetings to a fully online format.",
        category=AnnouncementCategory.GENERAL, created_at=ANCHOR - timedelta(days=60),
        status=AnnouncementStatus.REJECTED, admin=admin,
        rejection_reason="The robotics lab requires in-person access; an online-only format was voted down at the last core team meeting.",
    )

    # ---- decisions: STV committee election + a simple poll --------------
    candidates = [f"Candidate {chr(65 + i)}" for i in range(11)]
    stv_decision, stv_opts = await b.make_decision(
        title="Core Team Committee Election (5 seats)",
        description="Ranked-choice election for five committee seats among eleven candidates.",
        group=core, kind=DecisionKind.ELECTION, declared_rule="stv",
        ballot_style=BallotStyle.RANKED, options=candidates, seats=5,
        opened_at=ANCHOR - timedelta(days=200), admin=admin,
    )
    ids = [o.id for o in stv_opts]
    strength = list(range(11, 0, -1))
    voter_pool = rng.sample(members, 70)
    for voter in voter_pool:
        order = rng.choices(
            population=list(range(11)), weights=strength, k=11,
        )
        seen, ranked = set(), []
        for idx in order:
            if idx not in seen:
                seen.add(idx)
                ranked.append(ids[idx])
        ranking = [[opt] for opt in ranked]
        await b.cast_ranked_ballot(stv_decision, voter, ranking,
                                    ANCHOR - timedelta(days=rng.uniform(1, 195)))

    theme_decision, theme_opts = await b.make_decision(
        title="Preferred theme for next TechFest",
        description="Pick the club's showcase theme for the coming year.",
        group=core, kind=DecisionKind.POLL, declared_rule="schulze",
        ballot_style=BallotStyle.RANKED,
        options=["Autonomous Navigation", "Swarm Robotics", "Human-Robot Interaction"],
        opened_at=ANCHOR - timedelta(days=70), admin=admin,
    )
    p, q, r = (o.id for o in theme_opts)
    theme_orders = [[[p], [q], [r]]] * 30 + [[[q], [p], [r]]] * 15 + [[[r], [q], [p]]] * 5
    voters4 = rng.sample(members, 50)
    for i, voter in enumerate(voters4):
        await b.cast_ranked_ballot(theme_decision, voter, theme_orders[i % len(theme_orders)],
                                    ANCHOR - timedelta(days=rng.uniform(1, 65)))

    await b.flush(force=True)
    return b


# ===========================================================================
# materialization + reporting
# ===========================================================================

async def materialize_and_report(db, tenant: Tenant) -> None:
    await set_tenant_context(db, tenant.id)
    materializer = InsightMaterializer(db, tenant)
    runs = await materializer.materialize_all()
    real = [r for r in runs if not r.insufficient]
    stubbed = [r for r in runs if r.insufficient]
    print(f"\n=== {tenant.slug}: insight_runs after materialize_all() ===")
    print(f"{len(runs)} services walked, {len(real)} real reading(s), {len(stubbed)} insufficient_data")
    if real:
        print("-- real readings --")
        for r in sorted(real, key=lambda x: x.service):
            print(f"  {r.service:45s} n={r.n:<5d} n_censored={r.n_censored:<5d} status={r.worst_status}")
    print("-- insufficient_data (first line of why) --")
    for r in sorted(stubbed, key=lambda x: x.service)[:15]:
        caveat = (r.payload.get("caveats") or [""])[0]
        print(f"  {r.service:45s} {caveat[:90]}")
    if len(stubbed) > 15:
        print(f"  ... and {len(stubbed) - 15} more")


async def main() -> None:
    async with SessionLocal() as db:
        try:
            rwa = await build_rwa_society(db)
            campus = await build_campus_club(db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        print("=== seeded row counts ===")
        print("vaikunth-heights (rwa_society):", dict(rwa.counts))
        print("aavartan-robotics (campus_club):", dict(campus.counts))

        try:
            await materialize_and_report(db, rwa.tenant)
            await materialize_and_report(db, campus.tenant)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    print("\nDemo seed complete. Sign in as admin@vaikunth-heights.demo / "
          f"admin@aavartan-robotics.demo with password '{DEMO_PASSWORD}'.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
