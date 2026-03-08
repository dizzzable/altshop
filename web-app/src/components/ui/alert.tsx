import * as React from 'react'
import { cn } from '@/lib/utils'

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'destructive'
}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = 'default', ...props }, ref) => (
    <div
      ref={ref}
      role="alert"
      className={cn(
        'relative w-full rounded-xl border px-4 py-3 text-sm',
        variant === 'default' && 'border-white/12 bg-white/[0.03] text-foreground',
        variant === 'destructive' && 'border-destructive/45 bg-red-500/12 text-red-200',
        className
      )}
      {...props}
    />
  )
)
Alert.displayName = 'Alert'

const AlertDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('text-sm [&_p]:leading-relaxed', className)}
      {...props}
    />
  )
)
AlertDescription.displayName = 'AlertDescription'

export { Alert, AlertDescription }
