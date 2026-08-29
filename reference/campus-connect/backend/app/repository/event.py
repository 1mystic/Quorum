from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Event, EventStatus, EventRegistration, Club, RegistrationResult
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from datetime import datetime


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, club_id: int, created_by: int, title: str, description: str,
                           venue: str, starts_at: datetime, ends_at: datetime,
                           capacity: int | None, image_url: str | None) -> Event:
        new_event = Event(
            club_id=club_id,
            created_by=created_by,
            title=title,
            description=description,
            venue=venue,
            starts_at=starts_at,
            ends_at=ends_at,
            capacity=capacity,
            image_url=image_url,
            status=EventStatus.DRAFT,
        )
        self.db.add(new_event)
        await self.db.flush()
        return new_event

    async def get_by_id(self, event_id: int) -> Event | None:
        result = await self.db.execute(
            select(Event).where(Event.id == event_id).options(selectinload(Event.club))
        )
        return result.scalar_one_or_none()

    async def lock_for_update(self, event_id: int) -> Event | None:
        result = await self.db.execute(
            select(Event).where(Event.id == event_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_by_college(self, college_id: int, status: EventStatus | None = None,
                              club_id: int | None = None, search: str | None = None,
                              upcoming_only: bool = False) -> list[tuple[Event, str, int, bool]]:
        conditions = [Club.college_id == college_id]
        if status is not None:
            conditions.append(Event.status == status)
        if club_id is not None:
            conditions.append(Event.club_id == club_id)
        if upcoming_only:
            conditions.append(Event.ends_at >= func.now())
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(Event.title.ilike(pattern), Event.description.ilike(pattern),
                    Event.venue.ilike(pattern))
            )

        result = await self.db.execute(
            select(
                Event, Club.name, func.count(EventRegistration.id),
                # bool_or across the outer-joined registrations in the same
                # grouped query - avoids an N+1 "is this event's result
                # declared" check per row for what the leader events list
                # needs to tell "Set Results" from "View Results".
                func.bool_or(
                    EventRegistration.result.in_(
                        (RegistrationResult.WINNER, RegistrationResult.RUNNER_UP)
                    )
                ),
            )
            .join(Club, Club.id == Event.club_id)
            .outerjoin(EventRegistration, EventRegistration.event_id == Event.id)
            .where(*conditions)
            .group_by(Event.id, Club.name)
            .order_by(Event.starts_at.asc())
        )
        return [
            (event, club_name, count, bool(declared))
            for event, club_name, count, declared in result.all()
        ]

    async def count_registrations(self, event_id: int) -> int:
        result = await self.db.execute(
            select(func.count(EventRegistration.id)).where(EventRegistration.event_id == event_id)
        )
        return result.scalar_one()

    async def update_event(self, event: Event, title: str | None, description: str | None,
                           venue: str | None, starts_at: datetime | None, ends_at: datetime | None,
                           capacity: int | None, image_url: str | None) -> Event:
        if title is not None:
            event.title = title
        if description is not None:
            event.description = description
        if venue is not None:
            event.venue = venue
        if starts_at is not None:
            event.starts_at = starts_at
        if ends_at is not None:
            event.ends_at = ends_at
        if capacity is not None:
            event.capacity = capacity
        if image_url is not None:
            event.image_url = image_url
        return event

    async def set_status(self, event: Event, status: EventStatus) -> Event:
        event.status = status
        return event
