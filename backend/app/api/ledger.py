from fastapi import APIRouter, Depends, Header, Security

from app.schemas import (
    CreateDueRequest, DueItem, RecordPaymentRequest, PaymentItem, ReceiptItem,
    AddContributionRequest, ContributionItem, AddExpenseRequest, ExpenseItem,
    SettleDueRequest,
)
from app.services import LedgerService
from app.core.di import get_ledger_service, get_user_info

ledger_router = APIRouter(prefix="/ledger", tags=["Ledger"])


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
