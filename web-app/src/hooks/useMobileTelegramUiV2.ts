import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'

function isLikelySmartphoneBrowser(isNarrowViewport: boolean): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return false
  }

  const userAgent = navigator.userAgent || ''
  const mobileUserAgentPattern = /Android.+Mobile|iPhone|iPod|Windows Phone|IEMobile|Opera Mini|BlackBerry|Mobile/i
  const isMobileUserAgent = mobileUserAgentPattern.test(userAgent)
  if (isMobileUserAgent) {
    return true
  }

  const hasTouch = (navigator.maxTouchPoints ?? 0) > 0
  const shortScreenSide = Math.min(window.screen.width, window.screen.height)
  const isPhoneSizedScreen = shortScreenSide <= 520

  return hasTouch && isPhoneSizedScreen && isNarrowViewport
}

export function useMobileTelegramUiV2(): boolean {
  const { isInTelegram, isTelegramMobile, isNarrowViewport } = useTelegramWebApp()
  if (isInTelegram) {
    return true
  }
  return isTelegramMobile || isLikelySmartphoneBrowser(isNarrowViewport)
}
