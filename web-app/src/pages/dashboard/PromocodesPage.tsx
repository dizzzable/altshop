import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { translateWithLocale, type TranslationParams } from '@/i18n/runtime'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { useSubscriptionsQuery } from '@/hooks/useSubscriptionsQuery'
import { queryKeys } from '@/lib/query-keys'
import { cn, formatRelativeTime } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Ticket,
  Check,
  AlertCircle,
  Gift,
  Percent,
  Clock,
  Database,
  History,
  PanelRightOpen,
  Copy,
  ChevronLeft,
  ChevronRight,
  Info,
} from 'lucide-react'
import { toast } from 'sonner'
import type { PromocodeActivateResult, PromocodeActivationHistoryItem } from '@/types'
import type { StoredGiftPromocode } from '@/lib/gift-promocodes'
import {
  getStoredGiftPromocodes,
  removeStoredGiftPromocode,
} from '@/lib/gift-promocodes'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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

const HISTORY_PAGE_SIZE = 20
const HISTORY_PREVIEW_LIMIT = 4

type PromoLocale = 'ru' | 'en'

function translatePromo(locale: PromoLocale, key: string, params?: TranslationParams): string {
  return translateWithLocale(locale, key, params)
}

type PromoText = {
  title: string
  subtitle: string
  activateTitle: string
  activateDesc: string
  activatePlaceholder: string
  activating: string
  activate: string
  statusSelectSubscription: string
  statusConfirmRequired: string
  statusActivated: string
  statusActivationFailed: string
  activationFailedFallback: string
  enterPromocode: string
  selectSubscriptionFirst: string
  rewardLabel: string
  promocodeCopied: string
  promocodeCopyFailed: string
  rewardTypesTitle: string
  rewardTypesDesc: string
  rewardTypeExtraDays: string
  rewardTypeExtraDaysDesc: string
  rewardTypeFreeSubscription: string
  rewardTypeFreeSubscriptionDesc: string
  rewardTypePurchaseDiscount: string
  rewardTypePurchaseDiscountDesc: string
  rewardTypeTraffic: string
  rewardTypeTrafficDesc: string
  rewardTypePersonalDiscount: string
  rewardTypePersonalDiscountDesc: string
  rewardTypeDevices: string
  rewardTypeDevicesDesc: string
  historyTitle: string
  historyDesc: string
  open: string
  showingLatest: string
  fullHistory: string
  noHistoryTitle: string
  noHistoryDesc: string
  howToTitle: string
  howToStep1Title: string
  howToStep1Desc: string
  howToStep2Title: string
  howToStep2Desc: string
  howToStep3Title: string
  howToStep3Desc: string
  notesTitle: string
  note1: string
  note2: string
  note3: string
  note4: string
  detailsTitle: string
  detailsDesc: string
  activationHistory: string
  total: string
  pageOf: string
  prev: string
  next: string
  availableGiftCodes: string
  noSavedGiftCodes: string
  activateShort: string
  savedAt: string
  giftHint: string
  selectSubscriptionDialogTitle: string
  createSubscriptionDialogTitle: string
  selectSubscriptionDialogDesc: string
  createSubscriptionDialogDesc: string
  selectSubscriptionPlaceholder: string
  noEligibleSubscriptions: string
  createSubscriptionInfo: string
  cancel: string
  processing: string
  confirm: string
  subscriptionPrefix: string
  infoOpen: string
  infoModalTitle: string
  infoModalDesc: string
}

