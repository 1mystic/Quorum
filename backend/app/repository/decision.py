from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Decision, DecisionOption, Ballot, DecisionStatus
from app.repository.base import TenantScopedRepository


class DecisionRepository(TenantScopedRepository):
    """
    Tenant-scoped, same pattern as `RequestRepository`/`LedgerRepository`.
    `stream_decisions` is the whole of what this class hands the `decision`
    stream adapter: every decision opened before the window end, its options
    and its ballots, tenant-scoped, no arithmetic, no tallying. Rule D1 is
    already enforced at write time (`create_decision` requires `declared_rule`)
    and at the schema (`Decision.declared_rule` is `nullable=False`), so a row
    that reaches here always has one.
    """

    async def create_decision(
        self, *, title: str, kind, declared_rule: str, ballot_style,
        group_id: int | None = None,
        description: str | None = None, seats: int = 1,
        quorum_rule: str | None = None, budget_minor: int | None = None,
    ) -> Decision:
        """
        Created as DRAFT: `opened_at`/`eligible_strata` stay unset until a
        TenantAdmin approves a submitted decision (see `approve` below), so
        the roster snapshot is genuinely frozen at the moment voting opens.
        """
        decision = Decision(
            tenant_id=self.tenant_id,
            group_id=group_id,
            title=title,
            description=description,
            kind=kind,
            declared_rule=declared_rule,
            seats=seats,
            quorum_rule=quorum_rule,
            budget_minor=budget_minor,
            ballot_style=ballot_style,
            status=DecisionStatus.DRAFT,
        )
        self.db.add(decision)
        await self.db.flush()
        return decision

    async def submit_for_review(self, decision: Decision) -> Decision:
        decision.status = DecisionStatus.SUBMITTED
        decision.submitted_at = datetime.now(timezone.utc)
        return decision

    async def approve(self, decision: Decision, approved_by: int, eligible_strata: list) -> Decision:
        decision.status = DecisionStatus.OPEN
        decision.approved_by = approved_by
        decision.approved_at = datetime.now(timezone.utc)
        decision.opened_at = datetime.now(timezone.utc)
        decision.eligible_strata = eligible_strata
        return decision

    async def reject(self, decision: Decision, rejected_by: int, reason: str) -> Decision:
        decision.status = DecisionStatus.REJECTED
        decision.rejected_by = rejected_by
        decision.rejected_at = datetime.now(timezone.utc)
        decision.rejection_reason = reason
        return decision

    async def add_option(
        self, decision: Decision, *, label: str, cost_minor: int | None = None,
        tags: list[str] | None = None, proposer_id: int | None = None,
    ) -> DecisionOption:
        option = DecisionOption(
            tenant_id=self.tenant_id,
            decision_id=decision.id,
            label=label,
            cost_minor=cost_minor,
            tags=tags or [],
            proposer_id=proposer_id,
        )
        self.db.add(option)
        await self.db.flush()
        return option

    async def close_decision(self, decision: Decision) -> Decision:
        decision.closed_at = datetime.now(timezone.utc)
        decision.status = DecisionStatus.CLOSED
        return decision

    async def cast_ballot(
        self, decision: Decision, *, voter_id: int, ranking: list | None = None,
        approvals: list[int] | None = None, scores: dict | None = None,
        allocation: dict | None = None, channel: str | None = None,
    ) -> Ballot:
        """
        One ballot per voter per decision (`uq_ballot_decision_voter`): a
        resubmission replaces the existing row rather than accumulating a
        second one, matching how a real poll works.
        """
        existing = await self._existing_ballot(decision.id, voter_id)
        if existing is not None:
            existing.ranking = ranking or []
            existing.approvals = approvals or []
            existing.scores = scores or {}
            existing.allocation = allocation or {}
            existing.channel = channel
            existing.cast_at = datetime.now(timezone.utc)
            await self.db.flush()
            return existing
        ballot = Ballot(
            tenant_id=self.tenant_id,
            decision_id=decision.id,
            voter_id=voter_id,
            ranking=ranking or [],
            approvals=approvals or [],
            scores=scores or {},
            allocation=allocation or {},
            channel=channel,
        )
        self.db.add(ballot)
        await self.db.flush()
        return ballot

    async def _existing_ballot(self, decision_id: int, voter_id: int) -> Ballot | None:
        result = await self.db.execute(
            self.scope(select(Ballot), Ballot)
            .where(Ballot.decision_id == decision_id, Ballot.voter_id == voter_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, decision_id: int) -> Decision | None:
        result = await self.db.execute(
            self.scope(select(Decision), Decision)
            .where(Decision.id == decision_id)
            .options(selectinload(Decision.options), selectinload(Decision.ballots))
        )
        return result.scalar_one_or_none()

    async def list_decisions(self, limit: int = 50, offset: int = 0) -> list[Decision]:
        result = await self.db.execute(
            self.scope(select(Decision), Decision)
            # created_at, not opened_at: a DRAFT/SUBMITTED/REJECTED decision
            # has no opened_at yet and would sort unpredictably by it.
            .order_by(Decision.created_at.desc())
            .limit(limit)
            .offset(offset)
            # DecisionItem._item reads decision.options; without an eager
            # load here that lazy-loads outside the async session context
            # during response serialization (MissingGreenlet), unlike
            # get_by_id which already selectinload's this relationship.
            .options(selectinload(Decision.options))
        )
        return list(result.scalars().unique().all())

    # ---- stream fetch -------------------------------------------------

    async def stream_decisions(self, window_end: datetime) -> list[Decision]:
        result = await self.db.execute(
            self.scope(select(Decision), Decision)
            .where(Decision.opened_at < window_end)
            .options(selectinload(Decision.options), selectinload(Decision.ballots))
        )
        return list(result.scalars().unique().all())
