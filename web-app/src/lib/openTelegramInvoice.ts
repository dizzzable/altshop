import { openExternalLink } from '@/lib/openExternalLink'

export type TelegramInvoiceStatus = 'paid' | 'cancelled' | 'failed' | 'pending' | string

export function openTelegramInvoice(
  rawUrl: string,
  onStatus?: (status: TelegramInvoiceStatus) => void
): boolean {
  const url = rawUrl.trim()
  if (!url) {
    return false
  }

  let parsedUrl: URL
  try {
    parsedUrl = new URL(url)
  } catch {
    return false
  }

  if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
    return false
  }

  try {
    const telegramOpenInvoice = window.Telegram?.WebApp?.openInvoice
    if (typeof telegramOpenInvoice === 'function') {
      telegramOpenInvoice(url, (status) => {
        onStatus?.(status)
      })
      return true
    }
  } catch {
    // Fall through to the generic link opener for older or partial WebApp bridges.
  }

  return openExternalLink(url)
}
