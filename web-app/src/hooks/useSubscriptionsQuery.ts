import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useAdaptivePollingInterval } from '@/hooks/useAdaptivePollingInterval'
import { queryKeys } from '@/lib/query-keys'
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
  const refetchInterval = useAdaptivePollingInterval(60_000, {
    enabled: enabled && pollWhenVisible,
    slowIntervalMs: 120_000,
    saveDataIntervalMs: 300_000,
  })

  return useQuery<unknown, Error, Subscription[]>({
    queryKey: queryKeys.subscriptions(),
    queryFn: async () => {
      const response = await api.subscription.list()
      return response.data
    },
    select: normalizeSubscriptions,
    enabled,
    refetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retryDelay: (attemptIndex) => Math.min(1_000 * (2 ** attemptIndex), 300_000),
    staleTime: 10_000,
  })
}
