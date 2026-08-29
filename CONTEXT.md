# Living context

**Update this before you stop. An agent that stops without updating this file has not finished.**

---

## Where we are

**Phase 0 done. Phase A opened, then jumped to Phase B at user request.**

Name is **locked: Quorum** — settled when the user created `github.com/1mystic/Quorum`.

Three directions were built and reviewed. The user picked **Graticule's structure + Almanac's
spacing**, with fresher colour and type. That synthesis is now the **house direction**, living in
`design/samples/quorum/`. Next: fold it into `design/tokens.css` (B.4), then resume Phase A at
**A.2** (the data spine).

## Done

| When | What |
|---|---|
| 2026-08-29 | Read both legacy RWA planning docs; classified them as historical research, not requirements |
| 2026-08-29 | Studied `MAY2026-Team-003` (Campus Connect); confirmed it as the port source |
| 2026-08-29 | Extracted `design-sources.zip` → VibeCurb skill pack; reviewed all seven protocols |
| 2026-08-29 | Reviewed sangam-club.com as an adjacent reference |
| 2026-08-29 | `PLAN.md`, `CLAUDE.md`, `docs/RULES.md`, `docs/WORKPLAN.md`, `docs/GLOSSARY.md`, `CONTEXT.md`, `.claude/agents/*` (cards 0.1–0.3) |
| 2026-08-29 | Vendored `reference/campus-connect/` and `reference/vibecurb/` into the repo |
| 2026-08-29 | `git init` on `main`, `.gitignore`, synced to `github.com/1mystic/Quorum` (card 0.4) |
| 2026-08-29 | `docs/EVIDENCE_CONTRACT.md` — the envelope, four render states, min-n policy, censoring rule (card A.1) |
| 2026-08-29 | Name locked: **Quorum** (card B.1) |
| 2026-08-29 | Three directions built — Almanac, Graticule, Signal — with landing + dashboard each (card B.2a) |
| 2026-08-29 | House direction synthesized into `design/samples/quorum/` after user review |
| 2026-08-29 | `design/tokens.css` + `design/tokens.json`, 76 tokens, light and dark (card B.4) |
| 2026-08-29 | `design/brand/logo/` mark, mono, favicon cut, two lockups, usage rules (card B.3) |
| 2026-08-29 | `design/BRAND.md` updated from the provisional terracotta/serif proposal to the shipped palette and type |
| 2026-08-29 | `docs/DATA_SPINE.md`: six streams, field-level schema, ten normative censoring rules for `request_flow`, adapter conformance contract (card A.2) |
| 2026-08-29 | `docs/STATS_CATALOG.md`: 63 services across the four packs, each with min-n, automatic checks, Method Card and its known answer (cards A.3–A.6) |
| 2026-08-29 | `docs/VERTICALS.md`: seven manifests; `rwa_society` and `campus_club` complete with demo seed requirements (card A.7) |
| 2026-08-29 | `docs/STATS_API.md`: read surface, `insight_runs` shape, cadence table, five agent tools, registry invariants (card A.8) |
| 2026-08-29 | `frontend/` scaffolded — Vite + Vue 3 + Vue Router + Pinia + Vitest, composables ported near-verbatim from Campus Connect, tokenized `style.css` (22 numbered sections) built from `design/samples/quorum/dashboard.html`, `STYLE-INDEX.md` written (Vue scaffold half of card C.1) |
| 2026-08-29 | Evidence component set built: `EvidenceValue`, `StatTile`, `SurvivalCurve`, `ControlChart`, `MethodCardLink`, `AuditLine`, all four render states from `docs/EVIDENCE_CONTRACT.md` §3, 27 Vitest tests passing (card C.11, brought forward) |
| 2026-08-29 | `backend/` scaffolded from `reference/campus-connect/backend/`, full rename pass per `docs/GLOSSARY.md` applied across models/schemas/services/repository/api/exceptions/tests/templates/agent prompts, fixed-weight `LeaderboardService` deleted, `Tenant` model (`vertical`, `enabled_packs`, `settings`, `timezone`; `email_suffix` dropped), `app/verticals/` manifest loader + two provisional manifests, `TenantScopedRepository`, `/api/t/{slug}` routing with JWT slug/claim check, Postgres RLS migration, `tests/integration/test_tenancy.py` isolation suite (cards C.1-C.5, see decision log for what did not get ported to full parity) |

