"""
Idempotency for the money-moving endpoints (Part 2 of the ledger concurrency
card): payment verification and due settlement accept a client-supplied
`Idempotency-Key` header, and a repeated call with the same key returns the
original stored result rather than processing twice. One small table rather
than a column on `Payment`/`Due`, since the same mechanism covers more than
one endpoint and a due settled without a payment has nowhere on `Payment` to
carry it anyway.

This is deliberately separate from the row lock and the optimistic-locking
`version` column: the lock/version pair stop a genuine race between two
different callers; idempotency stops the same caller's retried request (after
a timeout or a dropped response) from being treated as a second, distinct
request.
"""
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base, utcnow


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scope", "key", name="uq_idempotency_tenant_scope_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    # A short label for the operation this key was scoped to
    # ("ledger.verify_payment", "ledger.settle_due", ...), so the same raw
    # key string sent to two different endpoints does not collide.
    scope: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(200))
    # The exact response body the first call produced, replayed verbatim on
    # a repeat rather than recomputed.
    response: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())
