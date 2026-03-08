import type { User, WebLocale } from '@/types'

const LOCALE_STORAGE_KEY = 'web_locale_override'
const FALLBACK_LOCALE: WebLocale = 'ru'

let runtimeLocale: WebLocale = FALLBACK_LOCALE

export function normalizeWebLocale(value: unknown): WebLocale | null {
  if (!value) {
    return null
  }

  const normalized = String(value).trim().toLowerCase()
  if (normalized.startsWith('en')) {
    return 'en'
  }
  if (normalized.startsWith('ru')) {
    return 'ru'
  }
  return null
}

export function normalizeSupportedLocales(locales: unknown): WebLocale[] {
  if (!Array.isArray(locales)) {
    return [FALLBACK_LOCALE]
  }

  const result: WebLocale[] = []
  for (const locale of locales) {
    const normalized = normalizeWebLocale(locale)
    if (normalized && !result.includes(normalized)) {
      result.push(normalized)
    }
  }

  if (!result.length) {
    result.push(FALLBACK_LOCALE)
  }

  return result
}

export function readLocaleOverride(): WebLocale | null {
  try {
    return normalizeWebLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY))
  } catch {
    return null
  }
}

export function writeLocaleOverride(locale: WebLocale | null): void {
  try {
    if (!locale) {
      window.localStorage.removeItem(LOCALE_STORAGE_KEY)
      return
    }
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
  } catch {
    // Ignore storage errors in private mode or restricted environments.
  }
}

export function resolveWebLocale(options: {
  overrideLocale?: WebLocale | null
  user?: User | null
  brandingDefaultLocale?: unknown
  supportedLocales?: unknown
}): WebLocale {
  const supportedLocales = normalizeSupportedLocales(options.supportedLocales)
  const isSupported = (locale: WebLocale | null): locale is WebLocale =>
    Boolean(locale && supportedLocales.includes(locale))

  const overrideLocale = options.overrideLocale ?? readLocaleOverride()
  if (isSupported(overrideLocale)) {
    return overrideLocale
  }

  const userLocale = normalizeWebLocale(options.user?.language)
  if (isSupported(userLocale)) {
    return userLocale
  }

  const brandingDefaultLocale = normalizeWebLocale(options.brandingDefaultLocale)
  if (isSupported(brandingDefaultLocale)) {
    return brandingDefaultLocale
  }

  return supportedLocales[0] ?? FALLBACK_LOCALE
}

export function setRuntimeWebLocale(locale: WebLocale): void {
  runtimeLocale = locale
}

export function getRuntimeWebLocale(): WebLocale {
  return runtimeLocale
}

