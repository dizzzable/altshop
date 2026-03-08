import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { getRuntimeWebLocale } from '@/lib/locale'
import type { WebLocale } from '@/types'
import { translate } from '@/i18n/runtime'

function resolveLocale(locale?: string): WebLocale {
  const source = (locale ?? getRuntimeWebLocale()).toLowerCase()
  return source.startsWith('ru') ? 'ru' : 'en'
}

/**
 * Merge Tailwind CSS classes with clsx for conditional classes
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format bytes to human-readable format
 */
export function formatBytes(bytes: number, decimals = 2): string {
  const locale = resolveLocale()
  if (bytes === 0) return translate('runtime.bytes.zero', undefined, locale)
  if (bytes === -1) return translate('runtime.bytes.unlimited', undefined, locale)

  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = [
    translate('runtime.bytes.unit.bytes', undefined, locale),
    translate('runtime.bytes.unit.kb', undefined, locale),
    translate('runtime.bytes.unit.mb', undefined, locale),
    translate('runtime.bytes.unit.gb', undefined, locale),
    translate('runtime.bytes.unit.tb', undefined, locale),
  ]

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

/**
 * Convert traffic limit in gigabytes to bytes.
 * Subscription/plan limits are stored as GB in API, while usage is returned in bytes.
 */
export function gigabytesToBytes(gigabytes: number): number {
  if (!Number.isFinite(gigabytes)) {
    return 0
  }

  if (gigabytes <= 0) {
    return gigabytes
  }

  const multiplier = 1024 ** 3
  return Math.round(gigabytes * multiplier)
}

/**
 * Format days until expiration
 */
export function formatDays(expireAt: string | Date): string {
  const locale = resolveLocale()
  const expire = new Date(expireAt)
  const now = new Date()
  const diff = expire.getTime() - now.getTime()
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24))

  if (days < 0) {
    return translate('runtime.days.expiredAgo', { days: Math.abs(days) }, locale)
  } else if (days === 0) {
    return translate('runtime.days.expiresToday', undefined, locale)
  } else if (days === 1) {
    return translate('runtime.days.expiresTomorrow', undefined, locale)
  } else if (days < 30) {
    return translate('runtime.days.short', { days }, locale)
  } else if (days < 365) {
    const months = Math.floor(days / 30)
    const monthUnit =
      months === 1
        ? translate('runtime.days.month.one', undefined, locale)
        : translate('runtime.days.month.other', undefined, locale)
    return `${months} ${monthUnit}`
  } else {
    const years = Math.floor(days / 365)
    const yearUnit =
      years === 1
        ? translate('runtime.days.year.one', undefined, locale)
        : translate('runtime.days.year.other', undefined, locale)
    return `${years} ${yearUnit}`
  }
}

/**
 * Format price with currency
 */
export function formatPrice(amount: number, currency: string = 'USD'): string {
  const locale = resolveLocale()
  return new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount)
}

/**
 * Format date to relative time
 */
export function formatRelativeTime(date: string | Date): string {
  const locale = resolveLocale()
  const d = new Date(date)
  if (Number.isNaN(d.getTime())) {
    return '-'
  }

  const now = new Date()
  const diffSeconds = Math.round((d.getTime() - now.getTime()) / 1000)
  const absSeconds = Math.abs(diffSeconds)
  const rtf = new Intl.RelativeTimeFormat(locale === 'ru' ? 'ru-RU' : 'en-US', {
    numeric: 'auto',
    style: 'short',
  })

  if (absSeconds < 5) return translate('runtime.relative.justNow', undefined, locale)
  if (absSeconds < 60) return rtf.format(diffSeconds, 'second')

  const diffMinutes = Math.round(diffSeconds / 60)
  if (Math.abs(diffMinutes) < 60) return rtf.format(diffMinutes, 'minute')

  const diffHours = Math.round(diffMinutes / 60)
  if (Math.abs(diffHours) < 24) return rtf.format(diffHours, 'hour')

  const diffDays = Math.round(diffHours / 24)
  if (Math.abs(diffDays) < 7) return rtf.format(diffDays, 'day')
  
  return d.toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US')
}

/**
 * Format Telegram username to URL
 */
export function formatUsernameToUrl(username: string, text?: string): string {
  const cleanUsername = username.replace('@', '')
  const encodedText = text ? encodeURIComponent(text) : ''
  return `https://t.me/${cleanUsername}${encodedText ? `?text=${encodedText}` : ''}`
}

/**
 * Generate random string
 */
export function generateRandomString(length: number): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/**
 * Check if value is valid email
 */
export function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

/**
 * Check if value is valid URL
 */
export function isValidUrl(url: string): boolean {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null
      func(...args)
    }

    if (timeout) {
      clearTimeout(timeout)
    }
    timeout = setTimeout(later, wait)
  }
}

/**
 * Sleep for specified milliseconds
 */
export function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
