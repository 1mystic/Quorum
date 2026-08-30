from app.repository import LedgerRepository, MemberRepository, UserRepository
from app.schemas import (
    CreateDueRequest, DueItem, RecordPaymentRequest, PaymentItem, ReceiptItem,
    AddContributionRequest, ContributionItem, AddExpenseRequest, ExpenseItem,
    LedgerActionResponse,
)
from app.exceptions import (
    DueNotFoundError, PaymentNotFoundError, PaymentAlreadySettledError,
    ReceiptAlreadyIssuedError, MemberNotFoundError, TenantNotFoundError,
    LedgerCategoryInvalidError,
)
from app.models import LedgerStatus
from app.core.messages import LedgerMessages
from app.verticals.adapters import get_adapter


class LedgerService:
    """
    Card C.10 (ledger domain). Same shape as `RequestService` (card C.8): a
    thin layer that validates the tenant's declared vocabulary and role, and
    hands everything else to `LedgerRepository`. No arithmetic on a duration
    or a lag happens here - that is the `ledger` stream reducer's job,
    downstream and pure.
    """

    def __init__(self, ledger_repo: LedgerRepository, member_repo: MemberRepository,
                 user_repo: UserRepository, tenant_repo):
        self.ledger_repo = ledger_repo
        self.member_repo = member_repo
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo

    async def raise_due(self, payload: dict, data: CreateDueRequest) -> DueItem:
        tenant_id = await self._tenant_id(payload)
        await self._validate_category(tenant_id, data.category)
        member = await self.member_repo.get_by_id(data.member_id)
        if not member or member.tenant_id != tenant_id:
            raise MemberNotFoundError()
        due = await self.ledger_repo.create_due(
            member_id=data.member_id, category=data.category, amount_minor=data.amount_minor,
            due_at=data.due_at, group_id=data.group_id, subcategory=data.subcategory,
            currency=data.currency,
        )
        return self._due_item(due)

    async def record_payment(self, payload: dict, data: RecordPaymentRequest) -> PaymentItem:
        tenant_id = await self._tenant_id(payload)
        await self._validate_category(tenant_id, data.category)
        if data.due_id is not None:
            due = await self.ledger_repo.get_due(data.due_id)
            if not due:
                raise DueNotFoundError()
        payment = await self.ledger_repo.record_payment(
            amount_minor=data.amount_minor, category=data.category, subcategory=data.subcategory,
            instrument=data.instrument, at=data.at, due_id=data.due_id, member_id=data.member_id,
            campaign_ref=data.campaign_ref, currency=data.currency,
        )
        return self._payment_item(payment)

    async def verify_payment(self, payload: dict, payment_id: int) -> PaymentItem:
        verifier = await self._get_member(payload)
        payment = await self.ledger_repo.get_payment(payment_id)
        if not payment:
            raise PaymentNotFoundError()
        if payment.status == LedgerStatus.SETTLED:
            raise PaymentAlreadySettledError()
        payment = await self.ledger_repo.verify_payment(payment, verifier.id)
        return self._payment_item(payment)

    async def issue_receipt(self, payload: dict, payment_id: int) -> ReceiptItem:
        issuer = await self._get_member(payload)
        payment = await self.ledger_repo.get_payment(payment_id)
        if not payment:
            raise PaymentNotFoundError()
        if payment.receipt is not None:
            raise ReceiptAlreadyIssuedError()
        receipt = await self.ledger_repo.issue_receipt(payment, issuer.id)
        return ReceiptItem(id=receipt.id, payment_id=receipt.payment_id,
                            issued_at=receipt.issued_at, collected_at=receipt.collected_at)

    async def collect_receipt(self, payload: dict, payment_id: int) -> ReceiptItem:
        payment = await self.ledger_repo.get_payment(payment_id)
        if not payment or payment.receipt is None:
            raise PaymentNotFoundError()
        receipt = await self.ledger_repo.collect_receipt(payment.receipt)
        return ReceiptItem(id=receipt.id, payment_id=receipt.payment_id,
                            issued_at=receipt.issued_at, collected_at=receipt.collected_at)

    async def add_contribution(self, payload: dict, data: AddContributionRequest) -> ContributionItem:
        tenant_id = await self._tenant_id(payload)
        await self._validate_category(tenant_id, data.category)
        contribution = await self.ledger_repo.add_contribution(
            kind=data.kind, category=data.category, at=data.at, member_id=data.member_id,
            campaign_ref=data.campaign_ref, amount_minor=data.amount_minor, currency=data.currency,
            description=data.description,
        )
        return ContributionItem(id=contribution.id, member_id=contribution.member_id,
                                 kind=contribution.kind, category=contribution.category,
                                 amount_minor=contribution.amount_minor, at=contribution.at)

    async def add_expense(self, payload: dict, data: AddExpenseRequest) -> ExpenseItem:
        tenant_id = await self._tenant_id(payload)
        await self._validate_category(tenant_id, data.category)
        expense = await self.ledger_repo.add_expense(
            category=data.category, amount_minor=data.amount_minor, instrument=data.instrument,
            at=data.at, counterparty_ref=data.counterparty_ref, campaign_ref=data.campaign_ref,
            subcategory=data.subcategory, currency=data.currency,
        )
        return self._expense_item(expense)

    async def my_dues(self, payload: dict) -> list[DueItem]:
        member = await self._get_member(payload)
        dues = await self.ledger_repo.list_dues_for_member(member.id)
        return [self._due_item(due) for due in dues]

    # ---- helpers --------------------------------------------------------

    async def _validate_category(self, tenant_id: int, category: str) -> None:
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()
        adapter = get_adapter(tenant.vertical)
        if category.strip().lower() not in adapter.ledger_categories:
            raise LedgerCategoryInvalidError(
                f"'{category}' is not in {tenant.vertical}'s declared ledger categories"
            )

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member

    async def _tenant_id(self, payload: dict) -> int:
        tenant_id = await self.user_repo.get_tenant_id(int(payload.get("sub")))
        if not tenant_id:
            raise TenantNotFoundError()
        return tenant_id

    @staticmethod
    def _due_item(due) -> DueItem:
        return DueItem(id=due.id, member_id=due.member_id, category=due.category,
                        subcategory=due.subcategory, amount_minor=due.amount_minor,
                        currency=due.currency, issued_at=due.issued_at, due_at=due.due_at,
                        status=due.status)

    @staticmethod
    def _payment_item(payment) -> PaymentItem:
        return PaymentItem(id=payment.id, due_id=payment.due_id, member_id=payment.member_id,
                            category=payment.category, amount_minor=payment.amount_minor,
                            currency=payment.currency, instrument=payment.instrument,
                            status=payment.status, at=payment.at, verified_at=payment.verified_at,
                            settled_at=payment.settled_at)

    @staticmethod
    def _expense_item(expense) -> ExpenseItem:
        return ExpenseItem(id=expense.id, category=expense.category,
                            subcategory=expense.subcategory,
                            counterparty_ref=expense.counterparty_ref,
                            amount_minor=expense.amount_minor, currency=expense.currency,
                            status=expense.status, at=expense.at)
