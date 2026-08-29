# Working agreement — read this first, every session

You are working on **Quorum** (working name), a multi-tenant community operations platform whose
differentiator is a **real statistical engine**, not CRUD and not an LLM wrapper.

> **Thesis: the LLM narrates; statistics decide.**

All work stays inside `/home/mystic1/Projects/RWA`. Never write outside it.

---

## The five rules that do not bend

1. **Commit messages are 1–2 lines.** `feat: kaplan-meier resolution curves`. No bodies, no bullet
   lists, no trailers.
2. **Never write `Co-Authored-By`, and never mention Claude, Anthropic, or any AI tool** in a commit
   message, PR body, code comment, or doc. The history is ours.
3. **Commit directly to `main`.** No feature branches, no PR ceremony. (Campus Connect's `RULES.md`
   branching playbook is deliberately *not* adopted — it was a course team's process.)
4. **`backend/app/stats/` is pure.** Zero DB access, zero network, deterministic over
   arrays/dataclasses. Services fetch; `stats/` does mathematics. This is what makes it testable.
5. **No bare numbers.** Every statistic crosses the API as an `Evidence` envelope carrying `n`,
   an interval, its method id, assumption checks, and `insufficient_data`. The UI must not render a
   figure without one, and the AI agent may only *narrate* an envelope — never compute or
   recompute a statistic itself.

---

## Cold start: how to pick up work

1. Read **`CONTEXT.md`** — current phase, what's done, what's in flight, decision log.
2. Read your card in **`docs/WORKPLAN.md`** — take the topmost unblocked one for your role.
3. Do the work.
4. Run the card's **acceptance gates**.
5. **Update `CONTEXT.md`** and tick the card.

*An agent that stops without updating `CONTEXT.md` has not finished.*

---

## Where everything lives

| Path | What |
|---|---|
| `PLAN.md` | Canonical plan — what we're building and why. Read once. |
| `CONTEXT.md` | Living state + decision log. **Read every session, update before stopping.** |
| `docs/WORKPLAN.md` | The task board. |
| `docs/RULES.md` | Full engineering policy and the test gates. |
| `docs/GLOSSARY.md` | Domain + statistical vocabulary, and the Campus Connect rename table. |
| `docs/DATA_SPINE.md` | The six canonical streams every vertical maps onto. |
| `docs/STATS_CATALOG.md` | The four Insight Packs, service by service, with Method Cards. |
| `docs/EVIDENCE_CONTRACT.md` | The `Evidence` envelope spec. |
| `reference/campus-connect/` | The Team-003 port source. **Read-only — never edit in place.** |
| `reference/vibecurb/skills/` | VibeCurb design protocols for Phase B. |
| `RWA_Master_Context.md`, `RWA-Focused-Project-Plan.md` | **Historical research.** The interview findings are gold; the scope decisions are void. Not requirements. |
| `backend/`, `frontend/`, `design/` | The product. |

---

## Build order (fixed)

**0** governance kit → **A** design the statistical services → **B** brand kit + UI system via
VibeCurb → **C** port and adapt Campus Connect.

Do not start Phase C code before Phase A's catalog exists. The whole point of the ordering is that
the data model falls out of the statistics, not the other way round.

---

## Architecture in six lines

- **Backend** FastAPI · async SQLAlchemy 2 · Postgres + `pgvector` · Alembic · JWT.
- **Layering** `api → services → repository`. Services own business rules; routers only check role.
- **Stats** `app/stats/` pure functions → `Evidence` → materialized into `insight_runs` by a worker.
- **Tenancy** every table has `tenant_id`; `TenantScopedRepository` + Postgres RLS. Routes are
  `/api/t/{slug}/…` and the slug must match the JWT claim.
- **Frontend** Vue 3 · Vite · Pinia · one tokenized stylesheet. Never hard-code a color.
- **Deploy** `web` (light) anywhere · `worker` (scientific stack) on a real box · frontend on Vercel
  · Neon/Supabase for Postgres. Nothing in code assumes a host.

## Running things

```bash
cd backend  && uv sync && uv run alembic upgrade head && uv run uvicorn main:app --reload
cd frontend && npm install && npm run dev
cd backend  && uv run pytest
cd frontend && npm run test
```

Secrets live in `.env`, never committed. `.env.example` is the contract.
