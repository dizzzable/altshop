import { Card, CardContent } from '@/components/ui/card'
import { useI18n } from '@/components/common/I18nProvider'
import { useAccessStatusQuery } from '@/hooks/useAccessStatusQuery'
import { resolveAccessCapabilities } from '@/lib/access-capabilities'
import { cn } from '@/lib/utils'
import { CreditCard, Smartphone, Ticket } from 'lucide-react'
import { Link } from 'react-router-dom'

const actions = [
  {
    titleKey: 'quickActions.purchase.title',
    descriptionKey: 'quickActions.purchase.desc',
    href: '/dashboard/subscription/purchase',
    icon: CreditCard,
  },
  {
    titleKey: 'quickActions.devices.title',
    descriptionKey: 'quickActions.devices.desc',
    href: '/dashboard/devices',
    icon: Smartphone,
  },
  {
    titleKey: 'quickActions.promocodes.title',
    descriptionKey: 'quickActions.promocodes.desc',
    href: '/dashboard/promocodes',
    icon: Ticket,
  },
]

export function DashboardQuickActions() {
  const { t } = useI18n()
  const { data: accessStatus } = useAccessStatusQuery()
  const accessCapabilities = resolveAccessCapabilities(accessStatus)

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold text-slate-100">{t('quickActions.title')}</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        {actions.map((action) => {
          const isDisabled =
            action.href === '/dashboard/subscription/purchase' && !accessCapabilities.canPurchase
          const content = (
            <Card
              className={cn(
                'border-white/10 bg-[#0a0d11]/82 transition-all duration-200',
                isDisabled
                  ? 'opacity-65'
                  : 'hover:-translate-y-0.5 hover:border-primary/30 hover:bg-[#0e131a]'
              )}
            >
              <CardContent className="flex items-center gap-3 p-4">
                <span className="grid h-9 w-9 place-items-center rounded-lg border border-white/12 bg-white/[0.03] text-primary">
                  <action.icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-100">{t(action.titleKey)}</p>
                  <p className="truncate text-xs text-slate-400">
                    {isDisabled ? t('quickActions.purchaseDisabled') : t(action.descriptionKey)}
                  </p>
                </div>
                <span className="text-xs font-medium text-slate-400">
                  {isDisabled ? '...' : `${t('common.open')} ->`}
                </span>
              </CardContent>
            </Card>
          )

          if (isDisabled) {
            return <div key={action.href}>{content}</div>
          }

          return (
            <Link key={action.href} to={action.href} className="group block">
              {content}
            </Link>
          )
        })}
      </div>
    </section>
  )
}
