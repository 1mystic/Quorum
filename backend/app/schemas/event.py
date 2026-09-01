from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, model_validator
from app.models import EventStatus


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class CreateEventRequest(BaseModel):
    group_id: int
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=5, max_length=2000)
    venue: str = Field(..., min_length=2, max_length=200)
    starts_at: datetime
    ends_at: datetime
    capacity: int | None = Field(None, ge=1, le=100000)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalise_tz(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def valid_window(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class UpdateEventRequest(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=150)
    description: str | None = Field(None, min_length=5, max_length=2000)
    venue: str | None = Field(None, min_length=2, max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    capacity: int | None = Field(None, ge=1, le=100000)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def normalise_tz(cls, value: datetime | None) -> datetime | None:
        return _as_utc(value) if value else None

    @model_validator(mode="after")
    def valid_window(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class CreateEventResponse(BaseModel):
    id: int
    group_id: int
    title: str
    status: EventStatus
    message: str


class EventStatusResponse(BaseModel):
    id: int
    title: str
    status: EventStatus
    message: str
    rejection_reason: str | None = None


class EventListItem(BaseModel):
    id: int
    group_id: int
    group_name: str
    title: str
    description: str
    venue: str
    starts_at: datetime
    ends_at: datetime
    capacity: int | None
    registration_count: int
    seats_left: int | None
    status: EventStatus
    image_url: str | None
    created_at: datetime
    results_declared: bool


class EventDetailResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    title: str
    description: str
    venue: str
    starts_at: datetime
    ends_at: datetime
    capacity: int | None
    registration_count: int
    seats_left: int | None
    status: EventStatus
    image_url: str | None
    created_at: datetime
    is_registered: bool = False
    my_registration_id: int | None = None
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
