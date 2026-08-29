import { createRouter, createWebHistory } from 'vue-router'
import { startLoading, finishLoading } from '../composables/useLoadingBar'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
    meta: { role: 'public', bodyClass: 'landing-body' }
  },
  {
    path: '/t/:slug/dashboard',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { role: 'member', bodyClass: 'portal-body' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach(function beginNavigation() {
  startLoading()
  return true
})

router.afterEach(function endNavigation() {
  finishLoading()
})

export default router
