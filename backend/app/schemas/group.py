from datetime import datetime
from pydantic import BaseModel, Field
from app.models import GroupType, GroupStatus, MembershipRole, MembershipStatus


class GroupLinkSchema(BaseModel):
    label: str = Field(..., min_length=1, max_length=50)
    url: str = Field(..., min_length=1, max_length=500)


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=5, max_length=1000)
    category: str = Field(..., min_length=2, max_length=50)
    type: GroupType
    links: list[GroupLinkSchema] = Field(default_factory=list)


class UpdateGroupRequest(BaseModel):
    description: str | None = Field(None, min_length=5, max_length=1000)
    category: str | None = Field(None, min_length=2, max_length=50)
    links: list[GroupLinkSchema] | None = None
    # A leader-supplied URL for the banner image, used when an uploaded file isn't
    # provided in the same request. Lets a group set its banner without needing S3.
    image_url: str | None = Field(None, max_length=500)


class CreateGroupResponse(BaseModel):
    id: int
    name: str
    type: GroupType
    status: GroupStatus
    message: str


class GroupStatusResponse(BaseModel):
    id: int
    name: str
    status: GroupStatus
    message: str


class GroupHeadInfo(BaseModel):
    """Name is visible to anyone in the tenant; contact details are filled for campus admins only."""
    member_id: int
    full_name: str
    email: str | None = None
    roll_no: str | None = None
    branch: str | None = None
    year: int | None = None


class GroupListItem(BaseModel):
    id: int
    name: str
    description: str
    category: str
    type: GroupType
    status: GroupStatus
    image_url: str | None
    member_count: int
    head_name: str
    created_at: datetime
    links: list[GroupLinkSchema]


class TrendingGroupItem(BaseModel):
    """Public, unauthenticated card for the marketing landing page - no
    description/head/links, just enough to show a live group with which
    tenant it belongs to."""
    id: int
    name: str
    category: str
    member_count: int
    tenant_name: str
    tenant_slug: str


class MyGroupItem(GroupListItem):
    membership_id: int
    membership_role: MembershipRole
    membership_status: MembershipStatus
    joined_at: datetime


class GroupDetailResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    type: GroupType
    status: GroupStatus
    image_url: str | None
    member_count: int
    created_at: datetime
    links: list[GroupLinkSchema]
    head: GroupHeadInfo | None = None
