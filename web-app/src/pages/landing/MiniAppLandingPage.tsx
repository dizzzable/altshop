import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/components/auth/AuthProvider'
import { useBranding } from '@/components/common/BrandingProvider'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/components/common/I18nProvider'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { openExternalLink } from '@/lib/openExternalLink'
import {
  persistPendingPaymentReturnStatus,
  resolvePaymentRedirectPath,
  resolvePaymentReturnStatusFromQueryParam,
  resolvePaymentReturnStatusFromTelegramStartParam,
} from '@/lib/payment-return'
import { sendWebTelemetryEvent } from '@/lib/telemetry'
import {
  AlertCircle,
  CheckCircle2,
  KeyRound,
  Shield,
  Smartphone,
  Ticket,
  Users,
  WalletCards,
} from 'lucide-react'

const MINIAPP_START_PARAM = 'miniapp'
const MINIAPP_AUTH_ERROR_KEY = 'miniapp_auth_error'

const miniAppFeatures = [
  {
    icon: WalletCards,
    titleKey: 'miniapp.feature.wallet.title',
    descriptionKey: 'miniapp.feature.wallet.desc',
  },
  {
    icon: Shield,
    titleKey: 'miniapp.feature.limits.title',
    descriptionKey: 'miniapp.feature.limits.desc',
  },
  {
    icon: Ticket,
    titleKey: 'miniapp.feature.promocodes.title',
    descriptionKey: 'miniapp.feature.promocodes.desc',
  },
  {
    icon: Users,
    titleKey: 'miniapp.feature.referrals.title',
    descriptionKey: 'miniapp.feature.referrals.desc',
  },
  {
    icon: Smartphone,
    titleKey: 'miniapp.feature.devices.title',
    descriptionKey: 'miniapp.feature.devices.desc',
  },
  {
    icon: KeyRound,
    titleKey: 'miniapp.feature.fastLogin.title',
    descriptionKey: 'miniapp.feature.fastLogin.desc',
  },
] as const

function resolveMiniAppDeepLink(preferredLaunchUrl: string | null): string {
  const normalizedPreferredLaunchUrl = preferredLaunchUrl?.trim() || ''
  if (normalizedPreferredLaunchUrl) {
    return normalizedPreferredLaunchUrl
  }

  const rawUsername = (import.meta.env.VITE_TELEGRAM_BOT_USERNAME || '').trim().replace(/^@/, '')
  if (!rawUsername) {
    return 'https://t.me'
  }
  return `https://t.me/${rawUsername}?startapp=${MINIAPP_START_PARAM}`
}

