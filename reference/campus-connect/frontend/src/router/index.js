import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { startLoading, finishLoading } from '../composables/useLoadingBar'

const publicRoutes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'landing-body'
    }
  },
  {
    path: '/signup',
    name: 'signup',
    component: () => import('../views/SignupView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'auth-body'
    }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'auth-body'
    }
  },
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: () => import('../views/ForgotPasswordView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'auth-body'
    }
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('../views/ResetPasswordView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'auth-body'
    }
  },
  {
    path: '/verify-email',
    name: 'verify-email',
    component: () => import('../views/VerifyEmailView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'auth-body'
    }
  },
  {
    // :serial is optional - /verify alone is the public lookup form (anyone
    // types a serial in); /verify/CC-XXXX-YYYY-ZZZZZ auto-verifies on load
    // (what the certificate itself links to, and what shared links use).
    path: '/verify/:serial?',
    name: 'verify-cert',
    component: () => import('../views/VerifyCertView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'verify-body'
    }
  },
  {
    path: '/cert/view/:serial',
    name: 'view-cert',
    component: () => import('../views/ViewCertView.vue'),
    meta: {
      role: 'public',
      bodyClass: 'cert-viewer-body'
    }
  }
]

const studentRoutes = [
  {
    path: '/:slug/onboard',
    name: 'onboard',
    component: () => import('../views/OnboardView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'onboard-body'
    }
  },
  {
    path: '/:slug/workspace',
    name: 'workspace',
    component: () => import('../views/WorkspaceView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'auth-body'
    }
  },
  {
    path: '/:slug/clubs',
    name: 'clubs',
    component: () => import('../views/ClubDirectoryView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/clubs/:id',
    name: 'club-profile',
    component: () => import('../views/ClubProfileView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/find-clubs',
    name: 'find-clubs',
    component: () => import('../views/FindClubsView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/events',
    name: 'events',
    component: () => import('../views/EventsView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/events/:id',
    name: 'event-detail',
    component: () => import('../views/EventDetailView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/announcements',
    name: 'announcements',
    component: () => import('../views/AnnouncementsView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/issues',
    name: 'issues',
    component: () => import('../views/IssuesView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/profile',
    name: 'profile',
    component: () => import('../views/ProfileView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leaderboard',
    name: 'leaderboard',
    component: () => import('../views/LeaderboardView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
    }
  },
    {
    path: '/:slug/clubs/propose',
    name: 'propose-club',
    component: () => import('../views/CreateClubView.vue'),
    meta: {
      role: 'student',
      bodyClass: 'portal-body'
  }
}
]

const leaderRoutes = [
  {
    path: '/:slug/leader/club',
    name: 'leader-club',
    component: () => import('../views/LeaderClubView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/events',
    name: 'leader-events',
    component: () => import('../views/LeaderEventsView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/events/new',
    name: 'create-event',
    component: () => import('../views/CreateEventView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/events/:id/edit',
    name: 'edit-event',
    component: () => import('../views/CreateEventView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/events/:id/attend',
    name: 'attendance',
    component: () => import('../views/AttendanceView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/events/:id/results',
    name: 'results',
    component: () => import('../views/ResultsView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/members',
    name: 'members',
    component: () => import('../views/MembersView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/announcements',
    name: 'leader-announcements',
    component: () => import('../views/LeaderAnnouncementsView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/announcements/new',
    name: 'post-announcement',
    component: () => import('../views/PostAnnouncementView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/leader/issues',
    name: 'leader-issues',
    component: () => import('../views/LeaderIssuesView.vue'),
    meta: {
      role: 'leader',
      bodyClass: 'portal-body'
    }
  }
]

const adminRoutes = [
  {
    path: '/:slug/admin',
    name: 'admin',
    component: () => import('../views/AdminOverviewView.vue'),
    meta: {
      role: 'admin',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/admin/approvals',
    name: 'admin-approvals',
    component: () => import('../views/AdminApprovalsView.vue'),
    meta: {
      role: 'admin',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/admin/colleges',
    name: 'admin-colleges',
    component: () => import('../views/AdminCollegesView.vue'),
    meta: {
      role: 'admin',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/:slug/admin/guidelines',
    name: 'admin-guidelines',
    component: () => import('../views/AdminGuidelinesView.vue'),
    meta: {
      role: 'admin',
      bodyClass: 'portal-body'
    }
  },
  {
    path: '/admin/onboard',
    name: 'admin-onboard',
    component: () => import('../views/AdminOnboardView.vue'),
     meta: {
      role: 'admin',
      bodyClass: 'auth-body'
  }
},
]

const routes = [
  ...publicRoutes,
  ...studentRoutes,
  ...leaderRoutes,
  ...adminRoutes
]

function resolveGuardTarget(to, auth) {
  // "Remember me" at login persists a flag alongside the token. A signed-in
  // visitor who checked it and lands on the bare landing page - a bookmark,
  // a new tab, reopening the browser - goes straight to their dashboard
  // instead of seeing the marketing page again. Left unchecked, "/" behaves
  // exactly as before even while still logged in this session.
  if (to.path === '/' && auth.isLoggedIn && localStorage.getItem('cc_remember') === 'true') {
    return auth.homeRoute
  }

  if (to.meta.role === 'public') {
    return null
  }

  const slug = to.params.slug

  if (!auth.isLoggedIn) {
    return slug ? `/${slug}/login` : '/'
  }

  if (to.meta.role === 'leader') {
    if (auth.canManageClubs) {
      return null
    }
    return auth.homeRoute
  }

  if (auth.role !== to.meta.role) {
    return auth.homeRoute
  }

  return null
}

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(function guardByRole(to) {
  startLoading()

  const auth = useAuthStore()
  const target = resolveGuardTarget(to, auth)

  if (target && target !== to.path) {
    return target
  }

  return true
})

router.afterEach(function stopProgress() {
  finishLoading()
})

router.onError(function stopProgressOnError() {
  finishLoading()
})

export default router
export { routes, resolveGuardTarget }
