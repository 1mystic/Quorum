from fastapi import APIRouter, Depends, Query, Security
from app.schemas import (
    RaiseRequestRequest, ReplyRequestRequest, RaiseRequestResponse, MyRequestItem,
    LeaderRequestItem, RequestActionResponse, OpenRequestCountResponse,
    AssignRequestRequest, MergeRequestRequest
)
from app.services import RequestService
from app.core.di import get_request_service, get_user_info
from app.models import RequestStatus

request_router = APIRouter(prefix="/requests", tags=["Requests"])


@request_router.post("", response_model=RaiseRequestResponse)
async def raise_request(
    data: RaiseRequestRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.raise_request(payload, data)


@request_router.get("", response_model=list[MyRequestItem])
async def my_requests(
    status: RequestStatus | None = Query(None),
    group_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.my_requests(payload, status=status, group_id=group_id,
                                   limit=limit, offset=offset)


@request_router.get("/group", response_model=list[LeaderRequestItem])
async def group_request_queue(
    status: RequestStatus | None = Query(None),
    group_id: int | None = Query(None, description="Limit to a single group you lead; ignored for a TENANT_ADMIN, who sees every group"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.group_queue(payload, status=status, group_id=group_id,
                                    limit=limit, offset=offset)


@request_router.get("/group/open-count", response_model=OpenRequestCountResponse)
async def open_request_count(
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.open_count(payload)


# reply/resolve/escalate/withdraw/assign/reassign/pause/resume/merge/reopen
# below all go through RequestService._managed_request, which requires the
# caller to be the group's own leader (Membership.is_leader). They stay
# MEMBER-only: a TENANT_ADMIN has no Member row to be a leader with, and
# widening the scope here would not grant real access, only a different
# error. Tenant-wide oversight for an admin is the group_queue/open-count
# routes above, not these leader actions.
@request_router.post("/{request_id}/reply", response_model=RequestActionResponse)
async def reply_to_request(
    request_id: int,
    data: ReplyRequestRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.reply(payload, request_id, data)


@request_router.patch("/{request_id}/resolve", response_model=RequestActionResponse)
async def resolve_request(
    request_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.resolve(payload, request_id)


@request_router.patch("/{request_id}/escalate", response_model=RequestActionResponse)
async def escalate_request(
    request_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.escalate(payload, request_id)


@request_router.patch("/{request_id}/withdraw", response_model=RequestActionResponse)
async def withdraw_request(
    request_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.withdraw(payload, request_id)


@request_router.patch("/{request_id}/assign", response_model=RequestActionResponse)
async def assign_request(
    request_id: int,
    data: AssignRequestRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.assign(payload, request_id, data.assignee_member_id)


@request_router.patch("/{request_id}/reassign", response_model=RequestActionResponse)
async def reassign_request(
    request_id: int,
    data: AssignRequestRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.reassign(payload, request_id, data.assignee_member_id)


@request_router.patch("/{request_id}/pause", response_model=RequestActionResponse)
async def pause_request(
    request_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.pause(payload, request_id)


@request_router.patch("/{request_id}/resume", response_model=RequestActionResponse)
async def resume_request(
    request_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.resume(payload, request_id)


@request_router.patch("/{request_id}/merge", response_model=RequestActionResponse)
async def merge_request(
    request_id: int,
    data: MergeRequestRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.merge(payload, request_id, data.into_request_id)


@request_router.patch("/{request_id}/reopen", response_model=RequestActionResponse)
async def reopen_request(
    request_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.reopen(payload, request_id)
