# AltShop Bot Dialogs

Проверено по коду: `2026-03-08`

Источник истины: `src/bot/states.py`

## Общая схема

Bot UI построен вокруг `aiogram-dialog` и `StatesGroup`. В коде присутствуют:

- пользовательские состояния для основного меню, подписок и partner UI
- admin/dev состояния для dashboard, access, users, backups, branding, gateway settings и importer flows
- helper `state_from_string(...)` для восстановления `State` из строкового значения

## Пользовательские state groups

| Group | Назначение | Ключевые состояния |
| --- | --- | --- |
| `MainMenu` | главное пользовательское меню | `MAIN`, `DEVICES`, `CONNECT_DEVICE`, `INVITE`, `EXCHANGE`, `EXCHANGE_*` |
| `Notification` | одношаговое закрытие уведомления | `CLOSE` |
| `Subscription` | все user-facing subscription flows | `MY_SUBSCRIPTIONS`, `SUBSCRIPTION_DETAILS`, `PROMOCODE*`, `PLANS`, `DURATION`, `PAYMENT_METHOD`, `PAYMENT_ASSET`, `CONFIRM`, `TRIAL` |
| `UserPartner` | клиентский partner portal внутри бота | `MAIN`, `REFERRALS`, `EARNINGS`, `WITHDRAW`, `WITHDRAW_CONFIRM`, `WITHDRAW_HISTORY`, `CURRENCY` |

## MainMenu detail

`MainMenu` покрывает три крупных пользовательских сценария:

1. Device management
   - `DEVICES`
   - `CONNECT_DEVICE`
   - `CONNECT_DEVICE_URL`
2. Referral UI
   - `INVITE`
   - `INVITE_ABOUT`
   - `INVITE_REFERRALS`
3. Points exchange
   - `EXCHANGE`
   - `EXCHANGE_SELECT_TYPE`
   - `EXCHANGE_POINTS`
   - `EXCHANGE_POINTS_CONFIRM`
   - `EXCHANGE_GIFT`
   - `EXCHANGE_GIFT_SELECT_PLAN`
   - `EXCHANGE_GIFT_CONFIRM`
   - `EXCHANGE_GIFT_SUCCESS`
   - `EXCHANGE_DISCOUNT`
   - `EXCHANGE_DISCOUNT_CONFIRM`
   - `EXCHANGE_TRAFFIC`
   - `EXCHANGE_TRAFFIC_CONFIRM`

## Subscription detail

`Subscription` покрывает:

- список и просмотр подписок
- удаление подписки
- ввод и применение промокодов
- выбор подписок для renew
- покупку новой подписки
- trial flow

Основные состояния:

- browsing: `MAIN`, `MY_SUBSCRIPTIONS`, `SUBSCRIPTION_DETAILS`
- deletion: `CONFIRM_DELETE`
- promocodes: `PROMOCODE`, `PROMOCODE_SELECT_SUBSCRIPTION`, `PROMOCODE_CONFIRM_NEW`
- renew selection: `SELECT_SUBSCRIPTION_FOR_RENEW`, `CONFIRM_RENEW_SELECTION`
- purchase funnel: `PLANS`, `DURATION`, `DEVICE_TYPE`, `PAYMENT_METHOD`, `PAYMENT_ASSET`, `CONFIRM`, `SUCCESS`, `FAILED`
- trial: `TRIAL`

## Admin and dashboard state groups

| Group | Назначение |
| --- | --- |
| `Dashboard` | корневой admin dashboard |
| `DashboardStatistics` | экран статистики |
| `DashboardBroadcast` | конфигурация и отправка рассылок |
| `DashboardPromocodes` | configurator промокодов и plan filter flow |
| `DashboardAccess` | access mode, rules и channel gating |
| `DashboardUsers` | поиск, recent users, blacklist, referrals |
| `DashboardUser` | детальная карточка пользователя, подписки, скидки, points, partner settings |
| `DashboardRemnashop` | системные admin разделы |
| `DashboardBackup` | backup list/manage/settings/restore/delete |
| `DashboardRemnawave` | integration view по users/hosts/nodes/inbounds |
| `DashboardImporter` | import/sync flows и assign plan |

## Remnashop-specific settings groups

| Group | Назначение |
| --- | --- |
| `RemnashopMultiSubscription` | глобальные настройки multi-subscription |
| `RemnashopBanners` | выбор, загрузка и удаление баннеров |
| `RemnashopReferral` | referral program settings и exchange configuration |
| `RemnashopPartner` | partner percentages, tax, fees, min withdrawal, review queue |
| `RemnashopGateways` | настройки payment gateways, currency и placement |
| `RemnashopNotifications` | user/system notification settings |
| `RemnashopBranding` | branding editor |
| `RemnashopPlans` | plan configurator, durations, prices, availability, squads |

## Что изменилось относительно старых описаний

- exchange flow теперь разбит на отдельные состояния для `SUBSCRIPTION_DAYS`, `GIFT_SUBSCRIPTION`, `DISCOUNT`, `TRAFFIC`
- partner UI имеет собственный `UserPartner` group
- backup, branding, multi-subscription и importer имеют отдельные admin groups
- `DashboardUser` теперь покрывает partner settings, max subscriptions и withdrawal review related screens

## Практический вывод

Если нужно искать актуальный диалог:

1. сначала определите `StatesGroup` в `src/bot/states.py`
2. затем ищите соответствующий router в `src/bot/routers/**`
3. не используйте старые frontend planning-docs как источник истины для bot flows
