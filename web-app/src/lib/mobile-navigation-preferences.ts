const MOBILE_EXTRA_NAVIGATION_STORAGE_KEY = 'mobile_extra_navigation_enabled'
const MOBILE_EXTRA_NAVIGATION_CHANGE_EVENT = 'mobile_extra_navigation_changed'

function normalizeStoredValue(rawValue: string | null): boolean {
  return rawValue === '1' || rawValue === 'true'
}

export function readMobileExtraNavigationEnabled(): boolean {
  if (typeof window === 'undefined') {
    return false
  }

  try {
    return normalizeStoredValue(window.localStorage.getItem(MOBILE_EXTRA_NAVIGATION_STORAGE_KEY))
  } catch {
    return false
  }
}

export function writeMobileExtraNavigationEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') {
    return
  }

  try {
    window.localStorage.setItem(MOBILE_EXTRA_NAVIGATION_STORAGE_KEY, enabled ? '1' : '0')
  } catch {
    // Ignore storage write errors in restrictive environments.
  }

  window.dispatchEvent(new Event(MOBILE_EXTRA_NAVIGATION_CHANGE_EVENT))
}

export function subscribeMobileExtraNavigationPreference(listener: () => void): () => void {
  if (typeof window === 'undefined') {
    return () => {}
  }

  const handleStorage = (event: StorageEvent) => {
    if (event.key === MOBILE_EXTRA_NAVIGATION_STORAGE_KEY) {
      listener()
    }
  }

  const handleCustomChange = () => {
    listener()
  }

  window.addEventListener('storage', handleStorage)
  window.addEventListener(MOBILE_EXTRA_NAVIGATION_CHANGE_EVENT, handleCustomChange)

  return () => {
    window.removeEventListener('storage', handleStorage)
    window.removeEventListener(MOBILE_EXTRA_NAVIGATION_CHANGE_EVENT, handleCustomChange)
  }
}
