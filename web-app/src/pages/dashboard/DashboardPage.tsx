import { useState, type ElementType } from 'react'
import { useAuth } from '@/components/auth/AuthProvider'
import { DashboardKpiCard } from '@/components/dashboard/DashboardKpiCard'
import { DashboardQuickActions } from '@/components/dashboard/DashboardQuickActions'
import { useI18n } from '@/components/common/I18nProvider'
import { SubscriptionUsageCard } from '@/components/dashboard/SubscriptionUsageCard'
import { useAccessStatusQuery } from '@/hooks/useAccessStatusQuery'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { useSubscriptionsQuery } from '@/hooks/useSubscriptionsQuery'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { api } from '@/lib/api'
import { aggregateDeviceStats, getActiveSubscriptions } from '@/lib/dashboard-metrics'
import infoSquareIcon from '@/assets/icons/info-square.svg'
import { cn } from '@/lib/utils'
import { useQuery } from '@tanstack/react-query'
import { AlertCircle, CreditCard, Shield, Smartphone, Ticket, Users, Wallet } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { PartnerInfo } from '@/types'

function getCurrencyFractionDigits(currency: string): number {
  if (currency === 'BTC') {
    return 8
  }
  if (
    currency === 'TON'
    || currency === 'ETH'
    || currency === 'LTC'
    || currency === 'BNB'
    || currency === 'DASH'
    || currency === 'SOL'
    || currency === 'XMR'
    || currency === 'TRX'
  ) {
    return 6
  }
  return 2
}

type DashboardKpiCardItem = {
  key: string
  title: string
  value: string
  description: string
  icon: ElementType
  loading?: boolean
  error?: boolean
  tone?: 'neutral' | 'success' | 'danger' | 'warning'
}

