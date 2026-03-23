import type { AccessStatus } from '@/types'

export interface AccessCapabilities {
  isBlocked: boolean
  isReadOnly: boolean
  isPurchaseBlocked: boolean
  canViewProductScreens: boolean
  canMutateProduct: boolean
  canPurchase: boolean
  shouldRedirectToAccessScreen: boolean
}

export function resolveAccessCapabilities(
  accessStatus?: AccessStatus | null
): AccessCapabilities {
  if (!accessStatus) {
    return {
      isBlocked: false,
      isReadOnly: false,
      isPurchaseBlocked: false,
      canViewProductScreens: true,
      canMutateProduct: true,
      canPurchase: true,
      shouldRedirectToAccessScreen: false,
    }
  }

  const isBlocked = accessStatus.access_level === 'blocked'
  const isReadOnly = accessStatus.access_level === 'read_only'
  const isPurchaseBlocked = accessStatus.access_mode === 'PURCHASE_BLOCKED'

  return {
    isBlocked,
    isReadOnly,
    isPurchaseBlocked,
    canViewProductScreens: accessStatus.can_view_product_screens ?? !isBlocked,
    canMutateProduct: accessStatus.can_mutate_product ?? (!isBlocked && !isReadOnly),
    canPurchase:
      accessStatus.can_purchase ?? (!isBlocked && !isReadOnly && !isPurchaseBlocked),
    shouldRedirectToAccessScreen:
      accessStatus.should_redirect_to_access_screen ?? isBlocked,
  }
}
