import * as React from 'react'
import { cn } from '@/lib/utils'

type SkeletonProps = React.HTMLAttributes<HTMLDivElement>

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'animate-pulse rounded-md bg-[linear-gradient(100deg,rgba(255,255,255,0.03),rgba(255,255,255,0.12),rgba(255,255,255,0.03))]',
        className
      )}
      {...props}
    />
  )
)
Skeleton.displayName = 'Skeleton'

export { Skeleton }
