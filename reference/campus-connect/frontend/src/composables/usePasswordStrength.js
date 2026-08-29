import { ref } from 'vue'

export function usePasswordStrength() {
  const strength = ref(0)

  function measurePasswordStrength(password) {
    if (password.length === 0) return 0

    let score = 0
    if (password.length >= 8) score++
    if (password.length >= 10) score++
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++
    if (/[0-9]/.test(password) || /[^A-Za-z0-9]/.test(password)) score++

    return score
  }

  function updateStrength(password) {
    strength.value = measurePasswordStrength(password)
  }

  return { strength, updateStrength, measurePasswordStrength }
}
