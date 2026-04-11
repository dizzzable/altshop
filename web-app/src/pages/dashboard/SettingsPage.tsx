import { useEffect, useState, type ElementType, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  CheckCircle2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  ExternalLink,
  Globe,
  History,
  Link as LinkIcon,
  LogOut,
  Mail,
  RefreshCw,
  Shield,
  User,
} from 'lucide-react'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { api, clearLegacyAuthStorage } from '@/lib/api'
import { resolveAccessCapabilities } from '@/lib/access-capabilities'
import { getPaymentGatewayDisplayName } from '@/lib/payment-gateway-icons'
import { readLocaleOverride } from '@/lib/locale'
import { openTelegramDeepLinkWithFallback } from '@/lib/openTelegramDeepLink'
import {
  readMobileExtraNavigationEnabled,
  subscribeMobileExtraNavigationPreference,
  writeMobileExtraNavigationEnabled,
} from '@/lib/mobile-navigation-preferences'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { cn } from '@/lib/utils'
import type { BadgeProps } from '@/components/ui/badge'
import type { Currency, Transaction } from '@/types'

const OPERATION_HISTORY_PAGE_SIZE = 10
const PARTNER_BALANCE_CURRENCY_OPTIONS: Array<{ value: Currency; label: string }> = [
  { value: 'RUB', label: 'RUB' },
  { value: 'USD', label: 'USD' },
  { value: 'USDT', label: 'USDT' },
  { value: 'TON', label: 'TON' },
  { value: 'BTC', label: 'BTC' },
  { value: 'ETH', label: 'ETH' },
  { value: 'LTC', label: 'LTC' },
  { value: 'BNB', label: 'BNB' },
  { value: 'DASH', label: 'DASH' },
  { value: 'SOL', label: 'SOL' },
  { value: 'XMR', label: 'XMR' },
  { value: 'USDC', label: 'USDC' },
  { value: 'TRX', label: 'TRX' },
]

function formatShortDate(value: string | undefined, locale: 'ru' | 'en'): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

function formatDateTime(value: string | undefined, locale: 'ru' | 'en'): string {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString(locale === 'ru' ? 'ru-RU' : 'en-US', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatAmount(value: number, currency: string, locale: 'ru' | 'en'): string {
  const amount = Number.isFinite(value) ? value : 0
  const formattedAmount = new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-US', {
    maximumFractionDigits: 2,
  }).format(amount)
  return `${formattedAmount} ${currency}`
}

function getOperationStatusVariant(status: string): BadgeProps['variant'] {
  if (status === 'FAILED' || status === 'CANCELED') return 'destructive'
  if (status === 'COMPLETED') return 'secondary'
  return 'secondary'
}

function getOperationStatusClass(status: string): string | undefined {
  if (status === 'COMPLETED') {
    return 'border-emerald-300/20 bg-emerald-400/12 text-emerald-200 hover:bg-emerald-400/18'
  }
  return undefined
}

function getRenewSubscriptionLabel(transaction: Transaction): string {
  if (transaction.renew_subscription_ids && transaction.renew_subscription_ids.length > 0) {
    return transaction.renew_subscription_ids.join(', ')
  }
  if (transaction.renew_subscription_id) {
    return String(transaction.renew_subscription_id)
  }
  return '-'
}

function getErrorMessage(error: unknown, fallback: string): string {
  const response = error as { response?: { data?: { detail?: unknown } } }
  const detail = response.response?.data?.detail
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object' && detail && 'message' in detail) {
    return String((detail as { message?: string }).message || fallback)
  }
  return fallback
}

