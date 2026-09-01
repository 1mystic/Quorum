"""insight_runs

Card C.10. docs/STATS_API.md section 2's table, verbatim. The only table the
read surface (`GET /api/t/{slug}/insights/...`) serves from; the API never
computes, it reads a row here.

Revision ID: 2678b05f0dc4
Revises: 700cabcdd2f5
Create Date: 2026-08-30 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core import rls


revision: str = '2678b05f0dc4'
down_revision: Union[str, None] = '700cabcdd2f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # The squashed init migration already builds `insight_runs` from ORM
    # metadata on a fresh database; skip straight to the RLS policy there.
    if not insp.has_table("insight_runs"):
        op.create_table(
            "insight_runs",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("pack", sa.String(), nullable=False),
            sa.Column("service", sa.String(), nullable=False),
            sa.Column("scope_key", sa.String(), nullable=False, server_default=""),
            sa.Column("params_hash", sa.String(), nullable=False),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column("n", sa.Integer(), nullable=False),
            sa.Column("n_censored", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("insufficient", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("worst_status", sa.String(), nullable=False),
            sa.Column("blocking", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("contract_version", sa.SmallInteger(), nullable=False, server_default="1"),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("stale_after", sa.DateTime(timezone=True), nullable=False),
            sa.Column("superseded_by", sa.BigInteger(), sa.ForeignKey("insight_runs.id"), nullable=True),
        )
        op.create_unique_constraint(
            "uq_insight_runs_identity", "insight_runs",
            ["tenant_id", "service", "scope_key", "params_hash", "window_end"],
        )
        op.create_index(
            "ix_insight_runs_tenant_pack_computed", "insight_runs",
            ["tenant_id", "pack", "computed_at"],
        )
        op.create_index(
            "ix_insight_runs_tenant_stale", "insight_runs", ["tenant_id", "stale_after"],
        )

    if not rls.policy_already_applied(bind, "insight_runs"):
        for statement in rls.enable_statements_for(["insight_runs"]):
            op.execute(statement)


def downgrade() -> None:
    for statement in rls.disable_statements_for(["insight_runs"]):
        op.execute(statement)

    op.drop_index("ix_insight_runs_tenant_stale", table_name="insight_runs")
    op.drop_index("ix_insight_runs_tenant_pack_computed", table_name="insight_runs")
    op.drop_constraint("uq_insight_runs_identity", "insight_runs", type_="unique")
    op.drop_table("insight_runs")
