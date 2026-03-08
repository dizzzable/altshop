import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/components/auth/AuthProvider'
import { useBranding } from '@/components/common/BrandingProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { translateWithLocale, type TranslationParams } from '@/i18n/runtime'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { useSubscriptionsQuery } from '@/hooks/useSubscriptionsQuery'
import { api } from '@/lib/api'
import { cn, formatRelativeTime } from '@/lib/utils'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Users,
  Copy,
  Share2,
  QrCode,
  TrendingUp,
  Gift,
  CheckCircle2,
  Activity,
  ChevronRight,
  Info,
} from 'lucide-react'
import { toast } from 'sonner'
import { addStoredGiftPromocode } from '@/lib/gift-promocodes'
import type {
  PointsExchangeType,
  Referral,
  ReferralEvent,
  ReferralExchangeExecuteRequest,
  ReferralExchangeExecuteResponse,
  ReferralExchangeTypeOption,
  ReferralInfo,
  ReferralListResponse,
  Subscription,
  SubscriptionStatus,
} from '@/types'

type ReferralTarget = 'telegram' | 'web'
type ReferralsLocale = 'ru' | 'en'

type ReferralActivityPoint = {
  key: string
  label: string
  invited: number
  qualified: number
}

const EXCHANGEABLE_SUBSCRIPTION_STATUSES: SubscriptionStatus[] = ['ACTIVE', 'EXPIRED', 'LIMITED']
const RECENT_REFERRALS_LIMIT = 5
const REFERRAL_ACTIVITY_DAYS = 14

function translateText(
  locale: ReferralsLocale,
  key: string,
  params?: TranslationParams
): string {
  return translateWithLocale(locale, key, params)
}

function formatText(template: string, params: TranslationParams): string {
  return Object.entries(params).reduce(
    (accumulator, [key, value]) => accumulator.replaceAll(`{${key}}`, String(value)),
    template
  )
}

function getExchangeTypeLabel(type: PointsExchangeType, locale: ReferralsLocale): string {
  if (type === 'SUBSCRIPTION_DAYS') {
    return translateText(locale, 'referrals.auto.001')
  }
  if (type === 'GIFT_SUBSCRIPTION') {
    return translateText(locale, 'referrals.auto.002')
  }
  if (type === 'DISCOUNT') {
    return translateText(locale, 'referrals.auto.003')
  }
  return translateText(locale, 'referrals.auto.004')
}

