"""tenant_admins rls exclusion

Card (backend-porter, real-Postgres pass). `tenant_admins` was force-RLS'd by
the original tenancy migration alongside every other tenant-scoped table, but
it has the same NULL-tenant_id-before-onboarding shape as `users` (already
excluded there, see that migration's docstring) - a TENANT_ADMIN signs up
with `tenant_id` NULL and only gets one once they onboard a tenant. FORCE
RLS's `tenant_id = current_setting(...)::int` is never true for NULL, so the
policy silently failed every admin signup closed once anything other than a
superuser connection role was used to run it. Only visible once the
integration suite ran against a real Postgres role without a superuser's
blanket RLS bypass.

Revision ID: 18be8337050d
Revises: 9d4a2f6c1b3e
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

from app.core import rls


revision: str = '18be8337050d'
down_revision: Union[str, None] = '9d4a2f6c1b3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls.disable_statements_for(["tenant_admins"]):
        op.execute(statement)


def downgrade() -> None:
    for statement in rls.enable_statements_for(["tenant_admins"]):
        op.execute(statement)
