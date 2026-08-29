# Engineering rules

The short version is in `CLAUDE.md`. This is the full policy plus the gates a card must pass
before it can be ticked in `docs/WORKPLAN.md`.

---

## 1. Git

We do **not** use the Campus Connect `RULES.md` playbook (`feature/*` → `dev` → `main`, mandatory
PRs, daily sync). That was a five-person course team's process and it does not apply here.

| Rule | Detail |
|---|---|
| **Branch** | Commit directly to `main`. Branch only for a genuine throwaway experiment, and delete it after. |
| **Message length** | **1–2 lines. Never longer.** No body paragraphs, no bullet lists, no trailers. |
| **Attribution** | **Never** `Co-Authored-By`. **Never** mention Claude, Anthropic, Copilot, or any AI tool — not in commits, not in PR bodies, not in code comments, not in docs. |
| **Prefixes** | `feat:` `fix:` `refactor:` `docs:` `test:` `chore:` |
| **History** | Never force-push `main`. |
| **Secrets** | Never commit `.env`, keys, tokens, or a real database URL. `.env.example` is the contract. |

Good: `feat: erlang-c staffing recommendation for target sla`
Good: `fix: km estimator dropped open tickets instead of censoring them`
Bad: anything with a bulleted body, a trailer, or the word "Claude".

## 2. Scope of work

Everything lives under `/home/mystic1/Projects/RWA`. Never write outside it.

`reference/campus-connect/` and `reference/vibecurb/` are **read-only source material**. Copy out of
them; never edit in place. They are the record of what we ported from.

`RWA_Master_Context.md` and `RWA-Focused-Project-Plan.md` are **historical research**. The interview
findings (payment flow, STP maintenance, receipt-collection gap, ~99% WhatsApp usage) remain valid
evidence. The scope decisions, the three-role model, the milestone dates and the feature cuts are
**void** — they were shaped by a course review we are no longer subject to.

## 3. The statistics purity rule

Everything in `backend/app/stats/`:

- **No DB access. No network. No I/O.** Takes arrays and dataclasses, returns `Evidence`.
- **Deterministic.** Any randomness takes an explicit seed parameter.
- **No global mutable state.** No module-level caches.
- Services do the fetching and the caching. `stats/` does the mathematics.

This mirrors `reference/campus-connect/backend/app/agent/recommender.py`, which is pure for the same
reason. It is what allows every statistical service to be unit-tested offline against a known
answer instead of a snapshot.

If a statistical function needs data it does not have, it raises `InsufficientData` or returns an
`Evidence` with `insufficient_data=True`. It never goes and gets it.

## 4. The Evidence rule

Every statistic crossing a boundary is an `Evidence` envelope (spec: `docs/EVIDENCE_CONTRACT.md`)
carrying at minimum `value`, `interval`, `n`, `method`, `assumption_checks`, `insufficient_data`,
`as_of`, `params_hash`.

- **Backend:** no service returns a raw float for a statistic.
- **Frontend:** no component renders a statistic without its envelope. Below `min_n` the figure is
  greyed with the reason shown, not hidden and not silently rendered.
- **Agent:** tools return envelopes. The model narrates them. It must not do arithmetic on them,
  combine them, or state a figure that is not in one. Enforced by a grounding test.

Every `method` id resolves to a **Method Card**: assumptions, when it is wrong, minimum n,
references. A service without a Method Card is not done.

## 5. Multi-tenancy

- Every table carries `tenant_id`.
- All reads go through `TenantScopedRepository`, which makes an unscoped query awkward to write by
  accident.
- **Postgres RLS is enabled as defense in depth**, not as the only line.
- Routes are `/api/t/{slug}/…`. The slug in the URL must match the `tenant_id` claim in the JWT, or
  403. Never trust the URL alone.
- Cross-tenant isolation is a test suite, not a comment.

## 6. Privacy

Small communities are small. A "per-block average" over three households is a disclosure.

- Aggregates below the k-anonymity threshold are suppressed, not rendered.
- Published per-stratum statistics carry Laplace DP noise where the vertical manifest requires it.
- Free-text complaint bodies are never sent to an LLM with the author's identity attached.

## 7. Test gates

A card cannot be ticked until its gates pass. `reviewer` runs these, not the implementing agent.

**All cards**
- `uv run pytest` green; `npm run test` green if the frontend changed.
- No secret, key, or real database URL in the diff.
- No AI attribution anywhere in the diff.

**Stats cards** — each service tested against a *known* answer, never a snapshot:
- Survival: Kaplan–Meier and Cox reproduce published coefficients on the standard `rossi` dataset.
- Queueing: Erlang-C matches published staffing tables.
- Social choice: Schulze/Condorcet match textbook cases, **including a deliberate Condorcet cycle**.
- Bayes: Beta-Binomial shrinkage matches the closed-form posterior.
- Conformal: empirical coverage on held-out synthetic data within tolerance of nominal 90%.
- **Forecast gate:** must beat seasonal-naive on MASE under rolling-origin CV, or it does not ship.
- **Calibration gate:** Brier score and reliability-diagram deviation under threshold.
- **Censoring regression:** a fixture where naive mean-of-closed and KM diverge, asserting we report KM.
- Purity check: the module imports nothing from `app.repository`, `app.services`, `sqlalchemy`,
  `httpx`, or `requests`.

**Tenancy cards**
- A cross-tenant read returns 403 at the API **and** zero rows under RLS with the API bypassed.

**Agent cards**
- A prompt-injection fixture planted in a request body moves no tool call and fabricates no
  `Evidence` value.

**Frontend cards**
- No hard-coded color, font, radius, or duration outside `design/tokens.css`.
- Renders correctly in light and dark.
- `prefers-reduced-motion` respected.

## 8. Code style

Match the surrounding file. Campus Connect's conventions carry over where we port its code:
one CSS declaration per line, numbered section banners in `style.css`, docstrings at the top of a
module explaining *why* the module is shaped the way it is rather than what it does line by line.

Comment density: match what is already there. Do not annotate the obvious.
