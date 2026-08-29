from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Announcement, AnnouncementCategory, Group, Membership, MembershipRole,
    MembershipStatus, Member, User
)
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from datetime import datetime


class AnnouncementRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_announcement(self, group_id: int, author_id: int, title: str, body: str,
                                  category: AnnouncementCategory,
                                  is_pinned: bool) -> Announcement:
        # tenant_id derived from the parent group, never from the caller.
        tenant_id = (await self.db.execute(
            select(Group.tenant_id).where(Group.id == group_id)
        )).scalar_one()
        new_announcement = Announcement(
            tenant_id=tenant_id,
            group_id=group_id,
            author_id=author_id,
            title=title,
            body=body,
            category=category,
            is_pinned=is_pinned,
        )
        self.db.add(new_announcement)
        await self.db.flush()
        return new_announcement

    async def get_by_id(self, announcement_id: int) -> Announcement | None:
        result = await self.db.execute(
            select(Announcement)
            .where(Announcement.id == announcement_id)
            .options(selectinload(Announcement.group))
        )
        return result.scalar_one_or_none()

    async def list_for_member(self, member_id: int, role: MembershipRole | None = None,
                               group_id: int | None = None,
                               category: AnnouncementCategory | None = None,
                               search: str | None = None, limit: int = 50,
                               offset: int = 0) -> list[tuple[Announcement, str, str]]:
        conditions = [
            Membership.member_id == member_id,
            Membership.status == MembershipStatus.APPROVED,
        ]
        if role is not None:
            conditions.append(Membership.role == role)
        if group_id is not None:
            conditions.append(Announcement.group_id == group_id)
        if category is not None:
            conditions.append(Announcement.category == category)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(Announcement.title.ilike(pattern), Announcement.body.ilike(pattern))
            )

        result = await self.db.execute(
            select(Announcement, Group.name, User.full_name)
            .join(Group, Group.id == Announcement.group_id)
            .join(Membership, Membership.group_id == Announcement.group_id)
            .join(Member, Member.id == Announcement.author_id)
            .join(User, User.id == Member.user_id)
            .where(*conditions)
            .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.all()

    async def count_unread(self, member_id: int, seen_at: datetime | None) -> int:
        conditions = [
            Membership.member_id == member_id,
            Membership.status == MembershipStatus.APPROVED,
        ]
        if seen_at is not None:
            conditions.append(Announcement.created_at > seen_at)

        result = await self.db.execute(
            select(func.count(Announcement.id))
            .join(Membership, Membership.group_id == Announcement.group_id)
            .where(*conditions)
        )
        return result.scalar_one()

    async def set_pinned(self, announcement: Announcement, is_pinned: bool) -> Announcement:
        announcement.is_pinned = is_pinned
        return announcement

    async def delete_announcement(self, announcement: Announcement) -> None:
        await self.db.delete(announcement)
