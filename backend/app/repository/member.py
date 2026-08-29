from sqlalchemy.ext.asyncio import AsyncSession
from app.core import utcnow
from app.models import Member, User
from sqlalchemy import select
from sqlalchemy.orm import selectinload

PROFILE_FIELDS = ("bio", "interests", "roll_no", "branch", "year")


class MemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_member_by_user_id(self, user_id: int) -> Member | None:
        result = await self.db.execute(select(Member).where(Member.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_by_id_with_user(self, member_id: int) -> Member | None:
        result = await self.db.execute(
            select(Member).where(Member.id == member_id).options(selectinload(Member.user))
        )
        return result.scalar_one_or_none()

    async def get_by_user_id_with_user(self, user_id: int) -> Member | None:
        result = await self.db.execute(
            select(Member).where(Member.user_id == user_id).options(selectinload(Member.user))
        )
        return result.scalar_one_or_none()

    async def get_full_name(self, member_id: int) -> str | None:
        result = await self.db.execute(
            select(User.full_name)
            .join(Member, Member.user_id == User.id)
            .where(Member.id == member_id)
        )
        return result.scalar_one_or_none()

    async def update_profile(self, member: Member, changes: dict) -> Member:
        for field in PROFILE_FIELDS:
            if field in changes:
                setattr(member, field, changes[field])
        await self.db.flush()
        return member

    async def mark_announcements_seen(self, member: Member) -> Member:
        member.announcements_seen_at = utcnow()
        await self.db.flush()
        return member
