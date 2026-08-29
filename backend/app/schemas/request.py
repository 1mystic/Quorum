from datetime import datetime
from pydantic import BaseModel, Field
from app.models import RequestCategory, RequestStatus


class RaiseRequestRequest(BaseModel):
    group_id: int
    category: RequestCategory
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=10, max_length=2000)
    event_id: int | None = None


class ReplyRequestRequest(BaseModel):
    reply: str = Field(..., min_length=2, max_length=2000)


class RaiseRequestResponse(BaseModel):
    id: int
    group_id: int
    title: str
    category: RequestCategory
    status: RequestStatus
    message: str


class RequestResponseInfo(BaseModel):
    by: str
    text: str
    at: datetime


class MyRequestItem(BaseModel):
    id: int
    group_id: int
    group_name: str
    event_id: int | None
    category: RequestCategory
    status: RequestStatus
    title: str
    description: str
    response: RequestResponseInfo | None
    created_at: datetime
    resolved_at: datetime | None


class LeaderRequestItem(BaseModel):
    id: int
    group_id: int
    group_name: str
    member_id: int
    raised_by: str
    event_id: int | None
    category: RequestCategory
    status: RequestStatus
    title: str
    description: str
    response: RequestResponseInfo | None
    created_at: datetime
    resolved_at: datetime | None


class RequestActionResponse(BaseModel):
    id: int
    status: RequestStatus
    message: str


class OpenRequestCountResponse(BaseModel):
    count: int
