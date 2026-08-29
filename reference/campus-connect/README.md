# Campus Connect
Campus Connect is a multi-user platform that helps colleges run their student clubs end to end. Campus admins onboard the college and approve clubs, club leaders manage members, events and announcements, and students discover clubs, register for events and collect verifiable certificates. It features role-based dashboards, an event lifecycle from draft to declared results, auto-generated certificate PDFs with QR verification, an activity leaderboard, an issue tracker and an AI club-finder assistant.

## 1. Built with

### Backend
- **FastAPI**: An async web framework for the REST API.
- **SQLAlchemy 2**: Async ORM for all database models and queries.
- **PostgreSQL**: The application database.
- **asyncpg**: High performance async Postgres driver.
- **Alembic**: Handles schema migrations.
- **python-jose**: Signs and verifies JWT access tokens.
- **bcrypt**: Hashes user passwords.
- **google-auth**: Verifies Google Sign-In tokens.
- **boto3**: Uploads certificate PDFs to AWS S3.
- **CairoSVG**: Renders certificate templates into PDFs.
- **qrcode**: Generates the verification QR on each certificate.
- **Jinja2**: Templates the certificates and outbound emails.
- **Anthropic**: Powers the AI club-finder assistant.
- **Uvicorn**: ASGI server that runs the app.

### Frontend
- **VueJS 3**: Builds dynamic, reactive user interfaces.
- **Vue Router 4**: Handles client side routing and route guards.
- **Pinia**: Manages application state.
- **Vite**: Provides a fast development environment for VueJS.
- **Lucide-Icons**: Provides a wide set of customizable icons.
- **jwt-decode**: Reads the role and college out of the access token.
- **CSS**: One central design system stylesheet drives all styling.
- **Vitest**: Unit and component testing with Vue Test Utils.

## 2. Installation Steps

### 1. Clone the Repository
```bash
git clone https://github.com/Srivastava-Shrestha/MAY2026-Team-003.git
```

### 2. Change the working directory
```bash
cd MAY2026-Team-003
```

### 3. Install uv
The backend uses [uv](https://docs.astral.sh/uv/) to manage Python 3.12+ and its dependencies.

For Linux/macOS:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
For Windows:
```
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 4. Install Required Backend Package Dependencies
```bash
cd backend
uv sync
```

### 5. Configure the Backend Environment
```bash
cp .env.example .env
```
Then fill in the values. `DATABASE_URL` must use the `postgresql+asyncpg://` scheme, and `JWT_SECRET_KEY` can be generated with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

> ⚠️ Point `TEST_DATABASE_URL` at a throwaway database. The test suite drops every table on teardown, so it must never share a database with `DATABASE_URL`.

### 6. Create the Database Schema
```bash
uv run alembic upgrade head
```

### 7. Run the Backend
```bash
uv run uvicorn main:app --reload
```
The API is served at `http://localhost:8000`, with Swagger UI at `/docs` and ReDoc at `/redoc`.

### 8. Install Frontend Dependencies
In a new terminal window, install frontend dependencies. Node 20+ and npm 10+ are required.
```bash
cd ../frontend
npm install
```

### 9. Configure the Frontend Environment
Create a `.env` file in the `frontend` directory:
```bash
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your-google-oauth-client-id
```
`VITE_GOOGLE_CLIENT_ID` is the OAuth client ID used by the Google Sign-In button, and it must match `GOOGLE_CLIENT_ID` in the backend `.env`. Leave it blank to run without Google Sign-In.

### 10. Run the Frontend Development Server
```bash
npm run dev
```
The app is served at `http://localhost:5173`.

✨ You are all set!
<hr>

## 3. Demo Credentials

Every demo account signs in with the password `12345678`.

| Role | Email | What it demonstrates |
|---|---|---|
| Campus Admin | `shrestha@ds.study.iitm.ac.in` | Club approval queue, all clubs by status, college leaderboard |
| Club Leader | `aarav.menon@ds.study.iitm.ac.in` | Leads CodeCrafters with 5 members. Create and publish events, mark attendance, declare results, answer the issue queue, post announcements |
| Member with Certificates | `sara.khan@ds.study.iitm.ac.in` | Holds 3 certificates covering WINNER, RUNNER_UP and PARTICIPANT, plus notifications and event registrations |

Other demo students, all on `@ds.study.iitm.ac.in`: `diya.sharma`, `kabir.rao`, `ananya.iyer`, `meera.nair`, `rohan.gupta`, `ishita.bose`, `vikram.reddy`, `aditya.verma`, `nikita.joshi`, `arjun.pillai`.

## 4. Demo Details

The demo runs on one full college, **IIT Madras BS Degree**, on the domain `ds.study.iitm.ac.in`. Club names, descriptions, logos and social links are taken from the real IITM BS societies rather than invented.

**Clubs (7)**, covering all four statuses so every admin view has content:

| Status | Clubs |
|---|---|
| ACTIVE | CodeCrafters (Technology), IRIS (Arts & Media), AKORD (Music), RAAHAT (Health & Wellness) |
| PENDING | Women in Tech, waiting in the admin approval queue |
| REJECTED | Heighers eSports, the one UNOFFICIAL club |
| ARCHIVED | Deva-Bhasha Sanskrit Society |

**Events (9)**: 4 completed with attendance marked and results declared, 3 upcoming and open for registration, 1 draft and 1 cancelled. One event carries no capacity limit.

**Certificates (15)**: real PDFs produced by the application's own renderer, each carrying a QR code that resolves to `/verify/<serial>`. 13 are stored on S3 and 2 sit on the Postgres fallback path, so both storage routes can be shown.

**Also available**: 23 memberships across approved, pending and rejected states, 7 announcements spanning all 5 categories with 2 pinned, 6 issues covering all 5 categories and all 3 statuses, 10 notifications across all 5 types, and a leaderboard that ranks the 4 active clubs on real activity scores.

Every column of every table is populated, and every enum value appears at least once.

## 5. Team

Team 003 (Nexmind), BSCS3001 Software Engineering Project, May 2026.

| Member | Role | Commits | PRs (merged) | Branches |
|---|---|---|---|---|
| **Shrestha** | Backend and System Architect | 248 | 32 (27) | 21 |
| **Shrishti** | Frontend | 10 | 12 (10) | 10 |
| **Atharv** | Product Manager | 71 | 13 (13) | 7 |
| **Pawan** | Testing | 46 | 14 (13) | 13 |
| **Kavisha** | Scrum Master | 4 | 0 | 0 |
| `github-actions[bot]` | CI automation | 92 | 0 | 0 |
| | **Total** | **471** | **71 (63)** | **51** |


## 6. Documentation

| Where | What |
|---|---|
| [`backend/README.md`](backend/README.md) | Backend setup, configuration and testing |
| [`frontend/README.md`](frontend/README.md) | Frontend setup, structure and design system |
| [`backend/openapi.yaml`](backend/openapi.yaml) | Full API spec with endpoints, user story mapping, role matrix and error catalogue |
| [`RULES.md`](RULES.md) | Team working agreement |

<hr>
<h3 align="center">
Thank You 🐻
</h3>
