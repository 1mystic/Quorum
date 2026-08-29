"""
Every tenant-scoped repository inherits this. The point is to make an
unscoped query awkward to write by accident (docs/RULES.md section 5):

- The constructor requires a tenant_id. There is no code path that builds
  a scoped repository without one.
- `self.scope(stmt, Model)` is the one-line way to add the tenant filter to
  a select/update/delete statement, so the natural thing to type is the safe
  thing to type.
- Repositories that create rows should set `tenant_id=self.tenant_id`
  themselves rather than accept it as a caller-supplied argument, so a wrong
  or stale caller value can never smuggle a row into the wrong tenant.

Postgres row-level security (see the tenancy migration) is the backstop for
the query that still gets written wrong. This class is the first line, not
the only one.
"""
from sqlalchemy import Select, Update, Delete
from sqlalchemy.ext.asyncio import AsyncSession


class TenantScopedRepository:
    def __init__(self, db: AsyncSession, tenant_id: int):
        if tenant_id is None:
            raise ValueError("TenantScopedRepository requires a tenant_id")
        self.db = db
        self.tenant_id = tenant_id

    def scope(self, stmt: Select | Update | Delete, model) -> Select | Update | Delete:
        """Add `model.tenant_id == self.tenant_id` to a statement."""
        return stmt.where(model.tenant_id == self.tenant_id)
