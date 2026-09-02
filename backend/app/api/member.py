from fastapi import APIRouter, Depends, File, Form, Security, UploadFile
from app.schemas import (
    MemberProfileResponse, UpdateProfileRequest, UpdateProfileResponse, PublicMemberResponse
)
from app.services import MemberService
from app.core.di import get_member_service, get_user_info
from app.core.forms import parse_form_model

member_router = APIRouter(prefix="/members", tags=["Members"])


# my_profile/update_my_profile are self-scoped (the caller's own profile) and
# stay MEMBER-only; a TENANT_ADMIN has no Member row for "my profile" to mean
# anything. Viewing someone else's profile is member_profile below, already
# MEMBER + TENANT_ADMIN.
@member_router.get("/me", response_model=MemberProfileResponse)
async def my_profile(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: MemberService = Depends(get_member_service),
):
    return await service.my_profile(payload)


@member_router.patch("/me", response_model=UpdateProfileResponse)
async def update_my_profile(
    data: str | None = Form(None, description="JSON body of UpdateProfileRequest"),
    image: UploadFile | None = File(None),
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: MemberService = Depends(get_member_service),
):
    parsed = parse_form_model(UpdateProfileRequest, data) if data is not None else UpdateProfileRequest()
    return await service.update_my_profile(payload, parsed, image)


@member_router.get("/{member_id}", response_model=PublicMemberResponse)
async def member_profile(
    member_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: MemberService = Depends(get_member_service),
):
    return await service.public_profile(payload, member_id)
