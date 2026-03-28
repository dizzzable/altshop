import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useBranding } from '@/components/common/BrandingProvider'
import { useI18n } from '@/components/common/I18nProvider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  buildAbsoluteAppUrl,
  resolvePaymentRedirectPath,
  resolveTelegramPaymentReturnUrl,
  type PaymentReturnStatus,
  type PaymentReturnTarget,
} from '@/lib/payment-return'

function parsePaymentReturnStatus(rawStatus: string | null): PaymentReturnStatus {
  return rawStatus === 'failed' ? 'failed' : 'success'
}

function parsePaymentReturnTarget(rawTarget: string | null): PaymentReturnTarget {
  return rawTarget === 'telegram' ? 'telegram' : 'web'
}

export function PaymentReturnPage() {
  const { t } = useI18n()
  const { isLoaded: isBrandingLoaded, miniAppLaunchUrl, miniAppUrl, telegramBotLink } = useBranding()
  const [searchParams] = useSearchParams()
  const status = parsePaymentReturnStatus(searchParams.get('status'))
  const target = parsePaymentReturnTarget(searchParams.get('target'))

  const redirectUrl = useMemo(() => {
    if (target === 'telegram') {
      if (!isBrandingLoaded) {
        return null
      }
      return resolveTelegramPaymentReturnUrl(status, {
        miniAppLaunchUrl,
        telegramBotLink,
        miniAppUrl,
      })
    }

    return buildAbsoluteAppUrl(resolvePaymentRedirectPath(status))
  }, [isBrandingLoaded, miniAppLaunchUrl, miniAppUrl, status, target, telegramBotLink])

  useEffect(() => {
    if (!redirectUrl) {
      return
    }

    const timeoutId = window.setTimeout(() => {
      window.location.replace(redirectUrl)
    }, 180)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [redirectUrl])

  const handleContinue = () => {
    if (!redirectUrl) {
      return
    }
    window.location.replace(redirectUrl)
  }

  const title =
    status === 'success' ? t('paymentReturn.successTitle') : t('paymentReturn.failedTitle')
  const description =
    target === 'telegram'
      ? t('paymentReturn.telegramDescription')
      : t('paymentReturn.webDescription')
  const buttonLabel =
    target === 'telegram'
      ? t('paymentReturn.openTelegram')
      : t('paymentReturn.openDashboard')

  return (
    <div className="flex min-h-[100svh] items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md border-white/12 bg-card/95 backdrop-blur">
        <CardHeader className="space-y-2">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{t('paymentReturn.redirecting')}</p>
          <Button className="w-full" onClick={handleContinue} disabled={!redirectUrl}>
            {buttonLabel}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
