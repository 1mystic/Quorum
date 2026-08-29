# Vertical manifests

*Card A.7. Depends on `docs/DATA_SPINE.md` and `docs/STATS_CATALOG.md`.*

A vertical is **configuration, not code**. It is a frozen dataclass in `backend/app/verticals/`
that names labels, default packs, categories, roles, auth mode, strata schema, privacy floor and
the adapter's stream mappings. No statistical service knows a vertical exists.

Seven ship: `rwa_society`, `campus_club`, `ngo_volunteer`, `alumni_chapter`, `housing_coop`,
`sports_club`, `professional_guild`.

---

## 0. The manifest shape

```python
@dataclass(frozen=True)
class VerticalManifest:
    id: str
    name: str
    tagline: str

    # Vocabulary. The ONLY place domain words live.
    labels: Mapping[str, str]          # canonical -> displayed, e.g. "request" -> "Complaint"

    # Streams
    streams_supported: frozenset[str]
    request_categories: tuple[str, ...]
    request_priorities: tuple[str, ...]
    ledger_categories: tuple[str, ...]
    participation_kinds: tuple[str, ...]
    exit_reasons: tuple[str, ...]
    strata_schema: Mapping[str, tuple[str, ...]]

    # Packs
    default_packs: tuple[str, ...]
    optional_packs: tuple[str, ...]
    disabled_services: tuple[str, ...]     # services that are wrong for this vertical
    service_overrides: Mapping[str, Mapping[str, Any]]   # per-service parameter defaults

    # Access
    roles: tuple[RoleSpec, ...]
    auth_modes: tuple[str, ...]            # first is the default
    membership_rule: str | None            # e.g. "email_suffix" | "invite" | "admin_approval"

    # Policy
    k_anonymity_threshold: int
    dp_required_for: tuple[str, ...]       # service ids that must add Laplace noise
    reopen_policy: Literal["new_spell", "extend"]
    sla_clock: Literal["wall", "active"]
    default_season_length: int             # periods per seasonal cycle for Pack 3
    timezone: str
    currency: str

    # Modules
    modules: Mapping[str, bool]            # certificates, documents, knowledge_base, ...
    onboarding: OnboardingCopy
```

`RoleSpec` carries `id`, `label`, `inherits`, `can_see_individual_risk_scores: bool` and
`can_see_per_stratum_breakdowns: bool`. Those last two are on the role, not on a permission table,
because they are the two capabilities that can cause a privacy incident and they should be visible
when reading a manifest.

**Rule V1.** `k_anonymity_threshold` is a floor with no runtime override. A manifest may raise it,
never lower it below 5.

**Rule V2.** `disabled_services` is expressive on purpose. A service that is statistically wrong for
a vertical is switched off in the manifest rather than left available with a caveat, because a
caveat next to a plausible-looking number does not stop anyone.

**Rule V3.** `labels` maps only *display* strings. The database column is `request.category`, always.
A vertical cannot rename a field.

---

## 1. `rwa_society` (complete, demo-seedable)

> Resident welfare association or apartment society. **The design reference vertical**, and the one
> the interview evidence in `RWA_Master_Context.md` §4 to §5 actually describes.

**Which services matter here, and why.** The interview findings choose the pack, not a feature list:

- Payment flow is *bank transfer, WhatsApp screenshot, manual treasurer verification, physical
  register, receipt frequently uncollected*. That makes `LedgerEntry.verified_at` and
  `receipt_collected_at` the two most valuable columns in this vertical, and it makes
  **verification lag** and **receipt-collection gap** headline statistics, each computed as a
  survival curve over a censored duration rather than an average.
- Cash handed person to person causes reconciliation errors. So **`ledger` reconciliation
  completeness** and a **`survival` curve on time-to-reconcile** matter more than any forecasting
  sophistication.
