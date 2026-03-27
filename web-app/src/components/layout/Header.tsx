import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/components/auth/AuthProvider'
import { useBranding } from '@/components/common/BrandingProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { LifeBuoy, LogOut, Settings, Shield } from 'lucide-react'
import { cn } from '@/lib/utils'
import { NotificationCenterDialog } from './NotificationCenterDialog'

function resolveSupportUrl(rawValue: string | null | undefined): string | null {
  const trimmed = String(rawValue || '').trim()
  if (!trimmed) {
    return null
  }

  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    return trimmed
  }

  return `https://t.me/${trimmed.replace(/^@+/, '')}`
}

interface HeaderProps {
  forceMobileShell?: boolean
}

export function Header({ forceMobileShell = false }: HeaderProps) {
  const { user, logout } = useAuth()
  const { projectName, supportUrl: brandingSupportUrl } = useBranding()
  const { t } = useI18n()
  const navigate = useNavigate()
  const rawDisplayName = user?.name ?? user?.username ?? 'User'
  const displayName = String(rawDisplayName || 'User')
  const rawDisplayUsername = user?.username ?? `id${user?.telegram_id ?? ''}`
  const displayUsername = String(rawDisplayUsername || 'id')
  const avatarFallback = displayName.trim().charAt(0).toUpperCase() || 'U'
  const personalDiscount = Math.max(0, Math.min(999, Math.round(Number(user?.personal_discount ?? 0))))
  const purchaseDiscount = Math.max(0, Math.min(999, Math.round(Number(user?.purchase_discount ?? 0))))
  const hasPersonalDiscount = Number.isFinite(personalDiscount) && personalDiscount > 0
  const hasPurchaseDiscount = Number.isFinite(purchaseDiscount) && purchaseDiscount > 0
  const fallbackSupportUrl = resolveSupportUrl(
    import.meta.env.VITE_SUPPORT_URL || import.meta.env.VITE_SUPPORT_USERNAME || null
  )
  const supportUrl = resolveSupportUrl(brandingSupportUrl) || fallbackSupportUrl
  const mobileLayoutVisibility = forceMobileShell ? 'flex' : 'flex lg:hidden'
  const desktopLayoutVisibility = forceMobileShell ? 'hidden' : 'hidden lg:flex'

  return (
    <header className="sticky top-0 z-50 w-full bg-[#050608]/84 backdrop-blur-xl">
      <div className="pt-[var(--app-safe-top)]">
        <div className="mx-auto max-w-[1480px] px-4 md:px-6 lg:px-6">
          <div className={cn('h-[72px] items-center gap-2', mobileLayoutVisibility)}>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <Link
                to="/dashboard"
                className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-2.5 py-1.5"
              >
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-primary/20 bg-primary/12 text-primary">
                  <Shield className="h-4 w-4" />
                </span>
                <span className="truncate text-xs font-semibold tracking-[0.12em] text-slate-200">
                  {projectName}
                </span>
              </Link>

              <div className="shrink-0">
                <NotificationCenterDialog />
              </div>
            </div>

            {supportUrl ? (
              <Button
                asChild
                variant="ghost"
                className="relative h-10 w-10 shrink-0 rounded-full border border-white/12 bg-white/[0.03] p-0 hover:bg-white/[0.08]"
                aria-label={t('header.support')}
              >
                <a href={supportUrl} target="_blank" rel="noopener noreferrer">
                  <LifeBuoy className="h-4 w-4 text-slate-200" />
                </a>
              </Button>
            ) : null}
          </div>

          <div className={cn('h-[72px] items-center justify-between gap-2', desktopLayoutVisibility)}>
            <Link
              to="/dashboard"
              className="mr-auto flex items-center gap-3"
            >
              <span className="grid h-9 w-9 place-items-center rounded-xl border border-primary/20 bg-primary/12 text-primary">
                <Shield className="h-4 w-4" />
              </span>
              <span>
                <span className="block text-[11px] uppercase tracking-[0.2em] text-slate-500">{t('layout.workspace')}</span>
                <span className="block text-sm font-semibold tracking-wide text-slate-100">{projectName}</span>
              </span>
            </Link>

            <div className="flex items-center justify-end gap-2">
              {hasPurchaseDiscount && (
                <>
                  <div className="flex h-8 max-w-[112px] items-center justify-center gap-1.5 rounded-full border border-violet-300/25 bg-violet-500/15 px-2 text-[10px] font-medium text-violet-100 md:hidden">
                    <span className="h-2 w-2 shrink-0 rounded-full bg-violet-300" />
                    <span className="truncate whitespace-nowrap">{t('header.nextDiscountCompact', { value: purchaseDiscount })}</span>
                  </div>
                  <div className="hidden h-8 max-w-[136px] items-center justify-center gap-2 rounded-full border border-violet-300/25 bg-violet-500/15 px-3 text-xs font-medium text-violet-100 md:flex">
                    <span className="h-2 w-2 shrink-0 rounded-full bg-violet-300" />
                    <span className="truncate whitespace-nowrap">{t('header.nextDiscount', { value: purchaseDiscount })}</span>
                  </div>
                </>
              )}

              {hasPersonalDiscount && (
                <>
                  <div className="flex h-8 max-w-[112px] items-center justify-center gap-1.5 rounded-full border border-fuchsia-300/25 bg-fuchsia-500/15 px-2 text-[10px] font-medium text-fuchsia-100 md:hidden">
                    <span className="h-2 w-2 shrink-0 rounded-full bg-fuchsia-300" />
                    <span className="truncate whitespace-nowrap">{t('header.personalDiscountCompact', { value: personalDiscount })}</span>
                  </div>
                  <div className="hidden h-8 max-w-[136px] items-center justify-center gap-2 rounded-full border border-fuchsia-300/25 bg-fuchsia-500/15 px-3 text-xs font-medium text-fuchsia-100 md:flex">
                    <span className="h-2 w-2 shrink-0 rounded-full bg-fuchsia-300" />
                    <span className="truncate whitespace-nowrap">{t('header.personalDiscount', { value: personalDiscount })}</span>
                  </div>
                </>
              )}

              <div className="hidden h-8 items-center justify-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-400/12 px-3 text-xs font-medium text-emerald-200 md:flex">
                <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-300" />
                <span className="whitespace-nowrap">{t('header.synced')}</span>
              </div>

              <NotificationCenterDialog />
              {supportUrl ? (
                <Button
                  asChild
                  variant="ghost"
                  className="relative h-10 w-10 rounded-full border border-white/12 bg-white/[0.03] p-0 hover:bg-white/[0.08]"
                  aria-label={t('header.support')}
                >
                  <a href={supportUrl} target="_blank" rel="noopener noreferrer">
                    <LifeBuoy className="h-4 w-4 text-slate-200" />
                  </a>
                </Button>
              ) : null}

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    className="relative h-10 w-10 rounded-full border border-white/12 bg-white/[0.03] p-0 hover:bg-white/[0.08]"
                    aria-label={t('header.profileMenu')}
                    title={t('header.profileMenu')}
                  >
                    <Avatar className="h-10 w-10">
                      <AvatarImage src={user?.photo_url || undefined} alt={displayName} />
                      <AvatarFallback className="bg-primary/16 text-primary">
                        {avatarFallback}
                      </AvatarFallback>
                    </Avatar>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="w-56" align="end" forceMount>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium leading-none">{displayName}</p>
                      <p className="text-xs leading-none text-slate-400">
                        @{displayUsername}
                      </p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-white/10" />
                  <DropdownMenuItem
                    className="cursor-pointer text-slate-100"
                    onClick={() => navigate('/dashboard/settings')}
                  >
                    <Settings className="mr-2 h-4 w-4" />
                    {t('nav.settings')}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-white/10" />
                  <DropdownMenuItem
                    className="cursor-pointer text-red-300 focus:bg-red-500/15 focus:text-red-200"
                    onClick={logout}
                  >
                    <LogOut className="mr-2 h-4 w-4" />
                    {t('header.logout')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
