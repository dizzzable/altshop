const TELEGRAM_MINIAPP_NEW_USER_ONBOARDING_KEY = 'tg_miniapp_new_user_onboarding_pending'
const TRIAL_ONBOARDING_KEY = 'trial_onboarding_pending'

export function setPendingTrialOnboarding(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.setItem(TRIAL_ONBOARDING_KEY, '1')
}

export function hasPendingTrialOnboarding(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  return (
    window.sessionStorage.getItem(TRIAL_ONBOARDING_KEY) === '1' ||
    window.sessionStorage.getItem(TELEGRAM_MINIAPP_NEW_USER_ONBOARDING_KEY) === '1'
  )
}

export function clearPendingTrialOnboarding(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.removeItem(TRIAL_ONBOARDING_KEY)
  window.sessionStorage.removeItem(TELEGRAM_MINIAPP_NEW_USER_ONBOARDING_KEY)
}

export function setPendingTelegramMiniAppOnboarding(): void {
  setPendingTrialOnboarding()
}

export function hasPendingTelegramMiniAppOnboarding(): boolean {
  return hasPendingTrialOnboarding()
}

export function clearPendingTelegramMiniAppOnboarding(): void {
  clearPendingTrialOnboarding()
}
