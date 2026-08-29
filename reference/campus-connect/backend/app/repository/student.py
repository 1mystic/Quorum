from sqlalchemy.ext.asyncio import AsyncSession
from app.core import utcnow
from app.models import Student, User
from sqlalchemy import select
from sqlalchemy.orm import selectinload

PROFILE_FIELDS = ("bio", "interests", "roll_no", "branch", "year")


class StudentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_student_by_user_id(self, user_id: int) -> Student | None:
        result = await self.db.execute(select(Student).where(Student.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_by_id_with_user(self, student_id: int) -> Student | None:
        result = await self.db.execute(
            select(Student).where(Student.id == student_id).options(selectinload(Student.user))
        )
        return result.scalar_one_or_none()

    async def get_by_user_id_with_user(self, user_id: int) -> Student | None:
        result = await self.db.execute(
            select(Student).where(Student.user_id == user_id).options(selectinload(Student.user))
        )
        return result.scalar_one_or_none()

    async def get_full_name(self, student_id: int) -> str | None:
        result = await self.db.execute(
            select(User.full_name)
            .join(Student, Student.user_id == User.id)
            .where(Student.id == student_id)
        )
        return result.scalar_one_or_none()

    async def update_profile(self, student: Student, changes: dict) -> Student:
        for field in PROFILE_FIELDS:
            if field in changes:
                setattr(student, field, changes[field])
        await self.db.flush()
        return student

    async def mark_announcements_seen(self, student: Student) -> Student:
        student.announcements_seen_at = utcnow()
        await self.db.flush()
        return student
