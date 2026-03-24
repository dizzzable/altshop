import { withAppBase } from '@/lib/app-path'

export type PaymentReturnStatus = 'success' | 'failed'
export type PaymentReturnTarget = 'web' | 'telegram'

const TELEGRAM_PAYMENT_START_PARAMS: Record<PaymentReturnStatus, string> = {
  success: 'payment-success',
  failed: 'payment-failed',
}

const PENDING_PAYMENT_RETURN_STATUS_KEY = 'pending_payment_return_status'

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

export function resolveTelegramPaymentReturnUrl(status: PaymentReturnStatus): string {
  const botUsername = resolveTelegramBotUsername()
  if (!botUsername) {
    return buildAbsoluteAppUrl('/miniapp?tg_open=1')
  }

  const startParam = TELEGRAM_PAYMENT_START_PARAMS[status]
  return `https://t.me/${botUsername}?startapp=${startParam}`
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