export function DashboardPage() {
  const { user, isLoading: authLoading } = useAuth()
  const { t, locale } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const isPartnerActive = Boolean(user?.is_partner_active)
  const { data: accessStatus } = useAccessStatusQuery({ enabled: !authLoading })
  const isReadOnlyAccess = accessStatus?.access_level === 'read_only'
  const [kpiDialogOpen, setKpiDialogOpen] = useState(false)

  const subscriptionsQuery = useSubscriptionsQuery()

  const referralQuery = useQuery({
    queryKey: ['referral-info'],
    queryFn: () => api.referral.info().then((response) => response.data),
    enabled: !isPartnerActive,
  })
  const partnerQuery = useQuery<PartnerInfo>({
    queryKey: ['partner-info'],
    queryFn: () => api.partner.info().then((response) => response.data),
    enabled: isPartnerActive,
  })

  if (authLoading) {
    return <DashboardPageSkeleton />
  }

  const subscriptions = subscriptionsQuery.data ?? []
  const activeSubscriptions = getActiveSubscriptions(subscriptions)
  const devices = aggregateDeviceStats(subscriptions)

  const subscriptionError = subscriptionsQuery.isError
  const referralError = !isPartnerActive && referralQuery.isError
  const partnerError = isPartnerActive && partnerQuery.isError

  const displayName = user?.name || user?.username || t('common.userFallback')
  const personalDiscount = user?.personal_discount ?? 0
  const purchaseDiscount = user?.purchase_discount ?? 0
  const hasDiscounts = personalDiscount > 0 || purchaseDiscount > 0

  const referralPoints = referralQuery.data?.points ?? 0
  const referralCount = referralQuery.data?.referral_count ?? 0
  const partnerInfo = partnerQuery.data
  const partnerReferralsCount =
    (partnerInfo?.referrals_count ?? 0) +
    (partnerInfo?.level2_referrals_count ?? 0) +
    (partnerInfo?.level3_referrals_count ?? 0)
  const partnerCurrency = partnerInfo?.effective_currency ?? 'RUB'
  const partnerBalanceValue = partnerInfo?.balance_display ?? ((partnerInfo?.balance ?? 0) / 100)
  const partnerBalanceLabel = `${new Intl.NumberFormat(locale === 'ru' ? 'ru-RU' : 'en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: getCurrencyFractionDigits(partnerCurrency),
  }).format(partnerBalanceValue)} ${partnerCurrency}`
  const partnerValue = partnerError
    ? t('common.unavailable')
    : t('dashboard.kpi.partnerBalance', { amount: partnerBalanceLabel })
  const partnerDescription = partnerError
    ? t('dashboard.kpi.partnerDown')
    : partnerInfo?.is_active === false
      ? t('dashboard.kpi.partnerInactive')
      : t('dashboard.kpi.partnerDesc', { count: partnerReferralsCount })

  const devicesValue = subscriptionError
    ? t('common.unavailable')
    : devices.unlimited
      ? `${devices.used}/${t('devices.unlimited')}`
      : `${devices.used}/${devices.limit}`
  const devicesDescription = subscriptionError
    ? t('dashboard.kpi.devicesDown')
    : devices.unlimited
      ? t('dashboard.kpi.devicesUnlimited')
      : t('dashboard.kpi.devicesSlots', { count: devices.available })

  const kpiCards: DashboardKpiCardItem[] = [
    isPartnerActive
      ? {
          key: 'partner',
          title: t('dashboard.kpi.partner'),
          value: partnerValue,
          description: partnerDescription,
          icon: Wallet,
          loading: partnerQuery.isLoading,
          error: partnerError,
          tone: partnerError ? 'neutral' : 'success',
        }
      : {
          key: 'referrals',
          title: t('dashboard.kpi.referrals'),
          value: referralError ? t('common.unavailable') : t('dashboard.kpi.referralPoints', { count: referralPoints }),
          description: referralError
            ? t('dashboard.kpi.referralsDown')
            : t('dashboard.kpi.referralsDesc', { count: referralCount }),
          icon: Users,
          loading: referralQuery.isLoading,
          error: referralError,
          tone: 'neutral',
        },
    {
      key: 'devices',
      title: t('dashboard.kpi.devices'),
      value: devicesValue,
      description: devicesDescription,
      icon: Smartphone,
      loading: subscriptionsQuery.isLoading,
      error: subscriptionError,
      tone: 'neutral',
    },
    {
      key: 'account',
      title: t('dashboard.kpi.account'),
      value: user?.is_blocked ? t('dashboard.kpi.blocked') : t('dashboard.kpi.active'),
      description: t('dashboard.kpi.accountDesc', { role: user?.role || 'USER' }),
      icon: Shield,
      tone: user?.is_blocked ? 'danger' : 'success',
    },
    {
      key: 'promocodes',
      title: t('dashboard.kpi.promocodes'),
      value: `${personalDiscount}% / ${purchaseDiscount}%`,
      description: hasDiscounts ? t('dashboard.kpi.promocodesDesc') : t('dashboard.kpi.promocodesNone'),
      icon: Ticket,
      tone: hasDiscounts ? 'success' : 'neutral',
    },
  ]

  return (
    <>
      <div className="space-y-6">
        <div className={cn('flex gap-3', useMobileUiV2 ? 'items-start justify-between' : 'items-end justify-between')}>
          <div>
            <h1 className={cn('font-bold tracking-tight text-slate-100', useMobileUiV2 ? 'text-2xl' : 'text-3xl')}>
              {t('dashboard.title', { name: displayName })}
            </h1>
            {!useMobileUiV2 && <p className="text-sm text-slate-400">{t('dashboard.subtitle')}</p>}
          </div>
          {useMobileUiV2 && (
            <Button
              type="button"
              size="icon"
              variant="outline"
              className="h-11 w-11 shrink-0 border-white/15 bg-white/[0.03] text-slate-100 hover:bg-white/[0.08]"
              aria-label={t('dashboard.mobile.kpiOpen')}
              onClick={() => setKpiDialogOpen(true)}
            >
              <img src={infoSquareIcon} alt="" className="h-4 w-4" />
            </Button>
          )}
        </div>

        {isReadOnlyAccess && (
          <Card className="border-amber-300/25 bg-amber-500/10">
            <CardContent className="py-4">
              <p className="text-sm text-amber-100">{t('dashboard.readOnlyNotice')}</p>
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 xl:grid-cols-12">
          <section className="space-y-4 xl:col-span-9">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">{t('dashboard.activeTitle')}</h2>
                {!useMobileUiV2 && (
                  <p className="text-sm text-slate-400">
                    {t('dashboard.activeDesc')}
                  </p>
                )}
              </div>
              {!subscriptionError && !subscriptionsQuery.isLoading && (
                <span className="rounded-full border border-white/12 bg-white/[0.03] px-3 py-1 text-xs font-medium text-slate-300">
                  {t('dashboard.activeBadge', { active: activeSubscriptions.length, total: subscriptions.length })}
                </span>
              )}
            </div>

            {subscriptionError && (
              <Card className="border-destructive/40 bg-destructive/10">
                <CardContent className="py-4">
                  <p className="flex items-center gap-2 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4" />
                    {t('dashboard.subsUnavailable')}
                  </p>
                </CardContent>
              </Card>
            )}

            {!subscriptionError && subscriptionsQuery.isLoading && <SubscriptionsListSkeleton />}

            {!subscriptionError && !subscriptionsQuery.isLoading && activeSubscriptions.length === 0 && (
              <Card className="border-white/10 bg-card/90">
                <CardContent className="py-10 text-center">
                  <CreditCard className="mx-auto mb-4 h-10 w-10 text-slate-500" />
                  <p className="text-base font-medium text-slate-100">{t('dashboard.noActiveTitle')}</p>
                  <p className="mt-1 text-sm text-slate-400">{t('dashboard.noActiveDesc')}</p>
                  <Button asChild={!isReadOnlyAccess} className="mt-5" disabled={isReadOnlyAccess}>
                    {isReadOnlyAccess ? (
                      <span>{t('dashboard.purchase')}</span>
                    ) : (
                      <Link to="/dashboard/subscription/purchase">{t('dashboard.purchase')}</Link>
                    )}
                  </Button>
                </CardContent>
              </Card>
            )}

            {!subscriptionError && !subscriptionsQuery.isLoading && activeSubscriptions.length > 0 && (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {activeSubscriptions.map((subscription) => (
                  <SubscriptionUsageCard key={subscription.id} subscription={subscription} />
                ))}
              </div>
            )}
          </section>

          {!useMobileUiV2 && (
            <aside className="xl:col-span-3">
              <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2">
                {kpiCards.map((card) => (
                  <DashboardKpiCard
                    key={card.key}
                    title={card.title}
                    value={card.value}
                    description={card.description}
                    icon={card.icon}
                    loading={card.loading}
                    error={card.error}
                    tone={card.tone}
                  />
                ))}
              </div>
            </aside>
          )}
        </div>

        <DashboardQuickActions />
      </div>

      {useMobileUiV2 && (
        <Dialog open={kpiDialogOpen} onOpenChange={setKpiDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{t('dashboard.mobile.kpiTitle')}</DialogTitle>
              <DialogDescription>{t('dashboard.mobile.kpiDesc')}</DialogDescription>
            </DialogHeader>
            <div className="grid gap-3">
              {kpiCards.map((card) => (
                <DashboardKpiCard
                  key={card.key}
                  title={card.title}
                  value={card.value}
                  description={card.description}
                  icon={card.icon}
                  loading={card.loading}
                  error={card.error}
                  tone={card.tone}
                  className="min-h-[128px]"
                />
              ))}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}

function DashboardPageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-4 w-[420px] max-w-full" />
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="grid gap-3 sm:grid-cols-2 xl:col-span-9 xl:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <Card key={item} className="border-white/10 bg-card/90">
              <CardContent className="space-y-3 py-4">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-5 w-36" />
                  <Skeleton className="h-5 w-16" />
                </div>
                <Skeleton className="h-2 w-full" />
                <Skeleton className="h-2 w-full" />
                <div className="flex gap-2">
                  <Skeleton className="h-7 w-20" />
                  <Skeleton className="h-7 w-20" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 xl:col-span-3">
          {[1, 2, 3, 4].map((item) => (
            <Card key={item} className="border-white/10 bg-card/90">
              <CardContent className="space-y-3 py-5">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-28" />
                <Skeleton className="h-3 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}

function SubscriptionsListSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[1, 2, 3, 4].map((item) => (
        <Card key={item} className="border-white/10 bg-card/90">
          <CardContent className="space-y-3 py-4">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-36" />
              <Skeleton className="h-5 w-16" />
            </div>
            <Skeleton className="h-2 w-full" />
            <Skeleton className="h-2 w-full" />
            <div className="flex gap-2">
              <Skeleton className="h-7 w-20" />
              <Skeleton className="h-7 w-20" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
