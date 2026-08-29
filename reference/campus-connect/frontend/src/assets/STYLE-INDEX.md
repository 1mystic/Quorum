# style.css - Section Index

A map of the central stylesheet so you can jump straight to the styles you
need. The file is one large stylesheet organized top to bottom as: design
tokens first, then shared components, then page-specific styles, and finally
the motion and responsive layers.

## How to use this index

Line numbers are approximate and shift as the file grows. The reliable way to
navigate is to search for the section banner comment, for example
`/*  27. AI Club Finder  */`. Every section starts with one of these numbered
banners.

A note on numbering: the sections are not strictly sequential. Some landing
sub-passes (40c through 40g and 42) and a few later additions were appended as
the design evolved, so a page's styles can live in more than one place. Search
by label rather than trusting the number order.

## Quick reference by page

| Page or area              | Sections to search                     |
| ------------------------- | -------------------------------------- |
| Landing page              | 15, 40, 40c, 40d, 40e, 40f, 40g, 42    |
| Authentication            | 16, 19, 22                             |
| Club discovery and profile| 17, 24, 25                             |
| Create club               | 28                                     |
| Events                    | 29                                     |
| Announcements             | 30                                     |
| Issues                    | 31                                     |
| Leaderboard               | 18, 33                                 |
| Student profile           | 32                                     |
| Certificates              | 34, 35                                 |
| Institute admin           | 26                                     |
| Club leader dashboard     | 36, 38                                 |
| AI Club Finder            | 27                                     |

## Quick reference by concern

| Concern                          | Sections to search        |
| -------------------------------- | ------------------------- |
| Colors, fonts, spacing, shadows  | 1                         |
| Reset and base element styles    | 2                         |
| App shells and sidebars          | 3, 4, 5                   |
| Topbar                           | 6                         |
| Cards, buttons, forms, tables    | 7, 8, 9, 10               |
| Chips, empty state, grid helpers | 11, 12, 13, 14            |
| Toggle switch, progress bar      | 37, 20                    |
| Icons inside colored club dots   | 41                        |
| Mobile and responsive layers     | 39, 39b, 40g, 43, 44      |

## Full section list in file order

| Section | What it covers                                                   |
| ------- | ---------------------------------------------------------------- |
| 1       | Design tokens and CSS variables (colors, fonts, borders, shadows)|
| 2       | Base and reset                                                   |
| 3       | Shell layout systems (portal, landing, auth bodies)              |
| 4       | Sidebar shell                                                    |
| 5       | Sidebar elements (logo, menu items, user card)                   |
| 6       | Topbar                                                           |
| 7       | Card components (base card, stat cards, identity cards)          |
| 8       | Buttons and badges                                               |
| 9       | Forms and inputs                                                 |
| 10      | Data tables                                                      |
| 11      | Filter chips                                                     |
| 12      | Empty state                                                      |
| 13      | Grid and flex helpers                                            |
| 14      | Dashboard layouts                                                |
| 15      | Landing page styles (hero, nav, roles grid)                      |
| 16      | Auth page styles (login, signup shells and sidebars)             |
| 17      | Club cards on the discovery page                                 |
| 18      | Leaderboard podium                                               |
| 19      | Auth extras (divider, SSO buttons, form logo, password eye)      |
| 20      | Progress bar                                                     |
| 22      | OTP verification styles                                          |
| 23      | Banner color modifiers                                           |
| 24      | Club profile page                                                |
| 25      | Clubs page sections                                              |
| 26      | Admin dashboard                                                  |
| 27      | AI Club Finder, full-screen chat                                 |
| 28      | Create club form                                                 |
| 29      | Events                                                           |
| 30      | Announcements                                                    |
| 31      | Issues                                                           |
| 32      | Student profile                                                  |
| 33      | Leaderboard list                                                 |
| 34      | Certificate verify, public page                                  |
| 35      | Certificate viewer, standalone page                              |
| 36      | Members management                                               |
| 37      | Toggle switch                                                    |
| 38      | Leader club dashboard and role-isolated extras                   |
| 39      | Mobile bottom nav and responsive layer                           |
| 39b     | Mobile joined-clubs carousel visibility                          |
| 40      | Landing motion, full-screen sections, footer                     |
| 40c     | Landing filler sections (stats, marquee, how it works, quotes)   |
| 41      | Lucide icons inside colored club dots                            |
| 40d     | Landing density pass (hero balance, trending carousel)           |
| 42      | Hero app-usage showcase carousels                                |
| 40e     | Fit tuning so the hero screen composes into one viewport         |
| 40f     | Landing zoom for large screens                                   |
| 40g     | Mobile polish (nav, hero CTAs, role cards)                       |
| 43      | Mobile polish for club-leader and institute-admin pages          |
| 44      | Dashboard card tints for club-leader and institute-admin         |
| 45      | Leader top nav (legacy, component now unused)                     |
| 46      | Route loading bar + toast notifications                          |
| 47      | Club guidelines CRUD + application links                         |
| 48      | Post-login workspace chooser (member vs club leader)             |
| 49      | Unified card hover (gradient accent + lift)                      |
| 50      | Unified button hover colours                                     |
| 51      | Global entrance animation + route buffer                        |
| 52      | Custom select (replaces native dropdowns)                       |
| 53      | Mobile fixes for auth/verify pages                              |
| 54      | Auth layout fixes (signup scroll, login sidebar alignment)      |
| 55      | AI Club Finder response variants (event fallback + popularity)  |
| 56      | Club card artwork (banner icon/image) + AI finder pending state |
| 57      | Club proposal stack (propose-club + leader club pages)          |
| 58      | Issues page layout (responsive grid, wide-screen density)       |
| 59      | Issue conversation thread (student issues page)                 |
| 60      | Results picker (winner / runner-up selection)                   |
| 61      | Certificate viewer empty state                                  |
| 62      | Button loading spinner                                          |
| 63      | Leader club page - club switcher beside Edit/Delete             |
| 64      | Page-level loading / not-found state                            |

## Conventions

- One CSS declaration per line. Keep new styles in this format.
- Group new page styles under a new numbered banner and add a row here.
- Prefer the design tokens in section 1 over hard-coded values so the theme
  stays consistent.
