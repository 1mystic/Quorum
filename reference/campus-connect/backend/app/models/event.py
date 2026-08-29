import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class EventStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("students.id"))
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    venue: Mapped[str] = mapped_column()
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int | None] = mapped_column()
    image_url: Mapped[str | None] = mapped_column()
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    club: Mapped["Club"] = relationship(back_populates="events")
    creator: Mapped["Student"] = relationship(back_populates="created_events")
    registrations: Mapped[list["EventRegistration"]] = relationship(back_populates="event")
    issues: Mapped[list["Issue"]] = relationship(back_populates="event")
