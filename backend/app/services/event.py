from datetime import datetime, timezone
from fastapi import UploadFile
from app.repository import (
    EventRepository, EventRegistrationRepository, GroupRepository,
    MembershipRepository, MemberRepository, UserRepository
)
from app.models import Event, EventStatus, GroupStatus, UserRole
from app.schemas import (
    CreateEventRequest, UpdateEventRequest, CreateEventResponse, EventStatusResponse,
    EventListItem, EventDetailResponse, RejectContentRequest
)
from app.exceptions import (
    EventNotFoundError, EventActionNotAllowedError, GroupNotFoundError, GroupNotActiveError,
    NotGroupLeaderError, MemberNotFoundError, TenantNotFoundError
)
from app.core.messages import EventMessages
from app.core.storage import Storage, EVENT_FOLDER

# The editable states: a leader can still change the event while it has not
# yet gone live. SUBMITTED and PUBLISHED are frozen until a review decision
# (or, for PUBLISHED, a cancellation) moves it out of them.
_EDITABLE = (EventStatus.DRAFT, EventStatus.REJECTED)


class EventService:
    def __init__(self, event_repo: EventRepository, registration_repo: EventRegistrationRepository,
                 group_repo: GroupRepository, membership_repo: MembershipRepository,
                 member_repo: MemberRepository, user_repo: UserRepository, storage: Storage):
        self.event_repo = event_repo
        self.registration_repo = registration_repo
        self.group_repo = group_repo
        self.membership_repo = membership_repo
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.storage = storage

    async def create(self, payload: dict, data: CreateEventRequest,
                     image: UploadFile | None = None) -> CreateEventResponse:
        member = await self._get_member(payload)
        tenant_id = await self._tenant_id(payload)

        group = await self.group_repo.get_by_id(data.group_id)
        if not group or group.tenant_id != tenant_id:
            raise GroupNotFoundError()
        if group.status != GroupStatus.ACTIVE:
            raise GroupNotActiveError()
        if not await self.membership_repo.is_leader(member.id, group.id):
            raise NotGroupLeaderError()

        image_url = await self.storage.upload_image(image, EVENT_FOLDER) if image else None
        event = await self.event_repo.create_event(
            group_id=group.id,
            created_by=member.id,
            title=data.title,
            description=data.description,
            venue=data.venue,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            capacity=data.capacity,
            image_url=image_url,
        )
        return CreateEventResponse(
            id=event.id, group_id=group.id, title=event.title,
            status=event.status, message=EventMessages.CREATED,
        )

    async def list(self, payload: dict, status: EventStatus | None = None,
                   group_id: int | None = None, search: str | None = None,
                   upcoming_only: bool = False) -> list[EventListItem]:
        tenant_id = await self._tenant_id(payload)
        effective_status = await self._effective_status(payload, status, group_id)

        rows = await self.event_repo.list_by_tenant(
            tenant_id, effective_status, group_id, search, upcoming_only
        )
        return [
            EventListItem(
                id=event.id,
                group_id=event.group_id,
                group_name=group_name,
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
            for event, group_name, count, results_declared in rows
        ]

    async def get(self, payload: dict, event_id: int) -> EventDetailResponse:
        event = await self._visible_event(payload, event_id)

        registration = None
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if member:
            registration = await self.registration_repo.get(event.id, member.id)

        count = await self.event_repo.count_registrations(event.id)
        return EventDetailResponse(
            id=event.id,
            group_id=event.group_id,
            group_name=event.group.name,
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
            submitted_at=event.submitted_at,
            approved_at=event.approved_at,
            rejected_at=event.rejected_at,
            rejection_reason=event.rejection_reason,
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

    async def submit_for_review(self, payload: dict, event_id: int) -> EventStatusResponse:
        """The group leader's step: DRAFT (or a REJECTED event being resubmitted) -> SUBMITTED."""
        event = await self._managed_event(payload, event_id)
        if event.status not in _EDITABLE:
            raise EventActionNotAllowedError(
                "Only a draft or a rejected event can be submitted for review"
            )
        await self.event_repo.submit_for_review(event)
        return EventStatusResponse(
            id=event.id, title=event.title, status=event.status,
            message=EventMessages.SUBMITTED,
        )

    async def publish(self, payload: dict, event_id: int) -> EventStatusResponse:
        """
        TenantAdmin-only (router scope). Only callable from SUBMITTED: nothing
        public-facing goes live without an explicit review, so a leader can no
        longer publish straight from DRAFT.
        """
        event = await self._admin_event(payload, event_id)
        if event.status == EventStatus.CANCELLED:
            raise EventActionNotAllowedError("A cancelled event cannot be published")
        if event.status == EventStatus.PUBLISHED:
            raise EventActionNotAllowedError("Event is already published")
        if event.status != EventStatus.SUBMITTED:
            raise EventActionNotAllowedError("Only an event submitted for review can be published")
        if event.starts_at <= self._now():
            raise EventActionNotAllowedError("An event starting in the past cannot be published")

        await self.event_repo.approve(event, self._user_id(payload))
        return EventStatusResponse(
            id=event.id, title=event.title, status=event.status,
            message=EventMessages.PUBLISHED,
        )

    async def reject(self, payload: dict, event_id: int, reason: str) -> EventStatusResponse:
        """
        TenantAdmin-only. A rejection carries a reason (visible to the
        submitter on the detail response) and lands on REJECTED rather than a
        dead end: `submit_for_review` accepts a REJECTED event, so the leader
        can revise and resubmit it.
        """
        event = await self._admin_event(payload, event_id)
        if event.status != EventStatus.SUBMITTED:
            raise EventActionNotAllowedError("Only an event submitted for review can be rejected")

        await self.event_repo.reject(event, self._user_id(payload), reason)
        return EventStatusResponse(
            id=event.id, title=event.title, status=event.status,
            message=EventMessages.REJECTED, rejection_reason=event.rejection_reason,
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
        return payload.get("role") == UserRole.TENANT_ADMIN

    @staticmethod
    def _seats_left(capacity: int | None, taken: int) -> int | None:
        return None if capacity is None else max(capacity - taken, 0)

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

    async def _effective_status(self, payload: dict, status: EventStatus | None,
                                group_id: int | None) -> EventStatus | None:
        # Campus admins see every status. A group leader does too, but only for a group they
        # lead and only when they ask for it by id, so the open browse feed stays published-only.
        if self._is_admin(payload):
            return status
        if group_id is not None and await self._leads_group(payload, group_id):
            return status
        return EventStatus.PUBLISHED

    async def _leads_group(self, payload: dict, group_id: int) -> bool:
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        return bool(member) and await self.membership_repo.is_leader(member.id, group_id)

    async def _visible_event(self, payload: dict, event_id: int) -> Event:
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFoundError()
        if event.group.tenant_id != await self._tenant_id(payload):
            raise EventNotFoundError()

        if event.status == EventStatus.PUBLISHED or self._is_admin(payload):
            return event

        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if member and await self.membership_repo.is_leader(member.id, event.group_id):
            return event
        raise EventNotFoundError()

    async def _managed_event(self, payload: dict, event_id: int) -> Event:
        member = await self._get_member(payload)
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFoundError()
        if event.group.tenant_id != await self._tenant_id(payload):
            raise EventNotFoundError()
        if not await self.membership_repo.is_leader(member.id, event.group_id):
            raise NotGroupLeaderError()
        return event

    async def _admin_event(self, payload: dict, event_id: int) -> Event:
        """
        For approve/reject: the router already checked TENANT_ADMIN scope, so
        this only needs the tenant match, not a leader check - an admin
        reviews every group's submissions, not just one they happen to lead.
        """
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise EventNotFoundError()
        if event.group.tenant_id != await self._tenant_id(payload):
            raise EventNotFoundError()
        return event

    @staticmethod
    def _user_id(payload: dict) -> int:
        return int(payload.get("sub"))
