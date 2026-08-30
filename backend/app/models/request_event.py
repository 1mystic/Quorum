import enum
from datetime import datetime
from sqlalchemy import ForeignKey, Enum, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class RequestEventKind(str, enum.Enum):
    """
    Mirrors `RequestEventKind` in `app/stats/streams/request_flow.py` exactly
    (docs/DATA_SPINE.md section 2). This is the ORM row shape; the stream atom
    is the frozen dataclass the vertical adapter reduces this row into. The two
    are kept as separate types on purpose (S2: no stream dataclass may carry a
    tenant_id, and this table does), so keep them in sync by hand rather than
    importing one from the other.
    """
    OPENED = "opened"
    ACKNOWLEDGED = "acknowledged"
    ASSIGNED = "assigned"
    REASSIGNED = "reassigned"
    STATUS_CHANGE = "status_change"
    COMMENT = "comment"
    PAUSED = "paused"
    RESUMED = "resumed"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    WITHDRAWN = "withdrawn"
    MERGED = "merged"
    REOPENED = "reopened"
    CLOSED = "closed"


class RequestEventLog(Base):
    """
    Card C.8. The request event/status-change log the `rwa_society` and
    `campus_club` stream adapters flagged as missing (TODOs in
    `app/verticals/adapters/base.py`): without it there is nowhere to record
    "assigned", "reassigned", "paused", "resumed", "escalated", "withdrawn",
    "merged" or "reopened", so `survival.competing_risks_cif` has nothing to
    estimate and `duration_active_hours` (needed by any vertical that declares
    `sla_clock="active"`, e.g. `campus_club`) is unavailable.

    This table is the append-only atom source for `docs/DATA_SPINE.md`'s
    `request_flow` stream. It is deliberately a log, not a mutation of `Request`
    in place: a reducer needs every state the request passed through, not just
    the last one, to build a `RequestSpell` and decide censoring (C1-C10). The
    denormalized `Request.status`/`terminal_at`/`outcome` columns are a read
    convenience kept in sync by the repository on every write here; they are
    never the source a stream adapter reduces.
    """
    __tablename__ = "request_events"
    __table_args__ = (
        Index("ix_request_events_request_at", "request_id", "at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"))
    kind: Mapped[RequestEventKind] = mapped_column(Enum(RequestEventKind))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    # Snapshot at this event. category/priority may legitimately change mid-life;
    # each change is its own row rather than an in-place update, per the same
    # append-only principle as the rest of the log.
    category: Mapped[str | None] = mapped_column()
    subcategory: Mapped[str | None] = mapped_column()
    priority: Mapped[str | None] = mapped_column()
    channel: Mapped[str | None] = mapped_column()
    location_ref: Mapped[str | None] = mapped_column()
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    # For kind == MERGED: the request this one survives into. Matches
    # RequestEvent.parent_ref in the stream atom.
    parent_request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))
    # RequestEvent.at_precision / at_upper: a bulk-imported or batch-synced
    # terminal timestamp is sometimes only known to fall in a bracket, never
    # imputed to a midpoint (rule C4).
    at_precision: Mapped[str] = mapped_column(default="exact", server_default="exact")
    at_upper: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    request: Mapped["Request"] = relationship(
        back_populates="events", foreign_keys=[request_id]
    )
    actor: Mapped["Member | None"] = relationship(foreign_keys=[actor_id])
    assignee: Mapped["Member | None"] = relationship(foreign_keys=[assignee_id])
