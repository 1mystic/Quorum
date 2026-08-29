from fastapi import APIRouter, Depends, Query, Security
from app.schemas import (
    RaiseIssueRequest, ReplyIssueRequest, RaiseIssueResponse, MyIssueItem,
    LeaderIssueItem, IssueActionResponse, OpenIssueCountResponse
)
from app.services import IssueService
from app.core.di import get_issue_service, get_user_info
from app.models import IssueStatus

issue_router = APIRouter(prefix="/issues", tags=["Issues"])


@issue_router.post("", response_model=RaiseIssueResponse)
async def raise_issue(
    data: RaiseIssueRequest,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: IssueService = Depends(get_issue_service),
):
    return await service.raise_issue(payload, data)


@issue_router.get("", response_model=list[MyIssueItem])
async def my_issues(
    status: IssueStatus | None = Query(None),
    club_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: IssueService = Depends(get_issue_service),
):
    return await service.my_issues(payload, status=status, club_id=club_id,
                                   limit=limit, offset=offset)


@issue_router.get("/club", response_model=list[LeaderIssueItem])
async def club_issue_queue(
    status: IssueStatus | None = Query(None),
    club_id: int | None = Query(None, description="Limit to a single club you lead"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: IssueService = Depends(get_issue_service),
):
    return await service.club_queue(payload, status=status, club_id=club_id,
                                    limit=limit, offset=offset)


@issue_router.get("/club/open-count", response_model=OpenIssueCountResponse)
async def open_issue_count(
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: IssueService = Depends(get_issue_service),
):
    return await service.open_count(payload)


@issue_router.post("/{issue_id}/reply", response_model=IssueActionResponse)
async def reply_to_issue(
    issue_id: int,
    data: ReplyIssueRequest,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: IssueService = Depends(get_issue_service),
):
    return await service.reply(payload, issue_id, data)


@issue_router.patch("/{issue_id}/resolve", response_model=IssueActionResponse)
async def resolve_issue(
    issue_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: IssueService = Depends(get_issue_service),
):
    return await service.resolve(payload, issue_id)
