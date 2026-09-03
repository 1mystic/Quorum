# Running Quorum locally

The fast path is `docker compose up` from the repo root (see `README.md`). This is the manual
path, for when you want the two services running separately, or Docker is not available.

## Backend

```bash
cd backend
uv sync
cp .env.example .env
```

Fill in `.env`. At minimum, for local dev:

- `DATABASE_URL` - a Postgres 16+ instance, `postgresql+asyncpg://` scheme. Either a local
  Postgres you already have, or Neon's free tier (create a project, copy the connection string,
  rewrite `sslmode=require&channel_binding=require` to `ssl=require` - asyncpg has no
  `sslmode`/`channel_binding` connect kwarg and SQLAlchemy passes URL query params straight
  through, so the string Neon gives you crashes unmodified).
- `TEST_DATABASE_URL` - a second, throwaway database. Every table is dropped on teardown; never
  point this at the same database as `DATABASE_URL`.
- `JWT_SECRET_KEY` - `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
- `FRONTEND_URL` - `http://localhost:5173` for local dev.

Everything else in `.env.example` has a safe default or degrades gracefully when left blank (no
AI provider key runs the assistant in deterministic mock mode; no S3 credentials falls back to
storing certificate PDFs in Postgres itself; no SMTP credentials just means password-reset email
never actually sends, though the flow itself still runs).

```bash
uv run alembic upgrade head
uv run python scripts/seed_demo.py   # optional - loads the two demo tenants below
uv run uvicorn main:app --reload
```

`scripts/seed_demo.py` must run from `backend/` with `PYTHONPATH=.` if invoked any other way
(`uv run python scripts/seed_demo.py` from `backend/` already has this set correctly by `uv`).

## Frontend

```bash
cd frontend
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://localhost:8000/api
npm install
npm run dev
```

Open `http://localhost:5173`.

## Demo tenants

`scripts/seed_demo.py` builds two realistic, fully worked-through tenants with real computed
`Evidence` (not placeholder numbers) so every Insight Pack page has something genuine to show
on first login:

- **Vaikunth Heights** (`vaikunth-heights`, `rwa_society` vertical) - 60 residents, a Managing
  Committee group, months of raised/resolved/escalated maintenance requests, due cycles with
  payments and receipts at realistic collection/verification rates, general body meetings and a
  festival event with attendance, and a nudge-reminder experiment.
- **Aavartan Robotics** (`aavartan-robotics`, `campus_club` vertical) - a smaller campus club
  with the equivalent shape: members, groups, requests, events, ledger activity.

Every seeded account, admin and member alike, uses the password **`Demo12345!`**. Admin logins
are `admin@vaikunth-heights.demo` and `admin@aavartan-robotics.demo`; members run
`resident1@vaikunth-heights.demo` through `resident60@...`, and `member1@aavartan-robotics.demo`
through `member90@...`.

## Running the tests

```bash
cd backend && uv run pytest        # heavier - prefer scoped runs on a modest machine, e.g.
                                    # uv run pytest tests/integration/test_request.py
cd frontend && npm run test
```

## Local Postgres without Docker or root

If you have neither Docker nor an existing Postgres and cannot install packages system-wide:

```bash
mkdir pgtest && cd pgtest
apt-get download postgresql-16 postgresql-client-16 postgresql-common postgresql-client-common libpq5
for f in *.deb; do dpkg-deb -x "$f" extracted; done
export LD_LIBRARY_PATH="$PWD/extracted/usr/lib/x86_64-linux-gnu:$PWD/extracted/usr/lib/postgresql/16/lib"
extracted/usr/lib/postgresql/16/bin/initdb -D pgdata -U postgres --auth=trust
extracted/usr/lib/postgresql/16/bin/pg_ctl -D pgdata -o "-p 5544 -k $PWD" -l logfile start
extracted/usr/lib/postgresql/16/bin/createdb -h $PWD -p 5544 -U postgres quorum_dev
extracted/usr/lib/postgresql/16/bin/createdb -h $PWD -p 5544 -U postgres quorum_test
```

Then create a non-superuser role for the app to actually connect as (a superuser bypasses row-
level security unconditionally, which would make the tenant-isolation tests pass vacuously):

```sql
CREATE ROLE quorum_app LOGIN;
GRANT ALL ON SCHEMA public TO quorum_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO quorum_app;
```

`DATABASE_URL=postgresql+asyncpg://quorum_app@127.0.0.1:5544/quorum_dev`.
