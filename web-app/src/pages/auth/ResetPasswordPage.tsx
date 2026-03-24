import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, Shield } from 'lucide-react'
import { api } from '@/lib/api'
import { useI18n } from '@/components/common/I18nProvider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function ResetPasswordPage() {
  const { t } = useI18n()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token') || ''
  const hasToken = token.length > 0

  const [resetMethod, setResetMethod] = useState<'email' | 'telegram'>('email')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setMessage(null)

    if (!password || password.length < 6) {
      setError(t('auth.reset.errorMinLength'))
      return
    }

    if (password !== confirmPassword) {
      setError(t('auth.reset.errorNoMatch'))
      return
    }

    if (!hasToken) {
      if (resetMethod === 'email' && (!email.trim() || !code.trim())) {
        setError(t('auth.reset.errorEmailCodeRequired'))
        return
      }

      if (resetMethod === 'telegram' && (!username.trim() || !code.trim())) {
        setError(t('auth.reset.errorUsernameCodeRequired'))
        return
      }
    }

    setIsLoading(true)
    try {
      if (hasToken) {
        const { data } = await api.auth.resetPasswordByLink({
          token,
          new_password: password,
        })
        setMessage(data.message)
      } else {
        const { data } = resetMethod === 'email'
          ? await api.auth.resetPasswordByCode({
            email: email.trim(),
            code: code.trim(),
            new_password: password,
          })
          : await api.auth.resetPasswordByTelegramCode({
            username: username.trim(),
            code: code.trim(),
            new_password: password,
          })

        setMessage(data.message)
      }

      window.setTimeout(() => {
        navigate('/auth/login', { replace: true })
      }, 1200)
    } catch (err: unknown) {
      const errorResponse = err as { response?: { data?: { detail?: string } } }
      setError(errorResponse.response?.data?.detail || t('auth.reset.errorDefault'))
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
          <CardTitle className="text-2xl font-bold text-foreground">{t('auth.reset.title')}</CardTitle>
          <CardDescription className="text-muted-foreground">
            {hasToken ? t('auth.reset.descriptionByToken') : t('auth.reset.descriptionByCode')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {!hasToken && (
              <>
                <div className="space-y-2">
                  <Label>{t('auth.reset.methodLabel')}</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant={resetMethod === 'email' ? 'default' : 'outline'}
                      onClick={() => setResetMethod('email')}
                      disabled={isLoading}
                    >
                      {t('auth.reset.methodEmail')}
                    </Button>
                    <Button
                      type="button"
                      variant={resetMethod === 'telegram' ? 'default' : 'outline'}
                      onClick={() => setResetMethod('telegram')}
                      disabled={isLoading}
                    >
                      {t('auth.reset.methodTelegram')}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email-or-username">
                    {resetMethod === 'email' ? t('auth.reset.email') : t('auth.reset.username')}
                  </Label>
                  <Input
                    id="email-or-username"
                    type={resetMethod === 'email' ? 'email' : 'text'}
                    placeholder={
                      resetMethod === 'email'
                        ? t('auth.reset.emailPlaceholder')
                        : t('auth.reset.usernamePlaceholder')
                    }
                    value={resetMethod === 'email' ? email : username}
                    onChange={(e) => (
                      resetMethod === 'email' ? setEmail(e.target.value) : setUsername(e.target.value)
                    )}
                    disabled={isLoading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="code">{t('auth.reset.code')}</Label>
                  <Input
                    id="code"
                    placeholder={t('auth.reset.codePlaceholder')}
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    disabled={isLoading}
                  />
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="password">{t('auth.reset.newPassword')}</Label>
              <Input
                id="password"
                type="password"
                placeholder={t('auth.reset.newPasswordPlaceholder')}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isLoading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm">{t('auth.reset.confirmPassword')}</Label>
              <Input
                id="confirm"
                type="password"
                placeholder={t('auth.reset.confirmPasswordPlaceholder')}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isLoading}
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            {message && (
              <Alert>
                <AlertDescription>{message}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" disabled={isLoading} className="w-full">
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('auth.reset.submitting')}
                </>
              ) : (
                t('auth.reset.submit')
              )}
            </Button>
          </form>

          <div className="text-center">
            <p className="text-sm text-muted-foreground">
              {t('auth.reset.backTo')}{' '}
              <Link to="/auth/login" className="font-medium text-primary transition-colors hover:text-primary/80">
                {t('auth.reset.signIn')}
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