- STP maintenance costs roughly 6 lakh a year and the vendor competence gap is real. That makes
  **Pack 2 vendor ranking with shrinkage** genuinely load-bearing: a committee will fire a vendor on
  three data points otherwise. It also makes **Cox hazard ratios by category** worth having, because
  "STP requests resolve 2.4x slower than electrical" is a budget argument.
- Roughly 99% of residents use WhatsApp and some are uncomfortable with a new app. So `channel` is a
  first-class covariate everywhere, phone plus OTP is the default auth mode, and the **nudge
  experiment arms are channel and send-hour**, which is the single most valuable thing Pack 2 can
  test here.
- Complaints are per-block and blocks are small. **k-anonymity is 5 and DP noise is required** on
  per-block figures. This is the vertical that made `privacy.py` non-optional.

| Field | Value |
|---|---|
| `labels` | request -> "Complaint", member -> "Resident", group -> "Committee", decision -> "Resolution", ledger -> "Society accounts", participation -> "Involvement" |
| `streams_supported` | all six |
| `request_categories` | `water_supply`, `sewage_stp`, `electrical`, `lift`, `security`, `housekeeping`, `parking`, `common_area`, `pest_control`, `noise_nuisance`, `builder_defect`, `other` |
| `request_priorities` | `routine`, `urgent`, `safety` |
| `ledger_categories` | `maintenance_dues`, `corpus_fund`, `sinking_fund`, `stp_maintenance`, `lift_amc`, `security_wages`, `housekeeping_wages`, `electricity_common`, `water_tanker`, `festival_fund`, `repairs_capex`, `penalty_late_fee`, `misc` |
| `participation_kinds` | `attend` (general body meeting), `rsvp`, `volunteer_hours`, `post`, `comment`, `upvote`, `nudge_*` |
| `exit_reasons` | `sold_unit`, `tenancy_ended`, `deceased`, `removed`, `unknown` |
| `strata_schema` | `block`: A-H · `floor_band`: `ground`, `1-3`, `4-7`, `8+` · `unit_type`: `1BHK`, `2BHK`, `3BHK`, `4BHK+` · `ownership`: `owner`, `tenant` · `tenure_band`: `<1y`, `1-3y`, `3-7y`, `7y+` |
| `default_packs` | `reliability_ops`, `forecast_risk` |
| `optional_packs` | `governance_insight`, `bayes_ranking` |
| `disabled_services` | `audit.benford_digits` (dues are a fixed repeated amount, so the magnitude-span check would block it anyway and offering it invites misuse), `network.betweenness_centrality` (naming informal power brokers in a society with active political friction is a harm the interview evidence specifically warns about; `network.isolation_report` stays, since it is aggregate only) |
| `service_overrides` | `survival.*`: `clock="wall"` · `forecast.*`: `season_length=12` monthly · `queueing.erlang_c_staffing`: `target_within_days=5`, `target_fraction=0.9`, availability convention "a committee member is an 0.2 FTE server" · `conformal.mondrian_eta`: taxonomy is `category` · `bayes.*`: pool vendors within trade, never across |
| `roles` | `president` (super admin, escalation, sees individual risk scores), `secretary` (records, announcements, decisions), `treasurer` (ledger, receipts, sees individual risk scores), `committee_member` (assigned categories only), `resident`, `auditor` (read-only ledger, no individual risk scores), `guest` (public announcements) |
| `auth_modes` | `phone_otp` (default), `email_password`, `google` |
| `membership_rule` | `admin_approval`, keyed on unit number |
| `k_anonymity_threshold` | **5** |
| `dp_required_for` | `survival.logrank_compare` by `location_ref`, `fairness.workload_gini` per-person rows, `survey.likert_distribution` by block, `voting.turnout_representativeness` by block, `budgeting.fairness_report` |
| `reopen_policy` | `new_spell` (a recurring water complaint is a new event, not a longer one) |
| `sla_clock` | `wall` (a resident waiting for water does not care that the vendor was on hold) |
| `default_season_length` | 12 (monthly), with a festival `CalendarMark` set for Ganesh Utsav, Durga Puja, Diwali and the monsoon window |
| `currency` / `timezone` | `INR` / `Asia/Kolkata` |
| `modules` | documents on, knowledge_base on (the STP repository idea came from the interview), certificates **off**, events on, whatsapp_bridge on |

