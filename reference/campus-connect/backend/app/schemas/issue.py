from datetime import datetime
from pydantic import BaseModel, Field
from app.models import IssueCategory, IssueStatus


class RaiseIssueRequest(BaseModel):
    club_id: int
    category: IssueCategory
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=10, max_length=2000)
    event_id: int | None = None


class ReplyIssueRequest(BaseModel):
    reply: str = Field(..., min_length=2, max_length=2000)


class RaiseIssueResponse(BaseModel):
    id: int
    club_id: int
    title: str
    category: IssueCategory
    status: IssueStatus
    message: str


class IssueResponseInfo(BaseModel):
    by: str
    text: str
    at: datetime


class MyIssueItem(BaseModel):
    id: int
    club_id: int
    club_name: str
    event_id: int | None
    category: IssueCategory
    status: IssueStatus
    title: str
    description: str
    response: IssueResponseInfo | None
    created_at: datetime
    resolved_at: datetime | None


class LeaderIssueItem(BaseModel):
    id: int
    club_id: int
    club_name: str
    student_id: int
    raised_by: str
    event_id: int | None
    category: IssueCategory
    status: IssueStatus
    title: str
    description: str
    response: IssueResponseInfo | None
    created_at: datetime
    resolved_at: datetime | None


class IssueActionResponse(BaseModel):
    id: int
    status: IssueStatus
    message: str


class OpenIssueCountResponse(BaseModel):
    count: int