## In flight

Design and branding are done. Three agents now running in parallel on disjoint paths:

- **statistician**: **A.2 to A.8 complete.** Phase A is done. Next statistician cards are C.6
  (`contracts.py`, `registry.py`, purity lint) and C.7 (`streams/`), now unblocked since C.4 is done
- **backend-porter**: **C.1-C.5 done**, see decision log entries below for scope boundaries and the
  follow-up list. Next up would be C.6's dependency C.4 confirmation with statistician, then C.8
  (`request_flow` end to end) once C.6/C.7 land
- **frontend** finished the Vue scaffold and the Evidence component set (`frontend/` only); ready
  for `C.12` once `C.10`/`insight_runs` exists, but can keep building UI against fixtures meanwhile

Each commits only its own paths to avoid racing the others.

## Blocked

Nothing.

---

## Decision log

Newest first. Append, never rewrite. Record *why*, not just *what*.

| Date | Decision | Why |
|---|---|---|
| 2026-08-29 | `Issue` -> `Request` renamed with a word-boundary pass, not substring | Campus Connect already used `Request` as its pydantic-schema-class suffix (`RaiseIssueRequest`, etc.) and also uses "issue" as a verb for certificate issuance (`issue_certificate_job`, `issued_at`). A naive substring rename corrupted `CERTIFICATE_ISSUED` into `CERTIFICATE_REQUESTD` on the first pass; caught by re-parsing every file with `ast` and grepping for the mangled token, then fixed by hand |
| 2026-08-29 | Fourteen Campus Connect alembic migrations squashed into one `init schema` migration built from `Base.metadata.create_all`, plus one `tenancy row level security` migration | The rename touches almost every table and column name; replaying the old migration history under new names would be pure churn with no one depending on the old schema. The squashed migration cannot drift from `app/models` because it *is* the models |
| 2026-08-29 | `email_suffix`-based auto-tenant-assignment at signup replaced with an explicit `tenant_slug` field on `SignupRequest`/`GoogleAuthRequest` | `Tenant.email_suffix` does not generalize past the campus vertical (docs/GLOSSARY.md). A housing society has no email domain to join by. `TenantRepository.email_to_tenant` removed; a MEMBER now names the tenant it wants to join by slug, same as the URL does |
| 2026-08-29 | `tenant_id` denormalized onto every tenant-owned table, even where it was already reachable via a join (event -> group -> tenant) | `docs/RULES.md` §5 requires every table to carry it, mainly so Postgres RLS policies stay a flat `tenant_id = current_setting(...)` rather than a join-based policy per table. Repositories derive it from the parent row at create time (e.g. `EventRepository.create_event` looks up `Group.tenant_id`) rather than trusting a caller-supplied value |
| 2026-08-29 | `/api/t/{slug}/...` enforced by one router-level dependency (`app/core/tenancy.py:verify_tenant_scope`), not by editing every endpoint | FastAPI resolves path params against the whole dependency tree, not just the endpoint signature, so a single `Depends` on the parent `APIRouter(prefix="/api/t/{slug}")` catches every route mounted under it. Confirmed empirically since this project's FastAPI version lazily wraps included routers (`_IncludedRouter`) rather than eagerly flattening them |
| 2026-08-29 | JWT gains `tenant_id` and `tenant_slug` claims, signed at login/signup, cross-checked against the URL slug | The slug in the URL must match the JWT claim or 403 (never trust the URL alone). Carrying the slug in the token as well as the id avoids a DB round-trip in the tenancy dependency on every request |
| 2026-08-29 | `TenantScopedRepository` (`app/repository/base.py`) fully applied to `RequestRepository` only, not to all ten tenant-owned repositories | Given the size of the rest of card C.1-C.5, going deep on the flagship `request_flow` domain (PLAN.md calls it "the demo that sells the whole thesis") was judged more valuable than going wide and shallow across every repository. The other nine tables have `tenant_id` and are covered by RLS as a backstop; migrating `GroupRepository`, `EventRepository`, etc. to the same base class is the top follow-up, see below |
| 2026-08-29 | RLS enabled with `FORCE ROW LEVEL SECURITY` on ten tables (`app/core/rls.py`, shared by the migration and `tests/conftest.py`), **excluding** `users` and `group_links` | `users` is the pre-tenant identity table: signup/login run before any tenant context exists and a fresh TENANT_ADMIN's `tenant_id` is NULL, so RLS would lock them out of their own row. `group_links` has no `tenant_id` column of its own yet (follow-up). Every other tenant-owned table is covered |
| 2026-08-29 | Marketing "trending groups" and certificate verification/file download split into `public_group_router` / `public_certificate_router`, mounted outside `/api/t/{slug}` | Both were legitimately public and cross-tenant by design in Campus Connect already (anonymous landing page, anonymous QR verification). Forcing them under the tenant prefix would have broken them, not secured them |
| 2026-08-29 | Old `openapi.yaml` (10,150 hand-authored lines, Campus Connect routes and branding) deleted rather than rewritten | It would have been actively misleading (wrong paths, wrong domain names) and rewriting it by hand was out of scope. `/docs` and `/openapi.json` are auto-generated from the actual code and are now the reference, per the rewritten README |
| 2026-08-29 | Rename script's file-extension allowlist missed `.svg`/`.html` templates on the first pass, caught by running the offline unit tests | `test_render_pdf_all_result_templates` failed with `jinja2.exceptions.UndefinedError: 'club_name' is undefined` - the Python side had renamed `group_name` but the Jinja template hadn't. Fixed by hand in `app/templates/certificates/_base.svg`; this is the argument for always running whatever tests *can* run offline after a mechanical pass, not trusting the script |
| 2026-08-29 | Deep vertical-tuned agent prompts in `app/agent/intent.py`/`recommender.py` (few-shot examples like "climate... greener campus, tree plantation") left untouched | These are campus_club-specific example content, not generic naming - a mechanical rename would have degraded a hand-tuned prompt without actually generalizing it. User-facing identity strings (system prompt persona, error messages, tool descriptions) were renamed to Quorum; the campus-flavoured examples inside the NLU prompt are flagged as follow-up prompt engineering once a second vertical needs the agent |
| 2026-08-29 | The exposure log (`nudge_sent`/`delivered`/`opened`/`acted` with `arm_ref`) is added to `participation` | Pack 2's A/B tests and bandits need who was *offered* a nudge, not only who acted. Without it every nudge experiment measures self-selection. The six-stream sketch had no place for a system action against a member |
| 2026-08-29 | `StreamWindow.complete_through` is a first-class field, separate from `end` | Reporting lag is a property of the pipeline, not of any event. A forecaster fitted through `end` reads the partial final bucket as a collapse in collections. Nothing else in the spine protects against it |
| 2026-08-29 | Resident-facing ETAs use conformalized survival analysis (Candes, Lei, Ren), not split conformal | Split conformal calibrated on resolved requests is calibrated on the fast ones. Exchangeability fails in the direction that makes the ETA look good, which is the worst possible direction for the one number a resident will trust and quote |
| 2026-08-29 | A blocking MASE failure returns the seasonal-naive forecast, not an error | The tenant still gets a number and the number is the honest one. An error state would push people to a tool that answers |
| 2026-08-29 | `survey.likert_distribution` returns a `structure` with no `mean` key at all | Same mechanism as `TextDoc` having no identity field: prevention by type, not by discipline. A reviewer cannot forget a rule the shape does not permit breaking |
| 2026-08-29 | `network.isolation_report` returns shares by stratum and can never return individuals | A list of socially isolated neighbours is the most sensitive output the platform could produce. The service is shaped so the list cannot be constructed |
| 2026-08-29 | `rwa_society` disables `network.betweenness_centrality` and `audit.benford_digits` | Interview 1 documents active committee friction; naming informal power brokers is a foreseeable harm. Benford on fixed monthly dues is a guaranteed false positive. A vertical switches a wrong service off rather than shipping it with a caveat |
| 2026-08-29 | "Not enough data" is HTTP 200 with `insufficient_data: true`, never 404 or 422 | If honesty returns an error code, every client treats it as a failure and users learn that honest tools look broken |
| 2026-08-29 | The agent gets exactly five tools and none of them computes or queries a stream | No `compute_statistic` means it cannot produce an unaudited number; no `query_stream` means it cannot count rows and state a figure with no `n` and no checks |
| 2026-08-29 | A `ServiceSpec` without a Method Card fails at import | `docs/RULES.md` §4 as a load-time error rather than a review convention. Also: catalog and registry must match both ways, so the doc cannot drift from the code |
| 2026-08-29 | Where no external ground truth exists, the catalog says so in an appendix | Seven services are gated or property-tested rather than validated. A product whose claim is honesty cannot have a "known answer" column where some entries are quietly invented |
| 2026-08-29 | `EvidenceValue` gets a `display="range"` mode that shows the interval bounds as the headline figure, for conformal/predictive intervals | The contract doesn't say how a conformal ETA's point value relates to its interval, and the dashboard sample shows the interval itself as the big number ("2 ... 9 days"), not a point estimate. Read as: some methods assert a guarantee about a range, not a point, so the component needs an explicit mode rather than guessing from `interval_kind` |
| 2026-08-29 | Prose style: no em dashes anywhere in product copy or docs | User rule. En dashes stay in numeric ranges (`3.4-5.6`) and in `Kaplan-Meier`, where they are the correct mark rather than punctuation |
| 2026-08-29 | Status colours are mapped to the four Evidence render states, not to sentiment | `--accent` had to stay free for "actionable". A warning that competes with a hover fill is a worse bug than a dull palette |
| 2026-08-29 | Backend and frontend scaffolding run in parallel with the statistics spec | They touch disjoint paths and C.1 to C.4 only depend on B.4, which is now done. The stats spec is the long pole and should not block the port |
| 2026-08-29 | House direction = Graticule structure + Almanac spacing + new palette/type | User review: Graticule was most appealing but geometrically inconsistent and its dashboard cluttered; Almanac's landing and spacing were right but its cream-and-terracotta read dated; Signal was too loud for the audience |
| 2026-08-29 | Palette: warm limestone `#FAF7F2` · spruce `#13594A` · apricot `#E07A3F` · warm ink `#1A1714` | Warm and comfortable as asked, without the cream/terracotta cliché. Spruce stays calm for a data product; apricot carries interaction, never status |
| 2026-08-29 | Type: Bricolage Grotesque display · Inter Tight text · JetBrains Mono numerals | Bricolage has character without gimmick; a mono on every number is the instrument signal that made Graticule work |
| 2026-08-29 | Dashboard prose moved behind `<details>` disclosure | The chief complaint was clutter and small descriptive text. The Evidence contract still requires the explanation to be present — disclosure keeps it present without it being loud |
| 2026-08-29 | Buttons use a sweep-fill hover, label static | User asked for modern fill animations rather than colour swaps |
| 2026-08-29 | Git identity `1mystic <atharvkahre18@gmail.com>`, repo-local | User instruction. Note this differs by one character from the machine's global config (`atharvkhare18@`) — flagged to the user |
| 2026-08-29 | Name locked: **Quorum** | User created the remote under that name. Double meaning — enough people to decide, enough data to conclude |
| 2026-08-29 | Phase B pulled ahead of the rest of Phase A | User wants to see and choose a visual direction before more specification work. A.1 was complete, so A.2 resumes after the pick |
| 2026-08-29 | Reference material vendored into `reference/`, read-only | All work stays inside the RWA dir; keeps a record of exactly what we ported from |
| 2026-08-29 | Campus Connect's `RULES.md` git playbook **not** adopted; direct commits to `main` | Feature branches and mandatory PR review are a five-person course team's process, not ours |
| 2026-08-29 | Commit messages 1–2 lines; no AI attribution anywhere, ever | User rule, non-negotiable |
| 2026-08-29 | Build order fixed: governance → statistics design → brand → port | The data model should fall out of the statistics, not the other way round. Porting first would lock us into Campus Connect's schema before we know what the packs need |
| 2026-08-29 | The four Insight Packs are all in scope; Pack 2 ships last | Empirical Bayes and bandits need accumulated data to say anything, so they are worth little on day one |
| 2026-08-29 | `app/stats/` must be pure — no DB, no network, deterministic | It is the only way to test statistics against known analytic answers rather than snapshots. Mirrors the existing purity of Campus Connect's `agent/recommender.py` |
| 2026-08-29 | Every statistic crosses boundaries as an `Evidence` envelope; the agent may only narrate one | Structurally prevents the LLM from inventing or recomputing a figure. This is the product's trust story, not a nicety |
| 2026-08-29 | Six canonical streams instead of per-vertical statistics | Otherwise survival analysis gets written once per community type. This is what makes "each tenant picks its techniques" cheap instead of combinatorial |
| 2026-08-29 | Evolve Campus Connect's warm palette rather than replace it | It already reads personal rather than corporate-SaaS, which is exactly the brief. Dark mode and a separate dataviz palette are the additions |
| 2026-08-29 | Deploy stays host-agnostic; `web`/`worker` split | The scientific stack is ~500 MB and will not fit a 512 MB free tier alongside the API. Splitting lets the light half run anywhere |
| 2026-08-29 | Legacy RWA docs demoted to research | Their scope cuts existed to survive an instructor feasibility review we are no longer subject to. The interview findings remain valid evidence |
| 2026-08-29 | Product is free-standing — no course milestones or team-role constraints | User direction |

