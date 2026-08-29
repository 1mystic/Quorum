from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Notification, NotificationType, Member
from sqlalchemy import select, update, func


class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(self, member_id: int, type: NotificationType, message: str,
                                  group_id: int | None = None,
                                  event_id: int | None = None) -> Notification:
        # tenant_id derived from the recipient member, never from the caller.
        tenant_id = (await self.db.execute(
            select(Member.tenant_id).where(Member.id == member_id)
        )).scalar_one()
        new_notification = Notification(
            tenant_id=tenant_id,
            member_id=member_id,
            type=type,
            message=message,
            group_id=group_id,
            event_id=event_id,
        )
        self.db.add(new_notification)
        await self.db.flush()
        return new_notification

    async def get_by_id(self, notification_id: int) -> Notification | None:
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def list_by_member(self, member_id: int, is_read: bool | None = None,
                              type: NotificationType | None = None, limit: int = 50,
                              offset: int = 0) -> list[Notification]:
        conditions = [Notification.member_id == member_id]
        if is_read is not None:
            conditions.append(Notification.is_read == is_read)
        if type is not None:
            conditions.append(Notification.type == type)

        result = await self.db.execute(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_unread(self, member_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.member_id == member_id,
                Notification.is_read.is_(False),
            )
        )
        return result.scalar_one()

    async def set_read(self, notification: Notification) -> Notification:
        notification.is_read = True
        return notification

    async def mark_all_read(self, member_id: int) -> int:
        result = await self.db.execute(
            update(Notification)
            .where(Notification.member_id == member_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        return result.rowcount
