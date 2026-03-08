export interface StoredGiftPromocode {
  code: string
  createdAt: string
}

const GIFT_PROMOCODES_STORAGE_KEY = 'gift_promocodes_registry_v1'

function normalizeCode(rawCode: string): string {
  return rawCode.trim().toUpperCase()
}

function readRaw(): StoredGiftPromocode[] {
  try {
    const raw = localStorage.getItem(GIFT_PROMOCODES_STORAGE_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed
      .filter(
        (item): item is StoredGiftPromocode =>
          Boolean(item) &&
          typeof item === 'object' &&
          typeof item.code === 'string' &&
          typeof item.createdAt === 'string'
      )
      .map((item) => ({
        code: normalizeCode(item.code),
        createdAt: item.createdAt,
      }))
  } catch {
    return []
  }
}

function writeRaw(items: StoredGiftPromocode[]): void {
  try {
    localStorage.setItem(GIFT_PROMOCODES_STORAGE_KEY, JSON.stringify(items))
  } catch {
    // Ignore storage errors.
  }
}

export function getStoredGiftPromocodes(): StoredGiftPromocode[] {
  const uniqueByCode = new Map<string, StoredGiftPromocode>()
  for (const item of readRaw()) {
    uniqueByCode.set(item.code, item)
  }
  return Array.from(uniqueByCode.values()).sort((left, right) => {
    return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
  })
}

export function addStoredGiftPromocode(code: string): void {
  const normalizedCode = normalizeCode(code)
  if (!normalizedCode) {
    return
  }
  const current = getStoredGiftPromocodes()
  if (current.some((item) => item.code === normalizedCode)) {
    return
  }
  writeRaw([{ code: normalizedCode, createdAt: new Date().toISOString() }, ...current])
}

export function removeStoredGiftPromocode(code: string): void {
  const normalizedCode = normalizeCode(code)
  if (!normalizedCode) {
    return
  }
  const next = getStoredGiftPromocodes().filter((item) => item.code !== normalizedCode)
  writeRaw(next)
}
