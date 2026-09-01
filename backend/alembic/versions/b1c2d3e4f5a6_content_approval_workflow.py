"""content approval workflow

Draft -> submitted -> tenant-admin approved/rejected -> live, applied to
events, announcements and decisions. Extends `EventStatus` with SUBMITTED
and REJECTED (publish() moves to admin-only, callable only from SUBMITTED).
Gives `Announcement` a status column it never had at all (it used to publish
instantly). Gives `Decision` a status column and makes `opened_at` nullable,
since voting now opens only once a TenantAdmin approves a submitted decision,
not at creation time.

Every one of the three tables gets the same five audit columns:
submitted_at, approved_by, approved_at, rejected_by, rejected_at,
rejection_reason - the same audit-trail instinct `RequestEventLog` already
uses for the request_flow stream.

Revision ID: b1c2d3e4f5a6
Revises: 18be8337050d
Create Date: 2026-09-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '18be8337050d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ANNOUNCEMENT_STATUS = sa.Enum(
    "DRAFT", "SUBMITTED", "PUBLISHED", "REJECTED", name="announcementstatus"
)
_DECISION_STATUS = sa.Enum(
    "DRAFT", "SUBMITTED", "OPEN", "REJECTED", "CLOSED", name="decisionstatus"
)


def _existing_columns(insp, table: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table)}


def _add_audit_columns(insp, table: str) -> None:
    cols = _existing_columns(insp, table)
    if "submitted_at" not in cols:
        op.add_column(table, sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    if "approved_by" not in cols:
        op.add_column(table, sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    if "approved_at" not in cols:
        op.add_column(table, sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    if "rejected_by" not in cols:
        op.add_column(table, sa.Column("rejected_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    if "rejected_at" not in cols:
        op.add_column(table, sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    if "rejection_reason" not in cols:
        op.add_column(table, sa.Column("rejection_reason", sa.Text(), nullable=True))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # events: extend the enum, add the audit trail.
    op.execute("ALTER TYPE eventstatus ADD VALUE IF NOT EXISTS 'SUBMITTED'")
    op.execute("ALTER TYPE eventstatus ADD VALUE IF NOT EXISTS 'REJECTED'")
    _add_audit_columns(insp, "events")

    # announcements: brand new status column plus the same audit trail.
    _ANNOUNCEMENT_STATUS.create(bind, checkfirst=True)
    if "status" not in _existing_columns(insp, "announcements"):
        op.add_column(
            "announcements",
            sa.Column(
                "status", _ANNOUNCEMENT_STATUS, nullable=False, server_default="DRAFT"
            ),
        )
    _add_audit_columns(insp, "announcements")

    # decisions: status column, opened_at loses its NOT-NULL-at-creation
    # default now that opening happens at approval time, plus audit trail.
    _DECISION_STATUS.create(bind, checkfirst=True)
    decision_cols = _existing_columns(insp, "decisions")
    if "status" not in decision_cols:
        op.add_column(
            "decisions",
            sa.Column("status", _DECISION_STATUS, nullable=False, server_default="DRAFT"),
        )
    op.alter_column("decisions", "opened_at", nullable=True, server_default=None)
    _add_audit_columns(insp, "decisions")


def downgrade() -> None:
    for table in ("events", "announcements", "decisions"):
        for column in (
            "rejection_reason", "rejected_at", "rejected_by",
            "approved_at", "approved_by", "submitted_at",
        ):
            op.drop_column(table, column)

    op.alter_column("decisions", "opened_at", nullable=False,
                     server_default=sa.func.now())
    op.drop_column("decisions", "status")
    op.drop_column("announcements", "status")

    bind = op.get_bind()
    _DECISION_STATUS.drop(bind, checkfirst=True)
    _ANNOUNCEMENT_STATUS.drop(bind, checkfirst=True)

    # Postgres cannot drop a single enum value; SUBMITTED/REJECTED on
    # eventstatus are left in place on downgrade, documented rather than
    # worked around with a type-rebuild that would risk live data.
