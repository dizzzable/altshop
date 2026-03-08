import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold tracking-[0.01em] ring-offset-transparent transition-all duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50',
  {
    variants: {
      variant: {
        default:
          'bg-[linear-gradient(135deg,#d7e2ec_0%,#aebfce_100%)] text-primary-foreground shadow-[0_14px_34px_-18px_rgba(174,191,206,0.65)] hover:-translate-y-0.5 hover:shadow-[0_20px_42px_-20px_rgba(174,191,206,0.8)] active:translate-y-0',
        destructive:
          'bg-[linear-gradient(135deg,#ff7f93_0%,#f14f6a_100%)] text-destructive-foreground shadow-[0_14px_34px_-18px_rgba(241,79,106,0.9)] hover:-translate-y-0.5',
        outline:
          'border border-white/15 bg-white/[0.03] text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] hover:border-white/25 hover:bg-white/[0.09]',
        secondary: 'bg-secondary/80 text-secondary-foreground hover:bg-secondary',
        ghost: 'text-muted-foreground hover:bg-white/[0.08] hover:text-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-lg px-3',
        lg: 'h-12 rounded-xl px-8 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading = false, asChild = false, children, disabled, ...props }, ref) => {
    const classes = cn(buttonVariants({ variant, size, className }))

    if (asChild) {
      // Radix Slot requires exactly one child element.
      // Loading spinner is only supported in native button mode.
      return (
        <Slot
          className={classes}
          aria-disabled={disabled || loading ? true : undefined}
          data-disabled={disabled || loading ? '' : undefined}
          {...props}
        >
          {children}
        </Slot>
      )
    }

    return (
      <button
        className={classes}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" />}
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'

export { Button }
