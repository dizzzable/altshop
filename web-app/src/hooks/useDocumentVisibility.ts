import { useEffect, useState } from 'react'

function readIsDocumentVisible(): boolean {
  if (typeof document === 'undefined') {
    return true
  }

  return document.visibilityState === 'visible'
}

export function useDocumentVisibility(): boolean {
  const [isVisible, setIsVisible] = useState(readIsDocumentVisible)

  useEffect(() => {
    if (typeof document === 'undefined') {
      return undefined
    }

    const handleVisibilityChange = () => {
      setIsVisible(readIsDocumentVisible())
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  return isVisible
}