export function ReferralsPage() {
  const { user, refreshUser } = useAuth()
  const { locale } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const { projectName } = useBranding()
  const referralLocale: ReferralsLocale = locale === 'en' ? 'en' : 'ru'
  const queryClient = useQueryClient()
  const isPartnerActive = Boolean(user?.is_partner_active)
  const [qrDialogOpen, setQrDialogOpen] = useState(false)
  const [qrTarget, setQrTarget] = useState<ReferralTarget>('telegram')
  const [selectedExchangeType, setSelectedExchangeType] = useState<PointsExchangeType | null>(null)
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string>('')
  const [selectedGiftPlanId, setSelectedGiftPlanId] = useState<string>('')
  const [exchangeDialogOpen, setExchangeDialogOpen] = useState(false)
  const [kpiInfoDialogOpen, setKpiInfoDialogOpen] = useState(false)
  const [fullHistoryOpen, setFullHistoryOpen] = useState(false)

  const { data: referralInfo, isLoading: infoLoading } = useQuery<ReferralInfo>({
    queryKey: ['referral-info'],
    queryFn: () => api.referral.info().then((response) => response.data),
    enabled: !isPartnerActive,
  })

  const { data: referralList, isLoading: listLoading } = useQuery<ReferralListResponse>({
    queryKey: ['referrals'],
    queryFn: () => api.referral.list().then((response) => response.data),
    enabled: !isPartnerActive,
  })

  const { data: exchangeOptions, isLoading: exchangeLoading } = useQuery({
    queryKey: ['referral-exchange-options'],
    queryFn: () => api.referral.exchangeOptions().then((response) => response.data),
    enabled: !isPartnerActive,
  })

  const { data: subscriptionsData = [] } = useSubscriptionsQuery({
    enabled: !isPartnerActive,
  })

  const { data: qrBlob, isLoading: qrLoading } = useQuery<Blob>({
    queryKey: ['referral-qr', qrTarget],
    queryFn: () => api.referral.qr(qrTarget).then((response) => response.data),
    enabled: qrDialogOpen && !isPartnerActive,
  })

  const qrImageUrl = useMemo(() => (qrBlob ? URL.createObjectURL(qrBlob) : null), [qrBlob])

  useEffect(() => {
    if (!qrImageUrl) {
      return
    }

    return () => {
      URL.revokeObjectURL(qrImageUrl)
    }
  }, [qrImageUrl])

  const subscriptions = subscriptionsData
  const exchangeableSubscriptions = useMemo(
    () =>
      subscriptions.filter(
        (subscription) =>
          EXCHANGEABLE_SUBSCRIPTION_STATUSES.includes(subscription.status) && !isUnlimited(subscription)
      ),
    [subscriptions]
  )

  const availableExchangeTypes = useMemo(
    () => (exchangeOptions?.types ?? []).filter((option) => option.enabled && option.available),
    [exchangeOptions?.types]
  )
  const giftPlans = useMemo(() => exchangeOptions?.gift_plans ?? [], [exchangeOptions?.gift_plans])

  const effectiveSelectedExchangeType = useMemo(() => {
    if (availableExchangeTypes.length === 0) {
      return null
    }

    if (
      selectedExchangeType &&
      availableExchangeTypes.some((option) => option.type === selectedExchangeType)
    ) {
      return selectedExchangeType
    }

    return availableExchangeTypes[0].type
  }, [availableExchangeTypes, selectedExchangeType])

  const selectedExchangeOption = useMemo(
    () =>
      availableExchangeTypes.find((option) => option.type === effectiveSelectedExchangeType) ?? null,
    [availableExchangeTypes, effectiveSelectedExchangeType]
  )
  const selectedExchangeLabel = selectedExchangeOption
    ? getExchangeTypeLabel(selectedExchangeOption.type, referralLocale)
    : null

  const selectedSubscriptionValue = useMemo(() => {
    if (!selectedExchangeOption?.requires_subscription || exchangeableSubscriptions.length === 0) {
      return ''
    }

    if (
      selectedSubscriptionId &&
      exchangeableSubscriptions.some(
        (subscription) => subscription.id.toString() === selectedSubscriptionId
      )
    ) {
      return selectedSubscriptionId
    }

    return exchangeableSubscriptions[0].id.toString()
  }, [exchangeableSubscriptions, selectedExchangeOption, selectedSubscriptionId])

  const selectedGiftPlanValue = useMemo(() => {
    if (selectedExchangeOption?.type !== 'GIFT_SUBSCRIPTION' || giftPlans.length === 0) {
      return ''
    }

    if (selectedGiftPlanId && giftPlans.some((plan) => plan.plan_id.toString() === selectedGiftPlanId)) {
      return selectedGiftPlanId
    }

    const preferredPlanId = selectedExchangeOption.gift_plan_id?.toString()
    if (preferredPlanId && giftPlans.some((plan) => plan.plan_id.toString() === preferredPlanId)) {
      return preferredPlanId
    }

    return giftPlans[0].plan_id.toString()
  }, [giftPlans, selectedExchangeOption, selectedGiftPlanId])

  const executeExchangeMutation = useMutation({
    mutationFn: (payload: ReferralExchangeExecuteRequest) =>
      api.referral.exchangeExecute(payload).then((response) => response.data),
    onSuccess: async (result: ReferralExchangeExecuteResponse) => {
      if (result.exchange_type === 'GIFT_SUBSCRIPTION' && result.result.gift_promocode) {
        addStoredGiftPromocode(result.result.gift_promocode)
      }
      toast.success(buildExchangeSuccessMessage(result, referralLocale))

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['referral-info'] }),
        queryClient.invalidateQueries({ queryKey: ['referrals'] }),
        queryClient.invalidateQueries({ queryKey: ['referral-exchange-options'] }),
        queryClient.invalidateQueries({ queryKey: ['subscriptions'] }),
        queryClient.invalidateQueries({ queryKey: ['user-profile'] }),
      ])
      await refreshUser()
    },
    onError: (error: unknown) => {
      const detail = extractExchangeError(error, referralLocale)
      toast.error(detail)
    },
  })

  const referrals = useMemo(() => referralList?.referrals ?? [], [referralList?.referrals])
  const sortedReferrals = useMemo(
    () => [...referrals].sort((left, right) => getReferralSortTimestamp(right) - getReferralSortTimestamp(left)),
    [referrals]
  )
  const recentReferrals = useMemo(
    () => sortedReferrals.slice(0, RECENT_REFERRALS_LIMIT),
    [sortedReferrals]
  )
  const referralActivitySeries = useMemo(
    () => buildReferralActivitySeries(sortedReferrals, referralLocale, REFERRAL_ACTIVITY_DAYS),
    [referralLocale, sortedReferrals]
  )

  if (isPartnerActive) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{translateText(referralLocale, 'referrals.auto.005')}</CardTitle>
          <CardDescription>
            {translateText(referralLocale, 'referrals.auto.006')}
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (infoLoading) {
    return <ReferralsSkeleton />
  }
  const activeReferrals = referrals.filter((referral) => referral.is_active).length
  const qualifiedReferrals =
    referralInfo?.qualified_referral_count ??
    referrals.filter((referral) => referral.is_qualified ?? Boolean(referral.qualified_at)).length
  const totalRewards = referrals.reduce((sum, referral) => sum + getReferralRewards(referral), 0)
  const telegramReferralLink = referralInfo?.telegram_referral_link || referralInfo?.referral_link || ''
  const webReferralLink = referralInfo?.web_referral_link || ''
  const activeReferralLink = qrTarget === 'web' ? webReferralLink : telegramReferralLink
  const showExchangePreview = exchangeLoading || Boolean(exchangeOptions?.exchange_enabled)
  const showMobileExchangeAction = Boolean(!exchangeLoading && exchangeOptions?.exchange_enabled)
  const isMobileExchangeActionActive = Boolean(
    exchangeOptions?.exchange_enabled && availableExchangeTypes.length > 0
  )

  const copyLink = async (link: string, label: string) => {
    if (!link) {
      toast.error(translateText(referralLocale, 'referrals.auto.007'))
      return
    }
    await navigator.clipboard.writeText(link)
    toast.success(
      formatText(
        translateText(referralLocale, 'referrals.auto.008'),
        { label }
      )
    )
  }

  const handleShareReferralLink = async () => {
    if (!activeReferralLink) {
      toast.error(translateText(referralLocale, 'referrals.auto.007'))
      return
    }

    if (navigator.share) {
      await navigator.share({
        title: translateText(referralLocale, 'referrals.share.joinTitle', { projectName }),
        text: translateText(referralLocale, 'referrals.share.joinText', { projectName }),
        url: activeReferralLink,
      })
      return
    }

    await navigator.clipboard.writeText(activeReferralLink)
    toast.success(translateText(referralLocale, 'referrals.auto.009'))
  }

  const handleExecuteExchange = () => {
    if (!selectedExchangeOption) {
      toast.error(translateText(referralLocale, 'referrals.auto.010'))
      return
    }

    const payload: ReferralExchangeExecuteRequest = {
      exchange_type: selectedExchangeOption.type,
    }

    if (selectedExchangeOption.requires_subscription) {
      if (!selectedSubscriptionValue) {
        toast.error(translateText(referralLocale, 'referrals.auto.011'))
        return
      }
      payload.subscription_id = Number(selectedSubscriptionValue)
    }

    if (selectedExchangeOption.type === 'GIFT_SUBSCRIPTION' && selectedGiftPlanValue) {
      payload.gift_plan_id = Number(selectedGiftPlanValue)
    }

    executeExchangeMutation.mutate(payload)
  }

  return (
    <div className="space-y-6">
      <div className={cn('flex gap-3', useMobileUiV2 ? 'items-start justify-between' : 'items-end justify-between')}>
        <div className="min-w-0">
          <h1 className={cn('font-bold', useMobileUiV2 ? 'text-2xl' : 'text-3xl')}>
            {translateText(referralLocale, 'referrals.auto.012')}
          </h1>
          <p className="text-muted-foreground">
            {translateText(referralLocale, 'referrals.auto.013')}
          </p>
        </div>

        {useMobileUiV2 && (
          <div className="flex shrink-0 items-center gap-2">
            {showMobileExchangeAction && (
              <Button
                variant="outline"
                size="icon"
                className={cn(
                  'h-11 w-11 border-white/15 bg-white/5 hover:bg-white/10',
                  isMobileExchangeActionActive
                    ? 'border-primary/45 bg-primary/15 text-primary motion-reduce:animate-none motion-safe:animate-pulse'
                    : 'text-slate-200'
                )}
                onClick={() => setExchangeDialogOpen(true)}
                aria-label={translateText(referralLocale, 'referrals.mobile.exchangeAction')}
              >
                <Gift className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="outline"
              size="icon"
              className="h-11 w-11 border-primary/35 bg-primary/12 text-primary hover:bg-primary/20"
              onClick={() => setKpiInfoDialogOpen(true)}
              aria-label={translateText(referralLocale, 'referrals.mobile.kpiInfoAction')}
            >
              <Info className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      <div
        className={
          showExchangePreview && !useMobileUiV2
            ? 'grid gap-4 xl:grid-cols-[1.35fr_1fr]'
            : undefined
        }
      >
        <Card className={showExchangePreview && !useMobileUiV2 ? 'h-full' : undefined}>
          <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
            <div>
              <CardTitle>{translateText(referralLocale, 'referrals.auto.014')}</CardTitle>
              <CardDescription>
                {translateText(referralLocale, 'referrals.auto.015')}
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="icon"
              onClick={handleShareReferralLink}
              className={cn(useMobileUiV2 ? 'h-11 w-11' : 'h-9 w-9')}
              aria-label={translateText(referralLocale, 'referrals.mobile.shareAction')}
            >
              <Share2 className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            <ReferralLinkField
              label={translateText(referralLocale, 'referrals.auto.016')}
              value={telegramReferralLink}
              onCopy={() => copyLink(telegramReferralLink, translateText(referralLocale, 'referrals.auto.017'))}
              onShowQr={() => {
                setQrTarget('telegram')
                setQrDialogOpen(true)
              }}
              locale={referralLocale}
              compact={useMobileUiV2}
            />
            <ReferralLinkField
              label={translateText(referralLocale, 'referrals.auto.018')}
              value={webReferralLink}
              onCopy={() => copyLink(webReferralLink, translateText(referralLocale, 'referrals.auto.019'))}
              onShowQr={() => {
                setQrTarget('web')
                setQrDialogOpen(true)
              }}
              locale={referralLocale}
              compact={useMobileUiV2}
            />
          </CardContent>
        </Card>

        {!useMobileUiV2 && (
          <>
            {exchangeLoading ? (
              <Card>
                <CardHeader className="pb-2">
                  <Skeleton className="h-6 w-40" />
                  <Skeleton className="mt-2 h-4 w-52" />
                </CardHeader>
                <CardContent className="pt-0">
                  <Skeleton className="h-24 w-full" />
                </CardContent>
              </Card>
            ) : exchangeOptions?.exchange_enabled ? (
              <Card className="border-primary/25">
                <button
                  type="button"
                  onClick={() => setExchangeDialogOpen(true)}
                  className="w-full text-left transition hover:bg-muted/20"
                >
                  <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Gift className="h-5 w-5" />
                        {translateText(referralLocale, 'referrals.auto.020')}
                      </CardTitle>
                      <CardDescription>
                        {translateText(referralLocale, 'referrals.auto.021')}
                      </CardDescription>
                    </div>
                    <ChevronRight className="mt-0.5 h-5 w-5 text-muted-foreground" />
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="grid gap-2 sm:grid-cols-3">
                      <div className="rounded-lg border border-primary/30 bg-primary/10 p-2.5">
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                          {translateText(referralLocale, 'referrals.auto.022')}
                        </p>
                        <p className="text-lg font-bold">
                          {exchangeOptions.points_balance} {translateText(referralLocale, 'referrals.auto.023')}
                        </p>
                      </div>
                      <div className="rounded-lg border p-2.5">
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                          {translateText(referralLocale, 'referrals.auto.024')}
                        </p>
                        <p className="text-lg font-bold">{availableExchangeTypes.length}</p>
                      </div>
                      <div className="rounded-lg border p-2.5">
                        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                          {translateText(referralLocale, 'referrals.auto.025')}
                        </p>
                        <p className="truncate text-xs font-medium">
                          {selectedExchangeLabel || translateText(referralLocale, 'referrals.auto.026')}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </button>
              </Card>
            ) : null}
          </>
        )}
      </div>

      <Dialog open={qrDialogOpen} onOpenChange={setQrDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{translateText(referralLocale, 'referrals.auto.027')}</DialogTitle>
            <DialogDescription>
              {translateText(referralLocale, 'referrals.auto.028')}{' '}
              {qrTarget === 'web'
                ? translateText(referralLocale, 'referrals.auto.029')
                : translateText(referralLocale, 'referrals.auto.017')}{' '}
              {translateText(referralLocale, 'referrals.auto.030')}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-center py-8">
            <div className="h-64 w-64 rounded-lg bg-white p-4">
              {qrImageUrl ? (
                <img
                  src={qrImageUrl}
                  alt={translateText(referralLocale, 'referrals.auto.031')}
                  className="h-full w-full rounded"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center rounded bg-gradient-to-br from-primary/20 to-primary/40">
                  {qrLoading ? (
                    <Skeleton className="h-40 w-40 rounded" />
                  ) : (
                    <QrCode className="h-32 w-32 text-primary" />
                  )}
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={exchangeDialogOpen} onOpenChange={setExchangeDialogOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Gift className="h-5 w-5" />
              {translateText(referralLocale, 'referrals.auto.020')}
            </DialogTitle>
            <DialogDescription>
              {translateText(referralLocale, 'referrals.auto.032')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-lg border border-primary/30 bg-primary/10 p-3">
              <p className="text-sm text-muted-foreground">{translateText(referralLocale, 'referrals.auto.033')}</p>
              <p className="text-2xl font-bold">
                {exchangeOptions?.points_balance ?? 0} {translateText(referralLocale, 'referrals.auto.023')}
              </p>
            </div>

            {availableExchangeTypes.length === 0 ? (
              <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                {translateText(referralLocale, 'referrals.auto.034')}
              </div>
            ) : (
              <>
                <div className="grid gap-3 md:grid-cols-2">
                  {availableExchangeTypes.map((option) => (
                    <button
                      key={option.type}
                      type="button"
                      onClick={() => setSelectedExchangeType(option.type)}
                      className={`rounded-lg border p-3 text-left transition ${
                        effectiveSelectedExchangeType === option.type
                          ? 'border-primary bg-primary/10'
                          : 'border-border hover:border-primary/40'
                      }`}
                    >
                      <p className="font-medium">{getExchangeTypeLabel(option.type, referralLocale)}</p>
                      <p className="text-sm text-muted-foreground">{describeExchangeValue(option, referralLocale)}</p>
                    </button>
                  ))}
                </div>

                {selectedExchangeOption && (
                  <div className="space-y-3 rounded-lg border p-4">
                    <div className="flex items-center justify-between">
                      <p className="font-medium">{getExchangeTypeLabel(selectedExchangeOption.type, referralLocale)}</p>
                      <Badge variant="secondary">
                        {translateText(referralLocale, 'referrals.auto.035')}: {selectedExchangeOption.points_cost}{' '}
                        {translateText(referralLocale, 'referrals.auto.023')}
                      </Badge>
                    </div>

                    {selectedExchangeOption.requires_subscription && (
                      <div className="space-y-2">
                        <p className="text-sm text-muted-foreground">
                          {translateText(referralLocale, 'referrals.auto.036')}
                        </p>
                        <Select value={selectedSubscriptionValue} onValueChange={setSelectedSubscriptionId}>
                          <SelectTrigger>
                            <SelectValue placeholder={translateText(referralLocale, 'referrals.auto.037')} />
                          </SelectTrigger>
                          <SelectContent>
                            {exchangeableSubscriptions.map((subscription) => (
                              <SelectItem key={subscription.id} value={subscription.id.toString()}>
                                {subscription.plan.name} - {translateText(referralLocale, 'referrals.auto.038')} {formatShortDate(subscription.expire_at, referralLocale)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {selectedExchangeOption.type === 'GIFT_SUBSCRIPTION' &&
                      (giftPlans.length ? (
                        <div className="space-y-2">
                          <p className="text-sm text-muted-foreground">{translateText(referralLocale, 'referrals.auto.039')}</p>
                          <Select value={selectedGiftPlanValue} onValueChange={setSelectedGiftPlanId}>
                            <SelectTrigger>
                              <SelectValue placeholder={translateText(referralLocale, 'referrals.auto.040')} />
                            </SelectTrigger>
                            <SelectContent>
                              {giftPlans.map((plan) => (
                                <SelectItem key={plan.plan_id} value={plan.plan_id.toString()}>
                                  {plan.plan_name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          {translateText(referralLocale, 'referrals.auto.041')}
                        </p>
                      ))}

                    <Button
                      onClick={handleExecuteExchange}
                      disabled={
                        executeExchangeMutation.isPending ||
                        (selectedExchangeOption.requires_subscription &&
                          exchangeableSubscriptions.length === 0)
                      }
                      className="w-full"
                    >
                      {executeExchangeMutation.isPending
                        ? translateText(referralLocale, 'referrals.auto.042')
                        : translateText(referralLocale, 'referrals.auto.043')}
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={kpiInfoDialogOpen} onOpenChange={setKpiInfoDialogOpen}>
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{translateText(referralLocale, 'referrals.mobile.kpiModalTitle')}</DialogTitle>
            <DialogDescription>{translateText(referralLocale, 'referrals.mobile.kpiModalDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <KpiInfoRow
              label={translateText(referralLocale, 'referrals.mobile.kpi.totalReferrals')}
              value={referralInfo?.referral_count || 0}
              description={translateText(referralLocale, 'referrals.auto.045')}
            />
            <KpiInfoRow
              label={translateText(referralLocale, 'referrals.mobile.kpi.rewardsIssued')}
              value={totalRewards}
              description={translateText(referralLocale, 'referrals.auto.049')}
            />
            <KpiInfoRow
              label={translateText(referralLocale, 'referrals.mobile.kpi.qualified')}
              value={qualifiedReferrals}
              description={translateText(referralLocale, 'referrals.auto.047')}
            />
            <KpiInfoRow
              label={translateText(referralLocale, 'referrals.mobile.kpi.availablePoints')}
              value={referralInfo?.points || 0}
              description={formatText(translateText(referralLocale, 'referrals.auto.051'), { count: activeReferrals })}
              tone="primary"
            />
          </div>
        </DialogContent>
      </Dialog>

      {!useMobileUiV2 && (
        <div className="grid gap-4 md:grid-cols-4">
          <StatCard
            title={translateText(referralLocale, 'referrals.auto.044')}
            value={referralInfo?.referral_count || 0}
            description={translateText(referralLocale, 'referrals.auto.045')}
            icon={Users}
          />
          <StatCard
            title={translateText(referralLocale, 'referrals.auto.046')}
            value={qualifiedReferrals}
            description={translateText(referralLocale, 'referrals.auto.047')}
            icon={CheckCircle2}
            className="border-emerald-300/20 bg-emerald-400/10"
          />
          <StatCard
            title={translateText(referralLocale, 'referrals.auto.048')}
            value={totalRewards}
            description={translateText(referralLocale, 'referrals.auto.049')}
            icon={Gift}
          />
          <StatCard
            title={translateText(referralLocale, 'referrals.auto.050')}
            value={referralInfo?.points || 0}
            description={formatText(translateText(referralLocale, 'referrals.auto.051'), { count: activeReferrals })}
            icon={TrendingUp}
            className="bg-primary/10"
          />
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card className={referrals.length > 0 ? 'border-primary/25' : undefined}>
          <CardHeader className={cn('flex flex-row items-start justify-between space-y-0', useMobileUiV2 ? 'pb-2' : 'pb-4')}>
            <div>
              <CardTitle>{translateText(referralLocale, 'referrals.auto.052')}</CardTitle>
              {!useMobileUiV2 && (
                <CardDescription>
                  {translateText(referralLocale, 'referrals.auto.053')}
                </CardDescription>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 gap-1"
              disabled={referrals.length === 0}
              onClick={() => setFullHistoryOpen(true)}
            >
              {translateText(referralLocale, 'referrals.auto.054')}
              <ChevronRight className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent>
            {listLoading ? (
              <RecentReferralsSkeleton />
            ) : referrals.length > 0 ? (
              <button
                type="button"
                onClick={() => setFullHistoryOpen(true)}
                className="w-full overflow-hidden rounded-lg border border-border/70 text-left transition hover:border-primary/40"
              >
                <div className="divide-y divide-border/60">
                  {recentReferrals.map((referral) => (
                    <ReferralCompactRow
                      key={referral.telegram_id}
                      referral={referral}
                      locale={referralLocale}
                      compact={useMobileUiV2}
                    />
                  ))}
                </div>
                {referrals.length > recentReferrals.length && (
                  <div className="flex items-center justify-between bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
                    <span>
                      +{referrals.length - recentReferrals.length}{' '}
                      {translateText(referralLocale, 'referrals.auto.055')}
                    </span>
                    <span className="inline-flex items-center gap-1 text-primary">
                      {translateText(referralLocale, 'referrals.auto.056')}
                      <ChevronRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                )}
              </button>
            ) : (
              <div className="py-10 text-center">
                <Users className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
                <p className="text-muted-foreground">{translateText(referralLocale, 'referrals.auto.057')}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  {translateText(referralLocale, 'referrals.auto.058')}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-cyan-400/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-cyan-300" />
              {translateText(referralLocale, 'referrals.auto.059')}
            </CardTitle>
            <CardDescription>
              {translateText(referralLocale, 'referrals.auto.060')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ReferralActivityChart series={referralActivitySeries} isLoading={listLoading} locale={referralLocale} />
          </CardContent>
        </Card>
      </div>

      <Dialog open={fullHistoryOpen} onOpenChange={setFullHistoryOpen}>
        <DialogContent
          className={cn(
            'sm:max-w-5xl',
            useMobileUiV2 && 'max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain [touch-action:pan-y] [-webkit-overflow-scrolling:touch]'
          )}
        >
          <DialogHeader>
            <DialogTitle>{translateText(referralLocale, 'referrals.auto.061')}</DialogTitle>
            <DialogDescription>
              {translateText(referralLocale, 'referrals.auto.062')}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
            {listLoading ? (
              <ReferralsListSkeleton />
            ) : sortedReferrals.length > 0 ? (
              sortedReferrals.map((referral) => (
                <ReferralCard
                  key={referral.telegram_id}
                  referral={referral}
                  locale={referralLocale}
                  compact={useMobileUiV2}
                />
              ))
            ) : (
              <div className="py-10 text-center">
                <Users className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
                <p className="text-muted-foreground">{translateText(referralLocale, 'referrals.auto.057')}</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

interface ReferralCardProps {
  referral: Referral
  locale: ReferralsLocale
  compact?: boolean
}

interface ReferralCompactRowProps {
  referral: Referral
  locale: ReferralsLocale
  compact?: boolean
}

interface ReferralLinkFieldProps {
  label: string
  value: string
  onCopy: () => void
  onShowQr: () => void
  locale: ReferralsLocale
  compact?: boolean
}

function ReferralLinkField({
  label,
  value,
  onCopy,
  onShowQr,
  locale,
  compact = false,
}: ReferralLinkFieldProps) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          readOnly
          value={value}
          className={cn(
            'flex-1 rounded-md border bg-muted px-2.5 font-mono text-xs',
            compact ? 'h-11' : 'h-9'
          )}
        />
        <Button
          variant="outline"
          size="icon"
          onClick={onCopy}
          className={cn(compact ? 'h-11 w-11' : 'h-9 w-9')}
          aria-label={label}
        >
          <Copy className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          onClick={onShowQr}
          className={cn(compact ? 'h-11 w-11' : 'h-9 w-9')}
          aria-label={label}
        >
          <QrCode className="h-4 w-4" />
        </Button>
      </div>
      {!value && (
        <p className="text-[11px] text-muted-foreground">
          {translateText(locale, 'referrals.auto.007')}
        </p>
      )}
    </div>
  )
}

function ReferralCompactRow({ referral, locale, compact = false }: ReferralCompactRowProps) {
  const displayName = referral.name || referral.username || formatText(translateText(locale, 'referrals.auto.063'), { id: referral.telegram_id })
  const displayUsername = referral.username || `id${referral.telegram_id}`
  const invitedAt = referral.invited_at || referral.joined_at
  const isQualified = referral.is_qualified ?? Boolean(referral.qualified_at)
  const qualifiedAt = referral.qualified_at || null
  const inviteSource = referral.invite_source || 'UNKNOWN'

  return (
    <div className={cn('flex items-center justify-between gap-3', compact ? 'px-3 py-2.5' : 'px-4 py-3')}>
      <div className="min-w-0 flex-1">
        <p className={cn('truncate font-medium', compact ? 'text-[13px]' : 'text-sm')}>{displayName}</p>
        <p className={cn('truncate text-muted-foreground', compact ? 'text-[11px]' : 'text-xs')}>
          @{displayUsername} · {inviteSource} · L{referral.level}
        </p>
      </div>
      <div className={cn('shrink-0 text-right', compact ? 'w-[118px]' : '')}>
        <p className={cn('text-muted-foreground', compact ? 'text-[11px]' : 'text-xs')}>
          {formatText(translateText(locale, 'referrals.auto.064'), {
            time: formatSafeRelativeTime(invitedAt, locale),
          })}
        </p>
        <p className={cn('font-medium text-foreground', compact ? 'text-[11px]' : 'text-xs')}>
          {isQualified
            ? formatText(translateText(locale, 'referrals.auto.065'), {
                time: formatSafeRelativeTime(qualifiedAt, locale),
              })
            : translateText(locale, 'referrals.auto.066')}
        </p>
      </div>
    </div>
  )
}

function ReferralActivityChart({
  series,
  isLoading,
  locale,
}: {
  series: ReferralActivityPoint[]
  isLoading: boolean
  locale: ReferralsLocale
}) {
  if (isLoading) {
    return <Skeleton className="h-[220px] w-full rounded-lg" />
  }

  const invitedTotal = series.reduce((sum, item) => sum + item.invited, 0)
  const qualifiedTotal = series.reduce((sum, item) => sum + item.qualified, 0)
  const maxValue = Math.max(
    ...series.map((item) => Math.max(item.invited, item.qualified)),
    0
  )

  if (!series.length || maxValue === 0) {
    return (
      <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed border-cyan-400/40 bg-cyan-400/5 p-6 text-center">
        <Activity className="mb-3 h-8 w-8 text-cyan-300" />
        <p className="font-medium">{translateText(locale, 'referrals.auto.067')}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {translateText(locale, 'referrals.auto.068')}
        </p>
      </div>
    )
  }

  const width = 680
  const height = 240
  const paddingX = 24
  const paddingTop = 18
  const paddingBottom = 30
  const baselineY = height - paddingBottom
  const innerWidth = width - paddingX * 2
  const innerHeight = baselineY - paddingTop

  const createCoordinates = (field: 'invited' | 'qualified') =>
    series.map((item, index) => {
      const x =
        series.length === 1
          ? paddingX + innerWidth / 2
          : paddingX + (index / (series.length - 1)) * innerWidth
      const y = baselineY - (item[field] / maxValue) * innerHeight
      return {
        x,
        y,
      }
    })

  const invitedCoordinates = createCoordinates('invited')
  const qualifiedCoordinates = createCoordinates('qualified')

  const toLinePath = (coordinates: Array<{ x: number; y: number }>) =>
    coordinates
      .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
      .join(' ')

  const invitedPath = toLinePath(invitedCoordinates)
  const qualifiedPath = toLinePath(qualifiedCoordinates)
  const invitedAreaPath = `${invitedPath} L ${invitedCoordinates[invitedCoordinates.length - 1].x.toFixed(2)} ${baselineY.toFixed(2)} L ${invitedCoordinates[0].x.toFixed(2)} ${baselineY.toFixed(2)} Z`
  const midIndex = Math.floor(series.length / 2)

  return (
    <div className="rounded-lg border border-cyan-400/30 bg-cyan-400/5 p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-300" />
            {translateText(locale, 'referrals.auto.069')} ({invitedTotal})
          </span>
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
            {translateText(locale, 'referrals.auto.046')} ({qualifiedTotal})
          </span>
        </div>
        <Badge variant="secondary">{translateText(locale, 'referrals.auto.070')}: {maxValue}</Badge>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="h-[210px] w-full">
        <defs>
          <linearGradient id="ref-invited-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(103 232 249)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="rgb(103 232 249)" stopOpacity="0" />
          </linearGradient>
        </defs>

        <line
          x1={paddingX}
          y1={baselineY}
          x2={width - paddingX}
          y2={baselineY}
          stroke="rgba(148,163,184,0.35)"
          strokeWidth="1"
        />

        <path d={invitedAreaPath} fill="url(#ref-invited-fill)" />
        <path d={invitedPath} fill="none" stroke="rgb(103 232 249)" strokeWidth="2.75" strokeLinecap="round" />
        <path d={qualifiedPath} fill="none" stroke="rgb(110 231 183)" strokeWidth="2.75" strokeLinecap="round" />

        {invitedCoordinates.map((point) => (
          <circle key={`invited-${point.x}-${point.y}`} cx={point.x} cy={point.y} r="3" fill="rgb(103 232 249)" />
        ))}
        {qualifiedCoordinates.map((point) => (
          <circle key={`qualified-${point.x}-${point.y}`} cx={point.x} cy={point.y} r="3" fill="rgb(110 231 183)" />
        ))}

        <text x={paddingX} y={height - 6} fill="rgba(148,163,184,0.85)" fontSize="11">
          {series[0].label}
        </text>
        <text
          x={invitedCoordinates[midIndex].x}
          y={height - 6}
          textAnchor="middle"
          fill="rgba(148,163,184,0.85)"
          fontSize="11"
        >
          {series[midIndex].label}
        </text>
        <text
          x={width - paddingX}
          y={height - 6}
          textAnchor="end"
          fill="rgba(148,163,184,0.85)"
          fontSize="11"
        >
          {series[series.length - 1].label}
        </text>
      </svg>
    </div>
  )
}

function ReferralCard({ referral, locale, compact = false }: ReferralCardProps) {
  const displayName = referral.name || referral.username || translateText(locale, 'referrals.auto.071')
  const displayUsername = referral.username || `id${referral.telegram_id}`
  const invitedAt = referral.invited_at || referral.joined_at
  const inviteSource = referral.invite_source || 'UNKNOWN'
  const isQualified = referral.is_qualified ?? Boolean(referral.qualified_at)
  const qualifiedAt = referral.qualified_at || null
  const inviteSourceLabel = formatReferralSource(inviteSource, locale)
  const qualifiedChannelValue = referral.qualified_purchase_channel || (isQualified ? 'UNKNOWN' : 'NOT_YET')
  const qualifiedChannelLabel = formatReferralChannel(qualifiedChannelValue, locale)
  const rewards = getReferralRewards(referral)
  const events = buildReferralEvents(referral)

  return (
    <div className={cn('rounded-lg border', compact ? 'p-3' : 'p-4')}>
      <div className={cn('gap-4', compact ? 'space-y-3' : 'flex items-start justify-between')}>
        <div className={cn('flex items-start', compact ? 'gap-3' : 'gap-4')}>
          <div className={cn('flex items-center justify-center rounded-full bg-primary/10', compact ? 'h-9 w-9' : 'h-10 w-10')}>
            <span className="font-semibold text-primary">{displayName.charAt(0).toUpperCase()}</span>
          </div>
          <div className="min-w-0">
            <p className={cn('truncate font-medium', compact ? 'text-sm' : '')}>{displayName}</p>
            <p className={cn('text-muted-foreground', compact ? 'truncate text-xs' : 'text-sm')}>
              @{displayUsername} · {translateText(locale, 'referrals.auto.072')} {referral.level}
            </p>
            <div className={cn('mt-2 flex flex-wrap gap-2', compact ? 'gap-1.5' : '')}>
              <Badge variant={referral.is_active ? 'default' : 'secondary'}>
                {referral.is_active ? translateText(locale, 'referrals.auto.073') : translateText(locale, 'referrals.auto.074')}
              </Badge>
              <Badge variant="outline">{translateText(locale, 'referrals.auto.075')}: {inviteSourceLabel}</Badge>
              <Badge variant={isQualified ? 'default' : 'secondary'}>
                {isQualified ? translateText(locale, 'referrals.auto.076') : translateText(locale, 'referrals.auto.077')}
              </Badge>
            </div>
          </div>
        </div>
        <div className={cn(compact ? 'flex items-center justify-between rounded-md border border-white/10 bg-white/[0.02] px-2.5 py-2' : 'text-right')}>
          <p className="font-medium">
            {rewards} {translateText(locale, 'referrals.auto.023')}
          </p>
          <p className={cn('text-muted-foreground', compact ? 'text-xs' : 'text-sm')}>
            {formatText(translateText(locale, 'referrals.auto.064'), {
              time: formatSafeRelativeTime(invitedAt, locale),
            })}
          </p>
        </div>
      </div>

      <div className={cn('mt-4 grid gap-2 text-muted-foreground md:grid-cols-2', compact ? 'text-xs' : 'text-sm')}>
        <p>{translateText(locale, 'referrals.auto.078')}: {formatSafeRelativeTime(invitedAt, locale)}</p>
        <p>{translateText(locale, 'referrals.auto.079')}: {qualifiedChannelLabel}</p>
        <p>
          {translateText(locale, 'referrals.auto.080')}: {' '}
          {qualifiedAt ? formatSafeRelativeTime(qualifiedAt, locale) : translateText(locale, 'referrals.auto.081')}
        </p>
      </div>

      {events.length > 0 && (
        <div className={cn('mt-4 rounded-md border border-dashed', compact ? 'p-2.5' : 'p-3')}>
          <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{translateText(locale, 'referrals.auto.082')}</p>
          <div className="space-y-2">
            {events.map((event) => (
              <div
                key={`${event.type}-${event.at}-${event.source ?? 'na'}-${event.channel ?? 'na'}`}
                className={cn('flex items-center justify-between gap-3', compact ? 'text-xs' : 'text-sm')}
              >
                <span>{formatReferralEventLabel(event, locale)}</span>
                <span className="text-muted-foreground">{formatSafeRelativeTime(event.at, locale)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({
  title,
  value,
  description,
  icon: Icon,
  className,
}: {
  title: string
  value: string | number
  description: string
  icon: React.ElementType
  className?: string
}) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

function KpiInfoRow({
  label,
  value,
  description,
  tone = 'default',
}: {
  label: string
  value: string | number
  description: string
  tone?: 'default' | 'primary'
}) {
  return (
    <div
      className={cn(
        'rounded-lg border px-3 py-2.5',
        tone === 'primary'
          ? 'border-primary/35 bg-primary/12'
          : 'border-white/10 bg-white/[0.03]'
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
          <p className="truncate text-[11px] text-muted-foreground">{description}</p>
        </div>
        <div className="text-xl font-semibold text-foreground">{value}</div>
      </div>
    </div>
  )
}

function ReferralsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((skeletonId) => (
          <Card key={skeletonId}>
            <CardHeader className="pb-3">
              <Skeleton className="h-4 w-32" />
            </CardHeader>
            <CardContent>
              <Skeleton className="mb-2 h-8 w-16" />
              <Skeleton className="h-3 w-24" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function ReferralsListSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((skeletonId) => (
        <div key={skeletonId} className="flex items-center justify-between rounded-lg border p-4">
          <div className="flex items-center gap-4">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-6 w-20" />
          </div>
        </div>
      ))}
    </div>
  )
}

function RecentReferralsSkeleton() {
  return (
    <div className="rounded-lg border border-border/70">
      {[1, 2, 3, 4].map((skeletonId) => (
        <div key={skeletonId} className="flex items-center justify-between gap-4 border-b border-border/60 px-4 py-3 last:border-b-0">
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-24" />
          </div>
          <div className="w-[120px] shrink-0 space-y-2 text-right">
            <Skeleton className="ml-auto h-3 w-20" />
            <Skeleton className="ml-auto h-3 w-16" />
          </div>
        </div>
      ))}
    </div>
  )
}

function getReferralRewards(referral: Referral): number {
  return referral.rewards_issued ?? referral.rewards_earned ?? 0
}

function buildReferralActivitySeries(
  referrals: Referral[],
  locale: ReferralsLocale,
  daysWindow = 14
): ReferralActivityPoint[] {
  const eventDates = referrals.flatMap((referral) =>
    buildReferralEvents(referral)
      .map((event) => parseDateSafe(event.at))
      .filter((date): date is Date => Boolean(date))
  )

  if (!eventDates.length) {
    return []
  }

  const today = toDayStart(new Date())
  const latestEventDay = toDayStart(new Date(Math.max(...eventDates.map((date) => date.getTime()))))
  const endDay = latestEventDay.getTime() > today.getTime() ? latestEventDay : today
  const startDay = new Date(endDay)
  startDay.setDate(startDay.getDate() - daysWindow + 1)

  const invitedDailyCount = new Map<string, number>()
  const qualifiedDailyCount = new Map<string, number>()

  for (const referral of referrals) {
    for (const event of buildReferralEvents(referral)) {
      const date = parseDateSafe(event.at)
      if (!date) {
        continue
      }
      const day = toDayStart(date)
      if (day < startDay || day > endDay) {
        continue
      }

      const key = toIsoDateKey(day)
      if (event.type === 'INVITED') {
        invitedDailyCount.set(key, (invitedDailyCount.get(key) ?? 0) + 1)
      } else if (event.type === 'QUALIFIED') {
        qualifiedDailyCount.set(key, (qualifiedDailyCount.get(key) ?? 0) + 1)
      }
    }
  }

  const series: ReferralActivityPoint[] = []

  for (let offset = 0; offset < daysWindow; offset += 1) {
    const day = new Date(startDay)
    day.setDate(startDay.getDate() + offset)

    const key = toIsoDateKey(day)
    series.push({
      key,
      label: day.toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US', { month: 'short', day: 'numeric' }),
      invited: invitedDailyCount.get(key) ?? 0,
      qualified: qualifiedDailyCount.get(key) ?? 0,
    })
  }

  return series
}

function getReferralSortTimestamp(referral: Referral): number {
  const invitedDate = parseDateSafe(referral.invited_at || referral.joined_at)
  return invitedDate?.getTime() ?? 0
}

function parseDateSafe(value?: string | null): Date | null {
  if (!value) {
    return null
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  return date
}

function toDayStart(date: Date): Date {
  const day = new Date(date)
  day.setHours(0, 0, 0, 0)
  return day
}

function toIsoDateKey(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function buildReferralEvents(referral: Referral): ReferralEvent[] {
  if (referral.events && referral.events.length > 0) {
    return referral.events
  }

  const invitedAt = referral.invited_at || referral.joined_at
  if (!invitedAt) {
    return []
  }

  const events: ReferralEvent[] = [
    {
      type: 'INVITED',
      at: invitedAt,
      source: referral.invite_source || 'UNKNOWN',
    },
  ]

  if (referral.qualified_at) {
    events.push({
      type: 'QUALIFIED',
      at: referral.qualified_at,
      channel: referral.qualified_purchase_channel || 'UNKNOWN',
    })
  }

  return events
}

function formatReferralEventLabel(event: ReferralEvent, locale: ReferralsLocale): string {
  if (event.type === 'INVITED') {
    return formatText(
      translateText(locale, 'referrals.auto.083'),
      { source: formatReferralSource(event.source || 'UNKNOWN', locale) }
    )
  }
  return formatText(
    translateText(locale, 'referrals.auto.084'),
    { channel: formatReferralChannel(event.channel || 'UNKNOWN', locale) }
  )
}

function formatReferralSource(source: string, locale: ReferralsLocale): string {
  const normalized = source.toUpperCase()
  if (normalized === 'WEB') {
    return translateText(locale, 'referrals.auto.019')
  }
  if (normalized === 'BOT' || normalized === 'TELEGRAM') {
    return translateText(locale, 'referrals.auto.017')
  }
  if (normalized === 'UNKNOWN') {
    return translateText(locale, 'referrals.auto.085')
  }
  return source
}

function formatReferralChannel(channel: string, locale: ReferralsLocale): string {
  const normalized = channel.toUpperCase()
  if (normalized === 'NOT_YET') {
    return translateText(locale, 'referrals.auto.086')
  }
  if (normalized === 'WEB') {
    return translateText(locale, 'referrals.auto.019')
  }
  if (normalized === 'BOT' || normalized === 'TELEGRAM') {
    return translateText(locale, 'referrals.auto.017')
  }
  if (normalized === 'UNKNOWN') {
    return translateText(locale, 'referrals.auto.085')
  }
  return channel
}

function formatSafeRelativeTime(value: string | null | undefined, locale: ReferralsLocale): string {
  if (!value) {
    return translateText(locale, 'referrals.auto.085')
  }

  try {
    return formatRelativeTime(value)
  } catch {
    return value
  }
}

function describeExchangeValue(option: ReferralExchangeTypeOption, locale: ReferralsLocale): string {
  if (option.type === 'SUBSCRIPTION_DAYS') {
    return formatText(translateText(locale, 'referrals.auto.087'), { value: option.computed_value })
  }
  if (option.type === 'GIFT_SUBSCRIPTION') {
    return formatText(
      translateText(locale, 'referrals.auto.088'),
      { value: option.gift_duration_days || option.computed_value }
    )
  }
  if (option.type === 'DISCOUNT') {
    return formatText(translateText(locale, 'referrals.auto.089'), { value: option.computed_value })
  }
  return formatText(translateText(locale, 'referrals.auto.090'), { value: option.computed_value })
}

function buildExchangeSuccessMessage(result: ReferralExchangeExecuteResponse, locale: ReferralsLocale): string {
  if (result.exchange_type === 'SUBSCRIPTION_DAYS') {
    return formatText(
      translateText(locale, 'referrals.auto.091'),
      { value: result.result.days_added || 0, points: result.points_spent }
    )
  }
  if (result.exchange_type === 'GIFT_SUBSCRIPTION') {
    return formatText(
      translateText(locale, 'referrals.auto.092'),
      { code: result.result.gift_promocode || '', points: result.points_spent }
    )
  }
  if (result.exchange_type === 'DISCOUNT') {
    return formatText(
      translateText(locale, 'referrals.auto.093'),
      { value: result.result.discount_percent_added || 0, points: result.points_spent }
    )
  }
  return formatText(
    translateText(locale, 'referrals.auto.094'),
    { value: result.result.traffic_gb_added || 0, points: result.points_spent }
  )
}

function extractExchangeError(error: unknown, locale: ReferralsLocale): string {
  const apiError = error as {
    response?: {
      data?: {
        detail?: string | { code?: string; message?: string }
      }
    }
  }

  const detail = apiError.response?.data?.detail
  if (typeof detail === 'string' && detail.length > 0) {
    return detail
  }
  if (detail && typeof detail === 'object' && detail.message) {
    return detail.message
  }
  return translateText(locale, 'referrals.auto.095')
}

function formatShortDate(value: string, locale: ReferralsLocale): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US')
}

function isUnlimited(subscription: Subscription): boolean {
  return subscription.plan.type === 'UNLIMITED'
}
