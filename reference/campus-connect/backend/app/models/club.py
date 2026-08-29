import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class ClubType(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    UNOFFICIAL = "UNOFFICIAL"


class ClubStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"))
    club_head: Mapped[int] = mapped_column(ForeignKey("students.id"))
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column()
    type: Mapped[ClubType] = mapped_column(Enum(ClubType))
    status: Mapped[ClubStatus] = mapped_column(Enum(ClubStatus))
    image_url: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    college: Mapped["College"] = relationship(back_populates="clubs")
    head: Mapped["Student"] = relationship(back_populates="headed_clubs")
    links: Mapped[list["ClubLink"]] = relationship(back_populates="club")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="club")
    events: Mapped[list["Event"]] = relationship(back_populates="club")
    announcements: Mapped[list["Announcement"]] = relationship(back_populates="club")
    issues: Mapped[list["Issue"]] = relationship(back_populates="club")


class ClubLink(Base):
    __tablename__ = "club_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    club_id: Mapped[int] = mapped_column(ForeignKey("clubs.id"))
    label: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column()

    club: Mapped["Club"] = relationship(back_populates="links")
