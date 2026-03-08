> [!WARNING]
> Исторический документ. Этот файл не входит в канонический комплект документации и не переаудировался в текущем проходе. Актуальная точка входа: [docs/README.md](README.md)

# Акт актуализации документации AltShop

**Дата:** 2026-03-08  
**Статус:** В процессе  
**Версия проекта:** 1.0.0

---

## Резюме анализа

Проведён полный анализ проекта AltShop и сравнение документации с реальным кодом. Выявлены существенные расхождения между документацией и фактическим состоянием проекта.

---

## Ключевые расхождения

### 1. Количество сервисов

| Документация | Реальность | Изменение |
|--------------|------------|-----------|
| 14 сервисов | 40+ сервисов | +26 сервисов |

**Новые сервисы (не задокументированы):**
- `subscription_device.py` — Управление устройствами
- `subscription_purchase.py` — Процесс покупки
- `subscription_runtime.py` — Runtime кэш
- `subscription_trial.py` — Пробные подписки
- `subscription_portal.py` — Portal service
- `plan_catalog.py` — Каталог планов
- `promocode_portal.py` — Portal service
- `referral_exchange.py` — Обмен баллов
- `referral_portal.py` — Portal service
- `partner_portal.py` — Portal service
- `user_profile.py` — Профиль пользователя
- `user_activity_portal.py` — Активность
- `web_account.py` — Веб-аккаунты
- `web_access_guard.py` — Веб-доступ
- `auth_challenge.py` — Аутентификация
- `access.py` — Контроль доступа
- `purchase_access.py` — Доступ к покупкам
- `purchase_gateway_policy.py` — Политики шлюзов
- `payment_webhook_event.py` — Обработка вебхуков
- `telegram_link.py` — Связка Telegram
- `email_sender.py` — Email отправка
- `email_recovery.py` — Восстановление email
- `user_notification_event.py` — События уведомлений
- `web_analytics_event.py` — Веб-аналитика
- `market_quote.py` — Котировки
- `pricing.py` — Ценообразование
- `command.py` — Команды бота

### 2. Платежные шлюзы

| Документация | Реальность | Изменение |
|--------------|------------|-----------|
| 10 шлюзов (7 реализовано) | 16 шлюзов | +6 шлюзов |

**Реальные шлюзы (src/infrastructure/payment_gateways/):**
1. `telegram_stars.py` — Telegram Stars ✅
2. `yookassa.py` — ЮKassa ✅
3. `yoomoney.py` — ЮMoney ⚠️
4. `cryptopay.py` — CryptoPay ✅
5. `cryptomus.py` — Cryptomus ⚠️
6. `heleket.py` — Heleket ✅
7. `pal24.py` — Pal24 (PayPalych) ✅
8. `platega.py` — Platega ✅
9. `wata.py` — WATA ✅
10. `tbank.py` — Тинькофф 🆕
11. `stripe.py` — Stripe 🆕
12. `robokassa.py` — Robokassa ⚠️
13. `mulenpay.py` — Mulenpay 🆕
14. `cloudpayments.py` — CloudPayments 🆕
15. `base.py` — Базовый класс
16. `__init__.py` — Фабрика

**Примечание:** ⚠️ — требуют проверки актуального состояния, 🆕 — новые шлюзы

### 3. База данных

| Документация | Реальность | Изменение |
|--------------|------------|-----------|
| 18 таблиц | 17 таблиц | -1 таблица |
| 27 миграций | 45 миграций | +18 миграций |

