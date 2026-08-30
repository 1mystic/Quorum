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
| 2026-08-30 | **Pack 1 implemented for real (card C.9, statistician).** All 19 `reliability_ops` services now have bodies instead of `NotImplementedError`: `survival.py` (delayed-entry Kaplan-Meier with Greenwood bands, Brookmeyer-Crowley median, SLA attainment, first-response and churn curves, Mantel-Haenszel log-rank with Holm-adjusted pairwise tests, Cox with Efron ties + Newton-Raphson + profile-likelihood intervals + the Grambsch-Therneau Schoenfeld test, Aalen-Johansen competing risks, and the `naive_vs_km_gap` demonstration figure), `spc.py` (EWMA and CUSUM with limits solved for a declared ARL0 by the Brook-Evans Markov chain, plus an exact-quantile Poisson/negative-binomial u-chart), `changepoint.py` (PELT with BIC/mBIC penalties, seeded bootstrap intervals on the break *date* and seeded permutation p-values), `queueing.py` (Little's Law with a blocking steady-state test, M/M/c, Erlang-C staffing with its sensitivity curve, Pollaczek-Khinchine, backlog projection) and `fairness.py` (Gini with a BCa bootstrap and k-anonymised rows, Hungarian balanced assignment). Two new support modules: `app/stats/numeric.py` (norm/chi-square/t/Poisson/negative-binomial/incomplete-gamma/incomplete-beta, Gaussian elimination, OLS with a t-test, seeded BCa bootstrap) and `app/stats/series.py` (period extraction, moving-range and robust sigma, Ljung-Box). Five published datasets vendored under `backend/tests/unit/stats/data/` (`lung`, `rossi`, `heart`, `nile`, `mgus2`) so the whole suite runs offline. **125 new tests, 842 in `tests/unit/stats`, 884 in `tests/unit`, all passing**; the purity lint passes over all 41 modules unchanged. Three factual corrections to `docs/STATS_CATALOG.md` and the matching Method Cards, all in the known-answer column, all because the implementation reproduced the real published tables and the prose did not match them: the EWMA constant `L=2.703` belongs to ARL0=370, not 500 (the ARL0=500 row is 2.615/2.814/2.998/3.071); the CUSUM and Poisson entries no longer claim to assert against Montgomery tables whose raw data is not vendored; and `fairness.balanced_assignment` cites exhaustive enumeration rather than `scipy.optimize.linear_sum_assignment`, since scipy is not a dependency |
| 2026-08-30 | **Ledger domain plus `insight_runs`/materialization worker (card C.10, backend-porter).** Two commits. **Ledger**: `app/models/ledger.py` (`Due`, `Payment`, `Receipt`, `Contribution`, `Expense`; migration `700cabcdd2f5`), `LedgerRepository` (tenant-scoped, same pattern as `RequestRepository`), `LedgerService`/`app/api/ledger.py` (raise a due, record a payment, verify it, issue/collect a receipt, add a contribution/expense, all vocabulary-checked against the vertical adapter same as `RequestService`). `PortedSchemaAdapter.ledger_entries` (`app/verticals/adapters/base.py`) now genuinely maps `Due`/`Payment`/`Receipt`/`Contribution`/`Expense` rows to `LedgerEntry` atoms instead of returning `()`: a due and the payment that settles it fold into one signed entry rather than double-counting, `verified_at`/`receipt_issued_at`/`receipt_collected_at` (the two rwa_society interview-grounded headline lags) are populated from whichever payment settled the due, and outflow is sign-flipped per the atom's contract. The stray duplicate `ledger_entries` stub further down the same class (silently overriding the real one, since Python takes the last method defined) is deleted. 10 new offline tests in `tests/unit/stats/test_ledger_adapter.py` (plain `SimpleNamespace` fixtures, no ORM, no DB) prove signs, categories, the settlement fold and the two lag fields; **all 10 pass**. **Materialization**: `InsightRun` model (`docs/STATS_API.md` section 2's exact shape; migration `2678b05f0dc4`), `InsightRunRepository` (append-only, `superseded_by` chains), `InsightsService`/`app/api/insights.py` (`GET .../insights/packs`, `.../insights/{pack}`, `.../insights/{pack}/{service}`, `.../history`, `.../health`, plus a top-level unauthenticated `GET /api/methods/{id}`), and `InsightMaterializer` (`app/services/insight_materializer.py`): walks `registry.implemented_ids()`, fetches stream rows through the repositories, hands them to the vertical adapter for atoms, calls `app.stats.streams.reduce` to get units, calls the pure function, stores the returned `Evidence` whole. **What it honestly could not prove against real Postgres data, and why**: `app.stats.streams.reduce.request_spells`/`flow_periods` (card C.7's declared, still-unimplemented reducers, statistician's file, out of this card's boundary) still raise `NotImplementedError`, so every one of the 19 Pack-1 services currently materializes as a correctly-shaped `insufficient_data` row with a caveat naming the failure, exactly `docs/STATS_API.md` section 8's documented worker-failure state ("a missing tile teaches users the dashboard is unreliable and a tile that says why does not"), never a fabricated number and never a silently skipped row. Proven anyway, without touching `app/stats/`: `tests/unit/services/test_insight_materializer.py` monkeypatches `stream_reduce.request_spells` with a small, honestly-labelled reduction written only in the test file, feeds it 40 real `RequestEvent` atoms (35 resolved at exactly 8 days, 5 still open), and asserts the worker's own code carries the number all the way into an `insight_runs`-shaped row: **n=40, n_censored=5, value=8.0**, matching a hand-checked answer, plus a second test proving the honest-degrade path fires with no monkeypatch. `tests/integration/test_insights.py` is the DB-backed twin (same monkeypatch technique, same reason documented at its top) that seeds real `Request` rows through the real API and asserts the cache round-trip end to end; it needs Postgres, which this sandbox does not have, so it is written and collects cleanly but has not been run. Once `streams/reduce.py` lands for real, nothing in `insight_materializer.py` changes. Full offline suite: **961 passed** (the one `test_calibration.py` failure observed is the statistician's own uncommitted concurrent Pack 3 work on `app/stats/calibration.py`, confirmed via `git status`/`git diff --stat` before touching anything, out of scope here exactly like the C.8 session's `survival.py` note); whole suite **1487 tests collect, zero import errors**; `alembic heads` resolves to one head, five-migration chain. Committed in two path-disjoint groups (ledger domain + adapter wiring, then materialization), `backend/app/stats/` untouched throughout |
| 2026-08-30 | **Pack 3 implemented for real (card C.13, statistician).** All 21 `forecast_risk` services now have bodies: `forecast.py` (loess-based STL, Holt-Winters in the ETS(A,A_d,A/M) state space form with bounded coordinate descent, SARIMA by conditional least squares with a Nelder-Mead simplex and a bounded AICc order search, rolling-origin backtest, and the three named compositions), `calibration.py` (pool-adjacent-violators isotonic, Platt with the prior correction, the Murphy decomposition and reliability diagrams with Wilson intervals per bin), `conformal.py` (split conformal, the censoring-aware Candes-Lei-Ren ETA bound with inverse-probability-of-censoring weights, and Mondrian class-conditional intervals), `drift.py` (PSI, two-sample KS with a Holm correction, label shift with Wilson and Newcombe intervals), `montecarlo.py` (correlated runway simulation) and `risk.py` (out-of-fold L2 logistic with nested out-of-fold calibration, gated on Brier skill and ECE). Support added to `numeric.py`: Wilson and Newcombe intervals, a deterministic Nelder-Mead, and IRLS logistic. **194 new tests, 1014 in `tests/unit/stats`, 1060 in `tests/unit`, all passing.** Headline measured numbers: Holt-Winters **MASE 0.156 vs seasonal-naive 1.001** over 34 folds and SARIMA **0.186**, with the gate's negative control (a seasonal random walk) making Holt-Winters **lose at 1.251 vs 1.002** and the service substituting the baseline; split conformal attaining **0.8981 / 0.9008** against nominal 0.90 and **0.9493 / 0.9514** against nominal 0.95, inside the theorem's two-sided band; and the naive resolved-only ETA covering **76.0%** where it claims 90% against the censoring-aware bound's **90.3%**. Two real bugs caught by the tests and fixed with named regression tests (PSI collapsing to 0.0 on a large shift because bins thin in *either* window were merged; risk ECE reading exactly 0.0000 because the calibration map was fitted on the scores it was then judged against). Seven known-answer corrections to `docs/STATS_CATALOG.md` and the matching Method Cards, five because the stated oracle is not vendored and there is no network access here, three substantive (the Murphy three-term identity is false for a continuous forecast; the inverse-Gaussian first-passage formula is for continuous monitoring and a ledger is monitored at period ends; the MASE check must not be blocking or the substituted baseline would be suppressed too) |

## In flight

Design and branding are done. Three agents now running in parallel on disjoint paths:

- **statistician**: **A.2 to A.8, C.6, C.7 and C.9 complete.** The statistical architecture exists in
  code and **Pack 1 is now real mathematics**: the envelope, the registry of all 81 services with
  their Method Cards, the six streams, two vertical adapters, and 19 implemented services. Nothing
  is left half-wired; what is not implemented raises `NotImplementedError` and says which document
  specifies it.

  **What is implemented versus stubbed.** Implemented and tested: everything in `contracts.py`
  (including `params_hash`, the render-state resolution and the wire format), the whole registry
  including its import-time invariants, every stream dataclass and its validation, both adapters,
  and **all 19 Pack 1 services** (`survival.*` 9, `spc.*` 3, `changepoint.*` 1, `queueing.*` 5,
  `fairness.*` 2, of which `queueing.backlog_projection` is a composition awaiting a real Pack 3
  forecast to consume). Still stubbed: the 62 services of Packs 2, 3 and 4, the atom-to-unit
  reducers in `streams/reduce.py` and the cross-stream `streams/capacity.py` reducer. That split is
  deliberate: each service body arrives with its known-answer test rather than in a batch, since a
  stub that returns a plausible number is worse than one that raises.

  **The purity lint is real and was verified by breaking it.** `tests/unit/stats/test_purity.py`
  AST-walks all 38 modules under `app/stats/` and fails on a forbidden import, a clock read or
  mutable module-level state. It was tested by planting `import sqlalchemy`, `from app.repository
  import ...`, `datetime.utcnow()` and `CACHE = {}` into `app/stats/survival.py`: three tests failed
  with the file, the line number and the rule, and passed again once reverted. It also has its own
  known-answer test so a future refactor cannot quietly neuter it, and it is AST-based so prose
  about the rule is not a breach of it.

  **Pack 1's known answers, actually reproduced** (numbers from the shipped code, not from a
  snapshot): `lung` median 310 days, 95% CI 285 to 363, and S(365) = 0.409 (0.345, 0.486), matching
  R `survfit` exactly; `survdiff ~ sex` chi-square 10.327, p = 0.00131 against the published 10.3,
  p = 0.001, with group medians 426 and 270; `rossi` Cox coefficients fin -0.3794, age -0.0574,
  race 0.3139, wexp -0.1498, mar -0.4337, paro -0.0849, prio 0.0915 against the published values to
  under 1e-3, partial log-likelihood -658.748; `cox.zph` global p = 0.0142 with `age` FAIL and `fin`
  PASS; EWMA limit constants 2.617 / 2.816 / 2.999 / 3.071 against Lucas and Saccucci's published
  2.615 / 2.814 / 2.998 / 3.071 for ARL0 = 500, and ARL1 = 10.33 against 10.3; CUSUM k=0.5, h=5
  giving ARL0 465.6, ARL1 10.38 / 5.75 / 4.01 against the published 465 / 10.4 / 5.75 / 4.01;
  Erlang-C requiring 24 agents at 20 erlangs, 14 at 10 and 5 at 3 for an 80% within 20 seconds
  target, matching the standard staffing tables; PELT finding the single Nile changepoint after
  1898 with segment means 1097.75 and 849.97.

  **The censoring regression passes and the two numbers genuinely diverge.**
  `tests/unit/stats/test_survival.py::test_the_censoring_regression` builds 100 requests where the
  mean of the 51 closed ones is exactly 3.1 days and the Kaplan-Meier median is exactly 8.0, and
  asserts we report 8.0 everywhere, that `n_censored` is 49, and that `naive_vs_km_gap` reports the
  gap of 4.9 days. The companion test filters the open requests out, which is what
  `WHERE resolved_at IS NOT NULL` does, and the median collapses to 2.0: the bias is downward and
  it is a factor of four.

  **Pack 3 is now real mathematics too (card C.13).** All 21 `forecast_risk` services have bodies.
  41 of the 81 registered services are now `implemented=True`; what remains stubbed is Packs 2 and
  4, plus `streams/reduce.py` and `streams/capacity.py`, which are the open statistician items and
  are now the single thing blocking the materialization worker from producing real numbers rather
  than honest `insufficient_data` rows.

  **The MASE gate is real and was verified in both directions.** On a trend-plus-season series
  Holt-Winters reaches **MASE 0.156 against seasonal-naive's 1.001** over 34 rolling-origin folds
  and SARIMA reaches **0.186**; on a seasonal random walk, where seasonal-naive is the optimal
  predictor by construction, Holt-Winters **loses at 1.251 against 1.002** and the service
  substitutes the baseline forecast, sets `structure.served = "seasonal_naive"` and says so in a
  caveat. A gate tested only in the passing direction is not a gate, so both fixtures ship.

  **Conformal coverage, measured rather than eyeballed.** Split conformal on a deliberately
  non-Gaussian heteroskedastic process attains **0.8981 and 0.9008 against a nominal 0.90** (at 99
  and 999 calibration points) and **0.9493 and 0.9514 against a nominal 0.95**, every one inside
  the theorem's `[1 - alpha, 1 - alpha + 1/(n+1)]` band within two binomial standard errors over
  20,000 trials. Both ends are asserted: a coverage-only test would pass an implementation that
  returns the whole real line. One subtlety cost a debugging pass and is recorded in the test file:
  the guarantee is **marginal**, so the experiment must draw a fresh calibration set per trial;
  conditioning on one calibration set measures a different quantity that legitimately sits outside
  the band at small n.

  **The censoring negative control is the sharpest number in the pack.** On a fixture with lognormal
  waits, exponential censoring and 43% of requests still open, the naive resolved-only bound claims
  90% and **actually covers 76.0%**, while the censoring-aware Kaplan-Meier bound covers **90.3%**.
  A fourteen point shortfall, in the direction that flatters the ETA.

  **Two real bugs were found by these tests and are fixed with regression tests naming them.**
  (1) `drift.psi` merged bins that were thin in *either* window, so a feature that moved clean off
  its reference bins collapsed to one bin and reported PSI **0.0** for the largest shift the system
  will ever see; merging now looks only at the reference counts and the same fixture reports 12.46.
  (2) `risk.*` fitted the calibration map on the same out-of-fold scores it then scored against, and
  isotonic regression is flexible enough to absorb the noise, so the expected calibration error came
  out as exactly **0.0000**, which is the number a gate reports when it is measuring nothing. The
  map is now fitted on the other folds and the held-out error is a genuine 0.029.

  **Seven known-answer corrections to `docs/STATS_CATALOG.md` and the matching Method Cards**, all
  in the same spirit as Pack 1's three. Four are "the stated oracle is not vendored here and there
  is no network access, so claiming it would be a known answer nothing checks": `forecast.sarima`
  (AirPassengers), `forecast.holt_winters` (FPP3 tourism and M3), `forecast.stl_decompose`
  (statsmodels on `co2`), `calibration.platt_calibrate` (sklearn), `drift.label_shift` (Newcombe's
  worked examples). Each was replaced with something the tests actually assert, and in two cases the
  replacement is stronger than the original: Platt is now checked against a vanishing gradient at
  the optimum, which is a theorem, rather than against another library that could share our
  mistakes. Three are substantive mathematics: `calibration.brier_decomposition`'s three-term Murphy
  identity is **false** for a continuous forecast and the exact form carries a fourth within-bin
  term (the three-term form is asserted separately under the constant-within-bin condition where it
  is exact); `montecarlo.runway_shortfall` cannot equal the inverse-Gaussian first-passage formula
  because that is for *continuously* monitored Brownian motion whereas a ledger is monitored at
  period ends, so the test brackets the simulator between two exact closed forms instead; and
  `forecast.holt_winters`'s MASE check is **not** blocking, because a blocking failure empties the
  value and the whole point of that failure path is that the substituted baseline is still shown.

  **Three deliberate design calls worth knowing about.** The `series` value shape follows
  `docs/EVIDENCE_CONTRACT.md` section 4's parallel arrays (`x`, `y`, `lo`, `hi`) rather than the
  catalog's sketched `{"t", "yhat"}` row dicts, since the contract is the normative document for the
  envelope. `conformal.survival_eta_bound` guarantees only the **lower** bound, because under right
  censoring the data is informative about short waits and systematically missing about long ones, so
  no distribution-free upper bound exists; the point and upper figures come from the censoring-aware
  Kaplan-Meier estimate and are labelled model-based in a caveat. And `risk.*` builds its per-member
  interval from fold disagreement rather than from the absolute residual, because conformalising
  `|y - p|` for a binary outcome yields a valid but near-vacuous interval about the *coin flip*
  rather than about the estimate; the caveat says which uncertainty it covers.

  **`risk.late_payment_risk` refuses `model="gbdt"` with a ValueError** naming the limit rather than
  silently fitting something else: a gradient-boosted model needs the scientific stack that
  `PLAN.md` deliberately keeps off the light tier.

  **1014 tests in `tests/unit/stats`, 1060 in `tests/unit`, all passing**; 1585 collect clean. The
  purity lint passes over all 41 modules and caught one genuine violation while this was being
  written (a mutable module-level dict in `conformal.py`), which is the lint doing its job.

  **`streams/reduce.py` and `streams/capacity.py` are now the top statistician item**, and they are
  the bottleneck for the whole product: the worker, the API and every dashboard tile are built and
  waiting on them. The backend has `RequestEventLog` and the ledger tables, so both reducers can be
  written against real atoms rather than against a shape. Packs 2 and 4 are the remaining
  mathematics.
