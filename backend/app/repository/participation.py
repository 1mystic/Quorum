from datetime import datetime, timezone

from sqlalchemy import select

from app.models import ParticipationEventLog
from app.repository.base import TenantScopedRepository


class ParticipationRepository(TenantScopedRepository):
    """
    Tenant-scoped, same pattern as `RequestRepository`/`LedgerRepository`:
    every query adds `tenant_id == self.tenant_id`, every write sets it
    itself. `stream_events` at the bottom is the whole of what this class
    hands the `participation` stream adapter: rows, tenant-scoped, no
    arithmetic. "You fetch and cache; they compute."
    """

    async def record_event(
        self, *, member_id: int, kind, at: datetime | None = None,
        object_type: str | None = None, object_id: int | None = None,
        group_id: int | None = None, weight: float = 1.0,
        channel: str | None = None, arm_ref: str | None = None,
        strata: dict | None = None,
    ) -> ParticipationEventLog:
        event = ParticipationEventLog(
            tenant_id=self.tenant_id,
            member_id=member_id,
            at=at or datetime.now(timezone.utc),
            kind=kind,
            object_type=object_type,
            object_id=object_id,
            group_id=group_id,
            weight=weight,
            channel=channel,
            arm_ref=arm_ref,
            strata=strata or {},
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_by_id(self, event_id: int) -> ParticipationEventLog | None:
        result = await self.db.execute(
            self.scope(select(ParticipationEventLog), ParticipationEventLog)
            .where(ParticipationEventLog.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_for_member(self, member_id: int, limit: int = 50,
                               offset: int = 0) -> list[ParticipationEventLog]:
        result = await self.db.execute(
            self.scope(select(ParticipationEventLog), ParticipationEventLog)
            .where(ParticipationEventLog.member_id == member_id)
            .order_by(ParticipationEventLog.at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    # ---- stream fetch -------------------------------------------------

    async def stream_events(self, window_end: datetime) -> list[ParticipationEventLog]:
        result = await self.db.execute(
            self.scope(select(ParticipationEventLog), ParticipationEventLog)
            .where(ParticipationEventLog.at < window_end)
            .order_by(ParticipationEventLog.member_id, ParticipationEventLog.at)
        )
        return list(result.scalars().all())
