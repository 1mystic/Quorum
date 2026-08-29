from datetime import datetime, timezone
from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository import (
    EventRegistrationRepository, EventRepository, ClubRepository,
    MembershipRepository, StudentRepository, UserRepository, NotificationRepository
)
from app.models import EventStatus, MembershipStatus, RegistrationResult, NotificationType
from app.schemas import (
    RegistrationConfirmation, UnregisterResponse, ParticipantItem, MarkAttendanceRequest,
    AttendanceResponse, DeclareResultsRequest, DeclaredResultItem, DeclareResultsResponse,
    MyRegistrationItem, MyResultItem
)
from app.exceptions import (
    EventNotFoundError, EventNotPublishedError, EventFullError, AlreadyRegisteredError,
    RegistrationNotFoundError, RegistrationClosedError, NotClubMemberError,
    AttendanceNotAllowedError, NotCheckedInError, NotClubLeaderError,
    StudentNotFoundError, CollegeNotFoundError, ResultsAlreadyDeclaredError
)
from app.core.messages import RegistrationMessages, NotificationMessages
from app.services.certificate import issue_certificate_job


class EventRegistrationService:
    def __init__(self, registration_repo: EventRegistrationRepository, event_repo: EventRepository,
                 club_repo: ClubRepository, membership_repo: MembershipRepository,
                 student_repo: StudentRepository, user_repo: UserRepository,
                 notification_repo: NotificationRepository, db: AsyncSession):
        self.registration_repo = registration_repo
        self.event_repo = event_repo
        self.club_repo = club_repo
        self.membership_repo = membership_repo
        self.student_repo = student_repo
        self.user_repo = user_repo
        self.notification_repo = notification_repo
        self.db = db

    async def register(self, payload: dict, event_id: int) -> RegistrationConfirmation:
        student = await self._get_student(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event or event.club.college_id != await self._college_id(payload):
            raise EventNotFoundError()

        if event.status != EventStatus.PUBLISHED:
            raise EventNotPublishedError()
        if event.starts_at <= self._now():
            raise RegistrationClosedError()

        membership = await self.membership_repo.get(student.id, event.club_id)
        if not membership or membership.status != MembershipStatus.APPROVED:
            raise NotClubMemberError()

        if await self.registration_repo.get(event_id, student.id):
            raise AlreadyRegisteredError()

        # Pessimistic lock: serialise concurrent registrations for this one event so the
        # capacity check and the insert cannot interleave. Uncapped events skip the lock.
        if event.capacity is not None:
            await self.event_repo.lock_for_update(event_id)
            taken = await self.registration_repo.count_for_event(event_id)
            if taken >= event.capacity:
                raise EventFullError()

        try:
            registration = await self.registration_repo.create(event_id, student.id)
        except IntegrityError:
            raise AlreadyRegisteredError()

        await self.notification_repo.create_notification(
            student_id=student.id,
            type=NotificationType.REGISTRATION_CONFIRMED,
            message=NotificationMessages.registration_confirmed(event.title),
            club_id=event.club_id,
            event_id=event.id,
        )

        return RegistrationConfirmation(
            registration_id=registration.id,
            event_id=event.id,
            event_title=event.title,
            venue=event.venue,
            starts_at=event.starts_at,
            message=RegistrationMessages.REGISTERED,
        )

    async def unregister(self, payload: dict, event_id: int) -> UnregisterResponse:
        student = await self._get_student(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event or event.club.college_id != await self._college_id(payload):
            raise EventNotFoundError()
        if event.starts_at <= self._now():
            raise RegistrationClosedError()

        registration = await self.registration_repo.get(event_id, student.id)
        if not registration:
            raise RegistrationNotFoundError()

        await self.registration_repo.delete(registration)
        return UnregisterResponse(event_id=event_id, message=RegistrationMessages.UNREGISTERED)

    async def participants(self, payload: dict, event_id: int) -> list[ParticipantItem]:
        await self._managed_event(payload, event_id)
        rows = await self.registration_repo.list_participants(event_id)
        return [
            ParticipantItem(
                registration_id=registration.id,
                student_id=student.id,
                full_name=full_name,
                email=email,
                roll_no=student.roll_no,
                branch=student.branch,
                year=student.year,
                checked_in=registration.checked_in,
                checked_in_at=registration.checked_in_at,
                result=registration.result,
                registered_at=registration.created_at,
            )
            for registration, student, full_name, email in rows
        ]

    async def mark_attendance(self, payload: dict, event_id: int, registration_id: int,
                              data: MarkAttendanceRequest) -> AttendanceResponse:
        event = await self._managed_event(payload, event_id)
        if event.starts_at > self._now():
            raise AttendanceNotAllowedError()
        if await self.registration_repo.results_declared(event_id):
            raise ResultsAlreadyDeclaredError()

        registration = await self._registration_of_event(registration_id, event_id)
        await self.registration_repo.set_attendance(registration, data.checked_in)

        await self.registration_repo.set_result(
            registration,
            RegistrationResult.PARTICIPANT if data.checked_in else RegistrationResult.REGISTRANT,
        )

        message = (
            RegistrationMessages.CHECKED_IN if data.checked_in
            else RegistrationMessages.CHECK_IN_UNDONE
        )
        return AttendanceResponse(
            registration_id=registration.id,
            student_id=registration.student_id,
            full_name=await self._student_name(registration.student_id),
            checked_in=registration.checked_in,
            checked_in_at=registration.checked_in_at,
            message=message,
        )

    async def declare_results(self, payload: dict, event_id: int, data: DeclareResultsRequest,
                              background: BackgroundTasks | None = None) -> DeclareResultsResponse:
        event = await self._managed_event(payload, event_id)
        if await self.registration_repo.results_declared(event_id):
            raise ResultsAlreadyDeclaredError()

        winner = await self._attendee(data.winner_registration_id, event_id)
        runner_up = await self._attendee(data.runner_up_registration_id, event_id)
        await self.registration_repo.set_result(winner, RegistrationResult.WINNER)
        await self.registration_repo.set_result(runner_up, RegistrationResult.RUNNER_UP)

        attendees = await self.registration_repo.list_checked_in(event_id)
        for registration in attendees:
            await self.notification_repo.create_notification(
                student_id=registration.student_id,
                type=NotificationType.RESULT_POSTED,
                message=NotificationMessages.result_posted(event.title, registration.result.value),
                club_id=event.club_id,
                event_id=event.id,
            )

        await self.db.commit()

        if background is not None:
            for registration in attendees:
                background.add_task(issue_certificate_job, registration.id)

        return DeclareResultsResponse(
            event_id=event.id,
            winner=await self._declared_item(winner),
            runner_up=await self._declared_item(runner_up),
            participants=len(attendees) - 2,
            certificates_queued=len(attendees),
            message=RegistrationMessages.RESULTS_DECLARED,
        )

    async def my_registrations(self, payload: dict) -> list[MyRegistrationItem]:
        student = await self._get_student(payload)
        rows = await self.registration_repo.list_by_student(student.id)
        return [
            MyRegistrationItem(
                registration_id=registration.id,
                event_id=event.id,
                event_title=event.title,
                club_id=event.club_id,
                club_name=club_name,
                venue=event.venue,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                event_status=event.status,
                checked_in=registration.checked_in,
                result=registration.result,
            )
            for registration, event, club_name in rows
        ]

    async def my_results(self, payload: dict) -> list[MyResultItem]:
        student = await self._get_student(payload)
        rows = await self.registration_repo.list_results_by_student(student.id)
        return [
            MyResultItem(
                event_id=event.id,
                event_title=event.title,
                club_id=event.club_id,
                club_name=club_name,
                venue=event.venue,
                starts_at=event.starts_at,
                registration_id=registration.id,
                result=registration.result,
            )
            for registration, event, club_name in rows
        ]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

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

    async def _student_name(self, student_id: int) -> str:
        return await self.student_repo.get_full_name(student_id)

    async def _managed_event(self, payload: dict, event_id: int):
        student = await self._get_student(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFoundError()
        if event.club.college_id != await self._college_id(payload):
            raise EventNotFoundError()
        if not await self.membership_repo.is_leader(student.id, event.club_id):
            raise NotClubLeaderError()
        return event

    async def _registration_of_event(self, registration_id: int, event_id: int):
        registration = await self.registration_repo.get_by_id(registration_id)
        if not registration or registration.event_id != event_id:
            raise RegistrationNotFoundError()
        return registration

    async def _attendee(self, registration_id: int, event_id: int):
        registration = await self._registration_of_event(registration_id, event_id)
        if not registration.checked_in:
            raise NotCheckedInError()
        return registration

    async def _declared_item(self, registration) -> DeclaredResultItem:
        return DeclaredResultItem(
            registration_id=registration.id,
            student_id=registration.student_id,
            full_name=await self._student_name(registration.student_id),
            result=registration.result,
        )