---

## Known constraints worth remembering

- **`brandkit-gen` is an image-generation skill** and no image-gen tool is available in the current
  environment. Phase B ships hand-authored SVG under VibeCurb's constraint discipline. The strategy
  brief is the input if a later session has image generation.
- **The scientific stack is heavy** (~500 MB with statsmodels + sklearn + lifelines). Anything
  running on a small free tier must read materialized `insight_runs`, never compute inline.
- **Small communities are small.** A per-block statistic over three households is a disclosure.
  k-anonymity and DP noise are requirements in the housing vertical, not polish.
- **Campus Connect's `Certificate` subsystem** is fully built and tested. Valuable for clubs and
  volunteer orgs, dead weight for RWA. Parked as a togglable module.
- **No Postgres is reachable in this sandbox** (no `docker`, no root/apt). `backend/` was verified
  by: all 561 tests collect with zero import errors, all 69 DB-independent tests pass (hashing,
  token, mailer, storage, certificate PDF/SVG rendering, agent recommender/grounding/llm_client),
  `main.py` builds the full FastAPI app and its OpenAPI schema resolves every intended route,
  `alembic history`/`heads` resolve the two-migration chain. **The tenant-isolation suite
  (`tests/integration/test_tenancy.py`) and every other integration test have not actually been run
  against a live database by this agent.** Running `uv run pytest` against a real
  `TEST_DATABASE_URL` is the first thing the next backend session should do.
