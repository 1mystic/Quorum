from fastapi import UploadFile
from app.repository import GroupRepository, MemberRepository, UserRepository, MembershipRepository
from app.models import Group, GroupType, GroupStatus, MembershipRole, MembershipStatus, UserRole
from app.schemas import (
    CreateGroupRequest, UpdateGroupRequest, CreateGroupResponse, GroupStatusResponse,
    GroupListItem, GroupDetailResponse, GroupLinkSchema, GroupHeadInfo, MyGroupItem, TrendingGroupItem
)
from app.exceptions import (
    GroupNotFoundError, NotGroupLeaderError, GroupActionNotAllowedError, MemberNotFoundError,
    TenantNotFoundError, InvalidStatusFilterError
)
from app.core.messages import GroupMessages
from app.core.storage import Storage, GROUP_FOLDER


class GroupService:
    def __init__(self, group_repo: GroupRepository, member_repo: MemberRepository,
                 user_repo: UserRepository, membership_repo: MembershipRepository,
                 storage: Storage):
        self.group_repo = group_repo
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.storage = storage

    async def create(self, payload: dict, data: CreateGroupRequest,
                     image: UploadFile | None = None) -> CreateGroupResponse:
        user_id = int(payload.get("sub"))
        member = await self.member_repo.get_member_by_user_id(user_id)
        if not member:
            raise MemberNotFoundError()

        tenant_id = await self._tenant_id(payload)
        status = GroupStatus.ACTIVE if data.type == GroupType.UNOFFICIAL else GroupStatus.PENDING

        image_url = await self.storage.upload_image(image, GROUP_FOLDER) if image else None
        group = await self.group_repo.create_group(
            tenant_id=tenant_id,
            group_head=member.id,
            name=data.name,
            description=data.description,
            category=data.category,
            type=data.type,
            status=status,
            image_url=image_url,
        )
        for link in data.links:
            await self.group_repo.add_link(group.id, link.label, link.url)

        await self.membership_repo.create_membership(
            member_id=member.id,
            group_id=group.id,
            role=MembershipRole.LEADER,
            status=MembershipStatus.APPROVED,
        )

        message = GroupMessages.CREATED_ACTIVE if status == GroupStatus.ACTIVE else GroupMessages.CREATED_PENDING
        return CreateGroupResponse(id=group.id, name=group.name, type=group.type, status=group.status, message=message)

    
    async def my_groups(self, payload: dict, role: MembershipRole | None = None,
                       status: str | None = None) -> list[MyGroupItem]:
        member = await self._get_member(payload)
        group_status, membership_status = self._resolve_status(role, status)
        rows = await self.membership_repo.list_by_member(
            member.id, role, membership_status=membership_status, group_status=group_status
        )
        return [
            MyGroupItem(
                id=group.id,
                name=group.name,
                description=group.description,
                category=group.category,
                type=group.type,
                status=group.status,
                image_url=group.image_url,
                member_count=count,
                head_name=head_name,
                created_at=group.created_at,
                links=[
                    GroupLinkSchema(label=link.label, url=link.url)
                    for link in group.links
                ],
                membership_id=membership.id,
                membership_role=membership.role,
                membership_status=membership.status,
                joined_at=membership.created_at,
            )
            for membership, group, count, head_name in rows
        ]

    async def trending(self, limit: int = 8) -> list[TrendingGroupItem]:
        rows = await self.group_repo.list_trending(limit)
        return [
            TrendingGroupItem(
                id=group.id,
                name=group.name,
                category=group.category,
                member_count=count,
                tenant_name=tenant_name,
                tenant_slug=tenant_slug,
            )
            for group, count, tenant_name, tenant_slug in rows
        ]

    async def list(self, payload: dict, status: GroupStatus | None = None,
                   search: str | None = None, category: str | None = None,
                   type: GroupType | None = None) -> list[GroupListItem]:
        tenant_id = await self._tenant_id(payload)
        effective_status = status if self._is_admin(payload) else GroupStatus.ACTIVE

        rows = await self.group_repo.list_by_tenant(tenant_id, effective_status, search, category, type)
        return [
            GroupListItem(
                id=group.id,
                name=group.name,
                description=group.description,
                category=group.category,
                type=group.type,
                status=group.status,
                image_url=group.image_url,
                member_count=count,
                head_name=head_name,
                created_at=group.created_at,
                links=[
                    GroupLinkSchema(label=link.label, url=link.url)
                    for link in group.links
                ],
            )
            for group, count, head_name in rows
        ]

    async def get(self, payload: dict, group_id: int) -> GroupDetailResponse:
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            raise GroupNotFoundError()

        tenant_id = await self._tenant_id(payload)
        if group.tenant_id != tenant_id:
            raise GroupNotFoundError()

        is_admin = self._is_admin(payload)
        if not is_admin and group.status != GroupStatus.ACTIVE:
            raise GroupNotFoundError()

        return await self._detail(group, include_contact=is_admin)

    async def update(self, payload: dict, group_id: int, data: UpdateGroupRequest,
                     image: UploadFile | None = None) -> GroupDetailResponse:
        member = await self._get_member(payload)
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            raise GroupNotFoundError()
        if not await self.membership_repo.is_leader(member.id, group_id):
            raise NotGroupLeaderError()

        old_image_url = group.image_url
        new_image_url = await self.storage.upload_image(image, GROUP_FOLDER) if image else data.image_url
        await self.group_repo.update_group(group, data.description, data.category, new_image_url)
        if new_image_url:
            await self.storage.delete_url(old_image_url)
        if data.links is not None:
            await self.group_repo.replace_links(group_id, data.links)

        updated = await self.group_repo.get_by_id(group_id)
        return await self._detail(updated, include_contact=False)

    async def delete(self, payload: dict, group_id: int) -> GroupStatusResponse:
        member = await self._get_member(payload)
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            raise GroupNotFoundError()
        if not await self.membership_repo.is_leader(member.id, group_id):
            raise NotGroupLeaderError()

        await self.group_repo.set_status(group, GroupStatus.ARCHIVED)
        return GroupStatusResponse(id=group.id, name=group.name, status=group.status, message=GroupMessages.ARCHIVED)

    async def approve(self, payload: dict, group_id: int) -> GroupStatusResponse:
        group = await self._admin_pending_group(payload, group_id)
        await self.group_repo.set_status(group, GroupStatus.ACTIVE)
        return GroupStatusResponse(id=group.id, name=group.name, status=group.status, message=GroupMessages.APPROVED)

    async def reject(self, payload: dict, group_id: int) -> GroupStatusResponse:
        group = await self._admin_pending_group(payload, group_id)
        await self.group_repo.set_status(group, GroupStatus.REJECTED)
        return GroupStatusResponse(id=group.id, name=group.name, status=group.status, message=GroupMessages.REJECTED)

    @staticmethod
    def _resolve_status(role: MembershipRole | None, status: str | None):
        if status is None:
            return None, None
        if role is None:
            raise InvalidStatusFilterError(GroupMessages.STATUS_NEEDS_ROLE)

        is_leader = role == MembershipRole.LEADER
        options = GroupStatus if is_leader else MembershipStatus
        try:
            parsed = options(status)
        except ValueError:
            allowed = ", ".join(option.value for option in options)
            raise InvalidStatusFilterError(
                f"status must be one of {allowed} when role is {role.value}"
            )
        return (parsed, None) if is_leader else (None, parsed)

    @staticmethod
    def _is_admin(payload: dict) -> bool:
        return payload.get("role") == UserRole.TENANT_ADMIN

    async def _tenant_id(self, payload: dict) -> int:
        tenant_id = await self.user_repo.get_tenant_id(int(payload.get("sub")))
        if not tenant_id:
            raise TenantNotFoundError()
        return tenant_id

    async def _detail(self, group: Group, include_contact: bool) -> GroupDetailResponse:
        member_count = await self.group_repo.count_members(group.id)
        return GroupDetailResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            category=group.category,
            type=group.type,
            status=group.status,
            image_url=group.image_url,
            member_count=member_count,
            created_at=group.created_at,
            links=[GroupLinkSchema(label=link.label, url=link.url) for link in group.links],
            head=self._head_info(group, include_contact),
        )

    @staticmethod
    def _head_info(group: Group, include_contact: bool) -> GroupHeadInfo:
        head = group.head
        return GroupHeadInfo(
            member_id=head.id,
            full_name=head.user.full_name,
            email=head.user.email if include_contact else None,
            roll_no=head.roll_no if include_contact else None,
            branch=head.branch if include_contact else None,
            year=head.year if include_contact else None,
        )

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member

    async def _admin_pending_group(self, payload: dict, group_id: int):
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            raise GroupNotFoundError()
        tenant_id = await self._tenant_id(payload)
        if group.tenant_id != tenant_id:
            raise GroupActionNotAllowedError()
        if group.status != GroupStatus.PENDING:
            raise GroupActionNotAllowedError("Group is not pending approval")
        return group
