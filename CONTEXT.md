# Living context

**Update this before you stop. An agent that stops without updating this file has not finished.**

---

## Where we are

**Phase 0 — Governance.** Nearly complete. Next card is **0.4** (`git init` + first commit), then
Phase A opens with **A.1** (the Evidence contract).

Working name: **Quorum** — provisional, locked in card B.1.

## Done

| When | What |
|---|---|
| 2026-08-29 | Read both legacy RWA planning docs; classified them as historical research, not requirements |
| 2026-08-29 | Studied `MAY2026-Team-003` (Campus Connect); confirmed it as the port source |
| 2026-08-29 | Extracted `design-sources.zip` → VibeCurb skill pack; reviewed all seven protocols |
| 2026-08-29 | Reviewed sangam-club.com as an adjacent reference |
| 2026-08-29 | `PLAN.md`, `CLAUDE.md`, `docs/RULES.md`, `docs/WORKPLAN.md`, `docs/GLOSSARY.md`, `CONTEXT.md`, `.claude/agents/*` (cards 0.1–0.3) |
| 2026-08-29 | Vendored `reference/campus-connect/` and `reference/vibecurb/` into the repo |

## In flight

Nothing. The board is clean — pick up card 0.4.

## Blocked

Nothing.

---

## Decision log

Newest first. Append, never rewrite. Record *why*, not just *what*.

| Date | Decision | Why |
|---|---|---|
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
