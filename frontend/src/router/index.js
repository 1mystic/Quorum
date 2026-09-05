import { createRouter, createWebHistory } from 'vue-router'
import { startLoading, finishLoading } from '../composables/useLoadingBar'
import { showRoleMismatch, dismissRoleMismatch } from '../composables/useRoleMismatch'
import { useAuthStore } from '../stores/auth'
import { useTenantStore } from '../stores/tenant'
import { labelForRole } from '../fixtures/roles'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { role: 'public', bodyClass: 'landing-body' }
  },

  // ── auth and onboarding: public, no sidebar shell ──
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { role: 'public', bodyClass: 'auth-body' } },
  { path: '/signup', name: 'signup', component: () => import('../views/SignupView.vue'), meta: { role: 'public', bodyClass: 'auth-body' } },
  { path: '/forgot-password', name: 'forgot-password', component: () => import('../views/ForgotPasswordView.vue'), meta: { role: 'public', bodyClass: 'auth-body' } },
  { path: '/reset-password', name: 'reset-password', component: () => import('../views/ResetPasswordView.vue'), meta: { role: 'public', bodyClass: 'auth-body' } },
  { path: '/verify-email', name: 'verify-email', component: () => import('../views/VerifyEmailView.vue'), meta: { role: 'public', bodyClass: 'auth-body' } },
  { path: '/onboard', name: 'onboard', component: () => import('../views/OnboardView.vue'), meta: { role: 'public', bodyClass: 'auth-body' } },
  // WorkspaceView.vue ("choose a workspace") is retired: app/models/user.py's
  // User.tenant_id is a single nullable FK, so a real account belongs to at
  // most one tenant and this screen's premise ("you belong to more than
  // one") is never true against the real backend - see TenantShell.vue's
  // sidebar for the same fix on the always-on switcher this route fed.

  // ── method cards: public, unauthenticated per docs/STATS_API.md §4 ──
  { path: '/methods', name: 'methods-index', component: () => import('../views/MethodsIndexView.vue'), meta: { role: 'public', bodyClass: 'landing-body' } },
  { path: '/methods/:id', name: 'method-card', component: () => import('../views/MethodCardView.vue'), meta: { role: 'public', bodyClass: 'landing-body' } },

  // ── getting-started guide: public, reachable with or without a session ──
  { path: '/guide', name: 'guide', component: () => import('../views/GuideView.vue'), meta: { role: 'public', bodyClass: 'landing-body' } },

  // ── marketing content pages, linked from the landing footer ──
  { path: '/about', name: 'about', component: () => import('../views/AboutView.vue'), meta: { role: 'public', bodyClass: 'landing-body' } },
  { path: '/verticals', name: 'verticals', component: () => import('../views/VerticalsView.vue'), meta: { role: 'public', bodyClass: 'landing-body' } },

  // ── member-facing core, tenant shell ──
  { path: '/t/:slug/dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  { path: '/t/:slug/requests', name: 'requests', component: () => import('../views/RequestsView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/requests/new', name: 'request-new', component: () => import('../views/RequestNewView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/requests/:ref', name: 'request-detail', component: () => import('../views/RequestDetailView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  { path: '/t/:slug/ledger', name: 'ledger', component: () => import('../views/LedgerView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  { path: '/t/:slug/events', name: 'events', component: () => import('../views/EventsView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/events/:id', name: 'event-detail', component: () => import('../views/EventDetailView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  { path: '/t/:slug/announcements', name: 'announcements', component: () => import('../views/AnnouncementsView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  { path: '/t/:slug/decisions', name: 'decisions', component: () => import('../views/DecisionsView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/decisions/:id', name: 'decision-detail', component: () => import('../views/DecisionDetailView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  { path: '/t/:slug/members', name: 'members', component: () => import('../views/MembersView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/profile', name: 'profile', component: () => import('../views/ProfileView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/assistant', name: 'assistant', component: () => import('../views/AssistantView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  // ── insight packs ──
  { path: '/t/:slug/insights/operations', name: 'insights-operations', component: () => import('../views/InsightsOperationsView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/insights/forecast', name: 'insights-forecast', component: () => import('../views/InsightsForecastView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/insights/governance', name: 'insights-governance', component: () => import('../views/InsightsGovernanceView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },
  { path: '/t/:slug/insights/comparison', name: 'insights-comparison', component: () => import('../views/InsightsComparisonView.vue'), meta: { role: 'member', bodyClass: 'portal-body' } },

  // ── committee / admin-facing ──
  { path: '/t/:slug/admin', name: 'admin-overview', component: () => import('../views/AdminOverviewView.vue'), meta: { role: 'admin', bodyClass: 'portal-body' } },
  { path: '/t/:slug/admin/approvals', name: 'admin-approvals', component: () => import('../views/AdminApprovalsView.vue'), meta: { role: 'admin', bodyClass: 'portal-body' } },
  { path: '/t/:slug/settings', name: 'tenant-settings', component: () => import('../views/TenantSettingsView.vue'), meta: { role: 'admin', bodyClass: 'portal-body' } },

  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to) {
    if (to.hash) {
      return { el: to.hash, top: 96 }
    }
    return { top: 0 }
  }
})

const TIER_RANK = { public: 0, member: 1, admin: 2 }

// A real gate now, not just a banner: `auth.role` is JWT-derived (a real
// MEMBER-vs-TENANT_ADMIN distinction), so a soft warn-only pass-through let
// every member session browse straight into the admin shell and see it
// render, only individual API calls inside it 403ing - that reads as "no
// RBAC" even though the backend itself was always safe. This is the
// product-facing access-control decision now, not a cosmetic one.
//
// The redirect itself is a second navigation, which runs this same guard
// again for the destination - a bare dismissRoleMismatch() on every entry
// would wipe the banner the mismatch branch just set before the browser
// ever painted it. suppressNextDismiss carries the banner across exactly
// that one follow-on navigation, and nowhere else.
let suppressNextDismiss = false

router.beforeEach(function checkAccess(to) {
  if (suppressNextDismiss) {
    suppressNextDismiss = false
  } else {
    dismissRoleMismatch()
  }

  const required = to.meta.role || 'public'
  if (required === 'public') return true

  const auth = useAuthStore()

  // No session at all: nothing to rank against, and the tenant dashboard
  // this would otherwise redirect to is exactly as unreachable as the page
  // that was actually requested.
  if (!auth.isLoggedIn) {
    // eslint-disable-next-line no-console
    console.warn(`[rbac] ${to.fullPath} requires "${required}", no session - redirecting to /login`)
    return '/login'
  }

  const currentTier = auth.role === 'admin' ? 'admin' : 'member'
  if (TIER_RANK[currentTier] >= TIER_RANK[required]) return true

  // This guard only needs a vertical for the mismatch message's role label,
  // never for access control - reading whatever TenantShell has already
  // cached for this slug (it fetches on every tenant-scoped mount) avoids a
  // second real fetch here; a cache miss falls back to the most common
  // vertical rather than blocking the redirect on a network call.
  const tenantStore = useTenantStore()
  const cachedTenant = tenantStore.bySlug[to.params.slug]
  const roleLabel = labelForRole(cachedTenant ? cachedTenant.vertical : 'rwa_society', auth.demoRole || 'resident')
  const message = `Viewing as ${roleLabel}. This page is ${required === 'admin' ? 'Admin' : 'Member'}-only, so you were sent back to the dashboard.`

  // eslint-disable-next-line no-console
  console.warn(`[rbac] ${to.fullPath} requires "${required}", current role is "${roleLabel}" (${currentTier}) - redirecting`)
  showRoleMismatch(message)
  suppressNextDismiss = true

  return `/t/${to.params.slug}/dashboard`
})

router.beforeEach(function beginNavigation() {
  startLoading()
  return true
})

router.afterEach(function endNavigation() {
  finishLoading()
})

export default router
