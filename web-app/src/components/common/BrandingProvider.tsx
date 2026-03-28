import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import { normalizeSupportedLocales, normalizeWebLocale } from '@/lib/locale'
import type { WebLocale } from '@/types'

type BrandingContextValue = {
  projectName: string
  webTitle: string
  defaultLocale: WebLocale
  supportedLocales: WebLocale[]
  supportUrl: string | null
  miniAppUrl: string | null
  miniAppLaunchUrl: string | null
  telegramBotLink: string | null
  isLoaded: boolean
}

const DEFAULT_BRANDING: BrandingContextValue = {
  projectName: 'AltShop',
  webTitle: 'AltShop - VPN Subscription Management',
  defaultLocale: 'ru',
  supportedLocales: ['ru'],
  supportUrl: null,
  miniAppUrl: null,
  miniAppLaunchUrl: null,
  telegramBotLink: null,
  isLoaded: false,
}

const BrandingContext = createContext<BrandingContextValue>(DEFAULT_BRANDING)

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<BrandingContextValue>(DEFAULT_BRANDING)

  useEffect(() => {
    let isMounted = true

    const loadBranding = async () => {
      try {
        const { data } = await api.auth.getBranding()
        if (!isMounted) {
          return
        }
        setBranding({
          projectName: data.project_name || DEFAULT_BRANDING.projectName,
          webTitle: data.web_title || DEFAULT_BRANDING.webTitle,
          defaultLocale: normalizeWebLocale(data.default_locale) || DEFAULT_BRANDING.defaultLocale,
          supportedLocales: normalizeSupportedLocales(data.supported_locales),
          supportUrl: data.support_url?.trim() || null,
          miniAppUrl: data.mini_app_url?.trim() || null,
          miniAppLaunchUrl: data.mini_app_launch_url?.trim() || null,
          telegramBotLink: data.telegram_bot_link?.trim() || null,
          isLoaded: true,
        })
      } catch {
        if (!isMounted) {
          return
        }
        setBranding({
          ...DEFAULT_BRANDING,
          isLoaded: true,
        })
      }
    }

    loadBranding()

    return () => {
      isMounted = false
    }
  }, [])

  useEffect(() => {
    document.title = branding.webTitle
  }, [branding.webTitle])

  const value = useMemo(
    () => ({
      projectName: branding.projectName,
      webTitle: branding.webTitle,
      defaultLocale: branding.defaultLocale,
      supportedLocales: branding.supportedLocales,
      supportUrl: branding.supportUrl,
      miniAppUrl: branding.miniAppUrl,
      miniAppLaunchUrl: branding.miniAppLaunchUrl,
      telegramBotLink: branding.telegramBotLink,
      isLoaded: branding.isLoaded,
    }),
    [
      branding.defaultLocale,
      branding.isLoaded,
      branding.miniAppLaunchUrl,
      branding.miniAppUrl,
      branding.projectName,
      branding.supportedLocales,
      branding.supportUrl,
      branding.telegramBotLink,
      branding.webTitle,
    ]
  )

  return (
    <BrandingContext.Provider value={value}>
      {children}
    </BrandingContext.Provider>
  )
}

export function useBranding() {
  return useContext(BrandingContext)
}
