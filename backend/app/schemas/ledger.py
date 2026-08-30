from datetime import datetime
from pydantic import BaseModel, Field

from app.models import DueStatus, LedgerInstrument, LedgerStatus, ContributionKind


class CreateDueRequest(BaseModel):
    member_id: int
    category: str = Field(..., min_length=1, max_length=64)
    subcategory: str | None = Field(None, max_length=64)
    amount_minor: int = Field(..., gt=0)
    currency: str = Field("INR", max_length=8)
    due_at: datetime
    group_id: int | None = None


class DueItem(BaseModel):
    id: int
    member_id: int
    category: str
    subcategory: str | None
    amount_minor: int
    currency: str
    issued_at: datetime
    due_at: datetime
    status: DueStatus


class RecordPaymentRequest(BaseModel):
    amount_minor: int = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=64)
    subcategory: str | None = Field(None, max_length=64)
    instrument: LedgerInstrument
    at: datetime
    due_id: int | None = None
    member_id: int | None = None
    campaign_ref: str | None = Field(None, max_length=64)
    currency: str = Field("INR", max_length=8)


class PaymentItem(BaseModel):
    id: int
    due_id: int | None
    member_id: int | None
    category: str
    amount_minor: int
    currency: str
    instrument: LedgerInstrument
    status: LedgerStatus
    at: datetime
    verified_at: datetime | None
    settled_at: datetime | None


class ReceiptItem(BaseModel):
    id: int
    payment_id: int
    issued_at: datetime | None
    collected_at: datetime | None


class AddContributionRequest(BaseModel):
    kind: ContributionKind
    category: str = Field(..., min_length=1, max_length=64)
    at: datetime
    member_id: int | None = None
    campaign_ref: str | None = Field(None, max_length=64)
    amount_minor: int = Field(0, ge=0)
    currency: str = Field("INR", max_length=8)
    description: str | None = Field(None, max_length=500)


class ContributionItem(BaseModel):
    id: int
    member_id: int | None
    kind: ContributionKind
    category: str
    amount_minor: int
    at: datetime


class AddExpenseRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=64)
    subcategory: str | None = Field(None, max_length=64)
    amount_minor: int = Field(..., gt=0)
    instrument: LedgerInstrument
    at: datetime
    counterparty_ref: str | None = Field(None, max_length=120)
    campaign_ref: str | None = Field(None, max_length=64)
    currency: str = Field("INR", max_length=8)


class ExpenseItem(BaseModel):
    id: int
    category: str
    subcategory: str | None
    counterparty_ref: str | None
    amount_minor: int
    currency: str
    status: LedgerStatus
    at: datetime


class LedgerActionResponse(BaseModel):
    id: int
    message: str
