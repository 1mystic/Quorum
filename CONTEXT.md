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
| 2026-08-29 | Full frontend page set built against fixtures, per the frontend-first resequencing decision below. Every page in `docs/WORKPLAN.md`'s frontend breadth pass now exists, is routed under `/t/:slug/...` (or public for auth/method-card pages) and is reachable from the sidebar/landing nav: `LoginView`, `SignupView`, `ForgotPasswordView`, `ResetPasswordView`, `VerifyEmailView`, `OnboardView`, `WorkspaceView`; `DashboardView`, `RequestsView`/`RequestDetailView`/`RequestNewView`, `LedgerView`, `EventsView`/`EventDetailView`, `AnnouncementsView`, `DecisionsView`/`DecisionDetailView`, `MembersView`, `ProfileView`; `AdminOverviewView`, `AdminApprovalsView`, `InsightsOperationsView`/`InsightsForecastView`/`InsightsGovernanceView`/`InsightsComparisonView` (one per pack), `TenantSettingsView`, `MethodCardView`/`MethodsIndexView`. Two new layout components (`TenantShell`, `AuthShell`) generalize the dashboard sample's `.app`/`.side`/`.main` shell so every page shares one sidebar/nav/tenant-switcher instead of each view rolling its own. Ten new fixture modules (`tenants`, `nav`, `requests`, `ledger`, `events`, `announcements`, `decisions`, `members`, `methodCards`, `insights`) carry `rwa_society` (Vaikunth Heights) and `campus_club` (Aavartan Robotics) demo data shaped to `docs/EVIDENCE_CONTRACT.md` §5's wire format; every statistic on every page still renders through `StatTile`/`EvidenceValue`/`SurvivalCurve`/`ControlChart`, none takes a bare number. `style.css` gained nine new numbered sections (23-31: auth/forms, status badges, filter chips, timeline, list rows, empty state, pairwise matrix, callouts, segmented toggle), `STYLE-INDEX.md` updated. Two new Vitest suites (`LedgerView.test.js` for the mark-paid flow, `DecisionDetailView.test.js` for the mandatory Condorcet-cycle disclosure) alongside the existing Evidence suite; **34/34 tests pass, `npm run build` succeeds**. No em dashes introduced (checked by grep before commit). Committed in five path-disjoint groups (fixtures+shells+CSS, auth pages, core member pages, insight/admin/method pages) per the card's incremental-commit instruction (frontend session, breadth-first pass) |
| 2026-08-29 | `backend/app/stats/` built: `contracts.py` (the `Evidence`/`Check`/`MethodCard`/`InsufficientData` types exactly per `docs/EVIDENCE_CONTRACT.md` §2, plus `params_hash` and the four render states as data), `registry.py` (**all 81 catalogued services registered, each with a complete Method Card**; 24 module files of `-> Evidence` stubs that raise `NotImplementedError`), `streams/` (the six streams as frozen dataclasses with the ten `RequestSpell` censoring rules and the exposure log, plus `capacity.py` and `reduce.py` signature stubs), `app/verticals/adapters/` (`PortedSchemaAdapter` + `rwa_society` + `campus_club`). Five test modules, **707 tests pass offline**, whole suite still collects clean (1268) and the 776 DB-independent tests pass (cards C.6, C.7) |
| 2026-08-30 | `request_flow` domain end to end (card C.8, backend-porter): new `RequestEventLog` model/table (`app/models/request_event.py`, migration `a3f7c9d1e2b4`) closes the adapter TODO that blocked "assigned"/"reassigned"/"paused"/"resumed"/"escalated"/"withdrawn"/"merged"/"reopened" from ever being recorded, append-only, `tenant_id`-scoped, RLS-covered. `Request.category`/`priority`/`channel`/`location_ref`/`subcategory` move from the ported Campus Connect enum to plain strings validated at the service layer against `get_adapter(tenant.vertical).request_categories`/`request_priorities` (docs/VERTICALS.md rule V3), closing the `rwa_society` "every row is other" gap named in the adapter's own docstring: `rwa_society`'s real vocabulary (`water_supply`, `sewage_stp`, ...) now maps straight through with nothing unmapped, and `campus_club`'s legacy-enum translation path is untouched. `RequestStatus` gains `ESCALATED`/`WITHDRAWN`/`MERGED` (rule C5's competing-risks terminals plus rule C7's merge exclusion); `Request` gains `terminal_at`/`outcome`/`merged_into_id` as a read convenience kept in sync by the repository, never the thing a stream adapter reduces. `RequestRepository` (already the sole fully `TenantScopedRepository`-wired repo, confirmed still true, no drift since C.1-C.5) gained one write method per lifecycle transition, each appending a `RequestEventLog` row, plus `stream_requests`/`stream_events` as the literal "fetch" half of the fetch/compute boundary (`app.stats.streams` never sees these directly; whoever wires `streams/reduce.py` reads through here). `RequestService` gained `assign`/`reassign`/`pause`/`resume`/`escalate`/`withdraw`/`merge`/`reopen`, all role-checked the same way `resolve` already was, plus vocabulary validation on `raise_request`; seven new `/api/t/{slug}/requests/{id}/...` routes. `app/verticals/adapters/base.py`'s `PortedSchemaAdapter.request_events` now actually reads the new `priority`/`channel`/`location_ref`/`subcategory` columns instead of hardcoding `None` for three of them; its docstring is updated to say what remains outstanding (folding the new event-log rows into the emitted atoms, left to whoever wires the reducer, not done here since that touches `app/verticals/` shape decisions the statistician owns). `tests/unit/stats/test_adapters.py`'s `rwa_society` "cannot categorise" test is rewritten into two: one proving real categories now map through, one proving a still-unmapped value is still counted, never guessed; a new parametrized test proves priority/channel/location/subcategory now flow. Full suite: **802 passed, 0 failed, 492 errored** (all 492 are `ConnectionRefusedError` from the DB-dependent integration suite against an absent Postgres, the same documented sandbox constraint as before, not new breakage: confirmed by grep for `FAILED` returning nothing and by diffing against `git stash` before/after); `uv run alembic history`/`heads` resolve the new three-migration chain; `1294 tests collected`, zero import errors. Ten unrelated `survival.py` test failures observed mid-session are the statistician's own uncommitted concurrent work on a file this card never touches (`app/stats/`), confirmed via `git status`/`git diff --stat` before touching anything, and are out of scope here |

