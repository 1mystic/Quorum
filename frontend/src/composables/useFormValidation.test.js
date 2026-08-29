import { describe, test, expect } from 'vitest'
import { useFormValidation } from './useFormValidation'

describe('useFormValidation', () => {
  test('isValidEmail accepts an address with an @ sign', () => {
    const { isValidEmail } = useFormValidation()

    expect(isValidEmail('shikha@knit.ac.in')).toBe(true)
  })

  test('isValidEmail rejects an address without an @ sign', () => {
    const { isValidEmail } = useFormValidation()

    expect(isValidEmail('shikha.knit.ac.in')).toBe(false)
  })

  test('isValidEmail rejects an empty string', () => {
    const { isValidEmail } = useFormValidation()

    expect(isValidEmail('   ')).toBe(false)
  })

  test('allFieldsFilled passes when every field has content', () => {
    const { allFieldsFilled } = useFormValidation()

    expect(allFieldsFilled({ name: 'Shikha', email: 'a@b.c' })).toBe(true)
  })

  test('allFieldsFilled fails when a field is blank', () => {
    const { allFieldsFilled } = useFormValidation()

    expect(allFieldsFilled({ name: 'Shikha', email: '  ' })).toBe(false)
  })

  test('isStrongEnough requires at least eight characters', () => {
    const { isStrongEnough } = useFormValidation()

    expect(isStrongEnough('1234567')).toBe(false)
    expect(isStrongEnough('12345678')).toBe(true)
  })
})
