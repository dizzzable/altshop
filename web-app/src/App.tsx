import { Suspense, lazy, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './components/auth/AuthProvider'
import { BrandingProvider } from './components/common/BrandingProvider'
import { I18nProvider, useI18n } from './components/common/I18nProvider'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PublicRoute } from './components/auth/PublicRoute'

const loadDashboardLayout = () => import('./components/layout/DashboardLayout')
const loadLoginPage = () => import('./pages/auth/LoginPage')
const loadRegisterPage = () => import('./pages/auth/RegisterPage')
const loadForgotPasswordPage = () => import('./pages/auth/ForgotPasswordPage')
const loadResetPasswordPage = () => import('./pages/auth/ResetPasswordPage')
const loadLandingPage = () => import('./pages/landing/LandingPage')
const loadMiniAppLandingPage = () => import('./pages/landing/MiniAppLandingPage')
const loadDashboardPage = () => import('./pages/dashboard/DashboardPage')
const loadSubscriptionPage = () => import('./pages/dashboard/SubscriptionPage')
const loadPurchasePage = () => import('./pages/dashboard/PurchasePage')
const loadDevicesPage = () => import('./pages/dashboard/DevicesPage')
const loadReferralsPage = () => import('./pages/dashboard/ReferralsPage')
const loadPromocodesPage = () => import('./pages/dashboard/PromocodesPage')
const loadPartnerPage = () => import('./pages/dashboard/PartnerPage')
const loadSettingsPage = () => import('./pages/dashboard/SettingsPage')
const loadPaymentReturnPage = () => import('./pages/payment/PaymentReturnPage')

const DashboardLayout = lazy(() =>
  loadDashboardLayout().then((module) => ({ default: module.DashboardLayout }))
)
const LoginPage = lazy(() => loadLoginPage().then((module) => ({ default: module.LoginPage })))
const RegisterPage = lazy(() =>
  loadRegisterPage().then((module) => ({ default: module.RegisterPage }))
)
const ForgotPasswordPage = lazy(() =>
  loadForgotPasswordPage().then((module) => ({ default: module.ForgotPasswordPage }))
)
const ResetPasswordPage = lazy(() =>
  loadResetPasswordPage().then((module) => ({ default: module.ResetPasswordPage }))
)
const LandingPage = lazy(() => loadLandingPage().then((module) => ({ default: module.LandingPage })))
const MiniAppLandingPage = lazy(() =>
  loadMiniAppLandingPage().then((module) => ({ default: module.MiniAppLandingPage }))
)
const DashboardPage = lazy(() =>
  loadDashboardPage().then((module) => ({ default: module.DashboardPage }))
)
const SubscriptionPage = lazy(() =>
  loadSubscriptionPage().then((module) => ({ default: module.SubscriptionPage }))
)
const PurchasePage = lazy(() =>
  loadPurchasePage().then((module) => ({ default: module.PurchasePage }))
)
const DevicesPage = lazy(() => loadDevicesPage().then((module) => ({ default: module.DevicesPage })))
const ReferralsPage = lazy(() =>
  loadReferralsPage().then((module) => ({ default: module.ReferralsPage }))
)
const PromocodesPage = lazy(() =>
  loadPromocodesPage().then((module) => ({ default: module.PromocodesPage }))
)
const PartnerPage = lazy(() => loadPartnerPage().then((module) => ({ default: module.PartnerPage })))
const SettingsPage = lazy(() =>
  loadSettingsPage().then((module) => ({ default: module.SettingsPage }))
)
const PaymentReturnPage = lazy(() =>
  loadPaymentReturnPage().then((module) => ({ default: module.PaymentReturnPage }))
)

function RouteFallback() {
  const { t } = useI18n()
  return <div className="p-6 text-sm text-slate-300">{t('common.loading')}</div>
}

function AuthCallbackFallback() {
  const { t } = useI18n()
  return <div className="p-6 text-sm text-slate-300">{t('common.authenticating')}</div>
}

function PrefetchPopularRoutes() {
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    if (!isAuthenticated) {
      return
    }

    const prefetch = () => {
      void loadDashboardLayout()
      void loadDashboardPage()
      void loadSubscriptionPage()
      void loadDevicesPage()
      void loadPromocodesPage()
    }

    if (typeof window.requestIdleCallback === 'function') {
      const idleId = window.requestIdleCallback(() => {
        prefetch()
      }, { timeout: 2000 })

      return () => {
        window.cancelIdleCallback(idleId)
      }
    }

    const timeoutId = window.setTimeout(prefetch, 700)
    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [isAuthenticated])

  return null
}

function App() {
  const routerBasename = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')

  return (
    <BrowserRouter basename={routerBasename || '/'}>
      <BrandingProvider>
        <AuthProvider>
          <I18nProvider>
            <PrefetchPopularRoutes />
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                {/* Landing pages */}
                <Route path="/" element={<LandingPage />} />
                <Route path="/miniapp" element={<MiniAppLandingPage />} />
                <Route path="/payment-return" element={<PaymentReturnPage />} />

                {/* Public routes */}
                <Route
                  path="/auth/login"
                  element={
                    <PublicRoute>
                      <LoginPage />
                    </PublicRoute>
                  }
                />
                <Route
                  path="/auth/register"
                  element={
                    <PublicRoute>
                      <RegisterPage />
                    </PublicRoute>
                  }
                />
                <Route
                  path="/auth/forgot-password"
                  element={
                    <PublicRoute>
                      <ForgotPasswordPage />
                    </PublicRoute>
                  }
                />
                <Route
                  path="/auth/reset-password"
                  element={
                    <PublicRoute>
                      <ResetPasswordPage />
                    </PublicRoute>
                  }
                />

                {/* Telegram OAuth callback - handled by AuthProvider */}
                <Route path="/auth/telegram/callback" element={<AuthCallbackFallback />} />

                {/* Protected routes */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <DashboardLayout />
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<DashboardPage />} />
                  <Route path="subscription" element={<SubscriptionPage />} />
                  <Route path="subscription/purchase" element={<PurchasePage />} />
                  <Route path="subscription/:id/renew" element={<PurchasePage />} />
                  <Route path="subscription/:id/upgrade" element={<PurchasePage />} />
                  <Route path="devices" element={<DevicesPage />} />
                  <Route path="referrals" element={<ReferralsPage />} />
                  <Route path="promocodes" element={<PromocodesPage />} />
                  <Route path="partner" element={<PartnerPage />} />
                  <Route path="settings" element={<SettingsPage />} />
                </Route>

                {/* Redirects */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </I18nProvider>
        </AuthProvider>
      </BrandingProvider>
    </BrowserRouter>
  )
}

export default App
