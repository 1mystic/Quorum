from fastapi import APIRouter, Depends, File, Form, Query, Security, UploadFile
from app.schemas import (
    CreateGroupRequest, UpdateGroupRequest, CreateGroupResponse, GroupStatusResponse,
    GroupListItem, GroupDetailResponse, JoinResponse, RequestActionRequest, MembershipActionResponse,
    PendingRequestItem, MemberItem, MyGroupItem, RemoveMemberResponse, TrendingGroupItem
)
from app.services import GroupService, MembershipService
from app.core.di import get_group_service, get_membership_service, get_user_info
from app.core.forms import parse_form_model
from app.models import GroupStatus, GroupType, MembershipRole

group_router = APIRouter(prefix="/groups", tags=["Groups"])

# Deliberately outside /api/t/{slug}: the marketing landing page needs a
# cross-tenant "trending groups" list before a visitor has picked a tenant at
# all. See app/api/__init__.py and main.py for where this mounts.
public_group_router = APIRouter(prefix="/public/groups", tags=["Groups (public)"])


@public_group_router.get("/trending", response_model=list[TrendingGroupItem])
async def trending_groups(
    limit: int = Query(8, ge=1, le=20),
    service: GroupService = Depends(get_group_service),
):
    """No auth, cross-tenant - powers the marketing landing page."""
    return await service.trending(limit)


@group_router.post("", response_model=CreateGroupResponse)
async def create_group(
    data: str = Form(..., description="JSON body of CreateGroupRequest"),
    image: UploadFile | None = File(None),
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.create(payload, parse_form_model(CreateGroupRequest, data), image)


@group_router.get("", response_model=list[GroupListItem])
async def browse_groups(
    status: GroupStatus | None = Query(None, description="Admins only; members always get ACTIVE groups"),
    type: GroupType | None = Query(None),
    category: str | None = Query(None, min_length=1, max_length=50),
    search: str | None = Query(None, min_length=1, max_length=100, description="Matches name, description or category"),
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.list(payload, status=status, search=search, category=category, type=type)


# Self-scoped ("groups I lead" / "groups I joined"); stays MEMBER-only.
@group_router.get("/me", response_model=list[MyGroupItem])
async def my_groups(
    role: MembershipRole | None = Query(None, description="LEADER returns groups you lead, MEMBER the ones you joined"),
    status: str | None = Query(
        None,
        description="Role-aware: with role=LEADER it filters the group status "
                    "(PENDING, ACTIVE, REJECTED, ARCHIVED); with role=MEMBER it filters your "
                    "membership status (PENDING, APPROVED, REJECTED). Requires role.",
    ),
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.my_groups(payload, role=role, status=status)


@group_router.get("/{group_id}", response_model=GroupDetailResponse)
async def view_group(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.get(payload, group_id)


@group_router.put("/{group_id}", response_model=GroupDetailResponse)
async def edit_group(
    group_id: int,
    data: str = Form(..., description="JSON body of UpdateGroupRequest"),
    image: UploadFile | None = File(None),
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.update(payload, group_id, parse_form_model(UpdateGroupRequest, data), image)


@group_router.delete("/{group_id}", response_model=GroupStatusResponse)
async def delete_group(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.delete(payload, group_id)


@group_router.patch("/{group_id}/approve", response_model=GroupStatusResponse)
async def approve_group(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["TENANT_ADMIN"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.approve(payload, group_id)


@group_router.patch("/{group_id}/reject", response_model=GroupStatusResponse)
async def reject_group(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["TENANT_ADMIN"]),
    service: GroupService = Depends(get_group_service),
):
    return await service.reject(payload, group_id)

@group_router.post("/{group_id}/join", response_model=JoinResponse)
async def join_group(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.join(payload, group_id)


@group_router.delete("/{group_id}/join", response_model=RemoveMemberResponse)
async def leave_group(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.leave(payload, group_id)


# pending_requests/handle_request/remove_member are leader actions
# (MembershipService asserts is_leader on the caller's own Member row); stay
# MEMBER-only for the same reason as request.py's leader-only actions.
@group_router.get("/{group_id}/requests", response_model=list[PendingRequestItem])
async def pending_requests(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.pending_requests(payload, group_id)


@group_router.patch("/{group_id}/requests/{membership_id}", response_model=MembershipActionResponse)
async def handle_request(
    group_id: int,
    membership_id: int,
    data: RequestActionRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.handle_request(payload, group_id, membership_id, data)


@group_router.get("/{group_id}/members", response_model=list[MemberItem])
async def group_members(
    group_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.members(group_id)


@group_router.delete("/{group_id}/members/{member_id}", response_model=RemoveMemberResponse)
async def remove_member(
    group_id: int,
    member_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.remove_member(payload, group_id, member_id)
