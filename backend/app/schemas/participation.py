from datetime import datetime
from pydantic import BaseModel, Field

from app.models import ParticipationKind


class RecordParticipationEventRequest(BaseModel):
    member_id: int
    kind: ParticipationKind
    at: datetime | None = None
    object_type: str | None = Field(None, max_length=32)
    object_id: int | None = None
    group_id: int | None = None
    weight: float = Field(1.0, gt=0)
    channel: str | None = Field(None, max_length=32)
    # Required for nudge_* kinds, forbidden otherwise; enforced in the service.
    arm_ref: str | None = Field(None, max_length=64)
    strata: dict[str, str] = Field(default_factory=dict)


class ParticipationEventItem(BaseModel):
    id: int
    member_id: int
    kind: ParticipationKind
    at: datetime
    object_type: str | None
    object_id: int | None
    weight: float
    channel: str | None
    arm_ref: str | None
