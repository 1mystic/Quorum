# Running Quorum locally

Two paths. Docker is the fastest way to see the product with real, demo data
already loaded. The manual path is for anyone without Docker, or for
backend/frontend development where you want fast reload loops.

---

## Path 1: Docker

Requires only Docker and Docker Compose. Nothing else needs to be installed.

```bash
docker compose up
```

This brings up four containers:

| Service | What | Port |
|---|---|---|
| `postgres` | Postgres 16, with the non-superuser `quorum_app` role Postgres row-level security is enforced against | `5544` |
| `backend` | The API: runs migrations, seeds the two demo tenants if the database is empty, then serves FastAPI | `8000` |
| `worker` | Runs the same materialization worker on a loop (`scripts/materialize_insights.py`), so Insight Pack figures stay fresh the same way a real deployment's worker tier would | - |
| `frontend` | `npm run dev` against the backend above | `5173` |

Once it says the frontend is ready, open **http://localhost:5173**. Two demo tenants are already
seeded:

| Tenant | Slug | Vertical | Admin login |
|---|---|---|---|
| Vaikunth Heights | `vaikunth-heights` | `rwa_society` | `admin@vaikunth-heights.demo` |
| Aavartan Robotics | `aavartan-robotics` | `campus_club` | `admin@aavartan-robotics.demo` |

Password for every seeded account (admin and every member) is **`Demo12345!`**. Member accounts
follow the pattern `resident1@vaikunth-heights.demo` .. `resident60@...` and
`member1@aavartan-robotics.demo` .. `member90@...` (see `backend/scripts/seed_demo.py` for the
exact roster).

The seed script populates six-plus months of realistic `request_flow`, `ledger`, `participation`
and `decision` history for both tenants, including a genuine Condorcet cycle in one poll, a
real STV committee election, a participatory budget allocation, and a deliberate volume
changepoint for the changepoint detector to find. It then runs the real statistical worker and
several Insight Pack figures (Kaplan-Meier resolution curves, control charts, changepoint
detection, workload fairness, request-volume forecasting) are already computed and cached in
`insight_runs` by the time the frontend loads - open a tenant's Insights pages to see them.

### Rebuilding, resetting, stopping

```bash
docker compose up --build      # after changing a Dockerfile or dependency
docker compose down            # stop everything, keep the data volume
docker compose down -v         # stop everything AND wipe the database volume
```

Running `docker compose up` again after `down` (without `-v`) reuses the existing Postgres
volume; the backend container's entrypoint only seeds a database that has zero tenants, so your
data survives a restart. `down -v` gives you a fully fresh demo on the next `up`.

To re-run the demo seed on a database that already has other tenants in it (without wiping
everything), run the seed script directly - it always rebuilds its own two tenants and leaves
anything else alone:

```bash
docker compose exec backend python scripts/seed_demo.py
```

### What's genuinely fake here

Every credential-shaped environment variable in `docker-compose.yml` is a fixed, clearly-labelled
placeholder (AWS keys, SMTP credentials, the JWT secret). This is intentional: the point of the
Docker path is zero setup. Password-reset emails and S3 certificate uploads will not actually
send/upload in this configuration; certificate PDFs fall back to being stored in Postgres itself
and served through the API, which the app already handles as a normal degraded path (see
`app/models/certificate.py`). Do not reuse these values for a real deployment - see
`backend/.env.example` for what a real deploy needs instead.

---

## Path 2: Manual (no Docker)

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, and a Postgres 16 instance you
control.

### 1. Postgres

Create a database and a **non-superuser** role for the app to connect as - this matters because
Postgres row-level security (`FORCE ROW LEVEL SECURITY`, see `app/core/rls.py`) is always bypassed
by a superuser connection, and the whole point of the tenancy isolation tests is to prove RLS
actually holds:

```sql
CREATE ROLE quorum_app LOGIN PASSWORD 'a-local-password';
CREATE DATABASE quorum_dev OWNER quorum_app;
CREATE DATABASE quorum_test OWNER quorum_app;
```

(If your Postgres user's `public` schema privileges are restrictive by default, also run
`GRANT ALL ON SCHEMA public TO quorum_app;` against both databases - see
`deploy/postgres-init.sql`, which does exactly this for the Docker path.)

### 2. Backend

```bash
cd backend
uv sync
cp .env.example .env
# edit .env: point DATABASE_URL/TEST_DATABASE_URL at the role/databases above
uv run alembic upgrade head
uv run python scripts/seed_demo.py
uv run uvicorn main:app --reload
```

The API is now at `http://localhost:8000`; interactive docs at `/docs`.

To keep Insight Pack figures fresh as you use the app, run the materializer worker in a second
terminal (it loops on `MATERIALIZE_INTERVAL_SECONDS`, default one hour - pass `--once` for a
single pass instead of a loop):

```bash
cd backend
uv run python scripts/materialize_insights.py --once
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env      # only needed if your backend is not on localhost:8000
npm run dev
```

Open `http://localhost:5173`. Sign in with the same seeded accounts as the Docker path (see
above).

### Tests

```bash
cd backend && uv run pytest
cd frontend && npm run test
```

`TEST_DATABASE_URL` is dropped and rebuilt on every test run - never point it at the same
database as `DATABASE_URL`.
