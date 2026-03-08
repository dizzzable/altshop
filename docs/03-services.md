# AltShop Services

Проверено по коду: `2026-03-08`

В `src/services` сейчас 42 service modules. Файл `base.py` даёт общий `BaseService` и в счёт не входит.

## Общий паттерн

Большинство services:

- получают зависимости через Dishka providers
- работают поверх `UnitOfWork`, Redis, Bot, TranslatorHub и других services
- не экспонируют HTTP/Telegram сами по себе, а вызываются из endpoints, routers и background tasks

## 1. Access и authentication

| Модуль | Назначение |
| --- | --- |
| `access.py` | общие правила доступа и регистрации |
| `auth_challenge.py` | хранение и проверка auth/email/telegram challenges |
| `email_recovery.py` | email verify, forgot password, password reset, change password |
| `email_sender.py` | SMTP-отправка служебных писем |
| `telegram_link.py` | привязка web account к Telegram user через код подтверждения |
| `web_access_guard.py` | вычисление `WebAccessStatus`, rules/channel/telegram link gating |
| `web_account.py` | регистрация, login, token versioning, bootstrap web credentials |

## 2. User profile и activity

| Модуль | Назначение |
| --- | --- |
| `notification.py` | отправка пользовательских и системных уведомлений |
| `user.py` | базовые операции с пользователями |
| `user_activity_portal.py` | transactions, notifications и promocode history для web portal |
| `user_notification_event.py` | запись доменных notification events |
| `user_profile.py` | сборка агрегированного profile snapshot для API |
| `web_analytics_event.py` | приём и хранение web analytics events |

## 3. Plans, pricing и promocodes

| Модуль | Назначение |
| --- | --- |
| `market_quote.py` | котировки/market helpers для settlement currency |
| `plan.py` | CRUD и базовые операции по планам |
| `plan_catalog.py` | публикация доступных планов и цен для user/web flow |
| `pricing.py` | вычисление финальных цен, скидок и currency settlement |
| `promocode.py` | core logic промокодов |
| `promocode_portal.py` | web-facing activation flow и snapshots |

## 4. Subscription lifecycle

| Модуль | Назначение |
| --- | --- |
| `purchase_access.py` | запрет/разрешение purchase operations по текущему access mode |
| `purchase_gateway_policy.py` | правила выбора и фильтрации payment gateways |
| `subscription.py` | базовые операции по подпискам |
| `subscription_device.py` | список устройств, генерация device link, revoke |
| `subscription_portal.py` | detail/update/delete flow для user-facing subscription API |
| `subscription_purchase.py` | execute/quote/retry alias flow для purchase и renew |
| `subscription_runtime.py` | batch runtime refresh и подготовка списка подписок |
| `subscription_trial.py` | eligibility и создание trial subscriptions |

## 5. Payments и transactions

| Модуль | Назначение |
| --- | --- |
| `payment_gateway.py` | registry/factory usage, payment creation, post-payment orchestration |
| `payment_webhook_event.py` | inbox/deduplication record для incoming payment webhooks |
| `transaction.py` | CRUD и status lifecycle транзакций |

## 6. Referral и partner

| Модуль | Назначение |
| --- | --- |
| `partner.py` | core partner program logic и earnings processing |
| `partner_portal.py` | partner dashboard snapshots, referrals, earnings, withdrawals |
| `referral.py` | attach referral, qualification, reward issuance |
| `referral_exchange.py` | обмен referral points на дни, traffic, discount, gift subscription |
| `referral_portal.py` | web-facing referral info, lists, QR, exchange options |

## 7. System, ops и external integration

| Модуль | Назначение |
| --- | --- |
| `backup.py` | ручные и автоматические backup jobs |
| `broadcast.py` | массовые рассылки |
| `command.py` | установка и удаление Telegram bot commands |
| `importer.py` | импорт данных из внешних источников |
| `remnawave.py` | интеграция с Remnawave users, nodes и webhook events |
| `settings.py` | runtime settings, branding, access mode, notifications config |
| `webhook.py` | setup/delete Telegram webhook и Redis lock по hash конфигурации |

## Сервисные зависимости верхнего уровня

Наиболее связные модули:

- `payment_gateway.py`
  - зависит от `transaction.py`, `subscription.py`, `referral.py`, `partner.py`, `user.py`
  - соединяет payment adapters и background subscription provisioning
- `subscription_purchase.py`
  - зависит от `plan_catalog.py`, `pricing.py`, `payment_gateway.py`, `purchase_access.py`
  - является главным оркестратором purchase/renew flows
- `web_account.py` и `email_recovery.py`
  - разделяют web auth lifecycle: регистрация, логин, reset, verification, token invalidation
- `user_profile.py` и `user_activity_portal.py`
  - собирают read-model snapshots для user-facing endpoints

## Что используют HTTP endpoints

### Web auth endpoints

Основные зависимости:

- `WebAccountService`
- `WebAccessGuardService`
- `TelegramLinkService`
- `EmailRecoveryService`
- `UserProfileService`
- `WebAnalyticsEventService`

### User API endpoints

Основные зависимости:

- `UserProfileService`
- `PlanCatalogService`
- `UserActivityPortalService`
- `SubscriptionPortalService`
- `SubscriptionPurchaseService`
- `SubscriptionDeviceService`
- `SubscriptionTrialService`
- `PromocodePortalService`
- `ReferralPortalService`
- `PartnerPortalService`

### Lifespan/startup

На старте backend особенно важны:

- `PaymentGatewayService`
- `SettingsService`
- `BackupService`
- `WebhookService`
- `CommandService`
- `RemnawaveService`

## Что НЕ входит в этот список

- `src/infrastructure/payment_gateways/*` это adapters, а не application services
- `src/infrastructure/database/repositories/*` это persistence layer
- `src/api/presenters/*` это serialization layer
- `src/api/contracts/*` это request DTO layer

## Полный список модулей

```text
access.py
auth_challenge.py
backup.py
broadcast.py
command.py
email_recovery.py
email_sender.py
importer.py
market_quote.py
notification.py
partner.py
partner_portal.py
payment_gateway.py
payment_webhook_event.py
plan.py
plan_catalog.py
pricing.py
promocode.py
promocode_portal.py
purchase_access.py
purchase_gateway_policy.py
referral.py
referral_exchange.py
referral_portal.py
remnawave.py
settings.py
subscription.py
subscription_device.py
subscription_portal.py
subscription_purchase.py
subscription_runtime.py
subscription_trial.py
telegram_link.py
transaction.py
user.py
user_activity_portal.py
user_notification_event.py
user_profile.py
web_access_guard.py
web_account.py
web_analytics_event.py
webhook.py
```
