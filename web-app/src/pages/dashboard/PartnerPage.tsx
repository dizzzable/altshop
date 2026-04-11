import { useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useBranding } from '@/components/common/BrandingProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { translateWithLocale, type TranslationParams } from '@/i18n/runtime'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { cn, copyToClipboard } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Activity,
  AlertCircle,
  ChevronRight,
  Copy,
  DollarSign,
  Handshake,
  Info,
  Link2,
  RotateCw,
  Share2,
  TrendingUp,
  Users,
  Wallet,
} from 'lucide-react'
import { toast } from 'sonner'
import type {
  PartnerEarning,
  PartnerEarningsListResponse,
  PartnerInfo,
  PartnerLevelSetting,
  PartnerReferral,
  PartnerReferralsListResponse,
  PartnerWithdrawal,
  PartnerWithdrawalsListResponse,
} from '@/types'

type DailyGrowthPoint = {
  key: string
  label: string
  count: number
}
type PartnerLocale = 'ru' | 'en'

type WithdrawalStatusNormalized =
  | 'PENDING'
  | 'APPROVED'
  | 'COMPLETED'
  | 'REJECTED'
  | 'CANCELED'
  | 'UNKNOWN'

type PartnerDetailsPanel = 'withdraw' | 'earnings' | 'withdrawals'

const STATUS_ALIASES: Record<string, WithdrawalStatusNormalized> = {
  PENDING: 'PENDING',
  COMPLETED: 'COMPLETED',
  REJECTED: 'REJECTED',
  CANCELED: 'CANCELED',
  CANCELLED: 'CANCELED',
  APPROVED: 'APPROVED',
}

function translateText(
  locale: PartnerLocale,
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

function normalizeWithdrawalStatus(status: string | null | undefined): WithdrawalStatusNormalized {
  if (!status) {
    return 'UNKNOWN'
  }
  return STATUS_ALIASES[status.toUpperCase()] ?? 'UNKNOWN'
}

function parseDisplayAmountInput(value: string): number | null {
  if (!value.trim()) {
    return null
  }

  const normalized = value.replace(',', '.').trim()
  const parsed = Number.parseFloat(normalized)
  if (!Number.isFinite(parsed)) {
    return null
  }

  return Math.round(parsed * 100) / 100
}

function getCurrencyFractionDigits(currency: string): number {
  if (currency === 'BTC') {
    return 8
  }
  if (currency === 'TON' || currency === 'ETH' || currency === 'LTC' || currency === 'BNB' || currency === 'DASH' || currency === 'SOL' || currency === 'XMR' || currency === 'TRX') {
    return 6
  }
  return 2
}

function formatAmountWithCurrency(value: number, currency: string): string {
  const digits = getCurrencyFractionDigits(currency)
  const normalized = Number.isFinite(value) ? value : 0
  return `${normalized.toFixed(digits).replace(/\.?0+$/, '')} ${currency}`
}

function formatRub(valueRub: number): string {
  return `${valueRub.toFixed(2)} RUB`
}

function formatRubFromKopecks(value: number): string {
  return `${(value / 100).toFixed(2)} RUB`
}

function formatSafeDate(value: string, locale: PartnerLocale): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return translateText(locale, 'partner.auto.001')
  }
  return parsed.toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US')
}

function extractErrorDetail(error: unknown): string | null {
  const detail = (
    error as { response?: { data?: { detail?: unknown } } }
  )?.response?.data?.detail
  return typeof detail === 'string' && detail.length > 0 ? detail : null
}

function toDayStart(date: Date): Date {
  const day = new Date(date)
  day.setHours(0, 0, 0, 0)
  return day
}

