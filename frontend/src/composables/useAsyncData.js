import { ref } from 'vue'
import { ApiError, NetworkError } from '../api/client'

// Small shared shape for "a view called the real API": loading, data,
// and an error message that tells a network failure apart from the
// backend's own stated reason, per the task's requirement to handle a
// real network error and a real 401 (401 itself is handled once in
// api/client.js, this only has to render whatever it throws).

export function useAsyncData() {
  const loading = ref(false)
  const error = ref('')
  const data = ref(null)

  // Deliberately does not rethrow: most callers fire this from onMounted
  // without awaiting it, and an unhandled rejection there is worse than a
  // swallowed one - `error.value` is the one true signal of failure.
  async function run(fn) {
    loading.value = true
    error.value = ''
    try {
      data.value = await fn()
      return data.value
    } catch (err) {
      if (err instanceof NetworkError || err instanceof ApiError) {
        error.value = err.message
      } else {
        error.value = 'Something went wrong loading this page.'
      }
      return null
    } finally {
      loading.value = false
    }
  }

  return { loading, error, data, run }
}