const PROMO_TEXT_KEYS: Record<keyof PromoText, string> = {
  title: 'promocodes.title',
  subtitle: 'promocodes.subtitle',
  activateTitle: 'promocodes.activateTitle',
  activateDesc: 'promocodes.activateDesc',
  activatePlaceholder: 'promocodes.activatePlaceholder',
  activating: 'promocodes.activating',
  activate: 'promocodes.activate',
  statusSelectSubscription: 'promocodes.statusSelectSubscription',
  statusConfirmRequired: 'promocodes.statusConfirmRequired',
  statusActivated: 'promocodes.statusActivated',
  statusActivationFailed: 'promocodes.statusActivationFailed',
  activationFailedFallback: 'promocodes.activationFailedFallback',
  enterPromocode: 'promocodes.enterPromocode',
  selectSubscriptionFirst: 'promocodes.selectSubscriptionFirst',
  rewardLabel: 'promocodes.rewardLabel',
  promocodeCopied: 'promocodes.promocodeCopied',
  promocodeCopyFailed: 'promocodes.promocodeCopyFailed',
  rewardTypesTitle: 'promocodes.rewardTypesTitle',
  rewardTypesDesc: 'promocodes.rewardTypesDesc',
  rewardTypeExtraDays: 'promocodes.rewardTypeExtraDays',
  rewardTypeExtraDaysDesc: 'promocodes.rewardTypeExtraDaysDesc',
  rewardTypeFreeSubscription: 'promocodes.rewardTypeFreeSubscription',
  rewardTypeFreeSubscriptionDesc: 'promocodes.rewardTypeFreeSubscriptionDesc',
  rewardTypePurchaseDiscount: 'promocodes.rewardTypePurchaseDiscount',
  rewardTypePurchaseDiscountDesc: 'promocodes.rewardTypePurchaseDiscountDesc',
  rewardTypeTraffic: 'promocodes.rewardTypeTraffic',
  rewardTypeTrafficDesc: 'promocodes.rewardTypeTrafficDesc',
  rewardTypePersonalDiscount: 'promocodes.rewardTypePersonalDiscount',
  rewardTypePersonalDiscountDesc: 'promocodes.rewardTypePersonalDiscountDesc',
  rewardTypeDevices: 'promocodes.rewardTypeDevices',
  rewardTypeDevicesDesc: 'promocodes.rewardTypeDevicesDesc',
  historyTitle: 'promocodes.historyTitle',
  historyDesc: 'promocodes.historyDesc',
  open: 'promocodes.open',
  showingLatest: 'promocodes.showingLatest',
  fullHistory: 'promocodes.fullHistory',
  noHistoryTitle: 'promocodes.noHistoryTitle',
  noHistoryDesc: 'promocodes.noHistoryDesc',
  howToTitle: 'promocodes.howToTitle',
  howToStep1Title: 'promocodes.howToStep1Title',
  howToStep1Desc: 'promocodes.howToStep1Desc',
  howToStep2Title: 'promocodes.howToStep2Title',
  howToStep2Desc: 'promocodes.howToStep2Desc',
  howToStep3Title: 'promocodes.howToStep3Title',
  howToStep3Desc: 'promocodes.howToStep3Desc',
  notesTitle: 'promocodes.notesTitle',
  note1: 'promocodes.note1',
  note2: 'promocodes.note2',
  note3: 'promocodes.note3',
  note4: 'promocodes.note4',
  detailsTitle: 'promocodes.detailsTitle',
  detailsDesc: 'promocodes.detailsDesc',
  activationHistory: 'promocodes.activationHistory',
  total: 'promocodes.total',
  pageOf: 'promocodes.pageOf',
  prev: 'promocodes.prev',
  next: 'promocodes.next',
  availableGiftCodes: 'promocodes.availableGiftCodes',
  noSavedGiftCodes: 'promocodes.noSavedGiftCodes',
  activateShort: 'promocodes.activateShort',
  savedAt: 'promocodes.savedAt',
  giftHint: 'promocodes.giftHint',
  selectSubscriptionDialogTitle: 'promocodes.selectSubscriptionDialogTitle',
  createSubscriptionDialogTitle: 'promocodes.createSubscriptionDialogTitle',
  selectSubscriptionDialogDesc: 'promocodes.selectSubscriptionDialogDesc',
  createSubscriptionDialogDesc: 'promocodes.createSubscriptionDialogDesc',
  selectSubscriptionPlaceholder: 'promocodes.selectSubscriptionPlaceholder',
  noEligibleSubscriptions: 'promocodes.noEligibleSubscriptions',
  createSubscriptionInfo: 'promocodes.createSubscriptionInfo',
  cancel: 'promocodes.cancel',
  processing: 'promocodes.processing',
  confirm: 'promocodes.confirm',
  subscriptionPrefix: 'promocodes.subscriptionPrefix',
  infoOpen: 'promocodes.infoOpen',
  infoModalTitle: 'promocodes.infoModalTitle',
  infoModalDesc: 'promocodes.infoModalDesc',
}