export function SettingsPage() {
  const { user, refreshUser, logout, isLoading: authLoading } = useAuth()
  const { t, locale, supportedLocales, setLocaleOverride, clearLocaleOverride } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const { isInTelegram } = useTelegramWebApp()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const requestFailedMessage = t('settings.error.requestFailed')
  const localeOverride = readLocaleOverride()
  const isAutoLocale = localeOverride === null

  const [telegramId, setTelegramId] = useState('')
  const [telegramCode, setTelegramCode] = useState('')
  const [email, setEmail] = useState('')
  const [emailCode, setEmailCode] = useState('')

  const [isTelegramRequestLoading, setIsTelegramRequestLoading] = useState(false)
  const [isTelegramConfirmLoading, setIsTelegramConfirmLoading] = useState(false)
  const [isTelegramBotConfirmLoading, setIsTelegramBotConfirmLoading] = useState(false)
  const [telegramBotOpenUrl, setTelegramBotOpenUrl] = useState<string | null>(null)
  const [isEmailSaveLoading, setIsEmailSaveLoading] = useState(false)
  const [isEmailVerifyLoading, setIsEmailVerifyLoading] = useState(false)
  const [isEmailResendLoading, setIsEmailResendLoading] = useState(false)
  const [isRulesAcceptLoading, setIsRulesAcceptLoading] = useState(false)
  const [isChannelRecheckLoading, setIsChannelRecheckLoading] = useState(false)
  const [isPartnerBalanceCurrencyLoading, setIsPartnerBalanceCurrencyLoading] = useState(false)
  const [isTelegramPasswordRequestLoading, setIsTelegramPasswordRequestLoading] = useState(false)
  const [isTelegramPasswordSubmitting, setIsTelegramPasswordSubmitting] = useState(false)

  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [telegramPasswordError, setTelegramPasswordError] = useState<string | null>(null)
  const [tokenHandled, setTokenHandled] = useState(false)
  const [operationHistoryOpen, setOperationHistoryOpen] = useState(false)
  const [operationHistoryPage, setOperationHistoryPage] = useState(1)
  const [isTelegramPasswordModalOpen, setIsTelegramPasswordModalOpen] = useState(false)
  const [languageModalOpen, setLanguageModalOpen] = useState(false)
  const [accountFieldsModalOpen, setAccountFieldsModalOpen] = useState(false)
  const [accessStatusModalOpen, setAccessStatusModalOpen] = useState(false)
  const [mobileAccordionOpen, setMobileAccordionOpen] = useState<'telegram' | 'password' | 'email' | null>(null)
  const [telegramPasswordCode, setTelegramPasswordCode] = useState('')
  const [telegramPassword, setTelegramPassword] = useState('')
  const [telegramPasswordConfirm, setTelegramPasswordConfirm] = useState('')
  const [extraNavigationEnabled, setExtraNavigationEnabled] = useState(() => readMobileExtraNavigationEnabled())

  const { data: userProfile, isLoading: profileLoading, refetch } = useQuery({
    queryKey: ['user-profile'],
    queryFn: () => api.user.me().then((response) => response.data),
    initialData: user || undefined,
  })

  const { data: operationHistoryData, isLoading: operationHistoryLoading } = useQuery({
    queryKey: ['user-transactions', operationHistoryPage, OPERATION_HISTORY_PAGE_SIZE],
    queryFn: () =>
      api.user.transactions(operationHistoryPage, OPERATION_HISTORY_PAGE_SIZE).then((response) => response.data),
    enabled: operationHistoryOpen,
  })

  const {
    data: accessStatus,
    isLoading: accessStatusLoading,
    refetch: refetchAccessStatus,
  } = useQuery({
    queryKey: ['auth-access-status'],
    queryFn: () => api.auth.getAccessStatus().then((response) => response.data),
  })

  useEffect(() => {
    if (userProfile?.linked_telegram_id && !telegramId) {
      setTelegramId(String(userProfile.linked_telegram_id))
    }
    if (userProfile?.email && !email) {
      setEmail(userProfile.email)
    }
  }, [userProfile, telegramId, email])

  useEffect(() => {
    return subscribeMobileExtraNavigationPreference(() => {
      setExtraNavigationEnabled(readMobileExtraNavigationEnabled())
    })
  }, [])

  useEffect(() => {
    if (tokenHandled) return
    const verifyToken = params.get('email_verify_token')
    if (!verifyToken) return

    const run = async () => {
      setTokenHandled(true)
      try {
        await api.auth.confirmEmailVerify({ token: verifyToken })
        setMessage(t('settings.message.emailVerified'))
        await refreshUser()
        await refetch()
      } catch (err: unknown) {
        setError(getErrorMessage(err, requestFailedMessage))
      } finally {
        params.delete('email_verify_token')
        setParams(params, { replace: true })
      }
    }

    void run()
  }, [params, refreshUser, refetch, requestFailedMessage, setParams, t, tokenHandled])

  useEffect(() => {
    const prefillTelegramId = params.get('telegram_id')
    const shouldFocusTelegram = params.get('focus') === 'telegram'
    const accessBlocked = params.get('access_blocked') === '1'

    const nextParams = new URLSearchParams(params)
    let hasChanges = false

    if (prefillTelegramId && /^\d+$/.test(prefillTelegramId) && !telegramId) {
      setTelegramId(prefillTelegramId)
    }

    if (shouldFocusTelegram) {
      const el = document.getElementById('telegram-link-card')
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
      nextParams.delete('focus')
      hasChanges = true
    }

    if (prefillTelegramId) {
      nextParams.delete('telegram_id')
      hasChanges = true
    }

    if (accessBlocked) {
      setMessage(t('settings.access.blockedRedirectNotice'))
      nextParams.delete('access_blocked')
      hasChanges = true
    }

    if (hasChanges) {
      setParams(nextParams, { replace: true })
    }
  }, [params, setParams, telegramId, t])

  useEffect(() => {
    const telegramLinkStatus = params.get('telegram_link')
    if (!telegramLinkStatus) {
      return
    }

    let isCancelled = false
    const nextParams = new URLSearchParams(params)
    nextParams.delete('telegram_link')

    const run = async () => {
      if (telegramLinkStatus === 'success') {
        try {
          await Promise.all([refreshUser(), refetch(), refetchAccessStatus()])
          if (!isCancelled) {
            setError(null)
            setMessage(t('settings.message.telegramLinkedViaBot'))
          }
        } catch (err: unknown) {
          if (!isCancelled) {
            setError(getErrorMessage(err, requestFailedMessage))
          }
        }
      } else if (!isCancelled) {
        if (telegramLinkStatus === 'cancelled') {
          setError(null)
          setMessage(t('settings.message.telegramLinkCancelled'))
        } else if (telegramLinkStatus === 'merge_conflict') {
          setMessage(null)
          setError(t('settings.message.telegramLinkMergeConflict'))
        } else {
          setMessage(null)
          setError(t('settings.message.telegramLinkInvalid'))
        }
      }

      if (!isCancelled) {
        setParams(nextParams, { replace: true })
      }
    }

    void run()
    return () => {
      isCancelled = true
    }
  }, [params, refetch, refetchAccessStatus, refreshUser, requestFailedMessage, setParams, t])

  const isLoading = authLoading || profileLoading || accessStatusLoading

  if (isLoading) {
    return <SettingsSkeleton />
  }

  const displayName = userProfile?.name || userProfile?.username || t('common.userFallback')
  const displayUsername = userProfile?.username || `id${userProfile?.telegram_id || ''}`
  const webLogin = userProfile?.web_login?.trim() || ''
  const profileUsername = userProfile?.username?.trim() || ''
  const showSeparateProfileUsername = Boolean(
    profileUsername && (!webLogin || profileUsername !== webLogin)
  )
  const avatarFallback = displayName.charAt(0).toUpperCase() || 'U'
  const isTelegramLinked = Boolean(userProfile?.telegram_linked && userProfile?.linked_telegram_id)
  const isEmailVerified = Boolean(userProfile?.email_verified)
  const activeBadgeClass = 'border-emerald-300/20 bg-emerald-400/12 text-emerald-200 hover:bg-emerald-400/18'
  const operationHistoryItems = operationHistoryData?.transactions || []
  const operationHistoryTotal = operationHistoryData?.total || 0
  const operationHistoryTotalPages = Math.max(1, Math.ceil(operationHistoryTotal / OPERATION_HISTORY_PAGE_SIZE))
  const unmetRequirements = new Set(accessStatus?.unmet_requirements || [])
  const accessCapabilities = resolveAccessCapabilities(accessStatus)
  const isReadOnlyAccess = accessCapabilities.isReadOnly
  const isAccessRestricted = accessCapabilities.shouldRedirectToAccessScreen || isReadOnlyAccess
  const isChannelVerificationUnavailable = Boolean(
    accessStatus?.channel_check_status === 'unavailable'
    || unmetRequirements.has('CHANNEL_VERIFICATION_UNAVAILABLE')
  )
  const hasWebAccount = Boolean(userProfile?.has_web_account)
  const hasBootstrappedWebCredentials = !userProfile?.needs_web_credentials_bootstrap
  const resetUsername = webLogin
  const canUseTelegramPasswordReset = Boolean(
    hasWebAccount && hasBootstrappedWebCredentials && isTelegramLinked && resetUsername
  )
  const telegramPasswordHint = !hasWebAccount
    ? t('settings.password.hintNoWebAccount')
    : !hasBootstrappedWebCredentials
      ? t('layout.tgBootstrapDesc')
    : !isTelegramLinked
      ? t('settings.password.hintLinkTelegram')
    : !resetUsername
        ? t('settings.password.hintNoWebLogin')
        : t('settings.password.hintLinked', { telegramId: userProfile?.linked_telegram_id ?? '-' })
  const currentLanguageLabel = isAutoLocale ? t('settings.language.option.auto') : locale.toUpperCase()
  const partnerBalanceCurrencyValue = userProfile?.partner_balance_currency_override ?? 'AUTO'
  const effectivePartnerBalanceCurrency = userProfile?.effective_partner_balance_currency ?? 'RUB'
  const authSource = typeof window !== 'undefined' ? window.sessionStorage.getItem('auth_source') : null
  const canAutoConfirmInTelegram = Boolean(
    (userProfile?.telegram_id ?? 0) > 0
      && (authSource === 'telegram' || authSource === 'telegram-miniapp')
      && !isTelegramLinked
  )

  const handleTelegramRequest = async () => {
    setError(null)
    setMessage(null)
    setTelegramBotOpenUrl(null)
    if (!telegramId.trim() || !/^\d+$/.test(telegramId.trim())) {
      setError(t('settings.validation.telegramId'))
      return
    }

    setIsTelegramRequestLoading(true)
    try {
      const { data } = await api.auth.requestTelegramLinkCode({ telegram_id: Number(telegramId.trim()) })
      setMessage(data.message)
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsTelegramRequestLoading(false)
    }
  }

  const handleTelegramConfirm = async () => {
    setError(null)
    setMessage(null)
    setTelegramBotOpenUrl(null)
    if (!telegramId.trim() || !telegramCode.trim()) {
      setError(t('settings.validation.telegramCodeRequired'))
      return
    }

    setIsTelegramConfirmLoading(true)
    try {
      const { data } = await api.auth.confirmTelegramLinkCode({
        telegram_id: Number(telegramId.trim()),
        code: telegramCode.trim(),
      })
      clearLegacyAuthStorage()
      setTelegramCode('')
      setMessage(data.message)
      await Promise.all([refreshUser(), refetch(), refetchAccessStatus()])
      navigate('/dashboard/settings', { replace: true })
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsTelegramConfirmLoading(false)
    }
  }

  const handleTelegramBotConfirm = async () => {
    setError(null)
    setMessage(null)
    setTelegramBotOpenUrl(null)

    setIsTelegramBotConfirmLoading(true)
    try {
      const { data } = await api.auth.requestTelegramLinkAutoConfirm({
        return_to_miniapp: authSource === 'telegram-miniapp' && isInTelegram,
      })
      if (!data.bot_confirm_url) {
        setError(t('settings.validation.telegramBotConfirmUnavailable'))
        return
      }

      setMessage(data.message)
      setTelegramBotOpenUrl(data.bot_confirm_url)

      if (authSource === 'telegram-miniapp' && isInTelegram) {
        window.location.href = data.bot_confirm_url
        return
      }

      const opened = openTelegramDeepLinkWithFallback(
        data.bot_confirm_deep_link,
        data.bot_confirm_url
      )
      if (!opened) {
        window.location.href = data.bot_confirm_url
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsTelegramBotConfirmLoading(false)
    }
  }

  const handleEmailSave = async () => {
    setError(null)
    setMessage(null)
    if (!email.trim() || !email.includes('@')) {
      setError(t('settings.validation.email'))
      return
    }

    setIsEmailSaveLoading(true)
    try {
      await api.user.setSecurityEmail({ email: email.trim() })
      setMessage(t('settings.message.emailSaved'))
      await Promise.all([refreshUser(), refetch(), refetchAccessStatus()])
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsEmailSaveLoading(false)
    }
  }

  const handleEmailResend = async () => {
    setError(null)
    setMessage(null)
    setIsEmailResendLoading(true)
    try {
      const { data } = await api.auth.requestEmailVerify()
      setMessage(data.message)
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsEmailResendLoading(false)
    }
  }

  const handleEmailVerify = async () => {
    setError(null)
    setMessage(null)
    if (!emailCode.trim()) {
      setError(t('settings.validation.verifyCodeRequired'))
      return
    }

    setIsEmailVerifyLoading(true)
    try {
      const { data } = await api.auth.confirmEmailVerify({ code: emailCode.trim() })
      setEmailCode('')
      setMessage(data.message)
      await refreshUser()
      await refetch()
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsEmailVerifyLoading(false)
    }
  }

  const handlePartnerBalanceCurrencyChange = async (value: string) => {
    setError(null)
    setMessage(null)
    setIsPartnerBalanceCurrencyLoading(true)
    try {
      await api.user.setPartnerBalanceCurrency({
        currency: value === 'AUTO' ? null : value,
      })
      setMessage(t('settings.message.partnerBalanceCurrencyUpdated'))
      await Promise.all([refreshUser(), refetch()])
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsPartnerBalanceCurrencyLoading(false)
    }
  }

  const handleAcceptRules = async () => {
    setError(null)
    setMessage(null)
    setIsRulesAcceptLoading(true)
    try {
      await api.auth.acceptAccessRules()
      setMessage(t('settings.access.rulesAccepted'))
      await Promise.all([refetchAccessStatus(), refreshUser(), refetch()])
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsRulesAcceptLoading(false)
    }
  }

  const handleChannelRecheck = async () => {
    setError(null)
    setMessage(null)
    setIsChannelRecheckLoading(true)
    try {
      const { data } = await api.auth.getAccessStatus(true)
      setMessage(
        data.channel_check_status === 'unavailable'
          ? t('settings.access.channelUnavailable')
          : data.channel_verified
          ? t('settings.access.channelVerified')
          : t('settings.access.channelNotVerified')
      )
      await refetchAccessStatus()
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsChannelRecheckLoading(false)
    }
  }

  const handleTelegramPasswordRequest = async () => {
    setError(null)
    setMessage(null)
    setTelegramPasswordError(null)
    if (!hasWebAccount) {
      setError(t('settings.password.errorNoWebAccount'))
      return
    }
    if (!isTelegramLinked) {
      setError(t('settings.password.errorTelegramNotLinked'))
      return
    }
    if (!resetUsername) {
      setError(t('settings.password.errorWebLoginRequired'))
      return
    }

    setIsTelegramPasswordRequestLoading(true)
    try {
      const { data } = await api.auth.forgotPasswordByTelegram({ username: resetUsername })
      setMessage(data.message)
      setTelegramPasswordCode('')
      setTelegramPassword('')
      setTelegramPasswordConfirm('')
      setIsTelegramPasswordModalOpen(true)
    } catch (err: unknown) {
      setError(getErrorMessage(err, requestFailedMessage))
    } finally {
      setIsTelegramPasswordRequestLoading(false)
    }
  }

  const handleTelegramPasswordSubmit = async () => {
    setError(null)
    setMessage(null)
    setTelegramPasswordError(null)
    if (!resetUsername) {
      setTelegramPasswordError(t('settings.password.errorWebLoginRequired'))
      return
    }
    if (!telegramPasswordCode.trim() || !telegramPassword || !telegramPasswordConfirm) {
      setTelegramPasswordError(t('settings.password.errorRequired'))
      return
    }
    if (telegramPassword.length < 6) {
      setTelegramPasswordError(t('settings.password.errorMinLength'))
      return
    }
    if (telegramPassword !== telegramPasswordConfirm) {
      setTelegramPasswordError(t('settings.password.errorNoMatch'))
      return
    }

    setIsTelegramPasswordSubmitting(true)
    try {
      const { data } = await api.auth.resetPasswordByTelegramCode({
        username: resetUsername,
        code: telegramPasswordCode.trim(),
        new_password: telegramPassword,
      })
      setMessage(data.message)
      setIsTelegramPasswordModalOpen(false)
      setTelegramPasswordCode('')
      setTelegramPassword('')
      setTelegramPasswordConfirm('')
      await logout()
    } catch (err: unknown) {
      setTelegramPasswordError(getErrorMessage(err, t('settings.password.errorDefault')))
    } finally {
      setIsTelegramPasswordSubmitting(false)
    }
  }

  const handleAccordionToggle = (key: 'telegram' | 'password' | 'email') => {
    setMobileAccordionOpen((previous) => (previous === key ? null : key))
  }

  const languageSelectorContent = (
    <div className="space-y-3">
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
        <span className="text-sm text-slate-200">{t('settings.language.current')}</span>
        <Badge variant="secondary">{currentLanguageLabel}</Badge>
      </div>
      <div className="grid grid-cols-3 gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-2">
        {supportedLocales.includes('ru') && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={`h-9 rounded-lg border text-xs font-semibold uppercase tracking-[0.08em] ${
              localeOverride === 'ru'
                ? 'border-primary/55 bg-primary text-primary-foreground hover:bg-primary/90'
                : 'border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5 hover:text-slate-100'
            }`}
            onClick={() => setLocaleOverride('ru')}
          >
            RU
          </Button>
        )}
        {supportedLocales.includes('en') && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={`h-9 rounded-lg border text-xs font-semibold uppercase tracking-[0.08em] ${
              localeOverride === 'en'
                ? 'border-primary/55 bg-primary text-primary-foreground hover:bg-primary/90'
                : 'border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5 hover:text-slate-100'
            }`}
            onClick={() => setLocaleOverride('en')}
          >
            EN
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={`h-9 rounded-lg border text-xs font-semibold uppercase tracking-[0.08em] ${
            isAutoLocale
              ? 'border-primary/55 bg-primary text-primary-foreground hover:bg-primary/90'
              : 'border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5 hover:text-slate-100'
          }`}
          onClick={clearLocaleOverride}
        >
          AUTO
        </Button>
      </div>
    </div>
  )

  const handleExtraNavigationToggle = () => {
    writeMobileExtraNavigationEnabled(!extraNavigationEnabled)
  }

  const extraNavigationToggleContent = (
    <NavigationPreferenceToggle
      enabled={extraNavigationEnabled}
      title={t('settings.navigation.toggleLabel')}
      description={t('settings.navigation.toggleDescription')}
      enabledLabel={t('settings.navigation.statusEnabled')}
      disabledLabel={t('settings.navigation.statusDisabled')}
      onToggle={handleExtraNavigationToggle}
    />
  )

  const accountFieldsContent = (
    <div className="space-y-3">
      <div className="grid gap-2">
        <Label htmlFor="name">{t('settings.section.displayName')}</Label>
        <Input id="name" value={userProfile?.name || ''} readOnly disabled />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="web-login">{t('settings.section.webLogin')}</Label>
        <Input id="web-login" value={userProfile?.web_login || ''} readOnly disabled />
      </div>
      {showSeparateProfileUsername ? (
        <div className="grid gap-2">
          <Label htmlFor="profile-username">{t('settings.section.profileUsername')}</Label>
          <Input id="profile-username" value={userProfile?.username || ''} readOnly disabled />
        </div>
      ) : null}
      {userProfile?.is_partner ? (
        <div className="grid gap-2">
          <Label htmlFor="partner-balance-currency">{t('settings.partnerBalanceCurrency.label')}</Label>
          <Select
            value={partnerBalanceCurrencyValue}
            onValueChange={(value: string) => {
              void handlePartnerBalanceCurrencyChange(value)
            }}
            disabled={isPartnerBalanceCurrencyLoading}
          >
            <SelectTrigger id="partner-balance-currency">
              <SelectValue placeholder={t('settings.partnerBalanceCurrency.placeholderAuto')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="AUTO">
                {t('settings.partnerBalanceCurrency.optionAuto', {
                  currency: effectivePartnerBalanceCurrency,
                })}
              </SelectItem>
              {PARTNER_BALANCE_CURRENCY_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-slate-400">
            {t('settings.partnerBalanceCurrency.effective', {
              currency: effectivePartnerBalanceCurrency,
            })}
          </p>
        </div>
      ) : null}
    </div>
  )

  const accessStatusContent = (
    <div className="space-y-3">
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-slate-400" />
          <span className="text-sm text-slate-200">{t('settings.section.accountStatus')}</span>
        </div>
        <Badge
          variant={userProfile?.is_blocked ? 'destructive' : 'secondary'}
          className={userProfile?.is_blocked ? undefined : activeBadgeClass}
        >
          {!userProfile?.is_blocked && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-300" />}
          {userProfile?.is_blocked ? t('settings.profile.blocked') : t('settings.profile.active')}
        </Badge>
      </div>
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-slate-400" />
          <span className="text-sm text-slate-200">{t('settings.section.botAccess')}</span>
        </div>
        <Badge
          variant={userProfile?.is_bot_blocked ? 'destructive' : 'secondary'}
          className={userProfile?.is_bot_blocked ? undefined : activeBadgeClass}
        >
          {!userProfile?.is_bot_blocked && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-300" />}
          {userProfile?.is_bot_blocked ? t('settings.profile.blocked') : t('settings.section.allowed')}
        </Badge>
      </div>
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-4 w-4 text-slate-400" />
          <span className="text-sm text-slate-200">{t('settings.section.updated')}</span>
        </div>
        <span className="text-sm text-slate-300">{formatShortDate(userProfile?.updated_at, locale)}</span>
      </div>

      {accessStatus && (
        <div className="space-y-2 rounded-xl border border-white/10 bg-white/[0.04] p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-slate-200">{t('settings.access.requirementsTitle')}</span>
            <Badge
              variant={isAccessRestricted ? 'destructive' : 'secondary'}
              className={isAccessRestricted ? undefined : activeBadgeClass}
            >
              {isReadOnlyAccess
                ? t('settings.access.readOnly')
                : isAccessRestricted
                  ? t('settings.access.limited')
                  : t('settings.access.ready')}
            </Badge>
          </div>

          {accessStatus.rules_required && (
            <RequirementStatusRow
              label={t('settings.access.requirementRules')}
              isMet={accessStatus.rules_accepted}
              doneLabel={t('settings.access.statusDone')}
              pendingLabel={t('settings.access.statusPending')}
            />
          )}

          {accessStatus.requires_telegram_id && (
            <RequirementStatusRow
              label={t('settings.access.requirementTelegram')}
              isMet={accessStatus.telegram_linked}
              doneLabel={t('settings.access.statusDone')}
              pendingLabel={t('settings.access.statusPending')}
            />
          )}

          {accessStatus.channel_required && (
            <RequirementStatusRow
              label={t('settings.access.requirementChannel')}
              isMet={accessStatus.channel_verified}
              doneLabel={t('settings.access.statusDone')}
              pendingLabel={t('settings.access.statusPending')}
            />
          )}

          {isChannelVerificationUnavailable ? (
            <p className="text-xs text-amber-200/90">{t('settings.access.channelUnavailable')}</p>
          ) : unmetRequirements.size > 0 ? (
            <p className="text-xs text-amber-200/90">{t('settings.access.pendingHint')}</p>
          ) : null}

          <div className="flex flex-wrap gap-2 pt-1">
            {accessStatus.rules_required && !accessStatus.rules_accepted && (
              <Button
                type="button"
                variant="outline"
                onClick={handleAcceptRules}
                disabled={isRulesAcceptLoading}
              >
                {isRulesAcceptLoading ? t('settings.access.acceptingRules') : t('settings.access.acceptRules')}
              </Button>
            )}

            {accessStatus.channel_required && accessStatus.telegram_linked && (
              <Button
                type="button"
                variant="outline"
                onClick={handleChannelRecheck}
                disabled={isChannelRecheckLoading}
              >
                {isChannelRecheckLoading ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    {t('settings.access.recheckingChannel')}
                  </>
                ) : (
                  t('settings.access.recheckChannel')
                )}
              </Button>
            )}
          </div>

          <div className="flex flex-wrap gap-3 text-xs">
            {accessStatus.rules_link && (
              <a
                href={accessStatus.rules_link}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                {t('settings.access.openRules')}
              </a>
            )}
            {accessStatus.channel_link && (
              <a
                href={accessStatus.channel_link}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                {t('settings.access.openChannel')}
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  )

  const telegramLinkSectionContent = (
    <div className="space-y-2.5 p-5 pt-0 md:p-6 md:pt-0">
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
        <span className="text-xs uppercase tracking-wide text-slate-300">{t('settings.section.status')}</span>
        <Badge variant={isTelegramLinked ? 'default' : 'secondary'}>
          {isTelegramLinked
            ? `${t('settings.section.linkedLabel')}: ${userProfile?.linked_telegram_id}`
            : t('settings.profile.notLinked')}
        </Badge>
      </div>
      {accessStatus?.requires_telegram_id && !accessStatus.telegram_linked && (
        <p className="text-xs text-amber-200/90">{t('settings.access.telegramRequiredHint')}</p>
      )}
      {canAutoConfirmInTelegram && (
        <div className="space-y-2 rounded-xl border border-white/10 bg-white/[0.03] p-3">
          <Button
            size="sm"
            variant="secondary"
            className="w-full"
            onClick={handleTelegramBotConfirm}
            disabled={isTelegramBotConfirmLoading}
          >
            {isTelegramBotConfirmLoading
              ? t('settings.section.openingTelegram')
              : t('settings.section.confirmInTelegram')}
          </Button>
          <p className="text-xs text-slate-400">{t('settings.section.confirmInTelegramHint')}</p>
        </div>
      )}
      <div className="space-y-2 rounded-xl border border-white/10 bg-white/[0.02] p-3">
        {canAutoConfirmInTelegram && (
          <p className="text-xs text-slate-400">{t('settings.section.manualConfirmHint')}</p>
        )}
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="telegram-id">{t('settings.section.telegramIdLabel')}</Label>
            <Input
              id="telegram-id"
              className="h-10"
              placeholder={t('settings.placeholder.telegramId')}
              value={telegramId}
              onChange={(e) => setTelegramId(e.target.value)}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="telegram-code">{t('settings.section.verificationCode')}</Label>
            <Input
              id="telegram-code"
              className="h-10"
              placeholder={t('settings.placeholder.code')}
              value={telegramCode}
              onChange={(e) => setTelegramCode(e.target.value)}
            />
          </div>
        </div>
        <div className={cn('grid gap-2', canAutoConfirmInTelegram ? 'sm:grid-cols-2' : 'sm:grid-cols-3')}>
          <Button
            size="sm"
            variant="outline"
            onClick={handleTelegramRequest}
            disabled={isTelegramRequestLoading}
          >
            {isTelegramRequestLoading ? t('settings.section.sending') : t('settings.section.requestCode')}
          </Button>
          <Button size="sm" onClick={handleTelegramConfirm} disabled={isTelegramConfirmLoading}>
            {isTelegramConfirmLoading ? t('settings.section.confirming') : t('settings.section.confirmLink')}
          </Button>
          {!canAutoConfirmInTelegram && (
            <Button
              size="sm"
              variant="secondary"
              onClick={handleTelegramBotConfirm}
              disabled={isTelegramBotConfirmLoading}
            >
              {isTelegramBotConfirmLoading
                ? t('settings.section.openingTelegram')
                : t('settings.section.confirmInTelegram')}
            </Button>
          )}
        </div>
        {!canAutoConfirmInTelegram && (
          <p className="text-xs text-slate-400">{t('settings.section.confirmInTelegramHint')}</p>
        )}
        {telegramBotOpenUrl && !isInTelegram && (
          <Button
            size="sm"
            variant="ghost"
            className="w-full justify-start px-0 text-primary hover:bg-transparent hover:text-primary/90"
            onClick={() => {
              window.location.href = telegramBotOpenUrl
            }}
          >
            <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
            {t('settings.access.openVerificationBot')}
          </Button>
        )}
      </div>
      <div className="flex flex-wrap gap-3 text-xs">
        {accessStatus?.verification_bot_link && (
          <a
            href={accessStatus.verification_bot_link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            {t('settings.access.openVerificationBot')}
          </a>
        )}
        {accessStatus?.tg_id_helper_bot_link && (
          <a
            href={accessStatus.tg_id_helper_bot_link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            {t('settings.access.openTgIdHelper')}
          </a>
        )}
      </div>
    </div>
  )

  const passwordSectionContent = (
    <div className="flex h-full flex-col justify-between gap-2.5 p-5 pt-0 md:p-6 md:pt-0">
      <p className={`text-xs ${canUseTelegramPasswordReset ? 'text-slate-300' : 'text-amber-200/90'}`}>
        {telegramPasswordHint}
      </p>
      <Button
        type="button"
        size="sm"
        onClick={handleTelegramPasswordRequest}
        disabled={!canUseTelegramPasswordReset || isTelegramPasswordRequestLoading}
      >
        {isTelegramPasswordRequestLoading
          ? t('settings.password.requestingCode')
          : t('settings.password.changeViaTelegram')}
      </Button>
    </div>
  )

  const recoveryEmailSectionContent = (
    <div className="space-y-2.5 p-5 pt-0 md:p-6 md:pt-0">
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
        <span className="text-xs uppercase tracking-wide text-slate-300">{t('settings.section.verification')}</span>
        <Badge variant={isEmailVerified ? 'default' : 'secondary'}>
          {isEmailVerified ? t('settings.section.verified') : t('settings.section.notVerified')}
        </Badge>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1.6fr_1fr]">
        <div className="grid gap-1.5">
          <Label htmlFor="recovery-email">{t('settings.section.email')}</Label>
          <Input
            id="recovery-email"
            type="email"
            className="h-10"
            placeholder={t('settings.placeholder.email')}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="email-code">{t('settings.section.verificationCode')}</Label>
          <Input
            id="email-code"
            className="h-10"
            placeholder={t('settings.placeholder.code')}
            value={emailCode}
            onChange={(e) => setEmailCode(e.target.value)}
          />
        </div>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <Button size="sm" variant="outline" onClick={handleEmailSave} disabled={isEmailSaveLoading}>
          {isEmailSaveLoading ? t('settings.section.saving') : t('settings.section.saveEmail')}
        </Button>
        <Button size="sm" variant="outline" onClick={handleEmailResend} disabled={isEmailResendLoading}>
          {isEmailResendLoading ? t('settings.section.resending') : t('settings.section.resendVerify')}
        </Button>
      </div>
      <Button size="sm" onClick={handleEmailVerify} disabled={isEmailVerifyLoading}>
        {isEmailVerifyLoading ? t('settings.section.verifying') : t('settings.section.confirmVerify')}
      </Button>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight text-slate-100">{t('settings.title')}</h1>
        <p className="text-sm text-slate-400">
          {t('settings.subtitle')}
        </p>
      </div>

      {(error || message) && (
        <Alert variant={error ? 'destructive' : 'default'}>
          <AlertDescription>{error || message}</AlertDescription>
        </Alert>
      )}

      {isAccessRestricted && (
        <Alert variant={isReadOnlyAccess ? 'default' : 'destructive'}>
          <AlertDescription>
            {isReadOnlyAccess ? t('settings.access.readOnlyNotice') : t('settings.access.restrictedDescription')}
          </AlertDescription>
        </Alert>
      )}

      <section className={cn('gap-4', useMobileUiV2 ? 'grid grid-cols-1' : 'grid lg:grid-cols-3')}>
        <Card className="border-white/10 bg-card/90 shadow-[0_20px_45px_rgba(4,9,18,0.45)]">
          <CardContent className={cn('gap-4', useMobileUiV2 ? 'space-y-4 p-4' : 'flex flex-col p-5 sm:flex-row sm:items-center')}>
            <div className={cn('gap-3', useMobileUiV2 ? 'flex items-center' : '')}>
              <Avatar className={cn(useMobileUiV2 ? 'h-14 w-14 ring-1 ring-white/15' : 'h-16 w-16 ring-1 ring-white/15')}>
                <AvatarImage src={user?.photo_url || undefined} alt={displayName} />
                <AvatarFallback className={cn('bg-primary/20 font-semibold text-primary', useMobileUiV2 ? 'text-lg' : 'text-xl')}>
                  {avatarFallback}
                </AvatarFallback>
              </Avatar>

              <div className={cn('space-y-1', useMobileUiV2 ? 'min-w-0' : '')}>
                <p className={cn('font-semibold text-slate-100', useMobileUiV2 ? 'truncate text-xl' : 'text-xl')}>{displayName}</p>
                <p className={cn('text-sm text-slate-400', useMobileUiV2 ? 'truncate' : '')}>@{displayUsername}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <Badge variant={userProfile?.role === 'ADMIN' || userProfile?.role === 'DEV' ? 'default' : 'secondary'}>
                    {userProfile?.role || 'USER'}
                  </Badge>
                  <Badge
                    variant={userProfile?.is_blocked ? 'destructive' : 'secondary'}
                    className={userProfile?.is_blocked ? undefined : activeBadgeClass}
                  >
                    {!userProfile?.is_blocked && <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-300" />}
                    {userProfile?.is_blocked ? t('settings.profile.blocked') : t('settings.profile.active')}
                  </Badge>
                </div>
              </div>
            </div>

            {useMobileUiV2 && (
              <div className="grid gap-2 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">{t('settings.profile.telegramId')}</p>
                  <p className="mt-1 font-mono text-sm text-slate-100">{userProfile?.linked_telegram_id || t('settings.profile.notLinked')}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">{t('settings.profile.language')}</p>
                  <p className="mt-1 text-sm text-slate-100">{currentLanguageLabel}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">{t('settings.profile.created')}</p>
                  <p className="mt-1 text-sm text-slate-100">{formatShortDate(userProfile?.created_at, locale)}</p>
                </div>
              </div>
            )}

            <Button
              type="button"
              variant="ghost"
              size="sm"
              className={cn(
                'text-primary hover:bg-primary/10 hover:text-primary',
                useMobileUiV2 ? 'h-10 justify-start px-2' : 'mt-2 h-8 px-2'
              )}
              onClick={() => {
                setOperationHistoryPage(1)
                setOperationHistoryOpen(true)
              }}
            >
              <History className="mr-2 h-4 w-4" />
              {t('settings.operations.open')}
            </Button>
          </CardContent>
        </Card>

        {useMobileUiV2 ? (
          <>
            <Card className="border-white/10 bg-card/90">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-slate-100">{t('settings.mobile.quickActionsTitle')}</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-2 pt-0">
                <MobileSettingsTile
                  icon={Globe}
                  title={t('settings.mobile.languageTile')}
                  onClick={() => setLanguageModalOpen(true)}
                />
                <MobileSettingsTile
                  icon={User}
                  title={t('settings.mobile.accountFieldsTile')}
                  onClick={() => setAccountFieldsModalOpen(true)}
                />
                <MobileSettingsTile
                  icon={Shield}
                  title={t('settings.mobile.accessStatusTile')}
                  onClick={() => setAccessStatusModalOpen(true)}
                />
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-card/90">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-slate-100">{t('settings.navigation.title')}</CardTitle>
                <CardDescription>{t('settings.navigation.desc')}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                {extraNavigationToggleContent}
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-card/90">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-slate-100">{t('settings.mobile.logoutTitle')}</CardTitle>
                <CardDescription>{t('settings.mobile.logoutDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <Button
                  type="button"
                  variant="destructive"
                  className="w-full"
                  onClick={() => {
                    void logout()
                  }}
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  {t('header.logout')}
                </Button>
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            <Card className="border-white/10 bg-card/90 shadow-[0_20px_45px_rgba(4,9,18,0.45)]">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg text-slate-100">
                  <Globe className="h-4 w-4 text-primary" />
                  {t('settings.languageTitle')}
                </CardTitle>
                <CardDescription>{t('settings.languageDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {languageSelectorContent}
                <div className="h-px bg-white/10" />
                {extraNavigationToggleContent}
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-card/90 shadow-[0_20px_45px_rgba(4,9,18,0.45)]">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg text-slate-100">{t('settings.profile.overviewTitle')}</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-400">{t('settings.profile.telegramId')}</p>
                  <p className="mt-1 font-mono text-sm text-slate-100">{userProfile?.linked_telegram_id || t('settings.profile.notLinked')}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-400">{t('settings.profile.language')}</p>
                  <p className="mt-1 text-sm text-slate-100">{locale.toUpperCase()}</p>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <p className="text-xs uppercase tracking-wide text-slate-400">{t('settings.profile.created')}</p>
                  <p className="mt-1 text-sm text-slate-100">{formatShortDate(userProfile?.created_at, locale)}</p>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </section>

      {!useMobileUiV2 && (
        <section className="grid gap-4 md:grid-cols-2">
          <Card className="border-white/10 bg-card/90">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base text-slate-100">
                <User className="h-4 w-4 text-primary" />
                {t('settings.section.accountFieldsTitle')}
              </CardTitle>
              <CardDescription>{t('settings.section.accountFieldsDesc')}</CardDescription>
            </CardHeader>
            <CardContent>{accountFieldsContent}</CardContent>
          </Card>

          <Card className="border-white/10 bg-card/90">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base text-slate-100">
                <Shield className="h-4 w-4 text-primary" />
                {t('settings.section.accessStatusTitle')}
              </CardTitle>
              <CardDescription>{t('settings.section.accessStatusDesc')}</CardDescription>
            </CardHeader>
            <CardContent>{accessStatusContent}</CardContent>
          </Card>
        </section>
      )}

      {useMobileUiV2 ? (
        <section className="space-y-2">
          <MobileAccordionItem
            id="telegram-link-card"
            icon={LinkIcon}
            title={t('settings.section.telegramLinkTitle')}
            status={isTelegramLinked ? t('settings.mobile.status.linked') : t('settings.mobile.status.notLinked')}
            isOpen={mobileAccordionOpen === 'telegram'}
            onToggle={() => handleAccordionToggle('telegram')}
          >
            {telegramLinkSectionContent}
          </MobileAccordionItem>

          <MobileAccordionItem
            icon={Shield}
            title={t('settings.password.title')}
            status={canUseTelegramPasswordReset ? t('settings.mobile.status.ready') : t('settings.mobile.status.unavailable')}
            isOpen={mobileAccordionOpen === 'password'}
            onToggle={() => handleAccordionToggle('password')}
          >
            {passwordSectionContent}
          </MobileAccordionItem>

          <MobileAccordionItem
            icon={Mail}
            title={t('settings.section.recoveryEmailTitle')}
            status={isEmailVerified ? t('settings.section.verified') : t('settings.section.notVerified')}
            isOpen={mobileAccordionOpen === 'email'}
            onToggle={() => handleAccordionToggle('email')}
          >
            {recoveryEmailSectionContent}
          </MobileAccordionItem>
        </section>
      ) : (
        <section className="grid gap-4 lg:grid-cols-3">
          <Card id="telegram-link-card" className="h-full border-white/10 bg-card/90">
            <CardHeader className="space-y-1 pb-2">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold text-slate-100 sm:text-base">
                <LinkIcon className="h-4 w-4 text-primary" />
                {t('settings.section.telegramLinkTitle')}
              </CardTitle>
              <CardDescription>{t('settings.section.telegramLinkDesc')}</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">{telegramLinkSectionContent}</CardContent>
          </Card>

          <Card className="h-full border-white/10 bg-card/90">
            <CardHeader className="space-y-1 pb-2">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold text-slate-100 sm:text-base">
                <Shield className="h-4 w-4 text-primary" />
                {t('settings.password.title')}
              </CardTitle>
              <CardDescription>{t('settings.password.description')}</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">{passwordSectionContent}</CardContent>
          </Card>

          <Card className="h-full border-white/10 bg-card/90">
            <CardHeader className="space-y-1 pb-2">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold text-slate-100 sm:text-base">
                <Mail className="h-4 w-4 text-primary" />
                {t('settings.section.recoveryEmailTitle')}
              </CardTitle>
              <CardDescription>{t('settings.section.recoveryEmailDesc')}</CardDescription>
            </CardHeader>
            <CardContent className="pt-0">{recoveryEmailSectionContent}</CardContent>
          </Card>
        </section>
      )}

      <Dialog open={languageModalOpen} onOpenChange={setLanguageModalOpen}>
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('settings.mobile.languageModalTitle')}</DialogTitle>
            <DialogDescription>{t('settings.mobile.languageModalDesc')}</DialogDescription>
          </DialogHeader>
          {languageSelectorContent}
        </DialogContent>
      </Dialog>

      <Dialog open={accountFieldsModalOpen} onOpenChange={setAccountFieldsModalOpen}>
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('settings.mobile.accountModalTitle')}</DialogTitle>
            <DialogDescription>{t('settings.mobile.accountModalDesc')}</DialogDescription>
          </DialogHeader>
          {accountFieldsContent}
        </DialogContent>
      </Dialog>

      <Dialog open={accessStatusModalOpen} onOpenChange={setAccessStatusModalOpen}>
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{t('settings.mobile.accessModalTitle')}</DialogTitle>
            <DialogDescription>{t('settings.mobile.accessModalDesc')}</DialogDescription>
          </DialogHeader>
          {accessStatusContent}
        </DialogContent>
      </Dialog>

      <Dialog
        open={isTelegramPasswordModalOpen}
        onOpenChange={(open) => {
          if (isTelegramPasswordSubmitting) {
            return
          }
          setIsTelegramPasswordModalOpen(open)
          if (!open) {
            setTelegramPasswordError(null)
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('settings.password.modalTitle')}</DialogTitle>
            <DialogDescription>{t('settings.password.modalDescription')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-2">
              <Label htmlFor="telegram-password-code">{t('settings.password.code')}</Label>
              <Input
                id="telegram-password-code"
                placeholder={t('settings.placeholder.code')}
                value={telegramPasswordCode}
                onChange={(e) => setTelegramPasswordCode(e.target.value)}
                disabled={isTelegramPasswordSubmitting}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="telegram-password-new">{t('settings.password.newPassword')}</Label>
              <Input
                id="telegram-password-new"
                type="password"
                placeholder="********"
                value={telegramPassword}
                onChange={(e) => setTelegramPassword(e.target.value)}
                disabled={isTelegramPasswordSubmitting}
                autoComplete="new-password"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="telegram-password-confirm">{t('settings.password.confirmPassword')}</Label>
              <Input
                id="telegram-password-confirm"
                type="password"
                placeholder="********"
                value={telegramPasswordConfirm}
                onChange={(e) => setTelegramPasswordConfirm(e.target.value)}
                disabled={isTelegramPasswordSubmitting}
                autoComplete="new-password"
              />
            </div>
            {telegramPasswordError && (
              <Alert variant="destructive">
                <AlertDescription>{telegramPasswordError}</AlertDescription>
              </Alert>
            )}
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsTelegramPasswordModalOpen(false)}
                disabled={isTelegramPasswordSubmitting}
              >
                {t('common.cancel')}
              </Button>
              <Button type="button" onClick={handleTelegramPasswordSubmit} disabled={isTelegramPasswordSubmitting}>
                {isTelegramPasswordSubmitting ? t('settings.password.submitting') : t('settings.password.submit')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={operationHistoryOpen}
        onOpenChange={(open) => {
          setOperationHistoryOpen(open)
          if (open) {
            setOperationHistoryPage(1)
          }
        }}
      >
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain [touch-action:pan-y] [-webkit-overflow-scrolling:touch] sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="h-5 w-5 text-primary" />
              {t('settings.operations.title')}
            </DialogTitle>
            <DialogDescription>{t('settings.operations.description')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm text-slate-300">{t('settings.operations.listTitle')}</p>
              <Badge variant="secondary">
                {operationHistoryTotal} {t('settings.operations.total')}
              </Badge>
            </div>

            {operationHistoryLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((item) => (
                  <div key={item} className="h-28 rounded-lg border border-white/10 bg-white/5" />
                ))}
              </div>
            ) : operationHistoryItems.length > 0 ? (
              <>
                <div className="space-y-2">
                  {operationHistoryItems.map((transaction) => {
                    const discountText =
                      transaction.pricing.discount_percent > 0
                        ? ` (${t('settings.operations.discount', {
                          value: transaction.pricing.discount_percent,
                        })})`
                        : ''
                    const planDuration =
                      transaction.plan.duration === -1
                        ? t('settings.operations.duration.unlimited')
                        : t('settings.operations.duration.days', { value: transaction.plan.duration })
                    const channelLabel = transaction.channel
                      ? t(`settings.operations.channel.${transaction.channel}`)
                      : t('settings.operations.channel.unknown')

                    return (
                      <div key={transaction.payment_id} className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-slate-100">
                              {t(`settings.operations.purchaseType.${transaction.purchase_type}`)}
                            </p>
                            <p className="text-xs text-slate-400">
                              {formatDateTime(transaction.created_at, locale)}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {transaction.is_test && (
                              <Badge variant="outline">{t('settings.operations.test')}</Badge>
                            )}
                            <Badge
                              variant={getOperationStatusVariant(transaction.status)}
                              className={getOperationStatusClass(transaction.status)}
                            >
                              {t(`settings.operations.status.${transaction.status}`)}
                            </Badge>
                          </div>
                        </div>

                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          <div className="rounded-lg border border-white/10 bg-black/20 p-2.5">
                            <p className="text-[11px] uppercase tracking-wide text-slate-400">
                              {t('settings.operations.fields.plan')}
                            </p>
                            <p className="mt-1 text-sm text-slate-100">
                              {transaction.plan.name} · {planDuration}
                            </p>
                          </div>
                          <div className="rounded-lg border border-white/10 bg-black/20 p-2.5">
                            <p className="text-[11px] uppercase tracking-wide text-slate-400">
                              {t('settings.operations.fields.amount')}
                            </p>
                            <p className="mt-1 text-sm text-slate-100">
                              {formatAmount(transaction.pricing.final_amount, transaction.currency, locale)}
                              {discountText}
                            </p>
                          </div>
                          <div className="rounded-lg border border-white/10 bg-black/20 p-2.5">
                            <p className="text-[11px] uppercase tracking-wide text-slate-400">
                              {t('settings.operations.fields.gateway')}
                            </p>
                            <p className="mt-1 text-sm text-slate-100">
                              {getPaymentGatewayDisplayName(transaction.gateway_type)}
                            </p>
                          </div>
                          <div className="rounded-lg border border-white/10 bg-black/20 p-2.5">
                            <p className="text-[11px] uppercase tracking-wide text-slate-400">
                              {t('settings.operations.fields.channel')}
                            </p>
                            <p className="mt-1 text-sm text-slate-100">{channelLabel}</p>
                          </div>
                        </div>

                        {transaction.purchase_type === 'RENEW' && (
                          <p className="mt-2 text-xs text-slate-400">
                            {t('settings.operations.fields.renewTarget')}:{' '}
                            <span className="font-medium text-slate-200">
                              {getRenewSubscriptionLabel(transaction)}
                            </span>
                          </p>
                        )}

                        <p className="mt-2 break-all text-xs text-slate-500">
                          {t('settings.operations.fields.paymentId')}: {transaction.payment_id}
                        </p>
                      </div>
                    )
                  })}
                </div>

                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-slate-400">
                    {t('settings.operations.pageOf', {
                      page: operationHistoryPage,
                      total: operationHistoryTotalPages,
                    })}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setOperationHistoryPage((prev) => Math.max(1, prev - 1))}
                      disabled={operationHistoryPage <= 1}
                    >
                      <ChevronLeft className="mr-1 h-4 w-4" />
                      {t('settings.operations.prev')}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setOperationHistoryPage((prev) => Math.min(operationHistoryTotalPages, prev + 1))
                      }
                      disabled={operationHistoryPage >= operationHistoryTotalPages}
                    >
                      {t('settings.operations.next')}
                      <ChevronRight className="ml-1 h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex h-32 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-sm text-slate-400">
                {t('settings.operations.empty')}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function NavigationPreferenceToggle({
  enabled,
  title,
  description,
  enabledLabel,
  disabledLabel,
  onToggle,
}: {
  enabled: boolean
  title: string
  description: string
  enabledLabel: string
  disabledLabel: string
  onToggle: () => void
}) {
  return (
    <div className="space-y-2.5 rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-100">{title}</p>
          <p className="mt-1 text-xs text-slate-400">{description}</p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={onToggle}
          className={cn(
            'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-all duration-200',
            enabled
              ? 'border-primary/65 bg-primary/80'
              : 'border-white/20 bg-white/[0.08]'
          )}
        >
          <span
            className={cn(
              'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200',
              enabled ? 'translate-x-5' : 'translate-x-0.5'
            )}
          />
        </button>
      </div>
      <Badge variant={enabled ? 'default' : 'secondary'}>
        {enabled ? enabledLabel : disabledLabel}
      </Badge>
    </div>
  )
}

function MobileSettingsTile({
  icon: Icon,
  title,
  onClick,
}: {
  icon: ElementType
  title: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className="flex min-h-20 flex-col items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.03] px-2 py-3 text-center text-xs font-medium text-slate-100 transition hover:border-white/20 hover:bg-white/[0.06]"
      onClick={onClick}
      aria-label={title}
    >
      <Icon className="h-4 w-4 text-primary" />
      <span className="leading-tight">{title}</span>
    </button>
  )
}

function MobileAccordionItem({
  id,
  icon: Icon,
  title,
  status,
  isOpen,
  onToggle,
  children,
}: {
  id?: string
  icon: ElementType
  title: string
  status: string
  isOpen: boolean
  onToggle: () => void
  children: ReactNode
}) {
  return (
    <div id={id} className="overflow-hidden rounded-xl border border-white/10 bg-card/90">
      <button
        type="button"
        className="flex min-h-11 w-full items-center gap-2 px-3 py-2.5 text-left"
        onClick={onToggle}
        aria-expanded={isOpen}
      >
        <Icon className="h-4 w-4 shrink-0 text-primary" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-100">{title}</span>
        <span className="text-xs text-slate-400">{status}</span>
        <ChevronRight className={cn('h-4 w-4 shrink-0 text-slate-400 transition-transform', isOpen ? 'rotate-90' : '')} />
      </button>
      {isOpen && <div className="border-t border-white/10">{children}</div>}
    </div>
  )
}

function RequirementStatusRow({
  label,
  isMet,
  doneLabel,
  pendingLabel,
}: {
  label: string
  isMet: boolean
  doneLabel: string
  pendingLabel: string
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/10 bg-black/20 px-2.5 py-2">
      <span className="text-sm text-slate-200">{label}</span>
      {isMet ? (
        <span className="inline-flex items-center gap-1 text-xs text-emerald-200">
          <CheckCircle2 className="h-3.5 w-3.5" />
          {doneLabel}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-xs text-amber-200">
          <CircleDashed className="h-3.5 w-3.5" />
          {pendingLabel}
        </span>
      )}
    </div>
  )
}

function SettingsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-40" />
        <Skeleton className="h-4 w-72" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardContent className="p-6">
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-3 p-6">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-3 p-6">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[1, 2, 3, 4].map((skeletonId) => (
          <Card key={skeletonId}>
            <CardHeader>
              <Skeleton className="h-5 w-36" />
              <Skeleton className="h-4 w-52" />
            </CardHeader>
            <CardContent className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
