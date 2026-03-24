import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { resolveAccessCapabilities } from '@/lib/access-capabilities'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { useAccessStatusQuery } from '@/hooks/useAccessStatusQuery'
import { translateWithLocale, type TranslationParams } from '@/i18n/runtime'
import { useSubscriptionsQuery } from '@/hooks/useSubscriptionsQuery'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertTriangle,
  Apple,
  Check,
  Laptop,
  Loader2,
  Monitor,
  Smartphone,
  type LucideIcon,
} from 'lucide-react'
import { cn, formatBytes, gigabytesToBytes } from '@/lib/utils'
import { getCryptoAssetDisplayName, getCryptoAssetIconPath } from '@/lib/crypto-asset-icons'
import { getPaymentGatewayDisplayName, getPaymentGatewayIconPath } from '@/lib/payment-gateway-icons'
import { toast } from 'sonner'
import { openExternalLink } from '@/lib/openExternalLink'
import { buildExternalPaymentReturnUrl } from '@/lib/payment-return'
import { savePendingPurchaseContext } from '@/lib/purchase-context'
import type {
  CryptoAsset,
  DeviceType,
  PartnerInfo,
  Plan,
  PlanDuration,
  PlanPrice,
  PurchaseType,
  PurchaseQuoteResponse,
  PurchasePaymentSource,
  SubscriptionPurchaseOptionsResponse,
  TrialEligibilityResponse,
  User,
} from '@/types'

const WEB_CHANNEL = 'WEB' as const
const TELEGRAM_CHANNEL = 'TELEGRAM' as const
const EXTERNAL_PAYMENT_SOURCE: PurchasePaymentSource = 'EXTERNAL'
const PARTNER_BALANCE_PAYMENT_SOURCE: PurchasePaymentSource = 'PARTNER_BALANCE'

type PurchaseLocale = 'ru' | 'en'

function translatePurchase(locale: PurchaseLocale, key: string, params?: TranslationParams): string {
  return translateWithLocale(locale, key, params)
}

type PurchaseText = {
  lifetime: string
  daysSuffix: string
  noPricesAvailable: string
  fromLabel: string
  unlimited: string
  paymentCompleted: string
  paymentFailed: string
  selectPlanError: string
  selectDurationMethodError: string
  selectDeviceError: string
  paymentSuccess: string
  openCheckoutFailed: string
  noPlansTitle: string
  noPlansDesc: string
  titleRenew: string
  titleUpgrade: string
  titlePurchase: string
  subtitleRenew: string
  subtitleUpgrade: string
  subtitlePurchase: string
  selectPlanTitle: string
  selectPlanDescRenew: string
  selectPlanDescUpgrade: string
  selectPlanDescPurchase: string
  noDescription: string
  includes: string
  type: string
  traffic: string
  devices: string
  subscriptions: string
  tag: string
  orderSummary: string
  summaryPlan: string
  summaryDuration: string
  summaryDevice: string
  summaryDeviceNotRequired: string
  summaryPayment: string
  summarySource: string
  summaryPartnerBalance: string
  summaryExternal: string
  summaryOriginalPrice: string
  summaryDiscount: string
  summaryTotal: string
  selectionLocked: string
  archivedReplacementWarning: string
  upgradeWarning: string
  legacySourcePlanWarning: string
  processing: string
  proceedRenew: string
  proceedUpgrade: string
  proceedPayment: string
  openCheckout: string
  quantity: string
  totalSubscriptions: string
  cancel: string
  limitCheckTitle: string
  limitCheckDesc: string
  limitReached: string
  limitWouldExceed: string
  limitCurrentActive: string
  limitMaximum: string
  limitRemaining: string
  manageSubscriptions: string
  subscriptionsAfterPurchase: string
  limitCheckMayExceed: string
  limitCheckServerValidation: string
  selectDurationTitle: string
  selectDurationDesc: string
  bestValue: string
  unlimitedTerm: string
  selectDeviceTitle: string
  selectDeviceDesc: string
  paymentSourceTitle: string
  paymentSourceDesc: string
  externalGateway: string
  externalGatewayDesc: string
  partnerBalance: string
  partnerBalancePartnerInactive: string
  available: string
  selectPaymentMethodTitle: string
  selectPaymentMethodError: string
  selectPaymentMethodPartnerDesc: string
  selectPaymentMethodExternalDesc: string
  noRubGateway: string
  noWebGateway: string
  noTelegramGateway: string
  choosePaymentMethod: string
  choosePaymentAsset: string
  insufficientPartnerBalance: string
  partnerBalanceRubOnly: string
  partnerBalanceWebOnly: string
  partnerBalanceGatewayRequired: string
  createPaymentFailed: string
  archivedPlanNotPurchasable: string
  selectPaymentAssetTitle: string
  selectPaymentAssetDesc: string
  selectPaymentAssetError: string
  summaryPaymentAsset: string
  trialTitle: string
  trialDesc: string
  trialActivate: string
  trialActivating: string
  trialActivated: string
  trialRequiresTelegram: string
  trialLinkTelegram: string
  trialErrorDefault: string
  trialErrorAlreadyUsed: string
  trialErrorExistingSubscription: string
  trialErrorLinkRequired: string
  trialUnavailable: string
  trialErrorPlanNotConfigured: string
  trialErrorPlanInactive: string
  trialErrorNoDuration: string
  trialErrorNotTrialPlan: string
  trialErrorPlanNotFound: string
  trialUpgradeRequired: string
  trialDebugReasonCode: string
  quotePreparing: string
  quoteUnavailable: string
  readOnlyNotice: string
  purchaseBlockedNotice: string
}

