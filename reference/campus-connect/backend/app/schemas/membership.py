from pydantic import BaseModel, model_validator
from app.models import MembershipRole, MembershipStatus


class JoinResponse(BaseModel):
    id: int
    club_id: int
    status: MembershipStatus
    message: str


class RequestActionRequest(BaseModel):
    action: MembershipStatus

    @model_validator(mode="after")
    def valid_action(self):
        if self.action not in (MembershipStatus.APPROVED, MembershipStatus.REJECTED):
            raise ValueError("action must be APPROVED or REJECTED")
        return self


class RequestActionResponse(BaseModel):
    id: int
    student_id: int
    club_id: int
    status: MembershipStatus
    message: str


class PendingRequestItem(BaseModel):
    id: int
    student_id: int
    full_name: str
    role: MembershipRole
    status: MembershipStatus


class MemberItem(BaseModel):
    id: int
    student_id: int
    full_name: str
    role: MembershipRole


class RemoveMemberResponse(BaseModel):
    id: int
    student_id: int
    club_id: int
    message: str
