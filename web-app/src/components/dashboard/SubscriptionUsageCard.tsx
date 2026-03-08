import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  calculateUsagePercent,
  formatAbsoluteDate,
  formatExpiryLabel,
  isExpiringSoon,
  isUnlimitedLimit,
} from '@/lib/dashboard-metrics'
import { useI18n } from '@/components/common/I18nProvider'
import { cn, formatBytes, gigabytesToBytes } from '@/lib/utils'
import { openExternalLink } from '@/lib/openExternalLink'
import {
  formatLimitLabel,
  formatPlanTypeLabel,
  getSubscriptionDeviceSummary,
} from '@/lib/subscription-display'
import type { Subscription } from '@/types'
import { CalendarClock, Clock3, Copy, Link2, RefreshCw, Smartphone } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

interface SubscriptionUsageCardProps {
  subscription: Subscription
}

const statusConfig: Record<string, { labelKey: string; className: string }> = {
  ACTIVE: {
    labelKey: 'subscription.status.active',
    className: 'border-emerald-300/30 bg-emerald-500/15 text-emerald-100',
  },
  EXPIRED: {
    labelKey: 'subscription.status.expired',
    className: 'border-red-300/30 bg-red-500/15 text-red-100',
  },
  LIMITED: {
    labelKey: 'subscription.status.limited',
    className: 'border-amber-300/30 bg-amber-500/15 text-amber-100',
  },
  DISABLED: {
    labelKey: 'subscription.status.disabled',
    className: 'border-slate-400/20 bg-slate-500/12 text-slate-200',
  },
  DELETED: {
    labelKey: 'subscription.status.deleted',
    className: 'border-slate-400/20 bg-slate-500/12 text-slate-300',
  },
}

