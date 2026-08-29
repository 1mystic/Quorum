import enum
from datetime import datetime
from sqlalchemy import ForeignKey, Enum, DateTime, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class NotificationType(str, enum.Enum):
    JOIN_APPROVED = "JOIN_APPROVED"
    JOIN_REJECTED = "JOIN_REJECTED"
    REGISTRATION_CONFIRMED = "REGISTRATION_CONFIRMED"
    RESULT_POSTED = "RESULT_POSTED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # the badge query, polled every ~60s per signed-in member
        Index("ix_notifications_member_unread", "member_id", "is_read"),
        # the bell list, newest first
        Index("ix_notifications_member_created", "member_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    message: Mapped[str] = mapped_column()
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    is_read: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    member: Mapped["Member"] = relationship(back_populates="notifications")
