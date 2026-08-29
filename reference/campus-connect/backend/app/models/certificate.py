from datetime import datetime
from sqlalchemy import ForeignKey, Enum, DateTime, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow
from app.models.event_registration import RegistrationResult


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("event_registrations.id"), unique=True)
    serial: Mapped[str] = mapped_column(unique=True, index=True)
    result: Mapped[RegistrationResult] = mapped_column(Enum(RegistrationResult))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                default=utcnow,
                                                server_default=func.now())
    # Set only when S3 is unavailable (no real AWS credentials configured yet) - the PDF
    # is generated locally same as always, just persisted in Postgres instead of S3 until
    # real credentials are supplied. Null once/if a certificate uploads to S3 normally.
    pdf_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    registration: Mapped["EventRegistration"] = relationship(back_populates="certificate")
