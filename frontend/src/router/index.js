import { createRouter, createWebHistory } from 'vue-router'
import { startLoading, finishLoading } from '../composables/useLoadingBar'
import { showRoleMismatch, dismissRoleMismatch } from '../composables/useRoleMismatch'
import { useAuthStore } from '../stores/auth'
import { tenantBySlug } from '../fixtures/tenants'
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
  { path: '/workspace', name: 'workspace', component: () => import('../views/WorkspaceView.vue'), meta: { role: 'member', bodyClass: 'auth-body' } },

  // ── method cards: public, unauthenticated per docs/STATS_API.md §4 ──
  { path: '/methods', name: 'methods-index', component: () => import('../views/MethodsIndexView.vue'), meta: { role: 'public', bodyClass: 'landing-body' } },
  { path: '/methods/:id', name: 'method-card', component: () => import('../views/MethodCardView.vue'), meta: { role: 'public', bodyClass: 'landing-body' } },

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

// This is a soft, UI-side gate: it never blocks navigation itself, since the
// backend is the real enforcement point (every route 403s a mismatched
// scope, per docs/RULES.md). A tier mismatch here just logs and surfaces a
// dismissible banner, ahead of the API call that would otherwise 403.
router.beforeEach(function checkDemoRole(to) {
  dismissRoleMismatch()

  const required = to.meta.role || 'public'
  if (required === 'public') return true

  const auth = useAuthStore()
  const currentTier = auth.role === 'admin' ? 'admin' : 'member'

  if (TIER_RANK[currentTier] >= TIER_RANK[required]) return true

  const tenant = tenantBySlug(to.params.slug)
  const roleLabel = labelForRole(tenant ? tenant.vertical : 'rwa_society', auth.demoRole || 'resident')
  const message = `Viewing as ${roleLabel}. This page is normally ${required === 'admin' ? 'Admin' : 'Member'}-only.`

  // eslint-disable-next-line no-console
  console.warn(`[demo-rbac] ${to.fullPath} requires "${required}", current demo role is "${roleLabel}" (${currentTier})`)
  showRoleMismatch(message)

  return true
})

router.beforeEach(function beginNavigation() {
  startLoading()
  return true
})

router.afterEach(function endNavigation() {
  finishLoading()
})

export default router
