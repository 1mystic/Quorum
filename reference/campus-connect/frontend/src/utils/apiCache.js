/**
 * A small in-memory response cache for GET-shaped API calls.
 *
 * clubsStore and eventsStore already avoid refetching on every route visit,
 * because Pinia store state survives across navigation - only a full page
 * reload clears it. Several other views never got that treatment: they fetch
 * straight into a local component ref inside onMounted(), and a local ref is
 * destroyed and rebuilt every time the component remounts, so navigating away
 * and back re-ran the request from scratch every single time.
 *
 * This gives those views the same property without turning each one into a
 * Pinia store: the cache lives in this module, not in any component, so it
 * survives route changes and is only ever cleared by a hard refresh (module
 * state resets) or by calling invalidateCache() after a mutation that makes
 * the cached data stale.
 */

const DEFAULT_TTL_MS = 2 * 60 * 1000 // 2 minutes - long enough to skip refetching on a quick back-and-forth between pages, short enough that changes from elsewhere still show up soon.

const cache = new Map()

/**
 * Return the cached value for `key` if it is still fresh; otherwise call
 * `fetchFn`, cache the result, and return it.
 */
export async function cachedFetch(key, fetchFn, ttlMs = DEFAULT_TTL_MS) {
  const entry = cache.get(key)
  const isFresh = entry && Date.now() - entry.time < ttlMs

  if (isFresh) {
    return entry.data
  }

  const data = await fetchFn()
  cache.set(key, { data, time: Date.now() })
  return data
}

/**
 * Drop one cached entry (or, with no key, everything) so the next read is
 * forced to hit the network. Call this right after any write that would
 * make the cached read stale - e.g. after raising an issue, invalidate the
 * key that lists issues.
 */
export function invalidateCache(key) {
  if (key) {
    cache.delete(key)
  } else {
    cache.clear()
  }
}
