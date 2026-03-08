import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Shield, Check, X } from 'lucide-react'
import { api, clearLegacyAuthStorage } from '@/lib/api'
import { useAuth } from '@/components/auth/AuthProvider'
import { useI18n } from '@/components/common/I18nProvider'
import type { RegistrationAccessRequirements } from '@/types'
import {
  captureReferralCodeFromLocation,
  clearStoredReferralCode,
  getReferralCodeForAuth,
} from '@/lib/referral'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { useMobileTelegramUiV2 } from '@/hooks/useMobileTelegramUiV2'
import { resolvePostLoginPathWithAccess } from '@/lib/post-login-route'

export function RegisterPage() {
  const navigate = useNavigate()
  const { refreshUser } = useAuth()
  const { t } = useI18n()
  const { deviceMode } = useTelegramWebApp()
  const useMobileUiV2 = useMobileTelegramUiV2()
  const [isLoading, setIsLoading] = useState(false)
  const [isRequirementsLoading, setIsRequirementsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [registrationAccess, setRegistrationAccess] = useState<RegistrationAccessRequirements | null>(null)
  const [formData, setFormData] = useState({
    telegram_id: '',
    username: '',
    password: '',
    confirm_password: '',
    accept_rules: false,
    accept_channel_subscription: false,
  })

  useEffect(() => {
    captureReferralCodeFromLocation()
    const loadRegistrationAccess = async () => {
      try {
        const { data } = await api.auth.getRegistrationAccessRequirements()
        setRegistrationAccess(data)
      } catch {
        setRegistrationAccess(null)
      } finally {
        setIsRequirementsLoading(false)
      }
    }

    void loadRegistrationAccess()
  }, [])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, type, checked, value } = e.target
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value,
    })
  }

  const validateForm = (): boolean => {
    if (!formData.username || !formData.password) {
      setError(t('auth.register.errorRequired'))
      return false
    }

    if (formData.password.length < 6) {
      setError(t('auth.register.errorMinLength'))
      return false
    }

    if (formData.password !== formData.confirm_password) {
      setError(t('auth.register.errorNoMatch'))
      return false
    }

    if (formData.telegram_id && !/^\d+$/.test(formData.telegram_id)) {
      setError(t('auth.register.errorTelegramDigits'))
      return false
    }

    if (registrationAccess?.requires_telegram_id && !formData.telegram_id.trim()) {
      setError(t('auth.register.errorTelegramRequired'))
      return false
    }

    if (registrationAccess?.rules_required && !formData.accept_rules) {
      setError(t('auth.register.errorRulesRequired'))
      return false
    }

    if (registrationAccess?.channel_required && !formData.accept_channel_subscription) {
      setError(t('auth.register.errorChannelRequired'))
      return false
    }

    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!validateForm()) return

    setIsLoading(true)

    try {
      await api.auth.register({
        username: formData.username,
        password: formData.password,
        telegram_id: formData.telegram_id ? Number(formData.telegram_id) : undefined,
        referral_code: getReferralCodeForAuth() || undefined,
        accept_rules: formData.accept_rules,
        accept_channel_subscription: formData.accept_channel_subscription,
      })

      clearLegacyAuthStorage()
      sessionStorage.setItem('auth_source', 'password')
      await refreshUser()
      clearStoredReferralCode()
      if (registrationAccess?.requires_telegram_id) {
        const normalizedTelegramId = formData.telegram_id.trim()
        if (normalizedTelegramId) {
          try {
            await api.auth.requestTelegramLinkCode({ telegram_id: Number(normalizedTelegramId) })
          } catch {
            // Best-effort: user can retry from Settings.
          }
        }

        const encodedTelegramId = encodeURIComponent(normalizedTelegramId)
        navigate(`/dashboard/settings?focus=telegram&telegram_id=${encodedTelegramId}`, { replace: true })
      } else {
        const nextPath = await resolvePostLoginPathWithAccess(deviceMode, useMobileUiV2)
        navigate(nextPath, { replace: true })
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string; detail?: string } } }
      const backendDetail = error.response?.data?.detail || error.response?.data?.message || ''
      const normalizedDetail = backendDetail.toLowerCase()
      const isAlreadyLinkedError =
        normalizedDetail.includes('telegram id already registered') ||
        normalizedDetail.includes('please login')
      const isTelegramRequiredError = normalizedDetail.includes('telegram id is required')
      const isRulesRequiredError = normalizedDetail.includes('accept the rules')
      const isChannelRequiredError = normalizedDetail.includes('channel subscription')

      if (isAlreadyLinkedError) {
        setError(t('auth.register.errorLinked'))
      } else if (isTelegramRequiredError) {
        setError(t('auth.register.errorTelegramRequired'))
      } else if (isRulesRequiredError) {
        setError(t('auth.register.errorRulesRequired'))
      } else if (isChannelRequiredError) {
        setError(t('auth.register.errorChannelRequired'))
      } else {
        setError(backendDetail || t('auth.register.errorDefault'))
      }
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      <div className="pointer-events-none absolute -left-28 top-[-130px] h-80 w-80 rounded-full bg-[#7f95ac]/22 blur-[120px]" />
      <div className="pointer-events-none absolute -right-32 bottom-[-140px] h-96 w-96 rounded-full bg-[#5b6b7d]/20 blur-[130px]" />

      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/30 bg-primary/12">
            <Shield className="h-8 w-8 text-primary" />
          </div>
          <CardTitle className="text-2xl font-bold text-foreground">{t('auth.register.title')}</CardTitle>
          <CardDescription className="text-muted-foreground">
            {t('auth.register.description')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Telegram ID */}
            <div className="space-y-2">
              <Label htmlFor="telegram_id">
                {registrationAccess?.requires_telegram_id
                  ? t('auth.register.telegramIdRequired')
                  : t('auth.register.telegramId')}
              </Label>
              <Input
                id="telegram_id"
                name="telegram_id"
                type="text"
                placeholder="123456789"
                value={formData.telegram_id}
                onChange={handleChange}
                disabled={isLoading}
              />
              <p className="text-xs text-muted-foreground">
                {registrationAccess?.requires_telegram_id
                  ? t('auth.register.telegramHintRequired')
                  : t('auth.register.telegramHint')}
              </p>
              {!isRequirementsLoading && registrationAccess?.tg_id_helper_bot_link && (
                <a
                  href={registrationAccess.tg_id_helper_bot_link}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary underline-offset-2 hover:underline"
                >
                  {t('auth.register.telegramIdHowTo')}
                </a>
              )}
            </div>

            {!isRequirementsLoading && registrationAccess && (registrationAccess.rules_required || registrationAccess.channel_required) && (
              <div className="space-y-3 rounded-lg border border-white/12 bg-white/[0.03] p-3">
                <p className="text-xs font-medium uppercase tracking-wide text-foreground">
                  {t('auth.register.accessRequirementsTitle')}
                </p>
                {registrationAccess.rules_required && (
                  <label className="flex items-start gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      name="accept_rules"
                      checked={formData.accept_rules}
                      onChange={handleChange}
                      disabled={isLoading}
                      className="mt-0.5 h-4 w-4 rounded border border-white/20 bg-background"
                    />
                    <span>
                      {t('auth.register.acceptRulesPrefix')}{' '}
                      {registrationAccess.rules_link ? (
                        <a
                          href={registrationAccess.rules_link}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary underline-offset-2 hover:underline"
                        >
                          {t('auth.register.acceptRulesLink')}
                        </a>
                      ) : (
                        t('auth.register.acceptRulesLink')
                      )}
                    </span>
                  </label>
                )}
                {registrationAccess.channel_required && (
                  <label className="flex items-start gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      name="accept_channel_subscription"
                      checked={formData.accept_channel_subscription}
                      onChange={handleChange}
                      disabled={isLoading}
                      className="mt-0.5 h-4 w-4 rounded border border-white/20 bg-background"
                    />
                    <span>
                      {t('auth.register.acceptChannelPrefix')}{' '}
                      {registrationAccess.channel_link ? (
                        <a
                          href={registrationAccess.channel_link}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary underline-offset-2 hover:underline"
                        >
                          {t('auth.register.acceptChannelLink')}
                        </a>
                      ) : (
                        t('auth.register.acceptChannelLink')
                      )}
                    </span>
                  </label>
                )}
                {registrationAccess.requires_telegram_id && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">{t('auth.register.verificationHint')}</p>
                    {registrationAccess.verification_bot_link && (
                      <a
                        href={registrationAccess.verification_bot_link}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-primary underline-offset-2 hover:underline"
                      >
                        {t('auth.register.verificationBotLink')}
                      </a>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Username */}
            <div className="space-y-2">
              <Label htmlFor="username">{t('auth.register.username')}</Label>
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
              <Label htmlFor="password">{t('auth.register.password')}</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="••••••••"
                value={formData.password}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>

            {/* Confirm Password */}
            <div className="space-y-2">
              <Label htmlFor="confirm_password">{t('auth.register.confirmPassword')}</Label>
              <Input
                id="confirm_password"
                name="confirm_password"
                type="password"
                placeholder="••••••••"
                value={formData.confirm_password}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>
                  {error}
                  {error === t('auth.register.errorLinked') && (
                    <span className="ml-2">
                      <Link to="/auth/login" className="underline underline-offset-2">
                        {t('auth.register.gotoLogin')}
                      </Link>
                    </span>
                  )}
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
                  {t('auth.register.submitting')}
                </>
              ) : (
                t('auth.register.submit')
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

          {/* Login Link */}
          <div className="text-center">
            <p className="text-sm text-muted-foreground">
              {t('auth.register.haveAccount')}{' '}
              <Link to="/auth/login" className="font-medium text-primary transition-colors hover:text-primary/80">
                {t('auth.register.signIn')}
              </Link>
            </p>
          </div>

          {/* Requirements */}
          <div className="space-y-2 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">{t('auth.register.passwordReq')}</p>
            <div className="flex items-center gap-2">
              {formData.password.length >= 6 ? (
                <Check className="w-3 h-3 text-emerald-300" />
              ) : (
                <X className="w-3 h-3 text-muted-foreground/60" />
              )}
              {t('auth.register.minLength')}
            </div>
            <div className="flex items-center gap-2">
              {formData.password && formData.password === formData.confirm_password ? (
                <Check className="w-3 h-3 text-emerald-300" />
              ) : (
                <X className="w-3 h-3 text-muted-foreground/60" />
              )}
              {t('auth.register.match')}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}


