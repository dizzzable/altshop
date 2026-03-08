import type { DeviceType, PlanType, Subscription } from '@/types'

type TranslateFn = (key: string, params?: Record<string, string | number>) => string

export const DEVICE_TYPE_META: Record<DeviceType, { labelKey: string; emoji: string }> = {
  ANDROID: { labelKey: 'devices.deviceType.android', emoji: '📱' },
  IPHONE: { labelKey: 'devices.deviceType.iphone', emoji: '🍏' },
  WINDOWS: { labelKey: 'devices.deviceType.windows', emoji: '🖥️' },
  MAC: { labelKey: 'devices.deviceType.mac', emoji: '💻' },
  OTHER: { labelKey: 'devices.deviceType.other', emoji: '🛩️' },
}

export function normalizeDeviceType(value: DeviceType | null | string | undefined): DeviceType {
  if (!value) {
    return 'OTHER'
  }

  return ['ANDROID', 'IPHONE', 'WINDOWS', 'MAC', 'OTHER'].includes(value)
    ? (value as DeviceType)
    : 'OTHER'
}

export function getDeviceTypeMeta(value: DeviceType | null | string | undefined) {
  return DEVICE_TYPE_META[normalizeDeviceType(value)]
}

export function formatPlanTypeLabel(
  type: PlanType | string | null | undefined,
  t: TranslateFn
): string {
  switch (type) {
    case 'TRAFFIC':
      return t('subscription.planType.traffic')
    case 'DEVICES':
      return t('subscription.planType.devices')
    case 'BOTH':
      return t('subscription.planType.both')
    case 'UNLIMITED':
      return t('subscription.planType.unlimited')
    default:
      return String(type || '')
  }
}

export function formatLimitLabel(value: number, unlimitedLabel: string): string {
  return value <= 0 ? unlimitedLabel : String(value)
}

export function getSubscriptionDeviceSummary(
  subscription: Pick<Subscription, 'device_type' | 'devices_count' | 'device_limit'>,
  t: TranslateFn
) {
  const meta = getDeviceTypeMeta(subscription.device_type)
  const unlimitedLabel = t('subscription.card.unlimited')
  const limitLabel = formatLimitLabel(subscription.device_limit, unlimitedLabel)
  const label = t(meta.labelKey)
  const countLabel = String(Math.max(subscription.devices_count, 0))

  return {
    ...meta,
    label,
    countLabel,
    limitLabel,
    text: `${meta.emoji} ${label} / ${countLabel} / ${limitLabel}`,
  }
}
