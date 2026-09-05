import { describe, test, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useTenantStore } from './tenant'
import { getTenant } from '../api/tenant'

vi.mock('../api/tenant', () => ({ getTenant: vi.fn() }))

const RAW = {
  name: 'Greenfield RWA',
  slug: 'greenfield-rwa',
  vertical: 'rwa_society',
  description: '80 flats',
  enabled_packs: ['reliability_ops'],
  timezone: 'Asia/Kolkata'
}

describe('useTenantStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getTenant.mockReset()
  })

  test('fetches a real tenant and enriches it with vertical config', async () => {
    getTenant.mockResolvedValue(RAW)
    const store = useTenantStore()

    const tenant = await store.fetchTenant('greenfield-rwa')

    expect(getTenant).toHaveBeenCalledWith('greenfield-rwa')
    expect(tenant.name).toBe('Greenfield RWA')
    expect(tenant.labels.request).toBe('Complaint')
    expect(tenant.optional_packs).toEqual(['forecast_risk', 'bayes_ranking', 'governance_insight'])
    expect(store.bySlug['greenfield-rwa']).toEqual(tenant)
  })

  test('falls back to generic vocabulary for a vertical with no real adapter', async () => {
    getTenant.mockResolvedValue({ ...RAW, vertical: 'sports_club' })
    const store = useTenantStore()

    const tenant = await store.fetchTenant('greenfield-rwa')

    expect(tenant.labels.request).toBe('Request')
    expect(tenant.requestCategories).toEqual(['general', 'other'])
  })

  test('a second call for the same slug is served from cache, not a second request', async () => {
    getTenant.mockResolvedValue(RAW)
    const store = useTenantStore()

    await store.fetchTenant('greenfield-rwa')
    await store.fetchTenant('greenfield-rwa')

    expect(getTenant).toHaveBeenCalledTimes(1)
  })

  test('two concurrent callers for the same slug dedupe into one real request', async () => {
    let resolve
    getTenant.mockReturnValue(new Promise((r) => { resolve = r }))
    const store = useTenantStore()

    const first = store.fetchTenant('greenfield-rwa')
    const second = store.fetchTenant('greenfield-rwa')
    resolve(RAW)
    const [a, b] = await Promise.all([first, second])

    expect(getTenant).toHaveBeenCalledTimes(1)
    expect(a).toBe(b)
  })

  test('a failed fetch records the error and leaves the cache empty, not a crash', async () => {
    getTenant.mockRejectedValue(new Error('Tenant not found'))
    const store = useTenantStore()

    const tenant = await store.fetchTenant('does-not-exist')

    expect(tenant).toBeNull()
    expect(store.bySlug['does-not-exist']).toBeUndefined()
    expect(store.errorSlug).toBe('does-not-exist')
    expect(store.errorMessage).toBe('Tenant not found')
  })

  test('force refetches even when a cached entry already exists', async () => {
    getTenant.mockResolvedValue(RAW)
    const store = useTenantStore()

    await store.fetchTenant('greenfield-rwa')
    await store.fetchTenant('greenfield-rwa', { force: true })

    expect(getTenant).toHaveBeenCalledTimes(2)
  })
})
