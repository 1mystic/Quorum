import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class RequestCategory(str, enum.Enum):
    EVENT = "EVENT"
    GROUP = "GROUP"
    CERTIFICATE = "CERTIFICATE"
    TECHNICAL = "TECHNICAL"
    GENERAL = "GENERAL"


class RequestStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class Request(Base):
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
    category: Mapped[RequestCategory] = mapped_column(Enum(RequestCategory))
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus))
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    response_body: Mapped[str | None] = mapped_column(Text)
    responded_by: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    member: Mapped["Member"] = relationship(foreign_keys=[member_id],
                                              back_populates="requests")
    responder: Mapped["Member | None"] = relationship(foreign_keys=[responded_by],
                                                       back_populates="request_responses")
    group: Mapped["Group"] = relationship(back_populates="requests")
    event: Mapped["Event | None"] = relationship(back_populates="requests")