## In flight

Design and branding are done. Three agents now running in parallel on disjoint paths:

- **statistician**: **A.2 to A.8, C.6 and C.7 complete.** The statistical architecture now exists in
  code: the envelope, the registry of all 81 services with their Method Cards, the six streams and
  two vertical adapters. Nothing is left half-wired; what is not implemented raises
  `NotImplementedError` and says which document specifies it.

  **What is implemented versus stubbed.** Implemented and tested: everything in `contracts.py`
  (including `params_hash`, the render-state resolution and the wire format), the whole registry
  including its import-time invariants, every stream dataclass and its validation, and both
  adapters. Stubbed: **all 81 statistical service bodies**, the atom-to-unit reducers in
  `streams/reduce.py`, and the cross-stream `streams/capacity.py` reducer. That split is
  deliberate: C.6 and C.7 are the contract and the shapes, and each service body arrives with its
  known-answer test rather than in a batch, since a stub that returns a plausible number is worse
  than one that raises.

  **The purity lint is real and was verified by breaking it.** `tests/unit/stats/test_purity.py`
  AST-walks all 38 modules under `app/stats/` and fails on a forbidden import, a clock read or
  mutable module-level state. It was tested by planting `import sqlalchemy`, `from app.repository
  import ...`, `datetime.utcnow()` and `CACHE = {}` into `app/stats/survival.py`: three tests failed
  with the file, the line number and the rule, and passed again once reverted. It also has its own
  known-answer test so a future refactor cannot quietly neuter it, and it is AST-based so prose
  about the rule is not a breach of it.

  **Next statistician card is C.8** (`request_flow` end to end), which means
  `streams/reduce.request_spells` plus the Kaplan-Meier family, with the `lung`/`rossi` fixtures and
  the censoring regression fixture from `docs/RULES.md` §7
