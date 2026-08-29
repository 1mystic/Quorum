import { describe, test, expect } from 'vitest'
import { usePasswordStrength } from './usePasswordStrength'

describe('usePasswordStrength', () => {
  test('empty password scores zero', () => {
    const { measurePasswordStrength } = usePasswordStrength()

    expect(measurePasswordStrength('')).toBe(0)
  })

  test('short lowercase password scores low', () => {
    const { measurePasswordStrength } = usePasswordStrength()

    expect(measurePasswordStrength('abcdef')).toBe(1)
  })

  test('long mixed-case password with digits scores full marks', () => {
    const { measurePasswordStrength } = usePasswordStrength()

    expect(measurePasswordStrength('Abcdefgh12')).toBe(4)
  })

  test('updateStrength stores the score in the strength ref', () => {
    const { strength, updateStrength } = usePasswordStrength()

    updateStrength('Abcdefgh12')

    expect(strength.value).toBe(4)
  })
})
