from collections import Counter
from datetime import datetime, timezone

from app.repository import DecisionRepository, MemberRepository, UserRepository, MembershipRepository, GroupRepository
from app.models import DECLARED_RULES, DecisionKind, DecisionStatus, GroupStatus
from app.schemas import (
    CreateDecisionRequest, DecisionItem, DecisionOptionItem, CastBallotRequest, BallotItem,
    DecisionActionResponse,
)
from app.exceptions import (
    DecisionNotFoundError, DecisionAlreadyClosedError, DeclaredRuleInvalidError,
    BallotOptionInvalidError, BallotShapeInvalidError, MemberNotFoundError, TenantNotFoundError,
    DecisionActionNotAllowedError, DecisionNotOpenError, GroupNotFoundError, GroupNotActiveError,
    NotGroupLeaderError,
)
from app.core.messages import DecisionMessages
from app.verticals.adapters import get_adapter

# The editable states, same shape as EventService/AnnouncementService: a
# draft or a rejected decision being revised for resubmission.
_EDITABLE = (DecisionStatus.DRAFT, DecisionStatus.REJECTED)


class DecisionService:
    """
    Card C.15 (decision half), plus the approval-workflow half of the same
    card the DRAFT/SUBMITTED/OPEN/REJECTED/CLOSED shape now enforces. Same
    shape as `LedgerService`: a thin layer that validates the tenant's
    declared vocabulary and role, and hands everything else to
    `DecisionRepository`. No tally, no Condorcet check, no fairness figure
    happens here - that is `app/stats/voting.py`/`budgeting.py`'s job,
    downstream and pure.

    Rule D1 is enforced twice over, deliberately: `Decision.declared_rule` is
    `nullable=False` at the schema (a row cannot exist without one), and this
    service additionally checks the value is one of the six the spine names,
    so a caller cannot silently create a decision with a rule nothing
    downstream knows how to score.

    Authorization was previously entirely absent from `create_decision`
    (anyone with a MEMBER or TENANT_ADMIN token could open a poll for any
    group). It is now: a group-scoped decision needs the caller to lead that
    group or be a TenantAdmin; a tenant-wide decision (`group_id is None`)
    needs a TenantAdmin outright. Voting only opens once a TenantAdmin
    approves a submitted decision, at which point the roster snapshot is
    taken (moved from creation time, where it used to be frozen too early).
    """

    def __init__(self, decision_repo: DecisionRepository, member_repo: MemberRepository,
                 user_repo: UserRepository, tenant_repo, membership_repo: MembershipRepository = None,
                 group_repo: GroupRepository = None):
        self.decision_repo = decision_repo
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.membership_repo = membership_repo
        self.group_repo = group_repo

    async def create_decision(self, payload: dict, data: CreateDecisionRequest) -> DecisionItem:
        tenant = await self._tenant(payload)
        self._validate_declared_rule(data.declared_rule)
        await self._authorize_leader_or_admin(payload, tenant.id, data.group_id)

        decision = await self.decision_repo.create_decision(
            title=data.title, description=data.description, kind=data.kind,
            declared_rule=data.declared_rule.strip().lower(), ballot_style=data.ballot_style,
            group_id=data.group_id, seats=data.seats, quorum_rule=data.quorum_rule,
            budget_minor=data.budget_minor,
        )
        for option in data.options:
            await self.decision_repo.add_option(
                decision, label=option.label, cost_minor=option.cost_minor, tags=option.tags,
            )
        decision = await self.decision_repo.get_by_id(decision.id)
        return self._item(decision)

    async def get_decision(self, payload: dict, decision_id: int) -> DecisionItem:
        decision = await self.decision_repo.get_by_id(decision_id)
        if not decision:
            raise DecisionNotFoundError()
        return self._item(decision)

    async def list_decisions(self, payload: dict, limit: int = 50, offset: int = 0) -> list[DecisionItem]:
        decisions = await self.decision_repo.list_decisions(limit=limit, offset=offset)
        return [self._item(d) for d in decisions]

    async def submit_for_review(self, payload: dict, decision_id: int) -> DecisionActionResponse:
        """The proposer's step: DRAFT (or a REJECTED one being revised) -> SUBMITTED."""
        tenant = await self._tenant(payload)
        decision = await self._get_or_404(decision_id)
        await self._authorize_leader_or_admin(payload, tenant.id, decision.group_id)
        if decision.status not in _EDITABLE:
            raise DecisionActionNotAllowedError(
                "Only a draft or a rejected decision can be submitted for review"
            )
        await self.decision_repo.submit_for_review(decision)
        return self._action(decision, DecisionMessages.SUBMITTED)

    async def approve(self, payload: dict, decision_id: int) -> DecisionActionResponse:
        """
        TenantAdmin-only. Only callable from SUBMITTED. Opens the poll for
        voting and freezes `eligible_strata` at this moment, not at draft
        time - a decision drafted weeks before it is approved must count the
        roster as it stands the day voting actually opens.
        """
        tenant = await self._tenant(payload)
        decision = await self._get_or_404(decision_id)
        if decision.status != DecisionStatus.SUBMITTED:
            raise DecisionActionNotAllowedError(
                "Only a decision submitted for review can be approved"
            )
        eligible_strata = await self._roster_snapshot(tenant)
        await self.decision_repo.approve(decision, self._user_id(payload), eligible_strata)
        return self._action(decision, DecisionMessages.APPROVED)

    async def reject(self, payload: dict, decision_id: int, reason: str) -> DecisionActionResponse:
        """
        TenantAdmin-only. Lands on REJECTED with a reason, not a dead end:
        `submit_for_review` accepts a REJECTED decision for resubmission.
        """
        decision = await self._get_or_404(decision_id)
        if decision.status != DecisionStatus.SUBMITTED:
            raise DecisionActionNotAllowedError(
                "Only a decision submitted for review can be rejected"
            )
        await self.decision_repo.reject(decision, self._user_id(payload), reason)
        return self._action(decision, DecisionMessages.REJECTED)

    async def close_decision(self, payload: dict, decision_id: int) -> DecisionItem:
        tenant = await self._tenant(payload)
        decision = await self._get_or_404(decision_id)
        await self._authorize_leader_or_admin(payload, tenant.id, decision.group_id)
        if decision.status == DecisionStatus.CLOSED:
            raise DecisionAlreadyClosedError()
        if decision.status != DecisionStatus.OPEN:
            raise DecisionNotOpenError()
        decision = await self.decision_repo.close_decision(decision)
        return self._item(decision)

    async def cast_ballot(self, payload: dict, decision_id: int, data: CastBallotRequest) -> BallotItem:
        voter = await self._get_member(payload)
        decision = await self._get_or_404(decision_id)
        if decision.status == DecisionStatus.CLOSED:
            raise DecisionAlreadyClosedError()
        if decision.status != DecisionStatus.OPEN:
            raise DecisionNotOpenError()

        option_ids = {option.id for option in decision.options}
        self._validate_ballot_shape(decision.ballot_style.value, data, option_ids)

        ballot = await self.decision_repo.cast_ballot(
            decision, voter_id=voter.id,
            ranking=[list(tier) for tier in data.ranking],
            approvals=list(data.approvals),
            scores={str(k): v for k, v in data.scores.items()},
            allocation={str(k): v for k, v in data.allocation.items()},
            channel=data.channel,
        )
        return self._ballot_item(ballot)

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _validate_declared_rule(declared_rule: str) -> None:
        if declared_rule.strip().lower() not in DECLARED_RULES:
            raise DeclaredRuleInvalidError(
                f"'{declared_rule}' is not one of the declared voting rules {DECLARED_RULES}"
            )

    @staticmethod
    def _validate_ballot_shape(ballot_style: str, data: CastBallotRequest, option_ids: set[int]) -> None:
        """
        A ballot's non-empty fields must match its decision's declared
        `ballot_style`, and every option it names must belong to the decision
        - an invalid ballot is rejected here rather than silently repaired
        downstream, the same discipline `Ballot.__post_init__` applies to a
        duplicate ranking entry in the stream atom.
        """
        referenced: set[int] = set()
        for tier in data.ranking:
            referenced.update(tier)
        referenced.update(data.approvals)
        referenced.update(data.scores.keys())
        referenced.update(data.allocation.keys())
        if not referenced.issubset(option_ids):
            raise BallotOptionInvalidError()

        shape = {
            "ranked": bool(data.ranking),
            "approval": bool(data.approvals),
            "score": bool(data.scores),
            "single": bool(data.approvals),
            "allocation": bool(data.allocation),
        }
        if not shape.get(ballot_style, False):
            raise BallotShapeInvalidError()

    async def _roster_snapshot(self, tenant) -> list[dict]:
        """
        `DecisionSpec.eligible_strata`, frozen at `opened_at` (spine section
        8): a member_lifecycle fact, not a decision fact, so a later move-in
        cannot change a past turnout figure. Computed from the adapter's own
        `member_strata` the same way `member_events` reads a `Member` row,
        since a dedicated `RosterSnapshot` reducer is not yet wired
        (`streams/reduce.py.roster_snapshot`, statistician's file).
        """
        adapter = get_adapter(tenant.vertical)
        members = await self.member_repo.stream_members(tenant.id, datetime.now(timezone.utc))
        counts: Counter[tuple[tuple[str, str], ...]] = Counter()
        for member in members:
            strata = adapter.member_strata(member)
            key = tuple(sorted(strata.items()))
            counts[key] += 1
        return [
            {"strata": dict(key), "count": count}
            for key, count in counts.items()
        ]

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member

    async def _tenant(self, payload: dict):
        tenant_id = await self.user_repo.get_tenant_id(int(payload.get("sub")))
        if not tenant_id:
            raise TenantNotFoundError()
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()
        return tenant

    async def _authorize_leader_or_admin(self, payload: dict, tenant_id: int,
                                         group_id: int | None) -> None:
        """
        The auth check `create_decision` used to have none of. A group-scoped
        decision needs the caller to lead that group or be a TenantAdmin; a
        tenant-wide decision (`group_id is None`) needs a TenantAdmin outright
        since there is no group leader to defer to.
        """
        is_admin = payload.get("role") == "TENANT_ADMIN"
        if group_id is None:
            if not is_admin:
                raise DecisionActionNotAllowedError(
                    "Only a TenantAdmin can create or manage a tenant-wide decision"
                )
            return
        if is_admin:
            return
        group = await self.group_repo.get_by_id(group_id)
        if not group or group.tenant_id != tenant_id:
            raise GroupNotFoundError()
        if group.status != GroupStatus.ACTIVE:
            raise GroupNotActiveError()
        member = await self._get_member(payload)
        if not await self.membership_repo.is_leader(member.id, group_id):
            raise NotGroupLeaderError()

    async def _get_or_404(self, decision_id: int):
        decision = await self.decision_repo.get_by_id(decision_id)
        if not decision:
            raise DecisionNotFoundError()
        return decision

    @staticmethod
    def _user_id(payload: dict) -> int:
        return int(payload.get("sub"))

    @staticmethod
    def _action(decision, message: str) -> DecisionActionResponse:
        return DecisionActionResponse(
            id=decision.id, status=decision.status, message=message,
            rejection_reason=decision.rejection_reason,
        )

    @staticmethod
    def _item(decision) -> DecisionItem:
        return DecisionItem(
            id=decision.id, title=decision.title, description=decision.description,
            kind=decision.kind, declared_rule=decision.declared_rule,
            ballot_style=decision.ballot_style, seats=decision.seats,
            quorum_rule=decision.quorum_rule, budget_minor=decision.budget_minor,
            status=decision.status, opened_at=decision.opened_at, closed_at=decision.closed_at,
            submitted_at=decision.submitted_at, approved_at=decision.approved_at,
            rejected_at=decision.rejected_at, rejection_reason=decision.rejection_reason,
            options=[
                DecisionOptionItem(id=o.id, label=o.label, cost_minor=o.cost_minor, tags=o.tags)
                for o in decision.options
            ],
        )

    @staticmethod
    def _ballot_item(ballot) -> BallotItem:
        return BallotItem(
            id=ballot.id, decision_id=ballot.decision_id, voter_id=ballot.voter_id,
            cast_at=ballot.cast_at, ranking=ballot.ranking, approvals=ballot.approvals,
            scores={int(k): v for k, v in ballot.scores.items()},
            allocation={int(k): v for k, v in ballot.allocation.items()},
        )