**Актуальные таблицы (17):**
1. `users` — Пользователи
2. `subscriptions` — Подписки
3. `plans` — Планы
4. `plan_durations` — Длительности планов
5. `plan_prices` — Цены планов
6. `transactions` — Транзакции
7. `payment_gateways` — Платежные шлюзы
8. `promocodes` — Промокоды
9. `promocode_activations` — Активации промокодов
10. `referrals` — Рефералы
11. `referral_rewards` — Реферальные вознаграждения
12. `partners` — Партнеры
13. `partner_referrals` — Партнерские рефералы
14. `partner_transactions` — Партнерские транзакции
15. `partner_withdrawals` — Партнерские выводы
16. `settings` — Настройки
17. `broadcasts` — Рассылки
18. `broadcast_messages` — Сообщения рассылок
19. `web_accounts` — Веб-аккаунты 🆕
20. `auth_challenges` — Аутентификационные челленджи 🆕
21. `user_notification_events` — События уведомлений 🆕
22. `web_analytics_events` — События веб-аналитики 🆕
23. `payment_webhook_events` — События платежных вебхуков 🆕

**Новые миграции (28-45):**
- 0028: Add auth fields
- 0029: Repair auth fields if missing
- 0030: Add web_accounts and auth_challenges
- 0031: Add promocode activation snapshots
- 0032: Add other device type
- 0033: Add referral identity and exchange channels
- 0034: Add branding settings
- 0035: Add promocode allowed_plan_ids
- 0036: Add web password reset flags
- 0037: Create user_notification_events
- 0038: Create web_analytics_events
- 0039: Create payment_webhook_events
- 0040: Drop legacy user auth columns
- 0041: Add web_account_credentials_bootstrapped_at
- 0042: Add more payment gateway types
- 0043: Add crypto payment assets
- 0044: Add TBank partner balance and market currencies
- 0045: Drop plan subscription_count

### 4. Версии зависимостей

| Компонент | Документация | Реальность (pyproject.toml) |
|-----------|--------------|-----------------------------|
| Python | 3.12 | 3.12 ✅ |
| FastAPI | 0.120.2+ | 0.120.2+ ✅ |
| aiogram | 3.22.0 | 3.22.0 ✅ |
| aiogram-dialog | 2.4.0 | 2.4.0 ✅ |
| SQLAlchemy | 2.0+ | 2.0+ ✅ |
| asyncpg | 0.30.0 | 0.30.0 ✅ |
| Redis | 6.4.0 | 6.4.0 ✅ |
| Taskiq | 0.11.19 | 0.11.19 ✅ |
| pydantic | 2.4.1,<2.12 | 2.4.1,<2.12 ✅ |
| pydantic-settings | 2.11.0 | 2.11.0 ✅ |
| httpx | 0.27.2,<0.28.0 | 0.27.2,<0.28.0 ✅ |
| uvicorn | 0.38.0 | 0.38.0 ✅ |
| cryptography | 46.0.3 | 46.0.3 ✅ |
| bcrypt | 4.0.0 | 4.0.0 ✅ |
| Alembic | 1.16.5 | 1.16.5 ✅ |
| dishka | 1.6.0 | 1.6.0 ✅ |
| fluentogram | 1.2.1 | 1.2.1 ✅ |
| loguru | 0.7.3 | 0.7.3 ✅ |
| msgspec | 0.19.0 | 0.19.0 ✅ |
| remnawave | 2.3.2+ | 2.3.2+ ✅ |

**Новые зависимости:**
- `greenlet>=3.2.4`
- `qrcode[pil]>=8.2`
- `python-jose[cryptography]>=3.4.0`
- `aiofiles>=24.1.0`
- `pillow>=11.0.0`

**Dev зависимости:**
- `mypy>=1.18.2`
- `ruff>=0.14.2`
- `pytest>=8.4.2`
- `watchfiles>=1.1.1`
- `ftl-extract>=0.9.0`
- `types-cachetools`

### 5. Enumerations (enums.py)

**Актуальные перечисления (40+):**

