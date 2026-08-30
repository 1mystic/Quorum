from app.repository import (
    RequestRepository, GroupRepository, EventRepository, MembershipRepository,
    MemberRepository, UserRepository, TenantRepository
)
from app.models import Request, RequestStatus, GroupStatus
from app.schemas import (
    RaiseRequestRequest, ReplyRequestRequest, RaiseRequestResponse, RequestResponseInfo,
    MyRequestItem, LeaderRequestItem, RequestActionResponse, OpenRequestCountResponse
)
from app.exceptions import (
    RequestNotFoundError, RequestActionNotAllowedError, GroupNotFoundError, GroupNotActiveError,
    NotGroupLeaderError, MemberNotFoundError, TenantNotFoundError, EventNotFoundError,
    RequestCategoryInvalidError, RequestAlreadyTerminalError, RequestMergeTargetInvalidError
)
from app.core.messages import RequestMessages
from app.verticals.adapters import get_adapter

_TERMINAL = {RequestStatus.RESOLVED, RequestStatus.ESCALATED, RequestStatus.WITHDRAWN,
             RequestStatus.MERGED}


class RequestService:
    def __init__(self, request_repo: RequestRepository, group_repo: GroupRepository,
                 event_repo: EventRepository, membership_repo: MembershipRepository,
                 member_repo: MemberRepository, user_repo: UserRepository,
                 tenant_repo: TenantRepository):
        self.request_repo = request_repo
        self.group_repo = group_repo
        self.event_repo = event_repo
        self.membership_repo = membership_repo
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo

    async def raise_request(self, payload: dict, data: RaiseRequestRequest) -> RaiseRequestResponse:
        member = await self._get_member(payload)
        tenant_id = await self._tenant_id(payload)

        group = await self.group_repo.get_by_id(data.group_id)
        if not group or group.tenant_id != tenant_id:
            raise GroupNotFoundError()
        if group.status != GroupStatus.ACTIVE:
            raise GroupNotActiveError()

        if data.event_id is not None:
            event = await self.event_repo.get_by_id(data.event_id)
            if not event or event.group_id != group.id:
                raise EventNotFoundError()

        await self._validate_vocabulary(tenant_id, data.category, data.priority)

        request = await self.request_repo.create_request(
            member_id=member.id,
            group_id=group.id,
            event_id=data.event_id,
            category=data.category,
            title=data.title,
            description=data.description,
            subcategory=data.subcategory,
            priority=data.priority,
            channel=data.channel,
            location_ref=data.location_ref,
        )
        return RaiseRequestResponse(
            id=request.id, group_id=group.id, title=request.title, category=request.category,
            status=request.status, message=RequestMessages.RAISED,
        )

    async def my_requests(self, payload: dict, status: RequestStatus | None = None,
                        group_id: int | None = None, limit: int = 50,
                        offset: int = 0) -> list[MyRequestItem]:
        member = await self._get_member(payload)
        rows = await self.request_repo.list_by_member(
            member.id, status=status, group_id=group_id, limit=limit, offset=offset
        )
        return [
            MyRequestItem(
                id=request.id,
                group_id=request.group_id,
                group_name=group_name,
                event_id=request.event_id,
                category=request.category,
                subcategory=request.subcategory,
                priority=request.priority,
                channel=request.channel,
                location_ref=request.location_ref,
                status=request.status,
                title=request.title,
                description=request.description,
                response=self._response_info(request, responder_name),
                created_at=request.created_at,
                resolved_at=request.resolved_at,
                terminal_at=request.terminal_at,
                outcome=request.outcome,
            )
            for request, group_name, responder_name in rows
        ]

    async def group_queue(self, payload: dict, status: RequestStatus | None = None,
                         group_id: int | None = None, limit: int = 50,
                         offset: int = 0) -> list[LeaderRequestItem]:
        member = await self._get_member(payload)
        rows = await self.request_repo.list_for_leader(
            member.id, status=status, group_id=group_id, limit=limit, offset=offset
        )
        return [
            LeaderRequestItem(
                id=request.id,
                group_id=request.group_id,
                group_name=group_name,
                member_id=request.member_id,
                raised_by=raised_by,
                event_id=request.event_id,
                category=request.category,
                subcategory=request.subcategory,
                priority=request.priority,
                channel=request.channel,
                location_ref=request.location_ref,
                status=request.status,
                title=request.title,
                description=request.description,
                response=self._response_info(request, responder_name),
                created_at=request.created_at,
                resolved_at=request.resolved_at,
                terminal_at=request.terminal_at,
                outcome=request.outcome,
            )
            for request, group_name, raised_by, responder_name in rows
        ]

    async def open_count(self, payload: dict) -> OpenRequestCountResponse:
        member = await self._get_member(payload)
        count = await self.request_repo.count_open_for_leader(member.id)
        return OpenRequestCountResponse(count=count)

    async def reply(self, payload: dict, request_id: int,
                    data: ReplyRequestRequest) -> RequestActionResponse:
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        if request.status in _TERMINAL:
            raise RequestActionNotAllowedError("A closed request cannot be replied to")

        await self.request_repo.set_response(request, data.reply, member.id)
        await self.request_repo.set_status(request, RequestStatus.IN_PROGRESS, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.REPLIED,
        )

    async def resolve(self, payload: dict, request_id: int) -> RequestActionResponse:
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        self._require_not_terminal(request)

        await self.request_repo.set_status(request, RequestStatus.RESOLVED, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.RESOLVED,
        )

    async def escalate(self, payload: dict, request_id: int) -> RequestActionResponse:
        """
        Rule C5's second competing-risks terminal: an escalated request will
        not resolve through this queue. Cause-specific analysis that treats it
        as neutral censoring overstates eventual resolution, which is exactly
        why the outcome has to be observable and not folded into "resolved".
        """
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        self._require_not_terminal(request)

        await self.request_repo.set_status(request, RequestStatus.ESCALATED, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.ESCALATED,
        )

    async def withdraw(self, payload: dict, request_id: int) -> RequestActionResponse:
        """The requester or a leader can withdraw; either way it is a competing risk, not a resolution."""
        member = await self._get_member(payload)
        request = await self.request_repo.get_by_id(request_id)
        if not request or request.group.tenant_id != await self._tenant_id(payload):
            raise RequestNotFoundError()
        is_owner = request.member_id == member.id
        is_leader = await self.membership_repo.is_leader(member.id, request.group_id)
        if not (is_owner or is_leader):
            raise NotGroupLeaderError()
        self._require_not_terminal(request)

        await self.request_repo.set_status(request, RequestStatus.WITHDRAWN, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.WITHDRAWN,
        )

    async def assign(self, payload: dict, request_id: int, assignee_member_id: int) -> RequestActionResponse:
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        self._require_not_terminal(request)

        assignee = await self.member_repo.get_by_id(assignee_member_id)
        if not assignee or assignee.tenant_id != await self._tenant_id(payload):
            raise MemberNotFoundError()

        await self.request_repo.assign(request, assignee_member_id, member.id, reassign=False)
        if request.status == RequestStatus.OPEN:
            await self.request_repo.set_status(request, RequestStatus.IN_PROGRESS, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.ASSIGNED,
        )

    async def reassign(self, payload: dict, request_id: int, assignee_member_id: int) -> RequestActionResponse:
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        self._require_not_terminal(request)

        assignee = await self.member_repo.get_by_id(assignee_member_id)
        if not assignee or assignee.tenant_id != await self._tenant_id(payload):
            raise MemberNotFoundError()

        await self.request_repo.assign(request, assignee_member_id, member.id, reassign=True)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.REASSIGNED,
        )

    async def pause(self, payload: dict, request_id: int) -> RequestActionResponse:
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        self._require_not_terminal(request)

        await self.request_repo.pause(request, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.PAUSED,
        )

    async def resume(self, payload: dict, request_id: int) -> RequestActionResponse:
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        self._require_not_terminal(request)

        await self.request_repo.resume(request, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.RESUMED,
        )

    async def merge(self, payload: dict, request_id: int, into_request_id: int) -> RequestActionResponse:
        """Rule C7: the survivor keeps counting; the merged row is excluded, never double-counted."""
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        self._require_not_terminal(request)

        if into_request_id == request_id:
            raise RequestMergeTargetInvalidError()
        target = await self.request_repo.get_by_id(into_request_id)
        if not target or target.group.tenant_id != await self._tenant_id(payload):
            raise RequestNotFoundError()
        if target.status == RequestStatus.MERGED:
            raise RequestMergeTargetInvalidError()

        await self.request_repo.merge_into(request, into_request_id, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.MERGED,
        )

    async def reopen(self, payload: dict, request_id: int) -> RequestActionResponse:
        member = await self._get_member(payload)
        request = await self._managed_request(payload, request_id)
        if request.status not in _TERMINAL:
            raise RequestActionNotAllowedError("Only a closed request can be reopened")

        await self.request_repo.reopen(request, member.id)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.REOPENED,
        )

    @staticmethod
    def _response_info(request: Request, responder_name: str | None) -> RequestResponseInfo | None:
        if not request.response_body:
            return None
        return RequestResponseInfo(
            by=responder_name or "",
            text=request.response_body,
            at=request.responded_at,
        )

    @staticmethod
    def _require_not_terminal(request: Request) -> None:
        if request.status in _TERMINAL:
            raise RequestAlreadyTerminalError()

    async def _validate_vocabulary(self, tenant_id: int, category: str,
                                   priority: str | None) -> None:
        """
        docs/VERTICALS.md's declared vocabulary per tenant vertical, enforced
        here rather than by a database constraint (rule V3: the column is
        always `request.category`; a vertical is free to declare its own
        values without a migration).
        """
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()
        adapter = get_adapter(tenant.vertical)
        if category.strip().lower() not in adapter.request_categories:
            raise RequestCategoryInvalidError(
                f"'{category}' is not in {tenant.vertical}'s declared request categories"
            )
        if priority is not None and priority.strip().lower() not in adapter.request_priorities:
            raise RequestCategoryInvalidError(
                f"'{priority}' is not in {tenant.vertical}'s declared request priorities"
            )

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member

    async def _tenant_id(self, payload: dict) -> int:
        tenant_id = await self.user_repo.get_tenant_id(int(payload.get("sub")))
        if not tenant_id:
            raise TenantNotFoundError()
        return tenant_id

    async def _managed_request(self, payload: dict, request_id: int) -> Request:
        member = await self._get_member(payload)
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            raise RequestNotFoundError()
        if request.group.tenant_id != await self._tenant_id(payload):
            raise RequestNotFoundError()
        if not await self.membership_repo.is_leader(member.id, request.group_id):
            raise NotGroupLeaderError()
        return request
