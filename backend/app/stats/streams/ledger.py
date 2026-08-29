"""
Stream 3: `ledger`. docs/DATA_SPINE.md section 3.

Signed money movement, grounded in the RWA interview evidence: bank transfer,
screenshot to WhatsApp, manual treasurer verification, physical register,
receipt frequently never collected. The spine records that whole path so we can
measure it rather than assume it.

Money is `int` minor units plus an ISO-4217 currency. Never a float, ever,
anywhere (spine rule S4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

from app.stats.streams.request import CensoringKind

LedgerInstrument = Literal[
    "upi", "bank_transfer", "cash", "cheque", "card", "in_kind", "adjustment"
]

LedgerStatus = Literal["expected", "pending", "settled", "failed", "reversed", "written_off"]


@dataclass(frozen=True)
class LedgerEntry:
    """
    Atom. Append-only and signed.

    `verified_at`, `receipt_issued_at` and `receipt_collected_at` are not
    bookkeeping decoration. The gap between `at` and `verified_at` is the manual
    verification lag the ex-Secretary described; the gap between issued and
    collected is the receipt-adoption gap. Both are request_flow-shaped censored
    durations and both are rwa_society headline statistics.

    Rule L3: a reversal is a NEW signed entry (`reversal_of`), never a mutation
    of the original, so Benford and audit statistics see the true digit
    distribution.
    """

    entry_ref: str
    at: datetime                   # value date: when the money moved
    booked_at: datetime            # when it was recorded in the system
    amount_minor: int              # SIGNED. inflow positive, outflow negative.
    currency: str                  # ISO 4217
    category: str
    direction: Literal["inflow", "outflow"]   # redundant with the sign, kept for adapter safety
    instrument: LedgerInstrument
    status: LedgerStatus
    subcategory: str | None = None
    member_ref: str | None = None         # payer or payee if a member
    counterparty_ref: str | None = None   # vendor, contractor, bank. Pseudonymous.
    group_ref: str | None = None
    campaign_ref: str | None = None       # event or fundraiser this belongs to
    due_at: datetime | None = None        # receivables only
    settled_at: datetime | None = None
    reversal_of: str | None = None
    verified_at: datetime | None = None   # treasurer confirmed it. The WhatsApp-screenshot lag.
    verified_by_ref: str | None = None
    receipt_issued_at: datetime | None = None
    receipt_collected_at: datetime | None = None
    reconciled: bool = False
    attributes: Mapping[str, float | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise ValueError(
                "LedgerEntry.amount_minor must be int minor units, never a float (spine rule S4); "
                "entry " + self.entry_ref
            )
        if self.direction == "inflow" and self.amount_minor < 0:
            raise ValueError("entry " + self.entry_ref + " is an inflow with a negative amount")
        if self.direction == "outflow" and self.amount_minor > 0:
            raise ValueError("entry " + self.entry_ref + " is an outflow with a positive amount")


@dataclass(frozen=True)
class DueSpell:
    """
    Unit. A receivable as a time-to-event record.

    Rule L1: an unpaid due is right-censored, exactly like an open request. The
    "average days to pay" of only the paid dues is the same defect as C1, and it
    understates the lag by exactly the amount that matters.
    """

    due_ref: str
    member_ref: str
    issued_at: datetime
    due_at: datetime
    amount_minor: int
    at_risk_from: datetime
    settled_at: datetime | None
    duration_days: float           # due_at -> min(settled_at, window.end); negative if paid early
    event_observed: bool           # settled inside the window
    censoring: CensoringKind
    partial_paid_minor: int = 0
    reminders_sent: int = 0
    strata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_observed and self.censoring == "none":
            raise ValueError(
                "due " + self.due_ref + " is unsettled, so it is censored (rule L1); "
                "censoring='none' is reserved for observed settlements"
            )


@dataclass(frozen=True)
class LedgerPeriod:
    """
    Unit. Periodised money for forecasting and the runway simulation.

    Rule L2: `expected` entries are forecast inputs, never actuals. A service
    mixing them must say so in a caveat.
    """

    period_start: datetime
    period_end: datetime
    inflow_minor: int
    outflow_minor: int
    net_minor: int
    closing_balance_minor: int | None
    by_category: Mapping[str, int] = field(default_factory=dict)
    complete: bool = True          # respects window.complete_through


__all__ = ["DueSpell", "LedgerEntry", "LedgerInstrument", "LedgerPeriod", "LedgerStatus"]
