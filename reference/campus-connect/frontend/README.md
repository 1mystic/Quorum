# Campus Connect - Frontend

> Find your club. Build your story.

The web client for Campus Connect, the student club management platform.
It is a single-page application built with Vue 3, Vue Router, and Pinia,
bundled by Vite. All visual styling is driven by one central design system
stylesheet.

## Tech stack

| Layer      | Choice                        |
| ---------- | ----------------------------- |
| Framework  | Vue 3 (Composition API)       |
| Routing    | Vue Router 4                  |
| State      | Pinia                         |
| Build tool | Vite                          |
| Icons      | lucide-vue-next               |
| Testing    | Vitest and Vue Test Utils     |

## Prerequisites

- Node.js version 20 or newer
- npm version 10 or newer (ships with Node)

Check what you have:

```bash
node -v
npm -v
```

## Getting started

From inside the `frontend` directory:

```bash
# 1. Install dependencies
npm install

# 2. Start the development server
npm run dev
```

The dev server prints a local URL, usually http://localhost:5173.
Open it in your browser. Vite hot-reloads changes to Vue files and to the
stylesheet as you save.

## Available scripts

| Command              | What it does                                      |
| -------------------- | ------------------------------------------------- |
| `npm run dev`        | Start the Vite dev server with hot reload         |
| `npm run build`      | Produce an optimized production build in `dist`   |
| `npm run preview`    | Serve the production build locally for a final check |
| `npm run test`       | Run the unit test suite once                      |
| `npm run test:watch` | Run the tests in watch mode while developing      |

## Capturing screenshots

`scripts/capture-screens.mjs` walks every screen for all three roles and saves
desktop and mobile screenshots under `screenshots/`. It uses Playwright and
signs in by setting the role in local storage, so no manual clicking is needed.

```bash
# 1. Start the dev server in one terminal
npm run dev

# 2. Install the browser once
npx playwright install chromium

# 3. Run the capture in another terminal
node scripts/capture-screens.mjs
```

## Project structure

```
frontend/
  index.html            App entry HTML, mounts the Vue app
  vite.config.js        Vite configuration
  public/               Static assets served as-is
  src/
    main.js             App bootstrap, imports the global stylesheet
    App.vue             Root component, picks the page shell class
    router/             Route definitions
    stores/             Pinia stores (auth, events, and so on)
    api/                Mock data and API helper functions
    composables/        Reusable Composition API logic
    components/
      layout/           Sidebars, topbar, mobile bottom nav
      ui/               Shared building blocks (cards, pills, rows)
    views/              One component per page
    assets/
      style.css         The single central stylesheet
      STYLE-INDEX.md    Map of which section of style.css covers what
```

## Styling and the design system

All styles live in one file, `src/assets/style.css`. It opens with the
design tokens (colors, fonts, spacing, shadows) as CSS variables, then moves
through shared components, then page-specific styles, and finishes with the
motion and responsive layers.

Because the file is large, use `src/assets/STYLE-INDEX.md` to jump to the
right section quickly. Each block is marked with a numbered comment banner
such as `/*  27. AI Club Finder  */`, so searching for that label is the
fastest way to land in the correct place.

Formatting convention: one CSS declaration per line. Keep it that way when
you add styles so the file stays easy to scan and to review in diffs.

## Design inspiration and why it fits Campus Connect

Campus Connect has to work for three very different people at once: a
first-year student deciding whether to join a club, a club leader running
events and issuing certificates, and an institute administrator who needs to
trust the platform enough to approve clubs and rely on its records. The
design choices below are built around that tension: warm and inviting enough
for students to want to use it, structured and credible enough for staff to
rely on it.

**Color palette.** The base is a warm cream canvas with soft brown ink text,
instead of stark white and black. This reads as a friendly community space
rather than clinical enterprise software, which matters for adoption among
students who are the platform's largest and most reluctant-to-onboard user
group. On top of that neutral base, each role gets its own accent color:
orange for students, green for club leaders, blue and navy for
administrators. This is not decoration, it is wayfinding. On a platform with
three distinct roles, a consistent accent color lets a person recognize
which part of the app they are in at a glance, before reading a single word.
Brighter saturated colors are reserved for moments worth celebrating, such as
certificates, leaderboards, and event cards, so color also reinforces the
platform's core promise of recognizing participation.

**Typography.** Headings use Outfit, a geometric but rounded typeface that
feels confident without feeling cold. Body text uses Plus Jakarta Sans, a
highly legible humanist sans that keeps dense dashboards, member lists, and
event details easy to scan. Certificate codes and identifiers use JetBrains
Mono, a monospace face that signals precision and machine verifiability,
which matters directly for the platform's verifiable certificate feature.

**Design system.** Rounded cards, pill-shaped buttons, and soft shadows give
the interface a tactile, approachable feel similar to the consumer apps
students already use daily. Illustrated characters and small celebratory
details humanize what could otherwise be a plain administrative tool. The
system is mobile-first because students live on their phones, so navigation,
carousels, and stacked cards are all designed to collapse cleanly to small
screens while the same components scale up for the wider dashboards
administrators use on desktop.

**Why this fits our clients.** Indian higher-education institutions need one
product that satisfies three audiences with different priorities: student
adoption, club leader efficiency, and administrative trust. A single
consistent design system, built from shared tokens and reused components,
lets the same visual language stretch across all three without feeling like
three different products stitched together. The result should feel like it
belongs to campus life rather than looking like generic institutional
software.

## Source control workflow

This project follows a three-tier branch model: `feature/...` branches merge
into `dev`, and `dev` merges into `main`. Everything ships through a pull
request. Pull the latest `dev` before starting work, branch off it with a
name like `feature/yourname-task`, commit in small labeled chunks
(`feat:`, `fix:`, `refactor:`), and open a pull request into `dev` when the
work is ready. See the repository RULES file for the full playbook.

## License

This repository does not currently include a LICENSE file. It is a student
team project (Team NexMind, Team-003, IITM BS Software Engineering course)
and is not published for external use.
