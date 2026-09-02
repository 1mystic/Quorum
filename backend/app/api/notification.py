from fastapi import APIRouter, Depends, Query, Security
from app.schemas import (
    NotificationItem, NotificationCountResponse, NotificationReadResponse,
    MarkAllNotificationsReadResponse
)
from app.services import NotificationService
from app.core.di import get_notification_service, get_user_info
from app.models import NotificationType

notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])

# All four routes below are self-scoped (the caller's own notifications) and
# stay MEMBER-only. Nothing here is tenant oversight - a TENANT_ADMIN reading
# "my notifications" is not a meaningful action, and NotificationService's
# _get_member would raise MemberNotFoundError for a TENANT_ADMIN token anyway
# since it never has a Member row.
@notification_router.get("", response_model=list[NotificationItem])
async def my_notifications(
    is_read: bool | None = Query(None, description="Filter by read state"),
    type: NotificationType | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.list(payload, is_read=is_read, type=type, limit=limit, offset=offset)


@notification_router.get("/unread-count", response_model=NotificationCountResponse)
async def unread_notification_count(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.unread_count(payload)


@notification_router.post("/read-all", response_model=MarkAllNotificationsReadResponse)
async def mark_all_notifications_read(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.mark_all_read(payload)


@notification_router.patch("/{notification_id}/read", response_model=NotificationReadResponse)
async def mark_notification_read(
    notification_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.mark_read(payload, notification_id)
