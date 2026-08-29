"""
The Postgres row-level security statements for the tenancy migration
(alembic/versions/*_tenancy_row_level_security.py), factored out so the test
suite can apply the same DDL when it builds the schema via
Base.metadata.create_all instead of `alembic upgrade head` (see
tests/conftest.py's setup_db). Keeping one source of truth here means the
test database's RLS behaviour cannot silently drift from what a real
deployment gets from the migration.
"""

TENANT_SCOPED_TABLES = [
    "tenant_admins",
    "members",
    "groups",
    "events",
    "announcements",
    "notifications",
    "requests",
    "certificates",
    "event_registrations",
    "memberships",
]

POLICY_NAME = "tenant_isolation"
TENANT_FILTER = "tenant_id = current_setting('app.tenant_id', true)::int"


def enable_statements() -> list[str]:
    statements = []
    for table in TENANT_SCOPED_TABLES:
        statements.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        statements.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        statements.append(
            f"CREATE POLICY {POLICY_NAME} ON {table} "
            f"USING ({TENANT_FILTER}) WITH CHECK ({TENANT_FILTER})"
        )
    return statements


def disable_statements() -> list[str]:
    statements = []
    for table in TENANT_SCOPED_TABLES:
        statements.append(f"DROP POLICY IF EXISTS {POLICY_NAME} ON {table}")
        statements.append(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        statements.append(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    return statements
