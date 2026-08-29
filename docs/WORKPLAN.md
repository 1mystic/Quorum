# Work plan — the board

**How to use this.** Take the topmost card for your role whose dependencies are all `DONE`. Do it,
run its gates, tick it, then append to `CONTEXT.md`. Do not start a card whose deps are open.

Status: `TODO` · `WIP` · `BLOCKED` · `DONE`

---

## Phase 0 — Governance

| # | Card | Owner | Deps | Status |
|---|---|---|---|---|
| 0.1 | `PLAN.md`, `CLAUDE.md`, `docs/RULES.md` written | supervisor | — | DONE |
| 0.2 | `docs/WORKPLAN.md`, `CONTEXT.md`, `docs/GLOSSARY.md` written | supervisor | 0.1 | DONE |
| 0.3 | `.claude/agents/*` roster written | supervisor | 0.2 | DONE |
| 0.4 | `git init`, first commit, `.gitignore` | supervisor | 0.3 | DONE |

**0.4 acceptance:** repo initialised on `main`; `.gitignore` covers `.env`, `node_modules`,
`__pycache__`, `.venv`, `dist`; commit message is one line with no AI attribution.

---

## Phase A — Statistical service design

*No product code in this phase. The output is specification precise enough that the data model
falls out of it.*

| # | Card | Owner | Deps | Status |
|---|---|---|---|---|
| A.1 | `docs/EVIDENCE_CONTRACT.md` — the envelope, `Check`, `MethodCard`, `InsufficientData`, min-n policy, serialization shape | statistician | 0.4 | DONE |
| A.2 | `docs/DATA_SPINE.md` — the six canonical streams: field-level schema, event semantics, censoring rules, per-vertical adapter contract | statistician | A.1 | DONE |
| A.3 | `docs/STATS_CATALOG.md` Pack 1 — Reliability & Service Ops, service by service | statistician | A.2 | DONE |
| A.4 | `docs/STATS_CATALOG.md` Pack 3 — Forecasting & Calibrated Risk | statistician | A.2 | DONE |
| A.5 | `docs/STATS_CATALOG.md` Pack 4 — Governance, Segmentation & Text | statistician | A.2 | DONE |
| A.6 | `docs/STATS_CATALOG.md` Pack 2 — Bayesian Ranking & Experimentation | statistician | A.2 | DONE |
| A.7 | `docs/VERTICALS.md` — seven vertical manifests: labels, default packs, categories, roles, auth mode | statistician | A.3–A.6 | DONE |
| A.8 | `docs/STATS_API.md` — the read surface: endpoints, pack toggling, cadence, `insight_runs` shape, agent tool signatures | statistician | A.7 | DONE |

**A.1 acceptance:** a frontend engineer could build the "statistic tile" component from this doc
alone, including the below-min-n and failed-assumption states.

**A.2 acceptance:** every Pack-1..4 service in `PLAN.md` names the stream fields it consumes, and
no service needs a field the spine does not define. Censoring is explicit for `request_flow`.

**A.3–A.6 acceptance, per service:** id · which streams · inputs · outputs · `min_n` · assumptions
· automatic assumption checks · failure mode when they break · the Method Card text · the known
answer its test will be checked against.

**A.7 acceptance:** `rwa_society` and `campus_club` are complete enough to seed a demo tenant.

---

## Phase B — Brand & design system

| # | Card | Owner | Deps | Status |
|---|---|---|---|---|
| B.1 | Lock the name — **Quorum**, settled by the user creating `github.com/1mystic/Quorum` | supervisor | — | DONE |
| B.2 | `design/BRAND.md` — VibeCurb Phase 1 strategy brief + Phase 2 identity architecture | brand-designer | B.1 | DONE |
| B.2a | **3 style directions** + sample landing & dashboard page per direction, for user pick | brand-designer | B.1 | DONE |
| B.2b | **House direction** — Graticule structure + Almanac spacing + fresh palette/type, in `design/samples/quorum/` | brand-designer | B.2a | DONE |
| B.3 | `design/brand/logo/*.svg` (mark, mono, favicon cut, horizontal + stacked lockups, rules) | brand-designer | B.2 | DONE |
| B.4 | `design/tokens.css` + `tokens.json`, full light **and** dark roles, type scale, spacing, radii, shadows, motion | brand-designer | B.2 | DONE |
| B.5 | `design/DATAVIZ.md` — chart palette (separate system from brand), mark specs, axis/legend/tooltip rules, the survival-curve and control-chart specs | brand-designer | B.4 | TODO |
| B.6 | `design/MOTION.md` — motion personality, easing palette, timing sheet, stagger choreography, reduced-motion | brand-designer | B.4 | TODO |
| B.7 | Design canvas artifact — logo lockups · palette · type specimen · components · tenant home · request detail (conformal ETA + KM curve) · Insight dashboard · decision console · mobile | brand-designer | B.5, B.6 | TODO |

