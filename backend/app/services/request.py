from app.repository import (
    RequestRepository, GroupRepository, EventRepository, MembershipRepository,
    MemberRepository, UserRepository
)
from app.models import Request, RequestStatus, GroupStatus
from app.schemas import (
    RaiseRequestRequest, ReplyRequestRequest, RaiseRequestResponse, RequestResponseInfo,
    MyRequestItem, LeaderRequestItem, RequestActionResponse, OpenRequestCountResponse
)
from app.exceptions import (
    RequestNotFoundError, RequestActionNotAllowedError, GroupNotFoundError, GroupNotActiveError,
    NotGroupLeaderError, MemberNotFoundError, TenantNotFoundError, EventNotFoundError
)
from app.core.messages import RequestMessages


class RequestService:
    def __init__(self, request_repo: RequestRepository, group_repo: GroupRepository,
                 event_repo: EventRepository, membership_repo: MembershipRepository,
                 member_repo: MemberRepository, user_repo: UserRepository):
        self.request_repo = request_repo
        self.group_repo = group_repo
        self.event_repo = event_repo
        self.membership_repo = membership_repo
        self.member_repo = member_repo
        self.user_repo = user_repo

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

        request = await self.request_repo.create_request(
            member_id=member.id,
            group_id=group.id,
            event_id=data.event_id,
            category=data.category,
            title=data.title,
            description=data.description,
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
                status=request.status,
                title=request.title,
                description=request.description,
                response=self._response_info(request, responder_name),
                created_at=request.created_at,
                resolved_at=request.resolved_at,
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
                status=request.status,
                title=request.title,
                description=request.description,
                response=self._response_info(request, responder_name),
                created_at=request.created_at,
                resolved_at=request.resolved_at,
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
        if request.status == RequestStatus.RESOLVED:
            raise RequestActionNotAllowedError("A resolved request cannot be replied to")

        await self.request_repo.set_response(request, data.reply, member.id)
        await self.request_repo.set_status(request, RequestStatus.IN_PROGRESS)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.REPLIED,
        )

    async def resolve(self, payload: dict, request_id: int) -> RequestActionResponse:
        request = await self._managed_request(payload, request_id)
        if request.status == RequestStatus.RESOLVED:
            raise RequestActionNotAllowedError("Request is already resolved")

        await self.request_repo.set_status(request, RequestStatus.RESOLVED)
        return RequestActionResponse(
            id=request.id, status=request.status, message=RequestMessages.RESOLVED,
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