const PURCHASE_TEXT_KEYS: Record<keyof PurchaseText, string> = {
  lifetime: 'purchase.lifetime',
  daysSuffix: 'purchase.daysSuffix',
  noPricesAvailable: 'purchase.noPricesAvailable',
  fromLabel: 'purchase.fromLabel',
  unlimited: 'purchase.unlimited',
  paymentCompleted: 'purchase.paymentCompleted',
  paymentFailed: 'purchase.paymentFailed',
  selectPlanError: 'purchase.selectPlanError',
  selectDurationMethodError: 'purchase.selectDurationMethodError',
  selectDeviceError: 'purchase.selectDeviceError',
  paymentSuccess: 'purchase.paymentSuccess',
  openCheckoutFailed: 'purchase.openCheckoutFailed',
  noPlansTitle: 'purchase.noPlansTitle',
  noPlansDesc: 'purchase.noPlansDesc',
  titleRenew: 'purchase.titleRenew',
  titleUpgrade: 'purchase.titleUpgrade',
  titlePurchase: 'purchase.titlePurchase',
  subtitleRenew: 'purchase.subtitleRenew',
  subtitleUpgrade: 'purchase.subtitleUpgrade',
  subtitlePurchase: 'purchase.subtitlePurchase',
  selectPlanTitle: 'purchase.selectPlanTitle',
  selectPlanDescRenew: 'purchase.selectPlanDescRenew',
  selectPlanDescUpgrade: 'purchase.selectPlanDescUpgrade',
  selectPlanDescPurchase: 'purchase.selectPlanDescPurchase',
  noDescription: 'purchase.noDescription',
  includes: 'purchase.includes',
  type: 'purchase.type',
  traffic: 'purchase.traffic',
  devices: 'purchase.devices',
  subscriptions: 'purchase.subscriptions',
  tag: 'purchase.tag',
  orderSummary: 'purchase.orderSummary',
  summaryPlan: 'purchase.summaryPlan',
  summaryDuration: 'purchase.summaryDuration',
  summaryDevice: 'purchase.summaryDevice',
  summaryDeviceNotRequired: 'purchase.summaryDeviceNotRequired',
  summaryPayment: 'purchase.summaryPayment',
  summarySource: 'purchase.summarySource',
  summaryPartnerBalance: 'purchase.summaryPartnerBalance',
  summaryExternal: 'purchase.summaryExternal',
  summaryOriginalPrice: 'purchase.summaryOriginalPrice',
  summaryDiscount: 'purchase.summaryDiscount',
  summaryTotal: 'purchase.summaryTotal',
  selectionLocked: 'purchase.selectionLocked',
  archivedReplacementWarning: 'purchase.archivedReplacementWarning',
  upgradeWarning: 'purchase.upgradeWarning',
  legacySourcePlanWarning: 'purchase.legacySourcePlanWarning',
  processing: 'purchase.processing',
  proceedRenew: 'purchase.proceedRenew',
  proceedUpgrade: 'purchase.proceedUpgrade',
  proceedPayment: 'purchase.proceedPayment',
  openCheckout: 'purchase.openCheckout',
  quantity: 'purchase.quantity',
  totalSubscriptions: 'purchase.totalSubscriptions',
  cancel: 'purchase.cancel',
  limitCheckTitle: 'purchase.limitCheckTitle',
  limitCheckDesc: 'purchase.limitCheckDesc',
  limitReached: 'purchase.limitReached',
  limitWouldExceed: 'purchase.limitWouldExceed',
  limitCurrentActive: 'purchase.limitCurrentActive',
  limitMaximum: 'purchase.limitMaximum',
  limitRemaining: 'purchase.limitRemaining',
  manageSubscriptions: 'purchase.manageSubscriptions',
  subscriptionsAfterPurchase: 'purchase.subscriptionsAfterPurchase',
  limitCheckMayExceed: 'purchase.limitCheckMayExceed',
  limitCheckServerValidation: 'purchase.limitCheckServerValidation',
  selectDurationTitle: 'purchase.selectDurationTitle',
  selectDurationDesc: 'purchase.selectDurationDesc',
  bestValue: 'purchase.bestValue',
  unlimitedTerm: 'purchase.unlimitedTerm',
  selectDeviceTitle: 'purchase.selectDeviceTitle',
  selectDeviceDesc: 'purchase.selectDeviceDesc',
  paymentSourceTitle: 'purchase.paymentSourceTitle',
  paymentSourceDesc: 'purchase.paymentSourceDesc',
  externalGateway: 'purchase.externalGateway',
  externalGatewayDesc: 'purchase.externalGatewayDesc',
  partnerBalance: 'purchase.partnerBalance',
  partnerBalancePartnerInactive: 'purchase.partnerBalancePartnerInactive',
  available: 'purchase.available',
  selectPaymentMethodTitle: 'purchase.selectPaymentMethodTitle',
  selectPaymentMethodError: 'purchase.selectPaymentMethodError',
  selectPaymentMethodPartnerDesc: 'purchase.selectPaymentMethodPartnerDesc',
  selectPaymentMethodExternalDesc: 'purchase.selectPaymentMethodExternalDesc',
  noRubGateway: 'purchase.noRubGateway',
  noWebGateway: 'purchase.noWebGateway',
  noTelegramGateway: 'purchase.noTelegramGateway',
  choosePaymentMethod: 'purchase.choosePaymentMethod',
  choosePaymentAsset: 'purchase.choosePaymentAsset',
  insufficientPartnerBalance: 'purchase.insufficientPartnerBalance',
  partnerBalanceRubOnly: 'purchase.partnerBalanceRubOnly',
  partnerBalanceWebOnly: 'purchase.partnerBalanceWebOnly',
  partnerBalanceGatewayRequired: 'purchase.partnerBalanceGatewayRequired',
  createPaymentFailed: 'purchase.createPaymentFailed',
  archivedPlanNotPurchasable: 'purchase.archivedPlanNotPurchasable',
  selectPaymentAssetTitle: 'purchase.selectPaymentAssetTitle',
  selectPaymentAssetDesc: 'purchase.selectPaymentAssetDesc',
  selectPaymentAssetError: 'purchase.selectPaymentAssetError',
  summaryPaymentAsset: 'purchase.summaryPaymentAsset',
  trialTitle: 'purchase.trialTitle',
  trialDesc: 'purchase.trialDesc',
  trialActivate: 'purchase.trialActivate',
  trialActivating: 'purchase.trialActivating',
  trialActivated: 'purchase.trialActivated',
  trialRequiresTelegram: 'purchase.trialRequiresTelegram',
  trialLinkTelegram: 'purchase.trialLinkTelegram',
  trialErrorDefault: 'purchase.trialErrorDefault',
  trialErrorAlreadyUsed: 'purchase.trialErrorAlreadyUsed',
  trialErrorExistingSubscription: 'purchase.trialErrorExistingSubscription',
  trialErrorLinkRequired: 'purchase.trialErrorLinkRequired',
  trialUnavailable: 'purchase.trialUnavailable',
  trialErrorPlanNotConfigured: 'purchase.trialErrorPlanNotConfigured',
  trialErrorPlanInactive: 'purchase.trialErrorPlanInactive',
  trialErrorNoDuration: 'purchase.trialErrorNoDuration',
  trialErrorNotTrialPlan: 'purchase.trialErrorNotTrialPlan',
  trialErrorPlanNotFound: 'purchase.trialErrorPlanNotFound',
  trialUpgradeRequired: 'purchase.trialUpgradeRequired',
  trialDebugReasonCode: 'purchase.trialDebugReasonCode',
  quotePreparing: 'purchase.quotePreparing',
  quoteUnavailable: 'purchase.quoteUnavailable',
  readOnlyNotice: 'purchase.readOnlyNotice',
  purchaseBlockedNotice: 'purchase.purchaseBlockedNotice',
}

type SubmitBlockReason =
  | 'LIMIT_REACHED'
  | 'LIMIT_WOULD_BE_EXCEEDED'
  | 'READ_ONLY_ACCESS'
  | 'PURCHASES_DISABLED'
  | 'MISSING_PLAN'
  | 'MISSING_DURATION'
  | 'MISSING_DEVICE'
  | 'MISSING_GATEWAY'
  | 'MISSING_PAYMENT_ASSET'
  | 'QUOTE_PENDING_OR_FAILED'

function buildPurchaseText(locale: PurchaseLocale): PurchaseText {
  return Object.fromEntries(
    Object.entries(PURCHASE_TEXT_KEYS).map(([field, key]) => [field, translatePurchase(locale, key)])
  ) as PurchaseText
}

function resolvePurchaseWarning(
  warningCode: string | null | undefined,
  text: PurchaseText
): string | null {
  if (!warningCode) {
    return null
  }

  if (warningCode === 'ARCHIVED_PLAN_REPLACEMENT') {
    return text.archivedReplacementWarning
  }
  if (warningCode === 'UPGRADE_RESETS_EXPIRY') {
    return text.upgradeWarning
  }
  if (warningCode === 'LEGACY_SOURCE_PLAN_UNAVAILABLE') {
    return text.legacySourcePlanWarning
  }

  return null
}

function formatDurationLabel(days: number, text: PurchaseText): string {
  return days <= 0 ? text.lifetime : `${days} ${text.daysSuffix}`
}

function sortDurations(durations: PlanDuration[]): PlanDuration[] {
  return [...durations].sort((left, right) => {
    const leftLifetime = left.days <= 0
    const rightLifetime = right.days <= 0
    if (leftLifetime && rightLifetime) {
      return left.id - right.id
    }
    if (leftLifetime) {
      return 1
    }
    if (rightLifetime) {
      return -1
    }
    return left.days - right.days
  })
}

function getPreferredDurationPrice(
  duration: PlanDuration,
  preferredCurrency: string | undefined
): PlanPrice | undefined {
  if (!duration.prices.length) {
    return undefined
  }

  return duration.prices.find((price) => price.currency === preferredCurrency) ?? duration.prices[0]
}

function getDurationPriceLabel(
  duration: PlanDuration,
  text: PurchaseText,
  preferredCurrency: string | undefined
): string {
  const preferredPrice = getPreferredDurationPrice(duration, preferredCurrency)
  if (!preferredPrice) {
    return text.noPricesAvailable
  }

  return `${text.fromLabel} ${formatPriceAmount(Number(preferredPrice.price))} ${preferredPrice.currency}`
}

function formatGatewayLabel(gateway: string | undefined): string {
  return getPaymentGatewayDisplayName(gateway)
}

function GatewayNameWithIcon({
  gatewayType,
  className,
  iconClassName = 'h-4 w-4',
}: {
  gatewayType: string | undefined
  className?: string
  iconClassName?: string
}) {
  const iconPath = getPaymentGatewayIconPath(gatewayType)
  const [failedIconPath, setFailedIconPath] = useState<string | null>(null)

  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      {iconPath && failedIconPath !== iconPath ? (
        <img
          src={iconPath}
          alt=""
          className={cn('shrink-0 object-contain', iconClassName)}
          onError={() => setFailedIconPath(iconPath)}
        />
      ) : null}
      <span>{formatGatewayLabel(gatewayType)}</span>
    </span>
  )
}

function CryptoAssetNameWithIcon({
  asset,
  className,
  iconClassName = 'h-4 w-4',
}: {
  asset: CryptoAsset | undefined
  className?: string
  iconClassName?: string
}) {
  const iconPath = getCryptoAssetIconPath(asset)
  const [failedIconPath, setFailedIconPath] = useState<string | null>(null)

  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      {iconPath && failedIconPath !== iconPath ? (
        <img
          src={iconPath}
          alt=""
          className={cn('shrink-0 object-contain', iconClassName)}
          onError={() => setFailedIconPath(iconPath)}
        />
      ) : null}
      <span>{getCryptoAssetDisplayName(asset)}</span>
    </span>
  )
}

function formatPriceAmount(value: number): string {
  if (!Number.isFinite(value)) {
    return '0'
  }

  const rounded = Math.round(value)
  if (Math.abs(value - rounded) < 0.000001) {
    return String(rounded)
  }

  return value.toFixed(2).replace(/\.?0+$/, '')
}

function hasActiveDiscount(
  price:
    | Pick<PlanPrice, 'discount_source' | 'discount_percent' | 'original_price' | 'price'>
    | Pick<PurchaseQuoteResponse, 'discount_source' | 'discount_percent' | 'original_price' | 'price'>
    | undefined
): boolean {
  if (!price) {
    return false
  }

  return (
    price.discount_source !== 'NONE'
    && price.discount_percent > 0
    && price.original_price > price.price
  )
}

function DiscountBadge({ percent }: { percent: number }) {
  return (
    <span className="inline-flex items-center rounded-full border border-emerald-300/30 bg-emerald-500/15 px-2.5 py-1 text-xs font-semibold text-emerald-200">
      -{percent}%
    </span>
  )
}

