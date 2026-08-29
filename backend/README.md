# Quorum — Backend

REST API for Quorum, a multi-tenant community operations platform: tenant onboarding, member
and group directories, the event lifecycle from draft to results, announcements, request
tracking, and (from Phase C onward) the statistical Insight Packs in `app/stats/`.

Ported from Campus Connect (`reference/campus-connect/`), Team 003's May 2026 course project, and
renamed and generalized per `docs/GLOSSARY.md`.

**Stack:** FastAPI · SQLAlchemy 2 (async) · PostgreSQL + asyncpg · Alembic · JWT (python-jose) · uv

---

## Quick start

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and a running PostgreSQL instance.

```bash
uv sync                      # install dependencies
cp .env.example .env         # then fill in the values
uv run alembic upgrade head  # create the schema
uv run uvicorn main:app --reload
```

The API is served at `http://localhost:8000`.

## Multi-tenancy

Every tenant-owned table carries `tenant_id`. Almost every route lives under
`/api/t/{slug}/...`; the `{slug}` in the URL must match the `tenant_slug` claim signed into the
caller's JWT or the request 403s before any repository runs a query (`app/core/tenancy.py`).
Postgres row-level security is enabled as defense in depth on top of that check, not instead of
it — see the `alembic/versions/*_tenancy_rls*` migration.

A handful of routes are deliberately global or public and sit outside `/api/t/{slug}`:
`/api/auth/*` (no tenant yet), `/api/tenant/onboarding` (creates the tenant), and the two
`/api/public/*` routers (cross-tenant trending groups, certificate verification).

## Configuration

All five core variables in `.env.example` are required — the app fails to start if any is
missing. Tenant timezone is a per-tenant setting (`Tenant.timezone`), not an environment variable.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Application database. Must use the `postgresql+asyncpg://` scheme |
| `TEST_DATABASE_URL` | Database used by the test suite |
| `JWT_SECRET_KEY` | Token signing key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | Signing algorithm, e.g. `HS256` |
| `FRONTEND_URL` | Allowed CORS origin. Exact scheme + host + port, no trailing slash |

## API documentation

`/docs` (Swagger) and `/redoc` are auto-generated from the code. Authentication is JWT bearer:
get a token from `POST /api/auth/signup` or `POST /api/auth/login` and send it as
`Authorization: Bearer <access_token>`.

## Tests

```bash
uv run pytest
```

Tests run against `TEST_DATABASE_URL` and **drop every table on teardown** — point it at a
throwaway database. `tests/integration/test_tenancy.py` is the isolation suite: a cross-tenant
read must 403 at the API and return zero rows under RLS with the API bypassed.

## Layout

```
main.py             FastAPI app, CORS, global exception handler, tenant route mounting
app/
  api/               routers, one per domain, auth via Security scopes
  services/          business rules and authorization
  repository/        database access; app/repository/base.py is TenantScopedRepository
  models/            SQLAlchemy models and enums
  schemas/           Pydantic request/response models
  exceptions/        AppException subclasses (status code + message)
  core/              config, database, DI wiring, JWT, tenancy dependency
  verticals/         vertical manifest loader + JSON manifests
  agent/             the bounded tool-calling loop, budget caps, grounding
alembic/             migrations
```

Requests flow `api → services → repository`. Services own all business rules; routers only
check the account role (`MEMBER` / `TENANT_ADMIN`), while group-level permissions
(`LEADER` / `MEMBER`) are enforced in the service layer.

## Docker

```bash
docker build -t quorum-backend .
docker run --env-file .env -p 8000:8000 quorum-backend
```

Migrations are not run by the container — apply them separately.
