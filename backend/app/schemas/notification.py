from datetime import datetime
from pydantic import BaseModel
from app.models import NotificationType


class NotificationItem(BaseModel):
    id: int
    type: NotificationType
    message: str
    group_id: int | None
    event_id: int | None
    is_read: bool
    created_at: datetime


class NotificationCountResponse(BaseModel):
    count: int


class NotificationReadResponse(BaseModel):
    id: int
    is_read: bool
    message: str


class MarkAllNotificationsReadResponse(BaseModel):
    updated: int
    message: str
