from datetime import datetime, timezone
from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository import (
    EventRegistrationRepository, EventRepository, GroupRepository,
    MembershipRepository, MemberRepository, UserRepository, NotificationRepository
)
from app.models import EventStatus, MembershipStatus, RegistrationResult, NotificationType
from app.schemas import (
    RegistrationConfirmation, UnregisterResponse, ParticipantItem, MarkAttendanceRequest,
    AttendanceResponse, DeclareResultsRequest, DeclaredResultItem, DeclareResultsResponse,
    MyRegistrationItem, MyResultItem
)
from app.exceptions import (
    EventNotFoundError, EventNotPublishedError, EventFullError, AlreadyRegisteredError,
    RegistrationNotFoundError, RegistrationClosedError, NotGroupMemberError,
    AttendanceNotAllowedError, NotCheckedInError, NotGroupLeaderError,
    MemberNotFoundError, TenantNotFoundError, ResultsAlreadyDeclaredError
)
from app.core.messages import RegistrationMessages, NotificationMessages
from app.services.certificate import issue_certificate_job


class EventRegistrationService:
    def __init__(self, registration_repo: EventRegistrationRepository, event_repo: EventRepository,
                 group_repo: GroupRepository, membership_repo: MembershipRepository,
                 member_repo: MemberRepository, user_repo: UserRepository,
                 notification_repo: NotificationRepository, db: AsyncSession):
        self.registration_repo = registration_repo
        self.event_repo = event_repo
        self.group_repo = group_repo
        self.membership_repo = membership_repo
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.notification_repo = notification_repo
        self.db = db

    async def register(self, payload: dict, event_id: int) -> RegistrationConfirmation:
        member = await self._get_member(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event or event.group.tenant_id != await self._tenant_id(payload):
            raise EventNotFoundError()

        if event.status != EventStatus.PUBLISHED:
            raise EventNotPublishedError()
        if event.starts_at <= self._now():
            raise RegistrationClosedError()

        membership = await self.membership_repo.get(member.id, event.group_id)
        if not membership or membership.status != MembershipStatus.APPROVED:
            raise NotGroupMemberError()

        if await self.registration_repo.get(event_id, member.id):
            raise AlreadyRegisteredError()

        # Pessimistic lock: serialise concurrent registrations for this one event so the
        # capacity check and the insert cannot interleave. Uncapped events skip the lock.
        if event.capacity is not None:
            await self.event_repo.lock_for_update(event_id)
            taken = await self.registration_repo.count_for_event(event_id)
            if taken >= event.capacity:
                raise EventFullError()

        try:
            registration = await self.registration_repo.create(event_id, member.id)
        except IntegrityError:
            raise AlreadyRegisteredError()

        await self.notification_repo.create_notification(
            member_id=member.id,
            type=NotificationType.REGISTRATION_CONFIRMED,
            message=NotificationMessages.registration_confirmed(event.title),
            group_id=event.group_id,
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
        member = await self._get_member(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event or event.group.tenant_id != await self._tenant_id(payload):
            raise EventNotFoundError()
        if event.starts_at <= self._now():
            raise RegistrationClosedError()

        registration = await self.registration_repo.get(event_id, member.id)
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
                member_id=member.id,
                full_name=full_name,
                email=email,
                roll_no=member.roll_no,
                branch=member.branch,
                year=member.year,
                checked_in=registration.checked_in,
                checked_in_at=registration.checked_in_at,
                result=registration.result,
                registered_at=registration.created_at,
            )
            for registration, member, full_name, email in rows
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
            member_id=registration.member_id,
            full_name=await self._member_name(registration.member_id),
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
                member_id=registration.member_id,
                type=NotificationType.RESULT_POSTED,
                message=NotificationMessages.result_posted(event.title, registration.result.value),
                group_id=event.group_id,
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
        member = await self._get_member(payload)
        rows = await self.registration_repo.list_by_member(member.id)
        return [
            MyRegistrationItem(
                registration_id=registration.id,
                event_id=event.id,
                event_title=event.title,
                group_id=event.group_id,
                group_name=group_name,
                venue=event.venue,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                event_status=event.status,
                checked_in=registration.checked_in,
                result=registration.result,
            )
            for registration, event, group_name in rows
        ]

    async def my_results(self, payload: dict) -> list[MyResultItem]:
        member = await self._get_member(payload)
        rows = await self.registration_repo.list_results_by_member(member.id)
        return [
            MyResultItem(
                event_id=event.id,
                event_title=event.title,
                group_id=event.group_id,
                group_name=group_name,
                venue=event.venue,
                starts_at=event.starts_at,
                registration_id=registration.id,
                result=registration.result,
            )
            for registration, event, group_name in rows
        ]

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member

    async def _tenant_id(self, payload: dict) -> int:
        tenant_id = await self.user_repo.get_tenant_id(int(payload.get("sub")))
        if not tenant_id:
            raise TenantNotFoundError()
        return tenant_id

    async def _member_name(self, member_id: int) -> str:
        return await self.member_repo.get_full_name(member_id)

    async def _managed_event(self, payload: dict, event_id: int):
        member = await self._get_member(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFoundError()
        if event.group.tenant_id != await self._tenant_id(payload):
            raise EventNotFoundError()
        if not await self.membership_repo.is_leader(member.id, event.group_id):
            raise NotGroupLeaderError()
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
            member_id=registration.member_id,
            full_name=await self._member_name(registration.member_id),
            result=registration.result,
        )
