"""init schema

This port squashes Campus Connect's fourteen incremental migrations into one:
the rename pass (docs/GLOSSARY.md) touches nearly every table and column, so
replaying the original history against the new names would just be churn.
This is the schema as it stands after the rename and the tenant_id additions.

Built from the ORM metadata rather than hand-written DDL, so it can never
drift from app/models. Safe for a fresh database; this is not meant to
upgrade a Campus Connect database in place.

Revision ID: 594b7f5de74d
Revises:
Create Date: 2026-08-29 15:22:12.436900

"""
from typing import Sequence, Union

from alembic import op

from app.core.database import Base
from app import models  # noqa: F401  (registers every model on Base.metadata)


# revision identifiers, used by Alembic.
revision: str = '594b7f5de74d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())