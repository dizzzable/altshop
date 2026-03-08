import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  getMobileNavPages,
  isDashboardNavItemActive,
} from '@/components/layout/dashboard-nav'

const MOBILE_NAV_PAGE_SWIPE_THRESHOLD_PX = 50
const MOBILE_NAV_PAGE_SWIPE_MAX_VERTICAL_DRIFT_PX = 36
const MOBILE_NAV_PAGE_SWIPE_MAX_DURATION_MS = 700

interface MobileBottomBarProps {
  forceVisible?: boolean
  extraNavigationEnabled?: boolean
}

export function MobileBottomBar({
  forceVisible = false,
  extraNavigationEnabled = false,
}: MobileBottomBarProps) {
  const location = useLocation()
  const { user } = useAuth()
  const { t } = useI18n()
  const [manualSelection, setManualSelection] = useState<{ pageIndex: number; pathname: string } | null>(null)
  const [pageTransitionDirection, setPageTransitionDirection] = useState<'next' | 'prev' | null>(null)
  const pageTransitionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const swipeHandledRef = useRef(false)
  const swipeStateRef = useRef<{
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

  const isPartnerActive = Boolean(user?.is_partner_active)
  const mobilePages = useMemo(() => getMobileNavPages(isPartnerActive), [isPartnerActive])
  const canTogglePages = mobilePages[1].length > 0
  const matchedPageIndex = mobilePages.findIndex((pageItems) =>
    pageItems.some((item) => isDashboardNavItemActive(location.pathname, item))
  )
  const manualPageIndex = manualSelection?.pathname === location.pathname
    ? manualSelection.pageIndex
    : null
  const activePageIndex = manualPageIndex ?? (matchedPageIndex >= 0 ? matchedPageIndex : 0)
  const currentPageItems = mobilePages[activePageIndex] || mobilePages[0]
  const showPageToggleButton = canTogglePages && !extraNavigationEnabled

  useEffect(() => {
    return () => {
      if (pageTransitionTimerRef.current) {
        clearTimeout(pageTransitionTimerRef.current)
        pageTransitionTimerRef.current = null
      }
    }
  }, [])

  const setPageWithTransition = (nextPageIndex: number) => {
    if (nextPageIndex === activePageIndex) {
      return
    }

    setPageTransitionDirection(nextPageIndex > activePageIndex ? 'next' : 'prev')
    if (pageTransitionTimerRef.current) {
      clearTimeout(pageTransitionTimerRef.current)
    }
    pageTransitionTimerRef.current = setTimeout(() => {
      setPageTransitionDirection(null)
      pageTransitionTimerRef.current = null
    }, 220)

    setManualSelection({
      pageIndex: nextPageIndex,
      pathname: location.pathname,
    })
  }

  const clearSwipeTracking = () => {
    swipeStateRef.current.tracking = false
    swipeStateRef.current.pointerId = null
    swipeStateRef.current.startX = 0
    swipeStateRef.current.startY = 0
    swipeStateRef.current.startTs = 0
  }

  const releaseSwipePointerCapture = (
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

  const handleContainerPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    swipeHandledRef.current = false
    if (!extraNavigationEnabled || !canTogglePages || event.pointerType !== 'touch') {
      clearSwipeTracking()
      return
    }

    swipeStateRef.current.pointerId = event.pointerId
    swipeStateRef.current.startX = event.clientX
    swipeStateRef.current.startY = event.clientY
    swipeStateRef.current.startTs = Date.now()
    swipeStateRef.current.tracking = true
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // Ignore transient pointer capture errors.
    }
  }

  const handleContainerPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    const swipeState = swipeStateRef.current
    const trackedPointerId = swipeState.pointerId
    if (
      !extraNavigationEnabled
      || !canTogglePages
      || !swipeState.tracking
      || swipeState.pointerId !== event.pointerId
    ) {
      releaseSwipePointerCapture(event.currentTarget, trackedPointerId)
      clearSwipeTracking()
      return
    }

    const deltaX = event.clientX - swipeState.startX
    const deltaY = event.clientY - swipeState.startY
    const gestureDuration = Date.now() - swipeState.startTs
    releaseSwipePointerCapture(event.currentTarget, trackedPointerId)
    clearSwipeTracking()

    if (
      Math.abs(deltaX) < MOBILE_NAV_PAGE_SWIPE_THRESHOLD_PX
      || Math.abs(deltaY) > MOBILE_NAV_PAGE_SWIPE_MAX_VERTICAL_DRIFT_PX
      || gestureDuration > MOBILE_NAV_PAGE_SWIPE_MAX_DURATION_MS
    ) {
      return
    }

    const nextPageIndex = deltaX < 0 ? 1 : 0
    if (nextPageIndex === activePageIndex) {
      return
    }

    swipeHandledRef.current = true
    setPageWithTransition(nextPageIndex)
  }

  const handleContainerPointerCancel = (event: ReactPointerEvent<HTMLDivElement>) => {
    releaseSwipePointerCapture(event.currentTarget, swipeStateRef.current.pointerId)
    clearSwipeTracking()
  }

  return (
    <nav
      aria-label={
        extraNavigationEnabled
          ? `${t('layout.controlDesk')}. ${t('layout.mobileNav.swipeHint')}`
          : t('layout.controlDesk')
      }
      className={cn('fixed inset-x-0 bottom-0 z-40', !forceVisible && 'lg:hidden')}
    >
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-[#050608] via-[#050608]/92 to-transparent" />

      <div className="relative px-3 pb-[calc(0.45rem+var(--app-safe-bottom))] pt-2">
        <div
          className="rounded-2xl border border-white/12 bg-[#090c10]/78 [touch-action:pan-y] shadow-[0_20px_45px_-34px_rgba(0,0,0,0.95)] backdrop-blur-xl"
          onPointerDown={handleContainerPointerDown}
          onPointerUp={handleContainerPointerUp}
          onPointerCancel={handleContainerPointerCancel}
          onClickCapture={(event) => {
            if (!swipeHandledRef.current) {
              return
            }
            swipeHandledRef.current = false
            event.preventDefault()
            event.stopPropagation()
          }}
        >
          <div
            className={cn(
              'gap-1 p-1',
              showPageToggleButton ? 'grid grid-cols-4' : 'grid grid-cols-3',
              pageTransitionDirection === 'next' && 'mobile-nav-page-swipe-next',
              pageTransitionDirection === 'prev' && 'mobile-nav-page-swipe-prev'
            )}
          >
            {currentPageItems.map((item) => {
              const isActive = isDashboardNavItemActive(location.pathname, item)

              return (
                <NavLink
                  key={item.href}
                  to={item.href}
                  end={item.end}
                  className={cn(
                    'group flex h-12 min-h-12 w-full items-center justify-center rounded-xl px-1 text-slate-400 transition-all duration-200',
                    isActive
                      ? 'flex-col bg-primary/14 px-2 text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.07)]'
                      : 'hover:bg-white/[0.05] hover:text-slate-200'
                  )}
                  aria-label={t(item.titleKey)}
                >
                  <item.icon
                    className={cn('h-[18px] w-[18px]', isActive ? 'text-primary' : 'text-current')}
                  />
                  {isActive ? (
                    <span className="mt-1 text-[10px] font-semibold leading-none tracking-[0.01em]">
                      {t(item.titleKey)}
                    </span>
                  ) : (
                    <span className="sr-only">{t(item.titleKey)}</span>
                  )}
                </NavLink>
              )
            })}

            {showPageToggleButton && (
              <button
                type="button"
                aria-label={activePageIndex === 0 ? t('layout.mobileNav.next') : t('layout.mobileNav.prev')}
                disabled={!canTogglePages}
                onClick={() => {
                  if (!canTogglePages) {
                    return
                  }
                  setPageWithTransition(activePageIndex === 0 ? 1 : 0)
                }}
                className={cn(
                  'flex h-12 min-h-12 w-full items-center justify-center rounded-xl border border-white/10 text-slate-200 transition-all duration-200',
                  canTogglePages
                    ? 'bg-white/[0.03] hover:bg-white/[0.06]'
                    : 'cursor-not-allowed bg-white/[0.01] text-slate-500'
                )}
              >
                {activePageIndex === 0 ? (
                  <ChevronRight className="h-[18px] w-[18px]" />
                ) : (
                  <ChevronLeft className="h-[18px] w-[18px]" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </nav>
  )
}
