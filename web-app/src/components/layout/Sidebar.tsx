import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useAuth } from '@/components/auth/AuthProvider'
import { useBranding } from '@/components/common/BrandingProvider'
import { useI18n } from '@/components/common/I18nProvider'
import {
  Shield,
} from 'lucide-react'
import {
  getVisibleDashboardNavItems,
  isDashboardNavItemActive,
} from '@/components/layout/dashboard-nav'

const prefetchedRoutes = new Set<string>()

const routePrefetchers: Record<string, () => Promise<unknown>> = {
  '/dashboard': () => import('@/pages/dashboard/DashboardPage'),
  '/dashboard/subscription': () => import('@/pages/dashboard/SubscriptionPage'),
  '/dashboard/devices': () => import('@/pages/dashboard/DevicesPage'),
  '/dashboard/referrals': () => import('@/pages/dashboard/ReferralsPage'),
  '/dashboard/partner': () => import('@/pages/dashboard/PartnerPage'),
  '/dashboard/promocodes': () => import('@/pages/dashboard/PromocodesPage'),
  '/dashboard/settings': () => import('@/pages/dashboard/SettingsPage'),
}

function prefetchRouteChunk(path: string) {
  if (prefetchedRoutes.has(path)) {
    return
  }

  const prefetch = routePrefetchers[path]
  if (!prefetch) {
    return
  }

  prefetchedRoutes.add(path)
  void prefetch()
}

export function Sidebar() {
  const location = useLocation()
  const { user } = useAuth()
  const { projectName } = useBranding()
  const { t } = useI18n()
  const visibleItems = getVisibleDashboardNavItems(Boolean(user?.is_partner_active))

  return (
    <aside className="flex h-full flex-col bg-transparent">
      {/* Logo */}
      <div className="flex h-[72px] items-center px-6">
        <NavLink to="/dashboard" className="flex items-center gap-3 font-semibold">
          <span className="grid h-10 w-10 place-items-center rounded-xl border border-primary/25 bg-primary/12 text-primary shadow-[var(--component-default-button-shadow)]">
            <Shield className="h-[18px] w-[18px]" />
          </span>
          <span>
            <span className="block text-sm uppercase tracking-[0.2em] text-muted-foreground">{projectName}</span>
            <span className="block text-base tracking-tight text-foreground">{t('layout.controlDesk')}</span>
          </span>
        </NavLink>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-2 p-4">
        {visibleItems.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            end={item.end}
            onMouseEnter={() => prefetchRouteChunk(item.href)}
            onFocus={() => prefetchRouteChunk(item.href)}
            className={cn(
              'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
              isDashboardNavItemActive(location.pathname, item)
                ? 'border border-primary/25 bg-primary/10 text-primary shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                : 'border border-transparent text-muted-foreground hover:border-[var(--component-outline-button-border)] hover:bg-[var(--component-outline-button-hover-bg)] hover:text-foreground'
            )}
          >
            <item.icon className="h-4 w-4 text-current" />
            {t(item.titleKey)}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
