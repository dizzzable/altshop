import axios, { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { withAppBase } from '@/lib/app-path'
import { getRuntimeWebLocale } from '@/lib/locale'
import { sendWebTelemetryEvent } from '@/lib/telemetry'
import type {
  AccessUnmetRequirementCode,
  AccessStatus,
  DeviceListResponse,
  DeviceType,
  GenericMessageResponse,
  PartnerEarningsListResponse,
  PartnerInfo,
  PasswordChangeResponse,
  PartnerReferralsListResponse,
  PartnerWithdrawalsListResponse,
  Plan,
  PromocodeActivateResult,
  PromocodeActivationHistoryResponse,
  PurchaseChannel,
  PurchaseType,
  PurchaseQuoteResponse,
  PurchaseResponse,
  ReferralExchangeExecuteRequest,
  ReferralExchangeExecuteResponse,
  ReferralExchangeOptions,
  RegistrationAccessRequirements,
  ReferralInfo,
  ReferralListResponse,
  SubscriptionPurchaseRequest,
  SubscriptionPurchaseOptionsResponse,
  Subscription,
  SubscriptionListResponse,
  TransactionHistoryResponse,
  UserNotificationListResponse,
  UnreadCountResponse,
  MarkReadResponse,
  AuthSessionResponse,
  TelegramLinkConfirmResponse,
  TelegramLinkRequestResponse,
  TelegramLinkStatusResponse,
  TrialEligibilityResponse,
  User,
  WebAccessBlockedErrorDetail,
  WebBrandingResponse,
} from '@/types'

const BASE_URL = '/api/v1'

const LEGACY_ACCESS_TOKEN_KEY = 'access_token'
const LEGACY_REFRESH_TOKEN_KEY = 'refresh_token'
const CSRF_TOKEN_COOKIE_NAME = 'altshop_csrf_token'
export const WEB_ACCESS_REQUIREMENTS_NOT_MET = 'WEB_ACCESS_REQUIREMENTS_NOT_MET'
export const WEB_ACCESS_READ_ONLY = 'WEB_ACCESS_READ_ONLY'
const WEB_ACCESS_UNMET_CODES: AccessUnmetRequirementCode[] = [
  'RULES_ACCEPTANCE_REQUIRED',
  'TELEGRAM_LINK_REQUIRED',
  'CHANNEL_SUBSCRIPTION_REQUIRED',
  'CHANNEL_VERIFICATION_UNAVAILABLE',
]

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

interface SubscriptionAssignmentRequest {
  plan_id?: number | null
  device_type?: DeviceType | null
}

function clearLegacyAuthStorage(): void {
  if (typeof window === 'undefined') {
    return
  }

  localStorage.removeItem(LEGACY_ACCESS_TOKEN_KEY)
  localStorage.removeItem(LEGACY_REFRESH_TOKEN_KEY)
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') {
    return null
  }

  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = document.cookie.match(new RegExp(`(?:^|; )${escapedName}=([^;]*)`))
  if (!match) {
    return null
  }

  try {
    return decodeURIComponent(match[1])
  } catch {
    return match[1]
  }
}

function getCsrfToken(): string | null {
  return readCookie(CSRF_TOKEN_COOKIE_NAME)
}

function isUnsafeMethod(method: string | undefined): boolean {
  const normalizedMethod = String(method || 'GET').toUpperCase()
  return !['GET', 'HEAD', 'OPTIONS'].includes(normalizedMethod)
}

function shouldAttemptSessionRefresh(url: string | undefined): boolean {
  const normalizedUrl = String(url || '')
  if (!normalizedUrl.startsWith('/auth/')) {
    return true
  }

  return ![
    '/auth/login',
    '/auth/register',
    '/auth/telegram',
    '/auth/refresh',
    '/auth/password/forgot',
    '/auth/password/forgot/telegram',
    '/auth/password/reset/by-link',
    '/auth/password/reset/by-code',
    '/auth/password/reset/by-telegram-code',
  ].some((path) => normalizedUrl.startsWith(path))
}

function isAccessUnmetRequirementCode(value: string): value is AccessUnmetRequirementCode {
  return WEB_ACCESS_UNMET_CODES.includes(value as AccessUnmetRequirementCode)
}

function parseWebAccessBlockedDetail(value: unknown): WebAccessBlockedErrorDetail | null {
  if (!value || typeof value !== 'object') {
    return null
  }

  const detail = value as { code?: unknown; message?: unknown; unmet_requirements?: unknown }
  if (typeof detail.code !== 'string') {
    return null
  }

  return {
    code: detail.code,
    message: typeof detail.message === 'string' ? detail.message : undefined,
    unmet_requirements: Array.isArray(detail.unmet_requirements)
      ? detail.unmet_requirements.filter(
        (item): item is AccessUnmetRequirementCode =>
          typeof item === 'string' && isAccessUnmetRequirementCode(item)
      )
      : undefined,
  }
}

