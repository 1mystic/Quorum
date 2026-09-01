import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class RequestStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    # Card C.8: the two competing-risks terminals docs/DATA_SPINE.md's request_flow
    # stream needs (rule C5). Neither one is "resolved" and cause-specific
    # Kaplan-Meier that treats them as neutral censoring overstates eventual
    # resolution, which is exactly what survival.competing_risks_cif exists to
    # correct once these terminals are observable.
    ESCALATED = "ESCALATED"
    WITHDRAWN = "WITHDRAWN"
    # A request merged into another (rule C7). Request.merged_into_id names the
    # survivor; this request is excluded from demand counts, not double-counted.
    MERGED = "MERGED"


class Request(Base):
    """
    Card C.8. `category`/`priority`/`channel`/`location_ref`/`subcategory` are
    plain, per-tenant-vertical-vocabulary strings, not a fixed enum: the ported
    Campus Connect `RequestCategory` enum did not generalize past the campus
    vertical (docs/VERTICALS.md rule V3: the column is always `request.category`,
    but a vertical is free to declare its own values). The vocabulary is
    validated at the service layer against the tenant's vertical adapter
    (`app.verticals.adapters.get_adapter(tenant.vertical).request_categories`),
    not by a database constraint, so a seventh vertical does not need a schema
    migration to add a category.

    `terminal_at` / `outcome` are a denormalized convenience for read paths that
    need "is this request over, and how" without joining `request_events`; the
    event log (`RequestEventLog`, `app/models/request_event.py`) remains the
    source of truth a stream adapter reduces into a `RequestSpell`, per
    docs/DATA_SPINE.md section 2. Nothing here ever computes a duration or a
    censoring kind - that is the reducer's job, downstream and pure.
    """
    __tablename__ = "requests"
    __table_args__ = (
        # leader queue: all requests of the groups a member leads
        Index("ix_requests_group_status", "group_id", "status"),
        # a member's own requests, newest first
        Index("ix_requests_member_created", "member_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    category: Mapped[str] = mapped_column()
    subcategory: Mapped[str | None] = mapped_column()
    priority: Mapped[str | None] = mapped_column()
    channel: Mapped[str | None] = mapped_column()
    location_ref: Mapped[str | None] = mapped_column()
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus))
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    response_body: Mapped[str | None] = mapped_column(Text)
    responded_by: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set together whenever a terminal event lands (resolved/escalated/withdrawn/merged).
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column()
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    member: Mapped["Member"] = relationship(foreign_keys=[member_id],
                                              back_populates="requests")
    responder: Mapped["Member | None"] = relationship(foreign_keys=[responded_by],
                                                       back_populates="request_responses")
    group: Mapped["Group"] = relationship(back_populates="requests")
    event: Mapped["Event | None"] = relationship(back_populates="requests")
    merged_into: Mapped["Request | None"] = relationship(remote_side=[id])
    events: Mapped[list["RequestEventLog"]] = relationship(
        back_populates="request", order_by="RequestEventLog.at", cascade="all, delete-orphan",
        foreign_keys="RequestEventLog.request_id",
    )
