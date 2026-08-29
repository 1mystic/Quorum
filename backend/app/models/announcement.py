import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class AnnouncementCategory(str, enum.Enum):
    GENERAL = "GENERAL"
    EVENT_UPDATE = "EVENT_UPDATE"
    RESOURCE = "RESOURCE"
    ACHIEVEMENT = "ACHIEVEMENT"
    URGENT = "URGENT"


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        # the member feed joins memberships -> announcements on group_id, newest first
        Index("ix_announcements_group_created", "group_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    title: Mapped[str] = mapped_column()
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[AnnouncementCategory] = mapped_column(Enum(AnnouncementCategory))
    is_pinned: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    group: Mapped["Group"] = relationship(back_populates="announcements")
    author: Mapped["Member"] = relationship(back_populates="announcements")
