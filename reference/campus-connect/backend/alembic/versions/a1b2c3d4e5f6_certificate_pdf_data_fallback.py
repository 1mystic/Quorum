"""certificate pdf_data fallback storage

Revision ID: a1b2c3d4e5f6
Revises: f3a9c1e40b27
Create Date: 2026-08-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a9c1e40b27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('certificates', sa.Column('pdf_data', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column('certificates', 'pdf_data')
