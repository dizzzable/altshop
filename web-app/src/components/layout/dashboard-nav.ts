import {
  CreditCard,
  Handshake,
  LayoutDashboard,
  type LucideIcon,
  Settings,
  Smartphone,
  Ticket,
  Users,
} from 'lucide-react'

export type MobileNavSwipeDirection = 'next' | 'prev'

export interface DashboardNavItem {
  titleKey: string
  href: string
  icon: LucideIcon
  end?: boolean
}

const dashboardNavItems: readonly DashboardNavItem[] = [
  {
    titleKey: 'nav.dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
    end: true,
  },
  {
    titleKey: 'nav.subscription',
    href: '/dashboard/subscription',
    icon: CreditCard,
  },
  {
    titleKey: 'nav.devices',
    href: '/dashboard/devices',
    icon: Smartphone,
  },
  {
    titleKey: 'nav.referrals',
    href: '/dashboard/referrals',
    icon: Users,
  },
  {
    titleKey: 'nav.partner',
    href: '/dashboard/partner',
    icon: Handshake,
  },
  {
    titleKey: 'nav.promocodes',
    href: '/dashboard/promocodes',
    icon: Ticket,
  },
  {
    titleKey: 'nav.settings',
    href: '/dashboard/settings',
    icon: Settings,
  },
]

export function getVisibleDashboardNavItems(isPartnerActive: boolean): DashboardNavItem[] {
  return isPartnerActive
    ? dashboardNavItems.filter((item) => item.href !== '/dashboard/referrals')
    : [...dashboardNavItems]
}

const MOBILE_NAV_ACTIVE_LAYOUT: readonly [readonly string[], readonly string[]] = [
  ['/dashboard/subscription', '/dashboard/partner', '/dashboard/settings'],
  ['/dashboard/devices', '/dashboard/promocodes', '/dashboard'],
]

const MOBILE_NAV_INACTIVE_LAYOUT: readonly [readonly string[], readonly string[]] = [
  ['/dashboard/subscription', '/dashboard/referrals', '/dashboard/settings'],
  ['/dashboard/devices', '/dashboard/promocodes', '/dashboard'],
]

function resolveMobileNavPage(
  targets: readonly string[],
  byHref: ReadonlyMap<string, DashboardNavItem>
): DashboardNavItem[] {
  return targets
    .map((href) => byHref.get(href))
    .filter((item): item is DashboardNavItem => Boolean(item))
}

export function getMobileNavPages(isPartnerActive: boolean): [DashboardNavItem[], DashboardNavItem[]] {
  const layout = isPartnerActive ? MOBILE_NAV_ACTIVE_LAYOUT : MOBILE_NAV_INACTIVE_LAYOUT
  const byHref = new Map(dashboardNavItems.map((item) => [item.href, item] as const))
  const pageOne = resolveMobileNavPage(layout[0], byHref)
  const pageTwo = resolveMobileNavPage(layout[1], byHref)
  return [pageOne, pageTwo]
}

function normalizePathname(pathname: string): string {
  const normalized = pathname.trim()
  if (!normalized) {
    return '/'
  }
  if (normalized.length > 1 && normalized.endsWith('/')) {
    return normalized.slice(0, -1)
  }
  return normalized
}

function getMobileNavSwipeSequence(isPartnerActive: boolean): string[] {
  const [firstPage, secondPage] = getMobileNavPages(isPartnerActive)
  return [...firstPage, ...secondPage].map((item) => item.href)
}

export function resolveMobileNavRootHref(pathname: string, isPartnerActive: boolean): string | null {
  const normalizedPath = normalizePathname(pathname)
  const sequence = getMobileNavSwipeSequence(isPartnerActive)
  return sequence.find((href) => normalizePathname(href) === normalizedPath) || null
}

export function resolveAdjacentMobileNavHref(
  pathname: string,
  direction: MobileNavSwipeDirection,
  isPartnerActive: boolean
): string | null {
  const sequence = getMobileNavSwipeSequence(isPartnerActive)
  const currentHref = resolveMobileNavRootHref(pathname, isPartnerActive)
  if (!currentHref) {
    return null
  }

  const currentIndex = sequence.indexOf(currentHref)
  if (currentIndex < 0) {
    return null
  }

  if (direction === 'next') {
    return sequence[currentIndex + 1] || null
  }
  return sequence[currentIndex - 1] || null
}

export function isDashboardNavItemActive(pathname: string, item: DashboardNavItem): boolean {
  if (item.end) {
    return pathname === item.href
  }

  return pathname === item.href || pathname.startsWith(`${item.href}/`)
}
