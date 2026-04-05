import { useEffect, useMemo, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { useAccessStatusQuery } from '@/hooks/useAccessStatusQuery'
import { useSubscriptionsQuery } from '@/hooks/useSubscriptionsQuery'
import { resolveAccessCapabilities } from '@/lib/access-capabilities'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Smartphone,
  RefreshCw,
  Copy,
  MoreVertical,
  Trash2,
  Link2,
  ExternalLink,
  Check,
  Ticket,
  Info,
  ShoppingCart,
  ArrowUpCircle,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMediaQuery } from 'react-responsive'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  formatLimitLabel,
  formatPlanTypeLabel,
  getSubscriptionDeviceSummary,
} from '@/lib/subscription-display'
import { formatBytes, formatDays, gigabytesToBytes, cn } from '@/lib/utils'
import { openExternalLink } from '@/lib/openExternalLink'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { useMobileTelegramUiV2 as useMobileUiV2Gate } from '@/hooks/useMobileTelegramUiV2'
import {
  addStoredGiftPromocode,
  getStoredGiftPromocodes,
  removeStoredGiftPromocode,
} from '@/lib/gift-promocodes'
import type { StoredGiftPromocode } from '@/lib/gift-promocodes'
import {
  clearPendingPurchaseContext,
  readPendingPurchaseContext,
  resolveSubscriptionForConnect,
} from '@/lib/purchase-context'
import { toast } from 'sonner'
import type { PromocodeActivateResult, PromocodeRewardType, Subscription } from '@/types'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

function canRenewSubscription(subscription: Subscription): boolean {
  return subscription.can_renew
}

function canUpgradeSubscription(subscription: Subscription): boolean {
  return subscription.can_upgrade
}

function canMultiRenewSubscription(subscription: Subscription): boolean {
  return subscription.can_multi_renew
}

interface SubscriptionCardActionState {
  canRenew: boolean
  canUpgrade: boolean
  canMultiRenew: boolean
  showRenew: boolean
  showUpgrade: boolean
}

function getSubscriptionCardActionState(
  subscription: Subscription,
  canPurchaseSubscriptions: boolean,
  multiRenewMode: boolean
): SubscriptionCardActionState {
  const canRenew = canPurchaseSubscriptions && canRenewSubscription(subscription)
  const canUpgrade = canPurchaseSubscriptions && canUpgradeSubscription(subscription)
  const canMultiRenew = canPurchaseSubscriptions && canMultiRenewSubscription(subscription)

  return {
    canRenew,
    canUpgrade,
    canMultiRenew,
    showRenew: canRenew && !multiRenewMode,
    showUpgrade: canUpgrade && !multiRenewMode,
  }
}

function extractErrorDetail(error: unknown): string | null {
  const detail = (
    error as { response?: { data?: { detail?: unknown } } }
  )?.response?.data?.detail
  return typeof detail === 'string' && detail.length > 0 ? detail : null
}

const MOBILE_LONG_PRESS_DURATION_MS = 430
const MOBILE_LONG_PRESS_MOVE_CANCEL_PX = 10

