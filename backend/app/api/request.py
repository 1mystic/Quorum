from fastapi import APIRouter, Depends, Query, Security
from app.schemas import (
    RaiseRequestRequest, ReplyRequestRequest, RaiseRequestResponse, MyRequestItem,
    LeaderRequestItem, RequestActionResponse, OpenRequestCountResponse
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
    group_id: int | None = Query(None, description="Limit to a single group you lead"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.group_queue(payload, status=status, group_id=group_id,
                                    limit=limit, offset=offset)


@request_router.get("/group/open-count", response_model=OpenRequestCountResponse)
async def open_request_count(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: RequestService = Depends(get_request_service),
):
    return await service.open_count(payload)


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
