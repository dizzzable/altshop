# Метрики и техдолг

Проверено по коду: 2026-04-08

## Цель и scope

Этот документ фиксирует management snapshot по cross-cutting качеству проекта: размер и форма кодовой базы, крупные зоны сложности, состояние тестового покрытия, активные маркеры техдолга, признаки dead deps / неиспользуемых артефактов и расхождения документации с текущим кодом. Scope включает backend (`src/`), frontend (`web-app/src/`), тесты (`tests/`) и рабочую документацию (`docs/`).

## Источники истины

- Backend: `src/`
- Frontend: `web-app/src/`, `web-app/package.json`, `web-app/openapi-ts.config.json`
- Тесты: `tests/`
- Документация и исторические аудиты: `docs/`, включая `docs/project-audit-2026-03-06.md`, `docs/backend-followup-2026-03-06.md`, `docs/refactor-followup-2026-03-07.md`
- Cross-check для OpenAPI generation: `docs/OPENAPI_GENERATION_SETUP.md`

## Snapshot проекта

| Срез | Ключевые метрики | Что это означает |
| --- | --- | --- |
| Backend | ~397 Python-файлов, ~75.4k LOC | Кодовая база уже крупная; основные риски сосредоточены в нескольких монолитах и сервисах-оркестраторах |
| Frontend | ~104 файлов в `web-app/src`, ~23.8k LOC | UI заметно компактнее backend, но большая часть сложности сконцентрирована в нескольких сверхкрупных страницах и словарях локализации |
| Tests | 38 test-модулей + `tests/conftest.py`, ~180 test functions | Backend покрыт точечно по критическим сценариям; frontend automated tests не найдены |
| Docs | ~56 Markdown-файлов, ~25.6k LOC | Документации много, но есть drift: часть файлов все еще описывает устаревшие auth / path / generated-client сценарии |

## Крупнейшие файлы

### Backend hotspots

| Файл | Строк | Размер | Комментарий |
| --- | ---: | ---: | --- |
| `src/services/backup.py` | 2983 | 119360 B | Самый тяжелый backend-монолит; высокий риск скрытой связности и дорогих изменений |
| `src/bot/routers/dashboard/users/user/handlers.py` | 2720 | 99043 B | Очень крупный router/handler слой, смешивает UI-flow и бизнес-правила |
| `src/bot/routers/subscription/handlers.py` | 2275 | 85713 B | Сложный subscription flow, высокая цена регрессий |
| `src/services/remnawave.py` | 1586 | 59413 B | Интеграционный сервис с высокой операционной критичностью |
| `src/services/subscription_purchase.py` | 1379 | 53895 B | Плотная бизнес-логика покупки и продления |

### Frontend hotspots

| Файл | Строк | Размер | Комментарий |
| --- | ---: | ---: | --- |
| `web-app/src/pages/dashboard/PurchasePage.tsx` | 2397 | 89232 B | Главный UI-монолит покупки; трудно безопасно менять без тестов |
| `web-app/src/pages/dashboard/SubscriptionPage.tsx` | 1904 | 72262 B | Большой stateful page с mobile/desktop ветвлениями |
| `web-app/src/pages/dashboard/SettingsPage.tsx` | 1802 | 74153 B | Смешение настроек, auth cleanup и UI state |
| `web-app/src/pages/dashboard/PartnerPage.tsx` | 1703 | 69100 B | Сложный партнерский кабинет, много условий и CTA |
| `web-app/src/i18n/locales/ru.ts` | ~1.15k | 93359 B | Крупнейший словарь локализации; рост ручного drift-риска |
| `web-app/src/i18n/locales/en.ts` | ~1.15k | 68974 B | Почти симметричный словарь; поддержка паритета остается ручной |

## Snapshot тестов

