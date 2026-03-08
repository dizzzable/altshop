import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useAuth } from '@/components/auth/AuthProvider'
import { useBranding } from '@/components/common/BrandingProvider'
import { translateWithLocale, type TranslationParams } from '@/i18n/runtime'
import {
  readLocaleOverride,
  resolveWebLocale,
  setRuntimeWebLocale,
  writeLocaleOverride,
} from '@/lib/locale'
import type { WebLocale } from '@/types'

type I18nContextValue = {
  locale: WebLocale
  supportedLocales: WebLocale[]
  setLocaleOverride: (locale: WebLocale) => void
  clearLocaleOverride: () => void
  t: (key: string, params?: TranslationParams) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)
const MANUAL_WEB_LOCALES: WebLocale[] = ['ru', 'en']

export function I18nProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { defaultLocale, supportedLocales: brandingLocales } = useBranding()
  const [overrideLocale, setOverrideLocale] = useState<WebLocale | null>(() => readLocaleOverride())
  const supportedLocales = useMemo(
    () => Array.from(new Set([...brandingLocales, ...MANUAL_WEB_LOCALES])) as WebLocale[],
    [brandingLocales]
  )

  const locale = useMemo(
    () => {
      const resolved = resolveWebLocale({
        overrideLocale,
        user,
        brandingDefaultLocale: defaultLocale,
        supportedLocales,
      })
      setRuntimeWebLocale(resolved)
      return resolved
    },
    [defaultLocale, overrideLocale, supportedLocales, user]
  )

  const setLocaleOverrideHandler = useCallback(
    (nextLocale: WebLocale) => {
      if (!supportedLocales.includes(nextLocale)) {
        return
      }
      writeLocaleOverride(nextLocale)
      setOverrideLocale(nextLocale)
    },
    [supportedLocales]
  )

  const clearLocaleOverrideHandler = useCallback(() => {
    writeLocaleOverride(null)
    setOverrideLocale(null)
  }, [])

  const t = useCallback(
    (key: string, params?: TranslationParams) => translateWithLocale(locale, key, params),
    [locale]
  )

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      supportedLocales,
      setLocaleOverride: setLocaleOverrideHandler,
      clearLocaleOverride: clearLocaleOverrideHandler,
      t,
    }),
    [clearLocaleOverrideHandler, locale, setLocaleOverrideHandler, supportedLocales, t]
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return context
}
