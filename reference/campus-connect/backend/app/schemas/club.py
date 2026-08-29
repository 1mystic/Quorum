from datetime import datetime
from pydantic import BaseModel, Field
from app.models import ClubType, ClubStatus, MembershipRole, MembershipStatus


class ClubLinkSchema(BaseModel):
    label: str = Field(..., min_length=1, max_length=50)
    url: str = Field(..., min_length=1, max_length=500)


class CreateClubRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=5, max_length=1000)
    category: str = Field(..., min_length=2, max_length=50)
    type: ClubType
    links: list[ClubLinkSchema] = Field(default_factory=list)


class UpdateClubRequest(BaseModel):
    description: str | None = Field(None, min_length=5, max_length=1000)
    category: str | None = Field(None, min_length=2, max_length=50)
    links: list[ClubLinkSchema] | None = None
    # A leader-supplied URL for the banner image, used when an uploaded file isn't
    # provided in the same request. Lets a club set its banner without needing S3.
    image_url: str | None = Field(None, max_length=500)


class CreateClubResponse(BaseModel):
    id: int
    name: str
    type: ClubType
    status: ClubStatus
    message: str


class ClubStatusResponse(BaseModel):
    id: int
    name: str
    status: ClubStatus
    message: str


class ClubHeadInfo(BaseModel):
    """Name is visible to anyone in the college; contact details are filled for campus admins only."""
    student_id: int
    full_name: str
    email: str | None = None
    roll_no: str | None = None
    branch: str | None = None
    year: int | None = None


class ClubListItem(BaseModel):
    id: int
    name: str
    description: str
    category: str
    type: ClubType
    status: ClubStatus
    image_url: str | None
    member_count: int
    head_name: str
    created_at: datetime
    links: list[ClubLinkSchema]


class TrendingClubItem(BaseModel):
    """Public, unauthenticated card for the marketing landing page - no
    description/head/links, just enough to show a live club with which
    college it belongs to."""
    id: int
    name: str
    category: str
    member_count: int
    college_name: str
    college_slug: str


class MyClubItem(ClubListItem):
    membership_id: int
    membership_role: MembershipRole
    membership_status: MembershipStatus
    joined_at: datetime


class ClubDetailResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    type: ClubType
    status: ClubStatus
    image_url: str | None
    member_count: int
    created_at: datetime
    links: list[ClubLinkSchema]
    head: ClubHeadInfo | None = None
