export function openTelegramDeepLinkWithFallback(
  deepLink: string | null | undefined,
  fallbackUrl: string | null | undefined,
  fallbackDelayMs = 1200
): boolean {
  const normalizedFallback = (fallbackUrl ?? '').trim()
  const normalizedDeepLink = (deepLink ?? '').trim()

  if (!normalizedDeepLink && !normalizedFallback) {
    return false
  }

  const targetUrl = normalizedDeepLink || normalizedFallback
  if (!targetUrl) {
    return false
  }

  if (typeof window === 'undefined') {
    return false
  }

  let hidden = false
  const markHidden = () => {
    hidden = document.visibilityState === 'hidden'
  }

  document.addEventListener('visibilitychange', markHidden, { once: true })
  window.addEventListener('pagehide', markHidden, { once: true })
  window.addEventListener('blur', markHidden, { once: true })

  if (normalizedDeepLink) {
    window.location.href = normalizedDeepLink
  } else {
    window.location.href = normalizedFallback
    return true
  }

  if (normalizedFallback) {
    window.setTimeout(() => {
      if (!hidden) {
        window.location.href = normalizedFallback
      }
    }, fallbackDelayMs)
  }

  return true
}