- **backend-porter**: **C.1-C.5 done, C.8 (`request_flow` end to end) done.** See the 2026-08-30
  `Done` row and decision log entry for the full shape. What C.8 did *not* do, on purpose, since it
  is the statistician's file: wire `app/verticals/adapters/*.request_events` (or `streams/reduce.py`)
  to actually consume `RequestEventLog` rows via the new `RequestRepository.stream_events`: the
  table and the fetch method exist and are tenant-scoped, but nothing yet turns those rows into the
  `assigned`/`paused`/`escalated`/... stream atoms. Also not done: the mechanical route-prefix /
  category-vocabulary cleanup of `tests/integration/test_request.py` (a route-prefix problem that
  predates this card, see the older decision log entry below; its category fixtures now also assume
  the pre-C.8 enum values, e.g. `"GENERAL"`, which no longer validate for `campus_club`'s real
  vocabulary once the routes are fixed to `/api/t/{slug}/...`). Next backend-porter card is C.10
  (`insight_runs` + materialization worker), which depends on C.9 (statistician's Pack 1).
- **frontend**: breadth pass done. Every page in the product now exists, is routed and is reachable
  from nav, built entirely against fixtures (`frontend/` only, no backend touched). Depth (real
  `/api/t/{slug}/...` wiring per `docs/STATS_API.md`, module by module starting with core features)
  is the next frontend card, once `C.10`/`insight_runs` exists on the backend side. Because every
  view already reads its data from a `fixtures/*.js` module rather than an inline literal, swapping
  a view onto the real API should be a one-line change per view (replace the fixture import with an
  API call returning the same envelope shape) rather than a rewrite.

  **Explicit TODOs left for the next frontend session** (not started, not half-wired): no page for
  `budgeting.fairness_report` (participatory budgeting, part of Pack 4; `DecisionDetailView` only
  covers the poll/Schulze half of the `decision` stream); no route guard enforces `meta.role`
  (`public`/`member`/`admin`) yet, every tenant route is reachable by URL regardless of
  `stores/auth`'s role, left alone deliberately since there is no real auth backend to guard against
  but it needs to land alongside real auth; `useAuthSession.completeSignIn` is unused since the auth
  pages sign a demo session directly (see decision log) rather than decoding a real JWT; no
  `useGoogleAuth` composable was ported, the Google buttons are `toast.info` stubs; `MethodCardView`
  reads a small hand-written `fixtures/methodCards.js` (~14 cards, only the methods actually
  referenced by a fixture `Evidence.method`), not the full 63-service `docs/STATS_CATALOG.md` set.

All three background agents finished and were verified against the gates in `docs/RULES.md` §7
rather than accepted on report (em dashes, secrets, AI attribution, and for the backend agent, an
independent re-run of its test claims). Fixes from that verification pass are committed.

The one open item that was genuinely blocking, the Pack 2 cross-tenant privacy question, is now
resolved (see decision log). Nothing is currently in flight; the session is pausing here by user
instruction ahead of a session limit. Next unblocked cards for a future session: **C.6/C.7**
(statistician, `app/stats/contracts.py` + `streams/`), the **manifest reconciliation** (backend's
two provisional verticals against the now-complete `docs/VERTICALS.md`), and route-prefix cleanup
in the ported integration test suite (noted in the backend-porter decision log entry).

Each commits only its own paths to avoid racing the others.

## Blocked

Nothing.

---

## Decision log

Newest first. Append, never rewrite. Record *why*, not just *what*.

| Date | Decision | Why |
|---|---|---|
| 2026-08-30 | `Request.category`/`priority` validated at the service layer against the vertical adapter's declared vocabulary, not by a database enum/constraint | docs/VERTICALS.md rule V3: the column is always `request.category`, but a vertical is free to declare its own values, and a seventh vertical (docs/VERTICALS.md names five more beyond the two shipped) must not need a schema migration just to add a category. A database enum would have re-created exactly the `rwa_society` gap this card closed: the CampusConnect-only `RequestCategory` enum was the reason `rwa_society` could not categorise a complaint at all |
| 2026-08-30 | `RequestEventLog` is a new append-only table, not a mutation of `Request` in place | docs/DATA_SPINE.md's `request_flow` reducer needs every state a request passed through, not just the last one, to build a `RequestSpell` and decide censoring (C1-C10 in particular C5's competing risks and C7's merge exclusion). `Request.status`/`terminal_at`/`outcome` stay as a denormalized read convenience kept in sync by the repository on every write, but the event log is the only thing a stream adapter is meant to reduce |
| 2026-08-30 | `PortedSchemaAdapter.request_events` was extended to read the new `priority`/`channel`/`location_ref`/`subcategory` columns, but was *not* extended to fold `RequestEventLog` rows into its emitted atoms | The card's boundary excludes `app/stats/`, and reading the new event log into the stream is closer to the reducer's shape decisions (does a `reopened` event start a new spell under `reopen_policy="new_spell"`, or extend the existing one?) than to a mechanical column read. The table and a tenant-scoped fetch method (`RequestRepository.stream_events`) exist and are the whole of what this card owes the fetch/compute boundary; wiring them into the adapter is left named, not attempted, so as not to collide with concurrent work on the same file |
| 2026-08-29 | The registry holds **81** services, not the 63 `docs/STATS_CATALOG.md`'s summary line claims | The registry test parses the catalog and asserts both directions of the parity: every `module.function` the catalog names is registered, and every registered service is named there. It passes at 81, so the "63" in the catalog's header and in this file's A.3-A.6 row is simply a stale count from before the composed views (`survival.naive_vs_km_gap`, `queueing.backlog_projection`), the three named forecast compositions, the three separate `voting.borda`/`approval`/`score` ids and `drift.label_shift` were written up. The code is the count that is checked on every commit; the prose number is not, which is the argument for the parity test existing at all |
| 2026-08-29 | Unimplemented services are **registered with a complete Method Card and a body that raises**, not omitted | A service that is absent from the registry is invisible: `GET /api/methods/{id}` 404s, the packs endpoint under-reports, and `docs/VERTICALS.md` rule 2 (a disabled service is still listed with its reason) cannot be honoured. `ServiceSpec.implemented` distinguishes the two states, and the stub raises `NotImplementedError` naming the document that specifies it rather than returning a plausible zero. It also means the whole read surface can be built and tested against a complete registry before any mathematics exists |
| 2026-08-29 | `min_n` stays an `int` and a companion `min_n_expression` string carries floors that are functions of a parameter | Several floors are not constants: Kaplan-Meier is "30 observed **events**, not rows", Cox is "10 events **per covariate**", every seasonal forecaster is `2 * season_length`, and split conformal has a mathematical floor of 9 and a practical floor of 100. Making `min_n` a callable would have made the registry unserialisable and the invariant "spec min_n equals card min_n" untestable. The integer is what the UI compares against for the calm empty state ("needs 30, has 11"); the expression is what it prints next to it |
| 2026-08-29 | Service availability is resolved **per service**, never per pack | `bayes.*` runs on `request_flow` alone even though its pack also lists the ledger, and `forecast.attendance` needs `member_lifecycle` for its `bounded-by-roster` check even though its pack does not. A first attempt asserted that pack streams and service streams agree and it failed in both directions, correctly. `available_for_streams` and `missing_streams` therefore answer per service, which is also what the greyed-out onboarding row in `docs/VERTICALS.md` rule 1 actually needs |
| 2026-08-29 | The purity lint bans `app.core`, `app.models`, `app.api` and `app.verticals` as well as the four names in the working agreement | The four named (`app.repository`, `app.services`, `sqlalchemy`, `httpx`/`requests`) are the routes to a database and a socket, but `app.core` reaches `Base` and the session factory, and `app.models` drags in SQLAlchemy transitively. Banning the reachable set rather than the enumerated set is what makes the rule mechanical. It also bans clock reads and mutable module-level state, since both break determinism, which is the property the rule exists to protect rather than an end in itself |
| 2026-08-29 | Both shipped adapters subclass one `PortedSchemaAdapter` | `rwa_society` and `campus_club` differ in vocabulary, strata, k-anonymity floor, reopen policy and SLA clock; they do not differ in where rows come from, because there is only one ported schema. Splitting on vocabulary and sharing the row mapping means the missing models get read once when they arrive rather than twice, and it makes the conformance suite meaningful: both verticals run the same open-request fixture through the same code path |
| 2026-08-29 | Ledger and decision are declared **empty** by both adapters rather than approximated from anything present | There is no ledger model and no decision model. An adapter that fabricated a stream would produce statistics with a currency symbol and no data behind them. Empty is a state the architecture already handles: the service raises `InsufficientData`, which the registry turns into "this pack needs the ledger switched on" rather than an error |
| 2026-08-29 | Ledger and decision views built as genuinely new page types rather than adapted Campus Connect screens | `docs/DATA_SPINE.md`'s `ledger` stream (verification lag, receipt-collection gap) and the `decision` stream's mandatory Condorcet-cycle disclosure have no Campus Connect analogue. The Evidence contract stretched cleanly to both once treated as ordinary envelopes: `LedgerView` reads `verification_lag`/`receipt_gap` through `StatTile` exactly like any other statistic, and `DecisionDetailView` treats the cycle disclosure as a `callout`, not a `details.why`: the contract's rule that a `Check` is measured, not asserted in prose, argues for always-visible disclosure on a cycle specifically, since `docs/STATS_CATALOG.md` calls this one "not blocking, and deliberately not an error" but still non-optional to show |
| 2026-08-29 | Auth/onboarding pages sign a demo session directly into `stores/auth` rather than calling `useAuthSession`'s `completeSignIn` | `completeSignIn` expects a real JWT with `role`/`tenant_slug`/`tenant_id` claims to decode via `jwt-decode`; no backend auth endpoint exists yet. Faking a JWT string felt more misleading than naming the stub: each auth view sets `auth.token = 'demo-token'` and routes to the chosen demo tenant's dashboard directly, with a code comment pointing at the real shape once `POST /api/auth/login` exists. Google sign-in is a `toast.info` stub, not a fake OAuth flow |
| 2026-08-29 | One shared `TenantShell` layout component generalizes the dashboard sample's hand-authored `.app`/`.side`/`.main` HTML into a Vue component driven by `fixtures/nav.js`, rather than each of the ~20 tenant-scoped views re-declaring the sidebar | The sample was one static page; the product needs the same chrome on every page with the active nav item, tenant switcher and pack-availability-aware nav groups (`insightNav` only lists a pack's link if the tenant's `enabled_packs`/`optional_packs` includes it) computed once. `AuthShell` is the equivalent for the five auth pages, sharing the `.card` token system without assuming a tenant context exists |
| 2026-08-29 | Phase C resequenced: frontend builds all pages and views first once architecture is ready, backend then completes module by module, core features first | User direction. See `docs/WORKPLAN.md` sequencing note. Frontend can build ahead of most backend modules because the Evidence contract and Stats API surface (`docs/EVIDENCE_CONTRACT.md`, `docs/STATS_API.md`) are already fully specified, so it can build against fixtures and swap in the real API per view as each backend module lands |
| 2026-08-29 | Cross-tenant hierarchical pooling secured with differential privacy: DP-noised sufficient statistics per tenant, batched weekly refresh, per-tenant epsilon budget, sensitivity test gate | User: privacy is a must, aggregated/anonymised patterns are fine for prior training, but tenant-level guardrails are required. Concentration and min-tenant floors alone bound influence, not observability, so they could not close a differencing attack on their own. This unblocks `bayes.hierarchical_pool` in `docs/STATS_CATALOG.md`. |
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

- **Four of the six streams have no backend model.** The adapters mark each gap with a `TODO`
  naming the missing model rather than inventing one. In descending order of consequence:
  **(1) the exposure log** (`nudge_sent`/`delivered`/`opened`/`acted` with `arm_ref`) has no table,
  so Pack 2's `experiments.*` and `bandits.*` have no input at all: this is the gap that blocks a
  whole pack rather than degrading a service. **(2) the ledger** has no model, so `forecast_risk`'s
  money half, `montecarlo.runway_shortfall`, `risk.late_payment_risk` and `audit.*` have nothing to
  read, and `rwa_society`'s two most interview-grounded headline statistics (verification lag,
  receipt-collection gap) cannot exist. **(3) decision/option/ballot** has no model, so
  `governance_insight` is unavailable; whoever adds it must make `declared_rule` non-nullable from
  the first migration, since spine rule D1 requires it to be recorded before any ballot is cast and
  backfilling it later leaves a history of decisions whose rule cannot be trusted. **(4) member
  lifecycle events** (lapse, reinstate, exit) do not exist, so `survival.churn_curve` would see a
  population nobody has ever left; its floor of 30 observed exits is what stops that being
  published. Also missing: a request event log (no reassignment, pause/resume, escalation or
  withdrawal, so `competing_risks_cif` cannot estimate and `duration_active_hours` is unavailable,
  which means `campus_club`'s declared `sla_clock="active"` cannot actually be honoured yet), and
  any ordinal/survey response table.
- **`rwa_society` cannot categorise a complaint yet.** `Request.category` is still the ported
  Campus Connect enum (EVENT, GROUP, CERTIFICATE, TECHNICAL, GENERAL) and no column holds a society
  complaint category, so the adapter maps every row to `"other"` and counts it as unmapped, loudly,
  which is the declared behaviour. Consequence: `survival.logrank_compare` and
  `survival.cox_hazard_ratios` have one category to work with, so "sewage requests resolve 2.4x
  slower than electrical", which the interview evidence makes a budget argument, cannot be computed.
  `campus_club` is fine: its legacy enum maps onto its declared vocabulary.
- **`app/verticals/manifests/*.json` is still the backend's two provisional manifests** and has not
  been reconciled against `docs/VERTICALS.md`. The adapters therefore carry their vocabulary,
  strata schema, k-anonymity floor, reopen policy and SLA clock as class attributes rather than
  reading the manifest, with the `campus_club` `department` list a placeholder. The reconciliation
  card should collapse the two: an adapter reading its own vocabulary is a vertical defined in two
  places.
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
