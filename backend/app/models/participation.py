"""
Card C.15 (participation half). docs/DATA_SPINE.md section 4: attendance,
RSVP, upvotes, volunteer hours, and the exposure log
(nudge_sent/delivered/opened/acted with arm_ref), as one append-only event
table, same shape as `RequestEventLog` (card C.8).

This is the model the two adapters' `participation_events` TODO named as
missing: without it Pack 2's `experiments.*` and `bandits.*` have no input at
all, because a nudge that was sent is a system action against a member, not a
member action, and no purely member-centric table would naturally carry it.

Nothing here computes a duration, a rate or an RFM feature. That is
`app/stats/streams/reduce.py`'s job, downstream and pure, once it reduces the
`ParticipationEvent` atoms the adapter builds from these rows.
"""
import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Enum, DateTime, Float, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base, utcnow


class ParticipationKind(str, enum.Enum):
    """Mirrors `ParticipationKind` in `app/stats/streams/participation.py` exactly."""
    RSVP = "rsvp"
    RSVP_CANCEL = "rsvp_cancel"
    ATTEND = "attend"
    NO_SHOW = "no_show"
    LOGIN = "login"
    POST = "post"
    COMMENT = "comment"
    UPVOTE = "upvote"
    READ_RECEIPT = "read_receipt"
    VOLUNTEER_HOURS = "volunteer_hours"
    TRAINING_COMPLETE = "training_complete"
    IN_KIND_CONTRIBUTION = "in_kind_contribution"
    # The exposure log (spine section 8): a system action against a member,
    # never a member action. `arm_ref` is required on these four kinds and
    # forbidden on every other one, enforced at the service layer exactly as
    # `ParticipationEvent.__post_init__` enforces it on the stream atom.
    NUDGE_SENT = "nudge_sent"
    NUDGE_DELIVERED = "nudge_delivered"
    NUDGE_OPENED = "nudge_opened"
    NUDGE_ACTED = "nudge_acted"


EXPOSURE_KINDS = frozenset({
    ParticipationKind.NUDGE_SENT, ParticipationKind.NUDGE_DELIVERED,
    ParticipationKind.NUDGE_OPENED, ParticipationKind.NUDGE_ACTED,
})


class ParticipationEventLog(Base):
    """
    Append-only. One row per thing a member did (or was offered), tenant-scoped.

    `object_type`/`object_id` is a generic polymorphic reference (event,
    announcement, request, poll, campaign) rather than five nullable foreign
    keys, matching the atom's own `object_ref`/`object_kind` pair. The adapter
    builds the opaque `object_ref` string ("e_12", "a_7", ...) from these two
    columns, the same construction `object_ref()` in
    `app/verticals/adapters/base.py` already uses for `EventRegistration`/
    `Announcement` rows.
    """
    __tablename__ = "participation_events"
    __table_args__ = (
        Index("ix_participation_events_member_at", "member_id", "at"),
        Index("ix_participation_events_kind_at", "kind", "at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[ParticipationKind] = mapped_column(Enum(ParticipationKind))
    object_type: Mapped[str | None] = mapped_column()
    object_id: Mapped[int | None] = mapped_column()
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    weight: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    channel: Mapped[str | None] = mapped_column()
    # Experiment/bandit arm. Required on the four nudge_* kinds, forbidden
    # elsewhere (spine section 8; ParticipationEvent.__post_init__'s rule).
    arm_ref: Mapped[str | None] = mapped_column()
    strata: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    member: Mapped["Member"] = relationship(foreign_keys=[member_id])