**Документированы:**
- UserRole (DEV, ADMIN, USER)
- SubscriptionStatus (ACTIVE, DISABLED, LIMITED, EXPIRED, DELETED)
- PlanType (TRAFFIC, DEVICES, BOTH, UNLIMITED)
- PlanAvailability (ALL, NEW, EXISTING, INVITED, ALLOWED, TRIAL)
- PromocodeRewardType (DURATION, TRAFFIC, DEVICES, SUBSCRIPTION, PERSONAL_DISCOUNT, PURCHASE_DISCOUNT)
- TransactionStatus (PENDING, COMPLETED, CANCELED, REFUNDED, FAILED)
- AccessMode (PUBLIC, INVITED, PURCHASE_BLOCKED, REG_BLOCKED, RESTRICTED)
- PaymentGatewayType (14 типов)
- Currency (14 валют)
- DeviceType (ANDROID, IPHONE, WINDOWS, MAC, OTHER)
- Locale (27 локалей)
- YookassaVatCode (10 кодов)

**Новые/Обновлённые:**
- ReferralRewardType (POINTS, EXTRA_DAYS)
- ReferralLevel (FIRST, SECOND, THIRD)
- ReferralInviteSource (BOT, WEB, UNKNOWN)
- PartnerLevel (LEVEL_1, LEVEL_2, LEVEL_3)
- PartnerAccrualStrategy (ON_FIRST_PAYMENT, ON_EACH_PAYMENT)
- PartnerRewardType (PERCENT, FIXED_AMOUNT)
- WithdrawalStatus (PENDING, COMPLETED, REJECTED, CANCELED)
- ReferralAccrualStrategy (ON_FIRST_PAYMENT, ON_EACH_PAYMENT)
- ReferralRewardStrategy (AMOUNT, PERCENT)
- PointsExchangeType (SUBSCRIPTION_DAYS, GIFT_SUBSCRIPTION, DISCOUNT, TRAFFIC)
- BroadcastStatus (PROCESSING, COMPLETED, CANCELED, DELETED, ERROR)
- BroadcastMessageStatus (SENT, FAILED, EDITED, DELETED, PENDING)
- BroadcastAudience (ALL, PLAN, SUBSCRIBED, UNSUBSCRIBED, EXPIRED, TRIAL)
- PurchaseType (NEW, RENEW, ADDITIONAL)
- PurchaseChannel (WEB, TELEGRAM)
- PaymentSource (EXTERNAL, PARTNER_BALANCE)
- DiscountSource (NONE, PERSONAL, PURCHASE)
- MessageEffect (FIRE, LIKE, DISLIKE, LOVE, CONFETTI, POOP)
- BannerName (DEFAULT, MENU, DASHBOARD, SUBSCRIPTION, PROMOCODE, REFERRAL)
- BannerFormat (JPG, JPEG, PNG, GIF, WEBP)
- MediaType (PHOTO, VIDEO, DOCUMENT)
- SystemNotificationType (12 типов)
- UserNotificationType (12 типов)
- UserRoleHierarchy (Enum для сравнения)
- PromocodeAvailability (ALL, NEW, EXISTING, INVITED, ALLOWED)
- CryptoAsset (11 ассетов)
- MiddlewareEventType (29 типов событий)
- RemnaUserEvent (14 событий)
- RemnaUserHwidDevicesEvent (2 события)
- RemnaNodeEvent (8 событий)
- Command (START, PAYSUPPORT, HELP)

### 6. Docker Compose

**Документация:** 8 сервисов  
**Реальность:** 8 сервисов ✅

**Актуальные сервисы:**
1. `altshop-nginx` — Nginx reverse proxy
2. `altshop-db` — PostgreSQL 17
3. `altshop-redis` — Valkey 9
4. `altshop` — Основной бэкенд
5. `altshop-taskiq-worker` — Воркер задач
6. `altshop-taskiq-scheduler` — Планировщик
7. `webapp-build` — Сборка frontend
8. `admin-backend` — Админ API (опционально)

### 7. Frontend (web-app)

**Версии:**
- React: 19.2.4 (документация: 19.2.4 ✅)
- TypeScript: 5.7 (документация: 5.7 ✅)
- Vite: 7.3.1 (документация: 6.x ⚠️)
- Tailwind CSS: 4.0 (документация: 4.0 ✅)