export function SubscriptionUsageCard({ subscription }: SubscriptionUsageCardProps) {
  const { t } = useI18n()
  const status = statusConfig[subscription.status] ?? statusConfig.ACTIVE
  const expiresSoon = isExpiringSoon(subscription.expire_at, 7)
  const unlimitedLabel = t('subscription.card.unlimited')
  const planTypeLabel = formatPlanTypeLabel(subscription.plan.type, t)
  const deviceSummary = getSubscriptionDeviceSummary(subscription, t)
  const planDuration =
    subscription.plan.duration <= 0
      ? t('subscription.card.lifetime')
      : t('subscription.card.durationDays', { days: subscription.plan.duration })
  const trafficLimitBytes = gigabytesToBytes(subscription.traffic_limit)
  const trafficLimitLabel = subscription.traffic_limit <= 0 ? unlimitedLabel : formatBytes(trafficLimitBytes)
  const deviceLimitLabel = formatLimitLabel(subscription.device_limit, unlimitedLabel)

  const trafficUnlimited = isUnlimitedLimit(subscription.traffic_limit)
  const trafficPercent = calculateUsagePercent(subscription.traffic_used, trafficLimitBytes)
  const trafficValue = trafficUnlimited
    ? `${formatBytes(Math.max(subscription.traffic_used, 0))} / ${unlimitedLabel}`
    : `${formatBytes(Math.max(subscription.traffic_used, 0))} / ${formatBytes(Math.max(trafficLimitBytes, 0))}`

  const devicesUnlimited = isUnlimitedLimit(subscription.device_limit)
  const devicesPercent = calculateUsagePercent(subscription.devices_count, subscription.device_limit)
  const deviceValue = devicesUnlimited
    ? `${subscription.devices_count} / ${unlimitedLabel}`
    : `${subscription.devices_count} / ${Math.max(subscription.device_limit, 0)}`

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(subscription.url)
      toast.success(t('subscription.card.linkCopied'))
    } catch {
      toast.error(t('subscription.card.linkCopyFailed'))
    }
  }

  function handleConnectLink() {
    if (!openExternalLink(subscription.url)) {
      toast.error(t('common.openLinkFailed'))
    }
  }

  return (
    <Card
      className={cn(
        'h-full border-white/10 bg-[#0a0d11]/90 shadow-[0_16px_34px_-24px_rgba(0,0,0,0.95)]',
        expiresSoon && 'border-amber-300/25 bg-amber-500/[0.05]'
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg text-slate-100">{subscription.plan.name}</CardTitle>
            <CardDescription className="mt-1 flex items-center gap-1.5 text-xs text-slate-400">
              <span className="shrink-0">{deviceSummary.emoji}</span>
              <span className="truncate">
                {deviceSummary.label} / {deviceSummary.countLabel} / {deviceSummary.limitLabel}
              </span>
            </CardDescription>
          </div>
          <Badge variant="outline" className={status.className}>
            {t(status.labelKey)}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-1.5">
          <span className="rounded-full border border-white/12 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-200">
            {t('subscription.card.type')}: {planTypeLabel}
          </span>
          <span className="rounded-full border border-white/12 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-200">
            {t('subscription.card.duration')}: {planDuration}
          </span>
          <span className="rounded-full border border-white/12 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-200">
            {t('subscription.card.traffic')}: {trafficLimitLabel}
          </span>
          <span className="rounded-full border border-white/12 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-200">
            {t('subscription.card.devices')}: {deviceLimitLabel}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
          <div className="flex items-center gap-2 text-slate-400">
            <CalendarClock className="h-3.5 w-3.5" />
            <span>{t('subscription.card.purchased')}: {formatAbsoluteDate(subscription.created_at)}</span>
          </div>
          <div className={cn('flex items-center gap-2', expiresSoon ? 'text-amber-200' : 'text-slate-300')}>
            <Clock3 className="h-3.5 w-3.5" />
            <span>
              {formatAbsoluteDate(subscription.expire_at)} ({formatExpiryLabel(subscription.expire_at)})
            </span>
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">{t('subscription.card.traffic')}</span>
            <span className="font-medium text-slate-200">{trafficValue}</span>
          </div>
          {trafficUnlimited ? (
            <div className="h-1.5 rounded-full bg-emerald-400/25" />
          ) : (
            <Progress value={trafficPercent} className="h-1.5" />
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">{t('subscription.card.devices')}</span>
            <span className="font-medium text-slate-200">{deviceValue}</span>
          </div>
          {devicesUnlimited ? (
            <div className="h-1.5 rounded-full bg-sky-400/25" />
          ) : (
            <Progress value={devicesPercent} className="h-1.5" />
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <Button
            asChild
            size="sm"
            variant="outline"
            className="h-8 inline-flex items-center justify-center gap-1.5 border-white/15 bg-white/[0.03] px-2.5 leading-none text-slate-100 hover:bg-white/[0.08]"
          >
            <Link
              to={`/dashboard/devices?subscription=${subscription.id}`}
              className="inline-flex items-center justify-center gap-1.5 leading-none"
            >
              <Smartphone className="h-3.5 w-3.5 shrink-0" />
              <span className="leading-none">{t('subscription.card.manage')}</span>
            </Link>
          </Button>

          <Button
            asChild
            size="sm"
            variant="outline"
            className="h-8 inline-flex items-center justify-center gap-1.5 border-white/15 bg-white/[0.03] px-2.5 leading-none text-slate-100 hover:bg-white/[0.08]"
          >
            <Link
              to={`/dashboard/subscription/${subscription.id}/renew`}
              className="inline-flex items-center justify-center gap-1.5 leading-none"
            >
              <RefreshCw className="h-3.5 w-3.5 shrink-0" />
              <span className="leading-none">{t('subscription.card.renew')}</span>
            </Link>
          </Button>

          <Button
            size="sm"
            variant="default"
            className="h-8 inline-flex items-center justify-center gap-1.5 px-2.5 leading-none"
            onClick={handleConnectLink}
          >
            <Link2 className="h-3.5 w-3.5 shrink-0" />
            <span className="leading-none">{t('subscription.card.connect')}</span>
          </Button>

          <Button
            size="sm"
            variant="ghost"
            className="h-8 inline-flex items-center justify-center gap-1.5 px-2.5 leading-none text-slate-300 hover:bg-white/[0.07] hover:text-slate-100"
            onClick={handleCopyLink}
          >
            <Copy className="h-3.5 w-3.5 shrink-0" />
            <span className="leading-none">{t('subscription.card.copyLink')}</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
