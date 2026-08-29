from datetime import datetime
from sqlalchemy import Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow




class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
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

    user: Mapped["User"] = relationship(back_populates="student")
    headed_clubs: Mapped[list["Club"]] = relationship(back_populates="head")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="student")
    created_events: Mapped[list["Event"]] = relationship(back_populates="creator")
    event_registrations: Mapped[list["EventRegistration"]] = relationship(back_populates="student")
    announcements: Mapped[list["Announcement"]] = relationship(back_populates="author")
    issues: Mapped[list["Issue"]] = relationship(back_populates="student",
                                                 foreign_keys="Issue.student_id")
    issue_responses: Mapped[list["Issue"]] = relationship(back_populates="responder",
                                                          foreign_keys="Issue.responded_by")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="student")