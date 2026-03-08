import { useEffect, useState } from 'react'
import type { DeviceMode } from '@/lib/post-login-route'

const TELEGRAM_WEBAPP_POLL_INTERVAL_MS = 80
const TELEGRAM_WEBAPP_WAIT_TIMEOUT_MS = 1500
const TELEGRAM_WEBAPP_SOFT_RETRY_INTERVAL_MS = 1200
const TELEGRAM_WEBAPP_SOFT_RETRY_WINDOW_MS = 12000
const TELEGRAM_NARROW_VIEWPORT_MAX_WIDTH_PX = 820

// Telegram WebApp types
declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp
    }
  }
}

interface TelegramWebApp {
  initData: string
  initDataUnsafe: TelegramInitDataUnsafe
  version: string
  platform: string
  colorScheme: string
  themeParams: Record<string, string>
  isActive: boolean
  isExpanded: boolean
  viewportHeight: number
  viewportStableHeight: number
  headerColor: string
  backgroundColor: string
  bottomBarColor: string
  isFullscreen: boolean
  safeAreaInset: {
    top: number
    bottom: number
    left: number
    right: number
  }
  contentSafeAreaInset: {
    top: number
    bottom: number
    left: number
    right: number
  }
  
  // Methods
  ready(): void
  expand(): void
  close(): void
  showPopup(params: Record<string, unknown>, callback?: (buttonId: string) => void): void
  showAlert(message: string, callback?: () => void): void
  showConfirm(message: string, callback?: (confirmed: boolean) => void): void
  openLink?(url: string, options?: Record<string, unknown>): void
  MainButton: MainButton
  BackButton: BackButton
  HapticFeedback: HapticFeedback
  CloudStorage: CloudStorage
  
  // Events
  onEvent(eventType: string, eventHandler: () => void): void
  offEvent(eventType: string, eventHandler: () => void): void
  
  // Version check
  isVersionAtLeast(version: string): boolean
  
  // Colors
  setHeaderColor(color: string): void
  setBackgroundColor(color: string): void
  setBottomBarColor(color: string): void
}

interface MainButton {
  text: string
  color: string
  textColor: string
  isVisible: boolean
  isActive: boolean
  isProgressVisible: boolean
  
  setText(text: string): void
  show(): void
  hide(): void
  enable(): void
  disable(): void
  showProgress(leaveActive?: boolean): void
  hideProgress(): void
  setParams(params: Record<string, unknown>): void
  onClick(callback: () => void): void
  offClick(callback: () => void): void
}

interface BackButton {
  isVisible: boolean
  
  show(): void
  hide(): void
  onClick(callback: () => void): void
  offClick(callback: () => void): void
}

interface HapticFeedback {
  impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void
  notificationOccurred(style: 'success' | 'error' | 'warning'): void
  selectionChanged(): void
}

interface CloudStorage {
  setItem(key: string, value: string, callback?: (err: string | null, stored: boolean) => void): void
  getItem(key: string, callback?: (err: string | null, value: string | null) => void): void
  getItems(keys: string[], callback?: (err: string | null, values: (string | null)[]) => void): void
  removeItem(key: string, callback?: (err: string | null, removed: boolean) => void): void
  removeItems(keys: string[], callback?: (err: string | null, removed: boolean) => void): void
  getKeys(callback?: (err: string | null, keys: string[]) => void): void
}

interface TelegramInitDataUnsafe {
  user?: TelegramUser
  query_id?: string
  start_param?: string
  auth_date?: number
  hash?: string
  chat_type?: string
  chat_instance?: string
}

interface TelegramUser {
  id: number
  first_name: string
  last_name?: string
  username?: string
  photo_url?: string
  language_code?: string
  is_premium?: boolean
}

interface TelegramLaunchContext {
  startParam: string | null
  hasQueryId: boolean
  chatType: string | null
  authDate: number | null
}

interface UseTelegramWebAppResult {
  tg: TelegramWebApp | null
  user: TelegramUser | null
  queryId: string | null
  initData: string | null
  launchContext: TelegramLaunchContext
  isInTelegram: boolean
  platform: string
  isTelegramMobile: boolean
  isTelegramDesktop: boolean
  isNarrowViewport: boolean
  deviceMode: DeviceMode
  isReady: boolean
  expand: () => void
  ready: () => void
  close: () => void
  theme: Record<string, string>
}

