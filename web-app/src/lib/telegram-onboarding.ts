const TELEGRAM_MINIAPP_NEW_USER_ONBOARDING_KEY = 'tg_miniapp_new_user_onboarding_pending'

export function setPendingTelegramMiniAppOnboarding(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.setItem(TELEGRAM_MINIAPP_NEW_USER_ONBOARDING_KEY, '1')
}

export function hasPendingTelegramMiniAppOnboarding(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  return window.sessionStorage.getItem(TELEGRAM_MINIAPP_NEW_USER_ONBOARDING_KEY) === '1'
}

export function clearPendingTelegramMiniAppOnboarding(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.removeItem(TELEGRAM_MINIAPP_NEW_USER_ONBOARDING_KEY)
}
