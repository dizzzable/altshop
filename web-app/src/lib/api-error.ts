type ApiErrorWithDetail = {
  response?: {
    data?: {
      detail?: unknown
      message?: unknown
    }
  }
}

export type ApiErrorDetailObject = {
  code?: unknown
  message?: unknown
}

export function getApiErrorDetail(error: unknown): unknown {
  return (error as ApiErrorWithDetail | null | undefined)?.response?.data?.detail
}

export function getApiErrorDetailObject(error: unknown): ApiErrorDetailObject | null {
  const detail = getApiErrorDetail(error)
  if (!detail || typeof detail !== 'object') {
    return null
  }

  return detail as ApiErrorDetailObject
}

export function getApiErrorMessageFromDetail(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.length > 0) {
    return detail
  }

  if (!detail || typeof detail !== 'object') {
    return null
  }

  const message = (detail as ApiErrorDetailObject).message
  return typeof message === 'string' && message.length > 0 ? message : null
}

export function getApiErrorMessage(error: unknown): string | null {
  const detailMessage = getApiErrorMessageFromDetail(getApiErrorDetail(error))
  if (detailMessage) {
    return detailMessage
  }

  const message = (error as ApiErrorWithDetail | null | undefined)?.response?.data?.message
  return typeof message === 'string' && message.length > 0 ? message : null
}
