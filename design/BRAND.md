# Quorum: brand strategy and identity architecture

*Cards B.2 / B.2a. Status: draft 1. Runs VibeCurb `brandkit-gen` Phase 1 (Brand Strategy) and
Phase 2 (Identity Architecture) under the hand-authored-SVG constraint, no image generation
available, so the identity ships as geometry and tokens, not as generated brand boards.*

---

## 0. The name

**Quorum.** Two readings, and the product is the second one wearing the first one's clothes:

- *the civic reading*: **enough people to decide**. A meeting without quorum cannot resolve.
- *the statistical reading*: **enough data to conclude**. An estimate without `n` cannot resolve
  either.

The name is not decoration on the strategy. It **is** the strategy. Every screen in this product is
answering "do we have quorum yet?" about attendance, about evidence, about both. The brand's job
is to make "not yet" look like an honest answer rather than a broken screen.

---

## 1. Brand Strategy Brief (Phase 1)

> **Strategy Brief.** A statistical instrument for ordinary communities. Category: community
> operations, positioned against both CRUD society apps and LLM-wrapper "AI assistants". Audience is
> split and must both be served on one surface: the **resident**, who wants the leaking tap fixed
> and wants to know *when*; and the **secretary**, who has to decide whether the new plumber is
> actually better or whether last month just felt better. Core metaphor: **the threshold**: the
> line a count crosses when it becomes enough to act on. Emotional promise: *you can defend this
> number in front of the committee.* Trust level: high, and earned by visible restraint rather than
> claimed by badge. Visual world: warm ink on paper, printed record-keeping, a measured instrument
> face, the register book and the calibrated dial, not the SaaS gradient. The brand should feel
> like it was designed by someone who has actually sat through an AGM.

### The ten signals

| Signal | Reading |
|---|---|
| **Category** | Community operations platform with an inferential engine. Not analytics-for-enterprise. |
| **Audience** | Two, on one surface. Resident: low-frequency, low-patience, wants an ETA. Secretary/coordinator: recurring, accountable to a committee, needs to justify decisions to peers who did not read the data. |
| **Product function** | Observe a community as processes, then **decide** with intervals, not vibes. |
| **Emotional promise** | Defensibility. The calm of a number you can be questioned about. |
| **Cultural position** | Warm-human and technical-expert simultaneously. Explicitly *not* corporate-SaaS, *not* playful-consumer, *not* "AI-powered". |
| **Trust level** | High. Communities handle other people's money and other people's complaints. |
| **Visual world** | Warm paper and printed rules; instrument faces, graticules, tick marks; the register book. |
| **Core metaphor** | **The threshold.** Enough people. Enough data. The line you cross. |
| **What to avoid** | AI-purple gradients, sparkle glyphs, node-graph "connectivity" clichés, globes, stock-photo smiling committees, dashboards that show a bare number in 48px. |
| **Reference quality** | Campus Connect's warm paper canvas (`#FCFBFA`, terracotta `#EF7B45`, ink `#3A2A24`) is the inherited floor: personal rather than corporate. It lacks dark mode, a dataviz system, and editorial type contrast. Evolve, do not discard. |

### Brand-to-symbol mapping

From the `brandkit-gen` verb table, Quorum's verbs are **organize/manage/control** (symbol pool:
grid, register, index, **calibration**, dial) and **analyze/discover** (lens, **trace**, signal).
Narrowed to three candidates:

1. **The filled threshold**: a level rising to meet a rule. Quorum, literally.
2. **The interval**: a span with two caps and a point inside it. Honest measurement, literally.
3. **The register rule**: a ruled line across a page, the unit of a ledger.

Candidate 1 wins: it carries *both* readings of the name in one form, and it survives 16px.

### Tagline

Energy: **declarative**. Locked line: **"Enough to decide."**

Working alternates, for voice range rather than replacement:
*"The number, and how sure it is."* · *"Statistics decide. The assistant just explains."*

Banned from all copy: *elevate, seamless, unleash, empower, revolutionise, AI-powered, next-gen.*

---

## 2. Identity Architecture (Phase 2)

### Visual mode

**Custom mode, declared: "Warm Instrument."** Constructed per the skill's custom-mode procedure, start from **Mode 11 (Warm Editorial / Humanist)** for canvas and temperature, swap the
art-historical image-world for a **measurement image-world** (graticules, control limits, ruled
bands, tick scales) drawn from **Mode 5 (Light Editorial / Compliance)**, and keep Mode 11's rule
that the logo must be so simple it disappears next to the data.

