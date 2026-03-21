import type { PurchaseType, Subscription } from '@/types'

export const PENDING_PURCHASE_CONTEXT_KEY = 'altshop:web:pending-purchase'

export interface PendingPurchaseContext {
  startedAt: string
  purchaseType: PurchaseType
  renewIds: number[]
  planId: number | null
  durationDays: number | null
}

function isValidPurchaseType(value: unknown): value is PurchaseType {
  return value === 'NEW' || value === 'RENEW' || value === 'UPGRADE' || value === 'ADDITIONAL'
}

function normalizeRenewIds(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value
    .map((entry) => Number(entry))
    .filter((entry) => Number.isInteger(entry) && entry > 0)
}

function normalizeNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null
  }

  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return null
  }
  return parsed
}

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

export function savePendingPurchaseContext(context: PendingPurchaseContext): void {
  if (!canUseStorage()) {
    return
  }

  try {
    window.localStorage.setItem(PENDING_PURCHASE_CONTEXT_KEY, JSON.stringify(context))
  } catch {
    // no-op: storage might be blocked
  }
}

export function readPendingPurchaseContext(): PendingPurchaseContext | null {
  if (!canUseStorage()) {
    return null
  }

  try {
    const raw = window.localStorage.getItem(PENDING_PURCHASE_CONTEXT_KEY)
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as Partial<PendingPurchaseContext>
    if (!parsed || !isValidPurchaseType(parsed.purchaseType)) {
      return null
    }

    const startedAt = typeof parsed.startedAt === 'string' ? parsed.startedAt : ''
    if (!startedAt) {
      return null
    }

    return {
      startedAt,
      purchaseType: parsed.purchaseType,
      renewIds: normalizeRenewIds(parsed.renewIds),
      planId: normalizeNullableNumber(parsed.planId),
      durationDays: normalizeNullableNumber(parsed.durationDays),
    }
  } catch {
    return null
  }
}

export function clearPendingPurchaseContext(): void {
  if (!canUseStorage()) {
    return
  }

  try {
    window.localStorage.removeItem(PENDING_PURCHASE_CONTEXT_KEY)
  } catch {
    // no-op
  }
}

function toTimestamp(dateValue: string): number {
  const ts = new Date(dateValue).getTime()
  return Number.isNaN(ts) ? Number.NEGATIVE_INFINITY : ts
}

export function resolveSubscriptionForConnect(
  subscriptions: Subscription[],
  context: PendingPurchaseContext | null
): Subscription | null {
  if (!subscriptions.length) {
    return null
  }

  if (context?.renewIds.length) {
    for (const renewId of context.renewIds) {
      const renewed = subscriptions.find((subscription) => subscription.id === renewId)
      if (renewed) {
        return renewed
      }
    }
  }

  return subscriptions.reduce<Subscription | null>((latest, current) => {
    if (!latest) {
      return current
    }

    const currentUpdatedAt = toTimestamp(current.updated_at)
    const latestUpdatedAt = toTimestamp(latest.updated_at)
    if (currentUpdatedAt > latestUpdatedAt) {
      return current
    }
    if (currentUpdatedAt < latestUpdatedAt) {
      return latest
    }
    return current.id > latest.id ? current : latest
  }, null)
}
