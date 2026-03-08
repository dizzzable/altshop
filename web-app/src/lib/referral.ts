const REFERRAL_STORAGE_KEY = 'pending_referral_code'
const REFERRAL_PREFIX = 'ref_'
const REFERRAL_CODE_RE = /^(?:ref_)?[A-Za-z0-9]{4,64}$/
const REFERRAL_TTL_MS = 30 * 60 * 1000

type StoredReferralPayload = {
  code: string
  capturedAt: number
}

function getSessionStorage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

function parseStoredPayload(raw: string): StoredReferralPayload | null {
  try {
    const parsed = JSON.parse(raw) as Partial<StoredReferralPayload>
    if (
      parsed &&
      typeof parsed === 'object' &&
      typeof parsed.code === 'string' &&
      typeof parsed.capturedAt === 'number'
    ) {
      return {
        code: parsed.code,
        capturedAt: parsed.capturedAt,
      }
    }
  } catch {
    // Ignore JSON parse errors and fallback below.
  }

  // Legacy format: plain referral code string in localStorage.
  if (typeof raw === 'string' && raw.trim().length > 0) {
    return {
      code: raw,
      capturedAt: 0,
    }
  }

  return null
}

function readStoredPayload(): StoredReferralPayload | null {
  const storage = getSessionStorage()
  if (storage) {
    const sessionRaw = storage.getItem(REFERRAL_STORAGE_KEY)
    if (sessionRaw) {
      return parseStoredPayload(sessionRaw)
    }
  }

  try {
    const legacyRaw = localStorage.getItem(REFERRAL_STORAGE_KEY)
    if (legacyRaw) {
      return parseStoredPayload(legacyRaw)
    }
  } catch {
    // Ignore legacy storage read errors.
  }

  return null
}

function isExpired(payload: StoredReferralPayload): boolean {
  if (payload.capturedAt <= 0) {
    return true
  }
  return Date.now() - payload.capturedAt > REFERRAL_TTL_MS
}

export function normalizeReferralCode(
  rawCode?: string | null,
  options: { requirePrefix?: boolean } = {}
): string | null {
  const { requirePrefix = false } = options
  if (!rawCode) {
    return null
  }

  const code = rawCode.trim()
  if (!code || !REFERRAL_CODE_RE.test(code)) {
    return null
  }
  if (requirePrefix && !code.startsWith(REFERRAL_PREFIX)) {
    return null
  }

  if (code.startsWith(REFERRAL_PREFIX)) {
    return code
  }

  return `${REFERRAL_PREFIX}${code}`
}

export function extractReferralCodeFromSearch(search: string): string | null {
  const params = new URLSearchParams(search)
  const explicitCandidates = [
    params.get('ref'),
    params.get('referral'),
  ]

  for (const candidate of explicitCandidates) {
    const normalized = normalizeReferralCode(candidate)
    if (normalized) {
      return normalized
    }
  }

  const telegramStartCandidates = [params.get('startapp'), params.get('start')]
  for (const candidate of telegramStartCandidates) {
    const normalized = normalizeReferralCode(candidate, { requirePrefix: true })
    if (normalized) {
      return normalized
    }
  }

  return null
}

export function getStoredReferralCode(): string | null {
  const payload = readStoredPayload()
  if (!payload) {
    return null
  }

  const normalizedCode = normalizeReferralCode(payload.code)
  if (!normalizedCode || isExpired(payload)) {
    clearStoredReferralCode()
    return null
  }

  return normalizedCode
}

export function setStoredReferralCode(referralCode: string): void {
  const normalizedCode = normalizeReferralCode(referralCode)
  if (!normalizedCode) {
    return
  }

  const payload: StoredReferralPayload = {
    code: normalizedCode,
    capturedAt: Date.now(),
  }

  const storage = getSessionStorage()
  try {
    storage?.setItem(REFERRAL_STORAGE_KEY, JSON.stringify(payload))
  } catch {
    // Ignore session storage errors.
  }

  try {
    // Drop legacy value to avoid stale referrals from old sessions.
    localStorage.removeItem(REFERRAL_STORAGE_KEY)
  } catch {
    // Ignore legacy storage errors.
  }
}

export function clearStoredReferralCode(): void {
  const storage = getSessionStorage()
  try {
    storage?.removeItem(REFERRAL_STORAGE_KEY)
  } catch {
    // Ignore session storage errors.
  }

  try {
    localStorage.removeItem(REFERRAL_STORAGE_KEY)
  } catch {
    // Ignore legacy storage errors.
  }
}

export function captureReferralCodeFromLocation(location: Location = window.location): string | null {
  const referralCode = extractReferralCodeFromSearch(location.search)
  if (referralCode) {
    setStoredReferralCode(referralCode)
  }
  return referralCode
}

export function getReferralCodeForAuth(): string | null {
  return captureReferralCodeFromLocation() ?? getStoredReferralCode()
}