- **Canvas:** warm limestone `#FAF7F2` light / warm near-black `#12100E` dark. Limestone, not
  cream and not grey: cream reads dated, grey reads corporate.
- **Canvas treatment:** *textured paper* (light) shifting to *technical grid* wherever data is
  plotted. The chart is the only place the grid appears; it is a signal that you are now looking at
  measurement rather than at copy.
- **Accents:** **spruce `#13594A`** as the primary, **apricot `#E07A3F`** as the interaction accent.
  Two accents maximum, per the skill's rule.
- **Mood:** considered, warm, accountable. A well-kept register book with an instrument on the desk
  beside it.

Why this over the obvious picks: Mode 9 (Enterprise SaaS) would put us in the indigo-on-cool-grey
sea that every society app already swims in, and it reads as *corporate*, which is the one thing
this audience distrusts. Mode 1/2 (dark developer/operator) is honest about the statistics but
alienates the resident, who is half the audience. An earlier draft of this brief proposed
terracotta-on-ivory; it was cut at review for reading as the expected warm-startup palette rather
than as a current one.

### Colour discipline

**Structure: split-warm anchor.** Spruce carries brand weight and calm; apricot carries interaction
and nothing else. Everything else is the limestone/ink pair.

Three rules, in priority order:

1. **Apricot is never a status colour.** It means "you can act on this": hovers, focus rings, the
   median crosshair, a signalled control point. Warning and stop have their own ramps (`--warn`,
   `--stop`) so an alert never competes with a button.
2. **Spruce is never a series colour**, and neither is apricot.
3. **Brand colour and chart colour are two separate systems.** A reader must never have to ask
   whether the orange line means "the brand" or "vendor 2".

> Specified fully in `design/DATAVIZ.md` (card B.5). The sample pages already obey it, and their
> categorical palettes were run through the six-check validator in both modes.

### Typography character

**Characterful grotesque + neutral text sans**, with a **monospace figure face** as a third,
non-optional role.

| Role | Face | Why |
|---|---|---|
| Display / headings | **Bricolage Grotesque** | Tight, slightly irregular, genuinely current. Carries personality without novelty, and holds up at 6rem where a neutral grotesque goes generic. |
| Body / UI | **Inter Tight** | Neutral by design so the display face does the talking. Legible for the resident at 16px on a phone at night. |
| **Figures, `n`, intervals, method ids** | **JetBrains Mono**, tabular figures | **A statistic wears a different face from prose.** This is the typographic form of the no-bare-numbers rule: if it is set in the mono face, it came out of an `Evidence` envelope. Nothing else may borrow that face. |

An earlier draft proposed an editorial serif for display. It was cut with the terracotta palette:
together they read as a familiar warm-editorial template rather than as this product. The
*three-role structure* is what is brand-level and does not vary; the faces filling those roles are
the ones above.

### Logo concept

**Method: Product Action + Metaphor Fusion** (two, the maximum allowed).

> **Geometry, one sentence:** *It is a circle with a horizontal chord that overshoots both edges, the
> area below the chord filled.*

Primitives: **2** (one circle, one rectangle), under the 3-primitive cap.

What it says: a level risen to meet a rule. Quorum reached. It reads simultaneously as a filled
proportion, an instrument face with its threshold marked, and a token counted into a box. The
overshoot is load-bearing: without it the mark is a moon phase; with it, the chord is unmistakably a
*threshold laid across* the circle rather than a boundary of it.

**Gate check:**

| Gate | Result |
|---|---|
| 3-primitive cap | 2 primitives. Pass. |
| 16px favicon | A filled lower segment plus one full-width rule. Both survive; verified in the sample pages' inline favicon. |
| One-sentence geometry | Stated above, no comma splice. Pass. |
| Inversion (black-on-white / white-on-black) | No colour-dependent form. Pass. |
| Wordmark pairing | Circular mark against the serif "Quorum"; the chord aligns to the wordmark's x-height. Pass. |
| Pattern tile | Tiles as a dot-and-rule field; reads as ruled paper. Pass. |
| Anti-patterns | No gradient, no chrome, no brain/neuron, no globe, no swoosh, no shield-with-wings, no letter-in-a-circle (there is no letter). Pass. |

