"""ledger concurrency control

Part 2: row locking, idempotency and optimistic locking on the money-moving
path. Adds `version` (SQLAlchemy's `version_id_col`) to `dues` and
`payments`, the second layer behind the explicit `SELECT ... FOR UPDATE`
locks in `LedgerRepository`. Adds `idempotency_records` so a repeated
payment-verification or due-settlement call with the same client-supplied
key returns the original result rather than processing twice.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core import rls


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "idempotency_records"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table in ("dues", "payments"):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "version" not in cols:
            op.add_column(
                table, sa.Column("version", sa.Integer(), nullable=False, server_default="1")
            )

    if not insp.has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("scope", sa.String(120), nullable=False),
            sa.Column("key", sa.String(200), nullable=False),
            sa.Column("response", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.UniqueConstraint("tenant_id", "scope", "key", name="uq_idempotency_tenant_scope_key"),
        )
        for statement in rls.enable_statements_for([_TABLE]):
            op.execute(statement)
    elif not rls.policy_already_applied(bind, _TABLE):
        for statement in rls.enable_statements_for([_TABLE]):
            op.execute(statement)


def downgrade() -> None:
    for statement in rls.disable_statements_for([_TABLE]):
        op.execute(statement)
    op.drop_table(_TABLE)
    op.drop_column("payments", "version")
    op.drop_column("dues", "version")
