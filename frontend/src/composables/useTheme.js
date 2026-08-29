import { ref } from 'vue'

// Shared theme state: mirrors the toggle script in design/samples/quorum/*.html
// but as a Vue composable so every shell (landing nav, auth shell, tenant
// topbar) reads and writes the same ref instead of touching the DOM directly.

const STORAGE_KEY = 'quorum-theme'

function systemPrefersDark() {
  return typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
}

function readStored() {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage.getItem(STORAGE_KEY)
  } catch (err) {
    return null
  }
}

const stored = readStored()
const isDark = ref(stored ? stored === 'dark' : systemPrefersDark())

function apply() {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
}

apply()

export function useTheme() {
  function toggleTheme() {
    isDark.value = !isDark.value
    apply()
    try {
      window.localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
    } catch (err) {
      // storage unavailable, theme still applies for this session
    }
  }

  return { isDark, toggleTheme }
}
