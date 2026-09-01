"""ledger domain

Card C.10 (ledger half). docs/GLOSSARY.md's new entities table: Due, Payment,
Receipt, Contribution, Expense -> the `ledger` stream (docs/DATA_SPINE.md
section 3). Closes the gap `app/verticals/adapters/base.py` named: there was
no ledger model, so rwa_society's two most interview-grounded headline
statistics (verification lag, receipt-collection gap) had nothing to read.

Revision ID: 700cabcdd2f5
Revises: a3f7c9d1e2b4
Create Date: 2026-08-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core import rls


revision: str = '700cabcdd2f5'
down_revision: Union[str, None] = 'a3f7c9d1e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DUE_STATUS = sa.Enum("OPEN", "PARTIAL", "PAID", "WAIVED", "WRITTEN_OFF", name="duestatus")
_INSTRUMENT = sa.Enum(
    "upi", "bank_transfer", "cash", "cheque", "card", "in_kind", "adjustment",
    name="ledgerinstrument",
)
_LEDGER_STATUS = sa.Enum(
    "expected", "pending", "settled", "failed", "reversed", "written_off",
    name="ledgerstatus",
)
_CONTRIBUTION_KIND = sa.Enum("cash", "volunteer_hours", "in_kind", name="contributionkind")

_TABLES = ["dues", "payments", "receipts", "contributions", "expenses"]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    _DUE_STATUS.create(bind, checkfirst=True)
    _INSTRUMENT.create(bind, checkfirst=True)
    _LEDGER_STATUS.create(bind, checkfirst=True)
    _CONTRIBUTION_KIND.create(bind, checkfirst=True)

    # The squashed init migration already builds every one of these tables
    # from ORM metadata on a fresh database; only create what is missing so
    # this migration stays correct for a genuinely incremental upgrade too.
    if insp.has_table("dues"):
        _apply_rls_if_missing(bind)
        return

    op.create_table(
        "dues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("subcategory", sa.String(), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", _DUE_STATUS, nullable=False, server_default="OPEN"),
        sa.Column("reminders_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dues_member_status", "dues", ["member_id", "status"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("due_id", sa.Integer(), sa.ForeignKey("dues.id"), nullable=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("campaign_ref", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("subcategory", sa.String(), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("instrument", _INSTRUMENT, nullable=False),
        sa.Column("status", _LEDGER_STATUS, nullable=False, server_default="pending"),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversal_of_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("reconciled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payments_member_at", "payments", ["member_id", "at"])

    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id"), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "contributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("campaign_ref", sa.String(), nullable=True),
        sa.Column("kind", _CONTRIBUTION_KIND, nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("campaign_ref", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("subcategory", sa.String(), nullable=True),
        sa.Column("counterparty_ref", sa.String(), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="INR"),
        sa.Column("instrument", _INSTRUMENT, nullable=False),
        sa.Column("status", _LEDGER_STATUS, nullable=False, server_default="pending"),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("reversal_of_id", sa.Integer(), sa.ForeignKey("expenses.id"), nullable=True),
        sa.Column("reconciled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    _apply_rls_if_missing(bind)


def _apply_rls_if_missing(bind) -> None:
    for table in _TABLES:
        if not rls.policy_already_applied(bind, table):
            for statement in rls.enable_statements_for([table]):
                op.execute(statement)


def downgrade() -> None:
    for statement in rls.disable_statements_for(_TABLES):
        op.execute(statement)

    op.drop_table("expenses")
    op.drop_table("contributions")
    op.drop_index("ix_payments_member_at", table_name="payments")
    op.drop_table("receipts")
    op.drop_table("payments")
    op.drop_index("ix_dues_member_status", table_name="dues")
    op.drop_table("dues")

    bind = op.get_bind()
    _CONTRIBUTION_KIND.drop(bind, checkfirst=True)
    _LEDGER_STATUS.drop(bind, checkfirst=True)
    _INSTRUMENT.drop(bind, checkfirst=True)
    _DUE_STATUS.drop(bind, checkfirst=True)
