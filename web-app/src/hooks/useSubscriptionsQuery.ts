import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useDocumentVisibility } from '@/hooks/useDocumentVisibility'
import { buildVisiblePollingQueryOptions } from '@/lib/query-defaults'
import type { Subscription } from '@/types'

function normalizeSubscriptions(value: unknown): Subscription[] {
  if (Array.isArray(value)) {
    return value as Subscription[]
  }

  if (value && typeof value === 'object' && Array.isArray((value as { subscriptions?: unknown }).subscriptions)) {
    return (value as { subscriptions: Subscription[] }).subscriptions
  }

  return []
}

export function useSubscriptionsQuery(options?: {
  enabled?: boolean
  pollWhenVisible?: boolean
}): UseQueryResult<Subscription[], Error> {
  const enabled = options?.enabled ?? true
  const pollWhenVisible = options?.pollWhenVisible ?? false
  const isDocumentVisible = useDocumentVisibility()

  return useQuery<unknown, Error, Subscription[]>({
    queryKey: ['subscriptions'],
    queryFn: async () => {
      const response = await api.subscription.list()
      return response.data
    },
    select: normalizeSubscriptions,
    ...buildVisiblePollingQueryOptions({
      enabled,
      active: pollWhenVisible && isDocumentVisible,
      staleTime: 10_000,
      refetchOnWindowFocus: true,
    }),
  })
}
