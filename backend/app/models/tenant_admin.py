from app.core import Base, utcnow
from datetime import datetime
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import ForeignKey, DateTime, func


class TenantAdmin(Base):
    __tablename__ = "tenant_admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable: a TENANT_ADMIN signs up before a tenant exists and onboards
    # one afterward (app/services/tenant.py). Matches User.tenant_id.
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="tenant_admin")