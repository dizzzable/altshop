import React from 'react'
import { Button } from '@/components/ui/button'
import { dictionaries } from '@/i18n/dictionaries'
import { getRuntimeWebLocale } from '@/lib/locale'

interface AppErrorBoundaryState {
  hasError: boolean
}

export class AppErrorBoundary extends React.Component<
  React.PropsWithChildren,
  AppErrorBoundaryState
> {
  constructor(props: React.PropsWithChildren) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Keep the error visible in browser console for fast diagnostics.
    console.error('UI runtime error:', error, errorInfo)
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    const locale = getRuntimeWebLocale()
    const title = dictionaries[locale]['error.interfaceTitle'] ?? dictionaries.ru['error.interfaceTitle']
    const description = dictionaries[locale]['error.interfaceDesc'] ?? dictionaries.ru['error.interfaceDesc']
    const actionLabel = dictionaries[locale]['error.reload'] ?? dictionaries.ru['error.reload']

    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#0a0d11]/95 p-6 text-center shadow-[0_20px_60px_rgba(3,7,18,0.5)]">
          <h2 className="text-xl font-semibold text-slate-100">{title}</h2>
          <p className="mt-2 text-sm text-slate-400">
            {description}
          </p>
          <Button className="mt-5 w-full" onClick={() => window.location.reload()}>
            {actionLabel}
          </Button>
        </div>
      </div>
    )
  }
}
