import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { buildStaticQueryOptions } from '@/lib/query-defaults'
import type { AccessStatus } from '@/types'

export function useAccessStatusQuery(options?: { enabled?: boolean }): UseQueryResult<AccessStatus, Error> {
  const enabled = options?.enabled ?? true

  return useQuery<AccessStatus, Error>({
    queryKey: ['auth-access-status'],
    queryFn: () => api.auth.getAccessStatus().then((response) => response.data),
    ...buildStaticQueryOptions({
      enabled,
      staleTime: 15_000,
      refetchOnWindowFocus: true,
    }),
  })
}
