from datetime import datetime
from pydantic import BaseModel, Field
from app.models import RequestStatus


class RaiseRequestRequest(BaseModel):
    group_id: int
    # Card C.8: a plain string, validated in the service against the tenant's
    # vertical adapter vocabulary (docs/VERTICALS.md's declared
    # request_categories), not a fixed Campus Connect enum. See
    # app.verticals.adapters.get_adapter.
    category: str = Field(..., min_length=1, max_length=64)
    subcategory: str | None = Field(None, max_length=64)
    priority: str | None = Field(None, max_length=32)
    channel: str | None = Field(None, max_length=32)
    location_ref: str | None = Field(None, max_length=64)
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=10, max_length=2000)
    event_id: int | None = None


class ReplyRequestRequest(BaseModel):
    reply: str = Field(..., min_length=2, max_length=2000)


class AssignRequestRequest(BaseModel):
    assignee_member_id: int


class MergeRequestRequest(BaseModel):
    into_request_id: int


class RaiseRequestResponse(BaseModel):
    id: int
    group_id: int
    title: str
    category: str
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
    category: str
    subcategory: str | None
    priority: str | None
    channel: str | None
    location_ref: str | None
    status: RequestStatus
    title: str
    description: str
    response: RequestResponseInfo | None
    created_at: datetime
    resolved_at: datetime | None
    terminal_at: datetime | None
    outcome: str | None


class LeaderRequestItem(BaseModel):
    id: int
    group_id: int
    group_name: str
    member_id: int
    raised_by: str
    event_id: int | None
    category: str
    subcategory: str | None
    priority: str | None
    channel: str | None
    location_ref: str | None
    status: RequestStatus
    title: str
    description: str
    response: RequestResponseInfo | None
    created_at: datetime
    resolved_at: datetime | None
    terminal_at: datetime | None
    outcome: str | None


class RequestActionResponse(BaseModel):
    id: int
    status: RequestStatus
    message: str


class OpenRequestCountResponse(BaseModel):
    count: int
