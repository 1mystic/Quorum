"""timestamps to utc

Revision ID: b7e2f04c8d31
Revises: 9c4a1d7e5b02
Create Date: 2026-08-08 22:12:40.116725
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2f04c8d31'
down_revision: Union[str, None] = '9c4a1d7e5b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = [
    ("announcements", "created_at"),
    ("campus_admins", "created_at"),
    ("clubs", "created_at"),
    ("colleges", "created_at"),
    ("event_registrations", "created_at"),
    ("events", "created_at"),
    ("issues", "created_at"),
    ("memberships", "created_at"),
    ("notifications", "created_at"),
    ("students", "announcements_seen_at"),
    ("students", "created_at"),
    ("users", "created_at"),
]


def upgrade() -> None:
    for table, column in COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    for table, column in COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.DateTime(),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
