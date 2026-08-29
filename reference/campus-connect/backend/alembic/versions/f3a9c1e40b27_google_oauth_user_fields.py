"""google oauth user fields

Revision ID: f3a9c1e40b27
Revises: b7e2f04c8d31
Create Date: 2026-08-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f3a9c1e40b27'
down_revision: Union[str, None] = 'b7e2f04c8d31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    auth_provider = postgresql.ENUM('LOCAL', 'GOOGLE', name='authprovider')
    auth_provider.create(op.get_bind(), checkfirst=True)

    op.add_column('users', sa.Column(
        'auth_provider', auth_provider, server_default='LOCAL', nullable=False
    ))
    op.add_column('users', sa.Column('google_sub', sa.String(), nullable=True))
    op.create_unique_constraint('uq_users_google_sub', 'users', ['google_sub'])
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(), nullable=False)
    op.drop_constraint('uq_users_google_sub', 'users', type_='unique')
    op.drop_column('users', 'google_sub')
    op.drop_column('users', 'auth_provider')
    postgresql.ENUM(name='authprovider').drop(op.get_bind(), checkfirst=True)