function getWebAccessBlockedDetail(error: AxiosError): WebAccessBlockedErrorDetail | null {
  const payload = error.response?.data as { detail?: unknown } | undefined
  const detail = parseWebAccessBlockedDetail(payload?.detail)
  if (
    !detail
    || (detail.code !== WEB_ACCESS_REQUIREMENTS_NOT_MET && detail.code !== WEB_ACCESS_READ_ONLY)
  ) {
    return null
  }
  return detail
}

function redirectToSettingsWithAccessNotice(): void {
  if (typeof window === 'undefined') {
    return
  }

  const settingsPath = withAppBase('/dashboard/settings')
  const currentPath = window.location.pathname
  if (currentPath === settingsPath) {
    return
  }

  window.location.href = withAppBase('/dashboard/settings?access_blocked=1')
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

function getCurrentAppPathname(): string | null {
  if (typeof window === 'undefined') {
    return null
  }
  return toAppPathname(window.location.pathname)
}

function isPublicAuthSurface(pathname: string | null): boolean {
  if (!pathname) {
    return false
  }

  return [
    '/',
    '/miniapp',
    '/auth/login',
    '/auth/register',
    '/auth/forgot-password',
    '/auth/reset-password',
    '/auth/telegram/callback',
  ].includes(pathname)
}

let refreshRequestPromise: Promise<AuthSessionResponse> | null = null
let currentUserRequestPromise: Promise<AxiosResponse<User>> | null = null

function getTelemetryDeviceMode(): 'telegram-mobile' | 'telegram-desktop' | 'web' {
  if (typeof window === 'undefined') {
    return 'web'
  }

  const telegramWebApp = window.Telegram?.WebApp
  if (!telegramWebApp?.initData) {
    return 'web'
  }

  const platform = String(telegramWebApp.platform || '').trim().toLowerCase()
  return platform === 'ios' || platform === 'android' ? 'telegram-mobile' : 'telegram-desktop'
}

function trackRefreshWaiter(): void {
  if (typeof window === 'undefined') {
    return
  }

  const telegramWebApp = window.Telegram?.WebApp
  sendWebTelemetryEvent({
    event_name: 'auth_refresh_singleflight_waiter',
    source_path: `${window.location.pathname}${window.location.search}`,
    device_mode: getTelemetryDeviceMode(),
    is_in_telegram: Boolean(telegramWebApp?.initData),
    has_init_data: Boolean(telegramWebApp?.initData),
    start_param: telegramWebApp?.initDataUnsafe?.start_param || undefined,
    has_query_id: Boolean(telegramWebApp?.initDataUnsafe?.query_id),
    chat_type: telegramWebApp?.initDataUnsafe?.chat_type || undefined,
    meta: {
      transport: 'cookie_refresh_mutex',
    },
  })
}

async function refreshSession(): Promise<AuthSessionResponse> {
  if (refreshRequestPromise) {
    trackRefreshWaiter()
    return refreshRequestPromise
  }

  const csrfToken = getCsrfToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Web-Locale': getRuntimeWebLocale(),
  }
  if (csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  refreshRequestPromise = axios
    .post<AuthSessionResponse>(
      `${BASE_URL}/auth/refresh`,
      {},
      {
        withCredentials: true,
        headers,
      }
    )
    .then((response) => {
      clearLegacyAuthStorage()
      return response.data
    })
    .finally(() => {
      refreshRequestPromise = null
    })

  return refreshRequestPromise
}

function getCurrentUserProfile(): Promise<AxiosResponse<User>> {
  if (currentUserRequestPromise) {
    return currentUserRequestPromise
  }

  currentUserRequestPromise = apiClient.get<User>('/user/me')
    .finally(() => {
      currentUserRequestPromise = null
    })

  return currentUserRequestPromise
}

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    config.headers['X-Web-Locale'] = getRuntimeWebLocale()
    if (isUnsafeMethod(config.method)) {
      const csrfToken = getCsrfToken()
      if (csrfToken) {
        config.headers['X-CSRF-Token'] = csrfToken
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 403 && getWebAccessBlockedDetail(error)) {
      redirectToSettingsWithAccessNotice()
    }

    if (
      error.response?.status === 401
      && originalRequest
      && !originalRequest._retry
      && shouldAttemptSessionRefresh(originalRequest.url)
    ) {
      originalRequest._retry = true

      try {
        await refreshSession()
        return apiClient(originalRequest)
      } catch (refreshError) {
        clearLegacyAuthStorage()
        if (typeof window !== 'undefined' && !isPublicAuthSurface(getCurrentAppPathname())) {
          window.location.href = withAppBase('/auth/login')
        }
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export const api = {
  auth: {
    login: (data: { username: string; password: string }) =>
      apiClient.post<AuthSessionResponse>('/auth/login', data),
    webAccountBootstrap: (data: { username: string; password: string }) =>
      apiClient.post<AuthSessionResponse>('/auth/web-account/bootstrap', data),
    register: (data: {
      telegram_id?: number
      username: string
      password: string
      referral_code?: string
      name?: string
      accept_rules?: boolean
      accept_channel_subscription?: boolean
    }) =>
      apiClient.post<AuthSessionResponse>('/auth/register', data),
    telegram: (data: {
      initData?: string
      queryId?: string
      id?: number
      first_name?: string
      last_name?: string
      username?: string
      photo_url?: string
      auth_date?: number
      hash?: string
      isTest?: boolean
      referralCode?: string
    }) => apiClient.post<AuthSessionResponse>('/auth/telegram', data),
    refresh: () => apiClient.post<AuthSessionResponse>('/auth/refresh', {}),
    logout: () => apiClient.post('/auth/logout'),
    me: () => apiClient.get<User>('/auth/me'),
    getBranding: () => apiClient.get<WebBrandingResponse>('/auth/branding'),
    getRegistrationAccessRequirements: () =>
      apiClient.get<RegistrationAccessRequirements>('/auth/registration/access-requirements'),
    getAccessStatus: (forceChannelRecheck = false) =>
      apiClient.get<AccessStatus>('/auth/access-status', {
        params: forceChannelRecheck ? { force_channel_recheck: true } : undefined,
      }),
    acceptAccessRules: () =>
      apiClient.post<AccessStatus>('/auth/access/rules/accept'),
    requestTelegramLinkCode: (data: { telegram_id: number }) =>
      apiClient.post<TelegramLinkRequestResponse>('/auth/telegram-link/request', data),
    confirmTelegramLinkCode: (data: { telegram_id: number; code: string }) =>
      apiClient.post<TelegramLinkConfirmResponse>('/auth/telegram-link/confirm', data),
    remindTelegramLinkLater: () =>
      apiClient.post<TelegramLinkStatusResponse>('/auth/telegram-link/remind-later'),
    requestEmailVerify: () =>
      apiClient.post<GenericMessageResponse>('/auth/email/verify/request'),
    confirmEmailVerify: (data: { code?: string; token?: string }) =>
      apiClient.post<GenericMessageResponse>('/auth/email/verify/confirm', data),
    forgotPassword: (data: { username?: string; email?: string }) =>
      apiClient.post<GenericMessageResponse>('/auth/password/forgot', data),
    forgotPasswordByTelegram: (data: { username: string }) =>
      apiClient.post<GenericMessageResponse>('/auth/password/forgot/telegram', data),
    resetPasswordByLink: (data: { token: string; new_password: string }) =>
      apiClient.post<GenericMessageResponse>('/auth/password/reset/by-link', data),
    resetPasswordByCode: (data: { email: string; code: string; new_password: string }) =>
      apiClient.post<GenericMessageResponse>('/auth/password/reset/by-code', data),
    resetPasswordByTelegramCode: (data: { username: string; code: string; new_password: string }) =>
      apiClient.post<GenericMessageResponse>('/auth/password/reset/by-telegram-code', data),
    changePassword: (data: { current_password: string; new_password: string }) =>
      apiClient.post<PasswordChangeResponse>('/auth/password/change', data),
  },

  user: {
    me: () => getCurrentUserProfile(),
    setSecurityEmail: (data: { email: string }) =>
      apiClient.patch<User>('/user/security/email', data),
    setPartnerBalanceCurrency: (data: { currency: string | null }) =>
      apiClient.patch<User>('/user/partner-balance-currency', data),
    transactions: (page = 1, limit = 20) =>
      apiClient.get<TransactionHistoryResponse>(`/user/transactions?page=${page}&limit=${limit}`),
  },

  notifications: {
    list: (page = 1, limit = 20) =>
      apiClient.get<UserNotificationListResponse>(`/user/notifications?page=${page}&limit=${limit}`),
    unreadCount: () => apiClient.get<UnreadCountResponse>('/user/notifications/unread-count'),
    markRead: (notificationId: number) =>
      apiClient.post<MarkReadResponse>(`/user/notifications/${notificationId}/read`),
    markAllRead: () => apiClient.post<MarkReadResponse>('/user/notifications/read-all'),
  },

  subscription: {
    list: () => apiClient.get<SubscriptionListResponse>('/subscription/list'),
    get: (id: number) => apiClient.get<Subscription>(`/subscription/${id}`),
    updateAssignment: (id: number, data: SubscriptionAssignmentRequest) =>
      apiClient.patch<Subscription>(`/subscription/${id}/assignment`, data),
    purchase: (data: SubscriptionPurchaseRequest) =>
      apiClient.post<PurchaseResponse>('/subscription/purchase', data),
    quote: (data: SubscriptionPurchaseRequest) =>
      apiClient.post<PurchaseQuoteResponse>('/subscription/quote', data),
    purchaseOptions: (id: number, purchaseType: Extract<PurchaseType, 'RENEW' | 'UPGRADE'>, channel?: PurchaseChannel) =>
      apiClient.get<SubscriptionPurchaseOptionsResponse>(`/subscription/${id}/purchase-options`, {
        params: {
          purchase_type: purchaseType,
          ...(channel ? { channel } : {}),
        },
      }),
    renew: (
      id: number,
      data: Omit<SubscriptionPurchaseRequest, 'purchase_type' | 'renew_subscription_id'>
    ) =>
      apiClient.post<PurchaseResponse>(`/subscription/${id}/renew`, data),
    upgrade: (
      id: number,
      data: Omit<SubscriptionPurchaseRequest, 'purchase_type' | 'renew_subscription_id'>
    ) =>
      apiClient.post<PurchaseResponse>(`/subscription/${id}/upgrade`, data),
    delete: (id: number) => apiClient.delete(`/subscription/${id}`),
    trialEligibility: () =>
      apiClient.get<TrialEligibilityResponse>('/subscription/trial/eligibility'),
    trial: (data?: { plan_id?: number }) => apiClient.post<Subscription>('/subscription/trial', data || {}),
  },

  plans: {
    list: (channel?: PurchaseChannel) =>
      apiClient.get<Plan[]>('/plans', {
        params: channel ? { channel } : undefined,
      }),
  },

  promocode: {
    activate: (data: { code: string; subscription_id?: number; create_new?: boolean }) =>
      apiClient.post<PromocodeActivateResult>('/promocode/activate', data),
    history: (page = 1, limit = 20) =>
      apiClient.get<PromocodeActivationHistoryResponse>(
        `/promocode/activations?page=${page}&limit=${limit}`
      ),
  },

  referral: {
    info: () => apiClient.get<ReferralInfo>('/referral/info'),
    qr: (target: 'telegram' | 'web' = 'telegram') =>
      apiClient.get<Blob>(`/referral/qr?target=${target}`, {
        responseType: 'blob',
      }),
    list: (page = 1, limit = 20) =>
      apiClient.get<ReferralListResponse>(`/referral/list?page=${page}&limit=${limit}`),
    exchangeOptions: () => apiClient.get<ReferralExchangeOptions>('/referral/exchange/options'),
    exchangeExecute: (data: ReferralExchangeExecuteRequest) =>
      apiClient.post<ReferralExchangeExecuteResponse>('/referral/exchange/execute', data),
    about: () => apiClient.get('/referral/about'),
  },

  partner: {
    info: () => apiClient.get<PartnerInfo>('/partner/info'),
    referrals: (page = 1, limit = 20) =>
      apiClient.get<PartnerReferralsListResponse>(`/partner/referrals?page=${page}&limit=${limit}`),
    earnings: (page = 1, limit = 20) =>
      apiClient.get<PartnerEarningsListResponse>(`/partner/earnings?page=${page}&limit=${limit}`),
    withdraw: (data: { amount: number; method: string; requisites: string }) =>
      apiClient.post('/partner/withdraw', data),
    withdrawals: () => apiClient.get<PartnerWithdrawalsListResponse>('/partner/withdrawals'),
  },

  devices: {
    list: (subscriptionId: number) =>
      apiClient.get<DeviceListResponse>(`/devices?subscription_id=${subscriptionId}`),
    generate: (data: { subscription_id: number; device_type?: DeviceType }) =>
      apiClient.post<{ hwid: string; connection_url: string; device_type: string }>('/devices/generate', data),
    revoke: (hwid: string, subscriptionId: number) =>
      apiClient.delete(`/devices/${hwid}?subscription_id=${subscriptionId}`),
  },
}

export { clearLegacyAuthStorage }

export default apiClient