- **backend-porter**: **C.1-C.5 done, C.8 (`request_flow` end to end) done, C.10 (`insight_runs` +
  materialization worker + ledger domain) done.** See the 2026-08-30 `Done` rows and decision log
  entries for the full shape. What C.8 did *not* do, on purpose, since it is the statistician's file:
  wire `app/verticals/adapters/*.request_events` (or `streams/reduce.py`) to actually consume
  `RequestEventLog` rows via the new `RequestRepository.stream_events`: the table and the fetch
  method exist and are tenant-scoped, but nothing yet turns those rows into the
  `assigned`/`paused`/`escalated`/... stream atoms. Also not done: the mechanical route-prefix /
  category-vocabulary cleanup of `tests/integration/test_request.py` (a route-prefix problem that
  predates this card, see the older decision log entry below; its category fixtures now also assume
  the pre-C.8 enum values, e.g. `"GENERAL"`, which no longer validate for `campus_club`'s real
  vocabulary once the routes are fixed to `/api/t/{slug}/...`).

  **What C.10 could not finish, and why it is not this card's gap to close**: `streams/reduce.py`'s
  `request_spells`/`flow_periods` are still `NotImplementedError` (statistician's file, out of this
  card's explicit boundary), so no Pack-1 service can materialize a real number against live data
  yet; the worker is proven correct against a monkeypatched reducer instead (see the C.10 `Done`
  row). Once the statistician lands the real reducer, `InsightMaterializer` needs zero changes for
  every `insight_runs` row to start carrying genuine numbers. Also not done in this card, named but
  not attempted: the `POST /api/t/{slug}/insights/preview` endpoint (admin-only synchronous
  recompute via a job), `PUT .../insights/packs/{pack_id}` (toggling a pack on writes
  `Tenant.enabled_packs` today only through the ORM/seed path, not an endpoint), and a real
  scheduler/cron entrypoint (`InsightMaterializer.materialize_all` is callable from a script or a
  test today; nothing invokes it on the cadence table in `docs/STATS_API.md` section 3 yet). A role
  check for who may verify a payment or issue a receipt (currently any `MEMBER` of the tenant, same
  breadth as `RequestService`'s lifecycle actions) is a follow-up once the platform has a treasurer
  role concept. Next unblocked backend-porter card is **C.18** (agent stats tools returning `Evidence`,
  deps C.9 which is done); C.19 (seed script) is still blocked on C.15 (Pack 4 domains).
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
| 2026-08-30 | A materialization job that catches `NotImplementedError` from `streams.reduce` writes a real, honestly-shaped `insufficient_data` `insight_runs` row rather than skipping the service | `docs/STATS_API.md` section 8 already specifies this as the documented worker-failure state for any computation that could not complete, not only for a DB error. Treating an unimplemented reducer as the same case rather than a special one meant the worker's control flow needed no `if reducer_not_ready` branch, and it means the moment the statistician lands `streams/reduce.py`, every affected row starts carrying a real number on the very next scheduled run with no code change anywhere in `insight_materializer.py` |
| 2026-08-30 | `InsightMaterializer._compute` inspects the pure function's own signature (`inspect.signature`) to decide what to pass it, rather than a per-service dispatch table | 19 Pack-1 services, and eventually 62 more, would otherwise need 81 hand-written call sites naming their exact keyword arguments, which drifts from `app/stats/registry.py` the moment a signature changes there. Reading `(spells, window, ...)` vs `(periods, window, ...)` vs `(series, window, ...)` off the function itself, then refusing (not guessing) when a service needs a parameter this worker does not yet supply (`queueing.mmc_metrics`'s `arrival_rate`/`service_rate`/`servers`, for instance), means a wrong call is a loud `NotImplementedError` caveat, never a `TypeError` crash or a silently wrong argument |
| 2026-08-30 | A due and the payment that settles it fold into **one** `LedgerEntry`, not two | The atom's own contract makes `due_at` receivables-only and `LedgerEntry` a single signed movement; a due showing the receivable and its settling payment separately would double the apparent inflow the moment `ledger_periods` sums entries by category. The verification lag and receipt fields fold onto the due's entry from whichever payment settled it, so `DueSpell` (rule L1) still has exactly one row per receivable to reduce |
| 2026-08-30 | The MASE gate's failure is a **non-blocking FAIL that substitutes the seasonal-naive forecast**, not a blocking one | Two existing rules collided. The Pack 1 decision "a blocking check failure empties the `value`" and the catalog's "a blocking MASE failure returns the seasonal-naive forecast, not an error" cannot both hold: blocking empties the very substitute the second rule exists to deliver, and the UI's `not_interpretable` state would hide it. The gate now emits `status="FAIL", blocking=False`, sets `structure.served="seasonal_naive"`, names both MASE figures in the check detail and in a caveat, and the envelope renders as `qualified`, which is exactly what it is: a number you can read with a stated qualification. The catalog line was corrected rather than the code bent to it |
| 2026-08-30 | `conformal.survival_eta_bound` guarantees the **lower** bound only, and labels the point and upper figures model-based | Under right censoring the data is informative about short waits and systematically missing about long ones, so a distribution-free UPPER bound on the waiting time does not exist: beyond the censoring horizon the honest statement is "longer than this". Candes, Lei and Ren give a valid lower predictive bound and that is what is underwritten by a theorem; the point and upper come from the censoring-aware Kaplan-Meier estimate. The alternative was to ship an upper bound with a guarantee it cannot have, on the one number a non-expert will trust and quote. The negative control was re-pointed accordingly: it is the naive resolved-only *upper* bound that under-covers (76% against a claimed 90%), because dropping open tickets removes exactly the slow requests |
| 2026-08-30 | The Murphy decomposition is reported with a **fourth `within_bin` term**, and the catalog's three-term identity was corrected | `Brier = reliability - resolution + uncertainty` is exact only when the forecast is constant inside each bin. For a continuous forecast the cross term does not vanish and the exact identity needs `within_bin = mean(d_i^2 - 2 d_i y_i)`. The choice was to state the true identity or quietly widen the tolerance until the false one passed; a document whose subject is honest measurement cannot take the second option. Both forms are asserted: four terms on arbitrary input, three under the constant-within-bin condition where it is genuinely exact, and `within_bin` is in the envelope so a reader can check the arithmetic |
| 2026-08-30 | `montecarlo.runway_shortfall` is tested against a **bracket of two exact closed forms**, not against the inverse Gaussian directly | The reflection-principle first-passage formula is for *continuously monitored* Brownian motion. A ledger is monitored at period ends, because that is when a treasurer looks, so a path may dip below the floor and recover inside one month without being counted. The two quantities genuinely differ and the continuous one is strictly larger. Asserting equality would have forced either a wrong simulator or a padded tolerance, so the simulator is pinned exactly at horizon 1 (where running minimum and terminal balance coincide) and bracketed between the exact terminal probability and the continuous one over longer horizons |
| 2026-08-30 | The `risk.*` per-member interval comes from **fold disagreement**, not from conformalising the absolute residual | Conformalising `|y - p|` is valid but nearly useless for a binary outcome: those residuals cluster at 0 and 1, so a member scored 0.8 gets roughly `[0.08, 1.0]`. That interval is about the coin flip, and a reader asking "how sure are we of this 0.8" is not asking about the coin flip. Fold disagreement answers the question actually being asked and the caveat states precisely which uncertainty it covers, so the two cannot be confused |
| 2026-08-30 | The `series` value shape follows the **contract's parallel arrays**, not the catalog's sketched row dicts | `docs/EVIDENCE_CONTRACT.md` section 4 defines `series` as `{"x", "y", "lo", "hi"}`; `docs/STATS_CATALOG.md` sketched `{"t", "yhat", "lo", "hi"}` rows. The contract is the normative document for the envelope and the frontend components are built against it, so the code follows the contract and the catalog was corrected. The backtest summary rides in the same dict under `structure`, which is what the catalog meant by "a series plus a structure block" |
| 2026-08-30 | `risk.late_payment_risk` **raises** on `model="gbdt"` rather than silently fitting the logistic model | The signature the catalog specified offers both. A gradient-boosted model needs the scientific stack that `PLAN.md` deliberately keeps off the light `web` tier, so it cannot be honoured here. Quietly substituting a different model class behind a parameter the caller explicitly set is the kind of silent divergence between the label and the mathematics that this whole package exists to prevent; naming the limit costs one error message |
| 2026-08-30 | Pack 1 is implemented in the **standard library only**: no numpy, no scipy, no lifelines, no statsmodels | `PLAN.md` already splits deploy into a light `web` process and a heavy `worker` precisely because the scientific stack is around half a gigabyte. Pack 1 is closed-form mathematics over at most a few thousand rows, so the handful of special functions it needs (`app/stats/numeric.py`: incomplete gamma and beta, the normal quantile, exact Poisson and negative-binomial tails, Gaussian elimination, a seeded BCa bootstrap) are written out and checked against published table values. The result is that the whole engine imports anywhere, `pyproject.toml` did not have to change while another agent was editing the backend, and every known-answer test is against a published figure rather than against another library that could be wrong in the same way |
| 2026-08-30 | The survival time scale is **age since the request opened**, with `entry = at_risk_from - opened_at` and `exit = entry + duration` | Spine rule C3 requires the delayed-entry `(entry, exit]` risk set, and rule C2 defines `duration_hours` as time under observation. Reconciling the two on the "time under observation" scale would silently discard the age a request had already accumulated when the window opened, which is exactly the bias left truncation exists to prevent. Checked against the Stanford `heart` data by counting the risk set straight off the CSV, and against an exponential simulation with staggered entry where the estimator has to recover `exp(-rate * t)` |
| 2026-08-30 | A blocking check failure empties the `value` in the envelope, it does not merely flag it | `docs/EVIDENCE_CONTRACT.md` §3 makes suppression the UI's job in the `not_interpretable` state, but a mis-wired client, an agent tool or a CSV export would still find a number sitting there. Emptying it in the service means the number does not exist to be printed. The suppressed figure is replaced by the check's `detail`, which is the sentence a reader actually needs: "the effect of age changes over time, so a single hazard ratio would be misleading" |
| 2026-08-30 | Cox intervals are genuine **profile-likelihood** intervals, not Wald intervals relabelled | The Method Card says `profile-95` and a card that describes a different interval than the code computes is the exact drift the registry parity test exists to prevent. Made affordable by accumulating the Efron risk sets in one downward sweep, which is O(n p^2) per iteration instead of O(events * n * p^2), and by solving for each bound with a one-dimensional Newton step whose derivative is the profile score. The whole seven-covariate `rossi` fit with fourteen profile bounds runs in about 0.7 seconds |
| 2026-08-30 | PELT searches with a floor of 2 periods and the service suppresses candidates near an edge, rather than flooring the search at `min_segment` | The first draft floored the search at `min_segment`, which made the `edge-changepoint` check unreachable: no candidate could ever be near an end, so a blocking check that `docs/STATS_CATALOG.md` calls "the single most common false positive in this family" could never fire. Suppression the reader can see beats a constraint that hides the same candidates inside the optimiser |
| 2026-08-30 | Three known-answer statements in `docs/STATS_CATALOG.md` were corrected rather than the code being bent to match them | The EWMA entry paired `L = 2.703` with ARL0 = 500; 2.703 is the ARL0 = 370 constant at `lam=0.10`, and the solver reproduces both published rows. The CUSUM and Poisson entries claimed to assert chart arithmetic against Montgomery examples whose raw tables are not vendored here, and `fairness.balanced_assignment` cited scipy as a second oracle when scipy is not a dependency. A catalog that states a known answer the test does not actually check is worse than one that says which identity it checks instead |
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

- **Three of the six streams still have no backend model** (card C.10 closed the fourth, `ledger`;
  see its `Done` row). The adapters mark each remaining gap with a `TODO` naming the missing model
  rather than inventing one. In descending order of consequence:
  **(1) the exposure log** (`nudge_sent`/`delivered`/`opened`/`acted` with `arm_ref`) has no table,
  so Pack 2's `experiments.*` and `bandits.*` have no input at all: this is the gap that blocks a
  whole pack rather than degrading a service. **(2) decision/option/ballot** has no model, so
  `governance_insight` is unavailable; whoever adds it must make `declared_rule` non-nullable from
  the first migration, since spine rule D1 requires it to be recorded before any ballot is cast and
  backfilling it later leaves a history of decisions whose rule cannot be trusted. **(3) member
  lifecycle events** (lapse, reinstate, exit) do not exist, so `survival.churn_curve` would see a
  population nobody has ever left; its floor of 30 observed exits is what stops that being
  published. Also missing: any ordinal/survey response table. (`RequestEventLog` closed the fourth
  gap this list used to name, card C.8; `competing_risks_cif` and `duration_active_hours` are
  blocked on `streams/reduce.py` folding those rows in, not on a missing table, see C.10's `Done`
  row and the statistician "in flight" note above.)
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
