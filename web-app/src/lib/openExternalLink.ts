export function openExternalLink(rawUrl: string): boolean {
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
    const telegramOpenLink = window.Telegram?.WebApp?.openLink
    if (typeof telegramOpenLink === 'function') {
      telegramOpenLink(url, { try_instant_view: false })
      return true
    }
  } catch {
    return false
  }

  const opened = window.open(url, '_blank', 'noopener,noreferrer')
  return opened !== null
}
