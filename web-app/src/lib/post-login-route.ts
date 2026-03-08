import { api } from '@/lib/api'
import { sendWebTelemetryEvent } from '@/lib/telemetry'

export type DeviceMode = 'telegram-mobile' | 'telegram-desktop' | 'web'

interface TelegramInitDataUnsafeLike {
  start_param?: string
  query_id?: string
  chat_type?: string
}

interface TelegramWebAppLike {
  initData?: string
  initDataUnsafe?: TelegramInitDataUnsafeLike
}

function toAppPathname(pathname: string): string {
  const basePath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  if (!basePath || basePath === '/') {
    return pathname || '/'
  }
  if (pathname.startsWith(basePath)) {
    const normalized = pathname.slice(basePath.length)
    return normalized.startsWith('/') ? normalized : `/${normalized}`
  }
  return pathname || '/'
}

function resolveCurrentSourcePath(): string {
  if (typeof window === 'undefined') {
    return '/auth/login'
  }
  return toAppPathname(window.location.pathname)
}

function resolveTelegramWebApp(): TelegramWebAppLike | undefined {
  if (typeof window === 'undefined') {
    return undefined
  }
  return window.Telegram?.WebApp as TelegramWebAppLike | undefined
}

export function resolveDefaultPostLoginPath(
  deviceMode: DeviceMode,
  preferMobileUiV2 = false
): string {
  if (deviceMode === 'telegram-mobile' || preferMobileUiV2) {
    return '/dashboard/subscription'
  }
  return '/dashboard'
}

export async function resolvePostLoginPathWithAccess(
  deviceMode: DeviceMode,
  preferMobileUiV2 = false
): Promise<string> {
  const sourcePath = resolveCurrentSourcePath()
  try {
    const { data } = await api.auth.getAccessStatus()
    if (data.access_level !== 'full') {
      const blockedPath = '/dashboard/settings?access_blocked=1'
      const telegramWebApp = resolveTelegramWebApp()
      sendWebTelemetryEvent({
        event_name: 'post_login_route_resolved',
        source_path: sourcePath,
        device_mode: deviceMode,
        is_in_telegram: deviceMode !== 'web',
        has_init_data: Boolean(telegramWebApp?.initData),
        start_param: telegramWebApp?.initDataUnsafe?.start_param || undefined,
        has_query_id: Boolean(telegramWebApp?.initDataUnsafe?.query_id),
        chat_type: telegramWebApp?.initDataUnsafe?.chat_type || undefined,
        meta: {
          next_path: blockedPath,
          access_blocked: true,
          access_level: data.access_level,
          channel_check_status: data.channel_check_status,
        },
      })
      return '/dashboard/settings?access_blocked=1'
    }
  } catch {
    // Keep a deterministic default route when access-status check fails.
  }

  const nextPath = resolveDefaultPostLoginPath(deviceMode, preferMobileUiV2)
  const telegramWebApp = resolveTelegramWebApp()
  sendWebTelemetryEvent({
    event_name: 'post_login_route_resolved',
    source_path: sourcePath,
    device_mode: deviceMode,
    is_in_telegram: deviceMode !== 'web',
    has_init_data: Boolean(telegramWebApp?.initData),
    start_param: telegramWebApp?.initDataUnsafe?.start_param || undefined,
    has_query_id: Boolean(telegramWebApp?.initDataUnsafe?.query_id),
    chat_type: telegramWebApp?.initDataUnsafe?.chat_type || undefined,
    meta: { next_path: nextPath, access_blocked: false },
  })
  return nextPath
}
