import { useEffect, useMemo, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { useAccessStatusQuery } from '@/hooks/useAccessStatusQuery'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { resolveAccessCapabilities } from '@/lib/access-capabilities'
import { cn } from '@/lib/utils'
import {
  readMobileExtraNavigationEnabled,
  subscribeMobileExtraNavigationPreference,
} from '@/lib/mobile-navigation-preferences'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { DashboardLayoutDialogs } from './DashboardLayoutDialogs'
import { Header } from './Header'
import { MobileBottomBar } from './MobileBottomBar'
import { Sidebar } from './Sidebar'
import { useDashboardDialogs } from './useDashboardDialogs'
import { useDashboardRouteSwipe } from './useDashboardRouteSwipe'

export function DashboardLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, refreshUser, logout } = useAuth()
  const { t } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const forceMobileShell = useMobileUiV2
  const isPartnerActive = Boolean(user?.is_partner_active)
  const { data: accessStatus } = useAccessStatusQuery({ enabled: Boolean(user) })
  const { isInTelegram } = useTelegramWebApp()
  const [extraNavigationEnabled, setExtraNavigationEnabled] = useState(() => readMobileExtraNavigationEnabled())
  const accessCapabilities = useMemo(
    () => resolveAccessCapabilities(accessStatus),
    [accessStatus]
  )
  const isReadOnlyAccess = accessCapabilities.isReadOnly
  const isPurchaseBlocked = accessCapabilities.isPurchaseBlocked
  const dialogs = useDashboardDialogs({
    canPurchase: accessCapabilities.canPurchase,
    isInTelegram,
    isPurchaseBlocked,
    logout,
    navigate,
    pathname: location.pathname,
    refreshUser,
    user,
  })
  const {
    routeSwipeAnimation,
    handlePointerDown,
    handlePointerUp,
    handlePointerCancel,
  } = useDashboardRouteSwipe({
    enabled: forceMobileShell,
    isPartnerActive,
    navigate,
    pathname: location.pathname,
  })

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
    if (!user || !accessCapabilities.shouldRedirectToAccessScreen) {
      return
    }
    if (location.pathname === '/dashboard/settings') {
      return
    }

    navigate('/dashboard/settings?access_blocked=1', { replace: true })
  }, [accessCapabilities.shouldRedirectToAccessScreen, location.pathname, navigate, user])

  return (
    <>
      <div className="relative min-h-screen overflow-x-clip text-foreground">
        <div className="pointer-events-none fixed inset-0 -z-10">
          <div className="absolute -left-36 top-24 h-72 w-72 rounded-full bg-[#6f7f91]/14 blur-[120px]" />
          <div className="absolute -right-20 top-8 h-80 w-80 rounded-full bg-[#596778]/16 blur-[130px]" />
          <div className="absolute bottom-[-120px] left-[22%] h-72 w-72 rounded-full bg-[#4f5d6d]/12 blur-[130px]" />
        </div>

        <div
          className={cn(
            'hidden lg:fixed lg:bottom-0 lg:top-[var(--app-safe-top)] lg:w-80 lg:flex-col',
            forceMobileShell ? 'lg:hidden' : 'lg:flex'
          )}
        >
          <Sidebar />
        </div>

        <div className={cn(!forceMobileShell && 'lg:pl-80')}>
          <Header forceMobileShell={forceMobileShell} />
          <main
            className="px-4 pb-[calc(5.75rem+var(--app-safe-bottom))] pt-5 [touch-action:pan-y] md:px-6 lg:px-6 lg:pb-[calc(2.5rem+var(--app-safe-bottom))]"
            onPointerDown={handlePointerDown}
            onPointerUp={handlePointerUp}
            onPointerCancel={handlePointerCancel}
          >
            <div
              className={cn(
                'mx-auto max-w-[1480px]',
                routeSwipeAnimation === 'next' && 'dashboard-route-swipe-next',
                routeSwipeAnimation === 'prev' && 'dashboard-route-swipe-prev'
              )}
            >
              {(isReadOnlyAccess || isPurchaseBlocked) && (
                <Alert className="mb-4 border-amber-300/25 bg-amber-500/10 text-amber-50">
                  <AlertDescription className="flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                    <span>
                      {isPurchaseBlocked
                        ? t('layout.access.purchaseBlockedBanner')
                        : t('layout.access.readOnlyBanner')}
                    </span>
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
      <DashboardLayoutDialogs dialogs={dialogs} />
    </>
  )
}
