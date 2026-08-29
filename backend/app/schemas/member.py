from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, Field, field_validator
from app.models import MembershipRole

Interest = Annotated[str, Field(min_length=1, max_length=30)]


class MemberGroupItem(BaseModel):
    group_id: int
    name: str
    category: str
    membership_role: MembershipRole
    joined_at: datetime


class PublicMemberResponse(BaseModel):
    member_id: int
    full_name: str
    profile_image_url: str | None
    branch: str | None
    year: int | None
    joined_groups: list[MemberGroupItem]


class MemberProfileResponse(BaseModel):
    member_id: int
    full_name: str
    email: str
    profile_image_url: str | None
    bio: str | None
    interests: list[str]
    roll_no: str | None
    branch: str | None
    year: int | None
    joined_groups: list[MemberGroupItem]
    created_at: datetime


class UpdateProfileResponse(MemberProfileResponse):
    message: str


class UpdateProfileRequest(BaseModel):
    bio: str | None = Field(None, max_length=500)
    interests: Annotated[list[Interest], Field(max_length=10)] | None = None
    roll_no: str | None = Field(None, max_length=50)
    branch: str | None = Field(None, max_length=100)
    year: int | None = Field(None, ge=1, le=5)

    @field_validator("bio", "roll_no", "branch", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None

    @field_validator("interests", mode="before")
    @classmethod
    def clean_interests(cls, value):
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        cleaned = []
        for item in value:
            item = item.strip() if isinstance(item, str) else item
            if item and item not in cleaned:
                cleaned.append(item)
        return cleaned
