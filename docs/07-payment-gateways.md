# AltShop Payment Gateways

Проверено по коду: `2026-03-08`

## Сводка

В текущем коде есть 14 concrete gateway implementations и 2 инфраструктурных файла:

- concrete adapters: `cloudpayments.py`, `cryptomus.py`, `cryptopay.py`, `heleket.py`, `mulenpay.py`, `pal24.py`, `platega.py`, `robokassa.py`, `stripe.py`, `tbank.py`, `telegram_stars.py`, `wata.py`, `yookassa.py`, `yoomoney.py`
- infrastructure only: `base.py`, `__init__.py`

## Gateway infrastructure

| Файл | Роль |
| --- | --- |
| `src/infrastructure/payment_gateways/base.py` | `BasePaymentGateway`, общие helper methods и factory protocol |
| `src/infrastructure/payment_gateways/__init__.py` | registry/export concrete gateway classes |

`base.py` и `__init__.py` не являются отдельными payment providers и не должны учитываться как gateway implementations.

## Enum и currency mapping

Поддерживаемые `PaymentGatewayType`:

- `TELEGRAM_STARS`
- `YOOKASSA`
- `YOOMONEY`
- `CRYPTOMUS`
- `HELEKET`
- `CRYPTOPAY`
- `TBANK`
- `ROBOKASSA`
- `STRIPE`
- `MULENPAY`
- `CLOUDPAYMENTS`
- `PAL24`
- `WATA`
- `PLATEGA`

`Currency.from_gateway_type(...)` сейчас маппит их так:

| Gateway | Default currency |
| --- | --- |
| `TELEGRAM_STARS` | `XTR` |
| `YOOKASSA` | `RUB` |
| `YOOMONEY` | `RUB` |
| `TBANK` | `RUB` |
| `ROBOKASSA` | `RUB` |
| `MULENPAY` | `RUB` |
| `CLOUDPAYMENTS` | `RUB` |
| `PAL24` | `RUB` |
| `WATA` | `RUB` |
| `PLATEGA` | `RUB` |
| `CRYPTOMUS` | `USD` |
| `HELEKET` | `USD` |
| `CRYPTOPAY` | `USD` |
| `STRIPE` | `USD` |

## Concrete implementations

| Enum | Файл | Класс | Тип интеграции |
| --- | --- | --- | --- |
| `TELEGRAM_STARS` | `telegram_stars.py` | `TelegramStarsGateway` | Telegram invoice link |
| `YOOKASSA` | `yookassa.py` | `YookassaGateway` | redirect payment API + webhook |
| `YOOMONEY` | `yoomoney.py` | `YoomoneyGateway` | redirect token + HTML handoff |
| `CRYPTOMUS` | `cryptomus.py` | `CryptomusGateway` | crypto invoice API |
| `HELEKET` | `heleket.py` | `HeleketGateway` | invoice API + signature verification |
| `CRYPTOPAY` | `cryptopay.py` | `CryptopayGateway` | CryptoBot/CryptoPay invoice API |
| `TBANK` | `tbank.py` | `TbankGateway` | bank acquiring integration |
| `ROBOKASSA` | `robokassa.py` | `RobokassaGateway` | hosted payment + webhook |
| `STRIPE` | `stripe.py` | `StripeGateway` | Stripe-hosted payment flow |
| `MULENPAY` | `mulenpay.py` | `MulenpayGateway` | provider API adapter |
| `CLOUDPAYMENTS` | `cloudpayments.py` | `CloudPaymentsGateway` | provider API adapter |
| `PAL24` | `pal24.py` | `Pal24Gateway` | PayPalych / Pal24 adapter |
| `WATA` | `wata.py` | `WataGateway` | WATA h2h payment link adapter |
| `PLATEGA` | `platega.py` | `PlategaGateway` | Platega API adapter |

## Runtime management

`PaymentGatewayService.create_default()` создаёт записи в таблице `payment_gateways` для всех 14 enum values.

Текущие defaults:

- `TELEGRAM_STARS` создаётся `is_active=True`
- все остальные gateway records создаются `is_active=False`

Также сервис:

- нормализует legacy settings (`normalize_gateway_settings()`)
- строит concrete instance через `PaymentGatewayFactory`
- создаёт payment transactions
- завершает post-payment orchestration

## HTTP surface

### Create-payment path

Пользовательские покупки идут не напрямую в adapter, а через:

1. `SubscriptionPurchaseService`
2. `PaymentGatewayService.create_payment(...)`
3. concrete `gateway.handle_create_payment(...)`

### Incoming payment webhooks

Основной webhook surface:

- `POST /api/v1/payments/{gateway_type}`

Endpoint:

1. резолвит gateway из path
2. вызывает `handle_webhook(request)`
3. пишет dedupe record в `payment_webhook_events`
4. enqueue'ит background task на обработку транзакции

### YooMoney redirect helper

Отдельный route:

- `GET /api/v1/payments/yoomoney/redirect`

Он принимает signed redirect token, раскладывает поля формы и отдаёт HTML со встроенным auto-submit к `YoomoneyGateway.QUICKPAY_URL`.

## Settings DTO coverage

`PaymentGatewayService.create_default()` использует следующие settings DTO:

- `YookassaGatewaySettingsDto`
- `YoomoneyGatewaySettingsDto`
- `CryptopayGatewaySettingsDto`
- `TbankGatewaySettingsDto`
- `CryptomusGatewaySettingsDto`
- `HeleketGatewaySettingsDto`
- `RobokassaGatewaySettingsDto`
- `StripeGatewaySettingsDto`
- `MulenpayGatewaySettingsDto`
- `CloudPaymentsGatewaySettingsDto`
- `Pal24GatewaySettingsDto`
- `WataGatewaySettingsDto`
- `PlategaGatewaySettingsDto`

Для `TelegramStars` отдельный settings DTO не требуется.

## Практические замечания

- Канонический источник gateway type names это `PaymentGatewayType` в `src/core/enums.py`
- Канонический источник default currencies это `Currency.from_gateway_type(...)`
- Канонический источник webhook path это `src/api/endpoints/payments.py`
- Исторические документы, где считались `base.py` и `__init__.py` как "ещё 2 gateway", больше не использовать