function toIsoDateKey(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function buildReferralGrowthSeries(
  referrals: PartnerReferral[],
  locale: PartnerLocale,
  daysWindow = 14
): DailyGrowthPoint[] {
  const validDates = referrals
    .map((ref) => (ref.joined_at ? new Date(ref.joined_at) : null))
    .filter((date): date is Date => Boolean(date && !Number.isNaN(date.getTime())))

  if (!validDates.length) {
    return []
  }

  const latestReferralDay = toDayStart(
    new Date(Math.max(...validDates.map((date) => date.getTime())))
  )
  const today = toDayStart(new Date())
  const endDay = latestReferralDay.getTime() > today.getTime() ? latestReferralDay : today
  const startDay = new Date(endDay)
  startDay.setDate(startDay.getDate() - daysWindow + 1)

  const dailyCounts = new Map<string, number>()
  for (const date of validDates) {
    const day = toDayStart(date)
    if (day < startDay || day > endDay) {
      continue
    }

    const key = toIsoDateKey(day)
    dailyCounts.set(key, (dailyCounts.get(key) ?? 0) + 1)
  }

  const series: DailyGrowthPoint[] = []
  for (let offset = 0; offset < daysWindow; offset += 1) {
    const day = new Date(startDay)
    day.setDate(startDay.getDate() + offset)

    const key = toIsoDateKey(day)
    series.push({
      key,
      label: day.toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US', { month: 'short', day: 'numeric' }),
      count: dailyCounts.get(key) ?? 0,
    })
  }

  return series
}

function buildPartnerLevelSettings(partnerInfo: PartnerInfo | undefined): PartnerLevelSetting[] {
  if (!partnerInfo) {
    return []
  }

  if (partnerInfo.level_settings && partnerInfo.level_settings.length > 0) {
    return [...partnerInfo.level_settings].sort((left, right) => left.level - right.level)
  }

  const fallbackPercents: Record<1 | 2 | 3, number> = {
    1: 10,
    2: 3,
    3: 1,
  }

  return [
    {
      level: 1,
      referrals_count: partnerInfo.referrals_count ?? 0,
      earned_amount: 0,
      global_percent: fallbackPercents[1],
      effective_percent: fallbackPercents[1],
      uses_global_value: true,
    },
    {
      level: 2,
      referrals_count: partnerInfo.level2_referrals_count ?? 0,
      earned_amount: 0,
      global_percent: fallbackPercents[2],
      effective_percent: fallbackPercents[2],
      uses_global_value: true,
    },
    {
      level: 3,
      referrals_count: partnerInfo.level3_referrals_count ?? 0,
      earned_amount: 0,
      global_percent: fallbackPercents[3],
      effective_percent: fallbackPercents[3],
      uses_global_value: true,
    },
  ]
}

function formatPartnerLevelReward(levelSetting: PartnerLevelSetting, locale: PartnerLocale): string {
  if (levelSetting.effective_fixed_amount && levelSetting.effective_fixed_amount > 0) {
    return formatText(
      translateText(locale, 'partner.auto.002'),
      { value: formatRubFromKopecks(levelSetting.effective_fixed_amount) }
    )
  }

  if (levelSetting.effective_percent !== null && levelSetting.effective_percent !== undefined) {
    return formatText(
      translateText(locale, 'partner.auto.003'),
      { value: levelSetting.effective_percent.toFixed(2) }
    )
  }

  return formatText(
    translateText(locale, 'partner.auto.004'),
    { value: levelSetting.global_percent.toFixed(2) }
  )
}

function formatPartnerAccrualStrategy(
  strategy: 'ON_FIRST_PAYMENT' | 'ON_EACH_PAYMENT' | string,
  locale: PartnerLocale
): string {
  if (strategy === 'ON_FIRST_PAYMENT') {
    return translateText(locale, 'partner.auto.005')
  }
  return translateText(locale, 'partner.auto.006')
}

export function PartnerPage() {
  const { projectName } = useBranding()
  const { locale } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const partnerLocale: PartnerLocale = locale === 'en' ? 'en' : 'ru'
  const queryClient = useQueryClient()
  const [activeDetailsPanel, setActiveDetailsPanel] = useState<PartnerDetailsPanel | null>(null)
  const [walletDialogOpen, setWalletDialogOpen] = useState(false)
  const [summaryDialogOpen, setSummaryDialogOpen] = useState(false)
  const [analyticsDialogOpen, setAnalyticsDialogOpen] = useState(false)
  const [withdrawAmount, setWithdrawAmount] = useState('')
  const [withdrawMethod, setWithdrawMethod] = useState('')
  const [requisites, setRequisites] = useState('')

  const {
    data: partnerInfo,
    isLoading: infoLoading,
    isFetching: infoFetching,
    refetch: refetchPartnerInfo,
  } = useQuery<PartnerInfo>({
    queryKey: ['partner-info'],
    queryFn: () => api.partner.info().then((response) => response.data),
  })

  const { data: earningsData, isLoading: earningsLoading } = useQuery<PartnerEarningsListResponse>({
    queryKey: ['partner-earnings'],
    queryFn: () => api.partner.earnings().then((response) => response.data),
    enabled: !!partnerInfo?.is_partner,
  })

  const { data: referralsData, isLoading: referralsLoading } = useQuery<PartnerReferralsListResponse>({
    queryKey: ['partner-referrals'],
    queryFn: () => api.partner.referrals().then((response) => response.data),
    enabled: !!partnerInfo?.is_partner,
  })

  const { data: withdrawalsData, isLoading: withdrawalsLoading } = useQuery<PartnerWithdrawalsListResponse>({
    queryKey: ['partner-withdrawals'],
    queryFn: () => api.partner.withdrawals().then((response) => response.data),
    enabled: !!partnerInfo?.is_partner,
  })

  const earnings = useMemo(() => earningsData?.earnings ?? [], [earningsData?.earnings])
  const referrals = useMemo(() => referralsData?.referrals ?? [], [referralsData?.referrals])
  const withdrawals = useMemo(() => withdrawalsData?.withdrawals ?? [], [withdrawalsData?.withdrawals])

  const referralGrowthSeries = useMemo(
    () => buildReferralGrowthSeries(referrals, partnerLocale),
    [partnerLocale, referrals]
  )

  const totalReferrals =
    (partnerInfo?.referrals_count ?? 0) +
    (partnerInfo?.level2_referrals_count ?? 0) +
    (partnerInfo?.level3_referrals_count ?? 0)

  const isPartnerActive = Boolean(partnerInfo?.is_active)
  const effectiveCurrency = partnerInfo?.effective_currency ?? 'RUB'
  const minWithdrawalRub = partnerInfo?.min_withdrawal_rub ?? 0
  const minWithdrawalDisplay = partnerInfo?.min_withdrawal_display ?? minWithdrawalRub
  const availableBalanceRub = (partnerInfo?.balance ?? 0) / 100
  const availableBalanceDisplay = partnerInfo?.balance_display ?? availableBalanceRub
  const totalEarnedDisplay = partnerInfo?.total_earned_display ?? ((partnerInfo?.total_earned ?? 0) / 100)
  const totalWithdrawnDisplay =
    partnerInfo?.total_withdrawn_display ?? ((partnerInfo?.total_withdrawn ?? 0) / 100)
  const showRubEquivalent = effectiveCurrency !== 'RUB'
  const canWithdraw = Boolean(partnerInfo?.can_withdraw) && isPartnerActive

  const activeReferrals = referrals.filter((ref) => ref.is_active).length
  const paidReferrals = referrals.filter((ref) => ref.is_paid).length
  const webReferrals = referrals.filter((ref) => (ref.invite_source || '').toUpperCase() === 'WEB').length
  const botReferrals = referrals.filter((ref) => (ref.invite_source || '').toUpperCase() === 'BOT').length
  const partnerLevelSettings = useMemo(
    () => buildPartnerLevelSettings(partnerInfo),
    [partnerInfo]
  )
  const partnerRewardType = partnerInfo?.effective_reward_type || 'PERCENT'
  const partnerAccrualStrategy = partnerInfo?.effective_accrual_strategy || 'ON_EACH_PAYMENT'
  const telegramPartnerLink = partnerInfo?.telegram_referral_link || partnerInfo?.referral_link || ''
  const webPartnerLink = partnerInfo?.web_referral_link || ''
  const activePartnerLink = webPartnerLink || telegramPartnerLink
  const hasTelegramPartnerLink = Boolean(telegramPartnerLink.trim())
  const hasWebPartnerLink = Boolean(webPartnerLink.trim())
  const hasBothPartnerLinks = hasTelegramPartnerLink && hasWebPartnerLink
  const latestEarning = useMemo(
    () =>
      [...earnings].sort(
        (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
      )[0] ?? null,
    [earnings]
  )
  const latestWithdrawal = useMemo(
    () =>
      [...withdrawals].sort(
        (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
      )[0] ?? null,
    [withdrawals]
  )
  const pendingWithdrawalsCount = withdrawals.filter(
    (withdrawal) => normalizeWithdrawalStatus(withdrawal.status) === 'PENDING'
  ).length

  const copyPartnerLink = async (link: string, label: string) => {
    if (!link) {
      toast.error(translateText(partnerLocale, 'partner.auto.007'))
      return
    }

    const copied = await copyToClipboard(link)
    if (!copied) {
      toast.error(translateText(partnerLocale, 'partner.auto.007'))
      return
    }

    toast.success(
      formatText(
        translateText(partnerLocale, 'partner.auto.008'),
        { label }
      )
    )
  }

  const sharePartnerLink = async () => {
    if (!activePartnerLink) {
      toast.error(translateText(partnerLocale, 'partner.auto.007'))
      return
    }

    if (navigator.share) {
      await navigator.share({
        title: translateText(partnerLocale, 'partner.share.joinTitle', { projectName }),
        text: translateText(partnerLocale, 'partner.auto.009'),
        url: activePartnerLink,
      })
      return
    }

    const copied = await copyToClipboard(activePartnerLink)
    if (!copied) {
      toast.error(translateText(partnerLocale, 'partner.auto.007'))
      return
    }

    toast.success(translateText(partnerLocale, 'partner.auto.010'))
  }

  const retryPartnerLinks = async () => {
    const result = await refetchPartnerInfo()
    const refreshed = result.data
    const refreshedTelegram = (refreshed?.telegram_referral_link || refreshed?.referral_link || '').trim()
    const refreshedWeb = (refreshed?.web_referral_link || '').trim()

    if (refreshedTelegram && refreshedWeb) {
      toast.success(translateText(partnerLocale, 'partner.auto.011'))
      return
    }
    toast.error(translateText(partnerLocale, 'partner.auto.012'))
  }

  const withdrawMutation = useMutation({
    mutationFn: (data: { amount: number; method: string; requisites: string }) => api.partner.withdraw(data),
    onSuccess: async () => {
      toast.success(translateText(partnerLocale, 'partner.auto.013'))
      setActiveDetailsPanel(null)
      setWithdrawAmount('')
      setWithdrawMethod('')
      setRequisites('')

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['partner-info'] }),
        queryClient.invalidateQueries({ queryKey: ['partner-withdrawals'] }),
      ])
    },
    onError: (error: unknown) => {
      toast.error(extractErrorDetail(error) || translateText(partnerLocale, 'partner.auto.014'))
    },
  })

  const handleWithdraw = (event: FormEvent) => {
    event.preventDefault()

    if (!canWithdraw) {
      toast.error(translateText(partnerLocale, 'partner.auto.015'))
      return
    }

    if (!withdrawMethod || !requisites.trim()) {
      toast.error(translateText(partnerLocale, 'partner.auto.016'))
      return
    }

    const parsedAmount = parseDisplayAmountInput(withdrawAmount)
    if (parsedAmount === null || parsedAmount <= 0) {
      toast.error(translateText(partnerLocale, 'partner.auto.017'))
      return
    }

    if (parsedAmount < minWithdrawalDisplay) {
      toast.error(
        formatText(
          translateText(partnerLocale, 'partner.auto.018'),
          { amount: formatAmountWithCurrency(minWithdrawalDisplay, effectiveCurrency) }
        )
      )
      return
    }

    if (parsedAmount > availableBalanceDisplay) {
      toast.error(
        formatText(
          translateText(partnerLocale, 'partner.auto.019'),
          { amount: formatAmountWithCurrency(availableBalanceDisplay, effectiveCurrency) }
        )
      )
      return
    }

    withdrawMutation.mutate({
      amount: parsedAmount,
      method: withdrawMethod,
      requisites: requisites.trim(),
    })
  }

  const openDetailsPanel = (panel: PartnerDetailsPanel) => {
    setWalletDialogOpen(false)
    setActiveDetailsPanel(panel)
  }

  if (infoLoading) {
    return <PartnerSkeleton />
  }

  if (!partnerInfo?.is_partner) {
    const applySupportUrl = partnerInfo?.apply_support_url || null

    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center">
              <Handshake className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
              <h2 className="mb-2 text-xl font-semibold">{translateText(partnerLocale, 'partner.auto.020')}</h2>
              <p className="mb-4 text-muted-foreground">
                {translateText(partnerLocale, 'partner.auto.021')}
              </p>
              {applySupportUrl ? (
                <Button asChild>
                  <a href={applySupportUrl} target="_blank" rel="noreferrer">
                    {translateText(partnerLocale, 'partner.auto.022')}
                  </a>
                </Button>
              ) : (
                <Button disabled>{translateText(partnerLocale, 'partner.auto.023')}</Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const summaryCards = [
    {
      title: translateText(partnerLocale, 'partner.auto.024'),
      value: formatAmountWithCurrency(availableBalanceDisplay, effectiveCurrency),
      description: showRubEquivalent
        ? `${translateText(partnerLocale, 'partner.auto.025')} • ${formatRubFromKopecks(partnerInfo.balance)}`
        : translateText(partnerLocale, 'partner.auto.025'),
      icon: Wallet,
      cardClass: 'border-rose-500/50',
    },
    {
      title: translateText(partnerLocale, 'partner.auto.026'),
      value: formatAmountWithCurrency(totalEarnedDisplay, effectiveCurrency),
      description: showRubEquivalent
        ? `${translateText(partnerLocale, 'partner.auto.027')} • ${formatRubFromKopecks(partnerInfo.total_earned)}`
        : translateText(partnerLocale, 'partner.auto.027'),
      icon: TrendingUp,
      cardClass: 'border-yellow-500/50',
    },
    {
      title: translateText(partnerLocale, 'partner.auto.028'),
      value: formatAmountWithCurrency(totalWithdrawnDisplay, effectiveCurrency),
      description: showRubEquivalent
        ? `${translateText(partnerLocale, 'partner.auto.029')} • ${formatRubFromKopecks(partnerInfo.total_withdrawn)}`
        : translateText(partnerLocale, 'partner.auto.029'),
      icon: DollarSign,
      cardClass: 'border-lime-500/50',
    },
    {
      title: translateText(partnerLocale, 'partner.auto.030'),
      value: totalReferrals,
      description: formatText(
        translateText(partnerLocale, 'partner.auto.031'),
        { count: paidReferrals }
      ),
      icon: Users,
      cardClass: 'border-pink-500/50',
    },
  ]
  const partnerSettingsMode =
    partnerInfo.use_global_settings === false
      ? translateText(partnerLocale, 'partner.auto.032')
      : translateText(partnerLocale, 'partner.auto.033')
  const partnerAccrualLabel = formatPartnerAccrualStrategy(partnerAccrualStrategy, partnerLocale)

  return (
    <div className="space-y-6">
      <div className={cn('flex gap-3', useMobileUiV2 ? 'items-start justify-between' : 'items-end justify-between')}>
        <div className="min-w-0">
          <h1 className={cn('font-bold', useMobileUiV2 ? 'text-2xl' : 'text-3xl')}>
            {translateText(partnerLocale, 'partner.auto.034')}
          </h1>
          <p className="text-muted-foreground">
            {translateText(partnerLocale, 'partner.auto.035')}
          </p>
        </div>

        {useMobileUiV2 && (
          <div className="flex shrink-0 items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-11 w-11 border-emerald-400/35 bg-emerald-500/12 text-emerald-200 hover:bg-emerald-500/20"
              onClick={() => setWalletDialogOpen(true)}
              aria-label={translateText(partnerLocale, 'partner.mobile.walletAction')}
            >
              <Wallet className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-11 w-11 border-primary/35 bg-primary/12 text-primary hover:bg-primary/20"
              onClick={() => setSummaryDialogOpen(true)}
              aria-label={translateText(partnerLocale, 'partner.mobile.summaryAction')}
            >
              <Info className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {!isPartnerActive && (
        <Card className="border-amber-300/30 bg-amber-500/10">
          <CardContent className="pt-6">
            <p className="text-sm text-amber-100">
              {translateText(partnerLocale, 'partner.auto.036')}
            </p>
          </CardContent>
        </Card>
      )}

      <div className={cn('grid gap-4', useMobileUiV2 ? 'grid-cols-1' : 'xl:grid-cols-[1.25fr_1fr]')}>
        <Card className="border-primary/30">
          <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Link2 className="h-5 w-5" />
                {translateText(partnerLocale, 'partner.auto.037')}
              </CardTitle>
              <CardDescription>
                {translateText(partnerLocale, 'partner.auto.038')}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {!hasBothPartnerLinks && (
                <Button
                  variant="outline"
                  size={useMobileUiV2 ? 'icon' : 'sm'}
                  onClick={retryPartnerLinks}
                  disabled={infoFetching}
                  className={cn(useMobileUiV2 ? 'h-11 w-11' : 'h-9')}
                  aria-label={translateText(partnerLocale, 'partner.mobile.retryLinksAction')}
                >
                  <RotateCw
                    className={cn(
                      'h-3.5 w-3.5',
                      !useMobileUiV2 && 'mr-1.5',
                      infoFetching && 'animate-spin'
                    )}
                  />
                  {!useMobileUiV2 && translateText(partnerLocale, 'partner.auto.039')}
                </Button>
              )}
              <Button
                variant="outline"
                size="icon"
                className={cn(useMobileUiV2 ? 'h-11 w-11' : 'h-9 w-9')}
                onClick={sharePartnerLink}
                aria-label={translateText(partnerLocale, 'partner.mobile.shareAction')}
              >
                <Share2 className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            <PartnerInviteField
              label={translateText(partnerLocale, 'partner.auto.040')}
              value={telegramPartnerLink}
              onCopy={() => copyPartnerLink(telegramPartnerLink, translateText(partnerLocale, 'partner.auto.041'))}
              isGenerating={!hasTelegramPartnerLink && infoFetching}
              locale={partnerLocale}
              compact={useMobileUiV2}
            />
            <PartnerInviteField
              label={translateText(partnerLocale, 'partner.auto.042')}
              value={webPartnerLink}
              onCopy={() => copyPartnerLink(webPartnerLink, translateText(partnerLocale, 'partner.auto.043'))}
              isGenerating={!hasWebPartnerLink && infoFetching}
              locale={partnerLocale}
              compact={useMobileUiV2}
            />
          </CardContent>
        </Card>

        {!useMobileUiV2 && (
          <Card className="border-cyan-500/30">
            <CardHeader>
              <CardTitle>{translateText(partnerLocale, 'partner.auto.044')}</CardTitle>
              <CardDescription>
                {partnerSettingsMode} - {partnerRewardType === 'FIXED_AMOUNT'
                  ? translateText(partnerLocale, 'partner.auto.045')
                  : translateText(partnerLocale, 'partner.auto.046')}
                {' '}({partnerAccrualLabel})
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {partnerLevelSettings.map((levelSetting) => (
                <div key={levelSetting.level} className="rounded-lg border border-border/70 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">
                        {translateText(partnerLocale, 'partner.auto.047')} {levelSetting.level}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatText(
                          translateText(partnerLocale, 'partner.auto.048'),
                          {
                            count: levelSetting.referrals_count,
                            amount: formatRubFromKopecks(levelSetting.earned_amount),
                          }
                        )}
                      </p>
                    </div>
                    <Badge variant={levelSetting.uses_global_value ? 'secondary' : 'default'}>
                      {levelSetting.uses_global_value
                        ? translateText(partnerLocale, 'partner.auto.049')
                        : translateText(partnerLocale, 'partner.auto.050')}
                    </Badge>
                  </div>
                  <p className="mt-2 text-sm font-semibold">{formatPartnerLevelReward(levelSetting, partnerLocale)}</p>
                  <p className="text-xs text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.049')}: {levelSetting.global_percent.toFixed(2)}%
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      {!useMobileUiV2 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {summaryCards.map((column) => {
            const Icon = column.icon

            return (
              <Card key={column.title} className={`overflow-hidden ${column.cardClass}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">{column.title}</CardTitle>
                      <CardDescription>{column.description}</CardDescription>
                    </div>
                    <Icon className="h-5 w-5 text-muted-foreground" />
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-2xl font-bold tracking-tight">{column.value}</p>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {!useMobileUiV2 && (
        <div className="pb-1">
          <div className="grid gap-3 md:grid-cols-3">
          <button
            type="button"
            onClick={() => setActiveDetailsPanel('withdraw')}
            className={cn(
              'w-full rounded-lg border border-emerald-500/30 bg-emerald-500/5 text-left transition hover:border-emerald-400/50',
              useMobileUiV2 ? 'p-3' : 'p-4'
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={cn('font-semibold', useMobileUiV2 ? 'text-sm' : 'text-base')}>
                  {translateText(partnerLocale, 'partner.auto.051')}
                </p>
                {!useMobileUiV2 && (
                  <p className="text-xs text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.052')}
                  </p>
                )}
              </div>
              <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />
            </div>
            <p className={cn('font-bold', useMobileUiV2 ? 'mt-2 text-lg' : 'mt-3 text-xl')}>
              {formatAmountWithCurrency(availableBalanceDisplay, effectiveCurrency)}
            </p>
            <p className={cn('text-muted-foreground', useMobileUiV2 ? 'text-[11px]' : 'text-xs')}>
              {translateText(partnerLocale, 'partner.auto.053')}: {formatAmountWithCurrency(minWithdrawalDisplay, effectiveCurrency)}
              {showRubEquivalent ? ` • ${formatRub(minWithdrawalRub)}` : ''}
            </p>
            <p className={cn('mt-1 text-muted-foreground', useMobileUiV2 ? 'text-[11px]' : 'text-xs')}>
              {canWithdraw
                ? translateText(partnerLocale, 'partner.auto.054')
                : translateText(partnerLocale, 'partner.auto.055')}
            </p>
          </button>

          <button
            type="button"
            onClick={() => setActiveDetailsPanel('earnings')}
            className={cn(
              'w-full rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/5 text-left transition hover:border-fuchsia-400/50',
              useMobileUiV2 ? 'p-3' : 'p-4'
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={cn('font-semibold', useMobileUiV2 ? 'text-sm' : 'text-base')}>
                  {translateText(partnerLocale, 'partner.auto.056')}
                </p>
                {!useMobileUiV2 && (
                  <p className="text-xs text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.057')}
                  </p>
                )}
              </div>
              <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />
            </div>
            <p className={cn('font-bold', useMobileUiV2 ? 'mt-2 text-lg' : 'mt-3 text-xl')}>
              {earnings.length}
            </p>
            <p className={cn('text-muted-foreground', useMobileUiV2 ? 'text-[11px]' : 'text-xs')}>
              {latestEarning
                ? formatText(
                    translateText(partnerLocale, 'partner.auto.058'),
                    {
                      amount: formatAmountWithCurrency(
                        latestEarning.earned_amount_display ?? (latestEarning.earned_amount / 100),
                        latestEarning.display_currency || effectiveCurrency
                      ),
                    }
                  )
                : translateText(partnerLocale, 'partner.auto.059')}
            </p>
          </button>

          <button
            type="button"
            onClick={() => setActiveDetailsPanel('withdrawals')}
            className={cn(
              'w-full rounded-lg border border-lime-500/30 bg-lime-500/5 text-left transition hover:border-lime-400/50',
              useMobileUiV2 ? 'p-3' : 'p-4'
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={cn('font-semibold', useMobileUiV2 ? 'text-sm' : 'text-base')}>
                  {translateText(partnerLocale, 'partner.auto.060')}
                </p>
                {!useMobileUiV2 && (
                  <p className="text-xs text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.061')}
                  </p>
                )}
              </div>
              <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />
            </div>
            <p className={cn('font-bold', useMobileUiV2 ? 'mt-2 text-lg' : 'mt-3 text-xl')}>
              {withdrawals.length}
            </p>
            <p className={cn('text-muted-foreground', useMobileUiV2 ? 'text-[11px]' : 'text-xs')}>
              {withdrawals.length > 0
                ? `${pendingWithdrawalsCount} ${translateText(partnerLocale, 'partner.auto.062')}${latestWithdrawal ? `, ${translateText(partnerLocale, 'partner.auto.063')} ${formatSafeDate(latestWithdrawal.created_at, partnerLocale)}` : ''}`
                : translateText(partnerLocale, 'partner.auto.064')}
            </p>
          </button>
          </div>
        </div>
      )}

      <Sheet
        open={activeDetailsPanel !== null}
        onOpenChange={(open) => {
          if (!open) {
            setActiveDetailsPanel(null)
          }
        }}
      >
        <SheetContent
          side={useMobileUiV2 ? 'bottom' : 'right'}
          className={cn(
            useMobileUiV2
              ? 'max-h-[calc(100vh-0.5rem)] w-full overflow-y-auto border-t border-border p-4 pb-[calc(1rem+var(--app-safe-bottom,0px))]'
              : 'w-full max-w-full overflow-y-auto border-l border-border p-6 sm:max-w-2xl'
          )}
        >
          {activeDetailsPanel === 'withdraw' && (
            <div className="space-y-5">
              <SheetHeader>
                <SheetTitle>{translateText(partnerLocale, 'partner.auto.051')}</SheetTitle>
                <SheetDescription>
                  {translateText(partnerLocale, 'partner.auto.065')}
                </SheetDescription>
              </SheetHeader>

              <div className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 p-3">
                <p className="text-sm text-muted-foreground">{translateText(partnerLocale, 'partner.auto.025')}</p>
                <p className="text-2xl font-bold">{formatAmountWithCurrency(availableBalanceDisplay, effectiveCurrency)}</p>
              </div>

              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <AlertCircle className="h-4 w-4" />
                <span>
                  {translateText(partnerLocale, 'partner.auto.066')}: {formatAmountWithCurrency(minWithdrawalDisplay, effectiveCurrency)}
                  {showRubEquivalent ? ` • ${formatRub(minWithdrawalRub)}` : ''}
                  {!isPartnerActive
                    ? translateText(partnerLocale, 'partner.auto.067')
                    : ''}
                </span>
              </div>

              <form onSubmit={handleWithdraw} className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="amount">
                    {translateText(partnerLocale, 'partner.auto.068', { currency: effectiveCurrency })}
                  </Label>
                  <Input
                    id="amount"
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    min={minWithdrawalDisplay.toFixed(2)}
                    max={availableBalanceDisplay.toFixed(2)}
                    placeholder={translateText(partnerLocale, 'partner.auto.069')}
                    value={withdrawAmount}
                    onChange={(event) => setWithdrawAmount(event.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.070')}: {formatAmountWithCurrency(availableBalanceDisplay, effectiveCurrency)} |{' '}
                    {translateText(partnerLocale, 'partner.auto.053')}: {formatAmountWithCurrency(minWithdrawalDisplay, effectiveCurrency)}
                  </p>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="method">{translateText(partnerLocale, 'partner.auto.071')}</Label>
                  <Select value={withdrawMethod} onValueChange={setWithdrawMethod}>
                    <SelectTrigger>
                      <SelectValue placeholder={translateText(partnerLocale, 'partner.auto.072')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bank_transfer">{translateText(partnerLocale, 'partner.auto.073')}</SelectItem>
                      <SelectItem value="crypto">{translateText(partnerLocale, 'partner.auto.074')}</SelectItem>
                      <SelectItem value="paypal">{translateText(partnerLocale, 'partner.auto.075')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="requisites">{translateText(partnerLocale, 'partner.auto.076')}</Label>
                  <Input
                    id="requisites"
                    placeholder={translateText(partnerLocale, 'partner.auto.077')}
                    value={requisites}
                    onChange={(event) => setRequisites(event.target.value)}
                  />
                </div>

                <div className="flex items-center justify-end gap-2">
                  <Button type="button" variant="outline" onClick={() => setActiveDetailsPanel(null)}>
                    {translateText(partnerLocale, 'partner.auto.078')}
                  </Button>
                  <Button type="submit" disabled={withdrawMutation.isPending || !canWithdraw}>
                    {withdrawMutation.isPending
                      ? translateText(partnerLocale, 'partner.auto.079')
                      : translateText(partnerLocale, 'partner.auto.080')}
                  </Button>
                </div>
              </form>
            </div>
          )}

          {activeDetailsPanel === 'earnings' && (
            <div className="space-y-5">
              <SheetHeader>
                <SheetTitle>{translateText(partnerLocale, 'partner.auto.056')}</SheetTitle>
                <SheetDescription>{translateText(partnerLocale, 'partner.auto.081')}</SheetDescription>
              </SheetHeader>
              {earningsLoading ? (
                <EarningsSkeleton />
              ) : earnings.length > 0 ? (
                <div className="space-y-4">
                  {earnings.map((earning) => (
                    <EarningCard key={earning.id} earning={earning} locale={partnerLocale} />
                  ))}
                </div>
              ) : (
                <div className="py-12 text-center">
                  <TrendingUp className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                  <p className="text-muted-foreground">{translateText(partnerLocale, 'partner.auto.059')}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.082')}
                  </p>
                </div>
              )}
            </div>
          )}

          {activeDetailsPanel === 'withdrawals' && (
            <div className="space-y-5">
              <SheetHeader>
                <SheetTitle>{translateText(partnerLocale, 'partner.auto.060')}</SheetTitle>
                <SheetDescription>{translateText(partnerLocale, 'partner.auto.083')}</SheetDescription>
              </SheetHeader>
              {withdrawalsLoading ? (
                <WithdrawalsSkeleton />
              ) : withdrawals.length > 0 ? (
                <div className="space-y-4">
                  {withdrawals.map((withdrawal) => (
                    <WithdrawalCard key={withdrawal.id} withdrawal={withdrawal} locale={partnerLocale} />
                  ))}
                </div>
              ) : (
                <div className="py-12 text-center">
                  <Wallet className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                  <p className="text-muted-foreground">{translateText(partnerLocale, 'partner.auto.084')}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.085')}
                  </p>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={walletDialogOpen} onOpenChange={setWalletDialogOpen}>
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{translateText(partnerLocale, 'partner.mobile.walletModalTitle')}</DialogTitle>
            <DialogDescription>{translateText(partnerLocale, 'partner.mobile.walletModalDesc')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {translateText(partnerLocale, 'partner.auto.024')}
              </p>
              <p className="mt-1 text-2xl font-semibold">
                {formatAmountWithCurrency(availableBalanceDisplay, effectiveCurrency)}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {translateText(partnerLocale, 'partner.auto.053')}: {formatAmountWithCurrency(minWithdrawalDisplay, effectiveCurrency)}
                {showRubEquivalent ? ` • ${formatRub(minWithdrawalRub)}` : ''}
              </p>
              <p className="text-xs text-muted-foreground">
                {canWithdraw
                  ? translateText(partnerLocale, 'partner.auto.054')
                  : translateText(partnerLocale, 'partner.auto.055')}
              </p>
            </div>

            <button
              type="button"
              onClick={() => openDetailsPanel('withdraw')}
              className="w-full rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-left transition hover:border-emerald-400/50"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{translateText(partnerLocale, 'partner.auto.051')}</p>
                  <p className="text-xs text-muted-foreground">{translateText(partnerLocale, 'partner.auto.052')}</p>
                </div>
                <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />
              </div>
            </button>

            <button
              type="button"
              onClick={() => openDetailsPanel('earnings')}
              className="w-full rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/5 p-3 text-left transition hover:border-fuchsia-400/50"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{translateText(partnerLocale, 'partner.auto.056')}</p>
                  <p className="text-xs text-muted-foreground">
                    {latestEarning
                      ? formatText(
                          translateText(partnerLocale, 'partner.auto.058'),
                          {
                            amount: formatAmountWithCurrency(
                              latestEarning.earned_amount_display ?? (latestEarning.earned_amount / 100),
                              latestEarning.display_currency || effectiveCurrency
                            ),
                          }
                        )
                      : translateText(partnerLocale, 'partner.auto.059')}
                  </p>
                </div>
                <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />
              </div>
              <p className="mt-2 text-lg font-bold">{earnings.length}</p>
            </button>

            <button
              type="button"
              onClick={() => openDetailsPanel('withdrawals')}
              className="w-full rounded-lg border border-lime-500/30 bg-lime-500/5 p-3 text-left transition hover:border-lime-400/50"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{translateText(partnerLocale, 'partner.auto.060')}</p>
                  <p className="text-xs text-muted-foreground">
                    {withdrawals.length > 0
                      ? `${pendingWithdrawalsCount} ${translateText(partnerLocale, 'partner.auto.062')}${latestWithdrawal ? `, ${translateText(partnerLocale, 'partner.auto.063')} ${formatSafeDate(latestWithdrawal.created_at, partnerLocale)}` : ''}`
                      : translateText(partnerLocale, 'partner.auto.064')}
                  </p>
                </div>
                <ChevronRight className="mt-0.5 h-4 w-4 text-muted-foreground" />
              </div>
              <p className="mt-2 text-lg font-bold">{withdrawals.length}</p>
            </button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={summaryDialogOpen} onOpenChange={setSummaryDialogOpen}>
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{translateText(partnerLocale, 'partner.mobile.summaryModalTitle')}</DialogTitle>
            <DialogDescription>{translateText(partnerLocale, 'partner.mobile.summaryModalDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2.5">
              <p className="text-xs text-muted-foreground">
                {partnerSettingsMode} - {partnerRewardType === 'FIXED_AMOUNT'
                  ? translateText(partnerLocale, 'partner.auto.045')
                  : translateText(partnerLocale, 'partner.auto.046')}
                {' '}({partnerAccrualLabel})
              </p>
            </div>

            {partnerLevelSettings.map((levelSetting) => (
              <div key={levelSetting.level} className="rounded-lg border border-border/70 bg-white/[0.03] p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">
                      {translateText(partnerLocale, 'partner.auto.047')} {levelSetting.level}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatText(
                        translateText(partnerLocale, 'partner.auto.048'),
                        {
                          count: levelSetting.referrals_count,
                          amount: formatRubFromKopecks(levelSetting.earned_amount),
                        }
                      )}
                    </p>
                  </div>
                  <Badge variant={levelSetting.uses_global_value ? 'secondary' : 'default'}>
                    {levelSetting.uses_global_value
                      ? translateText(partnerLocale, 'partner.auto.049')
                      : translateText(partnerLocale, 'partner.auto.050')}
                  </Badge>
                </div>
                <p className="mt-2 text-sm font-semibold">{formatPartnerLevelReward(levelSetting, partnerLocale)}</p>
                <p className="text-xs text-muted-foreground">
                  {translateText(partnerLocale, 'partner.auto.049')}: {levelSetting.global_percent.toFixed(2)}%
                </p>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={analyticsDialogOpen} onOpenChange={setAnalyticsDialogOpen}>
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{translateText(partnerLocale, 'partner.mobile.analyticsModalTitle')}</DialogTitle>
            <DialogDescription>{translateText(partnerLocale, 'partner.mobile.analyticsModalDesc')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  {translateText(partnerLocale, 'partner.auto.088')}
                </p>
                <p className="mt-1 text-xl font-semibold">{activeReferrals}</p>
              </div>
              <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">
                  {translateText(partnerLocale, 'partner.auto.089')}
                </p>
                <p className="mt-1 text-sm font-medium">{translateText(partnerLocale, 'partner.auto.043')}: {webReferrals}</p>
                <p className="text-sm font-medium">{translateText(partnerLocale, 'partner.auto.090')}: {botReferrals}</p>
              </div>
            </div>

            <div className="rounded-lg border border-border/70 bg-background/60 p-3">
              <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                {translateText(partnerLocale, 'partner.auto.091')}
              </p>
              {referralsLoading ? (
                <ReferralsSkeleton />
              ) : referrals.length > 0 ? (
                <div className="space-y-2">
                  {referrals.map((referral) => {
                    const referralName = referral.username
                      ? `@${referral.username}`
                      : referral.name || formatText(translateText(partnerLocale, 'partner.auto.092'), { id: referral.telegram_id })
                    const joinedLabel = referral.joined_at
                      ? new Date(referral.joined_at).toLocaleDateString(partnerLocale === 'ru' ? 'ru-RU' : 'en-US')
                      : translateText(partnerLocale, 'partner.auto.093')

                    return (
                      <div
                        key={`${referral.telegram_id}-${referral.level}`}
                        className="rounded-md border border-border/70 px-2.5 py-2"
                      >
                        <p className="truncate text-sm font-medium">{referralName}</p>
                        <p className="text-xs text-muted-foreground">
                          L{referral.level} | {joinedLabel}
                        </p>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="py-6 text-center text-sm text-muted-foreground">
                  <Users className="mx-auto mb-2 h-5 w-5" />
                  {translateText(partnerLocale, 'partner.auto.094')}
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Card className="border-cyan-500/30">
        <CardHeader>
          <div>
            <CardTitle>{translateText(partnerLocale, 'partner.auto.086')}</CardTitle>
            {!useMobileUiV2 && (
              <CardDescription>
                {translateText(partnerLocale, 'partner.auto.087')}
              </CardDescription>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {useMobileUiV2 ? (
            <div className="space-y-3">
              <ReferralGrowthChart
                series={referralGrowthSeries}
                isLoading={referralsLoading}
                locale={partnerLocale}
                compact
              />
              <button
                type="button"
                onClick={() => setAnalyticsDialogOpen(true)}
                className="flex w-full items-center justify-between rounded-lg border border-border/70 bg-background/50 px-3 py-2.5 text-left transition hover:border-primary/40"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{translateText(partnerLocale, 'partner.auto.091')}</p>
                  <p className="text-xs text-muted-foreground">
                    {translateText(partnerLocale, 'partner.mobile.analyticsHint')}
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
              </button>
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                  <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {translateText(partnerLocale, 'partner.auto.088')}
                    </p>
                    <p className="mt-1 text-xl font-semibold">{activeReferrals}</p>
                  </div>
                  <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {translateText(partnerLocale, 'partner.auto.089')}
                    </p>
                    <p className="mt-1 text-sm font-medium">{translateText(partnerLocale, 'partner.auto.043')}: {webReferrals}</p>
                    <p className="text-sm font-medium">{translateText(partnerLocale, 'partner.auto.090')}: {botReferrals}</p>
                  </div>
                </div>

                <div className="rounded-lg border border-border/70 bg-background/60 p-3">
                  <p className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
                    {translateText(partnerLocale, 'partner.auto.091')}
                  </p>
                  {referralsLoading ? (
                    <ReferralsSkeleton />
                  ) : referrals.length > 0 ? (
                    <div className="space-y-2">
                      {referrals.slice(0, 5).map((referral) => {
                        const referralName = referral.username
                          ? `@${referral.username}`
                          : referral.name || formatText(translateText(partnerLocale, 'partner.auto.092'), { id: referral.telegram_id })
                        const joinedLabel = referral.joined_at
                          ? new Date(referral.joined_at).toLocaleDateString(partnerLocale === 'ru' ? 'ru-RU' : 'en-US')
                          : translateText(partnerLocale, 'partner.auto.093')

                        return (
                          <div
                            key={`${referral.telegram_id}-${referral.level}`}
                            className="rounded-md border border-border/70 px-2 py-1.5"
                          >
                            <p className="text-sm font-medium">{referralName}</p>
                            <p className="text-xs text-muted-foreground">
                              L{referral.level} | {joinedLabel}
                            </p>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <div className="py-6 text-center text-sm text-muted-foreground">
                      <Users className="mx-auto mb-2 h-5 w-5" />
                      {translateText(partnerLocale, 'partner.auto.094')}
                    </div>
                  )}
                </div>
              </div>

              <ReferralGrowthChart series={referralGrowthSeries} isLoading={referralsLoading} locale={partnerLocale} />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function ReferralGrowthChart({
  series,
  isLoading,
  locale,
  compact = false,
}: {
  series: DailyGrowthPoint[]
  isLoading: boolean
  locale: PartnerLocale
  compact?: boolean
}) {
  if (isLoading) {
    return (
      <div className={cn('rounded-lg border border-border/70', compact ? 'p-3' : 'p-4')}>
        <Skeleton className={cn('w-full', compact ? 'h-[190px]' : 'h-[220px]')} />
      </div>
    )
  }

  if (!series.length || Math.max(...series.map((item) => item.count)) === 0) {
    return (
      <div className={cn(
        'flex flex-col items-center justify-center rounded-lg border border-dashed border-cyan-500/40 bg-cyan-500/5 text-center',
        compact ? 'min-h-[200px] p-4' : 'min-h-[240px] p-6'
      )}>
        <Activity className={cn('mb-3 text-cyan-300', compact ? 'h-7 w-7' : 'h-8 w-8')} />
        <p className={cn('font-medium', compact && 'text-sm')}>{translateText(locale, 'partner.auto.095')}</p>
        <p className={cn('mt-1 text-muted-foreground', compact ? 'text-xs' : 'text-sm')}>
          {translateText(locale, 'partner.auto.096')}
        </p>
      </div>
    )
  }

  const width = 680
  const height = 240
  const paddingX = 28
  const paddingY = 24
  const baselineY = height - paddingY
  const innerWidth = width - paddingX * 2
  const innerHeight = height - paddingY * 2
  const maxValue = Math.max(...series.map((item) => item.count), 1)

  const coordinates = series.map((item, index) => {
    const x =
      series.length === 1
        ? paddingX + innerWidth / 2
        : paddingX + (index / (series.length - 1)) * innerWidth
    const y = baselineY - (item.count / maxValue) * innerHeight
    return { ...item, x, y }
  })

  const linePath = coordinates
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ')

  const areaPath = `${linePath} L ${coordinates[coordinates.length - 1].x.toFixed(2)} ${baselineY.toFixed(2)} L ${coordinates[0].x.toFixed(2)} ${baselineY.toFixed(2)} Z`

  const midIndex = Math.floor(series.length / 2)

  return (
    <div className={cn('rounded-lg border border-cyan-500/30 bg-cyan-500/5', compact ? 'p-3' : 'p-4')}>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className={cn('font-medium', compact ? 'text-xs' : 'text-sm')}>
            {translateText(locale, 'partner.auto.097')}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatText(translateText(locale, 'partner.auto.098'), { days: series.length })}
          </p>
        </div>
        <Badge variant="secondary">{translateText(locale, 'partner.auto.099')}: {maxValue}</Badge>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className={cn('w-full', compact ? 'h-[190px]' : 'h-[220px]')}>
        <defs>
          <linearGradient id="ref-growth-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(34 211 238)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(34 211 238)" stopOpacity="0" />
          </linearGradient>
        </defs>

        <line
          x1={paddingX}
          y1={baselineY}
          x2={width - paddingX}
          y2={baselineY}
          stroke="rgba(148,163,184,0.4)"
          strokeWidth="1"
        />

        <path d={areaPath} fill="url(#ref-growth-fill)" />
        <path d={linePath} fill="none" stroke="rgb(34 211 238)" strokeWidth="3" strokeLinecap="round" />

        {coordinates.map((point) => (
          <circle key={point.key} cx={point.x} cy={point.y} r="3.5" fill="rgb(34 211 238)" />
        ))}

        <text x={paddingX} y={height - 6} fill="rgba(148,163,184,0.8)" fontSize="11">
          {series[0].label}
        </text>
        <text
          x={coordinates[midIndex].x}
          y={height - 6}
          textAnchor="middle"
          fill="rgba(148,163,184,0.8)"
          fontSize="11"
        >
          {series[midIndex].label}
        </text>
        <text
          x={width - paddingX}
          y={height - 6}
          textAnchor="end"
          fill="rgba(148,163,184,0.8)"
          fontSize="11"
        >
          {series[series.length - 1].label}
        </text>
      </svg>
    </div>
  )
}

function PartnerInviteField({
  label,
  value,
  onCopy,
  isGenerating = false,
  locale,
  compact = false,
}: {
  label: string
  value: string
  onCopy: () => void
  isGenerating?: boolean
  locale: PartnerLocale
  compact?: boolean
}) {
  const hasValue = Boolean(value.trim())
  const placeholder = isGenerating
    ? translateText(locale, 'partner.auto.100')
    : translateText(locale, 'partner.auto.007')

  return (
    <div className="space-y-1.5">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          readOnly
          value={value}
          placeholder={placeholder}
          className={cn(
            'flex-1 rounded-md border bg-muted px-2.5 font-mono text-xs',
            compact ? 'h-11' : 'h-9'
          )}
        />
        <Button
          variant="outline"
          size="icon"
          className={cn(compact ? 'h-11 w-11' : 'h-9 w-9')}
          onClick={onCopy}
          disabled={!hasValue || isGenerating}
          aria-label={label}
        >
          <Copy className="h-4 w-4" />
        </Button>
      </div>
      {!hasValue && (
        <p className="text-[11px] text-muted-foreground">
          {isGenerating
            ? translateText(locale, 'partner.auto.100')
            : translateText(locale, 'partner.auto.007')}
        </p>
      )}
    </div>
  )
}

function EarningCard({ earning, locale }: { earning: PartnerEarning; locale: PartnerLocale }) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-4">
      <div className="flex items-center gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
          <span className="font-semibold text-primary">L{earning.level}</span>
        </div>
        <div>
          <p className="font-medium">@{earning.referral_username || translateText(locale, 'partner.auto.101')}</p>
          <p className="text-sm text-muted-foreground">
            {formatText(
              translateText(locale, 'partner.auto.102'),
              { level: earning.level, percent: earning.percent }
            )}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="font-bold text-emerald-300">
          +{formatAmountWithCurrency(
            earning.earned_amount_display ?? (earning.earned_amount / 100),
            earning.display_currency || 'RUB'
          )}
        </p>
        <p className="text-sm text-muted-foreground">
          {formatText(
            translateText(locale, 'partner.auto.103'),
            {
              amount: formatAmountWithCurrency(
                earning.payment_amount_display ?? (earning.payment_amount / 100),
                earning.display_currency || 'RUB'
              ),
            }
          )}
        </p>
      </div>
    </div>
  )
}

function WithdrawalCard({ withdrawal, locale }: { withdrawal: PartnerWithdrawal; locale: PartnerLocale }) {
  const normalizedStatus = normalizeWithdrawalStatus(withdrawal.status)

  const statusColors: Record<WithdrawalStatusNormalized, string> = {
    PENDING: 'bg-yellow-500',
    APPROVED: 'bg-green-500',
    COMPLETED: 'bg-green-500',
    REJECTED: 'bg-red-500',
    CANCELED: 'bg-slate-500',
    UNKNOWN: 'bg-slate-400',
  }

  const statusLabels: Record<WithdrawalStatusNormalized, string> = {
    PENDING: translateText(locale, 'partner.auto.104'),
    APPROVED: translateText(locale, 'partner.auto.105'),
    COMPLETED: translateText(locale, 'partner.auto.106'),
    REJECTED: translateText(locale, 'partner.auto.107'),
    CANCELED: translateText(locale, 'partner.auto.108'),
    UNKNOWN: translateText(locale, 'partner.auto.109'),
  }

  const badgeVariant =
    normalizedStatus === 'REJECTED'
      ? 'destructive'
      : normalizedStatus === 'APPROVED' || normalizedStatus === 'COMPLETED'
        ? 'default'
        : 'secondary'

  return (
    <div className="flex items-center justify-between rounded-lg border p-4">
      <div className="flex items-center gap-4">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-full ${statusColors[normalizedStatus]}`}
        >
          <Wallet className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="font-medium">{withdrawal.method || translateText(locale, 'partner.auto.110')}</p>
          <p className="text-sm text-muted-foreground">
            {new Date(withdrawal.created_at).toLocaleDateString(locale === 'ru' ? 'ru-RU' : 'en-US')}
          </p>
          {withdrawal.admin_comment && (
            <p className="mt-1 text-xs text-muted-foreground">{withdrawal.admin_comment}</p>
          )}
        </div>
      </div>
      <div className="text-right">
        <p className="font-bold">
          {formatAmountWithCurrency(
            withdrawal.display_amount ?? (withdrawal.amount / 100),
            withdrawal.display_currency || 'RUB'
          )}
        </p>
        {withdrawal.display_currency && withdrawal.display_currency !== 'RUB' && (
          <p className="text-xs text-muted-foreground">
            {formatRubFromKopecks(withdrawal.amount)}
          </p>
        )}
        <Badge variant={badgeVariant}>{statusLabels[normalizedStatus]}</Badge>
      </div>
    </div>
  )
}

function PartnerSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((skeletonId) => (
          <Card key={skeletonId}>
            <CardHeader className="pb-3">
              <Skeleton className="h-4 w-32" />
            </CardHeader>
            <CardContent>
              <Skeleton className="mb-2 h-8 w-16" />
              <Skeleton className="mb-4 h-3 w-24" />
              <Skeleton className="h-16 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function EarningsSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((skeletonId) => (
        <div key={skeletonId} className="flex items-center justify-between rounded-lg border p-4">
          <div className="flex items-center gap-4">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
          <Skeleton className="h-8 w-24" />
        </div>
      ))}
    </div>
  )
}

function WithdrawalsSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((skeletonId) => (
        <div key={skeletonId} className="flex items-center justify-between rounded-lg border p-4">
          <div className="flex items-center gap-4">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
          <Skeleton className="h-8 w-24" />
        </div>
      ))}
    </div>
  )
}

function ReferralsSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((skeletonId) => (
        <div key={skeletonId} className="rounded-md border px-2 py-2">
          <Skeleton className="mb-1 h-4 w-28" />
          <Skeleton className="h-3 w-32" />
        </div>
      ))}
    </div>
  )
}





