-- Runs once, automatically, the first time the `postgres` docker-compose
-- service starts against an empty data directory (the official Postgres
-- image's /docker-entrypoint-initdb.d/ convention).
--
-- POSTGRES_USER/POSTGRES_PASSWORD (see docker-compose.yml) create the
-- bootstrap superuser this script runs as; the application itself never
-- connects with that role. `quorum_app` below is the same non-superuser,
-- RLS-subject role backend/.env.example already documents for a real
-- deployment (Postgres row-level security is enforced with FORCE ROW LEVEL
-- SECURITY, which a superuser connection always bypasses regardless of the
-- policy - see app/core/rls.py - so the app must never connect as the
-- bootstrap role or the whole tenancy isolation story becomes untested).
CREATE ROLE quorum_app LOGIN PASSWORD 'quorum_app_local_password';
GRANT ALL PRIVILEGES ON DATABASE quorum_dev TO quorum_app;
GRANT ALL ON SCHEMA public TO quorum_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO quorum_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO quorum_app;

-- A throwaway database for `uv run pytest` if anyone runs the suite inside
-- the backend container; TEST_DATABASE_URL points here and the suite drops
-- every table on teardown, so this must never be the same database as
-- quorum_dev.
CREATE DATABASE quorum_test OWNER quorum_app;
GRANT ALL PRIVILEGES ON DATABASE quorum_test TO quorum_app;

\connect quorum_test
GRANT ALL ON SCHEMA public TO quorum_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO quorum_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO quorum_app;
