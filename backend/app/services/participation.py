from app.repository import ParticipationRepository, MemberRepository, UserRepository
from app.models import EXPOSURE_KINDS
from app.schemas import RecordParticipationEventRequest, ParticipationEventItem
from app.exceptions import (
    MemberNotFoundError, TenantNotFoundError, ExposureArmRequiredError,
    ExposureArmNotAllowedError,
)


class ParticipationService:
    """
    Card C.15 (participation half). Same shape as `LedgerService`/
    `RequestService`: a thin layer that validates and hands everything else
    to `ParticipationRepository`. No RFM feature, no rate, no edge weight is
    computed here - that is `app/stats/streams/reduce.py`'s job, downstream
    and pure.
    """

    def __init__(self, participation_repo: ParticipationRepository, member_repo: MemberRepository,
                 user_repo: UserRepository, tenant_repo):
        self.participation_repo = participation_repo
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo

    async def record_event(self, payload: dict, data: RecordParticipationEventRequest) -> ParticipationEventItem:
        tenant_id = await self._tenant_id(payload)
        member = await self.member_repo.get_by_id(data.member_id)
        if not member or member.tenant_id != tenant_id:
            raise MemberNotFoundError()
        self._validate_exposure(data.kind.value, data.arm_ref)

        event = await self.participation_repo.record_event(
            member_id=data.member_id, kind=data.kind, at=data.at,
            object_type=data.object_type, object_id=data.object_id,
            group_id=data.group_id, weight=data.weight, channel=data.channel,
            arm_ref=data.arm_ref, strata=data.strata,
        )
        return self._item(event)

    async def my_events(self, payload: dict, limit: int = 50, offset: int = 0) -> list[ParticipationEventItem]:
        member = await self._get_member(payload)
        events = await self.participation_repo.list_for_member(member.id, limit=limit, offset=offset)
        return [self._item(event) for event in events]

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _validate_exposure(kind: str, arm_ref: str | None) -> None:
        """
        Mirrors `ParticipationEvent.__post_init__` in
        `app/stats/streams/participation.py` exactly, at the boundary where
        a row is written rather than at the boundary where it is read: an
        exposure-log row with no arm cannot ever be created, not merely
        rejected downstream.
        """
        if kind in EXPOSURE_KINDS and not arm_ref:
            raise ExposureArmRequiredError()
        if arm_ref and kind not in EXPOSURE_KINDS:
            raise ExposureArmNotAllowedError()

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

    @staticmethod
    def _item(event) -> ParticipationEventItem:
        return ParticipationEventItem(
            id=event.id, member_id=event.member_id, kind=event.kind, at=event.at,
            object_type=event.object_type, object_id=event.object_id, weight=event.weight,
            channel=event.channel, arm_ref=event.arm_ref,
        )