export function SubscriptionPage() {
  const { user, refreshUser } = useAuth()
  const { t, locale } = useI18n()
  const { tg } = useTelegramWebApp()
  const navigate = useNavigate()
  const isMobileActions = useMediaQuery({ maxWidth: 820 })
  const useMobileTelegramUiV2 = useMobileUiV2Gate()
  const { data: accessStatus } = useAccessStatusQuery()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [openPaymentSuccessDialog, setOpenPaymentSuccessDialog] = useState(false)
  const [connectTarget, setConnectTarget] = useState<Subscription | null>(null)
  const [shouldResolveSuccessDialog, setShouldResolveSuccessDialog] = useState(false)
  const [isMultiRenewMode, setIsMultiRenewMode] = useState(false)
  const [selectedRenewIds, setSelectedRenewIds] = useState<number[]>([])
  const [promocodeDialogOpen, setPromocodeDialogOpen] = useState(false)
  const [promocodeConfirmDialogOpen, setPromocodeConfirmDialogOpen] = useState(false)
  const [promocodeInput, setPromocodeInput] = useState('')
  const [pendingPromocode, setPendingPromocode] = useState<string | null>(null)
  const [pendingPromocodeResult, setPendingPromocodeResult] = useState<PromocodeActivateResult | null>(null)
  const [selectedPromocodeSubscriptionId, setSelectedPromocodeSubscriptionId] = useState<number | null>(null)
  const [openStatsInfoDialog, setOpenStatsInfoDialog] = useState(false)
  const [activeSubscriptionDetails, setActiveSubscriptionDetails] = useState<Subscription | null>(null)
  const [storedGiftPromocodes, setStoredGiftPromocodes] = useState<StoredGiftPromocode[]>(
    () => getStoredGiftPromocodes()
  )
  const [promocodeStatus, setPromocodeStatus] = useState<{
    kind: 'success' | 'info' | 'error'
    title: string
    message: string
  } | null>(null)
  const accessCapabilities = useMemo(
    () => resolveAccessCapabilities(accessStatus),
    [accessStatus]
  )
  const isReadOnlyAccess = accessCapabilities.isReadOnly
  const isPurchaseBlocked = accessCapabilities.isPurchaseBlocked
  const canMutateSubscriptions = accessCapabilities.canMutateProduct
  const canPurchaseSubscriptions = accessCapabilities.canPurchase
  const purchaseAccessNotice = isPurchaseBlocked
    ? t('subscription.purchaseBlockedNotice')
    : t('subscription.readOnlyNotice')

  const { data: subscriptions = [], isLoading } = useSubscriptionsQuery({ pollWhenVisible: true })

  useEffect(() => {
    const paymentStatus = searchParams.get('payment')
    if (!paymentStatus) {
      return
    }

    if (paymentStatus === 'success') {
      toast.success(t('subscription.paymentSuccess'))
      setShouldResolveSuccessDialog(true)
      void queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      void refreshUser()
      window.setTimeout(() => {
        void refreshUser()
      }, 2500)
    } else if (paymentStatus === 'failed') {
      toast.error(t('subscription.paymentFailed'))
    }

    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('payment')
    setSearchParams(nextParams, { replace: true })
  }, [queryClient, refreshUser, searchParams, setSearchParams, t])

  useEffect(() => {
    if (searchParams.get('payment')) {
      return
    }

    const rawPromocode = searchParams.get('promocode') || searchParams.get('broadcast_promocode')
    if (!rawPromocode) {
      return
    }

    const normalizedCode = rawPromocode.trim().toUpperCase()
    const shouldOpenDialog = searchParams.get('open_promocode') === '1'

    if (normalizedCode) {
      addStoredGiftPromocode(normalizedCode)
      setStoredGiftPromocodes(getStoredGiftPromocodes())
      setPromocodeInput(normalizedCode)
      setPromocodeStatus(null)
      if (shouldOpenDialog) {
        setPromocodeDialogOpen(true)
      }
    }

    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('promocode')
    nextParams.delete('broadcast_promocode')
    nextParams.delete('open_promocode')
    setSearchParams(nextParams, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    if (!shouldResolveSuccessDialog || isLoading) {
      return
    }

    const context = readPendingPurchaseContext()
    const target = resolveSubscriptionForConnect(subscriptions, context)
    setConnectTarget(target)
    setOpenPaymentSuccessDialog(true)
    clearPendingPurchaseContext()
    setShouldResolveSuccessDialog(false)
  }, [isLoading, shouldResolveSuccessDialog, subscriptions])

  const renewableSubscriptions = useMemo(
    () => subscriptions.filter((subscription) => canMultiRenewSubscription(subscription)),
    [subscriptions]
  )
  const selectablePromocodeSubscriptions = useMemo(() => {
    const availableIds = pendingPromocodeResult?.available_subscriptions
    if (!availableIds || availableIds.length === 0) {
      return subscriptions
    }

    const idSet = new Set(availableIds)
    return subscriptions.filter((subscription) => idSet.has(subscription.id))
  }, [pendingPromocodeResult?.available_subscriptions, subscriptions])

  useEffect(() => {
    setSelectedRenewIds((previous) => {
      const validIds = previous.filter((id) =>
        renewableSubscriptions.some((subscription) => subscription.id === id)
      )
      if (previous.length > 0 && validIds.length === 0) {
        setIsMultiRenewMode(false)
      }
      return validIds.length === previous.length ? previous : validIds
    })
  }, [renewableSubscriptions])

  const activeCount = subscriptions.filter((s) => s.status === 'ACTIVE').length
  const expiredCount = subscriptions.filter((s) => s.status === 'EXPIRED').length
  const effectiveMaxSubscriptions = user?.effective_max_subscriptions
  const activeVsAllowedLabel =
    effectiveMaxSubscriptions !== undefined
      ? `${activeCount} / ${effectiveMaxSubscriptions}`
      : `${activeCount} / -`

  const handleConnect = (subscription: Subscription) => {
    if (!openExternalLink(subscription.url)) {
      toast.error(t('common.openLinkFailed'))
    }
  }

  const handleCopySubscriptionLink = async (subscription: Subscription) => {
    try {
      await navigator.clipboard.writeText(subscription.url)
      toast.success(t('subscription.card.linkCopied'))
    } catch {
      toast.error(t('subscription.card.linkCopyFailed'))
    }
  }

  const triggerSelectionHaptic = () => {
    try {
      tg?.HapticFeedback?.selectionChanged()
    } catch {
      // Ignore Telegram haptic bridge failures.
    }
  }

  const handleMobileLongPressSelection = (id: number) => {
    if (!canPurchaseSubscriptions) {
      toast.error(purchaseAccessNotice)
      return
    }

    const targetSubscription = subscriptions.find((subscription) => subscription.id === id)
    if (!targetSubscription || !canMultiRenewSubscription(targetSubscription)) {
      return
    }

    if (!isMultiRenewMode) {
      setIsMultiRenewMode(true)
    }
    setSelectedRenewIds((previous) => {
      if (previous.includes(id)) {
        return previous
      }
      return [...previous, id]
    })
    triggerSelectionHaptic()
  }

  const handleMobileCardPress = (subscription: Subscription) => {
    if (isMultiRenewMode) {
      handleToggleRenewSelection(subscription.id)
      triggerSelectionHaptic()
      return
    }
    if (typeof window !== 'undefined') {
      window.requestAnimationFrame(() => {
        setActiveSubscriptionDetails(subscription)
      })
      return
    }
    setActiveSubscriptionDetails(subscription)
  }

  const toggleMultiRenewMode = () => {
    if (!canPurchaseSubscriptions) {
      toast.error(purchaseAccessNotice)
      return
    }
    if (isMultiRenewMode) {
      setIsMultiRenewMode(false)
      setSelectedRenewIds([])
      return
    }
    setIsMultiRenewMode(true)
  }

  const handleToggleRenewSelection = (id: number) => {
    if (!canPurchaseSubscriptions) {
      toast.error(purchaseAccessNotice)
      return
    }

    const targetSubscription = subscriptions.find((subscription) => subscription.id === id)
    if (!targetSubscription || !canMultiRenewSubscription(targetSubscription)) {
      return
    }

    setSelectedRenewIds((previous) => {
      if (previous.includes(id)) {
        const next = previous.filter((item) => item !== id)
        if (next.length === 0) {
          setIsMultiRenewMode(false)
        }
        return next
      }
      return [...previous, id]
    })
  }

  const handleRenewSelected = () => {
    if (!canPurchaseSubscriptions) {
      toast.error(purchaseAccessNotice)
      return
    }

    if (!selectedRenewIds.length) {
      toast.error(t('subscription.selectAtLeastOne'))
      return
    }

    const params = new URLSearchParams()
    selectedRenewIds.forEach((id) => {
      params.append('renew', String(id))
    })
    navigate(`/dashboard/subscription/purchase?${params.toString()}`)
  }

  const resetPromocodePendingState = () => {
    setPendingPromocode(null)
    setPendingPromocodeResult(null)
    setSelectedPromocodeSubscriptionId(null)
    setPromocodeConfirmDialogOpen(false)
  }

  const refreshStoredPromocodes = () => {
    setStoredGiftPromocodes(getStoredGiftPromocodes())
  }

  const getPromocodeRewardUnit = (rewardType: PromocodeRewardType): string => {
    switch (rewardType) {
      case 'DURATION':
        return t('promocodes.rewardUnit.days')
      case 'TRAFFIC':
        return t('promocodes.rewardUnit.gb')
      case 'DEVICES':
        return t('promocodes.rewardUnit.slots')
      case 'SUBSCRIPTION':
        return t('promocodes.rewardUnit.subscription')
      case 'PERSONAL_DISCOUNT':
      case 'PURCHASE_DISCOUNT':
        return t('promocodes.rewardUnit.discount')
      default:
        return t('promocodes.rewardUnit.rewards')
    }
  }

  const handlePromocodeResult = (result: PromocodeActivateResult, activationCode: string) => {
    if (result.next_step === 'SELECT_SUBSCRIPTION') {
      setPendingPromocode(activationCode)
      setPendingPromocodeResult(result)
      const defaultSubscriptionId = result.available_subscriptions?.[0] ?? null
      setSelectedPromocodeSubscriptionId(defaultSubscriptionId)
      setPromocodeConfirmDialogOpen(true)
      setPromocodeStatus({
        kind: 'info',
        title: t('promocodes.statusSelectSubscription'),
        message: result.message,
      })
      toast.info(result.message)
      return
    }

    if (result.next_step === 'CREATE_NEW') {
      setPendingPromocode(activationCode)
      setPendingPromocodeResult(result)
      setSelectedPromocodeSubscriptionId(null)
      setPromocodeConfirmDialogOpen(true)
      setPromocodeStatus({
        kind: 'info',
        title: t('promocodes.statusConfirmRequired'),
        message: result.message,
      })
      toast.info(result.message)
      return
    }

    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] }),
      queryClient.invalidateQueries({ queryKey: ['user-profile'] }),
      queryClient.invalidateQueries({ queryKey: ['referral-info'] }),
      queryClient.invalidateQueries({ queryKey: ['partner-info'] }),
      queryClient.invalidateQueries({ queryKey: ['promocode-activations'] }),
      queryClient.invalidateQueries({ queryKey: ['promocode-activations-preview'] }),
    ])
    void refreshUser()

    const rewardText = result.reward
      ? ` ${t('promocodes.rewardLabel')}: ${result.reward.value} ${getPromocodeRewardUnit(result.reward.type)}.`
      : ''
    setPromocodeStatus({
      kind: 'success',
      title: t('promocodes.statusActivated'),
      message: `${result.message}${rewardText}`,
    })
    toast.success(result.message)
    if (result.reward) {
      toast.info(`${t('promocodes.rewardLabel')}: ${result.reward.value} ${getPromocodeRewardUnit(result.reward.type)}`)
    }

    removeStoredGiftPromocode(activationCode)
    refreshStoredPromocodes()
    setPromocodeInput('')
    resetPromocodePendingState()
  }

  const activatePromocodeMutation = useMutation({
    mutationFn: (payload: { code: string; subscription_id?: number; create_new?: boolean }) =>
      api.promocode.activate(payload),
    onSuccess: (response, payload) => {
      handlePromocodeResult(response.data, payload.code)
    },
    onError: (error: unknown) => {
      const detail = extractErrorDetail(error) || t('promocodes.activationFailedFallback')
      setPromocodeStatus({
        kind: 'error',
        title: t('promocodes.statusActivationFailed'),
        message: detail,
      })
      toast.error(detail)
    },
  })

  const handlePromocodeActivate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canPurchaseSubscriptions) {
      toast.error(purchaseAccessNotice)
      return
    }
    const normalizedCode = promocodeInput.trim().toUpperCase()
    if (!normalizedCode) {
      toast.error(t('promocodes.enterPromocode'))
      return
    }

    setPromocodeStatus(null)
    setPromocodeInput(normalizedCode)
    activatePromocodeMutation.mutate({ code: normalizedCode })
  }

  const handlePromocodeConfirm = () => {
    if (!canPurchaseSubscriptions) {
      toast.error(purchaseAccessNotice)
      return
    }
    if (!pendingPromocode || !pendingPromocodeResult) {
      return
    }

    if (pendingPromocodeResult.next_step === 'SELECT_SUBSCRIPTION') {
      if (!selectedPromocodeSubscriptionId) {
        toast.error(t('promocodes.selectSubscriptionFirst'))
        return
      }

      activatePromocodeMutation.mutate({
        code: pendingPromocode,
        subscription_id: selectedPromocodeSubscriptionId,
      })
      return
    }

    if (pendingPromocodeResult.next_step === 'CREATE_NEW') {
      activatePromocodeMutation.mutate({
        code: pendingPromocode,
        create_new: true,
      })
      return
    }

    resetPromocodePendingState()
  }

  const handleStoredPromocodeActivate = (storedCode: string) => {
    if (!canPurchaseSubscriptions) {
      toast.error(purchaseAccessNotice)
      return
    }
    const normalizedCode = storedCode.trim().toUpperCase()
    if (!normalizedCode) {
      return
    }
    setPromocodeStatus(null)
    setPromocodeInput(normalizedCode)
    activatePromocodeMutation.mutate({ code: normalizedCode })
  }

  const handleStoredPromocodeCopy = async (storedCode: string) => {
    try {
      await navigator.clipboard.writeText(storedCode)
      toast.success(t('promocodes.promocodeCopied'))
    } catch {
      toast.error(t('promocodes.promocodeCopyFailed'))
    }
  }

  if (isLoading) {
    return <SubscriptionSkeleton />
  }

  return (
    <>
      <div className="space-y-6">
        {(isReadOnlyAccess || isPurchaseBlocked) && (
          <Card className="border-amber-300/25 bg-amber-500/10">
            <CardContent className="py-4">
              <p className="text-sm text-amber-100">{purchaseAccessNotice}</p>
            </CardContent>
          </Card>
        )}

        <div className={cn('flex justify-between gap-3', useMobileTelegramUiV2 ? 'items-start' : 'flex-wrap items-center')}>
          <div>
            <h1 className={cn('font-bold tracking-tight text-slate-100', useMobileTelegramUiV2 ? 'text-2xl' : 'text-3xl')}>
              {t('subscription.title')}
            </h1>
            <p className="text-sm text-slate-400">
              {t('subscription.subtitle')}
            </p>
          </div>

          {useMobileTelegramUiV2 ? (
            <div className="flex shrink-0 items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                className="h-11 w-11 border-white/15 bg-white/5 text-slate-100 hover:bg-white/10"
                aria-label={t('subscription.mobile.action.promocode')}
                onClick={() => {
                  refreshStoredPromocodes()
                  setPromocodeStatus(null)
                  setPromocodeDialogOpen(true)
                }}
                disabled={!canPurchaseSubscriptions}
              >
                <Ticket className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className={cn(
                  'h-11 w-11 border-white/15 text-slate-100 hover:bg-white/10',
                  isMultiRenewMode ? 'bg-primary/15' : 'bg-white/5'
                )}
                aria-label={t('subscription.mobile.action.multiRenew')}
                onClick={toggleMultiRenewMode}
                disabled={!canPurchaseSubscriptions || !renewableSubscriptions.length}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                className="h-11 w-11 bg-primary text-primary-foreground hover:bg-primary/90"
                aria-label={t('subscription.mobile.action.purchase')}
                onClick={() => navigate('/dashboard/subscription/purchase')}
                disabled={!canPurchaseSubscriptions}
              >
                <ShoppingCart className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className={cn(
              'flex gap-2',
              isMobileActions
                ? 'w-full flex-col'
                : 'w-full flex-col sm:w-auto sm:flex-row sm:flex-wrap sm:justify-end'
            )}>
              <Button
                variant="outline"
                className={cn(
                  'border-white/15 bg-white/5 text-slate-100 hover:bg-white/10',
                  isMobileActions ? 'w-full' : 'w-full sm:w-auto'
                )}
                onClick={() => {
                  refreshStoredPromocodes()
                  setPromocodeStatus(null)
                  setPromocodeDialogOpen(true)
                }}
                disabled={!canPurchaseSubscriptions}
              >
                {t('subscription.activatePromocode')}
              </Button>
              <Button
                variant="outline"
                className={cn(
                  'border-white/15 bg-white/5 text-slate-100 hover:bg-white/10',
                  isMobileActions ? 'w-full' : 'w-full sm:w-auto'
                )}
                onClick={toggleMultiRenewMode}
                disabled={!canPurchaseSubscriptions || !renewableSubscriptions.length}
              >
                {isMultiRenewMode ? t('subscription.cancelMultiRenew') : t('subscription.renewMultiple')}
              </Button>
              <Button
                className={cn(
                  'bg-primary text-primary-foreground hover:bg-primary/90',
                  isMobileActions ? 'w-full' : 'w-full sm:w-auto'
                )}
                onClick={() => navigate('/dashboard/subscription/purchase')}
                disabled={!canPurchaseSubscriptions}
              >
                {t('subscription.purchaseNew')}
              </Button>
            </div>
          )}
        </div>

        {isMultiRenewMode && (
          <Card className="border-primary/25 bg-primary/10">
            <CardContent className={cn('flex gap-3', useMobileTelegramUiV2 ? 'flex-col py-3' : 'flex-col py-4 sm:flex-row sm:items-center sm:justify-between')}>
              <p className="text-sm text-slate-100">
                {t('subscription.selectedForRenew', {
                  selected: selectedRenewIds.length,
                  total: renewableSubscriptions.length,
                })}
              </p>
              <div className={cn('flex gap-2', useMobileTelegramUiV2 ? 'w-full' : '')}>
                <Button
                  variant="outline"
                  className={cn(
                    'border-white/15 bg-white/5 text-slate-100 hover:bg-white/10',
                    useMobileTelegramUiV2 ? 'flex-1' : ''
                  )}
                  onClick={() => {
                    setSelectedRenewIds([])
                    setIsMultiRenewMode(false)
                  }}
                  disabled={!selectedRenewIds.length}
                >
                  {t('subscription.clearSelection')}
                </Button>
                <Button
                  className={cn(useMobileTelegramUiV2 ? 'flex-1' : '')}
                  onClick={handleRenewSelected}
                  disabled={!canPurchaseSubscriptions || !selectedRenewIds.length}
                >
                  {t('subscription.renewSelected')}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        <Card className="border-white/10 bg-card/90">
          <CardContent className={cn(useMobileTelegramUiV2 ? 'py-2.5' : 'space-y-2 py-3')}>
            {useMobileTelegramUiV2 ? (
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-slate-300">
                  {t('subscription.mobile.statsLabel')}
                </p>
                <Button
                  type="button"
                  size="icon"
                  variant="outline"
                  className="h-8 w-8 border-primary/40 bg-primary/15 text-primary shadow-[0_0_16px_-6px_rgba(183,198,211,0.7)] hover:bg-primary/25"
                  aria-label={t('subscription.mobile.openStatsInfo')}
                  onClick={() => setOpenStatsInfoDialog(true)}
                >
                  <Info className="h-3.5 w-3.5" />
                </Button>
              </div>
            ) : (
              <>
                <div className="grid gap-2 md:grid-cols-4">
                  <CompactStatItem
                    label={t('subscription.stats.subscriptions')}
                    value={activeVsAllowedLabel}
                    description={t('subscription.stats.activeLimit')}
                    className="border-white/15 bg-white/[0.03]"
                  />
                  <CompactStatItem
                    label={t('subscription.stats.total')}
                    value={subscriptions.length}
                    description={t('subscription.stats.all')}
                    className="border-white/12 bg-white/[0.02]"
                  />
                  <CompactStatItem
                    label={t('subscription.stats.active')}
                    value={activeCount}
                    description={t('subscription.stats.currentlyActive')}
                    className="border-emerald-400/20 bg-emerald-500/10"
                  />
                  <CompactStatItem
                    label={t('subscription.stats.expired')}
                    value={expiredCount}
                    description={t('subscription.stats.needRenewal')}
                    className="border-rose-400/20 bg-rose-500/10"
                  />
                </div>
                <p className="text-right text-[11px] text-slate-400">
                  {t('subscription.stats.caption')}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {subscriptions.length > 0 && (
          useMobileTelegramUiV2 ? (
            <div className="space-y-2">
              {subscriptions.map((sub) => {
                const actions = getSubscriptionCardActionState(
                  sub,
                  canPurchaseSubscriptions,
                  isMultiRenewMode
                )

                return (
                  <MobileSubscriptionCard
                    key={sub.id}
                    subscription={sub}
                    actions={actions}
                    multiRenewMode={isMultiRenewMode}
                    isSelectedForRenew={selectedRenewIds.includes(sub.id)}
                    onPress={handleMobileCardPress}
                    onLongPressSelect={handleMobileLongPressSelection}
                    onToggleRenewSelection={handleToggleRenewSelection}
                    onConnect={handleConnect}
                    onRenew={(id) => navigate(`/dashboard/subscription/${id}/renew`)}
                    onUpgrade={(id) => navigate(`/dashboard/subscription/${id}/upgrade`)}
                  />
                )
              })}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {subscriptions.map((sub) => {
                const actions = getSubscriptionCardActionState(
                  sub,
                  canPurchaseSubscriptions,
                  isMultiRenewMode
                )

                return (
                  <SubscriptionCard
                    key={sub.id}
                    subscription={sub}
                    actions={actions}
                    onRenew={(id) => navigate(`/dashboard/subscription/${id}/renew`)}
                    onUpgrade={(id) => navigate(`/dashboard/subscription/${id}/upgrade`)}
                    onManageDevices={(id) => navigate(`/dashboard/devices?subscription=${id}`)}
                    onConnect={handleConnect}
                    canDelete={canMutateSubscriptions}
                    multiRenewMode={isMultiRenewMode}
                    isSelectedForRenew={selectedRenewIds.includes(sub.id)}
                    onToggleRenewSelection={handleToggleRenewSelection}
                    onDelete={(id) => handleDelete(id)}
                  />
                )
              })}
            </div>
          )
        )}

        {subscriptions.length === 0 && (
          <Card className="border-white/10 bg-card/90">
            <CardContent className="pt-6">
              <div className="py-12 text-center">
                <p className="mb-4 text-sm text-slate-400">{t('subscription.empty')}</p>
                <Button
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                  onClick={() => navigate('/dashboard/subscription/purchase')}
                  disabled={!canPurchaseSubscriptions}
                >
                  {t('subscription.emptyCta')}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog
        open={openStatsInfoDialog}
        onOpenChange={setOpenStatsInfoDialog}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('subscription.mobile.statsInfoTitle')}</DialogTitle>
            <DialogDescription>
              {t('subscription.stats.caption')}
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-2">
            <CompactStatItem
              label={t('subscription.stats.subscriptions')}
              value={activeVsAllowedLabel}
              description={t('subscription.stats.activeLimit')}
              className="border-white/15 bg-white/[0.03]"
              compact
            />
            <CompactStatItem
              label={t('subscription.stats.total')}
              value={subscriptions.length}
              description={t('subscription.stats.all')}
              className="border-white/12 bg-white/[0.02]"
              compact
            />
            <CompactStatItem
              label={t('subscription.stats.active')}
              value={activeCount}
              description={t('subscription.stats.currentlyActive')}
              className="border-emerald-400/20 bg-emerald-500/10"
              compact
            />
            <CompactStatItem
              label={t('subscription.stats.expired')}
              value={expiredCount}
              description={t('subscription.stats.needRenewal')}
              className="border-rose-400/20 bg-rose-500/10"
              compact
            />
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => setOpenStatsInfoDialog(false)}>
              {t('common.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Sheet
        open={Boolean(activeSubscriptionDetails)}
        onOpenChange={(open) => {
          if (!open) {
            setActiveSubscriptionDetails(null)
          }
        }}
      >
        <SheetContent
          side="bottom"
          className="max-h-[calc(100vh-1rem)] overflow-y-auto overscroll-y-contain rounded-t-2xl rounded-b-none"
        >
          {activeSubscriptionDetails && (
            <MobileSubscriptionDetailsContent
              subscription={activeSubscriptionDetails}
              actions={getSubscriptionCardActionState(
                activeSubscriptionDetails,
                canPurchaseSubscriptions,
                false
              )}
              canDelete={canMutateSubscriptions}
              onConnect={handleConnect}
              onRenew={(id) => navigate(`/dashboard/subscription/${id}/renew`)}
              onUpgrade={(id) => navigate(`/dashboard/subscription/${id}/upgrade`)}
              onManageDevices={(id) => navigate(`/dashboard/devices?subscription=${id}`)}
              onCopyLink={handleCopySubscriptionLink}
              onDelete={handleDelete}
              onClose={() => setActiveSubscriptionDetails(null)}
            />
          )}
        </SheetContent>
      </Sheet>

      <Dialog
        open={openPaymentSuccessDialog}
        onOpenChange={(open) => {
          setOpenPaymentSuccessDialog(open)
          if (!open) {
            setConnectTarget(null)
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('subscription.dialog.paymentSuccessTitle')}</DialogTitle>
            <DialogDescription>
              {connectTarget
                ? t('subscription.dialog.paymentSuccessDescReady')
                : t('subscription.dialog.paymentSuccessDescMissing')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setOpenPaymentSuccessDialog(false)}>
              {t('common.close')}
            </Button>
            {connectTarget && (
              <Button onClick={() => handleConnect(connectTarget)}>
                <ExternalLink className="mr-1.5 h-4 w-4 shrink-0" />
                {t('subscription.connect')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={promocodeDialogOpen}
        onOpenChange={(open) => {
          setPromocodeDialogOpen(open)
          if (open) {
            refreshStoredPromocodes()
            return
          }
          setPromocodeInput('')
          setPromocodeStatus(null)
          resetPromocodePendingState()
        }}
      >
        <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('promocodes.activateTitle')}</DialogTitle>
            <DialogDescription>{t('promocodes.activateDesc')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <form onSubmit={handlePromocodeActivate} className="flex flex-col gap-2 sm:flex-row">
              <Input
                type="text"
                value={promocodeInput}
                onChange={(event) => setPromocodeInput(event.target.value)}
                placeholder={t('promocodes.activatePlaceholder')}
                className="flex-1 uppercase"
                disabled={activatePromocodeMutation.isPending}
              />
              <Button type="submit" disabled={activatePromocodeMutation.isPending}>
                <Ticket className="mr-1.5 h-4 w-4 shrink-0" />
                {activatePromocodeMutation.isPending ? t('promocodes.activating') : t('promocodes.activate')}
              </Button>
            </form>

            {promocodeStatus && (
              <div
                className={
                  promocodeStatus.kind === 'success'
                    ? 'rounded-lg border border-emerald-300/20 bg-emerald-500/10 p-3'
                    : promocodeStatus.kind === 'error'
                      ? 'rounded-lg border border-red-300/20 bg-red-500/10 p-3'
                      : 'rounded-lg border border-amber-300/20 bg-amber-500/10 p-3'
                }
              >
                <p className="text-sm font-semibold">{promocodeStatus.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{promocodeStatus.message}</p>
              </div>
            )}

            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="text-sm font-medium">{t('promocodes.availableGiftCodes')}</p>
                <Badge variant="secondary">{storedGiftPromocodes.length}</Badge>
              </div>

              {storedGiftPromocodes.length > 0 ? (
                <div className="space-y-2">
                  {storedGiftPromocodes.map((item) => (
                    <div key={item.code} className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-mono text-sm font-semibold tracking-wide">{item.code}</p>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            type="button"
                            onClick={() => handleStoredPromocodeCopy(item.code)}
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            type="button"
                            onClick={() => handleStoredPromocodeActivate(item.code)}
                            disabled={activatePromocodeMutation.isPending}
                          >
                            {t('promocodes.activateShort')}
                          </Button>
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {t('promocodes.savedAt', {
                          date: formatPromocodeSavedAt(item.createdAt, locale),
                        })}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-white/10 px-3 py-6 text-center text-sm text-muted-foreground">
                  {t('promocodes.noSavedGiftCodes')}
                </div>
              )}

              <p className="mt-3 text-xs text-muted-foreground">{t('promocodes.giftHint')}</p>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPromocodeDialogOpen(false)}>
              {t('common.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={promocodeConfirmDialogOpen}
        onOpenChange={(open) => {
          if (!open) {
            resetPromocodePendingState()
            return
          }
          setPromocodeConfirmDialogOpen(true)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pendingPromocodeResult?.next_step === 'SELECT_SUBSCRIPTION'
                ? t('promocodes.selectSubscriptionDialogTitle')
                : t('promocodes.createSubscriptionDialogTitle')}
            </DialogTitle>
            <DialogDescription>
              {pendingPromocodeResult?.next_step === 'SELECT_SUBSCRIPTION'
                ? t('promocodes.selectSubscriptionDialogDesc')
                : t('promocodes.createSubscriptionDialogDesc')}
            </DialogDescription>
          </DialogHeader>

          {pendingPromocodeResult?.next_step === 'SELECT_SUBSCRIPTION' && (
            <div className="py-2">
              {selectablePromocodeSubscriptions.length > 0 ? (
                <Select
                  value={selectedPromocodeSubscriptionId?.toString()}
                  onValueChange={(value) => setSelectedPromocodeSubscriptionId(Number(value))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('promocodes.selectSubscriptionPlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {selectablePromocodeSubscriptions.map((subscription) => (
                      <SelectItem key={subscription.id} value={subscription.id.toString()}>
                        {subscription.plan.name} - {subscription.status}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <p className="text-sm text-muted-foreground">{t('promocodes.noEligibleSubscriptions')}</p>
              )}
            </div>
          )}

          {pendingPromocodeResult?.next_step === 'CREATE_NEW' && (
            <div className="rounded-md border border-sky-300/20 bg-sky-500/12 p-3 py-4">
              <p className="text-sm">{t('promocodes.createSubscriptionInfo')}</p>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={resetPromocodePendingState}>
              {t('promocodes.cancel')}
            </Button>
            <Button type="button" onClick={handlePromocodeConfirm} disabled={activatePromocodeMutation.isPending}>
              {activatePromocodeMutation.isPending ? t('promocodes.processing') : t('promocodes.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )

  async function handleDelete(id: number) {
    if (!canMutateSubscriptions) {
      toast.error(t('subscription.readOnlyNotice'))
      return
    }

    try {
      await api.subscription.delete(id)
      toast.success(t('subscription.toast.deleted'))
      await queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
    } catch {
      toast.error(t('subscription.toast.deleteFailed'))
    }
  }
}

function formatPromocodeSavedAt(value: string, locale: 'ru' | 'en'): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString(locale === 'ru' ? 'ru-RU' : 'en-US')
}

function getSubscriptionStatusLabelKey(status: Subscription['status']): string {
  return `subscription.status.${status.toLowerCase()}`
}

interface MobileSubscriptionCardProps {
  subscription: Subscription
  actions: SubscriptionCardActionState
  multiRenewMode: boolean
  isSelectedForRenew: boolean
  onPress: (subscription: Subscription) => void
  onLongPressSelect: (id: number) => void
  onToggleRenewSelection: (id: number) => void
  onConnect: (subscription: Subscription) => void
  onRenew: (id: number) => void
  onUpgrade: (id: number) => void
}

function MobileSubscriptionCard({
  subscription,
  actions,
  multiRenewMode,
  isSelectedForRenew,
  onPress,
  onLongPressSelect,
  onToggleRenewSelection,
  onConnect,
  onRenew,
  onUpgrade,
}: MobileSubscriptionCardProps) {
  const { t } = useI18n()
  const pressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressTriggeredRef = useRef(false)
  const pressStartXRef = useRef(0)
  const pressStartYRef = useRef(0)
  const activePointerIdRef = useRef<number | null>(null)
  const pressMovedRef = useRef(false)
  const unlimitedLabel = t('subscription.card.unlimited')
  const trafficLimitBytes = gigabytesToBytes(subscription.traffic_limit)
  const trafficUnlimited = subscription.traffic_limit <= 0
  const trafficPercent = trafficUnlimited
    ? 0
    : Math.min((subscription.traffic_used / trafficLimitBytes) * 100, 100)
  const trafficValue = trafficUnlimited
    ? `${formatBytes(subscription.traffic_used)} / ${unlimitedLabel}`
    : `${formatBytes(subscription.traffic_used)} / ${formatBytes(trafficLimitBytes)}`
  const deviceSummary = getSubscriptionDeviceSummary(subscription, t)
  const { canRenew, canUpgrade, canMultiRenew, showUpgrade } = actions

  const clearPressTimer = () => {
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current)
      pressTimerRef.current = null
    }
  }

  const releasePointerCapture = (
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

  const resetPressTracking = () => {
    clearPressTimer()
    activePointerIdRef.current = null
    pressMovedRef.current = false
  }

  const handleActivate = () => {
    if (multiRenewMode) {
      onToggleRenewSelection(subscription.id)
      return
    }
    onPress(subscription)
  }

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'mouse' && event.button !== 0) {
      return
    }
    longPressTriggeredRef.current = false
    pressMovedRef.current = false
    pressStartXRef.current = event.clientX
    pressStartYRef.current = event.clientY
    activePointerIdRef.current = event.pointerId
    clearPressTimer()
    try {
      event.currentTarget.setPointerCapture(event.pointerId)
    } catch {
      // Ignore transient pointer capture errors.
    }
    if (multiRenewMode) {
      return
    }
    if (!canMultiRenew) {
      return
    }
    pressTimerRef.current = setTimeout(() => {
      if (pressMovedRef.current) {
        return
      }
      longPressTriggeredRef.current = true
      onLongPressSelect(subscription.id)
    }, MOBILE_LONG_PRESS_DURATION_MS)
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (activePointerIdRef.current !== event.pointerId) {
      return
    }

    const deltaX = Math.abs(event.clientX - pressStartXRef.current)
    const deltaY = Math.abs(event.clientY - pressStartYRef.current)
    if (deltaX <= MOBILE_LONG_PRESS_MOVE_CANCEL_PX && deltaY <= MOBILE_LONG_PRESS_MOVE_CANCEL_PX) {
      return
    }

    pressMovedRef.current = true
    clearPressTimer()
  }

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (activePointerIdRef.current !== event.pointerId) {
      return
    }
    releasePointerCapture(event.currentTarget, activePointerIdRef.current)
    const hasHandledLongPress = longPressTriggeredRef.current
    const hasMoved = pressMovedRef.current
    resetPressTracking()
    if (hasHandledLongPress) {
      return
    }
    if (hasMoved) {
      return
    }

    if (typeof window !== 'undefined') {
      window.requestAnimationFrame(() => {
        handleActivate()
      })
      return
    }
    handleActivate()
  }

  return (
    <Card
      className={cn(
        'border-white/10 bg-card/90 shadow-[0_14px_28px_-24px_rgba(3,7,18,0.8)]',
        isSelectedForRenew
          && 'border-[#18E8B7]/70 bg-[rgba(24,232,183,0.11)] shadow-[0_0_0_1px_rgba(24,232,183,0.45),0_0_24px_-10px_rgba(24,232,183,0.95)] motion-safe:animate-[subscription-selected-pulse_1.8s_ease-in-out_infinite]'
      )}
    >
      <div
        role="button"
        tabIndex={0}
        data-no-route-swipe
        aria-label={t('subscription.mobile.tapForDetails')}
        className="select-none rounded-xl p-3 outline-none [user-select:none] [-webkit-touch-callout:none] [-webkit-user-select:none] focus-visible:ring-2 focus-visible:ring-primary/70"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={(event) => {
          releasePointerCapture(event.currentTarget, activePointerIdRef.current)
          resetPressTracking()
        }}
        onContextMenu={(event) => event.preventDefault()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            handleActivate()
          }
        }}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-100">{subscription.plan.name}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-400">
              <span className="shrink-0">{deviceSummary.emoji}</span>
              <span className="truncate">
                {deviceSummary.label} / {deviceSummary.countLabel} / {deviceSummary.limitLabel}
              </span>
            </p>
          </div>
          <Badge variant="secondary" className="shrink-0 text-[10px] text-slate-100">
            {t(getSubscriptionStatusLabelKey(subscription.status))}
          </Badge>
        </div>

        <div className="mt-2.5 space-y-1.5">
          <div className="flex justify-between text-[11px] text-slate-300">
            <span>{t('subscription.card.traffic')}</span>
            <span>{trafficValue}</span>
          </div>
          {trafficUnlimited ? (
            <div className="h-1.5 rounded-full bg-emerald-400/25" />
          ) : (
            <Progress value={trafficPercent} className="h-1.5" />
          )}
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-300">
          <span>{t('subscription.card.expires')}: {formatDays(subscription.expire_at)}</span>
          {multiRenewMode && (
            <span className={cn(
              'rounded-full border px-2 py-0.5 text-[10px]',
              isSelectedForRenew
                ? 'border-[#18E8B7]/70 bg-[rgba(24,232,183,0.16)] text-[#d8fff6] shadow-[0_0_16px_-10px_rgba(24,232,183,0.9)]'
                : 'border-white/15 bg-white/[0.03] text-slate-300'
            )}>
              {isSelectedForRenew ? t('subscription.card.selected') : t('subscription.card.select')}
            </span>
          )}
        </div>

        <div className="mt-3 flex items-center gap-2">
          <Button
            type="button"
            variant="default"
            size="icon"
            className="h-11 w-11"
            aria-label={t('subscription.card.connect')}
            onPointerDown={(event) => event.stopPropagation()}
            onPointerUp={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation()
              onConnect(subscription)
            }}
          >
            <Link2 className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            disabled={!canRenew}
            className="h-11 w-11 border-white/15 bg-white/5 text-slate-100 hover:bg-white/10"
            aria-label={t('subscription.card.renew')}
            onPointerDown={(event) => event.stopPropagation()}
            onPointerUp={(event) => event.stopPropagation()}
            onClick={(event) => {
              event.stopPropagation()
              if (canRenew) {
                onRenew(subscription.id)
              }
            }}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          {showUpgrade && (
            <Button
              type="button"
              variant="outline"
              size="icon"
              disabled={!canUpgrade}
              className="h-11 w-11 border-white/15 bg-white/5 text-slate-100 hover:bg-white/10"
              aria-label={t('subscription.card.upgrade')}
              onPointerDown={(event) => event.stopPropagation()}
              onPointerUp={(event) => event.stopPropagation()}
              onClick={(event) => {
                event.stopPropagation()
                if (canUpgrade) {
                  onUpgrade(subscription.id)
                }
              }}
            >
              <ArrowUpCircle className="h-4 w-4" />
            </Button>
          )}

          <span className="ml-auto text-[10px] text-slate-400">
            {multiRenewMode ? t('subscription.mobile.selectHint') : t('subscription.mobile.tapForDetails')}
          </span>
          <span className="sr-only">{deviceSummary.label}</span>
        </div>
      </div>
    </Card>
  )
}

interface MobileSubscriptionDetailsContentProps {
  subscription: Subscription
  actions: SubscriptionCardActionState
  canDelete: boolean
  onConnect: (subscription: Subscription) => void
  onRenew: (id: number) => void
  onUpgrade: (id: number) => void
  onManageDevices: (id: number) => void
  onCopyLink: (subscription: Subscription) => Promise<void>
  onDelete: (id: number) => Promise<void>
  onClose: () => void
}

function MobileSubscriptionDetailsContent({
  subscription,
  actions,
  canDelete,
  onConnect,
  onRenew,
  onUpgrade,
  onManageDevices,
  onCopyLink,
  onDelete,
  onClose,
}: MobileSubscriptionDetailsContentProps) {
  const { t } = useI18n()
  const unlimitedLabel = t('subscription.card.unlimited')
  const planTypeLabel = formatPlanTypeLabel(subscription.plan.type, t)
  const deviceSummary = getSubscriptionDeviceSummary(subscription, t)
  const trafficLimitBytes = gigabytesToBytes(subscription.traffic_limit)
  const trafficUnlimited = subscription.traffic_limit <= 0
  const trafficPercent = trafficUnlimited
    ? 0
    : Math.min((subscription.traffic_used / trafficLimitBytes) * 100, 100)
  const trafficValue = trafficUnlimited
    ? `${formatBytes(subscription.traffic_used)} / ${unlimitedLabel}`
    : `${formatBytes(subscription.traffic_used)} / ${formatBytes(trafficLimitBytes)}`
  const planDuration =
    subscription.plan.duration <= 0
      ? t('subscription.card.lifetime')
      : t('subscription.card.durationDays', { days: subscription.plan.duration })
  const { showRenew, showUpgrade } = actions

  return (
    <>
      <SheetHeader>
        <SheetTitle>{subscription.plan.name}</SheetTitle>
        <SheetDescription>{t('subscription.mobile.detailsDescription')}</SheetDescription>
      </SheetHeader>

      <div className="space-y-3">
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="secondary" className="text-slate-100">
            {t(getSubscriptionStatusLabelKey(subscription.status))}
          </Badge>
          <span className="rounded-full border border-white/12 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-200">
            {t('subscription.card.type')}: {planTypeLabel}
          </span>
          <span className="rounded-full border border-white/12 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-200">
            {t('subscription.card.duration')}: {planDuration}
          </span>
          <span className="rounded-full border border-white/12 bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-200">
            {t('subscription.card.devices')}: {deviceSummary.countLabel} / {deviceSummary.limitLabel}
          </span>
        </div>

        <div className="space-y-1.5">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">{t('subscription.card.traffic')}</span>
            <span className="text-slate-200">{trafficValue}</span>
          </div>
          {trafficUnlimited ? (
            <div className="h-1.5 rounded-full bg-emerald-400/25" />
          ) : (
            <Progress value={trafficPercent} className="h-1.5" />
          )}
        </div>

        <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3 text-xs text-slate-300">
          <p>{t('subscription.card.expires')}: <span className="text-slate-100">{formatDays(subscription.expire_at)}</span></p>
          <p className="mt-1">
            {t('subscription.mobile.deviceType')}: <span className="text-slate-100">{deviceSummary.emoji} {deviceSummary.label}</span>
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-start">
        <Button
          variant="default"
          onClick={() => onConnect(subscription)}
        >
          <Link2 className="mr-1.5 h-4 w-4" />
          {t('subscription.card.connect')}
        </Button>
        {showRenew && (
          <Button
            variant="outline"
            className="border-white/15 bg-white/5 text-slate-100 hover:bg-white/10"
            onClick={() => onRenew(subscription.id)}
          >
            <RefreshCw className="mr-1.5 h-4 w-4" />
            {t('subscription.card.renew')}
          </Button>
        )}
        {showUpgrade && (
          <Button
            variant="outline"
            className="border-white/15 bg-white/5 text-slate-100 hover:bg-white/10"
            onClick={() => onUpgrade(subscription.id)}
          >
            <ArrowUpCircle className="mr-1.5 h-4 w-4" />
            {t('subscription.card.upgrade')}
          </Button>
        )}
        <Button variant="outline" onClick={() => onManageDevices(subscription.id)}>
          <Smartphone className="mr-1.5 h-4 w-4" />
          {t('subscription.card.manage')}
        </Button>
        <Button variant="outline" onClick={() => void onCopyLink(subscription)}>
          <Copy className="mr-1.5 h-4 w-4" />
          {t('subscription.card.copyLink')}
        </Button>
        {canDelete && (
          <Button
            variant="destructive"
            onClick={async () => {
              await onDelete(subscription.id)
              onClose()
            }}
          >
            <Trash2 className="mr-1.5 h-4 w-4" />
            {t('subscription.card.delete')}
          </Button>
        )}
      </div>
    </>
  )
}

interface SubscriptionCardProps {
  subscription: Subscription
  actions: SubscriptionCardActionState
  onRenew: (id: number) => void
  onUpgrade: (id: number) => void
  onManageDevices: (id: number) => void
  onConnect: (subscription: Subscription) => void
  canDelete: boolean
  multiRenewMode: boolean
  isSelectedForRenew: boolean
  onToggleRenewSelection: (id: number) => void
  onDelete: (id: number) => void
}

function SubscriptionCard({
  subscription,
  actions,
  onRenew,
  onUpgrade,
  onManageDevices,
  onConnect,
  canDelete,
  multiRenewMode,
  isSelectedForRenew,
  onToggleRenewSelection,
  onDelete,
}: SubscriptionCardProps) {
  const { t } = useI18n()
  const statusConfig = {
    ACTIVE: { labelKey: 'subscription.status.active', variant: 'default' as const, color: 'text-emerald-200' },
    EXPIRED: { labelKey: 'subscription.status.expired', variant: 'destructive' as const, color: 'text-red-200' },
    LIMITED: { labelKey: 'subscription.status.limited', variant: 'warning' as const, color: 'text-amber-200' },
    DISABLED: { labelKey: 'subscription.status.disabled', variant: 'secondary' as const, color: 'text-slate-300' },
    DELETED: { labelKey: 'subscription.status.deleted', variant: 'secondary' as const, color: 'text-slate-400' },
  }

  const config = statusConfig[subscription.status] || {
    labelKey: 'subscription.status.deleted',
    variant: 'secondary' as const,
    color: 'text-slate-300',
  }
  const unlimitedLabel = t('subscription.card.unlimited')
  const trafficLimitBytes = gigabytesToBytes(subscription.traffic_limit)
  const trafficUnlimited = subscription.traffic_limit <= 0
  const trafficPercent = trafficUnlimited
    ? 0
    : Math.min((subscription.traffic_used / trafficLimitBytes) * 100, 100)
  const trafficValue = trafficUnlimited
    ? `${formatBytes(subscription.traffic_used)} / ${unlimitedLabel}`
    : `${formatBytes(subscription.traffic_used)} / ${formatBytes(trafficLimitBytes)}`
  const devicesUnlimited = subscription.device_limit <= 0
  const devicesValue = devicesUnlimited
    ? `${subscription.devices_count} / ${unlimitedLabel}`
    : `${subscription.devices_count} / ${subscription.device_limit}`
  const deviceSummary = getSubscriptionDeviceSummary(subscription, t)
  const planTypeLabel = formatPlanTypeLabel(subscription.plan.type, t)
  const planDuration =
    subscription.plan.duration <= 0
      ? t('subscription.card.lifetime')
      : t('subscription.card.durationDays', { days: subscription.plan.duration })
  const trafficLimitLabel =
    subscription.traffic_limit <= 0 ? unlimitedLabel : formatBytes(trafficLimitBytes)
  const deviceLimitLabel =
    formatLimitLabel(subscription.device_limit, unlimitedLabel)
  const { canMultiRenew, showRenew, showUpgrade } = actions

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(subscription.url)
      toast.success(t('subscription.card.linkCopied'))
    } catch {
      toast.error(t('subscription.card.linkCopyFailed'))
    }
  }

  return (
    <Card className="relative border-white/10 bg-card/90 shadow-[0_16px_34px_-24px_rgba(3,7,18,0.8)]">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg leading-none text-slate-100">{subscription.plan.name}</CardTitle>
            <CardDescription className="mt-1 flex items-center gap-1.5 text-slate-400">
              <span className="shrink-0">{deviceSummary.emoji}</span>
              <span className="truncate">
                {deviceSummary.label} / {deviceSummary.countLabel} / {deviceSummary.limitLabel}
              </span>
            </CardDescription>
          </div>
          <Badge variant={config.variant} className={config.color}>
            {statusConfig[subscription.status] ? t(config.labelKey) : subscription.status}
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

        <div className="space-y-1.5">
          <div className="flex justify-between text-xs">
            <span className="text-slate-400">{t('subscription.card.traffic')}</span>
            <span className="text-slate-200">{trafficValue}</span>
          </div>
          {trafficUnlimited ? (
            <div className="h-1.5 rounded-full bg-emerald-400/25" />
          ) : (
            <Progress value={trafficPercent} className="h-1.5" />
          )}
        </div>

        <div className="grid gap-2 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-400">{t('subscription.card.devices')}</span>
            <div className="flex items-center gap-1">
              <Smartphone className="h-3.5 w-3.5 shrink-0" />
              <span className="text-slate-200">{devicesValue}</span>
            </div>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">{t('subscription.card.expires')}</span>
            <span className="font-medium text-slate-100">{formatDays(subscription.expire_at)}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <Button
            variant="outline"
            size="sm"
            className="h-8 inline-flex items-center gap-1.5 border-white/15 bg-white/5 px-2.5 text-slate-100 hover:bg-white/10"
            onClick={() => onManageDevices(subscription.id)}
          >
            <Smartphone className="h-4 w-4 shrink-0" />
            {t('subscription.card.manage')}
          </Button>

          {showRenew && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 inline-flex items-center gap-1.5 border-white/15 bg-white/5 px-2.5 text-slate-100 hover:bg-white/10"
              onClick={() => onRenew(subscription.id)}
            >
              <RefreshCw className="h-4 w-4 shrink-0" />
              {t('subscription.card.renew')}
            </Button>
          )}
          {showUpgrade && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 inline-flex items-center gap-1.5 border-white/15 bg-white/5 px-2.5 text-slate-100 hover:bg-white/10"
              onClick={() => onUpgrade(subscription.id)}
            >
              <ArrowUpCircle className="h-4 w-4 shrink-0" />
              {t('subscription.card.upgrade')}
            </Button>
          )}

          <Button
            variant="default"
            size="sm"
            className="h-8 inline-flex items-center gap-1.5 px-2.5"
            onClick={() => onConnect(subscription)}
          >
            <Link2 className="h-4 w-4 shrink-0" />
            {t('subscription.card.connect')}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="h-8 inline-flex items-center gap-1.5 px-2.5 text-slate-300 hover:bg-white/[0.07] hover:text-slate-100"
            onClick={handleCopyLink}
          >
            <Copy className="h-4 w-4 shrink-0" />
            {t('subscription.card.copyLink')}
          </Button>

          {multiRenewMode && (
            <Button
              variant="outline"
              size="sm"
              className={cn(
                'h-8 inline-flex items-center gap-1.5 border-white/15 px-2.5 text-slate-100',
                canMultiRenew
                  ? isSelectedForRenew
                    ? 'border-primary/35 bg-primary/15 hover:bg-primary/25'
                    : 'bg-white/5 hover:bg-white/10'
                  : 'cursor-not-allowed bg-white/5 text-slate-500'
              )}
              onClick={() => canMultiRenew && onToggleRenewSelection(subscription.id)}
              disabled={!canMultiRenew}
            >
              <Check className="h-4 w-4 shrink-0" />
              {isSelectedForRenew ? t('subscription.card.selected') : t('subscription.card.select')}
            </Button>
          )}

          {canDelete && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-auto h-8 w-8 text-slate-300 hover:bg-white/10 hover:text-slate-100"
                >
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="border-white/10 bg-card text-slate-100"
                align="end"
              >
                <DropdownMenuItem
                  onClick={() => onDelete(subscription.id)}
                  className="cursor-pointer text-destructive focus:bg-red-500/15 focus:text-red-200"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  {t('subscription.card.delete')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function CompactStatItem({ label, value, description, className, compact = false }: {
  label: string
  value: number | string
  description: string
  className?: string
  compact?: boolean
}) {
  return (
    <div className={cn('rounded-xl border', compact ? 'px-2.5 py-2' : 'px-3 py-2', className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className={cn('truncate font-medium text-slate-300', compact ? 'text-[11px]' : 'text-xs')}>{label}</p>
          <p className={cn('truncate text-slate-400', compact ? 'text-[10px]' : 'text-[11px]')}>{description}</p>
        </div>
        <div className={cn('font-semibold leading-none text-slate-100', compact ? 'text-xl' : 'text-2xl')}>{value}</div>
      </div>
    </div>
  )
}

function SubscriptionSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-10 w-32" />
          <Skeleton className="h-10 w-32" />
        </div>
      </div>
      <Card>
        <CardContent className="space-y-2 py-3">
          <div className="grid gap-2 md:grid-cols-4">
            {[1, 2, 3, 4].map((statId) => (
              <div key={`skeleton-stat-${statId}`} className="rounded-xl border border-white/10 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="space-y-1">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                  <Skeleton className="h-7 w-9" />
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-end">
            <Skeleton className="h-3 w-64" />
          </div>
        </CardContent>
      </Card>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {[1, 2, 3, 4].map((skeletonId) => (
          <Card key={`skeleton-${skeletonId}`}>
            <CardHeader className="pb-2">
              <div className="flex justify-between">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-5 w-16" />
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {[1, 2, 3].map((sectionId) => (
                <div key={sectionId} className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-1.5 w-full" />
                </div>
              ))}
              <div className="flex gap-2">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-20" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
