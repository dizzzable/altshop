const BASE_PATH = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')

export function withAppBase(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  // BASE_PATH can be empty string for root deployments.
  return BASE_PATH ? `${BASE_PATH}${normalizedPath}` : normalizedPath
}

