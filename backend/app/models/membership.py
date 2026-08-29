import enum
from datetime import datetime
from sqlalchemy import ForeignKey, Enum, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class MembershipRole(str, enum.Enum):
    LEADER = "LEADER"
    MEMBER = "MEMBER"


class MembershipStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("member_id", "group_id", name="uq_membership_member_group"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    role: Mapped[MembershipRole] = mapped_column(Enum(MembershipRole))
    status: Mapped[MembershipStatus] = mapped_column(Enum(MembershipStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    member: Mapped["Member"] = relationship(back_populates="memberships")
    group: Mapped["Group"] = relationship(back_populates="memberships")
