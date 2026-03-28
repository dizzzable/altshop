import type { PaymentGatewayType, PlanPrice, PurchaseChannel } from '@/types'

type GatewayPriceLike = Pick<PlanPrice, 'gateway_type'>

export function prioritizeGatewayPricesForChannel<T extends GatewayPriceLike>({
  gatewayPrices,
  purchaseChannel,
}: {
  gatewayPrices: T[]
  purchaseChannel: PurchaseChannel
}): T[] {
  if (purchaseChannel !== 'TELEGRAM') {
    return gatewayPrices
  }

  const starsGateway = gatewayPrices.find((price) => price.gateway_type === 'TELEGRAM_STARS')
  if (!starsGateway) {
    return gatewayPrices
  }

  return [
    starsGateway,
    ...gatewayPrices.filter((price) => price.gateway_type !== 'TELEGRAM_STARS'),
  ]
}

export function resolveEffectiveGatewayType({
  availableGatewayPrices,
  purchaseChannel,
  selectedGateway,
}: {
  availableGatewayPrices: GatewayPriceLike[]
  purchaseChannel: PurchaseChannel
  selectedGateway?: string
}): PaymentGatewayType | undefined {
  if (
    selectedGateway
    && availableGatewayPrices.some((price) => price.gateway_type === selectedGateway)
  ) {
    return selectedGateway as PaymentGatewayType
  }

  if (purchaseChannel === 'TELEGRAM') {
    const starsGateway = availableGatewayPrices.find(
      (price) => price.gateway_type === 'TELEGRAM_STARS'
    )
    if (starsGateway) {
      return starsGateway.gateway_type
    }
  }

  if (availableGatewayPrices.length === 1) {
    return availableGatewayPrices[0].gateway_type
  }

  return undefined
}
