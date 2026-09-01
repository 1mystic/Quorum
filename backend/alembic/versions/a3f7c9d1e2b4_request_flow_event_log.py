"""request_flow event log

Card C.8: closes the gap `app/verticals/adapters/base.py` flagged as a TODO on
`PortedSchemaAdapter.request_events` - there was no request event/status-change
log, so "assigned", "reassigned", "paused", "resumed", "escalated",
"withdrawn", "merged" and "reopened" had nowhere to be recorded. Without it
`survival.competing_risks_cif` had nothing to estimate (rule C5) and
`duration_active_hours` was unavailable for any vertical declaring
`sla_clock="active"` (campus_club).

Also: `requests.category` moves from the ported Campus Connect
`RequestCategory` enum to a plain string, validated at the service layer
against the tenant's vertical vocabulary (docs/VERTICALS.md) instead of a
fixed database enum, plus `subcategory`, `priority`, `channel`, `location_ref`
- the columns the adapter named as missing for request_flow's covariates.
`requeststatus` gains `ESCALATED`/`WITHDRAWN`/`MERGED`, the competing-risks
terminals; `requests` gains `terminal_at`, `outcome` and `merged_into_id` as a
read convenience over the new log (never the source a stream adapter reduces).

Revision ID: a3f7c9d1e2b4
Revises: 7544c1d671cc
Create Date: 2026-08-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core import rls


# revision identifiers, used by Alembic.
revision: str = 'a3f7c9d1e2b4'
down_revision: Union[str, None] = '7544c1d671cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_STATUS_VALUES = ("ESCALATED", "WITHDRAWN", "MERGED")

_REQUEST_EVENT_KIND = sa.Enum(
    "opened", "acknowledged", "assigned", "reassigned", "status_change", "comment",
    "paused", "resumed", "resolved", "escalated", "withdrawn", "merged", "reopened", "closed",
    name="requesteventkind",
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # requeststatus gains the two competing-risks terminals plus "merged".
    # Postgres requires ALTER TYPE ... ADD VALUE outside the value's own use,
    # which a schema migration naturally satisfies.
    for value in _NEW_STATUS_VALUES:
        op.execute(f"ALTER TYPE requeststatus ADD VALUE IF NOT EXISTS '{value}'")

    # requests.category: enum -> free string, validated in the service against
    # the tenant's vertical adapter rather than a fixed database enum. On a
    # fresh database the squashed init migration already built `requests`
    # from ORM metadata with `category` as a plain string, so this cast is a
    # no-op there; only run it when the column is still the old enum.
    existing_columns = {c["name"]: c for c in insp.get_columns("requests")}
    category_type = existing_columns["category"]["type"]
    if isinstance(category_type, sa.Enum):
        op.alter_column(
            "requests", "category",
            existing_type=sa.Enum(name="requestcategory"),
            type_=sa.String(),
            postgresql_using="category::text",
        )
    op.execute("DROP TYPE IF EXISTS requestcategory")

    for col_name, col_type in (
        ("subcategory", sa.String()),
        ("priority", sa.String()),
        ("channel", sa.String()),
        ("location_ref", sa.String()),
        ("terminal_at", sa.DateTime(timezone=True)),
        ("outcome", sa.String()),
    ):
        if col_name not in existing_columns:
            op.add_column("requests", sa.Column(col_name, col_type, nullable=True))
    if "merged_into_id" not in existing_columns:
        op.add_column(
            "requests",
            sa.Column("merged_into_id", sa.Integer(), sa.ForeignKey("requests.id"), nullable=True),
        )

    _REQUEST_EVENT_KIND.create(bind, checkfirst=True)
    if not insp.has_table("request_events"):
        op.create_table(
            "request_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id"), nullable=False),
            sa.Column("kind", _REQUEST_EVENT_KIND, nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
            sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("subcategory", sa.String(), nullable=True),
            sa.Column("priority", sa.String(), nullable=True),
            sa.Column("channel", sa.String(), nullable=True),
            sa.Column("location_ref", sa.String(), nullable=True),
            sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
            sa.Column("parent_request_id", sa.Integer(), sa.ForeignKey("requests.id"), nullable=True),
            sa.Column("at_precision", sa.String(), nullable=False, server_default="exact"),
            sa.Column("at_upper", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_request_events_request_at", "request_events", ["request_id", "at"])

    if not rls.policy_already_applied(bind, "request_events"):
        for statement in rls.enable_statements_for(["request_events"]):
            op.execute(statement)


def downgrade() -> None:
    bind = op.get_bind()

    for statement in rls.disable_statements_for(["request_events"]):
        op.execute(statement)

    op.drop_index("ix_request_events_request_at", table_name="request_events")
    op.drop_table("request_events")
    _REQUEST_EVENT_KIND.drop(bind, checkfirst=True)

    op.drop_column("requests", "merged_into_id")
    op.drop_column("requests", "outcome")
    op.drop_column("requests", "terminal_at")
    op.drop_column("requests", "location_ref")
    op.drop_column("requests", "channel")
    op.drop_column("requests", "priority")
    op.drop_column("requests", "subcategory")

    op.execute(
        "CREATE TYPE requestcategory AS ENUM "
        "('EVENT', 'GROUP', 'CERTIFICATE', 'TECHNICAL', 'GENERAL')"
    )
    op.alter_column(
        "requests", "category",
        existing_type=sa.String(),
        type_=sa.Enum(name="requestcategory"),
        postgresql_using="category::requestcategory",
    )

    # Postgres cannot drop an enum value; downgrading requeststatus is
    # deliberately a no-op rather than a lossy rewrite of every row.
