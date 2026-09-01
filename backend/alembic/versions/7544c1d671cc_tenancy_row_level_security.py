"""tenancy row level security

Defense in depth (docs/RULES.md section 5): TenantScopedRepository and the
/api/t/{slug} slug-vs-JWT-claim check (app/core/tenancy.py) are the first
line. This is the backstop for the query that gets that wrong anyway.

app/core/tenancy.py sets the session-local GUC app.tenant_id via
`SELECT set_config('app.tenant_id', ..., true)` on every tenant-scoped
request, before any repository query runs. Every policy here reads that same
setting. When it is unset (no session has called set_config), the comparison
is NULL and every policy denies by default - fail closed, not open.

`users` and `tenant_admins` are deliberately excluded. Both are pre-tenant
identity tables: signup and login run before any tenant context exists (they
are not under /api/t/{slug}), and a TENANT_ADMIN's tenant_id is NULL until
onboarding. FORCE RLS's `tenant_id = current_setting(...)::int` is never true
for a NULL tenant_id, so it would lock every admin signup out of its own row,
not just a cross-tenant read. Lookups on both are already scoped correctly in
Python (by id or unique email/user_id), and neither is ever exposed as a
generic cross-tenant list.

`group_links` is excluded for the same reason `users` is not a concern here
but for the opposite one: it has no tenant_id column of its own (it is a
small child of `groups`, reached only by group_id). Follow-up: either add
tenant_id there too or write its policy as a join against `groups`.

Revision ID: 7544c1d671cc
Revises: 594b7f5de74d
Create Date: 2026-08-29 15:22:48.810979

"""
from typing import Sequence, Union

from alembic import op

from app.core import rls


# revision identifiers, used by Alembic.
revision: str = '7544c1d671cc'
down_revision: Union[str, None] = '594b7f5de74d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for statement in rls.enable_statements():
        op.execute(statement)


def downgrade() -> None:
    for statement in rls.disable_statements():
        op.execute(statement)