**Структура:**
- `src/components/ui/` — Shadcn UI компоненты (27+)
- `src/components/auth/` — Аутентификация
- `src/components/layout/` — Layout
- `src/pages/auth/` — Страницы авторизации
- `src/pages/dashboard/` — Дашборд (9 страниц)
- `src/lib/api.ts` — API клиент
- `src/lib/utils.ts` — Утилиты
- `src/stores/` — Zustand store
- `src/hooks/` — React hooks
- `src/i18n/` — Интернационализация
- `src/types/` — TypeScript типы

### 8. Тесты

**Документация:** 63 тестовых файла  
**Реальность:** 60+ тестовых файлов

**Категории тестов:**
- Платежные шлюзы (14 тестов)
- Пользователи и подписки (12 тестов)
- Веб-аутентификация (6 тестов)
- Рефералы и партнерка (5 тестов)
- Промокоды (2 теста)
- Другие (14 тестов)

---

## Требуемые обновления документации

### Критические (требуют немедленного обновления)

1. **01-project-overview.md** ✅ — ОБНОВЛЕНО
   - Актуальная структура проекта
   - 40+ сервисов вместо 14
   - 16 платежных шлюзов
   - 45 миграций

2. **03-services.md** ⏳ — ТРЕБУЕТ ОБНОВЛЕНИЯ
   - Добавить 26 новых сервисов
   - Обновить зависимости между сервисами
   - Добавить portal services

3. **04-database.md** ⏳ — ТРЕБУЕТ ОБНОВЛЕНИЯ
   - 17 таблиц вместо 18
   - 45 миграций вместо 27
   - Новые таблицы: web_accounts, auth_challenges, user_notification_events, web_analytics_events, payment_webhook_events

4. **07-payment-gateways.md** ⏳ — ТРЕБУЕТ ОБНОВЛЕНИЯ
   - 16 шлюзов вместо 10
   - Обновить статусы шлюзов
   - Добавить новые шлюзы: TBank, Stripe, Mulenpay, CloudPayments

### Важные (требуют обновления в ближайшей итерации)

5. **02-architecture.md** ⏳
   - Обновить диаграммы слоёв
   - Добавить новые middleware
   - Обновить DI контейнер

6. **05-api.md** ⏳
   - Актуальные endpoints
   - Новые endpoints для web auth
   - Portal API endpoints

7. **06-bot-dialogs.md** ⏳
   - Актуальные state groups
   - Новые диалоги
   - Обновлённые виджеты

8. **08-configuration.md** ⏳
   - Новые .env переменные
   - Обновлённые значения по умолчанию

9. **API_CONTRACT.md** ⏳
   - Parity с реальными endpoints
   - Обновлённые типы данных
   - Новые endpoints

### Менее приоритетные

10. **09-deployment.md** ⏳
    - Минорные обновления docker-compose

11. **10-development.md** ⏳
    - Обновлённый workflow
    - Новые команды Makefile

---

## План работ

### Фаза 1: Критические обновления (сделано)
- [x] 01-project-overview.md — ОБНОВЛЕНО
- [ ] 03-services.md — 40+ сервисов
- [ ] 04-database.md — 17 таблиц + 45 миграций
- [ ] 07-payment-gateways.md — 16 шлюзов

### Фаза 2: Важные обновления
- [ ] 02-architecture.md
- [ ] 05-api.md
- [ ] 06-bot-dialogs.md
- [ ] 08-configuration.md
- [ ] API_CONTRACT.md

### Фаза 3: Завершающие обновления
- [ ] 09-deployment.md
- [ ] 10-development.md
- [ ] Создание README.md для docs/

---

## Приложения

### A. Список файлов документации

