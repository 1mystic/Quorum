// Mirrors the backend's actual constraints (app/schemas/user.py) so a form
// catches what the API would reject before a round trip, not instead of the
// backend check. The backend is still the real gate: this only makes the
// common cases fail fast with a clear message rather than a raw 422.
export const PASSWORD_MIN_LENGTH = 8

export function useFormValidation() {
  // A pragmatic email shape check, not a full RFC 5322 parser: one @, a
  // label before it, a domain with at least one dot after it. The backend's
  // EmailStr is stricter still (it also rejects reserved TLDs like .test),
  // so a value can pass here and still be refused by the API. That gap is
  // handled by describeApiError reading the backend's real detail, not by
  // trying to replicate every backend rule here.
  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  function isValidEmail(email) {
    return EMAIL_PATTERN.test(String(email).trim())
  }

  function allFieldsFilled(fields) {
    return Object.values(fields).every(function checkField(value) {
      return String(value).trim().length > 0
    })
  }

  function isStrongEnough(password) {
    return String(password).length >= PASSWORD_MIN_LENGTH
  }

  return { isValidEmail, allFieldsFilled, isStrongEnough, PASSWORD_MIN_LENGTH }
}
