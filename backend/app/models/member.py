from datetime import datetime
from sqlalchemy import Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow




class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    bio: Mapped[str | None] = mapped_column(Text)
    interests: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    roll_no: Mapped[str | None] = mapped_column()
    branch: Mapped[str | None] = mapped_column()
    year: Mapped[int | None] = mapped_column()
    announcements_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="member")
    headed_groups: Mapped[list["Group"]] = relationship(back_populates="head")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="member")
    created_events: Mapped[list["Event"]] = relationship(back_populates="creator")
    event_registrations: Mapped[list["EventRegistration"]] = relationship(back_populates="member")
    announcements: Mapped[list["Announcement"]] = relationship(back_populates="author")
    requests: Mapped[list["Request"]] = relationship(back_populates="member",
                                                 foreign_keys="Request.member_id")
    request_responses: Mapped[list["Request"]] = relationship(back_populates="responder",
                                                          foreign_keys="Request.responded_by")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="member")