"""
Card C.10. The `ledger` stream adapter conformance, same discipline as
`test_adapters.py`: plain `SimpleNamespace` fixtures, no ORM, no database.

Proves the TODO named in `app/verticals/adapters/base.py`'s class docstring
("there is no ledger model... approximating it from anything present would be
fiction with a currency symbol") is genuinely closed: `Due`, `Payment`,
`Receipt`, `Contribution` and `Expense` rows now produce real `LedgerEntry`
atoms, signed correctly, with the two rwa_society headline lags
(`verified_at`, `receipt_collected_at`) actually populated when the data has
them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.verticals.adapters import CampusClubAdapter, RwaSocietyAdapter

T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

ADAPTER_CLASSES = [RwaSocietyAdapter, CampusClubAdapter]


def receipt_row(**overrides):
    base = dict(id=1, issued_at=T0 + timedelta(hours=1), collected_at=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def payment_row(**overrides):
    base = dict(
        id=1, due_id=None, member_id=7, group_id=None, campaign_ref=None,
        category="maintenance_dues", subcategory=None,
        amount_minor=50000, currency="INR", instrument=SimpleNamespace(value="upi"),
        status=SimpleNamespace(value="settled"), at=T0, booked_at=T0,
        settled_at=T0, verified_at=None, verified_by_id=None, reconciled=False,
        receipt=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def due_row(category: str, **overrides):
    base = dict(
        id=1, member_id=7, group_id=None, category=category, subcategory=None,
        amount_minor=500000, currency="INR", issued_at=T0, due_at=T0 + timedelta(days=30),
        status=SimpleNamespace(value="open"), payments=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def contribution_row(category: str, **overrides):
    base = dict(
        id=1, member_id=7, group_id=None, campaign_ref="c_1",
        kind=SimpleNamespace(value="cash"), category=category, amount_minor=10000,
        currency="INR", at=T0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def expense_row(category: str, **overrides):
    base = dict(
        id=1, group_id=None, campaign_ref=None, category=category, subcategory=None,
        counterparty_ref="vendor_ac", amount_minor=75000, currency="INR",
        instrument=SimpleNamespace(value="bank_transfer"), status=SimpleNamespace(value="settled"),
        at=T0, booked_at=T0, settled_at=T0, approved_by_id=9, reconciled=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("adapter_class,category", [
    (RwaSocietyAdapter, "maintenance_dues"),
    (CampusClubAdapter, "membership_fee"),
])
def test_an_unpaid_due_is_an_inflow_with_no_settlement(adapter_class, category):
    """The receivable itself, still open: exactly what DueSpell (rule L1) censors, not drops."""
    entries = adapter_class().ledger_entries([due_row(category)])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.direction == "inflow"
    assert entry.amount_minor == 500000
    assert entry.due_at is not None
    assert entry.settled_at is None
    assert entry.verified_at is None
    assert entry.status == "expected"


@pytest.mark.parametrize("adapter_class,category", [
    (RwaSocietyAdapter, "maintenance_dues"),
    (CampusClubAdapter, "membership_fee"),
])
def test_a_settled_due_carries_the_verification_lag_and_receipt_gap(adapter_class, category):
    """
    The two interview-grounded rwa_society headline statistics: the gap
    between `at` (money moved) and `verified_at` (treasurer confirmed the
    WhatsApp screenshot), and between a receipt being issued and collected.
    """
    verified_at = T0 + timedelta(days=2)
    receipt = receipt_row(issued_at=T0 + timedelta(days=2, hours=1), collected_at=None)
    settling_payment = payment_row(
        due_id=1, verified_at=verified_at, verified_by_id=3, reconciled=True, receipt=receipt,
    )
    due = due_row(category, status=SimpleNamespace(value="paid"), payments=[settling_payment])

    entries = adapter_class().ledger_entries([due])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.status == "settled"
    assert entry.verified_at == verified_at
    assert entry.verified_by_ref == "m_3"
    assert entry.receipt_issued_at == receipt.issued_at
    assert entry.receipt_collected_at is None, "the receipt-collection gap: issued but not collected"


def test_a_settling_payment_is_not_double_counted_against_its_due():
    """A due and the payment that settles it are one signed movement, not two."""
    payment = payment_row(due_id=1, verified_at=T0 + timedelta(days=1))
    due = due_row("maintenance_dues", payments=[payment])
    entries = RwaSocietyAdapter().ledger_entries([due, payment])
    assert len(entries) == 1
    assert entries[0].entry_ref == "due_1"


def test_a_standalone_payment_with_no_due_is_its_own_entry():
    payment = payment_row(due_id=None, amount_minor=20000)
    entries = RwaSocietyAdapter().ledger_entries([payment])
    assert len(entries) == 1
    assert entries[0].entry_ref == "pay_1"
    assert entries[0].direction == "inflow"
    assert entries[0].amount_minor == 20000


def test_an_expense_is_a_negative_outflow():
    entries = RwaSocietyAdapter().ledger_entries([expense_row("stp_maintenance")])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.direction == "outflow"
    assert entry.amount_minor == -75000, "outflow must be signed negative (spine rule S4 / LedgerEntry contract)"
    assert entry.counterparty_ref == "vendor_ac"


def test_a_contribution_is_a_positive_inflow_with_no_due_at():
    entries = RwaSocietyAdapter().ledger_entries([contribution_row("festival_fund")])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.direction == "inflow"
    assert entry.amount_minor == 10000
    assert entry.due_at is None, "a contribution is never a receivable"


def test_an_unmapped_ledger_category_is_counted_as_other_never_dropped():
    adapter = RwaSocietyAdapter()
    entries = adapter.ledger_entries([expense_row("bribery_fund")])
    assert len(entries) == 1
    assert entries[0].category == "other"
    assert adapter.unmapped_report()["ledger_category:bribery_fund"] == 1


def test_mixed_ledger_rows_all_come_through_together():
    """The adapter obligation that nothing is filtered: dues, payments, contributions and expenses coexist."""
    rows = [
        due_row("maintenance_dues", id=1),
        payment_row(id=2, due_id=None),
        contribution_row("festival_fund", id=3),
        expense_row("stp_maintenance", id=4),
    ]
    entries = RwaSocietyAdapter().ledger_entries(rows)
    assert {e.entry_ref for e in entries} == {"due_1", "pay_2", "con_3", "exp_4"}
    inflow_total = sum(e.amount_minor for e in entries if e.direction == "inflow")
    outflow_total = sum(e.amount_minor for e in entries if e.direction == "outflow")
    assert inflow_total > 0
    assert outflow_total < 0
