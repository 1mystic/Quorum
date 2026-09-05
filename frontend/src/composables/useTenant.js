import { computed, toValue, watch } from 'vue'
import { useTenantStore } from '../stores/tenant'

// The one place a tenant-scoped view should read tenant identity from.
// `slugSource` is a ref, a getter or a plain string (see Vue's `toValue`);
// this fetches GET /api/t/{slug}/tenant through the store's cache once per
// slug, and again whenever the slug changes (a session can move between
// tenants across two `/t/:slug/...` navigations without a full reload).
//
// `tenant` starts out `null` and arrives asynchronously - every caller must
// gate its template on it (`v-if="tenant"`), not assume it like the old
// `tenantBySlug(slug.value)` synchronous fixture lookup did.

export function useTenant(slugSource) {
  const store = useTenantStore()
  const slug = computed(() => toValue(slugSource))

  function load() {
    if (slug.value) store.fetchTenant(slug.value)
  }

  load()
  watch(slug, load)

  const tenant = computed(() => (slug.value ? store.bySlug[slug.value] || null : null))
  const loading = computed(() => !tenant.value && store.loadingSlug === slug.value)
  const error = computed(() => (store.errorSlug === slug.value ? store.errorMessage : ''))

  function reload() {
    if (slug.value) store.fetchTenant(slug.value, { force: true })
  }

  return { tenant, loading, error, reload }
}
