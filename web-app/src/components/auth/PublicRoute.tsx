import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'

interface PublicRouteProps {
  children: React.ReactNode
}

export function PublicRoute({ children }: PublicRouteProps) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  const from = location.state?.from?.pathname || '/dashboard'

  if (isAuthenticated) {
    return <Navigate to={from} replace />
  }

  return <>{children}</>
}
