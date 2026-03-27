import { useEffect, useMemo, useState } from 'react'
import { useDocumentVisibility } from '@/hooks/useDocumentVisibility'

type EffectiveConnectionType = 'slow-2g' | '2g' | '3g' | '4g'

interface NetworkInformationLike {
  effectiveType?: EffectiveConnectionType
  saveData?: boolean
  addEventListener?: (
    type: string,
    callback: EventListenerOrEventListenerObject | null,
    options?: boolean | AddEventListenerOptions
  ) => void
  removeEventListener?: (
    type: string,
    callback: EventListenerOrEventListenerObject | null,
    options?: boolean | EventListenerOptions
  ) => void
}

interface AdaptivePollingSnapshot {
  hasFocus: boolean
  isOnline: boolean
  effectiveType: EffectiveConnectionType | null
  saveData: boolean
}

interface AdaptivePollingOptions {
  enabled?: boolean
  slowIntervalMs?: number
  saveDataIntervalMs?: number
}

function getNetworkInformation(): NetworkInformationLike | null {
  if (typeof navigator === 'undefined') {
    return null
  }

  const navigatorWithConnection = navigator as Navigator & {
    connection?: NetworkInformationLike
    mozConnection?: NetworkInformationLike
    webkitConnection?: NetworkInformationLike
  }

  return (
    navigatorWithConnection.connection
    ?? navigatorWithConnection.mozConnection
    ?? navigatorWithConnection.webkitConnection
    ?? null
  )
}

function readAdaptivePollingSnapshot(): AdaptivePollingSnapshot {
  const networkInformation = getNetworkInformation()

  return {
    hasFocus: typeof document === 'undefined' ? true : document.hasFocus(),
    isOnline: typeof navigator === 'undefined' ? true : navigator.onLine !== false,
    effectiveType: networkInformation?.effectiveType ?? null,
    saveData: networkInformation?.saveData === true,
  }
}

export function useAdaptivePollingInterval(
  baseIntervalMs: number,
  options?: AdaptivePollingOptions
): number | false {
  const enabled = options?.enabled ?? true
  const isDocumentVisible = useDocumentVisibility()
  const [snapshot, setSnapshot] = useState(readAdaptivePollingSnapshot)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined
    }

    const handleStateChange = () => {
      setSnapshot(readAdaptivePollingSnapshot())
    }

    const networkInformation = getNetworkInformation()

    window.addEventListener('focus', handleStateChange)
    window.addEventListener('blur', handleStateChange)
    window.addEventListener('online', handleStateChange)
    window.addEventListener('offline', handleStateChange)
    networkInformation?.addEventListener?.('change', handleStateChange)

    return () => {
      window.removeEventListener('focus', handleStateChange)
      window.removeEventListener('blur', handleStateChange)
      window.removeEventListener('online', handleStateChange)
      window.removeEventListener('offline', handleStateChange)
      networkInformation?.removeEventListener?.('change', handleStateChange)
    }
  }, [])

  return useMemo(() => {
    if (!enabled || !isDocumentVisible || !snapshot.hasFocus || !snapshot.isOnline) {
      return false
    }

    if (
      snapshot.saveData
      || snapshot.effectiveType === 'slow-2g'
      || snapshot.effectiveType === '2g'
    ) {
      return options?.saveDataIntervalMs ?? baseIntervalMs * 5
    }

    if (snapshot.effectiveType === '3g') {
      return options?.slowIntervalMs ?? baseIntervalMs * 2
    }

    return baseIntervalMs
  }, [
    baseIntervalMs,
    enabled,
    isDocumentVisible,
    options?.saveDataIntervalMs,
    options?.slowIntervalMs,
    snapshot.effectiveType,
    snapshot.hasFocus,
    snapshot.isOnline,
    snapshot.saveData,
  ])
}