- Backend: найдено 38 test-файлов и около 180 test functions; вместе с `tests/conftest.py` файлов под `tests/` — 39
- Frontend: test/spec файлов не найдено
- Лучше всего покрыты backend-сценарии вокруг backup, auth/web-login identity, subscription/runtime, payment tasks, referral/access policy, локализации и menu rendering
- Наиболее плотные модули: `tests/services/test_backup_service.py` (29 тестов), `tests/services/test_update_release_notifications.py` (15), `tests/services/test_web_login_identity.py` (13)
- Главный gap: почти весь frontend, включая самые крупные страницы (`PurchasePage.tsx`, `SubscriptionPage.tsx`, `SettingsPage.tsx`, `PartnerPage.tsx`), не имеет автоматизированной регрессии
- Второй gap: для самых крупных backend hotspot-файлов размер и orchestration-сложность растут быстрее, чем granular service-level coverage

## TODO / FIXME / похожие маркеры

В активной части репозитория найдено около 22 маркеров (без архивных `docs/archive/*`). Из них 14 находятся в backend-коде, еще 8 — в документации.

| Путь | Маркер | Краткий смысл |
| --- | --- | --- |
| `src/services/plan.py` | `TODO` | Нет логики доступности plan по gateway |
| `src/services/plan.py` | `TODO` | Не реализована общая скидка на plan |
| `src/services/remnawave.py` | `TODO` | Временная логика остановки node/plan перед reset traffic |
| `src/services/settings.py` | `FIXME` | Явно проблемный участок обновления `user_notifications` |
| `src/services/user.py` | `TODO` | Поиск username из панели остается незавершенным |
| `src/infrastructure/database/models/dto/settings.py` | `TODO` | В DTO нет `torrent_block` |
| `src/infrastructure/database/models/dto/settings.py` | `TODO` | В DTO нет `traffic_overuse` |
| `src/infrastructure/database/models/dto/user.py` | `NOTE` | Поле `remna_name` помечено как небезопасное для чтения |
| `src/core/utils/time.py` | `TODO` | Утилита `get_uptime()` живет не на финальном месте |
| `src/bot/middlewares/base.py` | `TODO` | Не реализована проверка performance |
| `src/bot/middlewares/channel.py` | `TODO` | Нет auto-confirming логики |
| `src/bot/routers/extra/goto.py` | `TODO` | Нет перехода к конкретному типу покупки |
| `src/bot/routers/dashboard/statistics/getters.py` | `TODO` | Не разделены unlimited-режимы по traffic/device/duration |
| `src/bot/routers/dashboard/remnashop/plans/handlers.py` | `NOTE` | Поведение с несуществующими users спорное и не оформлено явно |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | `bot_username` должен браться динамически |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | Username/name должны приходить из user service |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | Есть несколько незавершенных integration sections |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | Остаются незакрытые implementation placeholders |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | Остаются незакрытые implementation placeholders |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | Остаются незакрытые implementation placeholders |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | Workaround c username join не доведен до финального решения |
| `docs/SERVICE_INTEGRATION_STATUS.md` | `TODO` | Checklist фиксирует незавершенный username join |

## Dead deps, неиспользуемые артефакты и docs drift

### Вероятные dead deps / слабосвязанные зависимости

- Во frontend есть признаки вероятно неиспользуемых runtime deps: `@hookform/resolvers`, `@radix-ui/react-avatar`, `@radix-ui/react-separator`, `@radix-ui/react-slider`, `@radix-ui/react-switch`, `@radix-ui/react-tabs`, `jwt-decode`, `react-hook-form`, `zod`, `zustand`
- Это выглядит не как доказанный мусор, а как shortlist для dependency review: прямые импорты по коду не подтверждаются, а крупные страницы написаны в основном вручную без form/store abstractions

### Неиспользуемые артефакты

- В `web-app/package.json` и `web-app/openapi-ts.config.json` настроен `openapi-ts` с output в `web-app/src/generated`, но директория `web-app/src/generated` отсутствует
- Следствие: tooling под generated client заведено, но фактически не работает как source of truth для frontend API-типов
- Это же усиливает docs drift: setup описан как доступный и полезный, но generated artifacts в дереве нет

