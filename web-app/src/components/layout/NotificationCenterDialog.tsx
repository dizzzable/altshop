import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { useI18n } from '@/components/common/I18nProvider'
import { useAdaptivePollingInterval } from '@/hooks/useAdaptivePollingInterval'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { api } from '@/lib/api'
import type { UserNotificationItem } from '@/types'

const PAGE_SIZE = 20
const UNREAD_POLL_MS = 60_000

function formatNotificationDateTime(value: string, locale: 'ru' | 'en'): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString(locale === 'ru' ? 'ru-RU' : 'en-US', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatBadgeCount(count: number): string {
  if (count > 99) {
    return '99+'
  }
  return String(count)
}

export function NotificationCenterDialog() {
  const { t, locale } = useI18n()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(1)
  const unreadRefetchInterval = useAdaptivePollingInterval(UNREAD_POLL_MS, {
    enabled: true,
    slowIntervalMs: 120_000,
    saveDataIntervalMs: 300_000,
  })
  const listRefetchInterval = useAdaptivePollingInterval(UNREAD_POLL_MS, {
    enabled: open,
    slowIntervalMs: 120_000,
    saveDataIntervalMs: 180_000,
  })

  const unreadQuery = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => api.notifications.unreadCount().then((response) => response.data),
    enabled: true,
    refetchInterval: unreadRefetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retryDelay: (attemptIndex) => Math.min(1_000 * (2 ** attemptIndex), 300_000),
  })

  const listQuery = useQuery({
    queryKey: ['notifications', 'list', page, PAGE_SIZE],
    queryFn: () => api.notifications.list(page, PAGE_SIZE).then((response) => response.data),
    enabled: open,
    refetchInterval: listRefetchInterval,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retryDelay: (attemptIndex) => Math.min(1_000 * (2 ** attemptIndex), 300_000),
  })

  const markReadMutation = useMutation({
    mutationFn: (notificationId: number) =>
      api.notifications.markRead(notificationId).then((response) => response.data),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] }),
        queryClient.invalidateQueries({ queryKey: ['notifications', 'list'] }),
      ])
    },
  })

  const markAllReadMutation = useMutation({
    mutationFn: () => api.notifications.markAllRead().then((response) => response.data),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] }),
        queryClient.invalidateQueries({ queryKey: ['notifications', 'list'] }),
      ])
    },
  })

  const notifications = useMemo<UserNotificationItem[]>(
    () => listQuery.data?.notifications ?? [],
    [listQuery.data?.notifications]
  )
  const unreadCount = unreadQuery.data?.unread ?? listQuery.data?.unread ?? 0
  const hasUnread = unreadCount > 0
  const total = listQuery.data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)

  const pendingReadNotificationId = markReadMutation.isPending
    ? (markReadMutation.variables as number | undefined)
    : undefined

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)
    if (nextOpen) {
      setPage(1)
      void queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] })
    }
  }

  const handleNotificationClick = (notification: UserNotificationItem) => {
    if (notification.is_read || markReadMutation.isPending) {
      return
    }
    markReadMutation.mutate(notification.id)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          className={`relative h-10 w-10 rounded-full border border-white/12 bg-white/[0.03] p-0 hover:bg-white/[0.08] ${hasUnread ? 'ring-1 ring-primary/30 ring-offset-0' : ''}`}
          aria-label={t('notifications.title')}
        >
          <Bell
            className={`h-4 w-4 text-slate-200 ${hasUnread ? 'animate-pulse' : ''}`}
            style={hasUnread ? { animationDuration: '1.8s' } : undefined}
          />
          {hasUnread ? (
            <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full border border-primary/20 bg-primary px-1 text-[10px] font-semibold leading-5 text-primary-foreground">
              {formatBadgeCount(unreadCount)}
            </span>
          ) : null}
        </Button>
      </DialogTrigger>

      <DialogContent className="max-h-[calc(100vh-1.5rem)] overflow-y-auto overscroll-y-contain [touch-action:pan-y] [-webkit-overflow-scrolling:touch] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t('notifications.title')}</DialogTitle>
          <DialogDescription>{t('notifications.description')}</DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <Badge variant="secondary">
              {t('notifications.total', { total })}
            </Badge>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => markAllReadMutation.mutate()}
              disabled={unreadCount <= 0 || markAllReadMutation.isPending}
            >
              {markAllReadMutation.isPending ? t('common.loading') : t('notifications.markAllRead')}
            </Button>
          </div>

          {listQuery.isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4].map((item) => (
                <div key={item} className="h-24 rounded-xl border border-white/10 bg-white/5" />
              ))}
            </div>
          ) : listQuery.isError ? (
            <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-red-400/20 bg-red-500/10 p-4 text-sm text-red-100">
              <p>{t('notifications.error')}</p>
              <Button type="button" variant="outline" size="sm" onClick={() => listQuery.refetch()}>
                {t('notifications.retry')}
              </Button>
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex h-32 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-sm text-slate-400">
              {t('notifications.empty')}
            </div>
          ) : (
            <div className="space-y-2">
              {notifications.map((notification) => (
                <button
                  key={notification.id}
                  type="button"
                  onClick={() => handleNotificationClick(notification)}
                  className={`w-full rounded-xl border p-3 text-left transition-colors ${
                    notification.is_read
                      ? 'border-white/10 bg-white/[0.03] text-slate-400'
                      : 'border-primary/20 bg-primary/10 text-slate-100 hover:bg-primary/14'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold">{notification.title}</p>
                    {!notification.is_read ? (
                      <span className="inline-flex items-center gap-1 text-xs text-primary">
                        {pendingReadNotificationId === notification.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : null}
                        {t('notifications.markRead')}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm leading-relaxed">{notification.message}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    {formatNotificationDateTime(notification.created_at, locale)}
                  </p>
                </button>
              ))}
            </div>
          )}

          {notifications.length > 0 ? (
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-slate-400">
                {t('notifications.pageOf', { page: currentPage, total: totalPages })}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                  disabled={currentPage <= 1 || listQuery.isFetching}
                >
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  {t('notifications.prev')}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                  disabled={currentPage >= totalPages || listQuery.isFetching}
                >
                  {t('notifications.next')}
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}
