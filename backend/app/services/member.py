from fastapi import UploadFile
from app.repository import MemberRepository, UserRepository, MembershipRepository
from app.models import GroupStatus, MembershipStatus, Member
from app.schemas import (
    MemberGroupItem, PublicMemberResponse, MemberProfileResponse, UpdateProfileRequest,
    UpdateProfileResponse
)
from app.exceptions import MemberNotFoundError
from app.core.messages import MemberMessages
from app.core.storage import Storage, AVATAR_FOLDER


class MemberService:
    def __init__(self, member_repo: MemberRepository, user_repo: UserRepository,
                 membership_repo: MembershipRepository, storage: Storage):
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.storage = storage

    async def my_profile(self, payload: dict) -> MemberProfileResponse:
        member = await self._me(payload)
        return MemberProfileResponse(
            **self._profile_fields(member),
            joined_groups=await self._joined_groups(member.id),
        )

    async def update_my_profile(self, payload: dict, data: UpdateProfileRequest,
                                image: UploadFile | None = None) -> UpdateProfileResponse:
        member = await self._me(payload)
        await self.member_repo.update_profile(member, data.model_dump(exclude_unset=True))
        if image is not None:
            old_url = member.user.profile_image_url
            new_url = await self.storage.upload_image(image, AVATAR_FOLDER)
            await self.user_repo.set_profile_image(member.user, new_url)
            await self.storage.delete_url(old_url)
        return UpdateProfileResponse(
            **self._profile_fields(member),
            joined_groups=await self._joined_groups(member.id),
            message=MemberMessages.PROFILE_UPDATED,
        )

    async def public_profile(self, payload: dict, member_id: int) -> PublicMemberResponse:
        tenant_id = await self.user_repo.get_tenant_id(int(payload.get("sub")))
        member = await self.member_repo.get_by_id_with_user(member_id)
        if not member or tenant_id is None or member.user.tenant_id != tenant_id:
            raise MemberNotFoundError()

        return PublicMemberResponse(
            member_id=member.id,
            full_name=member.user.full_name,
            profile_image_url=member.user.profile_image_url,
            branch=member.branch,
            year=member.year,
            joined_groups=await self._joined_groups(member.id),
        )

    async def _joined_groups(self, member_id: int) -> list[MemberGroupItem]:
        rows = await self.membership_repo.list_by_member(
            member_id,
            membership_status=MembershipStatus.APPROVED,
            group_status=GroupStatus.ACTIVE,
        )
        return [
            MemberGroupItem(
                group_id=group.id,
                name=group.name,
                category=group.category,
                membership_role=membership.role,
                joined_at=membership.created_at,
            )
            for membership, group, _member_count, _head_name in rows
        ]

    @staticmethod
    def _profile_fields(member: Member) -> dict:
        return {
            "member_id": member.id,
            "full_name": member.user.full_name,
            "email": member.user.email,
            "profile_image_url": member.user.profile_image_url,
            "bio": member.bio,
            "interests": member.interests,
            "roll_no": member.roll_no,
            "branch": member.branch,
            "year": member.year,
            "created_at": member.created_at,
        }

    async def _me(self, payload: dict) -> Member:
        member = await self.member_repo.get_by_user_id_with_user(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member
