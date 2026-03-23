import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useI18n } from '@/components/common/I18nProvider'
import { useBranding } from '@/components/common/BrandingProvider'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useTelegramWebApp } from '@/hooks/useTelegramWebApp'
import { sendWebTelemetryEvent } from '@/lib/telemetry'
import {
  Shield,
  Zap,
  Smartphone,
  Globe,
  Headphones,
  Rocket,
  Check,
  ArrowRight,
  Star,
  Lock,
  Users,
  TrendingUp,
} from 'lucide-react'

const features = [
  {
    icon: Zap,
    titleKey: 'landing.feature.instant.title',
    descriptionKey: 'landing.feature.instant.desc',
    accent: 'text-amber-200',
    accentBg: 'bg-amber-300/15',
  },
  {
    icon: Smartphone,
    titleKey: 'landing.feature.devices.title',
    descriptionKey: 'landing.feature.devices.desc',
    accent: 'text-sky-200',
    accentBg: 'bg-sky-300/15',
  },
  {
    icon: Globe,
    titleKey: 'landing.feature.locations.title',
    descriptionKey: 'landing.feature.locations.desc',
    accent: 'text-cyan-200',
    accentBg: 'bg-cyan-300/15',
  },
  {
    icon: Shield,
    titleKey: 'landing.feature.privacy.title',
    descriptionKey: 'landing.feature.privacy.desc',
    accent: 'text-indigo-200',
    accentBg: 'bg-indigo-300/15',
  },
  {
    icon: Headphones,
    titleKey: 'landing.feature.support.title',
    descriptionKey: 'landing.feature.support.desc',
    accent: 'text-pink-200',
    accentBg: 'bg-pink-300/15',
  },
  {
    icon: Rocket,
    titleKey: 'landing.feature.speed.title',
    descriptionKey: 'landing.feature.speed.desc',
    accent: 'text-emerald-200',
    accentBg: 'bg-emerald-300/15',
  },
]

const plans = [
  {
    nameKey: 'landing.plan.start.name',
    durationKey: 'landing.plan.start.duration',
    hintKey: 'landing.plan.start.hint',
    popular: false,
    featureKeys: [
      'landing.plan.start.feature1',
      'landing.plan.start.feature2',
      'landing.plan.start.feature3',
    ],
  },
  {
    nameKey: 'landing.plan.smart.name',
    durationKey: 'landing.plan.smart.duration',
    hintKey: 'landing.plan.smart.hint',
    badgeKey: 'landing.plan.smart.badge',
    popular: true,
    featureKeys: [
      'landing.plan.smart.feature1',
      'landing.plan.smart.feature2',
      'landing.plan.smart.feature3',
    ],
  },
  {
    nameKey: 'landing.plan.ultra.name',
    durationKey: 'landing.plan.ultra.duration',
    hintKey: 'landing.plan.ultra.hint',
    badgeKey: 'landing.plan.ultra.badge',
    popular: false,
    featureKeys: [
      'landing.plan.ultra.feature1',
      'landing.plan.ultra.feature2',
      'landing.plan.ultra.feature3',
    ],
  },
]

const benefits = [
  'landing.benefit.autorenew',
  'landing.benefit.referrals',
  'landing.benefit.promocodes',
  'landing.benefit.devices',
]

