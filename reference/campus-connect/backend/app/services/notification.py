from app.repository import NotificationRepository, StudentRepository
from app.models import NotificationType
from app.schemas import (
    NotificationItem, NotificationCountResponse, NotificationReadResponse,
    MarkAllNotificationsReadResponse
)
from app.exceptions import NotificationNotFoundError, StudentNotFoundError
from app.core.messages import NotificationMessages


class NotificationService:
    def __init__(self, notification_repo: NotificationRepository,
                 student_repo: StudentRepository):
        self.notification_repo = notification_repo
        self.student_repo = student_repo

    async def list(self, payload: dict, is_read: bool | None = None,
                   type: NotificationType | None = None, limit: int = 50,
                   offset: int = 0) -> list[NotificationItem]:
        student = await self._get_student(payload)
        rows = await self.notification_repo.list_by_student(
            student.id, is_read=is_read, type=type, limit=limit, offset=offset
        )
        return [
            NotificationItem(
                id=notification.id,
                type=notification.type,
                message=notification.message,
                club_id=notification.club_id,
                event_id=notification.event_id,
                is_read=notification.is_read,
                created_at=notification.created_at,
            )
            for notification in rows
        ]

    async def unread_count(self, payload: dict) -> NotificationCountResponse:
        student = await self._get_student(payload)
        count = await self.notification_repo.count_unread(student.id)
        return NotificationCountResponse(count=count)

    async def mark_read(self, payload: dict, notification_id: int) -> NotificationReadResponse:
        student = await self._get_student(payload)
        notification = await self.notification_repo.get_by_id(notification_id)
        if not notification or notification.student_id != student.id:
            raise NotificationNotFoundError()

        await self.notification_repo.set_read(notification)
        return NotificationReadResponse(
            id=notification.id, is_read=notification.is_read,
            message=NotificationMessages.MARKED_READ,
        )

    async def mark_all_read(self, payload: dict) -> MarkAllNotificationsReadResponse:
        student = await self._get_student(payload)
        updated = await self.notification_repo.mark_all_read(student.id)
        return MarkAllNotificationsReadResponse(
            updated=updated, message=NotificationMessages.ALL_MARKED_READ,
        )

    async def _get_student(self, payload: dict):
        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        if not student:
            raise StudentNotFoundError()
        return student