function formatPlanType(type: string): string {
  return type.charAt(0) + type.slice(1).toLowerCase()
}

function formatDeviceLimit(value: number, text: PurchaseText): string {
  return value <= 0 ? text.unlimited : String(value)
}

function formatTrafficLimit(value: number, text: PurchaseText): string {
  return value <= 0 ? text.unlimited : formatBytes(gigabytesToBytes(value))
}

type DeviceOption = {
  value: DeviceType
  label: string
  icon: LucideIcon
}

function getDeviceOptions(locale: PurchaseLocale): DeviceOption[] {
  return [
    {
      value: 'WINDOWS',
      label: translatePurchase(locale, 'purchase.device.windows.label'),
      icon: Monitor,
    },
    {
      value: 'MAC',
      label: translatePurchase(locale, 'purchase.device.mac.label'),
      icon: Laptop,
    },
    {
      value: 'IPHONE',
      label: translatePurchase(locale, 'purchase.device.iphone.label'),
      icon: Apple,
    },
    {
      value: 'ANDROID',
      label: translatePurchase(locale, 'purchase.device.android.label'),
      icon: Smartphone,
    },
  ]
}

export function PurchasePage() {
  const { user } = useAuth()
  const isMobileShell = useMobileTelegramUiV2()
  const { isInTelegram } = useTelegramWebApp()
  const { locale } = useI18n()
  const purchaseLocale: PurchaseLocale = locale === 'en' ? 'en' : 'ru'
  const purchaseChannel = isInTelegram ? TELEGRAM_CHANNEL : WEB_CHANNEL
  const paymentReturnTarget = isInTelegram ? 'telegram' : 'web'
  const successRedirectUrl = buildExternalPaymentReturnUrl('success', paymentReturnTarget)
  const failRedirectUrl = buildExternalPaymentReturnUrl('failed', paymentReturnTarget)
  const text = useMemo(() => buildPurchaseText(purchaseLocale), [purchaseLocale])
  const deviceOptions = useMemo(() => getDeviceOptions(purchaseLocale), [purchaseLocale])
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { data: accessStatus } = useAccessStatusQuery()
  const { id: subscriptionIdFromPath } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const isUpgradeFlow = location.pathname.endsWith('/upgrade')

  const renewIdsFromQuery = isUpgradeFlow
    ? []
    : searchParams
      .getAll('renew')
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value) && value > 0)
  const pathSubscriptionId = subscriptionIdFromPath ? Number(subscriptionIdFromPath) : null
  const renewId = isUpgradeFlow ? null : pathSubscriptionId
  const upgradeSubscriptionId = isUpgradeFlow ? pathSubscriptionId : null
  const renewTargets = Array.from(
    new Set([...(renewId ? [renewId] : []), ...renewIdsFromQuery])
  )
  const singleRenewId = renewTargets.length === 1 ? renewTargets[0] : null
  const singleSubscriptionTargetId = upgradeSubscriptionId ?? singleRenewId

  const [selectedPlan, setSelectedPlan] = useState<number | null>(null)
  const [selectedDuration, setSelectedDuration] = useState<number | null>(null)
  const [selectedGateway, setSelectedGateway] = useState<string | undefined>(undefined)
  const [selectedPaymentAsset, setSelectedPaymentAsset] = useState<CryptoAsset | undefined>(undefined)
  const [paymentSource, setPaymentSource] = useState<PurchasePaymentSource>(EXTERNAL_PAYMENT_SOURCE)
  const [selectedDeviceType, setSelectedDeviceType] = useState<DeviceType | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [isPurchasing, setIsPurchasing] = useState(false)
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false)
  const [selectedRenewIds] = useState<number[]>(renewTargets.length > 1 ? renewTargets : [])
  const purchaseLaunchRef = useRef(false)

  const isRenewFlow = !isUpgradeFlow && (renewTargets.length > 0 || selectedRenewIds.length > 0)
  const isNewPurchaseFlow = !isRenewFlow && !isUpgradeFlow
  const purchaseType: PurchaseType = isUpgradeFlow ? 'UPGRADE' : isRenewFlow ? 'RENEW' : 'NEW'
  const isSingleSubscriptionFlow = singleSubscriptionTargetId !== null
  const accessCapabilities = useMemo(
    () => resolveAccessCapabilities(accessStatus),
    [accessStatus]
  )
  const isReadOnlyAccess = accessCapabilities.isReadOnly
  const isPurchaseBlocked = accessCapabilities.isPurchaseBlocked
  const canPurchase = accessCapabilities.canPurchase

  const { data: catalogPlans = [], isLoading: isCatalogPlansLoading } = useQuery<Plan[]>({
    queryKey: ['plans', purchaseChannel],
    queryFn: () => api.plans.list(purchaseChannel).then((response) => response.data),
    enabled: !isSingleSubscriptionFlow,
  })
  const { data: singlePurchaseOptions, isLoading: isPurchaseOptionsLoading } = useQuery<SubscriptionPurchaseOptionsResponse>({
    queryKey: ['subscription-purchase-options', singleSubscriptionTargetId, purchaseType, purchaseChannel],
    queryFn: () =>
      api.subscription
        .purchaseOptions(
          singleSubscriptionTargetId as number,
          isUpgradeFlow ? 'UPGRADE' : 'RENEW',
          purchaseChannel
        )
        .then((response) => response.data),
    enabled: isSingleSubscriptionFlow,
  })

  const { data: subscriptions = [] } = useSubscriptionsQuery()
  const { data: userProfile } = useQuery<User>({
    queryKey: ['user-profile'],
    queryFn: () => api.user.me().then((response) => response.data),
    enabled: Boolean(user),
  })
  const { data: trialEligibility } = useQuery<TrialEligibilityResponse>({
    queryKey: ['trial-eligibility'],
    queryFn: () => api.subscription.trialEligibility().then((response) => response.data),
    enabled: isNewPurchaseFlow,
    retry: false,
  })
  const activateTrialMutation = useMutation({
    mutationFn: () => api.subscription.trial(),
    onSuccess: async () => {
      toast.success(text.trialActivated)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['subscriptions'] }),
        queryClient.invalidateQueries({ queryKey: ['user-profile'] }),
        queryClient.invalidateQueries({ queryKey: ['trial-eligibility'] }),
      ])
      navigate('/dashboard/subscription')
    },
    onError: (error: unknown) => {
      toast.error(extractTrialError(error, text))
    },
  })

  const { data: partnerInfo } = useQuery<PartnerInfo>({
    queryKey: ['partner-info'],
    queryFn: () => api.partner.info().then((response) => response.data),
    enabled: Boolean((userProfile ?? user)?.is_partner || (userProfile ?? user)?.is_partner_active),
  })

  const renewSubscriptions = useMemo(
    () => subscriptions.filter((subscription) => renewTargets.includes(subscription.id)),
    [renewTargets, subscriptions]
  )
  const sourceSubscription = useMemo(
    () =>
      singleSubscriptionTargetId !== null
        ? subscriptions.find((subscription) => subscription.id === singleSubscriptionTargetId) ?? null
        : null,
    [singleSubscriptionTargetId, subscriptions]
  )
  const availablePlans = useMemo(
    () => (isSingleSubscriptionFlow ? (singlePurchaseOptions?.plans ?? []) : catalogPlans),
    [catalogPlans, isSingleSubscriptionFlow, singlePurchaseOptions?.plans]
  )
  const isLoading = isSingleSubscriptionFlow ? isPurchaseOptionsLoading : isCatalogPlansLoading
  const defaultFlowPlanId =
    (isSingleSubscriptionFlow ? availablePlans[0]?.id : renewSubscriptions[0]?.plan?.id) ?? null
  const effectivePlanId = useMemo(() => {
    if (selectedPlan !== null && availablePlans.some((plan) => plan.id === selectedPlan)) {
      return selectedPlan
    }
    if (isNewPurchaseFlow) {
      return null
    }
    if (defaultFlowPlanId && availablePlans.some((plan) => plan.id === defaultFlowPlanId)) {
      return defaultFlowPlanId
    }
    if (availablePlans.length === 1) {
      return availablePlans[0].id
    }
    return null
  }, [availablePlans, defaultFlowPlanId, isNewPurchaseFlow, selectedPlan])
  const selectedPlanData = useMemo(
    () => availablePlans.find((plan) => plan.id === effectivePlanId),
    [availablePlans, effectivePlanId]
  )
  const sortedDurations = useMemo(
    () => (selectedPlanData ? sortDurations(selectedPlanData.durations) : []),
    [selectedPlanData]
  )
  const defaultDurationDays = useMemo(() => {
    if (isNewPurchaseFlow || !selectedPlanData) {
      return null
    }
    const sourceDuration = sourceSubscription?.plan?.duration ?? renewSubscriptions[0]?.plan?.duration
    const matchingDuration = selectedPlanData.durations.find(
      (duration) => duration.days === sourceDuration
    )
    return matchingDuration?.days ?? sortedDurations[0]?.days ?? null
  }, [
    isNewPurchaseFlow,
    renewSubscriptions,
    selectedPlanData,
    sortedDurations,
    sourceSubscription?.plan?.duration,
  ])
  const effectiveSelectedDuration = useMemo(() => {
    if (selectedDuration !== null && sortedDurations.some((duration) => duration.days === selectedDuration)) {
      return selectedDuration
    }
    return defaultDurationDays
  }, [defaultDurationDays, selectedDuration, sortedDurations])
  const selectedDurationData = useMemo(
    () => selectedPlanData?.durations.find((duration) => duration.days === effectiveSelectedDuration),
    [effectiveSelectedDuration, selectedPlanData]
  )
  const availableGatewayPrices = useMemo(
    () =>
      (selectedDurationData?.prices || []).filter(
        (price) => paymentSource !== PARTNER_BALANCE_PAYMENT_SOURCE || price.currency === 'RUB'
      ),
    [paymentSource, selectedDurationData]
  )
  const effectiveSelectedGateway = useMemo(() => {
    if (!selectedDurationData) {
      return undefined
    }
    if (
      selectedGateway
      && availableGatewayPrices.some((price) => price.gateway_type === selectedGateway)
    ) {
      return selectedGateway
    }
    if (availableGatewayPrices.length === 1) {
      return availableGatewayPrices[0].gateway_type
    }
    return undefined
  }, [availableGatewayPrices, selectedDurationData, selectedGateway])
  const selectedPrice = useMemo(
    () => availableGatewayPrices.find((price) => price.gateway_type === effectiveSelectedGateway),
    [availableGatewayPrices, effectiveSelectedGateway]
  )
  const availablePaymentAssets = useMemo(
    () => selectedPrice?.supported_payment_assets ?? [],
    [selectedPrice]
  )
  const effectiveSelectedPaymentAsset = useMemo(() => {
    if (!effectiveSelectedGateway || !availablePaymentAssets.length) {
      return undefined
    }
    if (
      selectedPaymentAsset
      && availablePaymentAssets.includes(selectedPaymentAsset)
    ) {
      return selectedPaymentAsset
    }
    if (availablePaymentAssets.length === 1) {
      return availablePaymentAssets[0]
    }
    return undefined
  }, [availablePaymentAssets, effectiveSelectedGateway, selectedPaymentAsset])

  useEffect(() => {
    const paymentStatus = searchParams.get('payment')
    if (!paymentStatus) {
      return
    }

    if (paymentStatus === 'success') {
      toast.success(text.paymentCompleted)
      void queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
    } else if (paymentStatus === 'failed') {
      toast.error(text.paymentFailed)
    }

    const nextParams = new URLSearchParams(searchParams)
    nextParams.delete('payment')
    const nextSearch = nextParams.toString()

    navigate(
      {
        pathname: location.pathname,
        search: nextSearch ? `?${nextSearch}` : '',
      },
      { replace: true }
    )
  }, [location.pathname, navigate, queryClient, searchParams, text.paymentCompleted, text.paymentFailed])
  const normalizedQuantity = Number.isFinite(quantity) ? Math.max(1, Math.floor(quantity)) : 1
  const currentUser = userProfile ?? user
  const derivedActiveSubscriptionsCount = subscriptions.filter(
    (subscription) => subscription.status !== 'DELETED'
  ).length
  const activeSubscriptionsCount =
    currentUser?.active_subscriptions_count ?? derivedActiveSubscriptionsCount
  const trialReasonCode = trialEligibility?.reason_code ?? null
  const showTrialDebugReasonCode = currentUser?.role === 'DEV' && Boolean(trialReasonCode)
  const hideTrialCardReasonCodes = new Set([
    'TRIAL_ALREADY_USED',
    'TRIAL_NOT_FIRST_SUBSCRIPTION',
    'TRIAL_PLAN_NOT_CONFIGURED',
    'TRIAL_PLAN_NOT_FOUND',
    'TRIAL_PLAN_INACTIVE',
    'TRIAL_PLAN_NO_DURATION',
    'TRIAL_PLAN_NOT_TRIAL',
  ])
  const hideTrialCardForReason =
    Boolean(trialReasonCode && hideTrialCardReasonCodes.has(trialReasonCode))
  const hasConfiguredTrialPlan = trialEligibility?.trial_plan_id != null
  const canShowTrialCard =
    isNewPurchaseFlow
    && Boolean(trialEligibility)
    && hasConfiguredTrialPlan
    && !hideTrialCardForReason
  const canActivateTrial = Boolean(trialEligibility?.eligible) && canPurchase
  const shouldShowTrialLinkAction =
    Boolean(trialEligibility?.requires_telegram_link) ||
    trialReasonCode === 'TRIAL_TELEGRAM_LINK_REQUIRED'
  const trialEligibilityMessage = resolveTrialEligibilityMessage(trialEligibility, text)
  const effectiveMaxSubscriptions = currentUser?.effective_max_subscriptions ?? null
  const remainingSlots =
    effectiveMaxSubscriptions === null
      ? null
      : Math.max(0, effectiveMaxSubscriptions - activeSubscriptionsCount)
  const maxPurchasableQuantity =
    isNewPurchaseFlow && remainingSlots !== null ? remainingSlots : null
  const purchaseBlockedByLimit =
    isNewPurchaseFlow && maxPurchasableQuantity !== null && maxPurchasableQuantity <= 0
  const showQuantitySelector =
    isNewPurchaseFlow && maxPurchasableQuantity !== null && maxPurchasableQuantity > 1
  const effectiveSubscriptionCount = isNewPurchaseFlow
    ? normalizedQuantity
    : Math.max(renewTargets.length, 1)
  const priceMultiplier = isNewPurchaseFlow ? normalizedQuantity : 1
  const requiresPaymentAsset = availablePaymentAssets.length > 1
  const exceedsPredictedLimit =
    isNewPurchaseFlow
    && effectiveMaxSubscriptions !== null
    && activeSubscriptionsCount + effectiveSubscriptionCount > effectiveMaxSubscriptions
  const noGatewayAvailable =
    Boolean(selectedDurationData) && availableGatewayPrices.length === 0
  const canUsePartnerBalance =
    purchaseChannel === WEB_CHANNEL
    && Boolean(currentUser?.is_partner_active || partnerInfo?.is_active)
  const partnerBalanceRub = partnerInfo ? partnerInfo.balance / 100 : 0
  const partnerBalanceDisplay = partnerInfo?.balance_display ?? partnerBalanceRub
  const partnerBalanceCurrency = partnerInfo?.effective_currency ?? 'RUB'
  const noGatewayMessage = purchaseChannel === TELEGRAM_CHANNEL
    ? text.noTelegramGateway
    : paymentSource === PARTNER_BALANCE_PAYMENT_SOURCE
      ? text.noRubGateway
      : text.noWebGateway
  const purchaseQuoteEnabled = Boolean(
    effectivePlanId !== null
      && effectiveSelectedDuration !== null
      && effectiveSelectedGateway
      && canPurchase
      && !purchaseBlockedByLimit
      && !exceedsPredictedLimit
      && (!requiresPaymentAsset || effectiveSelectedPaymentAsset)
  )
  const {
    data: selectedQuote,
    isFetching: isQuoteFetching,
    error: quoteError,
  } = useQuery<PurchaseQuoteResponse>({
    queryKey: [
      'subscription-quote',
      purchaseChannel,
      paymentSource,
      effectivePlanId,
      effectiveSelectedDuration,
      effectiveSelectedGateway,
      effectiveSelectedPaymentAsset,
      normalizedQuantity,
      selectedDeviceType,
      singleRenewId,
      upgradeSubscriptionId,
      selectedRenewIds,
      purchaseType,
    ],
    queryFn: () =>
      api.subscription.quote({
        purchase_type: purchaseType,
        channel: purchaseChannel,
        payment_source: paymentSource,
        plan_id: effectivePlanId ?? undefined,
        duration_days: effectiveSelectedDuration ?? undefined,
        gateway_type: effectiveSelectedGateway,
        payment_asset: effectiveSelectedPaymentAsset,
        quantity: isNewPurchaseFlow ? normalizedQuantity : undefined,
        device_type: isNewPurchaseFlow ? selectedDeviceType || undefined : undefined,
        device_types:
          isNewPurchaseFlow && selectedDeviceType
            ? Array.from({ length: normalizedQuantity }, () => selectedDeviceType)
            : undefined,
        renew_subscription_id:
          purchaseType === 'NEW'
            ? undefined
            : upgradeSubscriptionId || singleRenewId || undefined,
        renew_subscription_ids:
          purchaseType === 'RENEW' && selectedRenewIds.length > 1 ? selectedRenewIds : undefined,
      }).then((response) => response.data),
    enabled: purchaseQuoteEnabled,
    retry: false,
  })
  const quoteErrorMessage = quoteError
    ? extractPurchaseError(quoteError, text)
    : text.quoteUnavailable
  const submitBlockReason: SubmitBlockReason | null = useMemo(() => {
    if (isPurchasing) {
      return null
    }
    if (isReadOnlyAccess) {
      return 'READ_ONLY_ACCESS'
    }
    if (isPurchaseBlocked) {
      return 'PURCHASES_DISABLED'
    }
    if (purchaseBlockedByLimit) {
      return 'LIMIT_REACHED'
    }
    if (exceedsPredictedLimit) {
      return 'LIMIT_WOULD_BE_EXCEEDED'
    }
    if (effectivePlanId === null) {
      return 'MISSING_PLAN'
    }
    if (effectiveSelectedDuration === null) {
      return 'MISSING_DURATION'
    }
    if (isNewPurchaseFlow && !selectedDeviceType) {
      return 'MISSING_DEVICE'
    }
    if (noGatewayAvailable || !effectiveSelectedGateway) {
      return 'MISSING_GATEWAY'
    }
    if (requiresPaymentAsset && !effectiveSelectedPaymentAsset) {
      return 'MISSING_PAYMENT_ASSET'
    }
    if (purchaseQuoteEnabled && (isQuoteFetching || !selectedQuote)) {
      return 'QUOTE_PENDING_OR_FAILED'
    }
    return null
  }, [
    effectivePlanId,
    exceedsPredictedLimit,
    isNewPurchaseFlow,
    isPurchasing,
    isQuoteFetching,
    isPurchaseBlocked,
    isReadOnlyAccess,
    noGatewayAvailable,
    purchaseBlockedByLimit,
    purchaseQuoteEnabled,
    requiresPaymentAsset,
    selectedDeviceType,
    effectiveSelectedDuration,
    effectiveSelectedGateway,
    effectiveSelectedPaymentAsset,
    selectedQuote,
  ])
  const submitBlockMessage = useMemo(() => {
    if (!submitBlockReason) {
      return null
    }

    switch (submitBlockReason) {
      case 'LIMIT_REACHED':
        return text.limitReached
      case 'LIMIT_WOULD_BE_EXCEEDED':
        return text.limitWouldExceed
      case 'READ_ONLY_ACCESS':
        return text.readOnlyNotice
      case 'PURCHASES_DISABLED':
        return text.purchaseBlockedNotice
      case 'MISSING_PLAN':
        return text.selectPlanError
      case 'MISSING_DURATION':
        return text.selectDurationMethodError
      case 'MISSING_DEVICE':
        return text.selectDeviceError
      case 'MISSING_GATEWAY':
        return noGatewayAvailable ? noGatewayMessage : text.selectPaymentMethodError
      case 'MISSING_PAYMENT_ASSET':
        return text.selectPaymentAssetError
      case 'QUOTE_PENDING_OR_FAILED':
        return isQuoteFetching ? text.quotePreparing : quoteErrorMessage
      default:
        return null
    }
  }, [
    isQuoteFetching,
    noGatewayAvailable,
    noGatewayMessage,
    quoteErrorMessage,
    submitBlockReason,
    text.limitReached,
    text.limitWouldExceed,
    text.purchaseBlockedNotice,
    text.readOnlyNotice,
    text.selectPlanError,
    text.selectDurationMethodError,
    text.selectDeviceError,
    text.selectPaymentMethodError,
    text.selectPaymentAssetError,
    text.quotePreparing,
  ])
  const showLimitWarning = submitBlockReason === 'LIMIT_REACHED' || submitBlockReason === 'LIMIT_WOULD_BE_EXCEEDED'
  const canOpenCheckout = Boolean(
    effectivePlanId !== null &&
      effectiveSelectedDuration !== null &&
      canPurchase &&
      !purchaseBlockedByLimit &&
      !exceedsPredictedLimit &&
      (!isNewPurchaseFlow || selectedDeviceType)
  )
  const canSubmit = submitBlockReason === null
  const purchaseWarningMessage =
    resolvePurchaseWarning(singlePurchaseOptions?.warning_code, text)
    ?? singlePurchaseOptions?.warning_message
    ?? null
  const isPlanSelectionLocked = Boolean(singlePurchaseOptions?.selection_locked)
  const pageTitle = isUpgradeFlow
    ? text.titleUpgrade
    : isRenewFlow
      ? text.titleRenew
      : text.titlePurchase
  const pageSubtitle = isUpgradeFlow
    ? text.subtitleUpgrade
    : isRenewFlow
      ? text.subtitleRenew
      : text.subtitlePurchase
  const selectPlanDescription = isUpgradeFlow
    ? text.selectPlanDescUpgrade
    : isRenewFlow
      ? text.selectPlanDescRenew
      : text.selectPlanDescPurchase
  const trialCard = canShowTrialCard ? (
    <Card className="border-sky-300/25 bg-sky-500/10">
      <CardHeader>
        <CardTitle>{text.trialTitle}</CardTitle>
        <CardDescription>{canActivateTrial ? text.trialDesc : text.trialUnavailable}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <p className="text-sm text-sky-100">
            {canActivateTrial ? text.trialDesc : trialEligibilityMessage}
          </p>
          {showTrialDebugReasonCode && (
            <p className="inline-flex items-center rounded-md border border-sky-300/25 bg-sky-950/30 px-2 py-1 font-mono text-xs text-sky-200">
              {text.trialDebugReasonCode}: {trialReasonCode}
            </p>
          )}
        </div>
        {canActivateTrial ? (
          <Button
            onClick={() => activateTrialMutation.mutate()}
            disabled={activateTrialMutation.isPending}
          >
            {activateTrialMutation.isPending ? text.trialActivating : text.trialActivate}
          </Button>
        ) : shouldShowTrialLinkAction ? (
          <Button variant="outline" onClick={() => navigate('/dashboard/settings?focus=telegram')}>
            {text.trialLinkTelegram}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  ) : null

  useEffect(() => {
    if (!isNewPurchaseFlow) {
      if (quantity !== 1) {
        setQuantity(1)
      }
      return
    }

    if (maxPurchasableQuantity === null) {
      return
    }

    const clampedQuantity =
      maxPurchasableQuantity <= 0 ? 1 : Math.min(normalizedQuantity, maxPurchasableQuantity)
    if (clampedQuantity !== quantity) {
      setQuantity(clampedQuantity)
    }
  }, [isNewPurchaseFlow, maxPurchasableQuantity, normalizedQuantity, quantity])

  useEffect(() => {
    if (purchaseChannel !== TELEGRAM_CHANNEL && (paymentSource !== PARTNER_BALANCE_PAYMENT_SOURCE || canUsePartnerBalance)) {
      return
    }

    setPaymentSource(EXTERNAL_PAYMENT_SOURCE)
    setSelectedGateway(undefined)
    setSelectedPaymentAsset(undefined)
  }, [canUsePartnerBalance, paymentSource, purchaseChannel])

  const handlePurchase = async () => {
    if (purchaseLaunchRef.current || isPurchasing) {
      return
    }
    if (isReadOnlyAccess) {
      toast.error(text.readOnlyNotice)
      return
    }
    if (isPurchaseBlocked) {
      toast.error(text.purchaseBlockedNotice)
      return
    }

    if (purchaseBlockedByLimit || exceedsPredictedLimit) {
      toast.error(text.limitReached)
      return
    }

    if (effectivePlanId === null) {
      toast.error(text.selectPlanError)
      return
    }

    if (effectiveSelectedDuration === null || !effectiveSelectedGateway) {
      toast.error(text.selectDurationMethodError)
      return
    }

    if (isNewPurchaseFlow && !selectedDeviceType) {
      toast.error(text.selectDeviceError)
      return
    }

    if (requiresPaymentAsset && !effectiveSelectedPaymentAsset) {
      toast.error(text.selectPaymentAssetError)
      return
    }

    if (paymentSource === PARTNER_BALANCE_PAYMENT_SOURCE && !canUsePartnerBalance) {
      setPaymentSource(EXTERNAL_PAYMENT_SOURCE)
      setSelectedGateway(undefined)
      toast.error(text.partnerBalancePartnerInactive)
      return
    }

    purchaseLaunchRef.current = true
    setIsPurchasing(true)
    try {
      const deviceTypes =
        isNewPurchaseFlow && selectedDeviceType
          ? Array.from({ length: normalizedQuantity }, () => selectedDeviceType)
          : undefined
      const basePayload = {
        channel: purchaseChannel,
        payment_source: paymentSource,
        plan_id: effectivePlanId,
        duration_days: effectiveSelectedDuration,
        gateway_type: effectiveSelectedGateway,
        payment_asset: effectiveSelectedPaymentAsset,
        quantity: isNewPurchaseFlow ? normalizedQuantity : undefined,
        device_type: isNewPurchaseFlow ? selectedDeviceType || undefined : undefined,
        device_types: isNewPurchaseFlow ? deviceTypes : undefined,
        success_redirect_url: successRedirectUrl,
        fail_redirect_url: failRedirectUrl,
      }

      let response
      if (upgradeSubscriptionId) {
        response = await api.subscription.upgrade(upgradeSubscriptionId, {
          ...basePayload,
        })
      } else if (renewId) {
        response = await api.subscription.renew(renewId, {
          ...basePayload,
          renew_subscription_ids: selectedRenewIds.length > 1 ? selectedRenewIds : undefined,
        })
      } else if (isRenewFlow) {
        response = await api.subscription.purchase({
          ...basePayload,
          purchase_type: 'RENEW',
          renew_subscription_id: singleRenewId || undefined,
          renew_subscription_ids: selectedRenewIds.length > 1 ? selectedRenewIds : undefined,
        })
      } else {
        response = await api.subscription.purchase({
          ...basePayload,
          purchase_type: 'NEW',
        })
      }

      const paymentUrl = response.data.payment_url || response.data.url
      if (paymentUrl) {
        savePendingPurchaseContext({
          startedAt: new Date().toISOString(),
          purchaseType,
          renewIds: upgradeSubscriptionId ? [upgradeSubscriptionId] : renewTargets,
          planId: effectivePlanId,
          durationDays: effectiveSelectedDuration,
        })

        if (isInTelegram) {
          const wasCheckoutOpen = isCheckoutOpen
          if (wasCheckoutOpen) {
            setIsCheckoutOpen(false)
            await new Promise((resolve) => window.setTimeout(resolve, 120))
          }

          const opened = openExternalLink(paymentUrl)
          if (!opened) {
            if (wasCheckoutOpen) {
              setIsCheckoutOpen(true)
            }
            toast.error(text.openCheckoutFailed)
            return
          }

          return
        }

        window.location.href = paymentUrl
        return
      }

      toast.success(text.paymentSuccess)
      await queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      navigate('/dashboard/subscription')
    } catch (error: unknown) {
      toast.error(extractPurchaseError(error, text))
    } finally {
      purchaseLaunchRef.current = false
      setIsPurchasing(false)
    }
  }

  const paymentAssetSelector = selectedPrice && availablePaymentAssets.length > 0 ? (
    <div className="space-y-3 border-t border-white/10 pt-3">
      <div>
        <p className="text-sm font-medium">{text.selectPaymentAssetTitle}</p>
        <p className="text-xs text-muted-foreground">{text.selectPaymentAssetDesc}</p>
      </div>

      {availablePaymentAssets.length === 1 ? (
        <div className="rounded-xl border border-white/12 bg-white/[0.04] p-4 text-sm">
          <CryptoAssetNameWithIcon asset={effectiveSelectedPaymentAsset} className="font-medium" />
        </div>
      ) : (
        <Select
          value={effectiveSelectedPaymentAsset}
          onValueChange={(value) => setSelectedPaymentAsset(value as CryptoAsset)}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder={text.choosePaymentAsset} />
          </SelectTrigger>
          <SelectContent position={isMobileShell ? 'item-aligned' : 'popper'}>
            {availablePaymentAssets.map((asset) => (
              <SelectItem key={asset} value={asset}>
                <CryptoAssetNameWithIcon asset={asset} />
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </div>
  ) : null

  const paymentSourceSelector = effectiveSelectedDuration !== null && canUsePartnerBalance ? (
    <Card>
      <CardHeader>
        <CardTitle>{text.paymentSourceTitle}</CardTitle>
        <CardDescription>{text.paymentSourceDesc}</CardDescription>
      </CardHeader>
      <CardContent>
        <RadioGroup
          value={paymentSource}
          onValueChange={(value) => {
            setPaymentSource(value as PurchasePaymentSource)
            setSelectedGateway(undefined)
            setSelectedPaymentAsset(undefined)
          }}
          className="grid gap-3 sm:grid-cols-2"
        >
          <button
            type="button"
            className={cn(
              'rounded-lg border px-4 py-3 text-left transition-all',
              paymentSource === EXTERNAL_PAYMENT_SOURCE
                ? 'border-primary/35 bg-primary/10 ring-1 ring-primary/40'
                : 'hover:bg-muted/30'
            )}
            onClick={() => {
              setPaymentSource(EXTERNAL_PAYMENT_SOURCE)
              setSelectedGateway(undefined)
              setSelectedPaymentAsset(undefined)
            }}
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem value={EXTERNAL_PAYMENT_SOURCE} id={EXTERNAL_PAYMENT_SOURCE} />
              <Label htmlFor={EXTERNAL_PAYMENT_SOURCE} className="cursor-pointer font-medium">
                {text.externalGateway}
              </Label>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{text.externalGatewayDesc}</p>
          </button>

          <button
            type="button"
            className={cn(
              'rounded-lg border px-4 py-3 text-left transition-all',
              paymentSource === PARTNER_BALANCE_PAYMENT_SOURCE
                ? 'border-primary/35 bg-primary/10 ring-1 ring-primary/40'
                : 'hover:bg-muted/30'
            )}
            onClick={() => {
              setPaymentSource(PARTNER_BALANCE_PAYMENT_SOURCE)
              setSelectedGateway(undefined)
              setSelectedPaymentAsset(undefined)
            }}
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem
                value={PARTNER_BALANCE_PAYMENT_SOURCE}
                id={PARTNER_BALANCE_PAYMENT_SOURCE}
              />
              <Label
                htmlFor={PARTNER_BALANCE_PAYMENT_SOURCE}
                className="cursor-pointer font-medium"
              >
                {text.partnerBalance}
              </Label>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {text.available}: {formatPriceAmount(partnerBalanceDisplay)} {partnerBalanceCurrency}
              {partnerBalanceCurrency !== 'RUB' ? ` (${partnerBalanceRub.toFixed(2)} RUB)` : ''}
            </p>
          </button>
        </RadioGroup>
      </CardContent>
    </Card>
  ) : null

  const paymentGatewaySelector = effectiveSelectedDuration !== null && selectedPlanData ? (
    <Card>
      <CardHeader>
        <CardTitle>{text.selectPaymentMethodTitle}</CardTitle>
        <CardDescription>
          {paymentSource === PARTNER_BALANCE_PAYMENT_SOURCE
            ? text.selectPaymentMethodPartnerDesc
            : text.selectPaymentMethodExternalDesc}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {showQuantitySelector && (
          <div className="flex items-center justify-between rounded-lg border border-white/12 bg-white/[0.02] px-3 py-2">
            <span className="text-xs text-muted-foreground">{text.quantity}</span>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() => setQuantity((prev) => Math.max(1, prev - 1))}
                disabled={normalizedQuantity <= 1}
              >
                -
              </Button>
              <span className="min-w-8 text-center text-sm font-semibold">{normalizedQuantity}</span>
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-8 w-8"
                onClick={() =>
                  setQuantity((prev) =>
                    maxPurchasableQuantity === null
                      ? prev + 1
                      : Math.min(prev + 1, maxPurchasableQuantity)
                  )
                }
                disabled={
                  maxPurchasableQuantity !== null && normalizedQuantity >= maxPurchasableQuantity
                }
              >
                +
              </Button>
            </div>
          </div>
        )}

        {noGatewayAvailable ? (
          <div className="rounded-xl border border-amber-300/20 bg-amber-500/10 p-4">
            <p className="flex items-center gap-2 text-sm text-amber-200">
              <AlertTriangle className="h-4 w-4" />
              {noGatewayMessage}
            </p>
          </div>
        ) : availableGatewayPrices.length === 1 ? (
          <div className="rounded-xl border border-white/12 bg-white/[0.04] p-4 text-sm">
            <p className="font-medium text-foreground">
              <GatewayNameWithIcon gatewayType={availableGatewayPrices[0].gateway_type} />
            </p>
            <p className="mt-1 text-muted-foreground">
              {formatPriceAmount(availableGatewayPrices[0].price)} {availableGatewayPrices[0].currency}
            </p>
          </div>
        ) : (
          <Select
            value={effectiveSelectedGateway}
            onValueChange={(value) => {
              setSelectedGateway(value)
              setSelectedPaymentAsset(undefined)
            }}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder={text.choosePaymentMethod} />
            </SelectTrigger>
            <SelectContent position={isMobileShell ? 'item-aligned' : 'popper'}>
              {availableGatewayPrices.map((price) => (
                <SelectItem key={price.gateway_type} value={price.gateway_type}>
                    <span className="flex w-full items-center gap-2">
                      <GatewayNameWithIcon gatewayType={price.gateway_type} />
                      <span className="ml-auto text-xs text-muted-foreground">
                        {formatPriceAmount(price.price)} {price.currency}
                        {price.discount_percent > 0 ? ` (-${price.discount_percent}%)` : ''}
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

        {paymentAssetSelector}
      </CardContent>
    </Card>
  ) : null
  const renderLimitWarningCard = () => {
    if (!showLimitWarning || effectiveMaxSubscriptions === null) {
      return null
    }

    return (
      <Card className="border-amber-300/25 bg-amber-500/10">
        <CardHeader>
          <CardTitle>{text.limitCheckTitle}</CardTitle>
          <CardDescription className="text-amber-100/90">
            {submitBlockReason === 'LIMIT_WOULD_BE_EXCEEDED' ? text.limitWouldExceed : text.limitReached}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-amber-300/15 bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-amber-200/80">{text.limitCurrentActive}</p>
              <p className="mt-1 text-lg font-semibold text-amber-50">{activeSubscriptionsCount}</p>
            </div>
            <div className="rounded-xl border border-amber-300/15 bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-amber-200/80">{text.limitMaximum}</p>
              <p className="mt-1 text-lg font-semibold text-amber-50">{effectiveMaxSubscriptions}</p>
            </div>
            <div className="rounded-xl border border-amber-300/15 bg-black/10 p-3">
              <p className="text-xs uppercase tracking-wide text-amber-200/80">{text.subscriptionsAfterPurchase}</p>
              <p className="mt-1 text-lg font-semibold text-amber-50">
                {activeSubscriptionsCount + effectiveSubscriptionCount}
              </p>
            </div>
            {remainingSlots !== null && remainingSlots > 0 && (
              <div className="rounded-xl border border-amber-300/15 bg-black/10 p-3">
                <p className="text-xs uppercase tracking-wide text-amber-200/80">{text.limitRemaining}</p>
                <p className="mt-1 text-lg font-semibold text-amber-50">{remainingSlots}</p>
              </div>
            )}
          </div>

          <div className="space-y-1">
            <p className="text-sm text-amber-100">{text.limitCheckDesc}</p>
            <p className="text-xs text-amber-200/85">{text.limitCheckServerValidation}</p>
          </div>

          <Button type="button" onClick={() => navigate('/dashboard/subscription')}>
            {text.manageSubscriptions}
          </Button>
        </CardContent>
      </Card>
    )
  }
  const renderSubmitBlockNotice = () => {
    if (!submitBlockMessage) {
      return null
    }

    return (
      <div
        className={cn(
          'rounded-lg border px-3 py-2',
          submitBlockReason === 'QUOTE_PENDING_OR_FAILED' && isQuoteFetching
            ? 'border-sky-300/25 bg-sky-500/10'
            : 'border-amber-300/20 bg-amber-500/10'
        )}
      >
        <p
          className={cn(
            'text-xs',
            submitBlockReason === 'QUOTE_PENDING_OR_FAILED' && isQuoteFetching
              ? 'text-sky-100'
              : 'text-amber-100'
          )}
        >
          {submitBlockMessage}
        </p>
      </div>
    )
  }

  const displayPrice = selectedQuote ?? selectedPrice
  const showOriginalPrice = hasActiveDiscount(displayPrice)
  const totalFinalPrice = selectedQuote?.price ?? ((selectedPrice?.price ?? 0) * priceMultiplier)
  const totalOriginalPrice =
    selectedQuote?.original_price ?? ((selectedPrice?.original_price ?? selectedPrice?.price ?? 0) * priceMultiplier)
  const totalCurrency = selectedQuote?.currency ?? selectedPrice?.currency ?? ''
  const showSettlementEquivalent = Boolean(
    selectedQuote
      && selectedQuote.currency !== selectedQuote.settlement_currency
  )

  const orderSummaryContent = (
    <div className="space-y-3">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{text.summaryPlan}</span>
        <span className="font-medium">{selectedPlanData?.name || '-'}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{text.summaryDuration}</span>
        <span className="font-medium">
          {effectiveSelectedDuration !== null ? formatDurationLabel(effectiveSelectedDuration, text) : '-'}
        </span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{text.summaryDevice}</span>
        <span className="font-medium">
          {isNewPurchaseFlow ? selectedDeviceType || '-' : text.summaryDeviceNotRequired}
        </span>
      </div>
      {isNewPurchaseFlow && (
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{text.quantity}</span>
          <span className="font-medium">x{normalizedQuantity}</span>
        </div>
      )}
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{text.totalSubscriptions}</span>
        <span className="font-medium">x{effectiveSubscriptionCount}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{text.summaryPayment}</span>
        <GatewayNameWithIcon gatewayType={effectiveSelectedGateway} className="font-medium" />
      </div>
      {availablePaymentAssets.length > 0 && (
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">{text.summaryPaymentAsset}</span>
          {effectiveSelectedPaymentAsset ? (
            <CryptoAssetNameWithIcon asset={effectiveSelectedPaymentAsset} className="font-medium" />
          ) : (
            <span className="font-medium">-</span>
          )}
        </div>
      )}
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{text.summarySource}</span>
        <span className="font-medium">
          {paymentSource === PARTNER_BALANCE_PAYMENT_SOURCE ? text.summaryPartnerBalance : text.summaryExternal}
        </span>
      </div>

      {displayPrice && (
        <>
          {showOriginalPrice && (
            <div className="border-t pt-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">{text.summaryOriginalPrice}</span>
                <span className="line-through">
                  {formatPriceAmount(totalOriginalPrice)} {totalCurrency}
                </span>
              </div>
            </div>
          )}
          <div className="flex justify-between border-t pt-3 text-lg font-semibold">
            <span>{text.summaryTotal}</span>
            <div className="text-right">
              <div className="flex items-center justify-end gap-2">
              {showOriginalPrice && (
                  <DiscountBadge percent={displayPrice.discount_percent} />
              )}
                <span>
                  {formatPriceAmount(totalFinalPrice)} {totalCurrency}
                </span>
              </div>
              {showSettlementEquivalent && selectedQuote && (
                <div className="mt-1 text-xs font-normal text-muted-foreground">
                  {formatPriceAmount(selectedQuote.settlement_price)} {selectedQuote.settlement_currency}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )

  if (isLoading) {
    return <PurchaseSkeleton />
  }

  if (!availablePlans.length) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">{pageTitle}</h1>
          <p className="text-muted-foreground">{pageSubtitle}</p>
        </div>

        {trialCard}
        {purchaseWarningMessage && (
          <Card className="border-amber-300/25 bg-amber-500/10">
            <CardContent className="pt-6">
              <p className="text-sm text-amber-100">{purchaseWarningMessage}</p>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>{text.noPlansTitle}</CardTitle>
            <CardDescription>
              {text.noPlansDesc}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">{pageTitle}</h1>
        <p className="text-muted-foreground">{pageSubtitle}</p>
      </div>

      {(isReadOnlyAccess || isPurchaseBlocked) && (
        <Card className="border-amber-300/25 bg-amber-500/10">
          <CardContent className="pt-6">
            <p className="text-sm text-amber-100">
              {isPurchaseBlocked ? text.purchaseBlockedNotice : text.readOnlyNotice}
            </p>
          </CardContent>
        </Card>
      )}

      {trialCard}
      {renderLimitWarningCard()}
      {purchaseWarningMessage && (
        <Card className="border-amber-300/25 bg-amber-500/10">
          <CardContent className="space-y-2 pt-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" />
              <p className="text-sm text-amber-100">{purchaseWarningMessage}</p>
            </div>
            {isPlanSelectionLocked && (
              <p className="text-xs text-amber-200/90">{text.selectionLocked}</p>
            )}
          </CardContent>
        </Card>
      )}

      <div className={cn('grid gap-6', isMobileShell ? 'grid-cols-1' : 'lg:grid-cols-3')}>
        <Card className={cn(!isMobileShell && 'lg:col-span-2')}>
          <CardHeader>
            <CardTitle>{text.selectPlanTitle}</CardTitle>
            <CardDescription>{selectPlanDescription}</CardDescription>
          </CardHeader>
          <CardContent>
            <RadioGroup
              value={effectivePlanId !== null ? effectivePlanId.toString() : ''}
              onValueChange={(value) => {
                if (isPlanSelectionLocked) {
                  return
                }
                setSelectedPlan(Number(value))
                setSelectedDuration(null)
                setSelectedGateway(undefined)
                setSelectedPaymentAsset(undefined)
              }}
              className="grid gap-4 md:grid-cols-2"
            >
              {availablePlans.map((plan) => (
                <label
                  key={plan.id}
                  htmlFor={`plan-${plan.id}`}
                  className={cn(
                    'flex flex-col gap-4 rounded-lg border p-4 transition-all',
                    isPlanSelectionLocked ? 'cursor-default' : 'cursor-pointer',
                    effectivePlanId === plan.id
                      ? 'border-primary/35 bg-primary/10 ring-1 ring-primary/40'
                      : 'hover:bg-muted/30'
                  )}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <RadioGroupItem value={plan.id.toString()} id={`plan-${plan.id}`} />
                      <span className="font-medium">{plan.name}</span>
                    </div>
                    {effectivePlanId === plan.id && <Check className="h-5 w-5 text-primary" />}
                  </div>

                  <div className="text-sm text-muted-foreground">
                    {plan.description || text.noDescription}
                  </div>

                  <div className="rounded-md border border-white/10 bg-white/[0.03] p-3">
                    <p className="mb-2 text-[11px] uppercase tracking-wide text-slate-400">
                      {text.includes}
                    </p>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full border border-white/12 bg-white/[0.03] px-2.5 py-1 text-slate-200">
                        {text.type}: {formatPlanType(plan.type)}
                      </span>
                      <span className="rounded-full border border-white/12 bg-white/[0.03] px-2.5 py-1 text-slate-200">
                        {text.traffic}: {formatTrafficLimit(plan.traffic_limit, text)}
                      </span>
                      <span className="rounded-full border border-white/12 bg-white/[0.03] px-2.5 py-1 text-slate-200">
                        {text.devices}: {formatDeviceLimit(plan.device_limit, text)}
                      </span>
                      {plan.tag && (
                        <span className="rounded-full border border-white/12 bg-white/[0.03] px-2.5 py-1 text-slate-200">
                          {text.tag}: {plan.tag}
                        </span>
                      )}
                    </div>
                  </div>
                </label>
              ))}
            </RadioGroup>
          </CardContent>
        </Card>

        {!isMobileShell && (
          <Card>
            <CardHeader>
              <CardTitle>{text.orderSummary}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {orderSummaryContent}

              <Button className="w-full" onClick={handlePurchase} disabled={!canSubmit}>
                {isPurchasing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {text.processing}
                  </>
                ) : isUpgradeFlow ? (
                  text.proceedUpgrade
                ) : isRenewFlow ? (
                  text.proceedRenew
                ) : (
                  text.proceedPayment
                )}
              </Button>
              {renderSubmitBlockNotice()}

              <Button
                variant="outline"
                className="w-full"
                onClick={() => navigate('/dashboard/subscription')}
              >
                {text.cancel}
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      {selectedPlanData && (
        <Card>
          <CardHeader>
            <CardTitle>{text.selectDurationTitle}</CardTitle>
            <CardDescription>{text.selectDurationDesc}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {sortedDurations.map((duration) => (
                <button
                  key={duration.id}
                  type="button"
                  className={cn(
                    'relative w-full cursor-pointer rounded-md border px-3 py-2 text-left transition-all',
                    effectiveSelectedDuration === duration.days
                    ? 'border-primary/35 bg-primary/10 ring-1 ring-primary/40'
                    : 'hover:bg-muted/30'
                  )}
                  onClick={() => {
                    setSelectedDuration(duration.days)
                    setSelectedGateway(undefined)
                    setSelectedPaymentAsset(undefined)
                  }}
                >
                  {duration.days >= 90 && (
                    <span className="absolute right-2 top-1 rounded-full bg-emerald-500/80 px-2 py-0.5 text-[10px] text-white">
                      {text.bestValue}
                    </span>
                  )}
                  {duration.days <= 0 && (
                    <span className="absolute right-2 top-1 rounded-full border border-sky-300/30 bg-sky-400/20 px-2 py-0.5 text-[10px] text-sky-100">
                      {text.unlimitedTerm}
                    </span>
                  )}
                  <div className="text-sm font-semibold">{formatDurationLabel(duration.days, text)}</div>
                  <div className="text-xs text-muted-foreground">
                    {getDurationPriceLabel(duration, text, currentUser?.default_currency)}
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {effectiveSelectedDuration !== null && isNewPurchaseFlow && (
        <Card>
          <CardHeader>
            <CardTitle>{text.selectDeviceTitle}</CardTitle>
            <CardDescription>{text.selectDeviceDesc}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {deviceOptions.map((device) => (
                <button
                  key={device.value}
                  type="button"
                  className={cn(
                    'rounded-lg border px-4 py-3 text-left transition-all',
                    selectedDeviceType === device.value
                      ? 'border-primary/35 bg-primary/10 ring-1 ring-primary/40'
                      : 'hover:bg-muted/30'
                  )}
                  onClick={() => setSelectedDeviceType(device.value)}
                >
                  <div className="flex items-center gap-2">
                    <device.icon className="h-4 w-4 text-primary" />
                    <p className="text-sm font-semibold">{device.label}</p>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {!isMobileShell && paymentSourceSelector}
      {!isMobileShell && paymentGatewaySelector}

      {isMobileShell && (
        <div className="sticky bottom-[calc(0.75rem+var(--app-safe-bottom))] z-20 rounded-2xl border border-white/12 bg-[#090c10]/96 p-3">
          <div className="grid grid-cols-2 gap-2">
            <Button type="button" onClick={() => setIsCheckoutOpen(true)} disabled={!canOpenCheckout}>
              {text.openCheckout}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/dashboard/subscription')}
            >
              {text.cancel}
            </Button>
          </div>
        </div>
      )}

      {isMobileShell && (
        <Sheet open={isCheckoutOpen} onOpenChange={setIsCheckoutOpen}>
          <SheetContent
            side="bottom"
            disableMotion
            overlayClassName="bg-black/88 backdrop-blur-0 data-[state=open]:animate-none data-[state=closed]:animate-none"
            className="max-h-[calc(100vh-0.5rem)] overflow-y-auto overscroll-y-contain rounded-t-2xl rounded-b-none border-white/12 bg-[#090c10] shadow-[0_18px_40px_-28px_rgba(0,0,0,0.95)]"
          >
            <SheetHeader>
              <SheetTitle>{text.orderSummary}</SheetTitle>
              <SheetDescription>{text.openCheckout}</SheetDescription>
            </SheetHeader>

            <div className="mt-4 space-y-4 pb-2">
              {paymentSourceSelector}
              {paymentGatewaySelector}
              {renderLimitWarningCard()}

              <Card>
                <CardContent className="pt-4">
                  {orderSummaryContent}
                </CardContent>
              </Card>

              <Button className="w-full" onClick={handlePurchase} disabled={!canSubmit}>
                {isPurchasing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {text.processing}
                  </>
                ) : isUpgradeFlow ? (
                  text.proceedUpgrade
                ) : isRenewFlow ? (
                  text.proceedRenew
                ) : (
                  text.proceedPayment
                )}
              </Button>
              {renderSubmitBlockNotice()}
            </div>
          </SheetContent>
        </Sheet>
      )}
    </div>
  )
}

function extractPurchaseError(error: unknown, text: PurchaseText): string {
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
  if (detail && typeof detail === 'object') {
    if (detail.code === 'INSUFFICIENT_PARTNER_BALANCE') {
      return text.insufficientPartnerBalance
    }
    if (detail.code === 'PARTNER_BALANCE_RUB_ONLY') {
      return text.partnerBalanceRubOnly
    }
    if (detail.code === 'PARTNER_BALANCE_WEB_ONLY') {
      return text.partnerBalanceWebOnly
    }
    if (detail.code === 'PARTNER_BALANCE_GATEWAY_REQUIRED') {
      return text.partnerBalanceGatewayRequired
    }
    if (detail.code === 'PARTNER_BALANCE_PARTNER_INACTIVE') {
      return text.partnerBalancePartnerInactive
    }
    if (detail.code === 'TRIAL_UPGRADE_REQUIRED') {
      return text.trialUpgradeRequired
    }
    if (detail.code === 'ARCHIVED_PLAN_NOT_PURCHASABLE') {
      return text.archivedPlanNotPurchasable
    }
    if (detail.message) {
      return detail.message
    }
  }
  return text.createPaymentFailed
}

function resolveTrialReasonMessageByCode(code: string, text: PurchaseText): string {
  if (code === 'TRIAL_TELEGRAM_LINK_REQUIRED') {
    return text.trialErrorLinkRequired
  }
  if (code === 'TRIAL_ALREADY_USED') {
    return text.trialErrorAlreadyUsed
  }
  if (code === 'TRIAL_NOT_FIRST_SUBSCRIPTION') {
    return text.trialErrorExistingSubscription
  }
  if (code === 'TRIAL_PLAN_NOT_CONFIGURED') {
    return text.trialErrorPlanNotConfigured
  }
  if (code === 'TRIAL_PLAN_INACTIVE') {
    return text.trialErrorPlanInactive
  }
  if (code === 'TRIAL_PLAN_NO_DURATION') {
    return text.trialErrorNoDuration
  }
  if (code === 'TRIAL_PLAN_NOT_TRIAL') {
    return text.trialErrorNotTrialPlan
  }
  if (code === 'TRIAL_PLAN_NOT_FOUND') {
    return text.trialErrorPlanNotFound
  }
  return text.trialUnavailable
}

function resolveTrialEligibilityMessage(
  trialEligibility: TrialEligibilityResponse | undefined,
  text: PurchaseText
): string {
  if (!trialEligibility) {
    return text.trialUnavailable
  }

  if (trialEligibility.eligible) {
    return text.trialDesc
  }

  if (trialEligibility.reason_code) {
    const mappedMessage = resolveTrialReasonMessageByCode(trialEligibility.reason_code, text)
    if (mappedMessage !== text.trialUnavailable) {
      return mappedMessage
    }
    return trialEligibility.reason_message || text.trialUnavailable
  }

  return trialEligibility.reason_message || text.trialUnavailable
}

function extractTrialError(error: unknown, text: PurchaseText): string {
  const apiError = error as {
    response?: {
      data?: {
        detail?: string | { code?: string; message?: string }
      }
    }
  }

  const detail = apiError.response?.data?.detail
  if (typeof detail === 'string' && detail.length > 0) {
    if (detail === 'Trial subscription already used') {
      return text.trialErrorAlreadyUsed
    }
    if (detail === 'Trial is only available before first active subscription') {
      return text.trialErrorExistingSubscription
    }
    return detail
  }

  if (detail && typeof detail === 'object') {
    if (detail.code === 'TRIAL_TELEGRAM_LINK_REQUIRED') {
      return text.trialErrorLinkRequired
    }
    if (detail.code) {
      return resolveTrialReasonMessageByCode(detail.code, text)
    }
    if (detail.message) {
      return detail.message
    }
  }

  return text.trialErrorDefault
}

function PurchaseSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              {[1, 2, 3, 4].map((skeletonId) => (
                <div key={`skeleton-${skeletonId}`} className="space-y-3 rounded-lg border p-4">
                  <Skeleton className="h-5 w-32" />
                  <Skeleton className="h-4 w-full" />
                  <div className="flex gap-4">
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            {[1, 2, 3, 4, 5].map((summaryId) => (
              <Skeleton key={`summary-${summaryId}`} className="h-4 w-full" />
            ))}
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