**Fill-state variant, and why it is not a gimmick:** the mark's fill level is a legitimate state.
At quorum the segment is filled to the chord; below quorum it is filled short of it, with the chord
still drawn. The product's most common empty state therefore has a *brand-native* form, the logo
itself is the "not enough data yet" illustration. This is the single best thing about the mark and
it is why it beat the interval-with-caps candidate.

*(Card B.3 ships this as `design/brand/logo/{primary,stacked,mark,favicon}.svg`. The sample pages
carry an inline copy of the mark; that inline copy is the reference geometry.)*

---

## 3. The design problem this brand exists to solve

Most of this product's pixels are **uncertainty**, not values:

- a survival curve is mostly its band,
- a control chart is mostly its limits,
- a conformal ETA *is* an interval, there is no point estimate at all,
- and for any tenant in its first months, the most frequent tile on the screen says
  **not enough data yet.**

So the states get designed first, and the hero second. Four states, from
`docs/EVIDENCE_CONTRACT.md` §3, and their fixed visual contract:

| State | Visual contract | Never |
|---|---|---|
| **Estimate** | Value in the mono face, unit, interval, `n`, and `n_censored` when non-zero. Method id links to its card. | A bare number. Ever. |
| **Qualified** | Value shown at full weight, with the failing check's label and detail inline beneath it, in the warning role. Not dimmed, not hidden, a qualified number is still a number. | Styling it as broken. |
| **Not interpretable** | Value **suppressed** and replaced by the blocking check's `detail`. The tile keeps its full size and its frame, the space is held, not collapsed. | Collapsing the tile, which hides that the question was asked. |
| **Not enough data** | Calm. Ink-muted, never a status colour, never an exclamation mark. States the target and the actual: *"needs 30 closed requests, has 11."* Carries a progress form (the logo's own fill state) so the reader sees it is *accruing*, not *failing*. | Red. Warning triangles. The word "error". Empty-state illustrations of confused people. |

**The rule behind all four:** *if honest reporting looks broken, people learn to prefer tools that
lie.* An empty state that reads as a defect is a product failure, not a visual one.

Two more contracts that apply to every figure everywhere:

1. **Every figure shows its `n` and its interval.** Where a quantity is exact (a count, a rank), it
   says so explicitly, `interval_kind: "none"` renders as *"exact count"*, not as blank space.
2. **The interval kind is named.** A 95% confidence interval, a 95% credible interval, a 90%
   conformal interval and a set of control limits are four different objects and the UI says which
   one it is showing. Control limits in particular are a **decision boundary, not an estimate**, and
   are drawn in a different visual language from every band on the page.

---

## 4. The three style directions

All three sit inside the strategy above and share the identity architecture, the same logo
geometry, the same three-role type structure, the same four render states, the same brand/chart
colour separation. They differ in **temperature, type voice, motion personality, and, the real
axis, what uncertainty is made of.**

The categorical chart hues do **not** vary by direction. Hue anchors are a CVD-safety mechanism, not
a mood lever; each direction re-steps the same four hue families against its own surface and both
step sets were validated (lightness band, chroma floor, CVD ΔE, normal-vision floor, contrast) in
light and dark. What varies is the *form* uncertainty takes, which is the honest place for a style
direction to express itself.

### A. **Almanac**: warm editorial

`design/samples/almanac/`

The printed community record. Warm ivory paper, a serif that has read a book, generous measure,
rules and marginalia. It looks like a well-kept society register that happens to contain a
statistics department. This is the direction that most obviously belongs to a housing society AGM
and the one that most reassures a non-technical resident.

- **Palette:** ivory `#FBF7F0` / ink `#2A211C` / terracotta `#B54A22` / indigo `#1F3A5F`.
- **Type:** *Fraunces* (editorial serif, optical display axis) + *Plus Jakarta Sans* (body) +
  *JetBrains Mono* (figures).
- **Motion personality:** **Cinematic**: slow editorial reveals, 500–800ms, `--ease-dramatic`.
- **Uncertainty is: hatching.** Confidence bands are drawn as diagonal hand-hatched fills, the way a
  printed almanac or a census report shades an uncertain region. Hatching reads as *"drawn by
  someone who knew this was approximate"* rather than as a coloured block that might be mistaken
  for data. Not-enough-data is a ruled but unfilled ledger line with the tally written in the margin.

### B. **Graticule**: precise instrument

`design/samples/graticule/`

The measuring device. Cool near-white, a grotesk with no opinions, monospace everywhere a number
appears, and a fine graticule under every plot. Chrome is hairlines and tick marks. It looks like
the face of an instrument that was calibrated by someone and signed off. This is the direction that
most respects the secretary who has to defend a decision.

- **Palette:** paper `#F7F8F7` / ink `#111417` / signal teal `#0E6A62` / indigo `#243B55`.
- **Type:** *Archivo* (neo-grotesk, tight display) + *Archivo* body + *IBM Plex Mono* (figures,
  axes, every label).
- **Motion personality:** **Surgical**: 120–240ms, `--ease-snap`, zero overshoot. Nothing on this
  page bounces; instruments do not bounce.
- **Uncertainty is: the graticule.** Bands are bounded by hairlines and filled with a fine ruled
  tint; every interval terminates in real tick caps against a real scale. The uncertainty is
  *measured*, with its edges legible, rather than atmospheric. Not-enough-data draws the complete
  scale with no reading on it, the instrument exists, it simply has not been given enough to say.

### C. **Signal**: high-contrast poster

`design/samples/signal/`

Attitude. Dark-first, near-black warm charcoal, oversized condensed display type set as a poster,
one acid accent, hard edges and no soft shadows. Built for the tenant who wants their community's
data to look like it matters, and for the screen behind the podium at a general body meeting. Its
light mode is bone paper with black ink, a printed poster, not a washed-out dark mode.

- **Palette:** charcoal `#131210` / bone `#F2F0E9` / acid `#C8F031` / ember `#F2823F`.
- **Type:** *Bricolage Grotesque* (variable display, condensed at scale) + *Space Grotesk* (body) +
  *Space Mono* (figures).
- **Motion personality:** **Physical**: spring-shaped entries and press compression, 300–520ms.
- **Uncertainty is: the shadow.** An interval is a solid offset block sitting behind its point
  estimate: the number literally casts the width of its own doubt, and a wide interval is visibly a
  bigger, heavier shape than a narrow one. Control-chart signals are treated as poster events, not
  as small red dots. Not-enough-data is a large, quiet typographic statement with a tally, the
  loudest direction saying the quietest thing, which is exactly where it earns trust.

---

## 5. Motion (brand-level, ahead of card B.6)

Three constraints are already locked and do not vary by direction:

1. **Easings are cubic-Bézier tokens.** No CSS keyword easings anywhere, not `ease`, not
   `ease-in-out`, not `linear` as an animation curve. Spring-shaped `linear()` curves are
   deliberately deferred to `design/MOTION.md` so that the token contract stays one type.
2. **`prefers-reduced-motion: reduce` is honoured on every page.** Reduced motion means no
   translation, no scale, no parallax, opacity at reduced duration is permitted, and all reveal
   states must resolve to visible regardless of whether their trigger ever fires.
3. **The motion budget follows frequency.** Marketing surfaces get full coverage. Product surfaces
   get almost none: a dashboard a secretary opens forty times a week must not animate its tiles
   forty times a week. Empty states and first-run are the one place the product spends delight.

Banned: scroll-jacking, hover disco, text disassembly, layout-property animation, infinite
preloaders, and any motion applied to a number that is still settling, **a figure never counts up.**
Counting animation implies the value is arriving; in this product the value arrived with an interval
attached and animating it is a small lie.

---

## 6. What this brief hands to the next cards

- **B.3**: logo SVGs from §2's geometry, including the fill-state variant.
- **B.4**: `tokens.css` / `tokens.json`. Every colour on bare `:root` for light and redefined under
  both `@media (prefers-color-scheme: dark)` and `[data-theme="dark"]`; no colour whose only
  definition lives in a media query. The sample pages already follow this rule and are the source
  for the token names.
- **B.5**: `DATAVIZ.md`. The categorical steps validated here, the sequential ramp, the diverging
  pair, the fixed status scale, and the two specs that matter most: the **survival curve with band**
  and the **control chart with limits**, including the rule that control limits never share a visual
  language with a confidence band.
- **B.6**: `MOTION.md`. The three personalities above, one selected once a direction is picked.
- **B.7**: the design canvas, built in the chosen direction.

**Open, for the user's pick:** which direction. The recommendation is recorded in `CONTEXT.md`.
