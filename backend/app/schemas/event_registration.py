from datetime import datetime
from pydantic import BaseModel, model_validator
from app.models import EventStatus, RegistrationResult


class RegistrationConfirmation(BaseModel):
    registration_id: int
    event_id: int
    event_title: str
    venue: str
    starts_at: datetime
    message: str


class UnregisterResponse(BaseModel):
    event_id: int
    message: str


class ParticipantItem(BaseModel):
    registration_id: int
    member_id: int
    full_name: str
    email: str
    roll_no: str | None
    branch: str | None
    year: int | None
    checked_in: bool
    checked_in_at: datetime | None
    result: RegistrationResult
    registered_at: datetime


class MarkAttendanceRequest(BaseModel):
    checked_in: bool


class AttendanceResponse(BaseModel):
    registration_id: int
    member_id: int
    full_name: str
    checked_in: bool
    checked_in_at: datetime | None
    message: str


class DeclareResultsRequest(BaseModel):
    winner_registration_id: int
    runner_up_registration_id: int

    @model_validator(mode="after")
    def distinct_winners(self):
        if self.winner_registration_id == self.runner_up_registration_id:
            raise ValueError("winner and runner up must be two different registrations")
        return self


class DeclaredResultItem(BaseModel):
    registration_id: int
    member_id: int
    full_name: str
    result: RegistrationResult


class DeclareResultsResponse(BaseModel):
    event_id: int
    winner: DeclaredResultItem
    runner_up: DeclaredResultItem
    participants: int
    certificates_queued: int
    message: str


class MyRegistrationItem(BaseModel):
    registration_id: int
    event_id: int
    event_title: str
    group_id: int
    group_name: str
    venue: str
    starts_at: datetime
    ends_at: datetime
    event_status: EventStatus
    checked_in: bool
    result: RegistrationResult


class MyResultItem(BaseModel):
    event_id: int
    event_title: str
    group_id: int
    group_name: str
    venue: str
    starts_at: datetime
    registration_id: int
    result: RegistrationResult
