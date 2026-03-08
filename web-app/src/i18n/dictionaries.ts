import type { WebLocale } from '@/types'
import { enDictionary } from '@/i18n/locales/en'
import { ruDictionary } from '@/i18n/locales/ru'

export type Dictionary = Record<string, string>

export const dictionaries: Record<WebLocale, Dictionary> = {
  en: enDictionary,
  ru: ruDictionary,
}