### Docs drift

- `docs/OPENAPI_GENERATION_SETUP.md` все еще ссылается на старый путь `D:\altshop-0.9.3` и предполагает наличие `src/generated`
- `docs/TROUBLESHOOTING.md`, `docs/WEB_APP_NGINX_SETUP.md`, `docs/SERVICE_INTEGRATION_GUIDE.md` содержат примеры с `access_token` / `refresh_token` в localStorage или JSON, хотя runtime уже cookie-first
- В исторических follow-up документах уже встречаются разные backend baselines (`139 passed`, `229 passed`); это полезно как история, но без явной маркировки легко принять за актуальный operational reference

## Что изменилось с мартовских аудитов

| Статус | Пункт | Комментарий |
| --- | --- | --- |
| Закрыто | Payment webhook enqueue failure | Критичный риск марта снят; больше не выглядит активной production-проблемой |
| Закрыто | Proxy-aware IP extraction | Проблема rate-limit/IP за reverse proxy закрыта |
| Закрыто | Cookie-first auth | Публичный auth-контракт приведен к cookie-first модели |
| Закрыто | Source maps off | Замечание по production source maps закрыто |
| Закрыто | Refactor `user.py` | Самый явный endpoint-monolith был уже частично разнесен и разгружен в runtime services |
| Частично закрыто | Auth cleanup в целом | Основной переход сделан, но Bearer fallback и compatibility thinking еще не до конца вычищены |
| Частично закрыто | Backend critical stability debt | March-level emergency debt в backend заметно снижен, но service/bot hotspots все еще слишком велики |
| Осталось | Frontend tests | Автотестов frontend по-прежнему нет |
| Осталось | Bearer fallback | Полное закрытие старой token-oriented ментальной модели не завершено |
| Осталось | Docs drift | Документация частично отстает от cookie-first и от реального tree shape |
| Осталось | UI/accessibility debt | Часть accessibility-атрибутов уже есть, но крупные страницы остаются вручную собранными и сложными для системной верификации |

## Top refactor targets

| Target | Почему это приоритет |
| --- | --- |
| `src/services/backup.py` | Почти 3k строк в критичном backend-сервисе; высокий риск побочных эффектов и сложный review surface |
| `src/bot/routers/dashboard/users/user/handlers.py` | Перегруженный handler-layer, где UI-flow, orchestration и правила доступа живут слишком близко |
| `src/bot/routers/subscription/handlers.py` | Ключевой user-flow с высокой вероятностью регрессий и слабой композиционностью |
| `src/services/remnawave.py` | Интеграционный монолит; любое изменение затрагивает внешний API, rate/latency и операционную устойчивость |
| `src/services/subscription_purchase.py` | Сложная purchase/business logic; хороший кандидат на разрезание по policy/orchestration/payment state |
| `web-app/src/pages/dashboard/PurchasePage.tsx` | Самый большой frontend page-монолит; без тестов это главный UI risk surface |
| `web-app/src/pages/dashboard/SubscriptionPage.tsx` + `SettingsPage.tsx` + `PartnerPage.tsx` | Три больших stateful экрана с высокой ценой ручной проверки и accessibility drift |
| `web-app/src/i18n/locales/ru.ts` и `web-app/src/i18n/locales/en.ts` | Объем словарей уже требует более строгих automation checks, иначе локализация будет тормозить release velocity |

## Вывод

Сейчас развитие проекта тормозит уже не аварийная backend-корректность, а сочетание четырех системных факторов: отсутствие frontend regression net, большие монолитные файлы в backend и web, отстающая документация относительно текущего runtime-контракта и незавершенный cleanup вокруг generated client / legacy auth thinking. Иными словами, core backend стал заметно здоровее по сравнению с мартом, но скорость безопасных изменений упирается в низкую проверяемость frontend и в слишком крупные change surfaces по обе стороны стека.
