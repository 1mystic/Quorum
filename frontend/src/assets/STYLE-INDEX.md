# style.css - section index

A map of `style.css`, in file order. Sections are numbered banners
(`/*  N. Title  */`); search by label, since line numbers shift as the file
grows. `tokens.css` is loaded before this file and owns every colour, font,
space, radius, shadow and duration; nothing below hard-codes a value.

| Section | What it covers |
| --- | --- |
| 1 | Reset and base element styles |
| 2 | Reduced motion and scroll-reveal helper (`.rv`) |
| 3 | App shell (`.app` grid, `.portal-body`, `.landing-body`) |
| 4 | Sidebar shell (`.side`) |
| 5 | Sidebar elements (brand mark, tenant switcher, nav groups) |
| 6 | Topbar (`.topbar`, `.asof`) |
| 7 | Grid helpers (`.row`, `.r-4`, `.r-32`, `.r-23`) |
| 8 | Card (`.card`, `.chead`) |
| 9 | Buttons (`.btn-primary` sweep-fill hover, `.btn-ghost`, `.tgl`) |
| 10 | Pills — the four Evidence render states (`.p-est`, `.p-qual`, `.p-hold`, `.p-wait`) |
| 11 | The Evidence value (`.big`, `.big.range`) |
| 12 | Meta strip (`.meta`) — `n`, interval, censored count |
| 13 | Progressive disclosure (`details.why`) — the long explanation, closed by default |
| 14 | Audit line (`.audit`) — method id + `params_hash` |
| 15 | Charts (`.chart`, `.legend`, `.draw`/`.fade` reveal keyframes) |
| 16 | Waiting state (`.wait-bar`, `.wait-num`) — calm, never an error colour |
| 17 | Withheld state (`.withheld`) — value suppressed by a blocking check |
| 18 | Table (`.tbl`, `.tbl-scroll` for horizontal overflow containment) |
| 19 | Shrinkage bar (`.shr`) — raw rate as a tick, posterior as a bar |
| 20 | Route loading bar and buffer spinner |
| 21 | Toast stack |
| 22 | StatTile-specific layout (`.stat-tile-empty`, `.check-detail`) |

## Quick reference by concern

| Concern | Sections |
| --- | --- |
| Evidence render states | 10, 11, 12, 13, 16, 17 |
| Dashboard shell | 3, 4, 5, 6, 7 |
| Cards and tables | 8, 18, 19 |
| Buttons and toggles | 9 |
| Charts (SurvivalCurve, ControlChart) | 15 |
| Async chrome (route bar, toasts) | 20, 21 |

## Adding to this file

New sections go at the end of `style.css` with the next integer banner, and
get a row here in the same pass. Do not renumber existing sections.
