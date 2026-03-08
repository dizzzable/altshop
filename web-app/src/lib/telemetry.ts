export type WebTelemetryEventName =
  | 'miniapp_landing_view'
  | 'miniapp_open_panel_click'
  | 'miniapp_open_panel_blocked_non_telegram'
  | 'miniapp_credentials_bootstrap_shown'
  | 'miniapp_credentials_bootstrap_completed'
  | 'miniapp_credentials_bootstrap_rejected'
  | 'web_landing_view_in_telegram'
  | 'web_landing_miniapp_cta_click'
  | 'telegram_auth_attempt'
  | 'telegram_auth_success'
  | 'telegram_auth_failed'
  | 'post_login_route_resolved'
  | 'auth_refresh_singleflight_waiter'

export type WebTelemetryDeviceMode = 'telegram-mobile' | 'telegram-desktop' | 'web'

export interface WebTelemetryEventPayload {
  event_name: WebTelemetryEventName
  source_path: string
  session_id?: string
  device_mode: WebTelemetryDeviceMode
  is_in_telegram: boolean
  has_init_data: boolean
  start_param?: string
  has_query_id?: boolean
  chat_type?: string
  meta?: Record<string, unknown>
}

const TELEMETRY_ENDPOINT = '/api/v1/analytics/web-events'
const TELEMETRY_SESSION_KEY = 'web_telemetry_session_id'

function createFallbackUuid(): string {
  const template = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'
  return template.replace(/[xy]/g, (char) => {
    const random = Math.floor(Math.random() * 16)
    const value = char === 'x' ? random : (random & 0x3) | 0x8
    return value.toString(16)
  })
}

function createSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return createFallbackUuid()
}

export function getOrCreateTelemetrySessionId(): string {
  try {
    const existing = window.localStorage.getItem(TELEMETRY_SESSION_KEY)
    if (existing && existing.trim()) {
      return existing
    }

    const next = createSessionId()
    window.localStorage.setItem(TELEMETRY_SESSION_KEY, next)
    return next
  } catch {
    return createSessionId()
  }
}

function sendByBeacon(payload: Omit<WebTelemetryEventPayload, 'session_id'> & { session_id: string }): boolean {
  if (typeof navigator === 'undefined' || typeof navigator.sendBeacon !== 'function') {
    return false
  }

  try {
    const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' })
    return navigator.sendBeacon(TELEMETRY_ENDPOINT, blob)
  } catch {
    return false
  }
}

async function sendByFetch(
  payload: Omit<WebTelemetryEventPayload, 'session_id'> & { session_id: string }
): Promise<void> {
  if (typeof fetch !== 'function') {
    return
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  try {
    await fetch(TELEMETRY_ENDPOINT, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      keepalive: true,
      credentials: 'include',
    })
  } catch {
    // Best-effort telemetry; ignore network errors.
  }
}

export function sendWebTelemetryEvent(payload: WebTelemetryEventPayload): void {
  if (typeof window === 'undefined') {
    return
  }

  const normalizedPayload = {
    ...payload,
    session_id: payload.session_id || getOrCreateTelemetrySessionId(),
    has_query_id: payload.has_query_id ?? false,
    meta: payload.meta ?? {},
  }

  if (sendByBeacon(normalizedPayload)) {
    return
  }

  void sendByFetch(normalizedPayload)
}
