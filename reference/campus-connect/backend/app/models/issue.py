import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class IssueCategory(str, enum.Enum):
    EVENT = "EVENT"
    CLUB = "CLUB"
    CERTIFICATE = "CERTIFICATE"
    TECHNICAL = "TECHNICAL"
    GENERAL = "GENERAL"


class IssueStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        # leader queue: all issues of the clubs a student leads
        Index("ix_issues_club_status", "club_id", "status"),
        # a student's own issues, newest first
        Index("ix_issues_student_created", "student_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    category: Mapped[IssueCategory] = mapped_column(Enum(IssueCategory))
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus))
    title: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    response_body: Mapped[str | None] = mapped_column(Text)
    responded_by: Mapped[int | None] = mapped_column(ForeignKey("students.id"))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    student: Mapped["Student"] = relationship(foreign_keys=[student_id],
                                              back_populates="issues")
    responder: Mapped["Student | None"] = relationship(foreign_keys=[responded_by],
                                                       back_populates="issue_responses")
    club: Mapped["Club"] = relationship(back_populates="issues")
    event: Mapped["Event | None"] = relationship(back_populates="issues")
