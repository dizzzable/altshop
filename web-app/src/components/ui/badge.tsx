import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors focus:outline-none focus:ring-2 focus:ring-primary/70 focus:ring-offset-0',
  {
    variants: {
      variant: {
        default: 'border-primary/35 bg-primary/15 text-primary hover:bg-primary/22',
        secondary: 'border-white/15 bg-white/[0.05] text-secondary-foreground hover:bg-white/[0.1]',
        destructive: 'border-red-400/30 bg-red-500/15 text-red-200 hover:bg-red-500/22',
        outline: 'border-white/18 bg-transparent text-foreground',
        warning: 'border-amber-400/35 bg-amber-400/18 text-amber-100 hover:bg-amber-400/26',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge }
