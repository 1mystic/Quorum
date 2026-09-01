"""
Card C.10 (ledger half). docs/DATA_SPINE.md section 3, docs/GLOSSARY.md's new
entities table: Due, Payment, Receipt, Contribution, Expense -> the `ledger`
stream.

Grounded in the RWA interview evidence in `RWA_Master_Context.md`: a bank
transfer, a screenshot to WhatsApp, a treasurer manually verifying it, a
physical register, and a receipt that frequently never gets collected. Five
tables so that path can be measured rather than assumed away:

- `Due` is a receivable raised against a member (a maintenance charge). It is
  right-censored exactly like an open `Request` if it is not settled by the
  observation window's end (spine rule L1) - the reducer, not this table,
  decides that.
- `Payment` is money actually moving in, optionally settling a `Due`, carrying
  the verification lag (`verified_at`) the interview flagged as the real
  bottleneck.
- `Receipt` is issued against a `Payment` and separately carries when it was
  collected, which is the other interview-grounded headline statistic (the
  receipt-collection gap).
- `Contribution` is inflow that is not a due settlement: a one-off donation, a
  festival-fund gift, an in-kind or volunteer-hours pledge with an estimated
  value.
- `Expense` is money moving out: vendor payments, wages, repairs.

None of these tables compute a duration, a lag or a censoring kind. That is
`app/stats/streams/reduce.py`'s job, downstream and pure, once it reduces the
`LedgerEntry` atoms the adapter builds from these rows.
"""
import enum
from datetime import datetime
from sqlalchemy import Text, ForeignKey, Enum, DateTime, Index, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core import Base, utcnow


class DueStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    WAIVED = "WAIVED"
    WRITTEN_OFF = "WRITTEN_OFF"


class LedgerInstrument(str, enum.Enum):
    UPI = "upi"
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    CHEQUE = "cheque"
    CARD = "card"
    IN_KIND = "in_kind"
    ADJUSTMENT = "adjustment"


class LedgerStatus(str, enum.Enum):
    EXPECTED = "expected"
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"
    REVERSED = "reversed"
    WRITTEN_OFF = "written_off"


class ContributionKind(str, enum.Enum):
    CASH = "cash"
    VOLUNTEER_HOURS = "volunteer_hours"
    IN_KIND = "in_kind"


class Due(Base):
    """
    A receivable raised against a member. Settled by one or more Payments.

    `version` is SQLAlchemy's optimistic-locking column
    (`__mapper_args__["version_id_col"]`): every UPDATE through the ORM
    carries a `WHERE version = <the value this session read>` and bumps it,
    so a writer that skipped the explicit `SELECT ... FOR UPDATE` row lock
    (see `LedgerRepository.get_due_for_update`) still fails loudly with a
    `StaleDataError` on a lost update rather than silently overwriting a
    concurrent change. Money-moving tables only (`Due`, `Payment`), not every
    model - this is deliberately not a house style.
    """
    __tablename__ = "dues"
    __table_args__ = (
        Index("ix_dues_member_status", "member_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    category: Mapped[str] = mapped_column()
    subcategory: Mapped[str | None] = mapped_column()
    amount_minor: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(default="INR", server_default="INR")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[DueStatus] = mapped_column(Enum(DueStatus), default=DueStatus.OPEN)
    reminders_sent: Mapped[int] = mapped_column(default=0, server_default="0")
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    member: Mapped["Member"] = relationship(foreign_keys=[member_id])
    payments: Mapped[list["Payment"]] = relationship(back_populates="due")

    __mapper_args__ = {"version_id_col": version}


class Payment(Base):
    """
    Money moving in. Usually settles a Due; a standalone payment (`due_id`
    None) covers one-off society collections that were never billed as a due.

    `verified_at` is the WhatsApp-screenshot-to-treasurer-confirmation lag
    from the interview evidence; `reconciled` is whether it was matched
    against a bank statement.
    """
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_member_at", "member_id", "at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    due_id: Mapped[int | None] = mapped_column(ForeignKey("dues.id"))
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    campaign_ref: Mapped[str | None] = mapped_column()
    category: Mapped[str] = mapped_column()
    subcategory: Mapped[str | None] = mapped_column()
    amount_minor: Mapped[int] = mapped_column()  # always positive; direction is inflow
    currency: Mapped[str] = mapped_column(default="INR", server_default="INR")
    instrument: Mapped[LedgerInstrument] = mapped_column(Enum(LedgerInstrument))
    status: Mapped[LedgerStatus] = mapped_column(Enum(LedgerStatus), default=LedgerStatus.PENDING)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))          # value date
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Optimistic-locking column, same reasoning as Due.version above.
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    due: Mapped["Due | None"] = relationship(back_populates="payments")
    member: Mapped["Member | None"] = relationship(foreign_keys=[member_id])
    verified_by: Mapped["Member | None"] = relationship(foreign_keys=[verified_by_id])
    reversal_of: Mapped["Payment | None"] = relationship(remote_side=[id])
    receipt: Mapped["Receipt | None"] = relationship(back_populates="payment", uselist=False)

    __mapper_args__ = {"version_id_col": version}


class Receipt(Base):
    """
    Issued against a Payment. `collected_at` staying null is the
    receipt-adoption gap the interview evidence names directly.
    """
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), unique=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    payment: Mapped["Payment"] = relationship(back_populates="receipt")
    issued_by: Mapped["Member | None"] = relationship(foreign_keys=[issued_by_id])


class Contribution(Base):
    """Inflow that is not a due settlement: donations, festival-fund gifts, in-kind/volunteer value."""
    __tablename__ = "contributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    campaign_ref: Mapped[str | None] = mapped_column()
    kind: Mapped[ContributionKind] = mapped_column(Enum(ContributionKind))
    category: Mapped[str] = mapped_column()
    amount_minor: Mapped[int] = mapped_column(default=0, server_default="0")
    currency: Mapped[str] = mapped_column(default="INR", server_default="INR")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    member: Mapped["Member | None"] = relationship(foreign_keys=[member_id])


class Expense(Base):
    """Money moving out: vendor payments, wages, repairs, capex."""
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    campaign_ref: Mapped[str | None] = mapped_column()
    category: Mapped[str] = mapped_column()
    subcategory: Mapped[str | None] = mapped_column()
    counterparty_ref: Mapped[str | None] = mapped_column()   # vendor/contractor, pseudonymous
    amount_minor: Mapped[int] = mapped_column()               # always positive; direction is outflow
    currency: Mapped[str] = mapped_column(default="INR", server_default="INR")
    instrument: Mapped[LedgerInstrument] = mapped_column(Enum(LedgerInstrument))
    status: Mapped[LedgerStatus] = mapped_column(Enum(LedgerStatus), default=LedgerStatus.PENDING)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"))
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    approved_by: Mapped["Member | None"] = relationship(foreign_keys=[approved_by_id])
    reversal_of: Mapped["Expense | None"] = relationship(remote_side=[id])
