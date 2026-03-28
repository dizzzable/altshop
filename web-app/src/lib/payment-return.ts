import { withAppBase } from '@/lib/app-path'

export type PaymentReturnStatus = 'success' | 'failed'
export type PaymentReturnTarget = 'web' | 'telegram'
export const PAYMENT_RETURN_STATUS_QUERY_KEY = 'payment_return_status'

const TELEGRAM_PAYMENT_START_PARAMS: Record<PaymentReturnStatus, string> = {
  success: 'payment-success',
  failed: 'payment-failed',
}

const PENDING_PAYMENT_RETURN_STATUS_KEY = 'pending_payment_return_status'
const TELEGRAM_HOSTS = new Set(['t.me', 'www.t.me', 'telegram.me', 'www.telegram.me'])

function resolveTelegramBotUsername(): string | null {
  const rawUsername = (import.meta.env.VITE_TELEGRAM_BOT_USERNAME || '').trim().replace(/^@/, '')
  return rawUsername || null
}

export function resolvePaymentRedirectPath(status: PaymentReturnStatus): string {
  return status === 'success'
    ? '/dashboard/subscription?payment=success'
    : '/dashboard/subscription/purchase?payment=failed'
}

export function buildAbsoluteAppUrl(path: string): string {
  if (typeof window === 'undefined') {
    return withAppBase(path)
  }

  return new URL(withAppBase(path), window.location.origin).toString()
}

export function buildExternalPaymentReturnUrl(
  status: PaymentReturnStatus,
  target: PaymentReturnTarget
): string {
  const params = new URLSearchParams({
    status,
    target,
  })
  return buildAbsoluteAppUrl(`/payment-return?${params.toString()}`)
}

function applyPaymentReturnPayload(url: string, status: PaymentReturnStatus): string | null {
  try {
    const resolved = new URL(url)
    if (TELEGRAM_HOSTS.has(resolved.hostname.toLowerCase())) {
      resolved.searchParams.set('startapp', TELEGRAM_PAYMENT_START_PARAMS[status])
      return resolved.toString()
    }

    resolved.searchParams.set(PAYMENT_RETURN_STATUS_QUERY_KEY, status)
    if (resolved.pathname.replace(/\/+$/, '').endsWith('/miniapp')) {
      resolved.searchParams.set('tg_open', '1')
    }
    return resolved.toString()
  } catch {
    return null
  }
}

export function resolveTelegramPaymentReturnUrl(
  status: PaymentReturnStatus,
  options: {
    miniAppLaunchUrl?: string | null
    telegramBotLink?: string | null
    miniAppUrl?: string | null
  } = {}
): string {
  const resolvedMiniAppLaunchUrl = applyPaymentReturnPayload(
    options.miniAppLaunchUrl?.trim() || '',
    status
  )
  if (resolvedMiniAppLaunchUrl) {
    return resolvedMiniAppLaunchUrl
  }

  const resolvedTelegramBotLink = applyPaymentReturnPayload(
    options.telegramBotLink?.trim() || '',
    status
  )
  if (resolvedTelegramBotLink) {
    return resolvedTelegramBotLink
  }

  const resolvedMiniAppUrl = applyPaymentReturnPayload(options.miniAppUrl?.trim() || '', status)
  if (resolvedMiniAppUrl) {
    return resolvedMiniAppUrl
  }

  const botUsername = resolveTelegramBotUsername()
  if (botUsername) {
    const startParam = TELEGRAM_PAYMENT_START_PARAMS[status]
    return `https://t.me/${botUsername}?startapp=${startParam}`
  }

  const fallbackParams = new URLSearchParams({
    tg_open: '1',
    [PAYMENT_RETURN_STATUS_QUERY_KEY]: status,
  })
  return buildAbsoluteAppUrl(`/miniapp?${fallbackParams.toString()}`)
}

export function resolvePaymentReturnStatusFromTelegramStartParam(
  startParam: string | null | undefined
): PaymentReturnStatus | null {
  if (!startParam) {
    return null
  }

  const normalizedStartParam = startParam.trim().toLowerCase()
  if (normalizedStartParam === TELEGRAM_PAYMENT_START_PARAMS.success) {
    return 'success'
  }
  if (normalizedStartParam === TELEGRAM_PAYMENT_START_PARAMS.failed) {
    return 'failed'
  }

  return null
}

export function resolvePaymentReturnStatusFromQueryParam(
  search: string | URLSearchParams | null | undefined
): PaymentReturnStatus | null {
  if (!search) {
    return null
  }

  const searchParams =
    search instanceof URLSearchParams
      ? search
      : new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
  const rawStatus = searchParams.get(PAYMENT_RETURN_STATUS_QUERY_KEY)
  if (rawStatus === 'success') {
    return 'success'
  }
  if (rawStatus === 'failed') {
    return 'failed'
  }
  return null
}

export function persistPendingPaymentReturnStatus(status: PaymentReturnStatus): void {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.sessionStorage.setItem(PENDING_PAYMENT_RETURN_STATUS_KEY, status)
  } catch {
    // Ignore storage failures in restrictive/private environments.
  }
}

export function consumePendingPaymentReturnStatus(): PaymentReturnStatus | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const rawStatus = window.sessionStorage.getItem(PENDING_PAYMENT_RETURN_STATUS_KEY)
    if (!rawStatus) {
      return null
    }

    window.sessionStorage.removeItem(PENDING_PAYMENT_RETURN_STATUS_KEY)
    return rawStatus === 'failed' ? 'failed' : 'success'
  } catch {
    return null
  }
}
