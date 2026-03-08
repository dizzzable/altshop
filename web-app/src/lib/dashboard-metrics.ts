import type { Subscription } from '@/types'
import { getRuntimeWebLocale } from '@/lib/locale'
import { translate } from '@/i18n/runtime'

const DAY_MS = 1000 * 60 * 60 * 24

export interface DeviceAggregate {
  used: number
  limit: number
  available: number
  unlimited: boolean
}

function parseDate(value: string): Date | null {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function isUnlimitedLimit(limit: number): boolean {
  return limit <= 0
}

export function calculateUsagePercent(used: number, limit: number): number {
  if (isUnlimitedLimit(limit)) {
    return 0
  }

  if (limit <= 0) {
    return 0
  }

  return clamp((used / limit) * 100, 0, 100)
}

export function getDaysUntil(dateValue: string): number | null {
  const date = parseDate(dateValue)
  if (!date) {
    return null
  }

  return Math.ceil((date.getTime() - Date.now()) / DAY_MS)
}

export function isExpiringSoon(dateValue: string, thresholdDays = 7): boolean {
  const daysUntil = getDaysUntil(dateValue)
  if (daysUntil === null) {
    return false
  }

  return daysUntil >= 0 && daysUntil <= thresholdDays
}

export function formatAbsoluteDate(dateValue: string): string {
  const date = parseDate(dateValue)
  if (!date) {
    return '-'
  }

  const locale = getRuntimeWebLocale() === 'ru' ? 'ru-RU' : 'en-US'
  return date.toLocaleDateString(locale, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function formatExpiryLabel(dateValue: string): string {
  const locale = getRuntimeWebLocale()
  const daysUntil = getDaysUntil(dateValue)
  if (daysUntil === null) {
    return translate('runtime.metrics.invalidDate', undefined, locale)
  }

  if (daysUntil < 0) {
    return translate('runtime.metrics.expiredAgo', { days: Math.abs(daysUntil) }, locale)
  }

  if (daysUntil === 0) {
    return translate('runtime.days.expiresToday', undefined, locale)
  }

  if (daysUntil === 1) {
    return translate('runtime.days.expiresTomorrow', undefined, locale)
  }

  return translate('runtime.metrics.expiresInDays', { days: daysUntil }, locale)
}

export function getActiveSubscriptions(subscriptions: Subscription[]): Subscription[] {
  const list = Array.isArray(subscriptions) ? subscriptions : []

  return list
    .filter((subscription) => subscription.status === 'ACTIVE')
    .sort((a, b) => {
      const left = parseDate(a.expire_at)?.getTime() ?? Number.POSITIVE_INFINITY
      const right = parseDate(b.expire_at)?.getTime() ?? Number.POSITIVE_INFINITY
      return left - right
    })
}

export function aggregateDeviceStats(subscriptions: Subscription[]): DeviceAggregate {
  const list = Array.isArray(subscriptions) ? subscriptions : []

  const used = list.reduce((sum, subscription) => {
    return sum + Math.max(subscription.devices_count || 0, 0)
  }, 0)

  const unlimited = list.some((subscription) => isUnlimitedLimit(subscription.device_limit))
  const limit = unlimited
    ? -1
    : list.reduce((sum, subscription) => sum + Math.max(subscription.device_limit || 0, 0), 0)
  const available = unlimited ? -1 : Math.max(limit - used, 0)

  return {
    used,
    limit,
    available,
    unlimited,
  }
}