function buildPromoText(locale: PromoLocale): PromoText {
  return Object.fromEntries(
    Object.entries(PROMO_TEXT_KEYS).map(([field, key]) => [field, translatePromo(locale, key)])
  ) as PromoText
}

function formatText(template: string, params: TranslationParams): string {
  return Object.entries(params).reduce(
    (accumulator, [key, value]) => accumulator.replaceAll(`{${key}}`, String(value)),
    template
  )
}

export function PromocodesPage() {
  const { refreshUser } = useAuth()
  const { locale } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const promoLocale: PromoLocale = locale === 'en' ? 'en' : 'ru'
  const text = useMemo(() => buildPromoText(promoLocale), [promoLocale])
  const queryClient = useQueryClient()
  const [code, setCode] = useState('')
  const [historyPage, setHistoryPage] = useState(1)
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false)
  const [infoDialogOpen, setInfoDialogOpen] = useState(false)
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<number | null>(null)
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [pendingCode, setPendingCode] = useState<string | null>(null)
  const [pendingResult, setPendingResult] = useState<PromocodeActivateResult | null>(null)
  const [storedGiftPromocodes, setStoredGiftPromocodes] = useState<StoredGiftPromocode[]>(
    () => getStoredGiftPromocodes()
  )
  const [activationStatus, setActivationStatus] = useState<{
    kind: 'success' | 'info' | 'error'
    title: string
    message: string
  } | null>(null)

  const { data: subscriptions } = useSubscriptionsQuery()

  const { data: previewHistoryData, isLoading: previewHistoryLoading } = useQuery({
    queryKey: queryKeys.promocodeActivationsPreviewLimit(HISTORY_PREVIEW_LIMIT),
    queryFn: () => api.promocode.history(1, HISTORY_PREVIEW_LIMIT).then((r) => r.data),
  })

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: queryKeys.promocodeActivationsPage(historyPage, HISTORY_PAGE_SIZE),
    queryFn: () => api.promocode.history(historyPage, HISTORY_PAGE_SIZE).then((r) => r.data),
    enabled: historyDialogOpen,
  })

  const previewHistoryItems = previewHistoryData?.activations || []
  const previewHistoryTotal = previewHistoryData?.total || 0
  const historyItems = historyData?.activations || []
  const historyTotal = historyData?.total || 0
  const historyTotalPages = Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE))

  const selectableSubscriptions = useMemo(() => {
    const list = subscriptions || []
    const availableIds = pendingResult?.available_subscriptions
    if (!availableIds || availableIds.length === 0) {
      return list
    }

    const idSet = new Set(availableIds)
    return list.filter((subscription) => idSet.has(subscription.id))
  }, [pendingResult?.available_subscriptions, subscriptions])

  const resetPendingState = () => {
    setPendingCode(null)
    setPendingResult(null)
    setSelectedSubscriptionId(null)
    setConfirmDialogOpen(false)
  }

  const refreshStoredGiftCodes = () => {
    setStoredGiftPromocodes(getStoredGiftPromocodes())
  }

  const handleActivationResult = (result: PromocodeActivateResult, activationCode: string) => {
    if (result.next_step === 'SELECT_SUBSCRIPTION') {
      setPendingCode(activationCode)
      setPendingResult(result)
      const defaultId = result.available_subscriptions?.[0] ?? null
      setSelectedSubscriptionId(defaultId)
      setConfirmDialogOpen(true)
      setActivationStatus({
        kind: 'info',
        title: text.statusSelectSubscription,
        message: result.message,
      })
      toast.info(result.message)
      return
    }

    if (result.next_step === 'CREATE_NEW') {
      setPendingCode(activationCode)
      setPendingResult(result)
      setSelectedSubscriptionId(null)
      setConfirmDialogOpen(true)
      setActivationStatus({
        kind: 'info',
        title: text.statusConfirmRequired,
        message: result.message,
      })
      toast.info(result.message)
      return
    }

    setHistoryPage(1)
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.userProfile() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.referralInfo() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.partnerInfo() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.promocodeActivations() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.promocodeActivationsPreview() }),
    ])
    void refreshUser()

    const rewardText = result.reward
      ? ` ${text.rewardLabel}: ${result.reward.value} ${getRewardUnit(result.reward.type, promoLocale)}.`
      : ''
    setActivationStatus({
      kind: 'success',
      title: text.statusActivated,
      message: `${result.message}${rewardText}`,
    })
    toast.success(result.message)
    if (result.reward) {
      toast.info(`${text.rewardLabel}: ${result.reward.value} ${getRewardUnit(result.reward.type, promoLocale)}`)
    }
    removeStoredGiftPromocode(activationCode)
    refreshStoredGiftCodes()
    setCode('')
    resetPendingState()
  }

  const activateMutation = useMutation({
    mutationFn: (payload: { code: string; subscription_id?: number; create_new?: boolean }) =>
      api.promocode.activate(payload),
    onSuccess: (response, payload) => {
      handleActivationResult(response.data, payload.code)
    },
    onError: (error: unknown) => {
      const detail = getApiErrorMessage(error) || text.activationFailedFallback
      setActivationStatus({
        kind: 'error',
        title: text.statusActivationFailed,
        message: detail,
      })
      toast.error(detail)
    },
  })

  const handleActivate = (e: React.FormEvent) => {
    e.preventDefault()
    const normalizedCode = code.trim().toUpperCase()
    if (!normalizedCode) {
      toast.error(text.enterPromocode)
      return
    }

    setActivationStatus(null)
    setCode(normalizedCode)
    activateMutation.mutate({ code: normalizedCode })
  }

  const handleConfirm = () => {
    if (!pendingResult || !pendingCode) {
      return
    }

    if (pendingResult.next_step === 'SELECT_SUBSCRIPTION') {
      if (!selectedSubscriptionId) {
        toast.error(text.selectSubscriptionFirst)
        return
      }

      activateMutation.mutate({
        code: pendingCode,
        subscription_id: selectedSubscriptionId,
      })
      return
    }

    if (pendingResult.next_step === 'CREATE_NEW') {
      activateMutation.mutate({
        code: pendingCode,
        create_new: true,
      })
      return
    }

    resetPendingState()
  }

  const applyStoredCode = (storedCode: string) => {
    const normalizedCode = storedCode.trim().toUpperCase()
    if (!normalizedCode) {
      return
    }
    setActivationStatus(null)
    setCode(normalizedCode)
    activateMutation.mutate({ code: normalizedCode })
  }

  const copyStoredCode = async (storedCode: string) => {
    try {
      await navigator.clipboard.writeText(storedCode)
      toast.success(text.promocodeCopied)
    } catch {
      toast.error(text.promocodeCopyFailed)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">{text.title}</h1>
        <p className="text-muted-foreground">{text.subtitle}</p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
          <div>
            <CardTitle>{text.activateTitle}</CardTitle>
            <CardDescription>{text.activateDesc}</CardDescription>
          </div>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="h-10 w-10 shrink-0 border-primary/35 bg-primary/12 text-primary hover:bg-primary/20"
            onClick={() => setInfoDialogOpen(true)}
            aria-label={text.infoOpen}
          >
            <Info className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleActivate} className="flex gap-2">
            <Input
              type="text"
              placeholder={text.activatePlaceholder}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              disabled={activateMutation.isPending}
              className="flex-1 uppercase"
            />
            <Button type="submit" disabled={activateMutation.isPending}>
              {activateMutation.isPending ? (
                <>{text.activating}</>
              ) : (
                <>
                  <Ticket className="h-4 w-4 mr-2" />
                  {text.activate}
                </>
              )}
            </Button>
          </form>

          {activationStatus && (
            <div
              className={
                activationStatus.kind === 'success'
                  ? 'mt-4 rounded-lg border border-emerald-300/20 bg-emerald-500/10 p-3'
                  : activationStatus.kind === 'error'
                    ? 'mt-4 rounded-lg border border-red-300/20 bg-red-500/10 p-3'
                    : 'mt-4 rounded-lg border border-amber-300/20 bg-amber-500/10 p-3'
              }
            >
              <p className="text-sm font-semibold">{activationStatus.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{activationStatus.message}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className={cn('grid gap-6', useMobileUiV2 ? '' : 'lg:grid-cols-[0.85fr_1.15fr]')}>
        {!useMobileUiV2 && (
          <Card className="h-full lg:flex lg:min-h-[clamp(360px,48vh,540px)] lg:flex-col">
            <CardHeader>
              <CardTitle>{text.rewardTypesTitle}</CardTitle>
              <CardDescription>{text.rewardTypesDesc}</CardDescription>
            </CardHeader>
            <CardContent className="lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
              <div className="grid gap-2">
                <RewardTypeCard
                  icon={Clock}
                  title={text.rewardTypeExtraDays}
                  description={text.rewardTypeExtraDaysDesc}
                  color="text-sky-400"
                  compact
                />
                <RewardTypeCard
                  icon={Gift}
                  title={text.rewardTypeFreeSubscription}
                  description={text.rewardTypeFreeSubscriptionDesc}
                  color="text-indigo-400"
                  compact
                />
                <RewardTypeCard
                  icon={Ticket}
                  title={text.rewardTypePurchaseDiscount}
                  description={text.rewardTypePurchaseDiscountDesc}
                  color="text-slate-300"
                  compact
                />
                <RewardTypeCard
                  icon={Database}
                  title={text.rewardTypeTraffic}
                  description={text.rewardTypeTrafficDesc}
                  color="text-cyan-400"
                  compact
                />
                <RewardTypeCard
                  icon={Percent}
                  title={text.rewardTypePersonalDiscount}
                  description={text.rewardTypePersonalDiscountDesc}
                  color="text-blue-400"
                  compact
                />
                <RewardTypeCard
                  icon={Check}
                  title={text.rewardTypeDevices}
                  description={text.rewardTypeDevicesDesc}
                  color="text-teal-400"
                  compact
                />
              </div>
            </CardContent>
          </Card>
        )}

        <Card className={cn('h-full', useMobileUiV2 ? '' : 'lg:flex lg:min-h-[clamp(360px,48vh,540px)] lg:flex-col')}>
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5 text-sky-300" />
                {text.historyTitle}
              </CardTitle>
              <CardDescription>{text.historyDesc}</CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setHistoryPage(1)
                setHistoryDialogOpen(true)
              }}
            >
              <PanelRightOpen className="mr-1 h-4 w-4" />
              {text.open}
            </Button>
          </CardHeader>
          <CardContent className="lg:flex lg:flex-1 lg:min-h-0 lg:flex-col">
            {previewHistoryLoading ? (
              <div className="space-y-3 lg:flex-1 lg:min-h-0 lg:overflow-y-auto lg:pr-1">
                {[1, 2, 3, 4].map((item) => (
                  <div key={item} className="h-14 rounded-lg border bg-muted/30" />
                ))}
              </div>
            ) : previewHistoryItems.length > 0 ? (
              <>
                <div className="space-y-2 lg:flex-1 lg:min-h-0 lg:overflow-y-auto lg:pr-1">
                  {previewHistoryItems.map((activation) => (
                    <ActivationHistoryCard key={activation.id} activation={activation} compact locale={promoLocale} />
                  ))}
                </div>
                <div className="mt-4 flex items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    {formatText(text.showingLatest, {
                      shown: Math.min(HISTORY_PREVIEW_LIMIT, previewHistoryItems.length),
                      total: previewHistoryTotal,
                    })}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setHistoryPage(1)
                      setHistoryDialogOpen(true)
                    }}
                  >
                    {text.fullHistory}
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-center py-12 lg:flex lg:h-full lg:flex-1 lg:items-center lg:justify-center lg:py-0">
                <div>
                  <History className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                  <p className="text-muted-foreground">{text.noHistoryTitle}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {text.noHistoryDesc}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {!useMobileUiV2 && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{text.howToTitle}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-primary">1</span>
                  </div>
                  <div>
                    <h3 className="font-semibold">{text.howToStep1Title}</h3>
                    <p className="text-sm text-muted-foreground">
                      {text.howToStep1Desc}
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-primary">2</span>
                  </div>
                  <div>
                    <h3 className="font-semibold">{text.howToStep2Title}</h3>
                    <p className="text-sm text-muted-foreground">
                      {text.howToStep2Desc}
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-primary">3</span>
                  </div>
                  <div>
                    <h3 className="font-semibold">{text.howToStep3Title}</h3>
                    <p className="text-sm text-muted-foreground">
                      {text.howToStep3Desc}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertCircle className="h-5 w-5" />
                {text.notesTitle}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-muted-foreground">- {text.note1}</p>
              <p className="text-sm text-muted-foreground">- {text.note2}</p>
              <p className="text-sm text-muted-foreground">- {text.note3}</p>
              <p className="text-sm text-muted-foreground">- {text.note4}</p>
            </CardContent>
          </Card>
        </>
      )}

      <Dialog open={infoDialogOpen} onOpenChange={setInfoDialogOpen}>
        <DialogContent className="max-h-[calc(100vh-var(--app-safe-top)-1rem)] overflow-y-auto overscroll-y-contain pt-[calc(1rem+var(--app-safe-top))] [&>button]:top-[calc(0.75rem+var(--app-safe-top))] sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{text.infoModalTitle}</DialogTitle>
            <DialogDescription>{text.infoModalDesc}</DialogDescription>
          </DialogHeader>

          <div className="space-y-5">
            <section className="space-y-2">
              <h3 className="text-sm font-semibold text-slate-100">{text.rewardTypesTitle}</h3>
              <p className="text-xs text-muted-foreground">{text.rewardTypesDesc}</p>
              <div className="grid gap-2">
                <RewardTypeCard
                  icon={Clock}
                  title={text.rewardTypeExtraDays}
                  description={text.rewardTypeExtraDaysDesc}
                  color="text-sky-400"
                  compact
                />
                <RewardTypeCard
                  icon={Gift}
                  title={text.rewardTypeFreeSubscription}
                  description={text.rewardTypeFreeSubscriptionDesc}
                  color="text-indigo-400"
                  compact
                />
                <RewardTypeCard
                  icon={Ticket}
                  title={text.rewardTypePurchaseDiscount}
                  description={text.rewardTypePurchaseDiscountDesc}
                  color="text-slate-300"
                  compact
                />
                <RewardTypeCard
                  icon={Database}
                  title={text.rewardTypeTraffic}
                  description={text.rewardTypeTrafficDesc}
                  color="text-cyan-400"
                  compact
                />
                <RewardTypeCard
                  icon={Percent}
                  title={text.rewardTypePersonalDiscount}
                  description={text.rewardTypePersonalDiscountDesc}
                  color="text-blue-400"
                  compact
                />
                <RewardTypeCard
                  icon={Check}
                  title={text.rewardTypeDevices}
                  description={text.rewardTypeDevicesDesc}
                  color="text-teal-400"
                  compact
                />
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-sm font-semibold text-slate-100">{text.howToTitle}</h3>
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">1. {text.howToStep1Title}: {text.howToStep1Desc}</p>
                <p className="text-sm text-muted-foreground">2. {text.howToStep2Title}: {text.howToStep2Desc}</p>
                <p className="text-sm text-muted-foreground">3. {text.howToStep3Title}: {text.howToStep3Desc}</p>
              </div>
            </section>

            <section className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                <AlertCircle className="h-4 w-4" />
                {text.notesTitle}
              </h3>
              <p className="text-sm text-muted-foreground">- {text.note1}</p>
              <p className="text-sm text-muted-foreground">- {text.note2}</p>
              <p className="text-sm text-muted-foreground">- {text.note3}</p>
              <p className="text-sm text-muted-foreground">- {text.note4}</p>
            </section>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={historyDialogOpen}
        onOpenChange={(open) => {
          setHistoryDialogOpen(open)
          if (open) {
            setHistoryPage(1)
            refreshStoredGiftCodes()
          }
        }}
      >
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain [touch-action:pan-y] [-webkit-overflow-scrolling:touch] sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <History className="h-5 w-5 text-sky-300" />
              {text.detailsTitle}
            </DialogTitle>
            <DialogDescription>
              {text.detailsDesc}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr] lg:min-h-0">
            <div className="flex min-h-0 flex-col rounded-lg border p-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="text-sm font-medium">{text.activationHistory}</p>
                <Badge variant="secondary">{historyTotal} {text.total}</Badge>
              </div>

              {historyLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((item) => (
                    <div key={item} className="h-14 rounded-lg border bg-muted/30" />
                  ))}
                </div>
              ) : historyItems.length > 0 ? (
                <>
                  <div className="min-h-0 space-y-2 overflow-y-auto pr-1">
                    {historyItems.map((activation) => (
                      <ActivationHistoryCard key={activation.id} activation={activation} compact locale={promoLocale} />
                    ))}
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <p className="text-xs text-muted-foreground">
                      {formatText(text.pageOf, { page: historyPage, total: historyTotalPages })}
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
                        disabled={historyPage <= 1}
                      >
                        <ChevronLeft className="mr-1 h-4 w-4" />
                        {text.prev}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.min(historyTotalPages, prev + 1))}
                        disabled={historyPage >= historyTotalPages}
                      >
                        {text.next}
                        <ChevronRight className="ml-1 h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
                  {text.noHistoryTitle}
                </div>
              )}
            </div>

            <div className="flex min-h-0 flex-col rounded-lg border p-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="text-sm font-medium">{text.availableGiftCodes}</p>
                <Badge variant="secondary">{storedGiftPromocodes.length}</Badge>
              </div>

              {storedGiftPromocodes.length > 0 ? (
                <div className="min-h-0 space-y-2 overflow-y-auto pr-1">
                  {storedGiftPromocodes.map((item) => (
                    <div key={item.code} className="rounded-lg border p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-mono text-sm font-semibold tracking-wide">{item.code}</p>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" onClick={() => copyStoredCode(item.code)}>
                            <Copy className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => {
                              setHistoryDialogOpen(false)
                              applyStoredCode(item.code)
                            }}
                            disabled={activateMutation.isPending}
                          >
                            {text.activateShort}
                          </Button>
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatText(text.savedAt, { date: formatShortDateTime(item.createdAt) })}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex h-[220px] items-center justify-center text-center text-sm text-muted-foreground">
                  {text.noSavedGiftCodes}
                </div>
              )}

              <p className="mt-3 text-xs text-muted-foreground">
                {text.giftHint}
              </p>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={confirmDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            resetPendingState()
          } else {
            setConfirmDialogOpen(true)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pendingResult?.next_step === 'SELECT_SUBSCRIPTION'
                ? text.selectSubscriptionDialogTitle
                : text.createSubscriptionDialogTitle}
            </DialogTitle>
            <DialogDescription>
              {pendingResult?.next_step === 'SELECT_SUBSCRIPTION'
                ? text.selectSubscriptionDialogDesc
                : text.createSubscriptionDialogDesc}
            </DialogDescription>
          </DialogHeader>

          {pendingResult?.next_step === 'SELECT_SUBSCRIPTION' && (
            <div className="py-4">
              {selectableSubscriptions.length > 0 ? (
                <Select
                  value={selectedSubscriptionId?.toString()}
                  onValueChange={(value) => setSelectedSubscriptionId(Number(value))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={text.selectSubscriptionPlaceholder} />
                  </SelectTrigger>
                  <SelectContent>
                    {selectableSubscriptions.map((subscription) => (
                      <SelectItem key={subscription.id} value={subscription.id.toString()}>
                        {subscription.plan.name} - {subscription.status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <p className="text-sm text-muted-foreground">{text.noEligibleSubscriptions}</p>
              )}
            </div>
          )}

          {pendingResult?.next_step === 'CREATE_NEW' && (
            <div className="rounded-md border border-sky-300/20 bg-sky-500/12 p-3 py-4">
              <p className="text-sm">{text.createSubscriptionInfo}</p>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={resetPendingState}>
              {text.cancel}
            </Button>
            <Button onClick={handleConfirm} disabled={activateMutation.isPending}>
              {activateMutation.isPending ? text.processing : text.confirm}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ActivationHistoryCard({
  activation,
  compact = false,
  locale,
}: {
  activation: PromocodeActivationHistoryItem
  compact?: boolean
  locale: PromoLocale
}) {
  const text = buildPromoText(locale)
  const rewardTypeLabel = getRewardTypeLabel(activation.reward.type, locale, compact)
  const rewardColorClass = getRewardValueClass(activation.reward.type)

  return (
    <div className={`flex items-center justify-between gap-3 rounded-lg border ${compact ? 'p-2.5' : 'p-3'}`}>
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-semibold">{activation.code}</p>
        <p className="text-xs text-muted-foreground">{formatRelativeTime(activation.activated_at)}</p>
        {!compact && (
          <p className="text-xs text-muted-foreground">{new Date(activation.activated_at).toLocaleString()}</p>
        )}
      </div>
      <div className="text-right">
        <p className={`text-sm font-semibold ${rewardColorClass}`}>
          +{activation.reward.value} {getRewardUnit(activation.reward.type, locale)}
        </p>
        <p className="text-xs text-muted-foreground">{rewardTypeLabel}</p>
        {activation.target_subscription_id ? (
          <p className="text-xs text-muted-foreground">
            {text.subscriptionPrefix}{activation.target_subscription_id}
          </p>
        ) : null}
      </div>
    </div>
  )
}

function RewardTypeCard({
  icon: Icon,
  title,
  description,
  color,
  compact = false,
}: {
  icon: React.ElementType
  title: string
  description: string
  color: string
  compact?: boolean
}) {
  return (
    <div className={`flex h-full min-w-0 gap-3 rounded-lg border ${compact ? 'p-2.5' : 'p-3'}`}>
      <Icon className={`${compact ? 'h-5 w-5' : 'h-6 w-6'} ${color} flex-shrink-0`} />
      <div className="min-w-0">
        <h3 className={`font-medium ${compact ? 'text-[13px]' : 'text-sm'}`}>{title}</h3>
        <p className={`break-words text-muted-foreground ${compact ? 'text-[11px]' : 'text-xs'}`}>
          {description}
        </p>
      </div>
    </div>
  )
}

function formatShortDateTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString()
}

function getRewardTypeLabel(type: string, locale: PromoLocale, compact = false): string {
  const prefix = compact ? 'promocodes.rewardTypeShort' : 'promocodes.rewardType'

  switch (type) {
    case 'DURATION':
      return translatePromo(locale, `${prefix}ExtraDays`)
    case 'TRAFFIC':
      return translatePromo(locale, `${prefix}Traffic`)
    case 'DEVICES':
      return translatePromo(locale, `${prefix}Devices`)
    case 'SUBSCRIPTION':
      return translatePromo(locale, `${prefix}FreeSubscription`)
    case 'PERSONAL_DISCOUNT':
      return translatePromo(locale, `${prefix}PersonalDiscount`)
    case 'PURCHASE_DISCOUNT':
      return translatePromo(locale, `${prefix}PurchaseDiscount`)
    default:
      return translatePromo(locale, 'promocodes.rewardLabel')
  }
}

function getRewardValueClass(type: string): string {
  switch (type) {
    case 'DURATION':
      return 'text-sky-300'
    case 'TRAFFIC':
      return 'text-cyan-300'
    case 'DEVICES':
      return 'text-teal-300'
    case 'SUBSCRIPTION':
      return 'text-indigo-300'
    case 'PERSONAL_DISCOUNT':
      return 'text-blue-300'
    case 'PURCHASE_DISCOUNT':
      return 'text-slate-200'
    default:
      return 'text-sky-300'
  }
}

function getRewardUnit(type: string, locale: PromoLocale): string {
  switch (type) {
    case 'DURATION':
      return translatePromo(locale, 'promocodes.rewardUnit.days')
    case 'TRAFFIC':
      return translatePromo(locale, 'promocodes.rewardUnit.gb')
    case 'DEVICES':
      return translatePromo(locale, 'promocodes.rewardUnit.slots')
    case 'SUBSCRIPTION':
      return translatePromo(locale, 'promocodes.rewardUnit.subscription')
    case 'PERSONAL_DISCOUNT':
    case 'PURCHASE_DISCOUNT':
      return translatePromo(locale, 'promocodes.rewardUnit.discount')
    default:
      return translatePromo(locale, 'promocodes.rewardUnit.rewards')
  }
}
