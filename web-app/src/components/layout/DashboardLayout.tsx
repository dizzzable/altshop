import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { useAccessStatusQuery } from '@/hooks/useAccessStatusQuery'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { api, clearLegacyAuthStorage } from '@/lib/api'
import { sendWebTelemetryEvent } from '@/lib/telemetry'
import { cn } from '@/lib/utils'
import {
  readMobileExtraNavigationEnabled,
  subscribeMobileExtraNavigationPreference,
} from '@/lib/mobile-navigation-preferences'
import {
  clearPendingTelegramMiniAppOnboarding,
  hasPendingTelegramMiniAppOnboarding,
} from '@/lib/telegram-onboarding'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Header } from './Header'
import { MobileBottomBar } from './MobileBottomBar'
import { Sidebar } from './Sidebar'
import {
  resolveAdjacentMobileNavHref,
  resolveMobileNavRootHref,
} from '@/components/layout/dashboard-nav'

const ROUTE_SWIPE_HORIZONTAL_THRESHOLD_PX = 72
const ROUTE_SWIPE_VERTICAL_DRIFT_PX = 32
const ROUTE_SWIPE_MAX_DURATION_MS = 700
const ROUTE_SWIPE_ANIMATION_DURATION_MS = 220
const ROUTE_SWIPE_INTERACTIVE_SELECTOR = [
  'a',
  'button',
  'input',
  'textarea',
  'select',
  'label',
  'summary',
  '[role="link"]',
  '[data-no-route-swipe]',
].join(', ')

function isRouteSwipeInteractiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) {
    return false
  }
  return Boolean(target.closest(ROUTE_SWIPE_INTERACTIVE_SELECTOR))
}

