from fastapi import APIRouter, Depends, Header, Security

from app.schemas import (
    CreateDueRequest, DueItem, RecordPaymentRequest, PaymentItem, ReceiptItem,
    AddContributionRequest, ContributionItem, AddExpenseRequest, ExpenseItem,
    SettleDueRequest,
)
from app.services import LedgerService
from app.core.di import get_ledger_service, get_user_info

ledger_router = APIRouter(prefix="/ledger", tags=["Ledger"])

# Every route below stays MEMBER-only. raise_due/record_payment/add_contribution/
# add_expense are treasurer-style actions done by a MEMBER with the right
# standing in this domain, not a TENANT_ADMIN action; verify_payment/settle_due/
# issue_receipt/collect_receipt call LedgerService._get_member for the actor,
# and a TENANT_ADMIN never has a Member row (see app/models/decision.py's
# comment), so widening those would trade a 403 for a MemberNotFoundError
# rather than granting real access. my_dues is self-scoped (dues owed by the
# caller) and there is no tenant-wide "all dues"/"all payments" oversight
# endpoint yet to widen onto; adding one is a feature, not an auth fix.
@ledger_router.post("/dues", response_model=DueItem)
async def raise_due(
    data: CreateDueRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.raise_due(payload, data)


@ledger_router.get("/dues/me", response_model=list[DueItem])
async def my_dues(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.my_dues(payload)


@ledger_router.post("/payments", response_model=PaymentItem)
async def record_payment(
    data: RecordPaymentRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.record_payment(payload, data)


@ledger_router.patch("/payments/{payment_id}/verify", response_model=PaymentItem,
                     description="Row-locked and idempotent: a repeated call with the same "
                                 "Idempotency-Key header returns the original result rather "
                                 "than processing twice.")
async def verify_payment(
    payment_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    return await service.verify_payment(payload, payment_id, idempotency_key)


@ledger_router.patch("/dues/{due_id}/settle", response_model=DueItem,
                     description="Direct settlement (paid off-book, waived, written off), "
                                 "outside a payment. Row-locked and idempotent, same as verify.")
async def settle_due(
    due_id: int,
    data: SettleDueRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    return await service.settle_due(payload, due_id, data, idempotency_key)


@ledger_router.post("/payments/{payment_id}/receipt", response_model=ReceiptItem)
async def issue_receipt(
    payment_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.issue_receipt(payload, payment_id)


@ledger_router.patch("/payments/{payment_id}/receipt/collect", response_model=ReceiptItem)
async def collect_receipt(
    payment_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.collect_receipt(payload, payment_id)


@ledger_router.post("/contributions", response_model=ContributionItem)
async def add_contribution(
    data: AddContributionRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.add_contribution(payload, data)


@ledger_router.post("/expenses", response_model=ExpenseItem)
async def add_expense(
    data: AddExpenseRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.add_expense(payload, data)
