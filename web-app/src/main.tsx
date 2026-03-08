import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App.tsx'
import { AppErrorBoundary } from './components/common/AppErrorBoundary.tsx'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
const TELEGRAM_MIN_TOP_OFFSET_MOBILE_PX = 56

interface TelegramSafeAreaInset {
  top?: number
  bottom?: number
}

interface TelegramWebAppRuntime {
  themeParams?: Record<string, string | undefined>
  safeAreaInset?: TelegramSafeAreaInset
  contentSafeAreaInset?: TelegramSafeAreaInset
  platform?: string
  ready: () => void
  expand: () => void
  onEvent?: (eventType: string, eventHandler: () => void) => void
}

function toInsetCssValue(value: unknown, fallbackValue: string): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallbackValue
  }

  return `${Math.max(0, value)}px`
}

function getTelegramMinTopInset(platform: unknown): number {
  if (typeof platform !== 'string') {
    return 0
  }

  const normalizedPlatform = platform.toLowerCase()
  if (normalizedPlatform === 'android' || normalizedPlatform === 'ios') {
    return TELEGRAM_MIN_TOP_OFFSET_MOBILE_PX
  }

  return 0
}

function applyTelegramSafeAreaInsets(webApp: TelegramWebAppRuntime) {
  const root = document.documentElement
  const topInsetRaw = webApp.contentSafeAreaInset?.top ?? webApp.safeAreaInset?.top
  const bottomInset = webApp.contentSafeAreaInset?.bottom ?? webApp.safeAreaInset?.bottom
  const minTopInset = getTelegramMinTopInset(webApp.platform)
  const topInset = typeof topInsetRaw === 'number' && Number.isFinite(topInsetRaw)
    ? Math.max(minTopInset, Math.max(0, topInsetRaw))
    : minTopInset

  root.style.setProperty('--app-safe-top', `${topInset}px`)
  root.style.setProperty('--app-safe-bottom', toInsetCssValue(bottomInset, 'env(safe-area-inset-bottom, 0px)'))
}

function applyTelegramThemeParams(webApp: TelegramWebAppRuntime) {
  const themeParams = webApp.themeParams
  if (!themeParams) {
    return
  }

  const root = document.documentElement
  root.style.setProperty('--tg-theme-bg-color', themeParams.bg_color || '#ffffff')
  root.style.setProperty('--tg-theme-text-color', themeParams.text_color || '#000000')
  root.style.setProperty('--tg-theme-button-color', themeParams.button_color || '#3390ec')
  root.style.setProperty('--tg-theme-button-text-color', themeParams.button_text_color || '#ffffff')
  root.style.setProperty('--tg-theme-hint-color', themeParams.hint_color || '#999999')
  root.style.setProperty('--tg-theme-link-color', themeParams.link_color || '#3390ec')
  root.style.setProperty('--tg-theme-secondary-bg-color', themeParams.secondary_bg_color || '#f0f0f0')
}

// Initialize Telegram WebApp
function initTelegramWebApp() {
  const root = document.documentElement
  root.style.setProperty('--app-safe-top', 'env(safe-area-inset-top, 0px)')
  root.style.setProperty('--app-safe-bottom', 'env(safe-area-inset-bottom, 0px)')

  const initWebApp = () => {
    const webApp = window.Telegram?.WebApp as TelegramWebAppRuntime | undefined
    if (!webApp) {
      return
    }

    webApp.ready()
    webApp.expand()
    applyTelegramThemeParams(webApp)
    applyTelegramSafeAreaInsets(webApp)

    webApp.onEvent?.('viewportChanged', () => {
      applyTelegramSafeAreaInsets(webApp)
    })
  }

  if (window.Telegram?.WebApp) {
    initWebApp()
    return
  }

  const scriptSource = 'https://telegram.org/js/telegram-web-app.js'
  const existingScript = document.querySelector<HTMLScriptElement>(`script[src="${scriptSource}"]`)

  if (existingScript) {
    existingScript.addEventListener('load', initWebApp, { once: true })
    return
  }

  const script = document.createElement('script')
  script.src = scriptSource
  script.async = true
  script.onload = initWebApp
  document.head.appendChild(script)
}

// Initialize Telegram WebApp before rendering
initTelegramWebApp()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AppErrorBoundary>
        <App />
      </AppErrorBoundary>
    </QueryClientProvider>
  </React.StrictMode>,
)