export function DashboardLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, refreshUser, logout } = useAuth()
  const { t } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const forceMobileShell = useMobileUiV2
  const isPartnerActive = Boolean(user?.is_partner_active)
  const { data: accessStatus } = useAccessStatusQuery({ enabled: Boolean(user) })
  const { isInTelegram, isReady: _isTelegramReady } = useTelegramWebApp()
  const [openForcePasswordPrompt, setOpenForcePasswordPrompt] = useState(false)
  const [forceCurrentPassword, setForceCurrentPassword] = useState('')
  const [forceNewPassword, setForceNewPassword] = useState('')
  const [forceConfirmPassword, setForceConfirmPassword] = useState('')
  const [forceError, setForceError] = useState<string | null>(null)
  const [isForceChanging, setIsForceChanging] = useState(false)
  const [openLinkPrompt, setOpenLinkPrompt] = useState(false)
  const [isSavingLater, setIsSavingLater] = useState(false)
  const [openBootstrapPrompt, setOpenBootstrapPrompt] = useState(false)
  const [bootstrapUsername, setBootstrapUsername] = useState('')
  const [bootstrapPassword, setBootstrapPassword] = useState('')
  const [bootstrapError, setBootstrapError] = useState<string | null>(null)
  const [isBootstrapping, setIsBootstrapping] = useState(false)
  const [openTrialOnboardingPrompt, setOpenTrialOnboardingPrompt] = useState(false)
  const [trialOnboardingError, setTrialOnboardingError] = useState<string | null>(null)
  const [isActivatingTrialOnboarding, setIsActivatingTrialOnboarding] = useState(false)
  const [extraNavigationEnabled, setExtraNavigationEnabled] = useState(() => readMobileExtraNavigationEnabled())
  const [routeSwipeAnimation, setRouteSwipeAnimation] = useState<'next' | 'prev' | null>(null)
  const bootstrapShownRef = useRef(false)
  const routeSwipeAnimationTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const routeSwipeStateRef = useRef<{
    pointerId: number | null
    startX: number
    startY: number
    startTs: number
    tracking: boolean
  }>({
    pointerId: null,
    startX: 0,
    startY: 0,
    startTs: 0,
    tracking: false,
  })
  const canSwipeBetweenRootRoutes = useMemo(
    () => Boolean(forceMobileShell && resolveMobileNavRootHref(location.pathname, isPartnerActive)),
    [forceMobileShell, isPartnerActive, location.pathname]
  )
  const isReadOnlyAccess = accessStatus?.access_level === 'read_only'
  const authSource =
    typeof window !== 'undefined' ? window.sessionStorage.getItem('auth_source') : null
  const isMiniAppBootstrapSession = authSource === 'telegram-miniapp'

  useEffect(() => {
    if (!useMobileUiV2 || typeof window === 'undefined') {
      return
    }
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [location.pathname, useMobileUiV2])

  useEffect(() => {
    return subscribeMobileExtraNavigationPreference(() => {
      setExtraNavigationEnabled(readMobileExtraNavigationEnabled())
    })
  }, [])

  useEffect(() => {
    return () => {
      if (routeSwipeAnimationTimerRef.current) {
        clearTimeout(routeSwipeAnimationTimerRef.current)
        routeSwipeAnimationTimerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    const shouldOpen = Boolean(
      user?.show_link_prompt
      && !user?.telegram_linked
      && !openBootstrapPrompt
      && !openForcePasswordPrompt
      && !user?.requires_password_change
    )
    setOpenLinkPrompt(shouldOpen)
  }, [
    openBootstrapPrompt,
    openForcePasswordPrompt,
    user?.requires_password_change,
    user?.show_link_prompt,
    user?.telegram_linked,
  ])

  useEffect(() => {
    const shouldOpen = Boolean(
      isMiniAppBootstrapSession
      && user?.needs_web_credentials_bootstrap
      && !openForcePasswordPrompt
      && !user?.requires_password_change
    )
    setOpenBootstrapPrompt(shouldOpen)
  }, [
    isMiniAppBootstrapSession,
    openForcePasswordPrompt,
    user?.needs_web_credentials_bootstrap,
    user?.requires_password_change,
  ])

  useEffect(() => {
    if (openBootstrapPrompt && !bootstrapShownRef.current) {
      bootstrapShownRef.current = true
      sendWebTelemetryEvent({
        event_name: 'miniapp_credentials_bootstrap_shown',
        source_path: location.pathname,
        device_mode: isInTelegram ? 'telegram-mobile' : 'web',
        is_in_telegram: isInTelegram,
        has_init_data: isInTelegram,
        has_query_id: false,
      })
    }
  }, [isInTelegram, location.pathname, openBootstrapPrompt])

  useEffect(() => {
    const shouldOpen = Boolean(user?.requires_password_change)
    setOpenForcePasswordPrompt(shouldOpen)
    if (!shouldOpen) {
      setForceCurrentPassword('')
      setForceNewPassword('')
      setForceConfirmPassword('')
      setForceError(null)
    }
  }, [user?.requires_password_change])

  useEffect(() => {
    if (!openBootstrapPrompt) {
      return
    }
    const preferredWebLogin = user?.web_login || user?.username
    if (!bootstrapUsername && preferredWebLogin) {
      setBootstrapUsername(preferredWebLogin)
    }
  }, [bootstrapUsername, openBootstrapPrompt, user?.username, user?.web_login])

  useEffect(() => {
    if (!openForcePasswordPrompt) {
      return
    }
    setOpenBootstrapPrompt(false)
    setOpenLinkPrompt(false)
  }, [openForcePasswordPrompt])

  const handleForcePasswordChange = async () => {
    if (!forceCurrentPassword || !forceNewPassword || !forceConfirmPassword) {
      setForceError(t('layout.forcePassword.errorRequired'))
      return
    }
    if (forceNewPassword.length < 6) {
      setForceError(t('layout.forcePassword.errorMinLength'))
      return
    }
    if (forceNewPassword !== forceConfirmPassword) {
      setForceError(t('layout.forcePassword.errorNoMatch'))
      return
    }

    setForceError(null)
    setIsForceChanging(true)
    try {
      await api.auth.changePassword({
        current_password: forceCurrentPassword,
        new_password: forceNewPassword,
      })
      clearLegacyAuthStorage()
      await refreshUser()
      setOpenForcePasswordPrompt(false)
      setForceCurrentPassword('')
      setForceNewPassword('')
      setForceConfirmPassword('')
    } catch (error: unknown) {
      const backendError = error as { response?: { data?: { detail?: string; message?: string } } }
      setForceError(
        backendError.response?.data?.detail
          || backendError.response?.data?.message
          || t('layout.forcePassword.errorDefault')
      )
    } finally {
      setIsForceChanging(false)
    }
  }

  const handleRemindLater = async () => {
    setIsSavingLater(true)
    try {
      await api.auth.remindTelegramLinkLater()
      await refreshUser()
    } finally {
      setIsSavingLater(false)
      setOpenLinkPrompt(false)
    }
  }

  const handleBootstrapCreate = async () => {
    const normalizedUsername = bootstrapUsername.trim()
    if (!normalizedUsername || !bootstrapPassword) {
      setBootstrapError(t('layout.tgBootstrapErrorRequired'))
      return
    }

    setBootstrapError(null)
    setIsBootstrapping(true)

    try {
      await api.auth.webAccountBootstrap({
        username: normalizedUsername,
        password: bootstrapPassword,
      })
      clearLegacyAuthStorage()
      sessionStorage.setItem('auth_source', 'password')
      sendWebTelemetryEvent({
        event_name: 'miniapp_credentials_bootstrap_completed',
        source_path: location.pathname,
        device_mode: isInTelegram ? 'telegram-mobile' : 'web',
        is_in_telegram: isInTelegram,
        has_init_data: isInTelegram,
        has_query_id: false,
        meta: {
          username: normalizedUsername,
        },
      })
      setBootstrapPassword('')
      await refreshUser()
      setOpenBootstrapPrompt(false)
      setBootstrapError(null)

      if (hasPendingTelegramMiniAppOnboarding() && !isReadOnlyAccess) {
        try {
          const { data: trialEligibility } = await api.subscription.trialEligibility()
          if (trialEligibility.eligible && trialEligibility.trial_plan_id !== null) {
            setTrialOnboardingError(null)
            setOpenTrialOnboardingPrompt(true)
          } else {
            clearPendingTelegramMiniAppOnboarding()
          }
        } catch {
          clearPendingTelegramMiniAppOnboarding()
        }
      }
    } catch (error: unknown) {
      const backendError = error as { response?: { data?: { detail?: string; message?: string } } }
      setBootstrapError(
        backendError.response?.data?.detail
          || backendError.response?.data?.message
          || t('layout.tgBootstrapErrorDefault')
      )
    } finally {
      setIsBootstrapping(false)
    }
  }

  const handleBootstrapLogout = () => {
    sendWebTelemetryEvent({
      event_name: 'miniapp_credentials_bootstrap_rejected',
      source_path: location.pathname,
      device_mode: isInTelegram ? 'telegram-mobile' : 'web',
      is_in_telegram: isInTelegram,
      has_init_data: isInTelegram,
      has_query_id: false,
    })
    void logout()
  }

  const handleCloseTrialOnboarding = () => {
    clearPendingTelegramMiniAppOnboarding()
    setTrialOnboardingError(null)
    setOpenTrialOnboardingPrompt(false)
  }

  const handleActivateTrialOnboarding = async () => {
    setIsActivatingTrialOnboarding(true)
    setTrialOnboardingError(null)
    try {
      await api.subscription.trial()
      clearPendingTelegramMiniAppOnboarding()
      setOpenTrialOnboardingPrompt(false)
      await refreshUser()
      navigate('/dashboard/subscription', { replace: true })
    } catch (error: unknown) {
      const fallbackMessage = t('layout.trialOnboarding.activateFailed')
      setTrialOnboardingError(extractApiErrorMessage(error, fallbackMessage))
    } finally {
      setIsActivatingTrialOnboarding(false)
    }
  }

  const clearRouteSwipeState = () => {
    routeSwipeStateRef.current.pointerId = null
    routeSwipeStateRef.current.startX = 0
    routeSwipeStateRef.current.startY = 0
    routeSwipeStateRef.current.startTs = 0
    routeSwipeStateRef.current.tracking = false
  }

  const releaseRouteSwipePointerCapture = (
    target: EventTarget | null,
    pointerId: number | null
  ) => {
    if (!(target instanceof HTMLElement) || pointerId === null) {
      return
    }
    if (typeof target.hasPointerCapture !== 'function' || typeof target.releasePointerCapture !== 'function') {
      return
    }
    if (!target.hasPointerCapture(pointerId)) {
      return
    }
    target.releasePointerCapture(pointerId)
  }

  const handleMainPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    if (!canSwipeBetweenRootRoutes || event.pointerType !== 'touch') {
      clearRouteSwipeState()
      return
    }
    if (isRouteSwipeInteractiveTarget(event.target)) {
      clearRouteSwipeState()
      return
    }

    routeSwipeStateRef.current.pointerId = event.pointerId
    routeSwipeStateRef.current.startX = event.clientX
    routeSwipeStateRef.current.startY = event.clientY
    routeSwipeStateRef.current.startTs = Date.now()
    routeSwipeStateRef.current.tracking = true
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // Ignore transient pointer capture errors.
    }
  }

  const handleMainPointerUp = (event: ReactPointerEvent<HTMLElement>) => {
    const swipeState = routeSwipeStateRef.current
    const trackedPointerId = swipeState.pointerId
    if (
      !canSwipeBetweenRootRoutes
      || !swipeState.tracking
      || swipeState.pointerId !== event.pointerId
    ) {
      releaseRouteSwipePointerCapture(event.currentTarget, trackedPointerId)
      clearRouteSwipeState()
      return
    }

    const deltaX = event.clientX - swipeState.startX
    const deltaY = event.clientY - swipeState.startY
    const gestureDuration = Date.now() - swipeState.startTs
    releaseRouteSwipePointerCapture(event.currentTarget, trackedPointerId)
    clearRouteSwipeState()

    if (
      Math.abs(deltaX) < ROUTE_SWIPE_HORIZONTAL_THRESHOLD_PX
      || Math.abs(deltaY) > ROUTE_SWIPE_VERTICAL_DRIFT_PX
      || gestureDuration > ROUTE_SWIPE_MAX_DURATION_MS
    ) {
      return
    }

    const swipeDirection = deltaX < 0 ? 'next' : 'prev'
    const nextPath = resolveAdjacentMobileNavHref(location.pathname, swipeDirection, isPartnerActive)
    if (!nextPath || nextPath === location.pathname) {
      return
    }

    setRouteSwipeAnimation(swipeDirection)
    if (routeSwipeAnimationTimerRef.current) {
      clearTimeout(routeSwipeAnimationTimerRef.current)
    }
    routeSwipeAnimationTimerRef.current = setTimeout(() => {
      setRouteSwipeAnimation(null)
      routeSwipeAnimationTimerRef.current = null
    }, ROUTE_SWIPE_ANIMATION_DURATION_MS)

    navigate(nextPath)
  }

  const handleMainPointerCancel = (event: ReactPointerEvent<HTMLElement>) => {
    releaseRouteSwipePointerCapture(event.currentTarget, routeSwipeStateRef.current.pointerId)
    clearRouteSwipeState()
  }

  return (
    <>
      <div className="relative min-h-screen overflow-x-clip text-foreground">
        <div className="pointer-events-none fixed inset-0 -z-10">
          <div className="absolute -left-36 top-24 h-72 w-72 rounded-full bg-[#6f7f91]/14 blur-[120px]" />
          <div className="absolute -right-20 top-8 h-80 w-80 rounded-full bg-[#596778]/16 blur-[130px]" />
          <div className="absolute bottom-[-120px] left-[22%] h-72 w-72 rounded-full bg-[#4f5d6d]/12 blur-[130px]" />
        </div>

        {/* Desktop Sidebar */}
        <div
          className={cn(
            'hidden lg:fixed lg:bottom-0 lg:top-[var(--app-safe-top)] lg:w-80 lg:flex-col',
            forceMobileShell ? 'lg:hidden' : 'lg:flex'
          )}
        >
          <Sidebar />
        </div>

        {/* Main Content */}
        <div className={cn(!forceMobileShell && 'lg:pl-80')}>
          <Header forceMobileShell={forceMobileShell} />
          <main
            className="px-4 pb-[calc(5.75rem+var(--app-safe-bottom))] pt-5 [touch-action:pan-y] md:px-6 lg:px-6 lg:pb-[calc(2.5rem+var(--app-safe-bottom))]"
            onPointerDown={handleMainPointerDown}
            onPointerUp={handleMainPointerUp}
            onPointerCancel={handleMainPointerCancel}
          >
            <div
              className={cn(
                'mx-auto max-w-[1480px]',
                routeSwipeAnimation === 'next' && 'dashboard-route-swipe-next',
                routeSwipeAnimation === 'prev' && 'dashboard-route-swipe-prev'
              )}
            >
              {isReadOnlyAccess && (
                <Alert className="mb-4 border-amber-300/25 bg-amber-500/10 text-amber-50">
                  <AlertDescription className="flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <span>{t('layout.access.readOnlyBanner')}</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="border-amber-200/30 bg-transparent text-amber-50 hover:bg-amber-500/15"
                      onClick={() => navigate('/dashboard/settings?access_blocked=1')}
                    >
                      {t('layout.access.openSettings')}
                    </Button>
                  </AlertDescription>
                </Alert>
              )}
              <Outlet />
            </div>
          </main>
          <MobileBottomBar
            forceVisible={forceMobileShell}
            extraNavigationEnabled={extraNavigationEnabled}
          />
        </div>
      </div>

      <Dialog open={openLinkPrompt} onOpenChange={setOpenLinkPrompt}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('layout.linkTgTitle')}</DialogTitle>
            <DialogDescription>
              {t('layout.linkTgDesc')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={handleRemindLater}
              disabled={isSavingLater}
            >
              {isSavingLater ? t('layout.linkSaving') : t('layout.linkLater')}
            </Button>
            <Button
              onClick={() => {
                setOpenLinkPrompt(false)
                navigate('/dashboard/settings?focus=telegram')
              }}
            >
              {t('layout.linkNow')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={openForcePasswordPrompt}
        onOpenChange={(open) => {
          if (open || user?.requires_password_change) {
            setOpenForcePasswordPrompt(true)
          }
        }}
      >
        <DialogContent
          showCloseButton={false}
          onEscapeKeyDown={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{t('layout.forcePassword.title')}</DialogTitle>
            <DialogDescription>
              {t('layout.forcePassword.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-1">
            <div className="space-y-2">
              <Label htmlFor="force-current-password">{t('layout.forcePassword.currentPassword')}</Label>
              <Input
                id="force-current-password"
                type="password"
                value={forceCurrentPassword}
                onChange={(event) => setForceCurrentPassword(event.target.value)}
                placeholder={t('layout.forcePassword.currentPasswordPlaceholder')}
                autoComplete="current-password"
                disabled={isForceChanging}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="force-new-password">{t('layout.forcePassword.newPassword')}</Label>
              <Input
                id="force-new-password"
                type="password"
                value={forceNewPassword}
                onChange={(event) => setForceNewPassword(event.target.value)}
                placeholder={t('layout.forcePassword.newPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={isForceChanging}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="force-confirm-password">{t('layout.forcePassword.confirmPassword')}</Label>
              <Input
                id="force-confirm-password"
                type="password"
                value={forceConfirmPassword}
                onChange={(event) => setForceConfirmPassword(event.target.value)}
                placeholder={t('layout.forcePassword.confirmPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={isForceChanging}
              />
            </div>
            {forceError && (
              <p className="text-sm text-red-300">
                {forceError}
              </p>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => {
                void logout()
              }}
              disabled={isForceChanging}
            >
              {t('layout.forcePassword.logout')}
            </Button>
            <Button onClick={handleForcePasswordChange} disabled={isForceChanging}>
              {isForceChanging ? t('layout.forcePassword.changing') : t('layout.forcePassword.change')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={openBootstrapPrompt}
        onOpenChange={(open) => {
          if (open) {
            setOpenBootstrapPrompt(true)
          }
        }}
      >
        <DialogContent
          showCloseButton={false}
          onEscapeKeyDown={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{t('layout.tgBootstrapTitle')}</DialogTitle>
            <DialogDescription>
              {t('layout.tgBootstrapDesc')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-1">
            <div className="space-y-2">
              <Label htmlFor="tg-bootstrap-username">{t('layout.tgBootstrapUsername')}</Label>
              <Input
                id="tg-bootstrap-username"
                value={bootstrapUsername}
                onChange={(event) => setBootstrapUsername(event.target.value)}
                placeholder={t('layout.tgBootstrapUsernamePlaceholder')}
                autoComplete="username"
                disabled={isBootstrapping}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tg-bootstrap-password">{t('layout.tgBootstrapPassword')}</Label>
              <Input
                id="tg-bootstrap-password"
                type="password"
                value={bootstrapPassword}
                onChange={(event) => setBootstrapPassword(event.target.value)}
                placeholder={t('layout.tgBootstrapPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={isBootstrapping}
              />
            </div>
            {bootstrapError && (
              <p className="text-sm text-red-300">
                {bootstrapError}
              </p>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={handleBootstrapLogout}
              disabled={isBootstrapping}
            >
              {t('layout.tgBootstrapLogout')}
            </Button>
            <Button onClick={handleBootstrapCreate} disabled={isBootstrapping}>
              {isBootstrapping ? t('layout.tgBootstrapCreating') : t('layout.tgBootstrapCreate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={openTrialOnboardingPrompt}
        onOpenChange={(open) => {
          if (!open) {
            handleCloseTrialOnboarding()
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('layout.trialOnboarding.title')}</DialogTitle>
            <DialogDescription>
              {t('layout.trialOnboarding.description')}
            </DialogDescription>
          </DialogHeader>

          {trialOnboardingError && (
            <p className="text-sm text-red-300">
              {trialOnboardingError}
            </p>
          )}

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={handleCloseTrialOnboarding}
              disabled={isActivatingTrialOnboarding}
            >
              {t('layout.trialOnboarding.later')}
            </Button>
            <Button onClick={handleActivateTrialOnboarding} disabled={isActivatingTrialOnboarding}>
              {isActivatingTrialOnboarding
                ? t('layout.trialOnboarding.activating')
                : t('layout.trialOnboarding.activate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

function extractApiErrorMessage(error: unknown, fallbackMessage: string): string {
  const backendError = error as {
    response?: {
      data?: {
        detail?: string | { message?: string }
        message?: string
      }
    }
  }
  const detail = backendError.response?.data?.detail
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail
  }
  if (detail && typeof detail === 'object' && typeof detail.message === 'string' && detail.message.trim().length > 0) {
    return detail.message
  }
  const message = backendError.response?.data?.message
  if (typeof message === 'string' && message.trim().length > 0) {
    return message
  }
  return fallbackMessage
}
