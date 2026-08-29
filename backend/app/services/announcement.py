from datetime import datetime
from app.repository import (
    AnnouncementRepository, GroupRepository, MembershipRepository,
    MemberRepository, UserRepository
)
from app.models import Announcement, AnnouncementCategory, GroupStatus, MembershipRole
from app.schemas import (
    CreateAnnouncementRequest, PinAnnouncementRequest, CreateAnnouncementResponse,
    AnnouncementItem, PinAnnouncementResponse, DeleteAnnouncementResponse,
    UnreadCountResponse, MarkAnnouncementsReadResponse
)
from app.exceptions import (
    AnnouncementNotFoundError, GroupNotFoundError, GroupNotActiveError,
    NotGroupLeaderError, MemberNotFoundError, TenantNotFoundError
)
from app.core.messages import AnnouncementMessages


class AnnouncementService:
    def __init__(self, announcement_repo: AnnouncementRepository, group_repo: GroupRepository,
                 membership_repo: MembershipRepository, member_repo: MemberRepository,
                 user_repo: UserRepository):
        self.announcement_repo = announcement_repo
        self.group_repo = group_repo
        self.membership_repo = membership_repo
        self.member_repo = member_repo
        self.user_repo = user_repo

    async def create(self, payload: dict, data: CreateAnnouncementRequest) -> CreateAnnouncementResponse:
        member = await self._get_member(payload)
        tenant_id = await self._tenant_id(payload)

        group = await self.group_repo.get_by_id(data.group_id)
        if not group or group.tenant_id != tenant_id:
            raise GroupNotFoundError()
        if group.status != GroupStatus.ACTIVE:
            raise GroupNotActiveError()
        if not await self.membership_repo.is_leader(member.id, group.id):
            raise NotGroupLeaderError()

        announcement = await self.announcement_repo.create_announcement(
            group_id=group.id,
            author_id=member.id,
            title=data.title,
            body=data.body,
            category=data.category,
            is_pinned=data.is_pinned,
        )
        return CreateAnnouncementResponse(
            id=announcement.id, group_id=group.id, title=announcement.title,
            category=announcement.category, is_pinned=announcement.is_pinned,
            message=AnnouncementMessages.POSTED,
        )

    async def feed(self, payload: dict, group_id: int | None = None,
                   category: AnnouncementCategory | None = None, search: str | None = None,
                   limit: int = 50, offset: int = 0) -> list[AnnouncementItem]:
        member = await self._get_member(payload)
        rows = await self.announcement_repo.list_for_member(
            member.id, group_id=group_id, category=category, search=search,
            limit=limit, offset=offset
        )
        return self._to_items(rows, member.announcements_seen_at)

    async def mine(self, payload: dict, group_id: int | None = None,
                   category: AnnouncementCategory | None = None, search: str | None = None,
                   limit: int = 50, offset: int = 0) -> list[AnnouncementItem]:
        member = await self._get_member(payload)
        rows = await self.announcement_repo.list_for_member(
            member.id, role=MembershipRole.LEADER, group_id=group_id,
            category=category, search=search, limit=limit, offset=offset
        )
        return self._to_items(rows, member.announcements_seen_at)

    async def unread_count(self, payload: dict) -> UnreadCountResponse:
        member = await self._get_member(payload)
        count = await self.announcement_repo.count_unread(
            member.id, member.announcements_seen_at
        )
        return UnreadCountResponse(count=count)

    async def pin(self, payload: dict, announcement_id: int,
                  data: PinAnnouncementRequest) -> PinAnnouncementResponse:
        announcement = await self._managed_announcement(payload, announcement_id)
        await self.announcement_repo.set_pinned(announcement, data.pinned)
        message = AnnouncementMessages.PINNED if data.pinned else AnnouncementMessages.UNPINNED
        return PinAnnouncementResponse(
            id=announcement.id, title=announcement.title,
            is_pinned=announcement.is_pinned, message=message,
        )

    async def delete(self, payload: dict, announcement_id: int) -> DeleteAnnouncementResponse:
        announcement = await self._managed_announcement(payload, announcement_id)
        await self.announcement_repo.delete_announcement(announcement)
        return DeleteAnnouncementResponse(
            id=announcement_id, message=AnnouncementMessages.DELETED,
        )

    async def mark_read(self, payload: dict) -> MarkAnnouncementsReadResponse:
        member = await self._get_member(payload)
        await self.member_repo.mark_announcements_seen(member)
        return MarkAnnouncementsReadResponse(
            seen_at=member.announcements_seen_at,
            message=AnnouncementMessages.MARKED_READ,
        )

    @staticmethod
    def _to_items(rows: list[tuple[Announcement, str, str]],
                  seen_at: datetime | None) -> list[AnnouncementItem]:
        return [
            AnnouncementItem(
                id=announcement.id,
                group_id=announcement.group_id,
                group_name=group_name,
                author_id=announcement.author_id,
                author_name=author_name,
                title=announcement.title,
                body=announcement.body,
                category=announcement.category,
                is_pinned=announcement.is_pinned,
                unread=seen_at is None or announcement.created_at > seen_at,
                created_at=announcement.created_at,
            )
            for announcement, group_name, author_name in rows
        ]

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member

    async def _tenant_id(self, payload: dict) -> int:
        tenant_id = await self.user_repo.get_tenant_id(int(payload.get("sub")))
        if not tenant_id:
            raise TenantNotFoundError()
        return tenant_id

    async def _managed_announcement(self, payload: dict, announcement_id: int) -> Announcement:
        member = await self._get_member(payload)
        announcement = await self.announcement_repo.get_by_id(announcement_id)
        if not announcement:
            raise AnnouncementNotFoundError()
        if announcement.group.tenant_id != await self._tenant_id(payload):
            raise AnnouncementNotFoundError()
        if not await self.membership_repo.is_leader(member.id, announcement.group_id):
            raise NotGroupLeaderError()
        return announcement
