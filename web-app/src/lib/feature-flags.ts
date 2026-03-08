function readBooleanEnv(value: unknown, defaultValue: boolean): boolean {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value !== 'string') {
    return defaultValue
  }

  const normalized = value.trim().toLowerCase()
  if (normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on') {
    return true
  }
  if (normalized === '0' || normalized === 'false' || normalized === 'no' || normalized === 'off') {
    return false
  }
  return defaultValue
}

export function isMobileTelegramUiV2Enabled(): boolean {
  return readBooleanEnv(import.meta.env.VITE_MOBILE_TELEGRAM_UI_V2, false)
}
