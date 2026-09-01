from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from app.models import (
    Due, DueStatus, Payment, Receipt, Contribution, Expense, LedgerStatus, IdempotencyRecord,
)
from app.repository.base import TenantScopedRepository


class LedgerRepository(TenantScopedRepository):
    """
    Tenant-scoped, same pattern as `RequestRepository` (card C.8): every query
    below adds `tenant_id == self.tenant_id`, and every write sets it itself
    rather than trusting a caller-supplied value.

    `stream_*` at the bottom is the whole of what this class hands the
    `ledger` stream adapter: rows, tenant-scoped, no arithmetic. "You fetch
    and cache; they compute."
    """

    # ---- writes -----------------------------------------------------------

    async def create_due(self, member_id: int, category: str, amount_minor: int,
                          due_at: datetime, group_id: int | None = None,
                          subcategory: str | None = None, currency: str = "INR",
                          issued_at: datetime | None = None) -> Due:
        due = Due(
            tenant_id=self.tenant_id,
            member_id=member_id,
            group_id=group_id,
            category=category,
            subcategory=subcategory,
            amount_minor=amount_minor,
            currency=currency,
            issued_at=issued_at or datetime.now(timezone.utc),
            due_at=due_at,
            status=DueStatus.OPEN,
        )
        self.db.add(due)
        await self.db.flush()
        return due

    async def record_payment(self, *, amount_minor: int, category: str, instrument,
                              at: datetime, due_id: int | None = None,
                              member_id: int | None = None, group_id: int | None = None,
                              campaign_ref: str | None = None, subcategory: str | None = None,
                              currency: str = "INR") -> Payment:
        payment = Payment(
            tenant_id=self.tenant_id,
            due_id=due_id,
            member_id=member_id,
            group_id=group_id,
            campaign_ref=campaign_ref,
            category=category,
            subcategory=subcategory,
            amount_minor=amount_minor,
            currency=currency,
            instrument=instrument,
            status=LedgerStatus.PENDING,
            at=at,
        )
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def verify_payment(self, payment: Payment, verified_by_id: int) -> Payment:
        """
        Caller must have already locked `payment` via `get_payment_for_update`
        (see `LedgerService.verify_payment`): this method only mutates, it
        does not itself acquire the lock, so the check-then-act window
        (status still PENDING -> flip to SETTLED) is covered by the caller's
        transaction holding the row lock across both.
        """
        now = datetime.now(timezone.utc)
        payment.verified_at = now
        payment.verified_by_id = verified_by_id
        payment.status = LedgerStatus.SETTLED
        payment.settled_at = now
        if payment.due_id is not None:
            due = await self.get_due_for_update(payment.due_id)
            if due is not None:
                settled = await self._settled_total(due.id)
                due.status = DueStatus.PAID if settled >= due.amount_minor else DueStatus.PARTIAL
        return payment

    async def settle_due(self, due: Due, status: DueStatus) -> Due:
        """
        Direct settlement (paid off-book, waived, written off), the same
        write path `verify_payment` uses for the due side of a payment.
        Caller must have already locked `due` via `get_due_for_update`.
        """
        due.status = status
        return due

    async def _settled_total(self, due_id: int) -> int:
        result = await self.db.execute(
            self.scope(select(Payment), Payment)
            .where(Payment.due_id == due_id, Payment.status == LedgerStatus.SETTLED)
        )
        return sum(p.amount_minor for p in result.scalars().all())

    async def issue_receipt(self, payment: Payment, issued_by_id: int | None = None) -> Receipt:
        receipt = Receipt(
            tenant_id=self.tenant_id,
            payment_id=payment.id,
            issued_at=datetime.now(timezone.utc),
            issued_by_id=issued_by_id,
        )
        self.db.add(receipt)
        await self.db.flush()
        return receipt

    async def collect_receipt(self, receipt: Receipt) -> Receipt:
        receipt.collected_at = datetime.now(timezone.utc)
        return receipt

    async def add_contribution(self, *, kind, category: str, at: datetime,
                                member_id: int | None = None, group_id: int | None = None,
                                campaign_ref: str | None = None, amount_minor: int = 0,
                                currency: str = "INR", description: str | None = None) -> Contribution:
        contribution = Contribution(
            tenant_id=self.tenant_id,
            member_id=member_id,
            group_id=group_id,
            campaign_ref=campaign_ref,
            kind=kind,
            category=category,
            amount_minor=amount_minor,
            currency=currency,
            at=at,
            description=description,
        )
        self.db.add(contribution)
        await self.db.flush()
        return contribution

    async def add_expense(self, *, category: str, amount_minor: int, instrument, at: datetime,
                           counterparty_ref: str | None = None, group_id: int | None = None,
                           campaign_ref: str | None = None, subcategory: str | None = None,
                           currency: str = "INR", approved_by_id: int | None = None) -> Expense:
        expense = Expense(
            tenant_id=self.tenant_id,
            group_id=group_id,
            campaign_ref=campaign_ref,
            category=category,
            subcategory=subcategory,
            counterparty_ref=counterparty_ref,
            amount_minor=amount_minor,
            currency=currency,
            instrument=instrument,
            status=LedgerStatus.SETTLED,
            at=at,
            settled_at=at,
            approved_by_id=approved_by_id,
        )
        self.db.add(expense)
        await self.db.flush()
        return expense

    # ---- reads --------------------------------------------------------

    async def get_due(self, due_id: int) -> Due | None:
        result = await self.db.execute(
            self.scope(select(Due), Due).where(Due.id == due_id)
        )
        return result.scalar_one_or_none()

    async def get_payment(self, payment_id: int) -> Payment | None:
        result = await self.db.execute(
            self.scope(select(Payment), Payment)
            .where(Payment.id == payment_id)
            .options(selectinload(Payment.receipt))
        )
        return result.scalar_one_or_none()

    # ---- row locking ----------------------------------------------------
    #
    # Any method above that reads a Due/Payment row with intent to mutate it
    # (verify a payment, settle a due) must go through one of these instead
    # of the plain reads above: `SELECT ... FOR UPDATE` inside the caller's
    # transaction, so a concurrent call for the same row blocks here rather
    # than racing, and re-reads the committed row once the lock is released
    # instead of working from a stale copy. `Due.version`/`Payment.version`
    # (SQLAlchemy's `version_id_col`) are the second layer: a code path that
    # still forgets the lock fails loudly on a lost update instead of
    # silently overwriting one.

    async def get_payment_for_update(self, payment_id: int) -> Payment | None:
        result = await self.db.execute(
            self.scope(select(Payment), Payment)
            .where(Payment.id == payment_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_due_for_update(self, due_id: int) -> Due | None:
        result = await self.db.execute(
            self.scope(select(Due), Due).where(Due.id == due_id).with_for_update()
        )
        return result.scalar_one_or_none()

    # ---- idempotency ----------------------------------------------------

    async def get_idempotent_response(self, scope: str, key: str) -> dict | None:
        result = await self.db.execute(
            self.scope(select(IdempotencyRecord), IdempotencyRecord)
            .where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key)
        )
        record = result.scalar_one_or_none()
        return record.response if record is not None else None

    async def store_idempotent_response(self, scope: str, key: str, response: dict) -> None:
        """
        Written as an upsert-and-ignore-conflict: two concurrent first calls
        with the same key can both reach this after doing the real work (the
        row lock above only protects the Due/Payment row, not this table),
        and the unique constraint on (tenant_id, scope, key) is the backstop
        that keeps only one recorded response rather than raising past the
        caller, who already has a perfectly good result to return.
        """
        stmt = pg_insert(IdempotencyRecord).values(
            tenant_id=self.tenant_id, scope=scope, key=key, response=response,
        ).on_conflict_do_nothing(
            index_elements=["tenant_id", "scope", "key"]
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def list_dues_for_member(self, member_id: int) -> list[Due]:
        result = await self.db.execute(
            self.scope(select(Due), Due)
            .where(Due.member_id == member_id)
            .order_by(Due.due_at.desc())
        )
        return list(result.scalars().all())

    # ---- stream fetch -------------------------------------------------
    #
    # "You fetch and cache; they compute." No arithmetic happens here: every
    # row opened before window_end comes back untouched, exactly as
    # `RequestRepository.stream_requests` does for `request_flow` (rule C1's
    # ledger analogue is spine rule L1 - an unsettled Due is right-censored,
    # never dropped).

    async def stream_dues(self, window_end: datetime) -> list[Due]:
        result = await self.db.execute(
            self.scope(select(Due), Due)
            .where(Due.issued_at < window_end)
            .options(selectinload(Due.payments).selectinload(Payment.receipt))
        )
        return list(result.scalars().unique().all())

    async def stream_payments(self, window_end: datetime) -> list[Payment]:
        result = await self.db.execute(
            self.scope(select(Payment), Payment)
            .where(Payment.at < window_end, Payment.due_id.is_(None))
            .options(selectinload(Payment.receipt))
        )
        return list(result.scalars().unique().all())

    async def stream_contributions(self, window_end: datetime) -> list[Contribution]:
        result = await self.db.execute(
            self.scope(select(Contribution), Contribution)
            .where(Contribution.at < window_end)
        )
        return list(result.scalars().all())

    async def stream_expenses(self, window_end: datetime) -> list[Expense]:
        result = await self.db.execute(
            self.scope(select(Expense), Expense)
            .where(Expense.at < window_end)
        )
        return list(result.scalars().all())
