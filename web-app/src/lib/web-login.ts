const WEB_LOGIN_PATTERN = /^(?![._])[a-z0-9._]{3,32}(?<![._])$/
const BACKEND_INVALID_WEB_LOGIN_REASON = 'invalid username format'

export function normalizeWebLogin(value: string): string {
  return value.trim().toLowerCase()
}

export function isValidWebLogin(value: string): boolean {
  return WEB_LOGIN_PATTERN.test(normalizeWebLogin(value))
}

export function isInvalidWebLoginBackendError(detail: string | null | undefined): boolean {
  return detail?.toLowerCase().includes(BACKEND_INVALID_WEB_LOGIN_REASON) ?? false
}
