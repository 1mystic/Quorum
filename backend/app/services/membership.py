from sqlalchemy.exc import IntegrityError
from app.repository import (
    MembershipRepository, GroupRepository, MemberRepository, NotificationRepository
)
from app.models import GroupStatus, MembershipRole, MembershipStatus, NotificationType
from app.schemas import (
    JoinResponse, RequestActionRequest, RequestActionResponse, PendingRequestItem, MemberItem,
    RemoveMemberResponse
)
from app.exceptions import (
    GroupNotFoundError, GroupNotActiveError, NotGroupLeaderError, AlreadyMemberError,
    MembershipNotFoundError, GroupActionNotAllowedError, MemberNotFoundError
)
from app.core.messages import MembershipMessages, NotificationMessages


class MembershipService:
    def __init__(self, membership_repo: MembershipRepository, group_repo: GroupRepository,
                 member_repo: MemberRepository, notification_repo: NotificationRepository):
        self.membership_repo = membership_repo
        self.group_repo = group_repo
        self.member_repo = member_repo
        self.notification_repo = notification_repo

    async def join(self, payload: dict, group_id: int) -> JoinResponse:
        member = await self._get_member(payload)
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            raise GroupNotFoundError()
        if group.status != GroupStatus.ACTIVE:
            raise GroupNotActiveError()

        existing = await self.membership_repo.get(member.id, group_id)
        if existing:
            raise AlreadyMemberError()

        try:
            membership = await self.membership_repo.create_membership(
                member_id=member.id,
                group_id=group_id,
                role=MembershipRole.MEMBER,
                status=MembershipStatus.PENDING,
            )
        except IntegrityError:
            # uq_membership_member_group: two concurrent joins raced past the check above
            raise AlreadyMemberError()
        return JoinResponse(
            id=membership.id,
            group_id=group_id,
            status=membership.status,
            message=MembershipMessages.JOIN_REQUESTED,
        )

    async def pending_requests(self, payload: dict, group_id: int) -> list[PendingRequestItem]:
        member = await self._get_member(payload)
        await self._assert_leader(member.id, group_id)
        rows = await self.membership_repo.get_pending_by_group(group_id)
        return [
            PendingRequestItem(
                id=membership.id,
                member_id=membership.member_id,
                full_name=full_name,
                role=membership.role,
                status=membership.status,
            )
            for membership, full_name in rows
        ]

    async def handle_request(self, payload: dict, group_id: int, membership_id: int,
                             data: RequestActionRequest) -> RequestActionResponse:
        member = await self._get_member(payload)
        await self._assert_leader(member.id, group_id)

        membership = await self.membership_repo.get_by_id(membership_id)
        if not membership or membership.group_id != group_id:
            raise MembershipNotFoundError()
        if membership.status != MembershipStatus.PENDING:
            raise GroupActionNotAllowedError("Request has already been handled")

        await self.membership_repo.set_status(membership, data.action)

        group = await self.group_repo.get_by_id(group_id)
        approved = data.action == MembershipStatus.APPROVED
        await self.notification_repo.create_notification(
            member_id=membership.member_id,
            type=NotificationType.JOIN_APPROVED if approved else NotificationType.JOIN_REJECTED,
            message=(
                NotificationMessages.join_approved(group.name) if approved
                else NotificationMessages.join_rejected(group.name)
            ),
            group_id=group_id,
        )

        message = (
            MembershipMessages.REQUEST_APPROVED
            if approved
            else MembershipMessages.REQUEST_REJECTED
        )
        return RequestActionResponse(
            id=membership.id,
            member_id=membership.member_id,
            group_id=membership.group_id,
            status=membership.status,
            message=message,
        )

    async def members(self, group_id: int) -> list[MemberItem]:
        group = await self.group_repo.get_by_id(group_id)
        if not group:
            raise GroupNotFoundError()
        rows = await self.membership_repo.get_members_by_group(group_id)
        return [
            MemberItem(
                id=membership.id,
                member_id=membership.member_id,
                full_name=full_name,
                role=membership.role,
            )
            for membership, full_name in rows
        ]

    async def remove_member(self, payload: dict, group_id: int, member_id: int) -> RemoveMemberResponse:
        member = await self._get_member(payload)
        await self._assert_leader(member.id, group_id)

        membership = await self.membership_repo.get(member_id, group_id)
        if not membership or membership.status != MembershipStatus.APPROVED:
            raise MembershipNotFoundError()
        if membership.role == MembershipRole.LEADER:
            raise GroupActionNotAllowedError("The group leader cannot be removed from their own group")

        membership_id = membership.id
        await self.membership_repo.delete(membership)

        return RemoveMemberResponse(
            id=membership_id,
            member_id=member_id,
            group_id=group_id,
            message=MembershipMessages.MEMBER_REMOVED,
        )

    async def leave(self, payload: dict, group_id: int) -> RemoveMemberResponse:
        """A member leaving a group of their own accord - the self-service
        counterpart to remove_member, which only a leader can do to someone
        else. A leader cannot leave their own group this way; they would need
        to hand off leadership or delete the group instead."""
        member = await self._get_member(payload)

        membership = await self.membership_repo.get(member.id, group_id)
        if not membership or membership.status != MembershipStatus.APPROVED:
            raise MembershipNotFoundError()
        if membership.role == MembershipRole.LEADER:
            raise GroupActionNotAllowedError("The group leader cannot leave their own group")

        membership_id = membership.id
        await self.membership_repo.delete(membership)

        return RemoveMemberResponse(
            id=membership_id,
            member_id=member.id,
            group_id=group_id,
            message=MembershipMessages.LEFT_GROUP,
        )

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member

    async def _assert_leader(self, member_id: int, group_id: int):
        if not await self.membership_repo.is_leader(member_id, group_id):
            raise NotGroupLeaderError()
