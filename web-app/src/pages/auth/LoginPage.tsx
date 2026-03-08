import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Shield } from 'lucide-react'
import { api, clearLegacyAuthStorage } from '@/lib/api'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { clearStoredReferralCode } from '@/lib/referral'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { resolvePostLoginPathWithAccess } from '@/lib/post-login-route'

export function LoginPage() {
  const navigate = useNavigate()
  const { refreshUser } = useAuth()
  const { t } = useI18n()
  const { deviceMode } = useTelegramWebApp()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!formData.username || !formData.password) {
      setError(t('auth.login.errorRequired'))
      return
    }

    setIsLoading(true)

    try {
      await api.auth.login({
        username: formData.username,
        password: formData.password,
      })

      clearLegacyAuthStorage()
      sessionStorage.setItem('auth_source', 'password')
      clearStoredReferralCode()
      await refreshUser()
      const nextPath = await resolvePostLoginPathWithAccess(deviceMode, useMobileUiV2)
      navigate(nextPath, { replace: true })
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string; detail?: string } } }
      setError(
        error.response?.data?.detail ||
          error.response?.data?.message ||
          t('auth.login.errorInvalid')
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8">
      <div className="pointer-events-none absolute -top-28 right-[-120px] h-72 w-72 rounded-full bg-[#7f95ac]/22 blur-[110px]" />
      <div className="pointer-events-none absolute -bottom-36 left-[-140px] h-80 w-80 rounded-full bg-[#5b6b7d]/20 blur-[120px]" />

      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/30 bg-primary/12">
            <Shield className="h-8 w-8 text-primary" />
          </div>
          <CardTitle className="text-2xl font-bold text-foreground">{t('auth.login.title')}</CardTitle>
          <CardDescription className="text-muted-foreground">
            {t('auth.login.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div className="space-y-2">
              <Label htmlFor="username">
                {t('auth.login.username')}
              </Label>
              <Input
                id="username"
                name="username"
                type="text"
                placeholder="username"
                value={formData.username}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="password">
                {t('auth.login.password')}
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                value={formData.password}
                onChange={handleChange}
                disabled={isLoading}
              />
              <div className="flex justify-end">
                <Link
                  to="/auth/forgot-password"
                  className="text-xs text-muted-foreground transition-colors hover:text-primary"
                >
                  {t('auth.login.forgot')}
                </Link>
              </div>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>
                  {error}
                </AlertDescription>
              </Alert>
            )}

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {t('auth.login.submitting')}
                </>
              ) : (
                t('auth.login.submit')
              )}
            </Button>
          </form>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/12"></div>
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">{t('auth.login.or')}</span>
            </div>
          </div>

          {/* Register Link */}
          <div className="text-center">
            <p className="text-sm text-muted-foreground">
              {t('auth.login.noAccount')}{' '}
              <Link
                to="/auth/register"
                className="font-medium text-primary transition-colors hover:text-primary/80"
              >
                {t('auth.login.register')}
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
