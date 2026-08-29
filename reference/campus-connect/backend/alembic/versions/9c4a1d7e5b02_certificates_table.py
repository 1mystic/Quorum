"""certificates table

Revision ID: 9c4a1d7e5b02
Revises: 27fde89f8708
Create Date: 2026-08-08 20:45:11.204188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9c4a1d7e5b02'
down_revision: Union[str, None] = '27fde89f8708'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    registration_result = postgresql.ENUM(
        'REGISTRANT', 'PARTICIPANT', 'RUNNER_UP', 'WINNER',
        name='registrationresult',
        create_type=False,
    )

    op.create_table('certificates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('registration_id', sa.Integer(), nullable=False),
    sa.Column('serial', sa.String(), nullable=False),
    sa.Column('result', registration_result, nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['registration_id'], ['event_registrations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('registration_id')
    )
    op.create_index(op.f('ix_certificates_serial'), 'certificates', ['serial'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_certificates_serial'), table_name='certificates')
    op.drop_table('certificates')