function readIsNarrowViewport(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  if (typeof window.matchMedia === 'function') {
    return window.matchMedia(`(max-width: ${TELEGRAM_NARROW_VIEWPORT_MAX_WIDTH_PX}px)`).matches
  }
  return window.innerWidth <= TELEGRAM_NARROW_VIEWPORT_MAX_WIDTH_PX
}

/**
 * Hook for working with Telegram WebApp
 * Provides safe access to Telegram WebApp API with fallbacks for browser testing
 */
export function useTelegramWebApp(): UseTelegramWebAppResult {
  const [tg, setTg] = useState<TelegramWebApp | null>(null)
  const [user, setUser] = useState<TelegramUser | null>(null)
  const [queryId, setQueryId] = useState<string | null>(null)
  const [initData, setInitData] = useState<string | null>(null)
  const [launchContext, setLaunchContext] = useState<TelegramLaunchContext>({
    startParam: null,
    hasQueryId: false,
    chatType: null,
    authDate: null,
  })
  const [isInTelegram, setIsInTelegram] = useState(false)
  const [platform, setPlatform] = useState<string>('unknown')
  const [isNarrowViewport, setIsNarrowViewport] = useState<boolean>(() => readIsNarrowViewport())
  const [isReady, setIsReady] = useState(false)
  const [theme, setTheme] = useState<Record<string, string>>({})

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    const mediaQuery = window.matchMedia?.(`(max-width: ${TELEGRAM_NARROW_VIEWPORT_MAX_WIDTH_PX}px)`) ?? null
    const applyViewportState = () => {
      setIsNarrowViewport(readIsNarrowViewport())
    }

    applyViewportState()

    if (mediaQuery && typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', applyViewportState)
      window.addEventListener('resize', applyViewportState, { passive: true })
      return () => {
        mediaQuery.removeEventListener('change', applyViewportState)
        window.removeEventListener('resize', applyViewportState)
      }
    }

    window.addEventListener('resize', applyViewportState, { passive: true })
    return () => {
      window.removeEventListener('resize', applyViewportState)
    }
  }, [])

  useEffect(() => {
    let disposed = false
    let initialized = false
    let prewarmedTelegram = false
    let activeTelegram: TelegramWebApp | null = null
    let themeChangeHandler: (() => void) | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let timeoutTimer: ReturnType<typeof setTimeout> | null = null
    let softRetryTimer: ReturnType<typeof setInterval> | null = null

    const cleanupTimers = () => {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
      if (timeoutTimer) {
        clearTimeout(timeoutTimer)
        timeoutTimer = null
      }
      if (softRetryTimer) {
        clearInterval(softRetryTimer)
        softRetryTimer = null
      }
    }

    const applyTelegramState = (telegram: TelegramWebApp): void => {
      const rawInitData = telegram.initData || ''
      const unsafeData = telegram.initDataUnsafe || {}
      const hasSignedInitData = rawInitData.trim().length > 0

      setTg(telegram)
      setUser((unsafeData.user as TelegramUser | undefined) ?? null)
      setQueryId(unsafeData.query_id ?? null)
      setInitData(hasSignedInitData ? rawInitData : null)
      setLaunchContext({
        startParam: unsafeData.start_param ?? null,
        hasQueryId: Boolean(unsafeData.query_id),
        chatType: unsafeData.chat_type ?? null,
        authDate: unsafeData.auth_date ?? null,
      })
      setPlatform(telegram.platform || 'unknown')
      setIsInTelegram(hasSignedInitData)
      setTheme(telegram.themeParams || {})

      telegram.ready()
      telegram.expand()

      themeChangeHandler = () => {
        if (!disposed) {
          setTheme(telegram.themeParams || {})
        }
      }
      telegram.onEvent('themeChanged', themeChangeHandler)
      setIsReady(true)
    }

    const tryInit = (): boolean => {
      const telegram = window.Telegram?.WebApp
      if (!telegram || disposed || initialized) {
        return false
      }

      const hasSignedInitData = (telegram.initData || '').trim().length > 0
      if (!hasSignedInitData) {
        if (!prewarmedTelegram) {
          prewarmedTelegram = true
          try {
            telegram.ready()
            telegram.expand()
          } catch {
            // Ignore transient WebApp bridge errors; polling will retry.
          }
        }
        return false
      }

      initialized = true
      activeTelegram = telegram
      cleanupTimers()
      applyTelegramState(telegram)
      return true
    }

    if (tryInit()) {
      return () => {
        disposed = true
        cleanupTimers()
        if (activeTelegram && themeChangeHandler) {
          activeTelegram.offEvent('themeChanged', themeChangeHandler)
        }
      }
    }

    pollTimer = setInterval(() => {
      tryInit()
    }, TELEGRAM_WEBAPP_POLL_INTERVAL_MS)

    timeoutTimer = setTimeout(() => {
      cleanupTimers()
      if (initialized || disposed) {
        return
      }

      setTg(null)
      setUser(null)
      setQueryId(null)
      setInitData(null)
      setLaunchContext({
        startParam: null,
        hasQueryId: false,
        chatType: null,
        authDate: null,
      })
      setIsInTelegram(false)
      setPlatform('browser')
      setTheme({})
      setIsReady(true)

      const softRetryStartedAt = Date.now()
      softRetryTimer = setInterval(() => {
        if (disposed || initialized) {
          cleanupTimers()
          return
        }

        if (Date.now() - softRetryStartedAt >= TELEGRAM_WEBAPP_SOFT_RETRY_WINDOW_MS) {
          if (softRetryTimer) {
            clearInterval(softRetryTimer)
            softRetryTimer = null
          }
          return
        }

        const telegram = window.Telegram?.WebApp
        if (!telegram) {
          return
        }

        const hasSignedInitData = (telegram.initData || '').trim().length > 0
        if (!hasSignedInitData) {
          return
        }

        initialized = true
        activeTelegram = telegram
        cleanupTimers()
        applyTelegramState(telegram)
      }, TELEGRAM_WEBAPP_SOFT_RETRY_INTERVAL_MS)
    }, TELEGRAM_WEBAPP_WAIT_TIMEOUT_MS)

    return () => {
      disposed = true
      cleanupTimers()
      if (activeTelegram && themeChangeHandler) {
        activeTelegram.offEvent('themeChanged', themeChangeHandler)
      }
    }
  }, [])

  const expand = () => {
    tg?.expand()
  }

  const ready = () => {
    tg?.ready()
  }

  const close = () => {
    tg?.close()
  }

  const normalizedPlatform = platform.toLowerCase()
  const isMobilePlatform = normalizedPlatform === 'ios' || normalizedPlatform === 'android'
  const isDesktopPlatform = normalizedPlatform === 'tdesktop' || normalizedPlatform === 'macos'
  const isWebPlatform =
    normalizedPlatform === 'web'
    || normalizedPlatform === 'weba'
    || normalizedPlatform === 'webk'
    || normalizedPlatform === 'webz'
    || normalizedPlatform === 'browser'
  const useNarrowViewportFallback = isInTelegram && !isDesktopPlatform && !isWebPlatform && isNarrowViewport
  const isTelegramMobile = isInTelegram && (isMobilePlatform || useNarrowViewportFallback)
  const isTelegramDesktop = isInTelegram && !isTelegramMobile
  const deviceMode: DeviceMode = isTelegramMobile
    ? 'telegram-mobile'
    : isTelegramDesktop
      ? 'telegram-desktop'
      : 'web'

  return {
    tg,
    user,
    queryId,
    initData,
    launchContext,
    isInTelegram,
    platform,
    isTelegramMobile,
    isTelegramDesktop,
    isNarrowViewport,
    deviceMode,
    isReady,
    expand,
    ready,
    close,
    theme,
  }
}

/**
 * Get auth data for sending to backend
 * Works both in Telegram and browser (for testing)
 */
function _getAuthData(): {
  initData?: string
  user?: TelegramUser
  queryId?: string
  startParam?: string
  chatType?: string
  isTest?: boolean
} | null {
  const telegram = window.Telegram?.WebApp
  
  if (!telegram?.initData) {
    // For browser testing - return mock data
    const testUser = {
      id: 123456789,
      first_name: 'Test',
      username: 'testuser',
    }
    return {
      user: testUser,
      isTest: true,
    }
  }

  return {
    initData: telegram.initData,
    user: telegram.initDataUnsafe?.user as TelegramUser | undefined,
    queryId: telegram.initDataUnsafe?.query_id,
    startParam: telegram.initDataUnsafe?.start_param,
    chatType: telegram.initDataUnsafe?.chat_type,
  }
}
