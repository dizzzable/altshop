import * as React from 'react'
import * as SheetPrimitive from '@radix-ui/react-dialog'
import { cva, type VariantProps } from 'class-variance-authority'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { translate } from '@/i18n/runtime'

const Sheet = SheetPrimitive.Root
const SheetPortal = SheetPrimitive.Portal

function getCloseLabel(): string {
  return translate('common.close')
}

const SheetOverlay = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof SheetPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <SheetPrimitive.Overlay
    className={cn(
      'fixed inset-0 z-50 bg-black/82 backdrop-blur-[4px] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      className
    )}
    {...props}
    ref={ref}
  />
))
SheetOverlay.displayName = SheetPrimitive.Overlay.displayName

const sheetVariants = cva(
  'fixed z-50 gap-4 overflow-y-auto overscroll-y-contain border-white/10 bg-[linear-gradient(180deg,rgba(11,13,17,0.98)_0%,rgba(5,7,10,0.99)_100%)] p-5 text-foreground shadow-[0_36px_90px_-48px_rgba(0,0,0,1)] transition ease-in-out [-webkit-overflow-scrolling:touch] [touch-action:pan-y] sm:p-6 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-300 data-[state=open]:duration-500',
  {
    variants: {
      side: {
        top: 'inset-x-2 top-2 max-h-[calc(100vh-1rem)] rounded-2xl border-b data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top',
        bottom:
          'inset-x-2 bottom-2 max-h-[calc(100vh-1rem)] rounded-2xl border-t data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
        left:
          'inset-y-2 left-2 h-[calc(100%-1rem)] w-[calc(100%-1rem)] rounded-2xl border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:w-3/4 sm:max-w-sm',
        right:
          'inset-y-2 right-2 h-[calc(100%-1rem)] w-[calc(100%-1rem)] rounded-2xl border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right sm:w-3/4 sm:max-w-sm',
      },
    },
    defaultVariants: {
      side: 'right',
    },
  }
)

interface SheetContentProps
  extends React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content>,
    VariantProps<typeof sheetVariants> {}

const SheetContent = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Content>,
  SheetContentProps
>(({ side = 'right', className, children, ...props }, ref) => (
  <SheetPortal>
    <SheetOverlay />
    <SheetPrimitive.Content ref={ref} className={cn(sheetVariants({ side }), className)} {...props}>
      {children}
      <SheetPrimitive.Close className="absolute right-4 top-4 rounded-md border border-white/10 bg-white/[0.02] p-1.5 text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground focus:outline-none focus:ring-2 focus:ring-primary/60 disabled:pointer-events-none">
        <X className="h-4 w-4" />
        <span className="sr-only">{getCloseLabel()}</span>
      </SheetPrimitive.Close>
    </SheetPrimitive.Content>
  </SheetPortal>
))
SheetContent.displayName = SheetPrimitive.Content.displayName

const SheetHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-col gap-1.5 text-left', className)} {...props} />
)
SheetHeader.displayName = 'SheetHeader'

const SheetTitle = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof SheetPrimitive.Title>
>(({ className, ...props }, ref) => (
  <SheetPrimitive.Title
    ref={ref}
    className={cn('text-lg font-semibold text-foreground', className)}
    {...props}
  />
))
SheetTitle.displayName = SheetPrimitive.Title.displayName

const SheetDescription = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof SheetPrimitive.Description>
>(({ className, ...props }, ref) => (
  <SheetPrimitive.Description
    ref={ref}
    className={cn('text-sm text-muted-foreground', className)}
    {...props}
  />
))
SheetDescription.displayName = SheetPrimitive.Description.displayName

export {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
}
