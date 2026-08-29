from app.repository import NotificationRepository, MemberRepository
from app.models import NotificationType
from app.schemas import (
    NotificationItem, NotificationCountResponse, NotificationReadResponse,
    MarkAllNotificationsReadResponse
)
from app.exceptions import NotificationNotFoundError, MemberNotFoundError
from app.core.messages import NotificationMessages


class NotificationService:
    def __init__(self, notification_repo: NotificationRepository,
                 member_repo: MemberRepository):
        self.notification_repo = notification_repo
        self.member_repo = member_repo

    async def list(self, payload: dict, is_read: bool | None = None,
                   type: NotificationType | None = None, limit: int = 50,
                   offset: int = 0) -> list[NotificationItem]:
        member = await self._get_member(payload)
        rows = await self.notification_repo.list_by_member(
            member.id, is_read=is_read, type=type, limit=limit, offset=offset
        )
        return [
            NotificationItem(
                id=notification.id,
                type=notification.type,
                message=notification.message,
                group_id=notification.group_id,
                event_id=notification.event_id,
                is_read=notification.is_read,
                created_at=notification.created_at,
            )
            for notification in rows
        ]

    async def unread_count(self, payload: dict) -> NotificationCountResponse:
        member = await self._get_member(payload)
        count = await self.notification_repo.count_unread(member.id)
        return NotificationCountResponse(count=count)

    async def mark_read(self, payload: dict, notification_id: int) -> NotificationReadResponse:
        member = await self._get_member(payload)
        notification = await self.notification_repo.get_by_id(notification_id)
        if not notification or notification.member_id != member.id:
            raise NotificationNotFoundError()

        await self.notification_repo.set_read(notification)
        return NotificationReadResponse(
            id=notification.id, is_read=notification.is_read,
            message=NotificationMessages.MARKED_READ,
        )

    async def mark_all_read(self, payload: dict) -> MarkAllNotificationsReadResponse:
        member = await self._get_member(payload)
        updated = await self.notification_repo.mark_all_read(member.id)
        return MarkAllNotificationsReadResponse(
            updated=updated, message=NotificationMessages.ALL_MARKED_READ,
        )

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member
