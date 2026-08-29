from app.models import (
    Request, RequestCategory, RequestStatus, Group, Membership, MembershipRole,
    MembershipStatus, Member, User
)
from sqlalchemy import select, func
from sqlalchemy.orm import aliased, selectinload
from datetime import datetime, timezone

from app.repository.base import TenantScopedRepository


class RequestRepository(TenantScopedRepository):
    """
    The flagship tenant-scoped repository (docs/RULES.md section 5): every
    query below adds `Request.tenant_id == self.tenant_id`, on top of
    whatever member_id/group_id scoping the query already had. That second
    filter is what makes a request from another tenant structurally
    unreachable through this class, not just unreachable in practice because
    nobody happens to pass a foreign id in.
    """

    async def create_request(self, member_id: int, group_id: int, event_id: int | None,
                           category: RequestCategory, title: str, description: str) -> Request:
        new_request = Request(
            tenant_id=self.tenant_id,
            member_id=member_id,
            group_id=group_id,
            event_id=event_id,
            category=category,
            status=RequestStatus.OPEN,
            title=title,
            description=description,
        )
        self.db.add(new_request)
        await self.db.flush()
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
        request.response_body = response_body
        request.responded_by = responder_id
        request.responded_at = datetime.now(timezone.utc)
        return request

    async def set_status(self, request: Request, status: RequestStatus) -> Request:
        request.status = status
        if status == RequestStatus.RESOLVED:
            request.resolved_at = datetime.now(timezone.utc)
        return request
