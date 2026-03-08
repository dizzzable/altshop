import * as React from 'react'
import { cn } from '@/lib/utils'

type AvatarProps = React.HTMLAttributes<HTMLDivElement>

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full',
        className
      )}
      {...props}
    />
  )
)
Avatar.displayName = 'Avatar'

const AvatarImage = React.forwardRef<HTMLImageElement, React.ImgHTMLAttributes<HTMLImageElement>>(
  ({ className, alt = '', src, onError, ...props }, ref) => {
    const [isError, setIsError] = React.useState(false)

    React.useEffect(() => {
      setIsError(false)
    }, [src])

    if (!src || isError) {
      return null
    }

    return (
      <img
        ref={ref}
        className={cn('aspect-square h-full w-full object-cover', className)}
        alt={alt}
        src={src}
        onError={(event) => {
          setIsError(true)
          onError?.(event)
        }}
        {...props}
      />
    )
  }
)
AvatarImage.displayName = 'AvatarImage'

const AvatarFallback = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex h-full w-full items-center justify-center rounded-full bg-muted',
        className
      )}
      {...props}
    />
  )
)
AvatarFallback.displayName = 'AvatarFallback'

export { Avatar, AvatarImage, AvatarFallback }
