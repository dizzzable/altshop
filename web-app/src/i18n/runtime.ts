import type { WebLocale } from '@/types'
import { dictionaries } from '@/i18n/dictionaries'
import { getRuntimeWebLocale } from '@/lib/locale'

export type TranslationParams = Record<string, string | number>

function applyParams(template: string, params?: TranslationParams): string {
  if (!params) {
    return template
  }

  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_, key) =>
    String(params[key] ?? `{${key}}`)
  )
}

export function translateWithLocale(
  locale: WebLocale,
  key: string,
  params?: TranslationParams
): string {
  const template = dictionaries[locale][key] ?? dictionaries.ru[key] ?? key
  return applyParams(template, params)
}

export function translate(
  key: string,
  params?: TranslationParams,
  locale: WebLocale = getRuntimeWebLocale()
): string {
  return translateWithLocale(locale, key, params)
}
