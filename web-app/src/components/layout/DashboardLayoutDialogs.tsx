import { useI18n } from '@/components/common/I18nProvider'
import type { DashboardDialogsState } from './useDashboardDialogs'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface DashboardLayoutDialogsProps {
  dialogs: DashboardDialogsState
}

export function DashboardLayoutDialogs({ dialogs }: DashboardLayoutDialogsProps) {
  const { t } = useI18n()

  return (
    <>
      <Dialog open={dialogs.linkPrompt.open} onOpenChange={dialogs.linkPrompt.onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('layout.linkTgTitle')}</DialogTitle>
            <DialogDescription>{t('layout.linkTgDesc')}</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => {
                void dialogs.linkPrompt.onRemindLater()
              }}
              disabled={dialogs.linkPrompt.isSavingLater}
            >
              {dialogs.linkPrompt.isSavingLater ? t('layout.linkSaving') : t('layout.linkLater')}
            </Button>
            <Button onClick={dialogs.linkPrompt.onLinkNow}>{t('layout.linkNow')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogs.forcePassword.open} onOpenChange={dialogs.forcePassword.onOpenChange}>
        <DialogContent
          showCloseButton={false}
          onEscapeKeyDown={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{t('layout.forcePassword.title')}</DialogTitle>
            <DialogDescription>{t('layout.forcePassword.description')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-1">
            <div className="space-y-2">
              <Label htmlFor="force-current-password">{t('layout.forcePassword.currentPassword')}</Label>
              <Input
                id="force-current-password"
                type="password"
                value={dialogs.forcePassword.currentPassword}
                onChange={(event) => dialogs.forcePassword.onCurrentPasswordChange(event.target.value)}
                placeholder={t('layout.forcePassword.currentPasswordPlaceholder')}
                autoComplete="current-password"
                disabled={dialogs.forcePassword.isSubmitting}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="force-new-password">{t('layout.forcePassword.newPassword')}</Label>
              <Input
                id="force-new-password"
                type="password"
                value={dialogs.forcePassword.newPassword}
                onChange={(event) => dialogs.forcePassword.onNewPasswordChange(event.target.value)}
                placeholder={t('layout.forcePassword.newPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={dialogs.forcePassword.isSubmitting}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="force-confirm-password">{t('layout.forcePassword.confirmPassword')}</Label>
              <Input
                id="force-confirm-password"
                type="password"
                value={dialogs.forcePassword.confirmPassword}
                onChange={(event) => dialogs.forcePassword.onConfirmPasswordChange(event.target.value)}
                placeholder={t('layout.forcePassword.confirmPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={dialogs.forcePassword.isSubmitting}
              />
            </div>
            {dialogs.forcePassword.error && (
              <p className="text-sm text-red-300">{dialogs.forcePassword.error}</p>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={dialogs.forcePassword.onLogout}
              disabled={dialogs.forcePassword.isSubmitting}
            >
              {t('layout.forcePassword.logout')}
            </Button>
            <Button
              onClick={() => {
                void dialogs.forcePassword.onSubmit()
              }}
              disabled={dialogs.forcePassword.isSubmitting}
            >
              {dialogs.forcePassword.isSubmitting
                ? t('layout.forcePassword.changing')
                : t('layout.forcePassword.change')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogs.bootstrap.open} onOpenChange={dialogs.bootstrap.onOpenChange}>
        <DialogContent
          showCloseButton={false}
          onEscapeKeyDown={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{t('layout.tgBootstrapTitle')}</DialogTitle>
            <DialogDescription>{t('layout.tgBootstrapDesc')}</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-1">
            <div className="space-y-2">
              <Label htmlFor="tg-bootstrap-username">{t('layout.tgBootstrapUsername')}</Label>
              <Input
                id="tg-bootstrap-username"
                value={dialogs.bootstrap.username}
                onChange={(event) => dialogs.bootstrap.onUsernameChange(event.target.value)}
                placeholder={t('layout.tgBootstrapUsernamePlaceholder')}
                autoComplete="username"
                disabled={dialogs.bootstrap.isSubmitting}
              />
              <p className="text-xs text-muted-foreground">
                {t('layout.tgBootstrapUsernameHint')}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="tg-bootstrap-password">{t('layout.tgBootstrapPassword')}</Label>
              <Input
                id="tg-bootstrap-password"
                type="password"
                value={dialogs.bootstrap.password}
                onChange={(event) => dialogs.bootstrap.onPasswordChange(event.target.value)}
                placeholder={t('layout.tgBootstrapPasswordPlaceholder')}
                autoComplete="new-password"
                disabled={dialogs.bootstrap.isSubmitting}
              />
            </div>
            {dialogs.bootstrap.error && (
              <p className="text-sm text-red-300">{dialogs.bootstrap.error}</p>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={dialogs.bootstrap.onLogout}
              disabled={dialogs.bootstrap.isSubmitting}
            >
              {t('layout.tgBootstrapLogout')}
            </Button>
            <Button
              onClick={() => {
                void dialogs.bootstrap.onSubmit()
              }}
              disabled={dialogs.bootstrap.isSubmitting}
            >
              {dialogs.bootstrap.isSubmitting
                ? t('layout.tgBootstrapCreating')
                : t('layout.tgBootstrapCreate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={dialogs.trialOnboarding.open}
        onOpenChange={dialogs.trialOnboarding.onOpenChange}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('layout.trialOnboarding.title')}</DialogTitle>
            <DialogDescription>{t('layout.trialOnboarding.description')}</DialogDescription>
          </DialogHeader>

          {dialogs.trialOnboarding.error && (
            <p className="text-sm text-red-300">{dialogs.trialOnboarding.error}</p>
          )}

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={dialogs.trialOnboarding.onClose}
              disabled={dialogs.trialOnboarding.isSubmitting}
            >
              {t('layout.trialOnboarding.later')}
            </Button>
            <Button
              onClick={() => {
                void dialogs.trialOnboarding.onSubmit()
              }}
              disabled={dialogs.trialOnboarding.isSubmitting}
            >
              {dialogs.trialOnboarding.isSubmitting
                ? t('layout.trialOnboarding.activating')
                : t('layout.trialOnboarding.activate')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
