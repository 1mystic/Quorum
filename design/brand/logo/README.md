# Quorum logo system

**Geometry, one sentence:** a circle with a horizontal chord that overshoots both edges, the area
below the chord filled.

Primitives: **2** (one circle, one rectangle), under the VibeCurb 3-primitive cap. The SVGs carry a
third element, the filled `<path>`, but it is the *intersection* of those two shapes rather than an
added form, precomputed because SVG has no boolean operators.

What it says: a level risen to meet a rule. Quorum reached. It reads at once as a filled proportion,
an instrument face with its threshold marked, and a token counted into a box. The overshoot is
load-bearing: without it the mark is a moon phase; with it, the chord is unmistakably a *threshold
laid across* the circle rather than a boundary of it.

| File | Use |
|---|---|
| `mark.svg` | The mark alone, full colour. Product chrome, app icon, avatars. |
| `mark-mono.svg` | Single-colour via `currentColor`. Inherits ink; use on photography, in dense UI, in print. |
| `favicon.svg` | 32px cut. Heavier stroke and a wider threshold so it holds at 16px. **Not a scaled-down `mark.svg`.** |
| `lockup-horizontal.svg` | Default lockup. Nav bars, letterheads, anywhere with horizontal room. |
| `lockup-stacked.svg` | Centred lockup. Splash, square placements, merchandise. |

## Rules

- **Clear space** on all sides equals the mark's stroke weight times four (`4.6 x 4 = 18.4` at the
  64px cut). Nothing enters it.
- **Minimum sizes:** mark 20px, horizontal lockup 120px wide, favicon cut below 24px.
- The threshold bar is **apricot `#E07A3F`** and the fill is **spruce `#13594A`**. Do not recolour
  them independently; use `mark-mono.svg` when a single colour is required.
- Never rotate the chord. It is a level, and a tilted level is a different claim.
- Never add a gradient, a shadow, or an outer container shape.
- The wordmark is **Bricolage Grotesque 700** at `-1.1` tracking. The lockup SVGs reference the
  family by name and fall back to Inter Tight; convert to outlines before sending anywhere the font
  will not be available.