**Headline statistics for the tenant home**, in order, chosen from the findings above:

1. `survival.naive_vs_km_gap` on complaint resolution. The demonstration figure.
2. `survival.median_resolution_days` by category, with `n_censored` prominent.
3. `conformal.mondrian_eta` on every open complaint's detail page.
4. `survival.median_resolution_days` over `DueSpell` verification lag: payment made to treasurer
   confirmed.
5. Receipt-collection gap: the share of issued receipts never collected, with a Wilson interval.
6. `queueing.erlang_c_staffing`: "to close 90% of complaints within 5 days you need 4 active
   committee members; you have 2."
7. `montecarlo.runway_shortfall` on the sinking fund.
8. `bayes.rank_by_posterior_lower_bound` on vendors, within trade.

**Demo seed requirements**: 340 residents across 8 blocks, 26 months of history, about 1,400
complaints of which 130 open at the window end and 40 escalated (so competing risks is material and
visible), 26 monthly billing cycles with a realistic late-payment tail and 18% of receipts never
collected, one festival contribution drive per year, two general body meeting polls of which one
contains a deliberate Condorcet cycle, one participatory budget allocation over 6 options and
12 lakh, and one deliberate step change in complaint volume at month 19 for the changepoint service
to find.

---

## 2. `campus_club` (complete, demo-seedable)

> A student club, society or chapter inside a college. Closest to the Campus Connect source, so the
> port lands here with the least adaptation.