**B.3 acceptance:** passes the VibeCurb logo gates — 3-primitive cap, legible as a 16px favicon,
geometry describable in one sentence, none of the banned patterns.

**B.4 acceptance:** every token defined on bare `:root` for light and redefined for dark; no color
whose only definition is inside a media query.

**B.7 acceptance:** every statistic shown on an artboard displays `n` and an interval.

---

## Phase C — Port & build

| # | Card | Owner | Deps | Status |
|---|---|---|---|---|
| C.1 | Scaffold `backend/` + `frontend/` from `reference/campus-connect`, strip campus-specific domain, keep `core/`, `exceptions/`, auth, agent loop | backend-porter | B.4 | TODO |
| C.2 | Rename pass per `docs/GLOSSARY.md` (College→Tenant, Student→Member, Club→Group, Issue→Request) | backend-porter | C.1 | TODO |
| C.3 | Tenant model: `slug`, `vertical`, `enabled_packs`, `settings` + vertical manifest loader | backend-porter | C.2 | TODO |
| C.4 | `TenantScopedRepository` + Postgres RLS + `/api/t/{slug}` routing + slug/claim match | backend-porter | C.3 | TODO |
| C.5 | **Tenant isolation test suite** | reviewer | C.4 | TODO |
| C.6 | `app/stats/contracts.py` + `registry.py` + purity lint | statistician | C.4, A.8 | TODO |
| C.7 | `app/stats/streams/` — canonical dataclasses + RWA and campus adapters | statistician | C.6 | TODO |
| C.8 | `request_flow` domain end to end (Request model, service, API, UI) | backend-porter | C.7 | TODO |
| C.9 | **Pack 1** implementation: `survival.py`, `spc.py`, `queueing.py` + known-answer tests | statistician | C.7 | TODO |
| C.10 | `insight_runs` table + materialization worker + cadence scheduler | backend-porter | C.9 | TODO |
| C.11 | Frontend retheme against `design/tokens.css` + `StatisticTile` / `EvidenceCard` components | frontend | B.7, C.6 | TODO |
| C.12 | Insight dashboard UI — KM curve, control chart, Erlang-C recommendation | frontend | C.11, C.10 | TODO |
| C.13 | `ledger` domain + **Pack 3** (`forecast.py`, `calibration.py`, `conformal.py`, `drift.py`) | statistician | C.10 | TODO |
| C.14 | Conformal ETA surfaced on the request detail page | frontend | C.13 | TODO |
| C.15 | `participation` + `decision` domains + **Pack 4** | statistician | C.13 | TODO |
| C.16 | Decision console UI — pairwise matrix, cycle disclosure, budgeting fairness report | frontend | C.15 | TODO |
| C.17 | **Pack 2** (`bayes.py`, `experiments.py`, `bandits.py`) + shrunk leaderboard | statistician | C.15 | TODO |
| C.18 | Agent stats tools returning `Evidence` + grounding tests | backend-porter | C.9 | TODO |
| C.19 | Seed script: one demo tenant per vertical with enough history for the packs to be non-trivial | backend-porter | C.15 | TODO |
| C.20 | Deploy: `web` + `worker` Dockerfiles, Vercel config, Neon migration, `.env.example` | supervisor | C.19 | TODO |

**C.5 acceptance:** cross-tenant read is 403 at the API **and** returns zero rows under RLS with
the API bypassed.

**C.9 acceptance:** all Pack-1 gates in `docs/RULES.md` §7 pass, including the censoring regression.

**C.13 acceptance:** the MASE and Brier gates pass; a forecaster that loses to seasonal-naive is
not merged.

**C.18 acceptance:** the injection fixture moves no tool call and fabricates no value.

---

## Parking lot

- Certificate + QR subsystem: keep as a togglable module? (leaning yes — already built and tested)
- Auth: email+password+Google as ported, or add phone+OTP per vertical manifest? (leaning both)
- WhatsApp broadcast — the RWA research found ~99% resident usage, which is the single strongest
  adoption signal in the file. Revisit once Phase C is walking.
- Cross-tenant hierarchical priors (Pack 2): privacy mechanism settled (DP-noised sufficient
  statistics, batched weekly refresh, per-tenant epsilon budget). See `docs/STATS_CATALOG.md`
  `bayes.hierarchical_pool`. Implementation still lands in card C.17, gated by the sensitivity
  test in addition to the known-answer test.