**Основная документация:**
- docs/01-project-overview.md ✅
- docs/02-architecture.md ⏳
- docs/03-services.md ⏳
- docs/04-database.md ⏳
- docs/05-api.md ⏳
- docs/06-bot-dialogs.md ⏳
- docs/07-payment-gateways.md ⏳
- docs/08-configuration.md ⏳
- docs/09-deployment.md ⏳
- docs/10-development.md ⏳
- docs/API_CONTRACT.md ⏳
- docs/BACKEND_OPERATOR_GUIDE.md
- docs/PRODUCTION_DEPLOYMENT_GUIDE.md
- docs/TROUBLESHOOTING.md
- docs/SERVICE_INTEGRATION_GUIDE.md
- docs/BOT_WEB_PARITY_IMPLEMENTATION.md
- docs/WEB_APP_SETUP.md
- docs/WEB_APP_NGINX_SETUP.md
- docs/OPENAPI_GENERATION_SETUP.md
- docs/QUICK_START_API.md

**Web App документация:**
- docs/web-app/01-ui-ux-design.md
- docs/web-app/02-component-design.md
- docs/web-app/03-api-design.md
- docs/web-app/04-database-schema.md
- docs/web-app/05-getting-started.md
- docs/web-app/DEPLOYMENT.md
- docs/web-app/IMPLEMENTATION_PLAN.md
- docs/web-app/PROGRESS.md
- docs/web-app/PROJECT_SUMMARY.md

**Прочее:**
- BACKEND_AUTH_IMPLEMENTATION.md
- COMPLETE_FIX_SUMMARY.md
- QUICK_DEPLOY.md

### B. Ключевые файлы кода

**Сервисы (40+ файлов):**
```
src/services/
├── user.py
├── user_profile.py
├── user_activity_portal.py
├── subscription.py
├── subscription_device.py
├── subscription_purchase.py
├── subscription_runtime.py
├── subscription_trial.py
├── subscription_portal.py
├── plan.py
├── plan_catalog.py
├── payment_gateway.py
├── transaction.py
├── promocode.py
├── promocode_portal.py
├── referral.py
├── referral_exchange.py
├── referral_portal.py
├── partner.py
├── partner_portal.py
├── broadcast.py
├── backup.py
├── notification.py
├── user_notification_event.py
├── settings.py
├── importer.py
├── webhook.py
├── access.py
├── auth_challenge.py
├── web_account.py
├── web_access_guard.py
├── purchase_access.py
├── purchase_gateway_policy.py
├── payment_webhook_event.py
├── telegram_link.py
├── email_sender.py
├── email_recovery.py
├── command.py
├── market_quote.py
├── pricing.py
├── web_analytics_event.py
├── base.py
└── __init__.py
```

**Платежные шлюзы (16 файлов):**
```
src/infrastructure/payment_gateways/
├── base.py
├── telegram_stars.py
├── yookassa.py
├── yoomoney.py
├── cryptopay.py
├── cryptomus.py
├── heleket.py
├── pal24.py
├── platega.py
├── wata.py
├── tbank.py
├── stripe.py
├── robokassa.py
├── mulenpay.py
├── cloudpayments.py
└── __init__.py
```

**Модели базы данных (17 таблиц):**
```
src/infrastructure/database/models/sql/
├── user.py
├── subscription.py
├── plan.py
├── transaction.py
├── payment_gateway.py
├── promocode.py
├── referral.py
├── partner.py
├── settings.py
├── broadcast.py
├── web_account.py
├── auth_challenge.py
├── user_notification_event.py
├── web_analytics_event.py
├── payment_webhook_event.py
├── base.py
├── timestamp.py
└── __init__.py
```

**Миграции (45 файлов):**
```
src/infrastructure/database/migrations/versions/
├── 0001_create_enums.py
├── 0002_create_base_tables.py
├── ...
├── 0045_drop_plan_subscription_count.py
```

---

## Контакты

Для вопросов по актуализации документации обращайтесь:
- GitHub: https://github.com/snoups/remnashop
- Telegram: https://t.me/@remna_shop

---

**Последнее обновление:** 2026-03-08
