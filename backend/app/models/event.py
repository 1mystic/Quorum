import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class EventStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"))
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    venue: Mapped[str] = mapped_column()
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int | None] = mapped_column()
    image_url: Mapped[str | None] = mapped_column()
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # References users.id, not members.id: the actor is a TENANT_ADMIN, who
    # never gets a Member row (see UserService.signup).
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    group: Mapped["Group"] = relationship(back_populates="events")
    creator: Mapped["Member"] = relationship(back_populates="created_events")
    registrations: Mapped[list["EventRegistration"]] = relationship(back_populates="event")
    requests: Mapped[list["Request"]] = relationship(back_populates="event")
