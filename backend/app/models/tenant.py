"""
The tenant is the unit of data isolation: one community using the platform.

`vertical` selects the manifest loaded by app.verticals (labels, default packs,
categories, roles, auth mode). `enabled_packs` is the subset of Insight Packs the
tenant has actually turned on, a strict subset of what its vertical allows.
`settings` is per-tenant free-form config (timezone lives here, not in a global
env var - see COLLEGE_TIMEZONE -> TENANT_TIMEZONE in docs/GLOSSARY.md).

Campus Connect's `College.email_suffix` (a hard membership rule enforced at
signup) does not generalize past the campus vertical, so it is not a column
here. Verticals that want it declare it as an optional membership rule in
their manifest instead.
"""
from datetime import datetime
from sqlalchemy import Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    slug: Mapped[str] = mapped_column(unique=True)
    vertical: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text)
    enabled_packs: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    timezone: Mapped[str] = mapped_column(default="UTC", server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    groups: Mapped[list["Group"]] = relationship(back_populates="tenant")