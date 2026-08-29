from datetime import datetime, timezone
from fastapi import UploadFile
from app.repository import (
    EventRepository, EventRegistrationRepository, ClubRepository,
    MembershipRepository, StudentRepository, UserRepository
)
from app.models import Event, EventStatus, ClubStatus, UserRole
from app.schemas import (
    CreateEventRequest, UpdateEventRequest, CreateEventResponse, EventStatusResponse,
    EventListItem, EventDetailResponse
)
from app.exceptions import (
    EventNotFoundError, EventActionNotAllowedError, ClubNotFoundError, ClubNotActiveError,
    NotClubLeaderError, StudentNotFoundError, CollegeNotFoundError
)
from app.core.messages import EventMessages
from app.core.storage import Storage, EVENT_FOLDER


class EventService:
    def __init__(self, event_repo: EventRepository, registration_repo: EventRegistrationRepository,
                 club_repo: ClubRepository, membership_repo: MembershipRepository,
                 student_repo: StudentRepository, user_repo: UserRepository, storage: Storage):
        self.event_repo = event_repo
        self.registration_repo = registration_repo
        self.club_repo = club_repo
        self.membership_repo = membership_repo
        self.student_repo = student_repo
        self.user_repo = user_repo
        self.storage = storage

    async def create(self, payload: dict, data: CreateEventRequest,
                     image: UploadFile | None = None) -> CreateEventResponse:
        student = await self._get_student(payload)
        college_id = await self._college_id(payload)

        club = await self.club_repo.get_by_id(data.club_id)
        if not club or club.college_id != college_id:
            raise ClubNotFoundError()
        if club.status != ClubStatus.ACTIVE:
            raise ClubNotActiveError()
        if not await self.membership_repo.is_leader(student.id, club.id):
            raise NotClubLeaderError()

        image_url = await self.storage.upload_image(image, EVENT_FOLDER) if image else None
        event = await self.event_repo.create_event(
            club_id=club.id,
            created_by=student.id,
            title=data.title,
            description=data.description,
            venue=data.venue,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            capacity=data.capacity,
            image_url=image_url,
        )
        return CreateEventResponse(
            id=event.id, club_id=club.id, title=event.title,
            status=event.status, message=EventMessages.CREATED,
        )

    async def list(self, payload: dict, status: EventStatus | None = None,
                   club_id: int | None = None, search: str | None = None,
                   upcoming_only: bool = False) -> list[EventListItem]:
        college_id = await self._college_id(payload)
        effective_status = await self._effective_status(payload, status, club_id)

        rows = await self.event_repo.list_by_college(
            college_id, effective_status, club_id, search, upcoming_only
        )
        return [
            EventListItem(
                id=event.id,
                club_id=event.club_id,
                club_name=club_name,
                title=event.title,
                description=event.description,
                venue=event.venue,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                capacity=event.capacity,
                registration_count=count,
                seats_left=self._seats_left(event.capacity, count),
                status=event.status,
                image_url=event.image_url,
                created_at=event.created_at,
                results_declared=results_declared,
            )
            for event, club_name, count, results_declared in rows
        ]

    async def get(self, payload: dict, event_id: int) -> EventDetailResponse:
        event = await self._visible_event(payload, event_id)

        registration = None
        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        if student:
            registration = await self.registration_repo.get(event.id, student.id)

        count = await self.event_repo.count_registrations(event.id)
        return EventDetailResponse(
            id=event.id,
            club_id=event.club_id,
            club_name=event.club.name,
            title=event.title,
            description=event.description,
            venue=event.venue,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            capacity=event.capacity,
            registration_count=count,
            seats_left=self._seats_left(event.capacity, count),
            status=event.status,
            image_url=event.image_url,
            created_at=event.created_at,
            is_registered=registration is not None,
            my_registration_id=registration.id if registration else None,
        )

    async def update(self, payload: dict, event_id: int, data: UpdateEventRequest,
                     image: UploadFile | None = None) -> EventDetailResponse:
        event = await self._managed_event(payload, event_id)
        if event.status == EventStatus.CANCELLED:
            raise EventActionNotAllowedError("A cancelled event cannot be edited")

        starts_at = data.starts_at or event.starts_at
        ends_at = data.ends_at or event.ends_at
        if ends_at <= starts_at:
            raise EventActionNotAllowedError("Event must end after it starts")

        old_image_url = event.image_url
        new_image_url = await self.storage.upload_image(image, EVENT_FOLDER) if image else None
        await self.event_repo.update_event(
            event, data.title, data.description, data.venue,
            data.starts_at, data.ends_at, data.capacity, new_image_url,
        )
        if new_image_url:
            await self.storage.delete_url(old_image_url)
        return await self.get(payload, event_id)

    async def publish(self, payload: dict, event_id: int) -> EventStatusResponse:
        event = await self._managed_event(payload, event_id)
        if event.status == EventStatus.CANCELLED:
            raise EventActionNotAllowedError("A cancelled event cannot be published")
        if event.status == EventStatus.PUBLISHED:
            raise EventActionNotAllowedError("Event is already published")
        if event.starts_at <= self._now():
            raise EventActionNotAllowedError("An event starting in the past cannot be published")

        await self.event_repo.set_status(event, EventStatus.PUBLISHED)
        return EventStatusResponse(
            id=event.id, title=event.title, status=event.status,
            message=EventMessages.PUBLISHED,
        )

    async def cancel(self, payload: dict, event_id: int) -> EventStatusResponse:
        event = await self._managed_event(payload, event_id)
        if event.status == EventStatus.CANCELLED:
            raise EventActionNotAllowedError("Event is already cancelled")

        await self.event_repo.set_status(event, EventStatus.CANCELLED)
        return EventStatusResponse(
            id=event.id, title=event.title, status=event.status,
            message=EventMessages.CANCELLED,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _is_admin(payload: dict) -> bool:
        return payload.get("role") == UserRole.CAMPUS_ADMIN

    @staticmethod
    def _seats_left(capacity: int | None, taken: int) -> int | None:
        return None if capacity is None else max(capacity - taken, 0)

    async def _get_student(self, payload: dict):
        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        if not student:
            raise StudentNotFoundError()
        return student

    async def _college_id(self, payload: dict) -> int:
        college_id = await self.user_repo.get_college_id(int(payload.get("sub")))
        if not college_id:
            raise CollegeNotFoundError()
        return college_id

    async def _effective_status(self, payload: dict, status: EventStatus | None,
                                club_id: int | None) -> EventStatus | None:
        # Campus admins see every status. A club leader does too, but only for a club they
        # lead and only when they ask for it by id, so the open browse feed stays published-only.
        if self._is_admin(payload):
            return status
        if club_id is not None and await self._leads_club(payload, club_id):
            return status
        return EventStatus.PUBLISHED

    async def _leads_club(self, payload: dict, club_id: int) -> bool:
        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        return bool(student) and await self.membership_repo.is_leader(student.id, club_id)

    async def _visible_event(self, payload: dict, event_id: int) -> Event:
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFoundError()
        if event.club.college_id != await self._college_id(payload):
            raise EventNotFoundError()

        if event.status == EventStatus.PUBLISHED or self._is_admin(payload):
            return event

        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        if student and await self.membership_repo.is_leader(student.id, event.club_id):
            return event
        raise EventNotFoundError()

    async def _managed_event(self, payload: dict, event_id: int) -> Event:
        student = await self._get_student(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFoundError()
        if event.club.college_id != await self._college_id(payload):
            raise EventNotFoundError()
        if not await self.membership_repo.is_leader(student.id, event.club_id):
            raise NotClubLeaderError()
        return event