function IconoirTelegram({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M4.7 11.8L18.55 5.98C19.4 5.62 20.24 6.41 19.98 7.27L16.75 17.77C16.54 18.44 15.72 18.68 15.19 18.28L11.2 15.33L8.66 17.78C8.17 18.25 7.35 17.94 7.29 17.27L7.03 14.26L4.31 13.27C3.48 12.97 3.89 12.14 4.7 11.8Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M19.7 6.02L7.32 13.97" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  )
}

export function MiniAppLandingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useI18n()
  const { projectName, miniAppLaunchUrl } = useBranding()
  const { isAuthenticated } = useAuth()
  const [showAuthError] = useState(() => {
    if (typeof window === 'undefined') {
      return false
    }

    try {
      const hasError = window.sessionStorage.getItem(MINIAPP_AUTH_ERROR_KEY) === '1'
      if (hasError) {
        window.sessionStorage.removeItem(MINIAPP_AUTH_ERROR_KEY)
      }
      return hasError
    } catch {
      return false
    }
  })
  const deepLink = useMemo(() => resolveMiniAppDeepLink(miniAppLaunchUrl), [miniAppLaunchUrl])
  const { isReady, isInTelegram, initData, launchContext, deviceMode } = useTelegramWebApp()
  const paymentReturnStatus =
    resolvePaymentReturnStatusFromTelegramStartParam(launchContext.startParam)
    ?? resolvePaymentReturnStatusFromQueryParam(location.search)

  useEffect(() => {
    if (!isReady) {
      return
    }

    sendWebTelemetryEvent({
      event_name: 'miniapp_landing_view',
      source_path: location.pathname,
      device_mode: deviceMode,
      is_in_telegram: isInTelegram,
      has_init_data: Boolean(initData),
      start_param: launchContext.startParam || undefined,
      has_query_id: launchContext.hasQueryId,
      chat_type: launchContext.chatType || undefined,
    })
  }, [deviceMode, initData, isInTelegram, isReady, launchContext, location.pathname])

  useEffect(() => {
    if (!paymentReturnStatus) {
      return
    }

    persistPendingPaymentReturnStatus(paymentReturnStatus)

    if (isAuthenticated) {
      navigate(resolvePaymentRedirectPath(paymentReturnStatus), { replace: true })
      return
    }

    if (!isReady || !isInTelegram) {
      return
    }

    const searchParams = new URLSearchParams(location.search)
    if (searchParams.get('tg_open') !== '1') {
      navigate('/miniapp?tg_open=1', { replace: true })
    }
  }, [isAuthenticated, isInTelegram, isReady, location.search, navigate, paymentReturnStatus])

  const handleOpenPanel = () => {
    sendWebTelemetryEvent({
      event_name: 'miniapp_open_panel_click',
      source_path: location.pathname,
      device_mode: deviceMode,
      is_in_telegram: isInTelegram,
      has_init_data: Boolean(initData),
      start_param: launchContext.startParam || undefined,
      has_query_id: launchContext.hasQueryId,
      chat_type: launchContext.chatType || undefined,
      meta: { action: 'tg_open_intent' },
    })

    if (isAuthenticated) {
      navigate('/dashboard/subscription')
      return
    }

    navigate('/miniapp?tg_open=1')
  }

  const handleOpenInTelegram = () => {
    sendWebTelemetryEvent({
      event_name: 'miniapp_open_panel_blocked_non_telegram',
      source_path: location.pathname,
      device_mode: deviceMode,
      is_in_telegram: isInTelegram,
      has_init_data: Boolean(initData),
      start_param: launchContext.startParam || undefined,
      has_query_id: launchContext.hasQueryId,
      chat_type: launchContext.chatType || undefined,
      meta: { action: 'open_telegram_deep_link' },
    })

    const opened = openExternalLink(deepLink)
    if (!opened) {
      window.location.href = deepLink
    }
  }

  if (!isReady) {
    return <div className="p-6 text-sm text-slate-300">{t('common.loading')}</div>
  }

  return (
    <div className="relative min-h-[100svh] px-3 pb-3 pt-[calc(0.65rem+var(--app-safe-top))] sm:px-4 sm:pb-4 sm:pt-[calc(0.7rem+var(--app-safe-top))]">
      <div className="pointer-events-none absolute inset-x-0 top-[-220px] z-[-1] h-[520px] bg-[radial-gradient(78%_120%_at_50%_30%,rgba(124,145,166,0.2)_0%,rgba(124,145,166,0)_76%)]" />
      <div className="pointer-events-none absolute left-[-120px] top-[56%] z-[-1] h-[250px] w-[250px] rounded-full bg-[#5f7082]/22 blur-[130px]" />
      <div className="pointer-events-none absolute right-[-120px] top-[24%] z-[-1] h-[250px] w-[250px] rounded-full bg-[#4f6072]/20 blur-[120px]" />

      <main className="mx-auto flex w-full max-w-md flex-col overflow-hidden rounded-[28px] border border-white/12 bg-[#070a0e]/86 shadow-[0_28px_80px_-52px_rgba(0,0,0,0.95)] backdrop-blur-xl max-h-[calc(100svh-var(--app-safe-top)-var(--app-safe-bottom)-0.9rem)] sm:max-h-[calc(100svh-var(--app-safe-top)-var(--app-safe-bottom)-1.1rem)]">
        <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-4 pt-4 [touch-action:pan-y] [-webkit-overflow-scrolling:touch] sm:px-5 sm:pt-5">
          <header className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="grid h-9 w-9 place-items-center rounded-xl border border-primary/30 bg-primary/12 text-primary">
                <Shield className="h-4 w-4" />
              </span>
              <div>
                <p className="text-[10px] uppercase tracking-[0.16em] text-slate-400">{projectName}</p>
                <p className="text-sm font-semibold text-slate-100">{t('miniapp.navLabel')}</p>
              </div>
            </div>
            <span className="shrink-0 rounded-full border border-white/12 bg-white/[0.03] px-2.5 py-1 text-[10px] font-medium text-slate-300">
              {isInTelegram ? t('miniapp.badge.telegram') : t('miniapp.badge.browser')}
            </span>
          </header>

          <section className="mt-3">
            <h1 className="text-[1.9rem] font-semibold leading-[1.05] text-white max-[359px]:text-[1.7rem] min-[390px]:text-[2.1rem]">
              {t('miniapp.title')}
            </h1>
            <p className="mt-2 text-[12px] leading-5 text-slate-300 min-[390px]:text-[13px]">
              {t('miniapp.subtitle')}
            </p>
          </section>

          {showAuthError ? (
            <div className="mt-3 flex items-start gap-2 rounded-xl border border-rose-300/35 bg-rose-500/10 px-3 py-2">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-200" />
              <p className="text-[11px] leading-4 text-rose-100">{t('miniapp.authFailed')}</p>
            </div>
          ) : null}

          <section className="mt-3 grid grid-cols-1 gap-2 min-[340px]:grid-cols-2">
            {miniAppFeatures.map((feature) => (
              <div
                key={feature.titleKey}
                className="rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2.5"
              >
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-primary/30 bg-primary/10 text-primary">
                    <feature.icon className="h-3.5 w-3.5" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold leading-4 text-slate-100">{t(feature.titleKey)}</p>
                    <p className="mt-0.5 text-[11px] leading-4 text-slate-400">{t(feature.descriptionKey)}</p>
                  </div>
                </div>
              </div>
            ))}
          </section>
          <div className="h-3 sm:h-4" />
        </div>

        <section className="sticky bottom-0 z-10 border-t border-primary/18 bg-[linear-gradient(180deg,rgba(7,10,14,0.6)_0%,rgba(8,10,14,0.92)_18%,rgba(8,10,14,0.98)_100%)] px-4 pb-[calc(0.85rem+var(--app-safe-bottom))] pt-3 backdrop-blur-xl sm:px-5 sm:pb-4">
          {isInTelegram ? (
            <Button className="h-11 w-full gap-2 text-sm font-semibold" onClick={handleOpenPanel}>
              <IconoirTelegram className="h-4 w-4" />
              {t('miniapp.openPanel')}
            </Button>
          ) : (
            <Button className="h-11 w-full gap-2 text-sm font-semibold" onClick={handleOpenInTelegram}>
              <IconoirTelegram className="h-4 w-4" />
              {t('miniapp.openInTelegram')}
            </Button>
          )}

          <div className="mt-2 flex items-start gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-2.5 py-2">
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <p className="text-[11px] leading-4 text-slate-300">
              {isInTelegram ? t('miniapp.openHint') : t('miniapp.telegramOnlyHint')}
            </p>
          </div>
        </section>
      </main>
    </div>
  )
}
