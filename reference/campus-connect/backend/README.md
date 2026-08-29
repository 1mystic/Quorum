# Campus Connect — Backend

REST API for Campus Connect, a student club management platform for higher education
institutions: club discovery and membership, the event lifecycle from draft to results,
announcements, and member issue tracking.

Team 003 (Nexmind) · BSCS3001 Software Engineering Project, May 2026.

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

## Configuration

All five variables in `.env.example` are required — the app fails to start if any is missing.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Application database. Must use the `postgresql+asyncpg://` scheme |
| `TEST_DATABASE_URL` | Database used by the test suite |
| `JWT_SECRET_KEY` | Token signing key. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `JWT_ALGORITHM` | Signing algorithm, e.g. `HS256` |
| `FRONTEND_URL` | Allowed CORS origin. Exact scheme + host + port, no trailing slash |

## API documentation

| Where | What |
|---|---|
| `/docs` | Swagger UI (auto-generated from the code) |
| `/redoc` | ReDoc |
| `openapi.yaml` | Hand-authored OpenAPI 3.1 spec — full endpoint descriptions, user story mapping, role matrix and error catalogue |

Authentication is JWT bearer. Get a token from `POST /auth/signup` or `POST /auth/login` and
send it as `Authorization: Bearer <access_token>`.

## Tests

```bash
uv run pytest
```

Tests run against `TEST_DATABASE_URL` and **drop every table on teardown** — point it at a
throwaway database.

## Layout

```
main.py            FastAPI app, CORS, global exception handler
app/
  api/             routers — one per domain, auth via Security scopes
  services/        business rules and authorization
  repository/      database access
  models/          SQLAlchemy models and enums
  schemas/         Pydantic request/response models
  exceptions/      AppException subclasses (status code + message)
  core/            config, database, DI wiring, JWT
alembic/           migrations
openapi.yaml       API specification
```

Requests flow `api → services → repository`. Services own all business rules; routers only
check the account role (`STUDENT` / `CAMPUS_ADMIN`), while club-level permissions
(`LEADER` / `MEMBER`) are enforced in the service layer.

## Docker

```bash
docker build -t campusconnect-backend .
docker run --env-file .env -p 8000:8000 campusconnect-backend
```

Migrations are not run by the container — apply them separately.