export function LandingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useI18n()
  const { projectName } = useBranding()
  const { isReady, isInTelegram, initData, launchContext, deviceMode } = useTelegramWebApp()

  const handleLogin = () => navigate('/auth/login')
  const handleRegister = () => navigate('/auth/register')
  const handleOpenMiniApp = () => {
    sendWebTelemetryEvent({
      event_name: 'web_landing_miniapp_cta_click',
      source_path: location.pathname,
      device_mode: deviceMode,
      is_in_telegram: isInTelegram,
      has_init_data: Boolean(initData),
      start_param: launchContext.startParam || undefined,
      has_query_id: launchContext.hasQueryId,
      chat_type: launchContext.chatType || undefined,
    })
    navigate('/miniapp')
  }

  useEffect(() => {
    if (!isReady || !isInTelegram) {
      return
    }

    sendWebTelemetryEvent({
      event_name: 'web_landing_view_in_telegram',
      source_path: location.pathname,
      device_mode: deviceMode,
      is_in_telegram: isInTelegram,
      has_init_data: Boolean(initData),
      start_param: launchContext.startParam || undefined,
      has_query_id: launchContext.hasQueryId,
      chat_type: launchContext.chatType || undefined,
    })
  }, [deviceMode, initData, isInTelegram, isReady, launchContext, location.pathname])

  useEffect(() => {
    if (!isReady || !isInTelegram) {
      return
    }

    // If Telegram opens the classic root entry, forward to Mini App landing.
    if (location.pathname === '/' && !location.search) {
      navigate('/miniapp', { replace: true })
    }
  }, [isInTelegram, isReady, location.pathname, location.search, navigate])

  return (
    <div className="relative isolate overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-[-180px] z-[-1] h-[540px] bg-[radial-gradient(75%_120%_at_50%_30%,rgba(124,145,166,0.18)_0%,rgba(124,145,166,0)_75%)]" />
      <div className="pointer-events-none absolute right-[-140px] top-[260px] z-[-1] h-[360px] w-[360px] rounded-full bg-[#5c6c7d]/24 blur-[140px]" />
      <div className="pointer-events-none absolute left-[-200px] top-[760px] z-[-1] h-[420px] w-[420px] rounded-full bg-[#4f5f70]/22 blur-[160px]" />

      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#050608]/78 backdrop-blur-xl">
        <div className="mx-auto flex h-[76px] max-w-[1240px] items-center justify-between px-4 sm:px-6">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-left transition-colors hover:bg-white/[0.07]"
          >
            <span className="grid h-9 w-9 place-items-center rounded-lg border border-primary/30 bg-primary/12 text-primary">
              <Shield className="h-4 w-4" />
            </span>
            <span>
              <span className="block text-[11px] uppercase tracking-[0.18em] text-slate-400">{projectName}</span>
              <span className="block text-sm font-semibold text-slate-100">{t('landing.navLabel')}</span>
            </span>
          </button>

          <div className="flex items-center gap-2">
            <Button
              onClick={handleLogin}
              variant="outline"
              className="hidden sm:inline-flex"
            >
              <Lock className="h-4 w-4" />
              {t('landing.login')}
            </Button>
            <Button onClick={handleRegister}>
              {t('landing.register')}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <main>
        <section className="mx-auto flex max-w-[1240px] flex-col px-4 pb-20 pt-16 sm:px-6 lg:pt-24">
          <div className="mx-auto max-w-4xl text-center">
            <Badge variant="secondary" className="mb-5">
              <Star className="mr-1.5 h-3.5 w-3.5" />
              {t('landing.badge')}
            </Badge>

            <h1 className="text-4xl font-semibold leading-tight text-white sm:text-5xl lg:text-6xl">
              {t('landing.title')}
              <span className="mt-2 block bg-[linear-gradient(90deg,#d3dfe8_0%,#b3c3d2_45%,#8ea4b8_100%)] bg-clip-text text-transparent">
                {t('landing.titleAccent')}
              </span>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-base text-slate-300 sm:text-lg">
              {t('landing.subtitle')}
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button size="lg" onClick={handleRegister} className="min-w-[220px]">
                {t('landing.ctaStart')}
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button size="lg" onClick={handleLogin} variant="outline" className="min-w-[220px]">
                {t('landing.ctaOpen')}
              </Button>
            </div>

            {isInTelegram ? (
              <Card className="mx-auto mt-4 max-w-2xl border-primary/20 bg-primary/10">
                <CardContent className="flex flex-col items-center justify-between gap-3 p-4 text-left sm:flex-row">
                  <p className="text-sm text-slate-200">{t('landing.telegramMiniAppHint')}</p>
                  <Button type="button" onClick={handleOpenMiniApp}>
                    {t('landing.telegramMiniAppCta')}
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            ) : null}
          </div>

          <div className="mt-14 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card className="border-white/10 bg-white/[0.03]">
              <CardContent className="p-5 text-center">
                <p className="text-3xl font-semibold text-white">10K+</p>
                <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-400">{t('landing.stats.users')}</p>
              </CardContent>
            </Card>
            <Card className="border-white/10 bg-white/[0.03]">
              <CardContent className="p-5 text-center">
                <p className="text-3xl font-semibold text-white">50+</p>
                <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-400">{t('landing.stats.locations')}</p>
              </CardContent>
            </Card>
            <Card className="border-white/10 bg-white/[0.03]">
              <CardContent className="p-5 text-center">
                <p className="text-3xl font-semibold text-white">99.9%</p>
                <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-400">{t('landing.stats.uptime')}</p>
              </CardContent>
            </Card>
            <Card className="border-white/10 bg-white/[0.03]">
              <CardContent className="p-5 text-center">
                <p className="text-3xl font-semibold text-white">24/7</p>
                <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-400">{t('landing.stats.support')}</p>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="mx-auto max-w-[1240px] px-4 py-8 sm:px-6 lg:py-14">
          <div className="mb-8 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-3xl font-semibold text-white">{t('landing.whyTitle', { project: projectName })}</h2>
              <p className="mt-2 max-w-2xl text-sm text-slate-400">
                {t('landing.whySubtitle')}
              </p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, index) => (
              <Card key={feature.titleKey} className="group border-white/10 bg-white/[0.03]">
                <CardContent className="p-6">
                  <div className="mb-4 flex items-center gap-3">
                    <span className={`grid h-11 w-11 place-items-center rounded-xl ${feature.accentBg}`}>
                      <feature.icon className={`h-5 w-5 ${feature.accent}`} />
                    </span>
                    <span className="text-xs uppercase tracking-[0.14em] text-slate-500">
                      Feature {String(index + 1).padStart(2, '0')}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-slate-100">{t(feature.titleKey)}</h3>
                  <p className="mt-2 text-sm text-slate-400">{t(feature.descriptionKey)}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-[1240px] px-4 py-10 sm:px-6 lg:py-16">
          <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
            <Card className="border-white/10 bg-[linear-gradient(170deg,rgba(13,17,22,0.94)_0%,rgba(8,11,15,0.94)_100%)]">
              <CardContent className="p-7 md:p-9">
                <h2 className="text-3xl font-semibold text-slate-100">{t('landing.pricingTitle')}</h2>
                <p className="mt-3 text-sm text-slate-400">
                  {t('landing.pricingDesc')}
                </p>

                <div className="mt-7 grid gap-4 md:grid-cols-3">
                  {plans.map((plan) => (
                    <Card
                      key={plan.nameKey}
                      className={`relative border ${plan.popular ? 'border-primary/30 bg-primary/10' : 'border-white/10 bg-white/[0.02]'}`}
                    >
                      {plan.badgeKey && (
                        <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">
                          {t(plan.badgeKey)}
                        </Badge>
                      )}
                      <CardContent className="p-5">
                        <p className="text-xl font-semibold text-slate-100">{t(plan.nameKey)}</p>
                        <p className="mt-1 text-sm text-slate-400">{t(plan.durationKey)}</p>
                        <p className="mt-3 text-xs uppercase tracking-[0.12em] text-slate-500">{t(plan.hintKey)}</p>
                        <ul className="mt-4 space-y-2">
                          {plan.featureKeys.map((itemKey) => (
                            <li key={itemKey} className="flex items-center gap-2 text-sm text-slate-300">
                              <Check className="h-4 w-4 text-primary" />
                              {t(itemKey)}
                            </li>
                          ))}
                        </ul>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-white/[0.03]">
              <CardContent className="flex h-full flex-col justify-between p-7">
                <div>
                  <p className="text-sm uppercase tracking-[0.14em] text-slate-500">{t('landing.insideLabel')}</p>
                  <h3 className="mt-2 text-2xl font-semibold text-slate-100">{t('landing.insideTitle')}</h3>
                  <p className="mt-3 text-sm text-slate-400">
                    {t('landing.insideDesc')}
                  </p>
                  <ul className="mt-6 space-y-3">
                    {benefits.map((itemKey) => (
                      <li key={itemKey} className="flex items-start gap-3 text-sm text-slate-300">
                        <span className="mt-0.5 grid h-5 w-5 place-items-center rounded-full bg-primary/16">
                          <Check className="h-3.5 w-3.5 text-primary" />
                        </span>
                        {t(itemKey)}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mt-8 grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                    <Users className="h-5 w-5 text-primary" />
                    <p className="mt-3 text-xl font-semibold text-slate-100">10K+</p>
                    <p className="text-xs text-slate-400">{t('landing.insideStats.clients')}</p>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                    <TrendingUp className="h-5 w-5 text-primary" />
                    <p className="mt-3 text-xl font-semibold text-slate-100">99%</p>
                    <p className="text-xs text-slate-400">{t('landing.insideStats.satisfaction')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="mx-auto max-w-[1240px] px-4 pb-20 pt-8 sm:px-6">
          <Card className="border-primary/20 bg-[linear-gradient(120deg,rgba(58,69,81,0.28)_0%,rgba(15,20,27,0.74)_52%,rgba(9,12,16,0.94)_100%)]">
            <CardContent className="p-8 text-center md:p-12">
              <h2 className="text-3xl font-semibold text-white md:text-4xl">{t('landing.finalTitle')}</h2>
              <p className="mx-auto mt-4 max-w-2xl text-slate-200">
                {t('landing.finalDesc')}
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Button size="lg" onClick={handleRegister} className="min-w-[220px]">
                  {t('landing.register')}
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button size="lg" variant="outline" onClick={handleLogin} className="min-w-[220px]">
                  {t('landing.login')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>
      </main>

      <footer className="border-t border-white/10 bg-black/20">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center justify-between gap-3 px-4 py-7 text-sm text-slate-400 sm:flex-row sm:px-6">
          <p>(c) 2026 {projectName}. {t('landing.footer')}</p>
          <div className="flex items-center gap-4">
            <a className="transition-colors hover:text-slate-200" href="/privacy-policy">
              {t('landing.privacyPolicy')}
            </a>
            <a className="transition-colors hover:text-slate-200" href="/privacy-policy">
              {t('landing.termsOfUse')}
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
