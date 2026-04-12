export const APP_QUERY_RETRY_ATTEMPTS = 1
export const APP_QUERY_RETRY_DELAY_MS_MAX = 300_000
export const APP_QUERY_REFETCH_INTERVAL_MS = 60_000

export function appQueryRetryDelay(attemptIndex: number) {
  return Math.min(1_000 * (2 ** attemptIndex), APP_QUERY_RETRY_DELAY_MS_MAX)
}

export function buildStaticQueryOptions(options?: {
  enabled?: boolean
  staleTime?: number
  refetchOnWindowFocus?: boolean
}) {
  return {
    enabled: options?.enabled ?? true,
    staleTime: options?.staleTime,
    refetchOnWindowFocus: options?.refetchOnWindowFocus ?? false,
    retryDelay: appQueryRetryDelay,
  }
}

export function buildVisiblePollingQueryOptions(options?: {
  enabled?: boolean
  active?: boolean
  intervalMs?: number
  staleTime?: number
  refetchOnWindowFocus?: boolean
}) {
  const enabled = options?.enabled ?? true
  const active = options?.active ?? true
  const intervalMs = options?.intervalMs ?? APP_QUERY_REFETCH_INTERVAL_MS
  const refetchInterval: number | false = enabled && active ? intervalMs : false

  return {
    enabled,
    refetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: options?.refetchOnWindowFocus ?? true,
    retryDelay: appQueryRetryDelay,
    staleTime: options?.staleTime,
  }
}

export const APP_QUERY_CLIENT_DEFAULT_OPTIONS = {
  queries: {
    retry: APP_QUERY_RETRY_ATTEMPTS,
    refetchOnWindowFocus: false,
    retryDelay: appQueryRetryDelay,
  },
} as const
