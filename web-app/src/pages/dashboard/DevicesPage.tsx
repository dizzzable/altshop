import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { useI18n } from '@/components/common/I18nProvider'
import { useAccessStatusQuery } from '@/hooks/useAccessStatusQuery'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { useSubscriptionsQuery } from '@/hooks/useSubscriptionsQuery'
import { resolveAccessCapabilities } from '@/lib/access-capabilities'
import { queryKeys } from '@/lib/query-keys'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
  DEVICE_TYPE_META,
  formatLimitLabel,
  normalizeDeviceType,
} from '@/lib/subscription-display'
import { cn, formatRelativeTime } from '@/lib/utils'
import { openExternalLink } from '@/lib/openExternalLink'
import {
  ChevronRight,
  Copy,
  ExternalLink,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import type { Device, DeviceListResponse, DeviceType, Subscription } from '@/types'

const STATUS_META: Record<
  Subscription['status'],
  { labelKey: string; tone: string }
> = {
  ACTIVE: { labelKey: 'devices.status.active', tone: 'text-emerald-200' },
  EXPIRED: { labelKey: 'devices.status.expired', tone: 'text-rose-200' },
  LIMITED: { labelKey: 'devices.status.limited', tone: 'text-amber-200' },
  DISABLED: { labelKey: 'devices.status.disabled', tone: 'text-slate-300' },
  DELETED: { labelKey: 'devices.status.deleted', tone: 'text-slate-500' },
}

function formatCount(value: number): string {
  return value < 0 ? '0' : String(value)
}

type SubscriptionsCache = Subscription[] | { subscriptions: Subscription[] }

function updateSubscriptionsCache(
  current: SubscriptionsCache | undefined,
  subscriptionId: number,
  patch: Partial<Pick<Subscription, 'device_type' | 'devices_count' | 'device_limit'>>
) {
  if (!current) {
    return current
  }

  const applyUpdate = (items: Subscription[]) =>
    items.map((subscription) =>
      subscription.id === subscriptionId
        ? { ...subscription, ...patch }
        : subscription
    )

  if (Array.isArray(current)) {
    return applyUpdate(current)
  }

  if (Array.isArray(current.subscriptions)) {
    return {
      ...current,
      subscriptions: applyUpdate(current.subscriptions),
    }
  }

  return current
}

export function DevicesPage() {
  const { t } = useI18n()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: accessStatus } = useAccessStatusQuery()
  const accessCapabilities = useMemo(
    () => resolveAccessCapabilities(accessStatus),
    [accessStatus]
  )

  const querySubscription = searchParams.get('subscription')
  const parsedSubscriptionId = querySubscription ? Number(querySubscription) : null
  const selectedSubscriptionId =
    parsedSubscriptionId && Number.isInteger(parsedSubscriptionId) && parsedSubscriptionId > 0
      ? parsedSubscriptionId
      : null

  const [detailsOpen, setDetailsOpen] = useState(false)
  const [generatedLink, setGeneratedLink] = useState<string | null>(null)
  const [assignmentDeviceType, setAssignmentDeviceType] = useState<DeviceType>('OTHER')
  const [deviceToDelete, setDeviceToDelete] = useState<string | null>(null)
  const isReadOnlyAccess = accessCapabilities.isReadOnly

  const { data: subscriptions = [], isLoading: subscriptionsLoading } = useSubscriptionsQuery()

  const visibleSubscriptions = useMemo(
    () => subscriptions.filter((subscription) => subscription.status !== 'DELETED'),
    [subscriptions]
  )

  useEffect(() => {
    if (subscriptionsLoading || selectedSubscriptionId || !visibleSubscriptions.length) {
      return
    }

    const preferred =
      visibleSubscriptions.find((subscription) => subscription.status === 'ACTIVE')
      || visibleSubscriptions[0]

    if (!preferred) {
      return
    }

    const next = new URLSearchParams(searchParams)
    next.set('subscription', String(preferred.id))
    setSearchParams(next, { replace: true })
  }, [
    searchParams,
    selectedSubscriptionId,
    setSearchParams,
    subscriptionsLoading,
    visibleSubscriptions,
  ])

  const selectedSubscription =
    visibleSubscriptions.find((subscription) => subscription.id === selectedSubscriptionId) ?? null
  const savedAssignmentDeviceType = normalizeDeviceType(selectedSubscription?.device_type)
  const hasAssignmentChanges = Boolean(selectedSubscription) && assignmentDeviceType !== savedAssignmentDeviceType

  const {
    data: devicesData,
    isLoading: devicesLoading,
    error: devicesError,
    refetch: refetchDevices,
  } = useQuery<DeviceListResponse, Error>({
    queryKey: queryKeys.devices(selectedSubscription?.id),
    queryFn: () => api.devices.list(selectedSubscription!.id).then((response) => response.data),
    enabled: !!selectedSubscription,
  })

  useEffect(() => {
    if (!devicesError) {
      return
    }
    toast.error(getApiErrorMessage(devicesError) || t('devices.toast.loadFailed'))
  }, [devicesError, t])

  useEffect(() => {
    if (!selectedSubscription || !devicesData) {
      return
    }

    queryClient.setQueryData<SubscriptionsCache>(queryKeys.subscriptions(), (current) =>
      updateSubscriptionsCache(current, selectedSubscription.id, {
        devices_count: devicesData.devices_count,
        device_limit: devicesData.device_limit,
      })
    )
  }, [devicesData, queryClient, selectedSubscription])

  const isInitialDevicesLoad = devicesLoading && !devicesData
  const currentDevicesCount =
    devicesData?.devices_count
    ?? (isInitialDevicesLoad ? null : selectedSubscription?.devices_count ?? null)
  const currentDevicesCountLabel = currentDevicesCount === null ? '—' : formatCount(currentDevicesCount)

  const assignmentMutation = useMutation({
    mutationFn: (payload: { device_type: DeviceType }) =>
      api.subscription.updateAssignment(selectedSubscription!.id, payload),
    onSuccess: (response) => {
      const updatedSubscription = response.data
      queryClient.setQueryData<SubscriptionsCache>(queryKeys.subscriptions(), (current) => {
        return updateSubscriptionsCache(current, updatedSubscription.id, {
          device_type: updatedSubscription.device_type,
        })
      })
      setAssignmentDeviceType(normalizeDeviceType(updatedSubscription.device_type))
      toast.success(t('devices.toast.assignmentUpdated'))
      queryClient.invalidateQueries({ queryKey: queryKeys.subscriptions() })
      queryClient.invalidateQueries({ queryKey: queryKeys.devices(selectedSubscription?.id) })
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error) || t('devices.toast.assignmentFailed'))
    },
  })

  const generateMutation = useMutation({
    mutationFn: (payload: { subscription_id: number; device_type: DeviceType }) =>
      api.devices.generate(payload),
    onSuccess: (response) => {
      if (selectedSubscription) {
        queryClient.setQueryData<SubscriptionsCache>(queryKeys.subscriptions(), (current) =>
          updateSubscriptionsCache(current, selectedSubscription.id, {
            device_type: normalizeDeviceType(response.data.device_type),
          })
        )
      }
      setGeneratedLink(response.data.connection_url)
      toast.success(t('devices.toast.linkRegenerated'))
      queryClient.invalidateQueries({ queryKey: queryKeys.devices(selectedSubscription?.id) })
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error) || t('devices.toast.linkRegenerateFailed'))
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (payload: { hwid: string; subscription_id: number }) =>
      api.devices.revoke(payload.hwid, payload.subscription_id),
    onSuccess: () => {
      toast.success(t('devices.toast.deviceRevoked'))
      setDeviceToDelete(null)
      refetchDevices()
    },
    onError: (error: unknown) => {
      toast.error(getApiErrorMessage(error) || t('devices.toast.deviceRevokeFailed'))
    },
  })

  const openDetails = (subscription: Subscription) => {
    const next = new URLSearchParams(searchParams)
    next.set('subscription', String(subscription.id))
    setSearchParams(next, { replace: true })
    setAssignmentDeviceType(normalizeDeviceType(subscription.device_type))
    setGeneratedLink(null)
    setDetailsOpen(true)
  }

  const saveAssignment = () => {
    if (isReadOnlyAccess) {
      toast.error(t('devices.readOnlyNotice'))
      return
    }

    if (!selectedSubscription || !hasAssignmentChanges) {
      return
    }

    assignmentMutation.mutate({
      device_type: assignmentDeviceType,
    })
  }

  const regenerateLink = () => {
    if (isReadOnlyAccess) {
      toast.error(t('devices.readOnlyNotice'))
      return
    }

    if (!selectedSubscription) {
      return
    }

    generateMutation.mutate({
      subscription_id: selectedSubscription.id,
      device_type: assignmentDeviceType,
    })
  }

  const connectBySubscriptionLink = () => {
    if (!selectedSubscription) {
      return
    }
    if (!openExternalLink(selectedSubscription.url)) {
      toast.error(t('common.openLinkFailed'))
    }
  }

  const copyText = async (value: string, message: string) => {
    try {
      await navigator.clipboard.writeText(value)
      toast.success(message)
    } catch {
      toast.error(t('devices.toast.copyFailed'))
    }
  }

  const closeDetailsPanel = (open: boolean) => {
    setDetailsOpen(open)
    if (!open) {
      setGeneratedLink(null)
      setDeviceToDelete(null)
    }
  }

  if (subscriptionsLoading) {
    return <DevicesSkeleton />
  }

  if (!visibleSubscriptions.length) {
    return (
      <div className="flex min-h-[320px] items-center justify-center">
        <Card className="w-full max-w-md border-white/10 bg-card/90">
          <CardContent className="pt-6 text-center">
            <p className="mb-3 text-slate-200">{t('devices.empty.title')}</p>
            <p className="mb-5 text-sm text-slate-400">
              {t('devices.empty.desc')}
            </p>
            <Button
              onClick={() => navigate('/dashboard/subscription/purchase')}
              disabled={isReadOnlyAccess}
            >
              {t('devices.empty.cta')}
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <>
      <div className="space-y-4">
        {isReadOnlyAccess && (
          <Card className="border-amber-300/25 bg-amber-500/10">
            <CardContent className="pt-6">
              <p className="text-sm text-amber-100">{t('devices.readOnlyNotice')}</p>
            </CardContent>
          </Card>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className={cn('font-bold tracking-tight text-slate-100', useMobileUiV2 ? 'text-2xl' : 'text-3xl')}>
              {t('devices.title')}
            </h1>
            <p className="text-sm text-slate-400">
              {t('devices.subtitle')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="border-white/15 bg-white/5 text-slate-200">
              {t('devices.badge.subscriptions', { count: visibleSubscriptions.length })}
            </Badge>
            {selectedSubscription && (
              <Badge variant="outline" className="border-white/15 bg-white/5 text-slate-200">
                {t('devices.badge.current')}: {currentDevicesCountLabel} /{' '}
                {formatLimitLabel(devicesData?.device_limit ?? selectedSubscription.device_limit, t('devices.unlimited'))}
              </Badge>
            )}
          </div>
        </div>

        <Card className="border-white/10 bg-card/90">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg text-slate-100">{t('devices.card.myDevices')}</CardTitle>
            <CardDescription className="text-slate-400">
              {t('devices.card.myDevicesDesc')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {visibleSubscriptions.map((subscription) => {
              const deviceType = normalizeDeviceType(subscription.device_type)
              const typeMeta = DEVICE_TYPE_META[deviceType]
              const isCurrent = subscription.id === selectedSubscription?.id
              const status = STATUS_META[subscription.status]
              const count = isCurrent && devicesData ? devicesData.devices_count : subscription.devices_count
              const limit = isCurrent && devicesData ? devicesData.device_limit : subscription.device_limit

              return (
                <button
                  key={subscription.id}
                  type="button"
                  onClick={() => openDetails(subscription)}
                  className={cn(
                    'w-full rounded-xl border px-3 py-2 text-left transition',
                    'hover:border-white/25 hover:bg-white/[0.04]',
                    isCurrent
                      ? 'border-emerald-400/35 bg-emerald-500/[0.08]'
                      : 'border-white/10 bg-white/[0.02]'
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-100">
                        {typeMeta.emoji} {t(typeMeta.labelKey)} - {subscription.plan.name}
                      </p>
                      <p className="truncate text-xs text-slate-400">
                        {t(status.labelKey)} · {t('devices.metrics.devices')} {formatCount(count)} / {formatLimitLabel(limit, t('devices.unlimited'))}
                      </p>
                    </div>
                    <ChevronRight className={cn('h-4 w-4 shrink-0', status.tone)} />
                  </div>
                </button>
              )
            })}
          </CardContent>
        </Card>
      </div>

      {useMobileUiV2 ? (
        <Sheet open={detailsOpen} onOpenChange={closeDetailsPanel}>
          <SheetContent
            side="bottom"
            className="max-h-[calc(100vh-0.75rem)] overflow-y-auto pb-[calc(1rem+var(--app-safe-bottom,0px))]"
          >
            <div className="space-y-4">
              <div className="space-y-1">
                <h2 className="pr-9 text-lg font-semibold text-slate-100">
                  {selectedSubscription ? (
                    <>
                      {DEVICE_TYPE_META[normalizeDeviceType(selectedSubscription.device_type)].emoji}{' '}
                      {t(DEVICE_TYPE_META[normalizeDeviceType(selectedSubscription.device_type)].labelKey)} -{' '}
                      {selectedSubscription.plan.name}
                    </>
                  ) : (
                    t('devices.dialog.titleFallback')
                  )}
                </h2>
                <p className="text-sm text-slate-400">{t('devices.dialog.desc')}</p>
              </div>

              {selectedSubscription && (
                <DeviceDetailsContent
                  currentDevicesCountLabel={currentDevicesCountLabel}
                  devicesData={devicesData}
                  devicesLoading={devicesLoading}
                  selectedSubscription={selectedSubscription}
                  assignmentDeviceType={assignmentDeviceType}
                  setAssignmentDeviceType={setAssignmentDeviceType}
                  saveAssignment={saveAssignment}
                  assignmentPending={assignmentMutation.isPending}
                  assignmentDirty={hasAssignmentChanges}
                  connectBySubscriptionLink={connectBySubscriptionLink}
                  copyText={copyText}
                  regenerateLink={regenerateLink}
                  regeneratePending={generateMutation.isPending}
                  generatedLink={generatedLink}
                  deviceToDelete={deviceToDelete}
                  mutationsDisabled={isReadOnlyAccess}
                  onDelete={(hwid) => {
                    if (isReadOnlyAccess) {
                      toast.error(t('devices.readOnlyNotice'))
                      return
                    }
                    if (deviceToDelete === hwid && selectedSubscription) {
                      revokeMutation.mutate({ hwid, subscription_id: selectedSubscription.id })
                      return
                    }
                    setDeviceToDelete(hwid)
                  }}
                  compact
                />
              )}

              <div className="flex justify-end">
                <Button variant="outline" className="h-11 min-w-[116px]" onClick={() => setDetailsOpen(false)}>
                  {t('common.close')}
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
      ) : (
        <Dialog open={detailsOpen} onOpenChange={closeDetailsPanel}>
          <DialogContent className="max-h-[90vh] sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle>
                {selectedSubscription ? (
                  <>
                    {DEVICE_TYPE_META[normalizeDeviceType(selectedSubscription.device_type)].emoji}{' '}
                    {t(DEVICE_TYPE_META[normalizeDeviceType(selectedSubscription.device_type)].labelKey)} -{' '}
                    {selectedSubscription.plan.name}
                  </>
                ) : (
                  t('devices.dialog.titleFallback')
                )}
              </DialogTitle>
              <DialogDescription>
                {t('devices.dialog.desc')}
              </DialogDescription>
            </DialogHeader>

            {selectedSubscription && (
              <DeviceDetailsContent
                currentDevicesCountLabel={currentDevicesCountLabel}
                devicesData={devicesData}
                devicesLoading={devicesLoading}
                selectedSubscription={selectedSubscription}
                assignmentDeviceType={assignmentDeviceType}
                setAssignmentDeviceType={setAssignmentDeviceType}
                saveAssignment={saveAssignment}
                assignmentPending={assignmentMutation.isPending}
                assignmentDirty={hasAssignmentChanges}
                connectBySubscriptionLink={connectBySubscriptionLink}
                copyText={copyText}
                regenerateLink={regenerateLink}
                regeneratePending={generateMutation.isPending}
                generatedLink={generatedLink}
                deviceToDelete={deviceToDelete}
                mutationsDisabled={isReadOnlyAccess}
                onDelete={(hwid) => {
                  if (isReadOnlyAccess) {
                    toast.error(t('devices.readOnlyNotice'))
                    return
                  }
                  if (deviceToDelete === hwid && selectedSubscription) {
                    revokeMutation.mutate({ hwid, subscription_id: selectedSubscription.id })
                    return
                  }
                  setDeviceToDelete(hwid)
                }}
                compact={false}
              />
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => setDetailsOpen(false)}>
                {t('common.close')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}

function DeviceDetailsContent({
  currentDevicesCountLabel,
  devicesData,
  devicesLoading,
  selectedSubscription,
  assignmentDeviceType,
  setAssignmentDeviceType,
  saveAssignment,
  assignmentPending,
  assignmentDirty,
  connectBySubscriptionLink,
  copyText,
  regenerateLink,
  regeneratePending,
  generatedLink,
  deviceToDelete,
  mutationsDisabled,
  onDelete,
  compact,
}: {
  currentDevicesCountLabel: string
  devicesData: DeviceListResponse | undefined
  devicesLoading: boolean
  selectedSubscription: Subscription
  assignmentDeviceType: DeviceType
  setAssignmentDeviceType: (value: DeviceType) => void
  saveAssignment: () => void
  assignmentPending: boolean
  assignmentDirty: boolean
  connectBySubscriptionLink: () => void
  copyText: (value: string, message: string) => Promise<void>
  regenerateLink: () => void
  regeneratePending: boolean
  generatedLink: string | null
  deviceToDelete: string | null
  mutationsDisabled: boolean
  onDelete: (hwid: string) => void
  compact: boolean
}) {
  const { t } = useI18n()

  return (
    <div className="space-y-4">
      <div className={cn('grid gap-2', compact ? 'grid-cols-2' : 'sm:grid-cols-4')}>
        <MiniMetric
          label={t('devices.metrics.status')}
          value={t(STATUS_META[selectedSubscription.status].labelKey)}
          toneClass={STATUS_META[selectedSubscription.status].tone}
          compact={compact}
        />
        <MiniMetric
          label={t('devices.metrics.plan')}
          value={selectedSubscription.plan.name}
          toneClass="text-slate-100"
          compact={compact}
        />
        <MiniMetric
          label={t('devices.metrics.devices')}
          value={`${currentDevicesCountLabel} / ${formatLimitLabel(
            devicesData?.device_limit ?? selectedSubscription.device_limit,
            t('devices.unlimited')
          )}`}
          toneClass="text-slate-100"
          compact={compact}
        />
        <MiniMetric
          label={t('devices.metrics.expires')}
          value={formatRelativeTime(selectedSubscription.expire_at)}
          toneClass="text-slate-100"
          compact={compact}
        />
      </div>

      <div className={cn('gap-2', compact ? 'grid grid-cols-1' : 'flex flex-wrap')}>
        <Button
          size="sm"
          variant="outline"
          className={cn(
            'border-white/15 bg-white/5 text-slate-100 hover:bg-white/10',
            compact ? 'h-11 w-full justify-start' : ''
          )}
          onClick={connectBySubscriptionLink}
        >
          <ExternalLink className="mr-1.5 h-4 w-4" />
          {t('devices.actions.connect')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className={cn(
            'border-white/15 bg-white/5 text-slate-100 hover:bg-white/10',
            compact ? 'h-11 w-full justify-start' : ''
          )}
          onClick={() => copyText(selectedSubscription.url, t('devices.toast.connectionLinkCopied'))}
        >
          <Copy className="mr-1.5 h-4 w-4" />
          {t('devices.actions.copyLink')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className={cn(
            'border-white/15 bg-white/5 text-slate-100 hover:bg-white/10',
            compact ? 'h-11 w-full justify-start' : ''
          )}
          onClick={regenerateLink}
          disabled={mutationsDisabled || regeneratePending}
        >
          <RefreshCw className="mr-1.5 h-4 w-4" />
          {regeneratePending ? t('devices.actions.regenerating') : t('devices.actions.regenerateLink')}
        </Button>
      </div>

      {generatedLink && (
        <div className={cn('rounded-lg border border-white/10 bg-white/[0.03]', compact ? 'p-2.5' : 'p-3')}>
          <p className="mb-2 text-xs text-slate-400">{t('devices.generatedLink')}</p>
          <div className={cn('gap-2', compact ? 'grid grid-cols-1' : 'flex')}>
            <input
              type="text"
              readOnly
              value={generatedLink}
              className="min-w-0 flex-1 break-all rounded-md border border-white/15 bg-black/20 px-2 py-1.5 font-mono text-xs text-slate-100"
            />
            <Button
              size="sm"
              variant="outline"
              className={cn(compact ? 'h-11 w-full' : '')}
              onClick={() => copyText(generatedLink, t('devices.toast.generatedLinkCopied'))}
            >
              <Copy className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      <div className={cn('rounded-lg border border-white/10 bg-white/[0.02]', compact ? 'p-2.5' : 'p-3')}>
        <p className="mb-2 text-sm font-medium">{t('devices.assignment.title')}</p>
        <div className="space-y-1">
          <p className="text-xs text-slate-400">{t('devices.assignment.deviceType')}</p>
          <Select
            value={assignmentDeviceType}
            onValueChange={(value) => setAssignmentDeviceType(value as DeviceType)}
            disabled={mutationsDisabled}
          >
            <SelectTrigger className={cn(compact ? 'h-11' : '')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(DEVICE_TYPE_META).map(([value, meta]) => (
                <SelectItem key={value} value={value}>
                  {meta.emoji} {t(meta.labelKey)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="mt-3 flex justify-end">
          <Button
            size="sm"
            className={cn(compact ? 'h-11 px-5' : '')}
            onClick={saveAssignment}
            disabled={mutationsDisabled || assignmentPending || !assignmentDirty}
          >
            {assignmentPending ? t('devices.assignment.saving') : t('devices.assignment.save')}
          </Button>
        </div>
      </div>

      <div className={cn('rounded-lg border border-white/10 bg-white/[0.02]', compact ? 'p-2.5' : 'p-3')}>
        <p className="mb-2 text-sm font-medium">{t('devices.connected.title')}</p>
        {devicesLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <DeviceRows
            devices={devicesData?.devices || []}
            deletingHwid={deviceToDelete}
            mutationsDisabled={mutationsDisabled}
            onDelete={onDelete}
            compact={compact}
          />
        )}
      </div>
    </div>
  )
}

function MiniMetric({
  label,
  value,
  toneClass,
  compact = false,
}: {
  label: string
  value: string
  toneClass: string
  compact?: boolean
}) {
  return (
    <div className={cn('rounded-lg border border-white/10 bg-white/[0.03]', compact ? 'px-2 py-1.5' : 'px-2.5 py-2')}>
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className={cn('min-w-0 truncate font-medium', compact ? 'text-[13px]' : 'text-sm', toneClass)}>{value}</p>
    </div>
  )
}

function DeviceRows({
  devices,
  deletingHwid,
  mutationsDisabled,
  onDelete,
  compact = false,
}: {
  devices: Device[]
  deletingHwid: string | null
  mutationsDisabled: boolean
  onDelete: (hwid: string) => void
  compact?: boolean
}) {
  const { t } = useI18n()
  if (!devices.length) {
    return (
      <div className="rounded-md border border-dashed border-white/10 py-6 text-center text-sm text-slate-400">
        {t('devices.connected.empty')}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {devices.map((device) => (
        <div
          key={device.hwid}
          className={cn(
            'rounded-md border border-white/10 bg-white/[0.02]',
            compact
              ? 'grid grid-cols-[1fr_auto] gap-2 px-2.5 py-2'
              : 'flex items-center justify-between gap-2 px-2.5 py-2'
          )}
        >
          <div className="min-w-0">
            <p className={cn('min-w-0 text-xs font-medium text-slate-100', compact ? 'break-all' : 'truncate')}>
              {device.hwid}
            </p>
            <p className={cn('text-[11px] text-slate-400', compact ? 'break-words' : 'truncate')}>
              {t(DEVICE_TYPE_META[normalizeDeviceType(device.device_type)].labelKey)} · {device.country || t('devices.connected.unknownCountry')} ·{' '}
              {device.last_connected ? formatRelativeTime(device.last_connected) : t('devices.connected.never')}
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              compact ? 'h-11 min-w-[44px] px-3 text-xs' : 'h-7 px-2 text-xs',
              deletingHwid === device.hwid
                ? 'text-destructive hover:bg-red-500/10'
                : 'text-slate-400 hover:bg-white/10 hover:text-slate-100'
            )}
            onClick={() => onDelete(device.hwid)}
            disabled={mutationsDisabled}
          >
            <Trash2 className={cn(compact ? 'h-4 w-4' : 'mr-1 h-3.5 w-3.5')} />
            {!compact && (deletingHwid === device.hwid ? t('common.confirm') : t('devices.connected.revoke'))}
          </Button>
        </div>
      ))}
    </div>
  )
}

function DevicesSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-9 w-52" />
          <Skeleton className="h-4 w-80" />
        </div>
        <Skeleton className="h-6 w-36" />
      </div>
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent className="space-y-2">
          {[1, 2, 3, 4].map((skeletonId) => (
            <Skeleton key={skeletonId} className="h-12 w-full rounded-xl" />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
