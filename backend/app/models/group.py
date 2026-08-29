import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class GroupType(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    UNOFFICIAL = "UNOFFICIAL"


class GroupStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    group_head: Mapped[int] = mapped_column(ForeignKey("members.id"))
    name: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column()
    type: Mapped[GroupType] = mapped_column(Enum(GroupType))
    status: Mapped[GroupStatus] = mapped_column(Enum(GroupStatus))
    image_url: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    tenant: Mapped["Tenant"] = relationship(back_populates="groups")
    head: Mapped["Member"] = relationship(back_populates="headed_groups")
    links: Mapped[list["GroupLink"]] = relationship(back_populates="group")
    memberships: Mapped[list["Membership"]] = relationship(back_populates="group")
    events: Mapped[list["Event"]] = relationship(back_populates="group")
    announcements: Mapped[list["Announcement"]] = relationship(back_populates="group")
    requests: Mapped[list["Request"]] = relationship(back_populates="group")


class GroupLink(Base):
    __tablename__ = "group_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    label: Mapped[str] = mapped_column()
    url: Mapped[str] = mapped_column()

    group: Mapped["Group"] = relationship(back_populates="links")
