import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { buildStaticQueryOptions } from '@/lib/query-defaults'
import type { ReferralInfo } from '@/types'

export function useReferralInfoQuery(options?: { enabled?: boolean }): UseQueryResult<ReferralInfo, Error> {
  const enabled = options?.enabled ?? true

  return useQuery<ReferralInfo, Error>({
    queryKey: ['referral-info'],
    queryFn: () => api.referral.info().then((response) => response.data),
    ...buildStaticQueryOptions({
      enabled,
      staleTime: 30_000,
    }),
  })
}
