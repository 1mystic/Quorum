from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Due, DueStatus, Payment, Receipt, Contribution, Expense, LedgerStatus
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
        now = datetime.now(timezone.utc)
        payment.verified_at = now
        payment.verified_by_id = verified_by_id
        payment.status = LedgerStatus.SETTLED
        payment.settled_at = now
        if payment.due_id is not None:
            due = await self.db.get(Due, payment.due_id)
            if due is not None and due.tenant_id == self.tenant_id:
                settled = await self._settled_total(due.id)
                due.status = DueStatus.PAID if settled >= due.amount_minor else DueStatus.PARTIAL
        return payment

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
