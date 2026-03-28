import { useEffect, useRef, useState } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import { useI18n } from '@/components/common/I18nProvider'
import { api, clearLegacyAuthStorage } from '@/lib/api'
import { getApiErrorMessage } from '@/lib/api-error'
import { sendWebTelemetryEvent } from '@/lib/telemetry'
import {
  isInvalidWebLoginBackendError,
  isValidWebLogin,
  normalizeWebLogin,
} from '@/lib/web-login'
import {
  clearPendingTelegramMiniAppOnboarding,
  hasPendingTelegramMiniAppOnboarding,
} from '@/lib/telegram-onboarding'
import type { User } from '@/types'

export interface DashboardLinkPromptState {
  open: boolean
  onLinkNow: () => void
  onOpenChange: (open: boolean) => void
  onRemindLater: () => Promise<void>
  isSavingLater: boolean
}

export interface DashboardForcePasswordState {
  open: boolean
  currentPassword: string
  newPassword: string
  confirmPassword: string
  error: string | null
  isSubmitting: boolean
  onConfirmPasswordChange: (value: string) => void
  onCurrentPasswordChange: (value: string) => void
  onLogout: () => void
  onNewPasswordChange: (value: string) => void
  onOpenChange: (open: boolean) => void
  onSubmit: () => Promise<void>
}

export interface DashboardBootstrapState {
  open: boolean
  username: string
  password: string
  error: string | null
  isSubmitting: boolean
  onLogout: () => void
  onOpenChange: (open: boolean) => void
  onPasswordChange: (value: string) => void
  onSubmit: () => Promise<void>
  onUsernameChange: (value: string) => void
}

export interface DashboardTrialOnboardingState {
  open: boolean
  error: string | null
  isSubmitting: boolean
  onClose: () => void
  onOpenChange: (open: boolean) => void
  onSubmit: () => Promise<void>
}

export interface DashboardDialogsState {
  bootstrap: DashboardBootstrapState
  forcePassword: DashboardForcePasswordState
  linkPrompt: DashboardLinkPromptState
  trialOnboarding: DashboardTrialOnboardingState
}

interface UseDashboardDialogsOptions {
  canPurchase: boolean
  isInTelegram: boolean
  isPurchaseBlocked: boolean
  logout: () => Promise<void>
  navigate: NavigateFunction
  pathname: string
  refreshUser: () => Promise<void>
  user: User | null
}

