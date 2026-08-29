from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    EventRegistration, RegistrationResult, Event, Club, Student, User
)
from sqlalchemy import select, func
from datetime import datetime, timezone


class EventRegistrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, event_id: int, student_id: int) -> EventRegistration:
        new_registration = EventRegistration(
            event_id=event_id,
            student_id=student_id,
            checked_in=False,
            result=RegistrationResult.REGISTRANT,
        )
        self.db.add(new_registration)
        await self.db.flush()
        return new_registration

    async def get(self, event_id: int, student_id: int) -> EventRegistration | None:
        result = await self.db.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.student_id == student_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, registration_id: int) -> EventRegistration | None:
        result = await self.db.execute(
            select(EventRegistration).where(EventRegistration.id == registration_id)
        )
        return result.scalar_one_or_none()

    async def count_for_event(self, event_id: int) -> int:
        result = await self.db.execute(
            select(func.count(EventRegistration.id)).where(
                EventRegistration.event_id == event_id
            )
        )
        return result.scalar_one()

    async def list_participants(self, event_id: int) -> list[tuple[EventRegistration, Student, str, str]]:
        result = await self.db.execute(
            select(EventRegistration, Student, User.full_name, User.email)
            .join(Student, Student.id == EventRegistration.student_id)
            .join(User, User.id == Student.user_id)
            .where(EventRegistration.event_id == event_id)
            .order_by(EventRegistration.created_at.asc())
        )
        return result.all()

    async def list_by_student(self, student_id: int) -> list[tuple[EventRegistration, Event, str]]:
        result = await self.db.execute(
            select(EventRegistration, Event, Club.name)
            .join(Event, Event.id == EventRegistration.event_id)
            .join(Club, Club.id == Event.club_id)
            .where(EventRegistration.student_id == student_id)
            .order_by(Event.starts_at.desc())
        )
        return result.all()

    async def list_results_by_student(self, student_id: int) -> list[tuple[EventRegistration, Event, str]]:
        result = await self.db.execute(
            select(EventRegistration, Event, Club.name)
            .join(Event, Event.id == EventRegistration.event_id)
            .join(Club, Club.id == Event.club_id)
            .where(
                EventRegistration.student_id == student_id,
                EventRegistration.checked_in.is_(True),
                EventRegistration.result != RegistrationResult.REGISTRANT,
            )
            .order_by(Event.starts_at.desc())
        )
        return result.all()

    async def list_checked_in(self, event_id: int) -> list[EventRegistration]:
        result = await self.db.execute(
            select(EventRegistration)
            .where(
                EventRegistration.event_id == event_id,
                EventRegistration.checked_in.is_(True),
            )
            .order_by(EventRegistration.id.asc())
        )
        return list(result.scalars().all())

    async def results_declared(self, event_id: int) -> bool:
        result = await self.db.execute(
            select(EventRegistration.id)
            .where(
                EventRegistration.event_id == event_id,
                EventRegistration.result.in_(
                    (RegistrationResult.WINNER, RegistrationResult.RUNNER_UP)
                ),
            )
            .limit(1)
        )
        return result.first() is not None

    async def set_attendance(self, registration: EventRegistration, checked_in: bool) -> EventRegistration:
        registration.checked_in = checked_in
        registration.checked_in_at = datetime.now(timezone.utc) if checked_in else None
        return registration

    async def set_result(self, registration: EventRegistration,
                         result: RegistrationResult) -> EventRegistration:
        registration.result = result
        return registration

    async def delete(self, registration: EventRegistration) -> None:
        await self.db.delete(registration)
