from fastapi import APIRouter, Depends, Security

from app.schemas import (
    CreateDueRequest, DueItem, RecordPaymentRequest, PaymentItem, ReceiptItem,
    AddContributionRequest, ContributionItem, AddExpenseRequest, ExpenseItem,
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


@ledger_router.patch("/payments/{payment_id}/verify", response_model=PaymentItem)
async def verify_payment(
    payment_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.verify_payment(payload, payment_id)


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
