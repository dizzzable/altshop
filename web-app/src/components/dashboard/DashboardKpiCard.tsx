import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

type KpiTone = 'neutral' | 'success' | 'danger' | 'warning'

interface DashboardKpiCardProps {
  title: string
  value: string
  description: string
  icon: React.ElementType
  loading?: boolean
  error?: boolean
  tone?: KpiTone
  className?: string
}

const toneClassMap: Record<KpiTone, string> = {
  neutral: 'border-white/10 bg-[#0a0d11]/88',
  success: 'border-emerald-300/20 bg-emerald-500/[0.08]',
  danger: 'border-red-300/20 bg-red-500/[0.08]',
  warning: 'border-amber-300/20 bg-amber-500/[0.08]',
}

export function DashboardKpiCard({
  title,
  value,
  description,
  icon: Icon,
  loading,
  error,
  tone = 'neutral',
  className,
}: DashboardKpiCardProps) {
  if (loading) {
    return (
      <Card className="min-h-[152px] border-white/10 bg-[#0a0d11]/88 shadow-[0_10px_28px_-22px_rgba(15,23,42,0.95)]">
        <CardHeader className="space-y-0 p-4 pb-2">
          <div className="flex items-center justify-between gap-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-4" />
          </div>
        </CardHeader>
        <CardContent className="space-y-0.5 p-4 pt-0">
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-3 w-32" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card
      className={cn(
        'min-h-[152px] overflow-hidden shadow-[0_10px_28px_-22px_rgba(15,23,42,0.95)]',
        toneClassMap[tone],
        error && 'border-destructive/40',
        className
      )}
    >
      <CardHeader className="p-4 pb-2">
        <div className="flex min-w-0 items-start justify-between gap-2">
          <CardTitle className="min-w-0 flex-1 whitespace-normal break-words text-[12px] font-medium leading-[1.2] text-slate-300">
            {title}
          </CardTitle>
          <Icon className="h-4 w-4 shrink-0 text-slate-400" />
        </div>
      </CardHeader>
      <CardContent className="min-w-0 space-y-1 p-4 pt-0">
        <p className="break-words text-xl font-semibold leading-[1.1] text-slate-100">{value}</p>
        <p
          className={cn(
            'whitespace-normal break-words text-[10.5px] leading-tight',
            error ? 'text-destructive' : 'text-slate-400'
          )}
        >
          {description}
        </p>
      </CardContent>
    </Card>
  )
}
