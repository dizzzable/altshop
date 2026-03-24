import { createContext, useContext, useEffect, useCallback, useReducer, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { User, TelegramAuthData } from '@/types'
import { api, clearLegacyAuthStorage } from '@/lib/api'
import { withAppBase } from '@/lib/app-path'
import {
  captureReferralCodeFromLocation,
  clearStoredReferralCode,
  getReferralCodeForAuth,
} from '@/lib/referral'
import {
  clearPendingTelegramMiniAppOnboarding,
  setPendingTelegramMiniAppOnboarding,
} from '@/lib/telegram-onboarding'
import {
  consumePendingPaymentReturnStatus,
  resolvePaymentRedirectPath,
} from '@/lib/payment-return'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { resolvePostLoginPathWithAccess } from '@/lib/post-login-route'

const MINIAPP_AUTH_ERROR_KEY = 'miniapp_auth_error'

interface AuthState {
  user: User | null
  isLoading: boolean
}

type AuthAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_USER'; payload: User | null }

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload }
    case 'SET_USER':
      return { ...state, user: action.payload }
    default:
      return state
  }
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: () => void
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, { user: null, isLoading: true })
  const { user, isLoading } = state
  const navigate = useNavigate()
  const location = useLocation()
  const { isInTelegram, isReady: isTelegramReady, initData, deviceMode } = useTelegramWebApp()
  const lastAttemptedInitDataRef = useRef<string | null>(null)
  const isTelegramAutoAuthInFlightRef = useRef(false)
  const isMountedRef = useRef(true)

  const resolvePostLoginPath = useCallback(() => resolvePostLoginPathWithAccess(deviceMode), [deviceMode])

  const loadUserWithRefresh = useCallback(async (): Promise<User | null> => {
    try {
      const { data } = await api.user.me()
      return data
    } catch {
      clearLegacyAuthStorage()
      return null
    }
  }, [])

  useEffect(() => {
    captureReferralCodeFromLocation()
  }, [])

  useEffect(() => {
    let isMounted = true

    const bootstrapAuth = async () => {
      const currentUser = await loadUserWithRefresh()
      if (!isMounted) {
        return
      }

      dispatch({ type: 'SET_USER', payload: currentUser })
      dispatch({ type: 'SET_LOADING', payload: false })
    }

    bootstrapAuth()

    return () => {
      isMounted = false
    }
  }, [loadUserWithRefresh])

  useEffect(() => {
    return () => {
      isMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (isLoading || user) {
      return
    }

    const searchParams = new URLSearchParams(location.search)
    const shouldRunTelegramMiniAppAutoAuth =
      location.pathname === '/miniapp' && searchParams.get('tg_open') === '1'

    if (!shouldRunTelegramMiniAppAutoAuth) {
      if (!isTelegramAutoAuthInFlightRef.current) {
        lastAttemptedInitDataRef.current = null
      }
      return
    }

    if (!isInTelegram || !isTelegramReady || !initData) {
      return
    }

    const attemptKey = `${initData}:${location.pathname}:${location.search}`
    if (lastAttemptedInitDataRef.current === attemptKey || isTelegramAutoAuthInFlightRef.current) {
      return
    }
    lastAttemptedInitDataRef.current = attemptKey
    isTelegramAutoAuthInFlightRef.current = true

    searchParams.delete('tg_open')
    const cleanedSearch = searchParams.toString()
    navigate(
      {
        pathname: location.pathname,
        search: cleanedSearch ? `?${cleanedSearch}` : '',
      },
      { replace: true }
    )

    const authenticateViaTelegramWebApp = async () => {
      dispatch({ type: 'SET_LOADING', payload: true })

      try {
        const { data } = await api.auth.telegram({
          initData,
          referralCode: getReferralCodeForAuth() || undefined,
        })
        clearLegacyAuthStorage()
        const authSource = data.auth_source === 'WEB_TELEGRAM_WEBAPP' ? 'telegram-miniapp' : 'telegram'
        sessionStorage.setItem('auth_source', authSource)
        const shouldStartMiniAppOnboarding =
          data.is_new_user === true && data.auth_source === 'WEB_TELEGRAM_WEBAPP'
        if (shouldStartMiniAppOnboarding) {
          setPendingTelegramMiniAppOnboarding()
        } else {
          clearPendingTelegramMiniAppOnboarding()
        }

        const currentUser = await loadUserWithRefresh()
        if (!isMountedRef.current) {
          return
        }

        dispatch({ type: 'SET_USER', payload: currentUser })
        if (currentUser) {
          clearStoredReferralCode()
          const pendingPaymentStatus = consumePendingPaymentReturnStatus()
          if (pendingPaymentStatus) {
            navigate(resolvePaymentRedirectPath(pendingPaymentStatus), { replace: true })
            return
          }
          const nextPath = await resolvePostLoginPath()
          navigate(nextPath, { replace: true })
        }
      } catch (error) {
        if (!isMountedRef.current) {
          return
        }
        console.error('Telegram Mini App auto-auth failed:', error)
        try {
          window.sessionStorage.setItem(MINIAPP_AUTH_ERROR_KEY, '1')
        } catch {
          // Ignore storage errors in private mode.
        }
        clearLegacyAuthStorage()
        dispatch({ type: 'SET_USER', payload: null })
      } finally {
        isTelegramAutoAuthInFlightRef.current = false
        if (isMountedRef.current) {
          dispatch({ type: 'SET_LOADING', payload: false })
        }
      }
    }

    void authenticateViaTelegramWebApp()
  }, [
    initData,
    isInTelegram,
    isLoading,
    isTelegramReady,
    loadUserWithRefresh,
    location.pathname,
    location.search,
    navigate,
    resolvePostLoginPath,
    user,
  ])

  const login = useCallback(() => {
    window.location.href = withAppBase('/auth/telegram/callback')
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.auth.logout()
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      clearLegacyAuthStorage()
      clearPendingTelegramMiniAppOnboarding()
      sessionStorage.removeItem('auth_source')
      dispatch({ type: 'SET_USER', payload: null })
      dispatch({ type: 'SET_LOADING', payload: false })
      navigate('/auth/login')
    }
  }, [navigate])

  const refreshUser = useCallback(async () => {
    dispatch({ type: 'SET_LOADING', payload: true })
    try {
      const currentUser = await loadUserWithRefresh()
      dispatch({ type: 'SET_USER', payload: currentUser })
    } catch (error) {
      console.error('Failed to refresh user:', error)
      clearLegacyAuthStorage()
      dispatch({ type: 'SET_USER', payload: null })
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false })
    }
  }, [loadUserWithRefresh])

  useEffect(() => {
    const handleAuthCallback = async () => {
      const queryParams = new URLSearchParams(window.location.search)
      const hash = queryParams.get('hash')
      const authCallbackPath = withAppBase('/auth/telegram/callback')
      if (!hash || window.location.pathname !== authCallbackPath) {
        return
      }

      dispatch({ type: 'SET_LOADING', payload: true })

      try {
        const authData: TelegramAuthData = {
          id: Number(queryParams.get('id')),
          first_name: queryParams.get('first_name') || '',
          last_name: queryParams.get('last_name') || undefined,
          username: queryParams.get('username') || undefined,
          photo_url: queryParams.get('photo_url') || undefined,
          auth_date: Number(queryParams.get('auth_date')),
          hash,
        }

        const { data } = await api.auth.telegram({
          ...authData,
          referralCode: getReferralCodeForAuth() || undefined,
        })
        clearLegacyAuthStorage()
        const authSource = data.auth_source === 'WEB_TELEGRAM_WEBAPP' ? 'telegram-miniapp' : 'telegram'
        sessionStorage.setItem('auth_source', authSource)
        const shouldStartMiniAppOnboarding =
          data.is_new_user === true && data.auth_source === 'WEB_TELEGRAM_WEBAPP'
        if (shouldStartMiniAppOnboarding) {
          setPendingTelegramMiniAppOnboarding()
        } else {
          clearPendingTelegramMiniAppOnboarding()
        }

        const currentUser = await loadUserWithRefresh()
        dispatch({ type: 'SET_USER', payload: currentUser })

        if (currentUser) {
          clearStoredReferralCode()
          const pendingPaymentStatus = consumePendingPaymentReturnStatus()
          if (pendingPaymentStatus) {
            navigate(resolvePaymentRedirectPath(pendingPaymentStatus), { replace: true })
            return
          }
          const nextPath = await resolvePostLoginPath()
          navigate(nextPath, { replace: true })
        } else {
          navigate('/auth/login?error=auth_failed')
        }
      } catch (error) {
        console.error('Auth callback error:', error)
        clearLegacyAuthStorage()
        dispatch({ type: 'SET_USER', payload: null })
        navigate('/auth/login?error=auth_failed')
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false })
      }
    }

    handleAuthCallback()
  }, [loadUserWithRefresh, navigate, resolvePostLoginPath])

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
