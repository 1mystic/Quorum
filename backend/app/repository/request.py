from app.models import (
    Request, RequestStatus, RequestEventLog, RequestEventKind, Group, Membership,
    MembershipRole, MembershipStatus, Member, User
)
from sqlalchemy import select, func
from sqlalchemy.orm import aliased, selectinload
from datetime import datetime, timezone

from app.repository.base import TenantScopedRepository

# RequestStatus values that are terminal outcomes, mapped onto the
# RequestEventLog kind logged when a request reaches them (docs/DATA_SPINE.md
# RequestSpell.outcome / rule C5's competing-risks terminals).
_TERMINAL_KIND = {
    RequestStatus.RESOLVED: RequestEventKind.RESOLVED,
    RequestStatus.ESCALATED: RequestEventKind.ESCALATED,
    RequestStatus.WITHDRAWN: RequestEventKind.WITHDRAWN,
    RequestStatus.MERGED: RequestEventKind.MERGED,
}
_OUTCOME = {
    RequestStatus.RESOLVED: "resolved",
    RequestStatus.ESCALATED: "escalated",
    RequestStatus.WITHDRAWN: "withdrawn",
    RequestStatus.MERGED: "merged",
}


class RequestRepository(TenantScopedRepository):
    """
    The flagship tenant-scoped repository (docs/RULES.md section 5): every
    query below adds `Request.tenant_id == self.tenant_id`, on top of
    whatever member_id/group_id scoping the query already had. That second
    filter is what makes a request from another tenant structurally
    unreachable through this class, not just unreachable in practice because
    nobody happens to pass a foreign id in.

    Card C.8: this class is also where every `request_flow` lifecycle
    transition is written, and every write here appends a row to
    `RequestEventLog` alongside whatever it does to `Request` itself. The log
    is the append-only atom source docs/DATA_SPINE.md's stream adapter reduces
    into a `RequestSpell`; the `Request` columns it also updates
    (`status`/`terminal_at`/`outcome`) are a read convenience, never the
    thing a stream reads.
    """

    async def create_request(self, member_id: int, group_id: int, event_id: int | None,
                           category: str, title: str, description: str,
                           subcategory: str | None = None, priority: str | None = None,
                           channel: str | None = None, location_ref: str | None = None) -> Request:
        group = await self.db.get(Group, group_id)
        new_request = Request(
            tenant_id=self.tenant_id,
            member_id=member_id,
            group_id=group_id,
            event_id=event_id,
            category=category,
            subcategory=subcategory,
            priority=priority,
            channel=channel,
            location_ref=location_ref,
            status=RequestStatus.OPEN,
            title=title,
            description=description,
        )
        self.db.add(new_request)
        await self.db.flush()
        self.db.add(RequestEventLog(
            tenant_id=self.tenant_id,
            request_id=new_request.id,
            kind=RequestEventKind.OPENED,
            at=new_request.created_at or datetime.now(timezone.utc),
            actor_id=member_id,
            category=category,
            subcategory=subcategory,
            priority=priority,
            channel=channel,
            location_ref=location_ref,
            group_id=group_id,
        ))
        return new_request

    async def get_by_id(self, request_id: int) -> Request | None:
        result = await self.db.execute(
            self.scope(select(Request), Request)
            .where(Request.id == request_id)
            .options(selectinload(Request.group))
        )
        return result.scalar_one_or_none()

    async def list_by_member(self, member_id: int, status: RequestStatus | None = None,
                              group_id: int | None = None, limit: int = 50,
                              offset: int = 0) -> list[tuple[Request, str, str | None]]:
        conditions = [Request.member_id == member_id]
        if status is not None:
            conditions.append(Request.status == status)
        if group_id is not None:
            conditions.append(Request.group_id == group_id)

        responder = aliased(Member)
        responder_user = aliased(User)

        result = await self.db.execute(
            self.scope(select(Request, Group.name, responder_user.full_name), Request)
            .join(Group, Group.id == Request.group_id)
            .outerjoin(responder, responder.id == Request.responded_by)
            .outerjoin(responder_user, responder_user.id == responder.user_id)
            .where(*conditions)
            .order_by(Request.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.all()

    async def list_for_leader(self, member_id: int, status: RequestStatus | None = None,
                              group_id: int | None = None, limit: int = 50,
                              offset: int = 0) -> list[tuple[Request, str, str, str | None]]:
        conditions = [
            Membership.member_id == member_id,
            Membership.role == MembershipRole.LEADER,
            Membership.status == MembershipStatus.APPROVED,
        ]
        if status is not None:
            conditions.append(Request.status == status)
        if group_id is not None:
            conditions.append(Request.group_id == group_id)

        raiser = aliased(Member)
        raiser_user = aliased(User)
        responder = aliased(Member)
        responder_user = aliased(User)

        result = await self.db.execute(
            self.scope(
                select(Request, Group.name, raiser_user.full_name, responder_user.full_name), Request
            )
            .join(Group, Group.id == Request.group_id)
            .join(Membership, Membership.group_id == Request.group_id)
            .join(raiser, raiser.id == Request.member_id)
            .join(raiser_user, raiser_user.id == raiser.user_id)
            .outerjoin(responder, responder.id == Request.responded_by)
            .outerjoin(responder_user, responder_user.id == responder.user_id)
            .where(*conditions)
            .order_by(Request.status, Request.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return result.all()

    async def count_open_for_leader(self, member_id: int) -> int:
        result = await self.db.execute(
            self.scope(select(func.count(Request.id)), Request)
            .join(Membership, Membership.group_id == Request.group_id)
            .where(
                Membership.member_id == member_id,
                Membership.role == MembershipRole.LEADER,
                Membership.status == MembershipStatus.APPROVED,
                Request.status != RequestStatus.RESOLVED,
            )
        )
        return result.scalar_one()

    async def set_response(self, request: Request, response_body: str, responder_id: int) -> Request:
        now = datetime.now(timezone.utc)
        request.response_body = response_body
        request.responded_by = responder_id
        request.responded_at = now
        self.db.add(RequestEventLog(
            tenant_id=self.tenant_id,
            request_id=request.id,
            kind=RequestEventKind.ACKNOWLEDGED,
            at=now,
            actor_id=responder_id,
            assignee_id=responder_id,
            category=request.category,
            group_id=request.group_id,
        ))
        return request

    async def set_status(self, request: Request, status: RequestStatus,
                          actor_id: int | None = None) -> Request:
        """
        Move a request to any status, terminal or not, logging the matching
        RequestEventLog row for the terminal ones (rule C5's competing-risks
        outcomes included). `RequestStatus.MERGED` is not set here directly -
        use `merge_into`, which also records `merged_into_id`.
        """
        now = datetime.now(timezone.utc)
        request.status = status
        kind = _TERMINAL_KIND.get(status)
        if kind is not None:
            request.terminal_at = now
            request.outcome = _OUTCOME[status]
            if status == RequestStatus.RESOLVED:
                request.resolved_at = now
            self.db.add(RequestEventLog(
                tenant_id=self.tenant_id,
                request_id=request.id,
                kind=kind,
                at=now,
                actor_id=actor_id,
                category=request.category,
                group_id=request.group_id,
            ))
        else:
            self.db.add(RequestEventLog(
                tenant_id=self.tenant_id,
                request_id=request.id,
                kind=RequestEventKind.STATUS_CHANGE,
                at=now,
                actor_id=actor_id,
                category=request.category,
                group_id=request.group_id,
            ))
        return request

    async def assign(self, request: Request, assignee_id: int, actor_id: int | None,
                     reassign: bool = False) -> Request:
        now = datetime.now(timezone.utc)
        self.db.add(RequestEventLog(
            tenant_id=self.tenant_id,
            request_id=request.id,
            kind=RequestEventKind.REASSIGNED if reassign else RequestEventKind.ASSIGNED,
            at=now,
            actor_id=actor_id,
            assignee_id=assignee_id,
            category=request.category,
            group_id=request.group_id,
        ))
        return request

    async def pause(self, request: Request, actor_id: int | None) -> Request:
        now = datetime.now(timezone.utc)
        self.db.add(RequestEventLog(
            tenant_id=self.tenant_id,
            request_id=request.id,
            kind=RequestEventKind.PAUSED,
            at=now,
            actor_id=actor_id,
            category=request.category,
            group_id=request.group_id,
        ))
        return request

    async def resume(self, request: Request, actor_id: int | None) -> Request:
        now = datetime.now(timezone.utc)
        self.db.add(RequestEventLog(
            tenant_id=self.tenant_id,
            request_id=request.id,
            kind=RequestEventKind.RESUMED,
            at=now,
            actor_id=actor_id,
            category=request.category,
            group_id=request.group_id,
        ))
        return request

    async def merge_into(self, request: Request, into_request_id: int,
                         actor_id: int | None) -> Request:
        """Rule C7: a merged request is excluded, never double-counted with the survivor."""
        now = datetime.now(timezone.utc)
        request.status = RequestStatus.MERGED
        request.terminal_at = now
        request.outcome = "merged"
        request.merged_into_id = into_request_id
        self.db.add(RequestEventLog(
            tenant_id=self.tenant_id,
            request_id=request.id,
            kind=RequestEventKind.MERGED,
            at=now,
            actor_id=actor_id,
            category=request.category,
            group_id=request.group_id,
            parent_request_id=into_request_id,
        ))
        return request

    async def reopen(self, request: Request, actor_id: int | None) -> Request:
        """
        Logs a `reopened` atom on the same request_ref. Whether the reducer
        treats this as extending the existing spell or starting a new one is
        the declared per-vertical `reopen_policy` (rule C6), decided
        downstream by the stream adapter/reducer, not here.
        """
        now = datetime.now(timezone.utc)
        request.status = RequestStatus.OPEN
        request.terminal_at = None
        request.outcome = None
        request.merged_into_id = None
        self.db.add(RequestEventLog(
            tenant_id=self.tenant_id,
            request_id=request.id,
            kind=RequestEventKind.REOPENED,
            at=now,
            actor_id=actor_id,
            category=request.category,
            group_id=request.group_id,
        ))
        return request

    # ---- stream fetch -----------------------------------------------------
    #
    # "You fetch and cache; they compute." These two methods are the whole of
    # what request_flow hands to a stream adapter: every Request opened before
    # the window end (rule C1 - no status/outcome filter, ever) and every
    # logged lifecycle event for those requests. No arithmetic happens here.

    async def stream_requests(self, window_end: datetime) -> list[Request]:
        result = await self.db.execute(
            self.scope(select(Request), Request)
            .where(Request.created_at < window_end)
            .options(selectinload(Request.events))
        )
        return list(result.scalars().unique().all())

    async def stream_events(self, window_end: datetime) -> list[RequestEventLog]:
        result = await self.db.execute(
            self.scope(select(RequestEventLog), RequestEventLog)
            .where(RequestEventLog.at < window_end)
            .order_by(RequestEventLog.request_id, RequestEventLog.at)
        )
        return list(result.scalars().all())
