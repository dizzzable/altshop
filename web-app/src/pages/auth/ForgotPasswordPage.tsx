import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Shield } from 'lucide-react'
import { api } from '@/lib/api'
import { useI18n } from '@/components/common/I18nProvider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export function ForgotPasswordPage() {
  const { t } = useI18n()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setMessage(null)

    if (!username.trim() && !email.trim()) {
      setError(t('auth.forgot.errorRequired'))
      return
    }

    setIsLoading(true)
    try {
      const trimmedUsername = username.trim()
      const trimmedEmail = email.trim()

      const { data } = trimmedEmail
        ? await api.auth.forgotPassword({
          email: trimmedEmail,
        })
        : await api.auth.forgotPasswordByTelegram({
          username: trimmedUsername,
        })

      setMessage(data.message)
    } catch (err: unknown) {
      const errorResponse = err as { response?: { data?: { detail?: string } } }
      setError(errorResponse.response?.data?.detail || t('auth.forgot.errorDefault'))
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
          <CardTitle className="text-2xl font-bold text-foreground">{t('auth.forgot.title')}</CardTitle>
          <CardDescription className="text-muted-foreground">
            {t('auth.forgot.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">{t('auth.forgot.username')}</Label>
              <Input
                id="username"
                placeholder="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isLoading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">{t('auth.forgot.email')}</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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
                  {t('auth.forgot.submitting')}
                </>
              ) : (
                t('auth.forgot.submit')
              )}
            </Button>
          </form>

          <div className="text-center">
            <p className="text-sm text-muted-foreground">
              {t('auth.forgot.backTo')}{' '}
              <Link to="/auth/login" className="font-medium text-primary transition-colors hover:text-primary/80">
                {t('auth.forgot.signIn')}
              </Link>
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              {t('auth.forgot.haveCode')}{' '}
              <Link to="/auth/reset-password" className="text-primary hover:text-primary/80">
                {t('auth.forgot.resetByCode')}
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
