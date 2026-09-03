# All-in-One Community Platform — Statistics-First Build Plan

> Canonical "what we are building and why". Read this once; then live in `CONTEXT.md` and `docs/WORKPLAN.md`.

## Context

`/home/mystic1/Projects/RWA` previously held two planning docs (now `reference/historical/RWA_Master_Context.md`, `reference/historical/RWA-Focused-Project-Plan.md`) for a narrow, course-scoped RWA/society app: complaints, dues, events, one GenAI categorization call. That scope was deliberately cut to survive an instructor feasibility review. **Those two files are historical research, not requirements**: the interview findings in them are still gold, the scope decisions are void.

We are now building something different and larger: **a general community operations platform**, multi-tenant by slug, where any kind of community — housing society, campus club, NGO, alumni chapter, co-op, sports club, professional guild — onboards and switches on the services it needs.

**This is our own product.** No course milestones, no team-file deliverables, no instructor feasibility review, no five-way role split to design around. Nothing is scoped down to be defensible to a grader. That changes real decisions: we take the heavy scientific stack instead of hand-rolling statistics to stay slim, we split web/worker instead of forcing one 512 MB box, we add background jobs and a materialization layer, we require dark mode and a real motion system, and we ship the packs in the order that makes the *product* strongest rather than the order that fills a sprint report.

The differentiator is **not** CRUD and not agentic AI. Those are table stakes. The differentiator is that the platform is a **statistical instrument for communities**: it treats every community as a stream of observable processes and applies real inferential machinery — survival analysis, statistical process control, queueing theory, empirical-Bayes shrinkage, calibrated forecasting, conformal prediction, social-choice theory, privacy-preserving aggregation — to answer questions communities actually cannot answer today.

> **The one-line thesis: the LLM narrates; statistics decide.**

Three existing assets feed this:

- **[MAY2026-Team-003](https://github.com/Srivastava-Shrestha/MAY2026-Team-003)** ("Campus Connect") — a genuinely well-built FastAPI + Vue 3 platform. Async SQLAlchemy 2, Alembic, JWT, clean `api → services → repository` layering, a 9,338-line design system, a bounded read-only AI agent loop with a *pure deterministic core* (`app/agent/recommender.py`), certificates with QR verification, notifications, `pgvector` already a dependency, and — critically — `College.slug` already exists. **This is our port source.**
- **`reference/historical/design-sources.zip`** → VibeCurb skill pack (`brandkit-gen`, `awwwards-hero`, `awwwards-sections`, `awwwards-motion`, `visual-redesign`, `pixel-perfect`, `imagegen-frontend`). Strict design protocols we run the branding phase through.
- **sangam-club.com** — adjacent reference (IITM club ops, six modules, role-based dashboards, minimalist warm aesthetic). Useful for vertical manifests and IA, not for copying.

**Build order is fixed:** (0) governance → **(A) design the statistical services** → **(B) brand kit + UI system via VibeCurb** → **(C) port and adapt Campus Connect code**.

---

## Phase 0 — Context & Governance Layer

Everything below is long-running work that many different agent sessions will touch. Each new session starts cold. So before any design or code, we lay down a **cold-start context kit**, so any subagent or LLM picks up state, rules and its next task in one read.

| File | Purpose |
|---|---|
| `PLAN.md` | This file. What we are building and why. |
| `CLAUDE.md` | Auto-loaded by every session. Short by design: product, build order, non-negotiable rules, pointers. |
| `CONTEXT.md` | Living state: current phase, done / in-flight / blocked, and a dated decision log. **The one file an agent must update before it stops.** |
| `docs/RULES.md` | Engineering policy: git rules, stats purity rule, Evidence rule, tenant scoping, secrets, test gates. |
| `docs/WORKPLAN.md` | The task board. Numbered cards with owner-agent, dependencies, acceptance criteria, status. |
| `docs/GLOSSARY.md` | Domain + statistical vocabulary, and the Campus Connect → new-name rename table. |

### Git rules (ours — Campus Connect's `RULES.md` playbook is explicitly **not** adopted)

No `feature/*` → `dev` → `main` tiering, no PR requirement, no daily-sync ritual. That was a five-person course team's process; it does not apply to us.

1. **Agents commit directly to `main`.** No branches unless a specific experiment genuinely warrants one.
2. **Commit messages are 1–2 lines. Never longer.** `feat: kaplan-meier resolution curves` — no bullet lists, no body paragraphs, no trailers.
3. **Never add a `Co-Authored-By` line, and never mention Claude, Anthropic or any AI tool** in a commit message, PR body, or code comment. The history is ours.

### The agent roster — `.claude/agents/`

- **`supervisor`** — owns `docs/WORKPLAN.md` and `CONTEXT.md`. Reads state, picks the next unblocked card, delegates, *verifies acceptance criteria were actually met rather than claimed*, updates the board and decision log. **Never writes feature code itself.**
- **`statistician`** — owns `backend/app/stats/`. Pure functions only; every public function returns `Evidence`; every service ships a Method Card and is tested against a known answer.
- **`brand-designer`** — owns `design/`. Runs the VibeCurb protocols; holds the anti-slop bans and the token contract.
- **`backend-porter`** — owns the Campus Connect port, the rename pass, tenant scoping and RLS.
- **`frontend`** — owns `frontend/`. Consumes tokens, never hard-codes a color; renders no figure without its `Evidence`.
- **`reviewer`** — read-only. Runs the gates before a card closes.

**Handoff protocol:** read `CONTEXT.md` → read the card in `docs/WORKPLAN.md` → do the work → run the card's gates → update `CONTEXT.md` and tick the card. *An agent that stops without updating `CONTEXT.md` has not finished.*

---

## Phase A — The Statistical Service Layer (design first, code later)

### A1. The Canonical Data Spine — the idea that makes this cheap

The failure mode of "stats for every community type" is writing survival analysis once for complaints, again for volunteer tasks, again for membership applications. We avoid it by defining **six vertical-agnostic streams**. Every community type maps its domain entities onto these via a thin adapter; **every statistical service is written once, against the stream**.

| Stream | Shape | Feeds |
|---|---|---|
| `member_lifecycle` | join / activate / lapse / exit events per member | survival, cohort retention, churn risk |
| `request_flow` | anything with `open → assign → progress → resolve/close`, with category, owner, timestamps | survival, SPC, queueing, changepoint, conformal ETA |
| `ledger` | signed money movements with category + counterparty (dues, contributions, expenses) | forecasting, runway, Benford, DP aggregates |
| `participation` | attendance, RSVP, login, upvote, volunteer hours | engagement, segmentation, network |
| `signal` | free text + ordinal ratings (complaint bodies, surveys, feedback) | topic mining, near-dup detection, ordinal models |
| `decision` | polls, ballots, budget allocations | social choice, participatory budgeting, representativeness |

Deliverable: `docs/DATA_SPINE.md` + `backend/app/stats/streams/` (typed dataclasses + per-vertical adapters).

### A2. The Evidence Contract — no bare numbers, ever

Every statistical service returns one typed envelope, and the UI is **structurally incapable** of rendering a figure without it:

```python
@dataclass(frozen=True)
class Evidence:
    value: float | dict | list
    interval: tuple[float, float] | None      # CI or credible interval
    interval_kind: str                         # "bootstrap-bca" | "credible-95" | "conformal-90"
    n: int
    method: str                                # registry id → links to a Method Card
    assumptions: list[str]
    assumption_checks: list[Check]             # each PASS / WARN / FAIL with a stat
    caveats: list[str]
    insufficient_data: bool                    # below min-n → UI greys out, agent must say so
    as_of: datetime
    params_hash: str                           # reproducibility
```

Two consequences that make the product defensible:

1. **The agent cannot compute statistics.** Its tools return `Evidence` envelopes only; it narrates them. This extends the grounding pattern already in Campus Connect's `app/agent/grounding.py` and `app/agent/tools.py` (read-only registry, no identity params, allow-list entity substitution) — we reuse that machinery.
2. **Method Cards.** Each service ships a card: what it assumes, when it is wrong, what n it needs, references. Rare, cheap, and it is the trust story.

### A3. Insight Packs — what the tenant slug actually switches on

A **pack** is a bundle with `id`, `verticals[]`, `required_streams[]`, `min_n`, `cadence`, and its services. Onboarding: pick vertical → get default packs → toggle individually. Stored as `Tenant.enabled_packs jsonb`.

#### Pack 1 — **Reliability & Service Ops** (`request_flow`)
*For: RWA maintenance, club issue queues, NGO case work, any helpdesk.*

- **Kaplan–Meier resolution curves** with **correct right-censoring** — open tickets are censored, not dropped. Every naive dashboard gets this wrong and systematically understates resolution time; this alone is a demonstrable correctness win. Log-rank test across categories / blocks / assignees.
- **Cox proportional hazards** with time-varying covariates → interpretable hazard ratios ("plumbing resolves 2.1× slower in monsoon, HR 2.11, 95% CI [1.4, 3.2]"). Schoenfeld residual test as an automatic assumption check.
- **Competing risks** (Aalen–Johansen) for `resolved` vs `escalated` vs `withdrawn`.
- **SPC control charts** — EWMA and CUSUM on arrival and resolution rates, limits tuned to a target ARL, not a lazy ±3σ. Answers "is this week actually unusual, or is it noise?"
- **Changepoint detection** (PELT / binary segmentation) on volume → "something changed on 12 Aug", with a p-value.
- **Queueing** — M/M/c and M/G/1 approximations for committee capacity; **Little's Law** turning backlog into expected wait; **Erlang-C** staffing for a target SLA ("to close 90% within 5 days you need 4 active resolvers, you have 2").
- **Workload fairness** — Hungarian algorithm for balanced assignment; Gini on the workload distribution.

#### Pack 2 — **Bayesian Ranking & Experimentation** (`request_flow`, `participation`, `ledger`)
*For: leaderboards, vendor selection, nudge policy — anywhere small samples get ranked.*

- **Beta-Binomial empirical Bayes shrinkage** on rates. Kills the "vendor resolved 3/3, therefore #1" pathology every community leaderboard has. Report shrunk estimate + credible interval; rank by posterior lower bound. Gamma-Poisson equivalent for count rates.
- **Hierarchical partial pooling across tenants** — the prior is learned from *all* communities on the platform. A single-society app structurally cannot do this; it is a platform-scale advantage and a real reason to be multi-tenant.
- **Bayesian A/B** on nudges (copy, channel, send hour): Beta posteriors, `P(A > B)`, expected loss, with a stopping rule that is not peeking.
- **Thompson sampling bandit** for reminder policy, with a **freeze-and-report** mode so a committee can see and explain why the system chose what it chose.
- **Bradley–Terry / Elo** for pairwise comparisons (competitions, vendor head-to-heads, ranked preferences).

#### Pack 3 — **Forecasting & Calibrated Risk** (`ledger`, `request_flow`, `participation`)
*For: treasury, budget runway, dues chasing, resident-facing ETAs.*

- **STL decomposition** (trend / seasonal / remainder) on dues collection, complaint volume, attendance — separates "festival season" from "we have a problem".
- **Holt–Winters / local-linear-trend state space**, SARIMA where warranted, **always with prediction intervals**.
- **Backtesting gate** — rolling-origin CV, MASE against a seasonal-naive baseline. A forecast that cannot beat naive is **not shipped**; the pack reports the comparison in the UI.
- **Budget runway & shortfall probability** via Monte Carlo over the predictive distribution: "68% chance the sinking fund is short before March".
- **Calibrated risk models** — late-payment and disengagement risk via regularized logistic + gradient boosting, then **isotonic/Platt calibration**, reported with **Brier score and a reliability diagram**, not a vanity AUC. A "30% risk" bucket must actually default ~30% of the time.
- **Conformal prediction** for resolution-time ETA — distribution-free, guaranteed 90% coverage, shown to the resident as "2–9 days" instead of a fake point estimate.
- **Drift monitoring** — PSI / KS on feature distributions; a stale model is flagged, not silently trusted.

#### Pack 4 — **Governance, Segmentation & Text** (`decision`, `participation`, `signal`)
*For: elections, participatory budgeting, surveys, member insight.*

- **Social choice** — Condorcet / Schulze, Borda, Approval, STV. Show the pairwise matrix; **disclose Condorcet cycles** rather than hiding them behind a winner.
- **Participatory budgeting** — Method of Equal Shares plus greedy knapsack, with a **fairness report** showing which member strata got their preferences funded.
- **Representativeness & quorum** — turnout against population strata; **raking / post-stratification weights** and a reported **design effect**, so a 12% turnout poll is presented honestly instead of as fact.
- **Sortition** — stratified random selection of a demographically representative committee.
- **Segmentation** — RFM-style engagement features → GMM / k-means with **BIC + silhouette model selection** and stable label assignment across runs (so "Segment 3" means the same thing next month).
- **Network statistics** — Louvain community detection and betweenness centrality on the interaction graph → surfaces isolated members and informal connectors.
- **Text** — TF-IDF + `pgvector` embeddings for **near-duplicate detection at submission time** ("3 neighbours already reported this"), MinHash/LSH for scale, NMF topic mining over resolved issues, ordinal logistic regression on Likert items.
- **Privacy** — k-anonymity thresholds and Laplace **differential-privacy noise** on small-cell aggregates, so per-block or per-household statistics cannot re-identify a household. Non-negotiable for a housing vertical.

### A4. Verticals (configuration, not code)

`backend/app/verticals/*.py` manifests: entity labels, default packs, default request categories, role set, auth mode, onboarding copy. Ship: `rwa_society`, `campus_club`, `ngo_volunteer`, `alumni_chapter`, `housing_coop`, `sports_club`, `professional_guild`.

**Phase A deliverables:** `docs/DATA_SPINE.md`, `docs/STATS_CATALOG.md`, `docs/EVIDENCE_CONTRACT.md`, `docs/VERTICALS.md`.

---

## Phase B — Brand & Design System (VibeCurb-driven)

Run **brandkit-gen Phases 1–3** (strategy → identity architecture → composition) and the **awwwards-hero / -sections / -motion** constraint rules.

> **Honest constraint:** `brandkit-gen` is explicitly an *image-generation* skill and no image-generation tool is available in the current environment. The identity therefore ships as **hand-authored SVG under the VibeCurb constraint discipline** (3-primitive logo cap, favicon gate, one-sentence geometry rule, anti-slop bans), not as AI-generated brand boards. The strategy brief we produce is the exact input for a later image-gen session if wanted.

1. **Naming.** Working name **Quorum** — it means both "enough people to decide" and, statistically, "enough data to conclude". That double meaning *is* the product. Alternates: **Chaupal** (the village square where a community gathers to decide — warmer, distinctly Indian), **Sabha**. Locked at the top of Phase B.
2. **Brand strategy brief** — positioning, the two audiences (the resident who wants their tap fixed; the secretary who wants to know if the vendor is actually better), personality axes, brand-to-symbol mapping.
3. **Identity architecture** — visual mode, palette structure, typography character, logo concept. Direction: **evolve, do not discard** Campus Connect's warm paper canvas (`--color-canvas: #FCFBFA`, terracotta `#EF7B45`, `Outfit` + `Plus Jakarta Sans`). It is already personal rather than corporate-SaaS, which is exactly the "modern yet personal" brief. Changes: a more editorial type pairing for a data-forward product, and a **disciplined, separate dataviz palette** (chart color is a different system from brand color).
4. **Dark mode is required.** The current system is light-only. Tokens get full light + dark role definitions.
5. **Motion spec** from `awwwards-motion`: locked motion personality, easing palette (no CSS keyword easings), timing sheet, stagger choreography, `prefers-reduced-motion` compliance.
6. **Deliverables** in `design/`: `brand/logo/*.svg` (primary, stacked, mark, favicon — must survive the favicon gate at 16px) · `tokens.css` + `tokens.json` · `BRAND.md` · `MOTION.md` · a **design-canvas Artifact** with artboards for logo lockups, palette, type specimen, component sheet, tenant home, request detail with conformal ETA + survival curve, Insight Pack dashboard, decision console, and mobile screens.

---

## Phase C — Port & Build

### C1. Scaffold and rename

Copy the Team-003 tree as the base, then apply one consistent rename pass:

| Campus Connect | New |
|---|---|
| `College` | `Tenant` (keeps `slug`, gains `vertical`, `enabled_packs`, `settings`) |
| `Student` | `Member` |
| `CampusAdmin` | `TenantAdmin` |
| `Club` | `Group` |
| `Issue` | `Request` (generalized to the `request_flow` stream) |
| `Membership`, `Event`, `Announcement`, `Certificate`, `Notification` | unchanged |
| — | **new:** `Ledger` (Due/Payment/Receipt/Contribution/Expense), `Decision` (Poll/Ballot/Allocation), `Survey`, `InsightRun` |

**Port with minimal change:** `app/core/` (config, database, di, token, mailer, storage), `app/exceptions/`, the auth stack, `app/agent/` (loop, budget, grounding, providers, tools, memory, intent), the `frontend/src/` skeleton (router, stores, composables — `useToast`, `useFormValidation`, `useLoadingBar`, `useChipFilter` are directly reusable), and `frontend/src/assets/style.css` retokenized against the new brand.

### C2. Multi-tenancy, done properly

- Every table carries `tenant_id`. A `TenantScopedRepository` base class makes an unscoped query impossible to write by accident.
- **Postgres RLS** as defense-in-depth, not as the only line.
- Routes `/api/t/{slug}/…`; JWT carries `tenant_id`; the slug in the URL **must** match the token claim or 403.
- Isolation is a test suite, not a comment.

### C3. The stats engine

```
backend/app/stats/
  contracts.py     Evidence, Check, MethodCard, InsufficientData
  registry.py      pack + service registry — same shape as app/agent/tools.py
  streams/         canonical dataclasses + per-vertical adapters + feature builders
  survival.py  spc.py  queueing.py                        ← Pack 1
  bayes.py  experiments.py  bandits.py                    ← Pack 2
  forecast.py  calibration.py  conformal.py  drift.py     ← Pack 3
  voting.py  budgeting.py  survey.py  segmentation.py  network.py  text.py   ← Pack 4
  privacy.py
  jobs.py          materialization scheduler
```

**Hard rule, mirroring `app/agent/recommender.py`:** every module here is **pure and deterministic over arrays/dataclasses, with zero DB access and zero network**. Services do the fetching; `stats/` does the mathematics. This is what makes the layer unit-testable offline against analytically known answers.

**Materialization:** an `insight_runs` table (`tenant_id, pack, service, params_hash, payload jsonb, computed_at`). The API serves cached runs; a worker recomputes on the pack's cadence. Request latency stays flat and a small box survives.

**Agent integration:** new read-only tools that return `Evidence` envelopes. The system prompt forbids the model from doing arithmetic on them.

### C4. Deployment — portable by construction

Two services sharing one database, so the heavy half can move independently:

- **`web`** — light: FastAPI, no scientific stack. Runs anywhere (Render free, Fly, HF Spaces).
- **`worker`** — heavy: numpy, scipy, pandas, scikit-learn, statsmodels, lifelines (~500 MB). Needs real memory.
- **Frontend** — Vercel.
- **Database** — Neon or Supabase (Postgres + `pgvector`, both free-tier).

Everything 12-factor + Docker. Concretely: Oracle Cloud Always Free (4 ARM cores / 24 GB) is the only free tier that runs the worker comfortably; Hugging Face Spaces Docker (16 GB, no spin-down) is the pragmatic fallback; Render free can host `web` but not `worker`. Pick at deploy time — nothing in the code assumes a host.

### C5. Build order

1. Tenant + auth + RLS + member directory (ported, renamed) — the spine.
2. `request_flow` end to end + **Pack 1** — the demo that sells the whole thesis.
3. `ledger` + **Pack 3**.
4. `participation` + `decision` + **Pack 4**.
5. **Pack 2** last — it needs accumulated data to be meaningful.
6. Agent stats tools + narration.

---

## Verification

**Stats correctness — the part that must not be hand-waved.** Because `app/stats/` is pure, each service is tested against a *known* answer, not a snapshot:

- Kaplan–Meier and Cox against the standard `rossi` recidivism dataset (published coefficients).
- Erlang-C against published staffing tables.
- Schulze/Condorcet against textbook cases **including a deliberate Condorcet cycle**.
- Beta-Binomial shrinkage against a closed-form posterior.
- Conformal prediction: empirical coverage on held-out synthetic data within tolerance of the nominal 90%.
- Forecasting: a **gate** — every shipped forecaster must beat seasonal-naive on MASE over rolling-origin CV.
- Calibration: a **gate** on Brier score and reliability-diagram deviation.
- Censoring regression test: a fixture where naive mean-of-closed and Kaplan–Meier diverge, asserting we report the KM figure.

**Everything else:**

- `uv run pytest` — tenant-isolation suite (cross-tenant read must 403 at the API *and* return zero rows under RLS), state machines, auth.
- `npm run test` (Vitest) — ported composables and stores.
- OpenAPI auto-generated at `/docs`.
- Agent grounding tests: a prompt-injection fixture in a request body must not move any tool call or fabricate an `Evidence` value.
- End to end: seed a demo tenant per vertical, run the worker, walk the UI — request intake shows near-duplicates, the detail page shows a conformal ETA, the Insight dashboard shows a KM curve with CI and an Erlang-C staffing recommendation, and every figure carries `n` and a Method Card link.

---

## Open items to settle in flight

- Final product name (Quorum / Chaupal / Sabha) — top of Phase B.
- Whether to keep the certificate + QR subsystem (strong for clubs and volunteer orgs, dead weight for RWA) — leaning keep, as a togglable module, since it is already built and tested.
- Auth: Campus Connect uses email + password + Google. The RWA research argued hard for phone + OTP. Leaning support both, selected per vertical manifest.
