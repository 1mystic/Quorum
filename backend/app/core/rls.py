"""
The Postgres row-level security statements for the tenancy migration
(alembic/versions/*_tenancy_row_level_security.py), factored out so the test
suite can apply the same DDL when it builds the schema via
Base.metadata.create_all instead of `alembic upgrade head` (see
tests/conftest.py's setup_db). Keeping one source of truth here means the
test database's RLS behaviour cannot silently drift from what a real
deployment gets from the migration.
"""

from sqlalchemy import text

TENANT_SCOPED_TABLES = [
    # `tenant_admins` is deliberately excluded, same reasoning as `users`
    # (see the tenancy migration's docstring): a TENANT_ADMIN's tenant_id is
    # NULL until onboarding, signup creates this row before onboarding ever
    # runs, and FORCE RLS's `tenant_id = current_setting(...)::int` check is
    # never true for a NULL tenant_id, so it would fail closed against every
    # admin signup, not just a cross-tenant read.
    "members",
    "groups",
    "events",
    "announcements",
    "notifications",
    "requests",
    "request_events",
    "certificates",
    "event_registrations",
    "memberships",
    "dues",
    "payments",
    "receipts",
    "contributions",
    "expenses",
    "insight_runs",
    "participation_events",
    "decisions",
    "decision_options",
    "ballots",
    "idempotency_records",
]

POLICY_NAME = "tenant_isolation"
TENANT_FILTER = "tenant_id = current_setting('app.tenant_id', true)::int"


def enable_statements(tables: list[str] | None = None) -> list[str]:
    statements = []
    for table in (tables if tables is not None else TENANT_SCOPED_TABLES):
        statements.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        statements.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        statements.append(
            f"CREATE POLICY {POLICY_NAME} ON {table} "
            f"USING ({TENANT_FILTER}) WITH CHECK ({TENANT_FILTER})"
        )
    return statements


def disable_statements(tables: list[str] | None = None) -> list[str]:
    statements = []
    for table in (tables if tables is not None else TENANT_SCOPED_TABLES):
        statements.append(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
        statements.append(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        statements.append(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    return statements


# Aliases read naturally at a call site that is scoping a subset of tables,
# e.g. a migration that adds one new tenant-scoped table after the original
# tenancy migration already covered the rest.
enable_statements_for = enable_statements
disable_statements_for = disable_statements


def policy_already_applied(bind, table: str) -> bool:
    """
    True when `tenant_isolation` is already on `table`. The squashed init
    migration builds every table up front from ORM metadata, so a later
    migration's own `enable_statements_for([...])` call can be reapplying a
    policy the tenancy migration already created for that same table; this
    guards that from failing with "policy already exists" on a fresh
    database while remaining a no-op for a genuinely incremental upgrade.
    """
    row = bind.execute(
        text(
            "SELECT 1 FROM pg_policies WHERE tablename = :table AND policyname = :policy"
        ),
        {"table": table, "policy": POLICY_NAME},
    ).first()
    return row is not None
