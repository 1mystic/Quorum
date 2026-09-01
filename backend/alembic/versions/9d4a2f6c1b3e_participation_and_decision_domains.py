"""participation and decision domains

Card C.15 (backend half). docs/DATA_SPINE.md sections 4 and 6: attendance,
RSVP, upvotes, volunteer hours and the exposure log
(nudge_sent/delivered/opened/acted with arm_ref) as one append-only
`participation_events` table; Poll/Ballot/Allocation as `decisions` /
`decision_options` / `ballots`. Closes two of the three remaining gaps
`app/verticals/adapters/base.py` named as TODOs: the exposure log had no
table at all, blocking Pack 2's experiments/bandits entirely, and there was
no decision/option/ballot model, so `governance_insight` had nothing to read.

`decisions.declared_rule` is `nullable=False` from this first migration
(rule D1): a decision cannot exist without a declared rule, so there is never
a history of decisions whose rule cannot be trusted.

Revision ID: 9d4a2f6c1b3e
Revises: 2678b05f0dc4
Create Date: 2026-08-30 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core import rls


revision: str = '9d4a2f6c1b3e'
down_revision: Union[str, None] = '2678b05f0dc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PARTICIPATION_KIND = sa.Enum(
    "rsvp", "rsvp_cancel", "attend", "no_show", "login", "post", "comment", "upvote",
    "read_receipt", "volunteer_hours", "training_complete", "in_kind_contribution",
    "nudge_sent", "nudge_delivered", "nudge_opened", "nudge_acted",
    name="participationkind",
)
_DECISION_KIND = sa.Enum("poll", "election", "budget_allocation", "referendum", name="decisionkind")
_BALLOT_STYLE = sa.Enum("ranked", "approval", "score", "single", "allocation", name="ballotstyle")

_TABLES = ["participation_events", "decisions", "decision_options", "ballots"]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    _PARTICIPATION_KIND.create(bind, checkfirst=True)
    _DECISION_KIND.create(bind, checkfirst=True)
    _BALLOT_STYLE.create(bind, checkfirst=True)

    # The squashed init migration already builds every one of these tables
    # from ORM metadata on a fresh database; only create what is missing so
    # this migration stays correct for a genuinely incremental upgrade too.
    if insp.has_table("participation_events"):
        for table in _TABLES:
            if not rls.policy_already_applied(bind, table):
                for statement in rls.enable_statements_for([table]):
                    op.execute(statement)
        return

    op.create_table(
        "participation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", _PARTICIPATION_KIND, nullable=False),
        sa.Column("object_type", sa.String(), nullable=True),
        sa.Column("object_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("arm_ref", sa.String(), nullable=True),
        sa.Column("strata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_participation_events_member_at", "participation_events", ["member_id", "at"])
    op.create_index("ix_participation_events_kind_at", "participation_events", ["kind", "at"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("kind", _DECISION_KIND, nullable=False),
        sa.Column("declared_rule", sa.String(), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("quorum_rule", sa.String(), nullable=True),
        sa.Column("budget_minor", sa.Integer(), nullable=True),
        sa.Column("ballot_style", _BALLOT_STYLE, nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eligible_strata", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "decision_options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("cost_minor", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("proposer_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "ballots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("decision_id", sa.Integer(), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("voter_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("cast_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ranking", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("approvals", postgresql.ARRAY(sa.Integer()), nullable=False, server_default="{}"),
        sa.Column("scores", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("allocation", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("decision_id", "voter_id", name="uq_ballot_decision_voter"),
    )

    for statement in rls.enable_statements_for(_TABLES):
        op.execute(statement)


def downgrade() -> None:
    for statement in rls.disable_statements_for(_TABLES):
        op.execute(statement)

    op.drop_table("ballots")
    op.drop_table("decision_options")
    op.drop_table("decisions")
    op.drop_index("ix_participation_events_kind_at", table_name="participation_events")
    op.drop_index("ix_participation_events_member_at", table_name="participation_events")
    op.drop_table("participation_events")

    bind = op.get_bind()
    _BALLOT_STYLE.drop(bind, checkfirst=True)
    _DECISION_KIND.drop(bind, checkfirst=True)
    _PARTICIPATION_KIND.drop(bind, checkfirst=True)
