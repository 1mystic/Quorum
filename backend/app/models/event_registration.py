import enum
from datetime import datetime
from sqlalchemy import ForeignKey, Enum, DateTime, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class RegistrationResult(str, enum.Enum):
    REGISTRANT = "REGISTRANT"
    PARTICIPANT = "PARTICIPANT"
    RUNNER_UP = "RUNNER_UP"
    WINNER = "WINNER"


class EventRegistration(Base):
    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "member_id", name="uq_event_registration_event_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    checked_in: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[RegistrationResult] = mapped_column(Enum(RegistrationResult))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    event: Mapped["Event"] = relationship(back_populates="registrations")
    member: Mapped["Member"] = relationship(back_populates="event_registrations")
    certificate: Mapped["Certificate | None"] = relationship(back_populates="registration")
