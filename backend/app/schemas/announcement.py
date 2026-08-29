from datetime import datetime
from pydantic import BaseModel, Field
from app.models import AnnouncementCategory


class CreateAnnouncementRequest(BaseModel):
    group_id: int
    title: str = Field(..., min_length=3, max_length=150)
    body: str = Field(..., min_length=5, max_length=5000)
    category: AnnouncementCategory
    is_pinned: bool = False


class PinAnnouncementRequest(BaseModel):
    pinned: bool


class CreateAnnouncementResponse(BaseModel):
    id: int
    group_id: int
    title: str
    category: AnnouncementCategory
    is_pinned: bool
    message: str


class AnnouncementItem(BaseModel):
    id: int
    group_id: int
    group_name: str
    author_id: int
    author_name: str
    title: str
    body: str
    category: AnnouncementCategory
    is_pinned: bool
    unread: bool
    created_at: datetime


class PinAnnouncementResponse(BaseModel):
    id: int
    title: str
    is_pinned: bool
    message: str


class DeleteAnnouncementResponse(BaseModel):
    id: int
    message: str


class UnreadCountResponse(BaseModel):
    count: int


class MarkAnnouncementsReadResponse(BaseModel):
    seen_at: datetime
    message: str
