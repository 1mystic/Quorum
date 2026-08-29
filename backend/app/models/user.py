import enum
from datetime import datetime
from sqlalchemy import ForeignKey, Enum, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class UserRole(str, enum.Enum):
    MEMBER = "MEMBER"
    TENANT_ADMIN = "TENANT_ADMIN"


class AuthProvider(str, enum.Enum):
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str | None] = mapped_column()
    full_name: Mapped[str] = mapped_column()
    profile_image_url: Mapped[str | None] = mapped_column()
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider), default=AuthProvider.LOCAL, server_default=text("'LOCAL'")
    )
    google_sub: Mapped[str | None] = mapped_column(unique=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow,
                                                 server_default=func.now())

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    member: Mapped["Member | None"] = relationship(back_populates="user", uselist=False)
    tenant_admin: Mapped["TenantAdmin | None"] = relationship(back_populates="user", uselist=False)





