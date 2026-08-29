from fastapi import APIRouter, Depends, File, Form, Query, Security, UploadFile
from app.schemas import (
    CreateClubRequest, UpdateClubRequest, CreateClubResponse, ClubStatusResponse,
    ClubListItem, ClubDetailResponse, JoinResponse, RequestActionRequest, RequestActionResponse,
    PendingRequestItem, MemberItem, MyClubItem, RemoveMemberResponse, TrendingClubItem
)
from app.services import ClubService, MembershipService
from app.core.di import get_club_service, get_membership_service, get_user_info
from app.core.forms import parse_form_model
from app.models import ClubStatus, ClubType, MembershipRole

club_router = APIRouter(prefix="/clubs", tags=["Clubs"])


@club_router.post("", response_model=CreateClubResponse)
async def create_club(
    data: str = Form(..., description="JSON body of CreateClubRequest"),
    image: UploadFile | None = File(None),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.create(payload, parse_form_model(CreateClubRequest, data), image)


@club_router.get("", response_model=list[ClubListItem])
async def browse_clubs(
    status: ClubStatus | None = Query(None, description="Admins only; students always get ACTIVE clubs"),
    type: ClubType | None = Query(None),
    category: str | None = Query(None, min_length=1, max_length=50),
    search: str | None = Query(None, min_length=1, max_length=100, description="Matches name, description or category"),
    payload: dict = Security(get_user_info, scopes=["STUDENT", "CAMPUS_ADMIN"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.list(payload, status=status, search=search, category=category, type=type)


@club_router.get("/me", response_model=list[MyClubItem])
async def my_clubs(
    role: MembershipRole | None = Query(None, description="LEADER returns clubs you lead, MEMBER the ones you joined"),
    status: str | None = Query(
        None,
        description="Role-aware: with role=LEADER it filters the club status "
                    "(PENDING, ACTIVE, REJECTED, ARCHIVED); with role=MEMBER it filters your "
                    "membership status (PENDING, APPROVED, REJECTED). Requires role.",
    ),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.my_clubs(payload, role=role, status=status)


@club_router.get("/public/trending", response_model=list[TrendingClubItem])
async def trending_clubs(
    limit: int = Query(8, ge=1, le=20),
    service: ClubService = Depends(get_club_service),
):
    """No auth - powers the marketing landing page's 'Trending clubs' section."""
    return await service.trending(limit)


@club_router.get("/{club_id}", response_model=ClubDetailResponse)
async def view_club(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT", "CAMPUS_ADMIN"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.get(payload, club_id)


@club_router.put("/{club_id}", response_model=ClubDetailResponse)
async def edit_club(
    club_id: int,
    data: str = Form(..., description="JSON body of UpdateClubRequest"),
    image: UploadFile | None = File(None),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.update(payload, club_id, parse_form_model(UpdateClubRequest, data), image)


@club_router.delete("/{club_id}", response_model=ClubStatusResponse)
async def delete_club(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.delete(payload, club_id)


@club_router.patch("/{club_id}/approve", response_model=ClubStatusResponse)
async def approve_club(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["CAMPUS_ADMIN"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.approve(payload, club_id)


@club_router.patch("/{club_id}/reject", response_model=ClubStatusResponse)
async def reject_club(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["CAMPUS_ADMIN"]),
    service: ClubService = Depends(get_club_service),
):
    return await service.reject(payload, club_id)

@club_router.post("/{club_id}/join", response_model=JoinResponse)
async def join_club(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.join(payload, club_id)


@club_router.delete("/{club_id}/join", response_model=RemoveMemberResponse)
async def leave_club(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.leave(payload, club_id)


@club_router.get("/{club_id}/requests", response_model=list[PendingRequestItem])
async def pending_requests(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.pending_requests(payload, club_id)


@club_router.patch("/{club_id}/requests/{membership_id}", response_model=RequestActionResponse)
async def handle_request(
    club_id: int,
    membership_id: int,
    data: RequestActionRequest,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.handle_request(payload, club_id, membership_id, data)


@club_router.get("/{club_id}/members", response_model=list[MemberItem])
async def club_members(
    club_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.members(club_id)


@club_router.delete("/{club_id}/members/{student_id}", response_model=RemoveMemberResponse)
async def remove_member(
    club_id: int,
    student_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: MembershipService = Depends(get_membership_service),
):
    return await service.remove_member(payload, club_id, student_id)