- **Ported test suite is not yet schema-clean.** Beyond `test_tenancy.py` (new, self-contained),
  the rest of `tests/integration/` still calls old unprefixed routes (`/groups` instead of
  `/api/t/{slug}/groups`) and some fixtures construct rows directly via the ORM without first
  calling `set_config('app.tenant_id', ...)`, which will now hit the RLS `WITH CHECK` and fail to
  insert. `tests/conftest.py`'s shared fixtures (`seed_tenant`, `admin_token`, `member_token`, the
  multipart interceptor) are fixed; the per-file route paths and direct-insert fixtures are not.
  This is real, mechanical, high-volume follow-up work, most naturally picked up alongside C.8
  (`request_flow` end to end) rather than as its own detour.
- **`TenantScopedRepository` is only fully wired through `RequestRepository`.** The other nine
  tenant-owned tables have `tenant_id` and RLS as a backstop, but their repositories
  (`GroupRepository`, `EventRepository`, `AnnouncementRepository`, etc.) still take a bare `db` and
  do not enforce tenant scoping at the query level the way `RequestRepository` does. Migrating them
  is mechanical once the pattern in `app/repository/base.py` and `app/repository/request.py` is the
  template.
- **`group_links` has no `tenant_id` column and is not covered by RLS.** Small child table of
  `groups`, low risk, flagged in the RLS migration's docstring rather than fixed.
- **Agent tool timezone is hardcoded to UTC** (`app/agent/intent.py`). Was Campus Connect's global
  `COLLEGE_TIMEZONE` setting; per `docs/GLOSSARY.md` it is now `Tenant.timezone`, but wiring the
  tenant's actual value through the bounded tool-calling loop is agent-integration work (card C.18),
  not tenancy plumbing.
