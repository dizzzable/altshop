import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import type { NavigateFunction } from 'react-router-dom'
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

interface UseDashboardRouteSwipeOptions {
  enabled: boolean
  isPartnerActive: boolean
  navigate: NavigateFunction
  pathname: string
}

function isRouteSwipeInteractiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) {
    return false
  }
  return Boolean(target.closest(ROUTE_SWIPE_INTERACTIVE_SELECTOR))
}

export function useDashboardRouteSwipe({
  enabled,
  isPartnerActive,
  navigate,
  pathname,
}: UseDashboardRouteSwipeOptions) {
  const [routeSwipeAnimation, setRouteSwipeAnimation] = useState<'next' | 'prev' | null>(null)
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
    () => Boolean(enabled && resolveMobileNavRootHref(pathname, isPartnerActive)),
    [enabled, isPartnerActive, pathname]
  )

  useEffect(() => {
    return () => {
      if (routeSwipeAnimationTimerRef.current) {
        clearTimeout(routeSwipeAnimationTimerRef.current)
        routeSwipeAnimationTimerRef.current = null
      }
    }
  }, [])

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
    if (
      typeof target.hasPointerCapture !== 'function'
      || typeof target.releasePointerCapture !== 'function'
    ) {
      return
    }
    if (!target.hasPointerCapture(pointerId)) {
      return
    }
    target.releasePointerCapture(pointerId)
  }

  const handlePointerDown = (event: ReactPointerEvent<HTMLElement>) => {
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

  const handlePointerUp = (event: ReactPointerEvent<HTMLElement>) => {
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
    const nextPath = resolveAdjacentMobileNavHref(pathname, swipeDirection, isPartnerActive)
    if (!nextPath || nextPath === pathname) {
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

  const handlePointerCancel = (event: ReactPointerEvent<HTMLElement>) => {
    releaseRouteSwipePointerCapture(event.currentTarget, routeSwipeStateRef.current.pointerId)
    clearRouteSwipeState()
  }

  return {
    routeSwipeAnimation,
    handlePointerDown,
    handlePointerUp,
    handlePointerCancel,
  }
}