| Field | Value |
|---|---|
| `labels` | request -> "Issue", member -> "Member", group -> "Club", decision -> "Vote", ledger -> "Club funds", participation -> "Activity" |
| `streams_supported` | all six |
| `request_categories` | `venue_booking`, `equipment`, `funding_request`, `permissions`, `event_logistics`, `membership_query`, `grievance`, `other` |
| `request_priorities` | `low`, `normal`, `deadline_bound` |
| `ledger_categories` | `membership_fee`, `college_grant`, `sponsorship`, `ticket_sales`, `event_expense`, `equipment_purchase`, `printing`, `refreshments`, `travel`, `misc` |
| `participation_kinds` | `rsvp`, `attend`, `no_show`, `volunteer_hours`, `post`, `comment`, `upvote`, `training_complete`, `nudge_*` |
| `exit_reasons` | `graduated`, `left_college`, `inactive`, `resigned`, `removed` |
| `strata_schema` | `year`: `1`, `2`, `3`, `4`, `pg` · `department`: a manifest-declared list · `role_track`: `core`, `active`, `general` · `join_cohort`: academic year |
| `default_packs` | `reliability_ops`, `governance_insight` |
| `optional_packs` | `forecast_risk`, `bayes_ranking` |
| `disabled_services` | `audit.benford_digits` (too few entries), `montecarlo.runway_shortfall` (a club's budget horizon is one semester and the correlation estimate needs 12 periods, so it would return `insufficient_data` permanently and is better absent than perpetually greyed) |
| `service_overrides` | `forecast.*`: `season_length=2` per academic year, with `CalendarMark` for term start, exams and breaks, which dominate every series in this vertical · `survival.churn_curve`: graduation is a **competing risk**, not churn, so `causes=("graduated","inactive","resigned")` and the churn figure means inactivity only · `spc.*`: weekly periods, and the exam-break marks are excluded from the baseline |
| `roles` | `faculty_advisor`, `president`, `core_team` (sees individual risk scores), `member`, `alumnus` (read-only), `guest` |
| `auth_modes` | `email_password` (default), `google` |
| `membership_rule` | `email_suffix`, the one thing carried over from Campus Connect's `College.email_suffix` |
| `k_anonymity_threshold` | **5** |
| `dp_required_for` | `survey.likert_distribution` by department, `voting.turnout_representativeness` by year |
| `reopen_policy` | `extend` (an unresolved venue booking is one ongoing problem) |
| `sla_clock` | `active` (a request blocked on the college administration is genuinely paused, and the club is judged on its own responsiveness) |
| `default_season_length` | 2 (semesters), or 12 if the tenant chooses monthly |
| `currency` / `timezone` | `INR` / `Asia/Kolkata` |
| `modules` | certificates **on** (the ported subsystem earns its keep here), events on, documents on, knowledge_base off, whatsapp_bridge optional |

**Headline statistics**: `survival.median_resolution_days` on issues; `segmentation.gmm_select_k`
on member engagement to find the drifting-away cohort; `network.isolation_report` by year, which
answers the real question a club president has, namely whether first-years are integrating;
`voting.schulze` with cycle disclosure for committee elections; `forecast.attendance` with the
`bounded-by-roster` check, since clubs consistently over-forecast turnout.

**Demo seed requirements**: 180 members across 4 years and 6 departments, 3 academic years of
history, 260 issues with 30 open, 24 events with RSVP and attendance so the no-show rate is
estimable, one multi-seat committee election with 5 seats and 11 candidates for STV, one satisfaction
survey with a 1 to 5 Likert battery and a proportional-odds violation planted in one item, and a
term-break gap in the series so the SPC baseline check has something to catch.

---

## 3. `ngo_volunteer`

> Volunteer-run NGO or field programme. `request_flow` carries **cases**, not complaints, and the
> stakes are higher.

| Field | Value |
|---|---|
| `labels` | request -> "Case", member -> "Volunteer", group -> "Programme", decision -> "Board decision", participation -> "Service" |
| `request_categories` | `intake`, `assessment`, `referral`, `follow_up`, `escalation`, `closure_review`, `other` |
| `request_priorities` | `standard`, `priority`, `safeguarding` |
| `ledger_categories` | `grant`, `individual_donation`, `csr`, `programme_expense`, `stipend`, `travel`, `admin_overhead`, `restricted_fund` |
| `strata_schema` | `programme`, `region`, `volunteer_tier`: `occasional`, `regular`, `core` · `training_level` |
| `default_packs` | `reliability_ops`, `forecast_risk`, `governance_insight` |
| `optional_packs` | `bayes_ranking` |
| `disabled_services` | `text.near_duplicate_candidates` on case text **by default** (case narratives are sensitive and similarity search across them is a re-identification vector; a tenant may enable it explicitly), `network.betweenness_centrality` |
| `service_overrides` | `survival.*`: `clock="active"`, and `competing_risks_cif` is **on by default** because case closure, referral out and client disengagement are three genuinely different exits and treating the last two as censoring would materially overstate closure · `risk.*`: individual risk scores are restricted to `programme_lead` and are never exported |
| `roles` | `board_member`, `programme_lead` (individual risk scores), `coordinator`, `volunteer`, `funder` (aggregate only, no per-stratum breakdowns), `guest` |
| `auth_modes` | `email_password`, `phone_otp` |
| `k_anonymity_threshold` | **10**, raised above the floor. Case-level strata are small and the subject population is vulnerable. |
| `dp_required_for` | every per-stratum figure over `request_flow` and `signal` |
| `reopen_policy` | `extend` |
| `sla_clock` | `active` |
| `default_season_length` | 12 |
| `modules` | certificates on (volunteer hour certificates are a real retention lever), documents on, knowledge_base on |

---

## 4. `alumni_chapter`

> A geographic or institutional alumni chapter. Sparse, bursty engagement; the interesting question
> is always re-engagement, and the interesting stream is `participation`, not `request_flow`.

| Field | Value |
|---|---|
| `labels` | request -> "Request", member -> "Alumnus", group -> "Chapter", ledger -> "Chapter fund", participation -> "Engagement" |
| `request_categories` | `directory_update`, `event_proposal`, `mentorship_match`, `donation_query`, `verification`, `other` |
| `ledger_categories` | `annual_dues`, `donation`, `endowment_pledge`, `event_expense`, `scholarship_disbursement`, `admin` |
| `strata_schema` | `grad_decade`, `region`, `industry`, `giving_tier`: `none`, `occasional`, `sustaining` |
| `default_packs` | `forecast_risk`, `bayes_ranking` |
| `optional_packs` | `reliability_ops`, `governance_insight` |
| `disabled_services` | `queueing.*` (there is no queue; request volume is a trickle and Erlang-C on 4 requests a month is nonsense), `spc.*` on request volume for the same reason |
| `service_overrides` | `segmentation.rfm_features`: `contribution_minor` is the dominant feature and the manifest says so · `risk.member_disengagement_risk`: horizon is 365 days, not 30, because the natural engagement cycle is annual · `forecast.*`: `season_length=12` with a reunion `CalendarMark` |
| `roles` | `chapter_president`, `treasurer`, `committee`, `alumnus`, `institution_liaison`, `guest` |
| `auth_modes` | `email_password`, `google` |
| `k_anonymity_threshold` | **10**. Giving tier crossed with graduation decade identifies people quickly. |
| `dp_required_for` | every figure crossing `giving_tier` with any other stratum |
| `default_season_length` | 12 |
| `modules` | events on, documents on, certificates off, knowledge_base off |

---

## 5. `housing_coop`

> A cooperative housing society with formal share ownership and statutory governance. Structurally
> close to `rwa_society` and deliberately shares most of its configuration, but the governance
> obligations are stronger and the privacy exposure is the highest in the set.

Inherits `rwa_society` and overrides:

| Field | Value |
|---|---|
| `labels` | member -> "Shareholder", decision -> "Resolution", group -> "Managing committee" |
| `request_categories` | `rwa_society`'s list plus `share_transfer`, `nomination`, `noc_request`, `bye_law_query` |
| `ledger_categories` | plus `share_capital`, `transfer_premium`, `statutory_audit_fee`, `property_tax` |
| `default_packs` | `reliability_ops`, `forecast_risk`, **`governance_insight`** (statutory voting makes this mandatory rather than optional) |
| `service_overrides` | `voting.*`: `declared_rule` is enforced strictly and the rule-sensitivity display is **on by default**, since a cooperative resolution can be legally challenged and the record must show what was declared and when · `voting.turnout_representativeness`: quorum is statutory, so `quorum-met` is blocking on any claim that a resolution passed · `sortition.*` available for sub-committee formation |
| `k_anonymity_threshold` | **10**, raised. A cooperative publishes more per-unit detail by statute, and the aggregate layer must compensate. |
| `dp_required_for` | all per-block, per-floor and per-unit-type aggregates without exception |
| `modules` | documents on with statutory retention, knowledge_base on, certificates off |

---

## 6. `sports_club`

> A sports or recreation club. The one vertical where **pairwise comparison is the point** rather
> than a corner of Pack 2.

| Field | Value |
|---|---|
| `labels` | request -> "Request", member -> "Member", group -> "Team", decision -> "Club vote", participation -> "Participation" |
| `request_categories` | `court_booking`, `equipment`, `coaching`, `membership`, `facility_maintenance`, `tournament_entry`, `grievance`, `other` |
| `ledger_categories` | `membership_fee`, `court_fee`, `coaching_fee`, `tournament_entry`, `equipment`, `ground_maintenance`, `coach_payment`, `misc` |
| `strata_schema` | `sport`, `age_group`, `skill_band`, `membership_tier` |
| `default_packs` | `reliability_ops`, `bayes_ranking` |
| `optional_packs` | `forecast_risk`, `governance_insight` |
| `disabled_services` | none by default |
| `service_overrides` | `pairwise.bradley_terry` and `pairwise.elo_update` are **primary services here**, over match results rather than vendor comparisons, with `connectivity` blocking enforced hard because ladder play produces disconnected comparison graphs constantly · `bayes.beta_binomial_shrink` over win rates, which is the same 3-of-3 pathology in its most familiar form · `forecast.attendance`: weekly `season_length=52` with a weather-season `CalendarMark` |
| `roles` | `club_secretary`, `treasurer`, `captain`, `coach`, `member`, `guest` |
| `auth_modes` | `phone_otp`, `email_password` |
| `k_anonymity_threshold` | **5** |
| `dp_required_for` | `survey.likert_distribution` by skill band |
| `default_season_length` | 52 |
| `modules` | events on, certificates on, documents on |

---

## 7. `professional_guild`

> A professional body, trade association or practitioner network. Membership is a paid annual
> lifecycle, and the two questions that matter are renewal and whether the CPD offering is working.

| Field | Value |
|---|---|
| `labels` | request -> "Ticket", member -> "Member", group -> "Chapter", decision -> "Council vote", participation -> "CPD activity" |
| `request_categories` | `membership_application`, `renewal_query`, `accreditation`, `cpd_credit`, `ethics_complaint`, `directory_update`, `event_query`, `other` |
| `ledger_categories` | `annual_subscription`, `accreditation_fee`, `event_income`, `sponsorship`, `secretariat_cost`, `event_expense`, `publication`, `misc` |
| `strata_schema` | `member_grade`: `student`, `associate`, `full`, `fellow` · `region` · `sector` · `years_in_practice_band` |
| `default_packs` | `reliability_ops`, `forecast_risk`, `governance_insight` |
| `optional_packs` | `bayes_ranking` |
| `disabled_services` | `network.*` by default (a professional network graph is commercially sensitive and members did not consent to being mapped) |
| `service_overrides` | `survival.churn_curve` is the **headline** service, over renewal spells, with `member_grade` as the stratifying covariate and `survival.cox_hazard_ratios` on grade, region and CPD engagement · `survey.ordinal_logistic` is primary for the annual member survey, with the Brant test blocking as specified · `risk.late_payment_risk` becomes renewal-lapse risk on a 365-day horizon |
| `roles` | `council_member`, `registrar` (individual risk scores), `secretariat`, `chapter_lead`, `member`, `guest` |
| `auth_modes` | `email_password`, `google` |
| `membership_rule` | `admin_approval` with grade assignment |
| `k_anonymity_threshold` | **10**. Grade crossed with region crossed with sector is a small cell almost everywhere. |
| `dp_required_for` | every figure crossing two or more strata |
| `default_season_length` | 12 |
| `modules` | certificates on (accreditation), documents on, knowledge_base on, events on |

---

## 8. Cross-vertical rules

1. **A pack is only offered when its required streams are supported.** The onboarding screen shows
   `governance_insight` greyed with "needs the decision stream" rather than hiding it, because a
   tenant should be able to see what they would gain by switching a domain on.
2. **A service is never silently omitted.** If a manifest disables it, the Method Card page still
   lists it with the reason. Vertical-specific disabling is a statement about that community, and
   `rwa_society` disabling betweenness centrality because of documented committee friction is
   exactly the kind of statement that should be readable.
3. **Vertical defaults never lower a statistical floor.** `min_n`, the k-anonymity floor and the
   MASE and calibration gates are properties of the mathematics, not of the community, and a
   manifest cannot touch them. It may only raise them, as `ngo_volunteer`, `alumni_chapter`,
   `housing_coop` and `professional_guild` each raise `k`.
4. **Adapters pass the shared conformance suite** in `docs/DATA_SPINE.md` §9 before the vertical is
   selectable. The critical case is the open-request fixture: an adapter that filters to closed
   requests fails, whatever else it does.
