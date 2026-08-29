from fastapi import APIRouter, Depends, Query, Security
from app.schemas import (
    CreateAnnouncementRequest, PinAnnouncementRequest, CreateAnnouncementResponse,
    AnnouncementItem, PinAnnouncementResponse, DeleteAnnouncementResponse,
    UnreadCountResponse, MarkAnnouncementsReadResponse
)
from app.services import AnnouncementService
from app.core.di import get_announcement_service, get_user_info
from app.models import AnnouncementCategory

announcement_router = APIRouter(prefix="/announcements", tags=["Announcements"])


@announcement_router.post("", response_model=CreateAnnouncementResponse)
async def post_announcement(
    data: CreateAnnouncementRequest,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: AnnouncementService = Depends(get_announcement_service),
):
    return await service.create(payload, data)


@announcement_router.get("", response_model=list[AnnouncementItem])
async def announcement_feed(
    club_id: int | None = Query(None, description="Limit the feed to a single joined club"),
    category: AnnouncementCategory | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=100,
                               description="Matches title or body"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: AnnouncementService = Depends(get_announcement_service),
):
    return await service.feed(payload, club_id=club_id, category=category, search=search,
                              limit=limit, offset=offset)


@announcement_router.get("/mine", response_model=list[AnnouncementItem])
async def my_club_announcements(
    club_id: int | None = Query(None, description="Limit to a single club you lead"),
    category: AnnouncementCategory | None = Query(None),
    search: str | None = Query(None, min_length=1, max_length=100,
                               description="Matches title or body"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: AnnouncementService = Depends(get_announcement_service),
):
    return await service.mine(payload, club_id=club_id, category=category, search=search,
                              limit=limit, offset=offset)


@announcement_router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_announcement_count(
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: AnnouncementService = Depends(get_announcement_service),
):
    return await service.unread_count(payload)


@announcement_router.post("/read-all", response_model=MarkAnnouncementsReadResponse)
async def mark_announcements_read(
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: AnnouncementService = Depends(get_announcement_service),
):
    return await service.mark_read(payload)


@announcement_router.patch("/{announcement_id}/pin", response_model=PinAnnouncementResponse)
async def pin_announcement(
    announcement_id: int,
    data: PinAnnouncementRequest,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: AnnouncementService = Depends(get_announcement_service),
):
    return await service.pin(payload, announcement_id, data)


@announcement_router.delete("/{announcement_id}", response_model=DeleteAnnouncementResponse)
async def delete_announcement(
    announcement_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: AnnouncementService = Depends(get_announcement_service),
):
    return await service.delete(payload, announcement_id)
