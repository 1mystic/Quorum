// Auto-captures a screenshot of every Campus Connect screen for all three roles,
// in both desktop and mobile widths.
//
// Usage:
//   1. Start the dev server in one terminal:   npm run dev
//   2. Install the browser once:               npx playwright install chromium
//   3. Run this script in another terminal:     node scripts/capture-screens.mjs
//
// Output lands in  frontend/screenshots/<viewport>/<group>__<route>.png
//
// Auth note: the app keeps the signed-in role in localStorage ('cc_role') and
// club leadership is a member capability, so the leader pages are reached with
// the student role. We set localStorage before navigating each group.

import { chromium } from 'playwright'
import { mkdirSync } from 'fs'

const BASE = process.env.CC_BASE || 'http://localhost:5173'
const OUT = 'screenshots'

const groups = {
  public: {
    role: null,
    routes: [
      '/', '/login', '/signup', '/forgot-password',
      '/verify-email', '/verify/CC-2026-1841', '/cert/view'
    ]
  },
  student: {
    role: 'student',
    routes: [
      '/onboard', '/workspace', '/clubs', '/clubs/1', '/find-clubs',
      '/events', '/events/1', '/announcements', '/issues', '/profile', '/leaderboard'
    ]
  },
  leader: {
    role: 'student',
    routes: [
      '/leader/club', '/leader/members', '/leader/events', '/leader/events/new',
      '/leader/events/1/attend', '/leader/events/1/results',
      '/leader/announcements', '/leader/announcements/new', '/leader/issues', '/leader/clubs/new'
    ]
  },
  admin: {
    role: 'admin',
    routes: ['/admin', '/admin/approvals', '/admin/colleges', '/admin/guidelines']
  }
}

const viewports = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 }
}

function safeName(route) {
  if (route === '/') return 'home'
  return route.replace(/^\//, '').replace(/\//g, '_').replace(/:/g, '')
}

async function capture(browser, viewportName, viewport) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: 2 })
  const page = await context.newPage()

  for (const [group, cfg] of Object.entries(groups)) {
    // Prime the role in localStorage on a first visit, then reload per route.
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
    await page.evaluate(function setRole(role) {
      if (role) {
        localStorage.setItem('cc_role', role)
      } else {
        localStorage.removeItem('cc_role')
      }
    }, cfg.role)

    for (const route of cfg.routes) {
      try {
        await page.goto(BASE + route, { waitUntil: 'networkidle', timeout: 15000 })
      } catch (error) {
        // The mock API call to :8000 fails fast; keep going once the DOM settles.
      }
      await page.waitForTimeout(700)
      const dir = `${OUT}/${viewportName}`
      mkdirSync(dir, { recursive: true })
      await page.screenshot({ path: `${dir}/${group}__${safeName(route)}.png`, fullPage: true })
      console.log(`[${viewportName}] ${group} ${route}`)
    }
  }

  await context.close()
}

async function main() {
  const browser = await chromium.launch()
  for (const [name, viewport] of Object.entries(viewports)) {
    await capture(browser, name, viewport)
  }
  await browser.close()
  console.log('\nDone. Screenshots are in frontend/screenshots/')
}

main()