export function useDashboardDialogs({
  canPurchase,
  isInTelegram,
  isPurchaseBlocked,
  logout,
  navigate,
  pathname,
  refreshUser,
  user,
}: UseDashboardDialogsOptions): DashboardDialogsState {
  const { t } = useI18n()
  const [openForcePasswordPrompt, setOpenForcePasswordPrompt] = useState(false)
  const [forceCurrentPassword, setForceCurrentPassword] = useState('')
  const [forceNewPassword, setForceNewPassword] = useState('')
  const [forceConfirmPassword, setForceConfirmPassword] = useState('')
  const [forceError, setForceError] = useState<string | null>(null)
  const [isForceChanging, setIsForceChanging] = useState(false)
  const [openLinkPrompt, setOpenLinkPrompt] = useState(false)
  const [isSavingLater, setIsSavingLater] = useState(false)
  const [openBootstrapPrompt, setOpenBootstrapPrompt] = useState(false)
  const [bootstrapUsername, setBootstrapUsername] = useState('')
  const [bootstrapPassword, setBootstrapPassword] = useState('')
  const [bootstrapError, setBootstrapError] = useState<string | null>(null)
  const [isBootstrapping, setIsBootstrapping] = useState(false)
  const [openTrialOnboardingPrompt, setOpenTrialOnboardingPrompt] = useState(false)
  const [trialOnboardingError, setTrialOnboardingError] = useState<string | null>(null)
  const [isActivatingTrialOnboarding, setIsActivatingTrialOnboarding] = useState(false)
  const bootstrapShownRef = useRef(false)
  const authSource =
    typeof window !== 'undefined' ? window.sessionStorage.getItem('auth_source') : null
  const isMiniAppBootstrapSession = authSource === 'telegram-miniapp'

  useEffect(() => {
    const shouldOpen = Boolean(
      user?.show_link_prompt
      && !user?.telegram_linked
      && !openBootstrapPrompt
      && !openForcePasswordPrompt
      && !user?.requires_password_change
    )
    setOpenLinkPrompt(shouldOpen)
  }, [
    openBootstrapPrompt,
    openForcePasswordPrompt,
    user?.requires_password_change,
    user?.show_link_prompt,
    user?.telegram_linked,
  ])

  useEffect(() => {
    const shouldOpen = Boolean(
      isMiniAppBootstrapSession
      && user?.needs_web_credentials_bootstrap
      && !openForcePasswordPrompt
      && !user?.requires_password_change
    )
    setOpenBootstrapPrompt(shouldOpen)
  }, [
    isMiniAppBootstrapSession,
    openForcePasswordPrompt,
    user?.needs_web_credentials_bootstrap,
    user?.requires_password_change,
  ])

  useEffect(() => {
    if (openBootstrapPrompt && !bootstrapShownRef.current) {
      bootstrapShownRef.current = true
      sendWebTelemetryEvent({
        event_name: 'miniapp_credentials_bootstrap_shown',
        source_path: pathname,
        device_mode: isInTelegram ? 'telegram-mobile' : 'web',
        is_in_telegram: isInTelegram,
        has_init_data: isInTelegram,
        has_query_id: false,
      })
    }
  }, [isInTelegram, openBootstrapPrompt, pathname])

  useEffect(() => {
    const shouldOpen = Boolean(user?.requires_password_change)
    setOpenForcePasswordPrompt(shouldOpen)
    if (!shouldOpen) {
      setForceCurrentPassword('')
      setForceNewPassword('')
      setForceConfirmPassword('')
      setForceError(null)
    }
  }, [user?.requires_password_change])

  useEffect(() => {
    if (!openBootstrapPrompt) {
      return
    }

    const preferredWebLogin = user?.web_login || user?.username
    if (!bootstrapUsername && preferredWebLogin) {
      setBootstrapUsername(normalizeWebLogin(preferredWebLogin))
    }
  }, [bootstrapUsername, openBootstrapPrompt, user?.username, user?.web_login])

  useEffect(() => {
    if (!openForcePasswordPrompt) {
      return
    }

    setOpenBootstrapPrompt(false)
    setOpenLinkPrompt(false)
  }, [openForcePasswordPrompt])

  const handleForcePasswordChange = async () => {
    if (!forceCurrentPassword || !forceNewPassword || !forceConfirmPassword) {
      setForceError(t('layout.forcePassword.errorRequired'))
      return
    }
    if (forceNewPassword.length < 6) {
      setForceError(t('layout.forcePassword.errorMinLength'))
      return
    }
    if (forceNewPassword !== forceConfirmPassword) {
      setForceError(t('layout.forcePassword.errorNoMatch'))
      return
    }

    setForceError(null)
    setIsForceChanging(true)
    try {
      await api.auth.changePassword({
        current_password: forceCurrentPassword,
        new_password: forceNewPassword,
      })
      clearLegacyAuthStorage()
      await refreshUser()
      setOpenForcePasswordPrompt(false)
      setForceCurrentPassword('')
      setForceNewPassword('')
      setForceConfirmPassword('')
    } catch (error: unknown) {
      setForceError(getApiErrorMessage(error) || t('layout.forcePassword.errorDefault'))
    } finally {
      setIsForceChanging(false)
    }
  }

  const handleRemindLater = async () => {
    setIsSavingLater(true)
    try {
      await api.auth.remindTelegramLinkLater()
      await refreshUser()
    } finally {
      setIsSavingLater(false)
      setOpenLinkPrompt(false)
    }
  }

  const handleBootstrapCreate = async () => {
    const normalizedUsername = normalizeWebLogin(bootstrapUsername)
    if (!normalizedUsername || !bootstrapPassword) {
      setBootstrapError(t('layout.tgBootstrapErrorRequired'))
      return
    }

    if (!isValidWebLogin(normalizedUsername)) {
      setBootstrapError(t('layout.tgBootstrapErrorInvalidFormat'))
      return
    }

    setBootstrapError(null)
    setIsBootstrapping(true)

    try {
      await api.auth.webAccountBootstrap({
        username: normalizedUsername,
        password: bootstrapPassword,
      })
      clearLegacyAuthStorage()
      sessionStorage.setItem('auth_source', 'password')
      sendWebTelemetryEvent({
        event_name: 'miniapp_credentials_bootstrap_completed',
        source_path: pathname,
        device_mode: isInTelegram ? 'telegram-mobile' : 'web',
        is_in_telegram: isInTelegram,
        has_init_data: isInTelegram,
        has_query_id: false,
        meta: {
          username: normalizedUsername,
        },
      })
      setBootstrapPassword('')
      await refreshUser()
      setOpenBootstrapPrompt(false)
      setBootstrapError(null)

      if (hasPendingTelegramMiniAppOnboarding() && canPurchase) {
        try {
          const { data: trialEligibility } = await api.subscription.trialEligibility()
          if (trialEligibility.eligible && trialEligibility.trial_plan_id !== null) {
            setTrialOnboardingError(null)
            setOpenTrialOnboardingPrompt(true)
          } else {
            clearPendingTelegramMiniAppOnboarding()
          }
        } catch {
          clearPendingTelegramMiniAppOnboarding()
        }
      }
    } catch (error: unknown) {
      const backendMessage = getApiErrorMessage(error)
      setBootstrapError(
        isInvalidWebLoginBackendError(backendMessage)
          ? t('layout.tgBootstrapErrorInvalidFormat')
          : backendMessage || t('layout.tgBootstrapErrorDefault')
      )
    } finally {
      setIsBootstrapping(false)
    }
  }

  const handleBootstrapLogout = () => {
    sendWebTelemetryEvent({
      event_name: 'miniapp_credentials_bootstrap_rejected',
      source_path: pathname,
      device_mode: isInTelegram ? 'telegram-mobile' : 'web',
      is_in_telegram: isInTelegram,
      has_init_data: isInTelegram,
      has_query_id: false,
    })
    void logout()
  }

  const handleCloseTrialOnboarding = () => {
    clearPendingTelegramMiniAppOnboarding()
    setTrialOnboardingError(null)
    setOpenTrialOnboardingPrompt(false)
  }

  const handleActivateTrialOnboarding = async () => {
    if (!canPurchase) {
      setTrialOnboardingError(
        isPurchaseBlocked ? t('purchase.purchaseBlockedNotice') : t('purchase.readOnlyNotice')
      )
      return
    }

    setIsActivatingTrialOnboarding(true)
    setTrialOnboardingError(null)
    try {
      await api.subscription.trial()
      clearPendingTelegramMiniAppOnboarding()
      setOpenTrialOnboardingPrompt(false)
      await refreshUser()
      navigate('/dashboard/subscription', { replace: true })
    } catch (error: unknown) {
      setTrialOnboardingError(
        getApiErrorMessage(error) || t('layout.trialOnboarding.activateFailed')
      )
    } finally {
      setIsActivatingTrialOnboarding(false)
    }
  }

  return {
    linkPrompt: {
      open: openLinkPrompt,
      onLinkNow: () => {
        setOpenLinkPrompt(false)
        navigate('/dashboard/settings?focus=telegram')
      },
      onOpenChange: setOpenLinkPrompt,
      onRemindLater: handleRemindLater,
      isSavingLater,
    },
    forcePassword: {
      open: openForcePasswordPrompt,
      currentPassword: forceCurrentPassword,
      newPassword: forceNewPassword,
      confirmPassword: forceConfirmPassword,
      error: forceError,
      isSubmitting: isForceChanging,
      onConfirmPasswordChange: setForceConfirmPassword,
      onCurrentPasswordChange: setForceCurrentPassword,
      onLogout: () => {
        void logout()
      },
      onNewPasswordChange: setForceNewPassword,
      onOpenChange: (open) => {
        if (open || user?.requires_password_change) {
          setOpenForcePasswordPrompt(true)
        }
      },
      onSubmit: handleForcePasswordChange,
    },
    bootstrap: {
      open: openBootstrapPrompt,
      username: bootstrapUsername,
      password: bootstrapPassword,
      error: bootstrapError,
      isSubmitting: isBootstrapping,
      onLogout: handleBootstrapLogout,
      onOpenChange: (open) => {
        if (open) {
          setOpenBootstrapPrompt(true)
        }
      },
      onPasswordChange: setBootstrapPassword,
      onSubmit: handleBootstrapCreate,
      onUsernameChange: (value) => {
        setBootstrapUsername(normalizeWebLogin(value))
      },
    },
    trialOnboarding: {
      open: openTrialOnboardingPrompt,
      error: trialOnboardingError,
      isSubmitting: isActivatingTrialOnboarding,
      onClose: handleCloseTrialOnboarding,
      onOpenChange: (open) => {
        if (!open) {
          handleCloseTrialOnboarding()
        }
      },
      onSubmit: handleActivateTrialOnboarding,
    },
  }
}
