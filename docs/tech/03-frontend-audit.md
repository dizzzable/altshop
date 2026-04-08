# Frontend Tech Audit

Проверено по коду: 2026-04-08

## Цель и scope

Этот документ фиксирует аудиторский слой поверх существующей документации по `web-app`: не повторяет setup и onboarding, а оценивает текущее техническое состояние frontend, устойчивость контрактов, DX и риски дальнейшего развития.

В scope входят:

- архитектура `web-app` и границы ответственности;
- интеграция с backend API и Telegram WebApp;
- состояние data-fetching, state management, routing, i18n и UI-слоя;
- maintainability, performance, accessibility и testability;
- признаки documentation drift и вероятные неиспользуемые зависимости.

## Источники истины

Основные источники истины для frontend-аудита:

- код приложения в `web-app/src`;
- зависимости и скрипты в `web-app/package.json`;
- сборочная конфигурация в `web-app/vite.config.ts`;
- текущий Axios/API слой в `web-app/src/lib/api.ts`;
- маршрутизация и lazy-loading в `web-app/src/App.tsx`;
- Telegram runtime integration в `web-app/src/main.tsx` и `web-app/src/hooks/useTelegramWebApp.ts`.

Вторичные, частично исторические источники, в которых уже заметен drift относительно runtime:

- `web-app/README.md`;
- `web-app/AUTH_SYSTEM.md`;
- `docs/OPENAPI_GENERATION_SETUP.md`.

## Executive Summary

`web-app` стоит на современном и в целом адекватном стеке: React 19, Vite 7, TypeScript, React Router 7, TanStack Query 5, Axios, Tailwind 4, Radix/shadcn. Базовый platform layer выглядит зрелее, чем feature layer: особенно хорошо собраны auth/session handling, cookie auth с CSRF, refresh singleflight и Telegram WebApp bootstrap.

Главный технический долг сосредоточен не в foundation, а в feature pages и контрактной дисциплине. Несколько dashboard-страниц разрослись до 1.7k-2.4k LOC, query keys и invalidation управляются в основном вручную, frontend test harness отсутствует, а документация и OpenAPI-источники отстают от реального cookie-first runtime. Это делает код рабочим, но дорогим в сопровождении и рискованным для дальнейших изменений.

## Оценка архитектуры `web-app`

### Общая картина

Архитектура ближе к pragmatic SPA с сильным app-shell и тяжелыми page-level контейнерами:

- entrypoint и platform bootstrap находятся в `web-app/src/main.tsx`;
- router, lazy routes и auth/layout composition находятся в `web-app/src/App.tsx`;
- API-доступ централизован в `web-app/src/lib/api.ts`;
- состояние в основном опирается на TanStack Query и локальный `useState`, без заметного реального использования глобального store;
- UI primitives вынесены в `web-app/src/components/ui`, но feature composition часто остается внутри самих страниц.

### Вердикт

Архитектура жизнеспособна и уже содержит правильные базовые решения, но сейчас упирается в page-bloat. У проекта хороший нижний слой и слабее выраженный средний слой: между `lib/api.ts`/hooks и крупными страницами не хватает feature modules, query factories, form models и переиспользуемых orchestration-компонентов.

## Сильные стороны stack и интеграций

### Foundation и integration strengths

- `web-app/src/lib/api.ts` реализует зрелый Axios client с `withCredentials`, CSRF header injection, централизованной обработкой ошибок и refresh singleflight; это сильная база для cookie-first auth.
- Cookie auth реализован лучше, чем это обычно бывает в SPA: есть очистка legacy storage, защита unsafe methods через CSRF и сериализация refresh-потока через общий promise, что снижает race conditions.
- Telegram WebApp integration собрана осознанно: `web-app/src/main.tsx` поднимает Telegram runtime до рендера, прокидывает theme params и safe area insets, а `web-app/src/hooks/useTelegramWebApp.ts` аккуратно работает с готовностью, viewport и launch context.
- Маршруты в `web-app/src/App.tsx` лениво грузятся, а популярные authenticated routes дополнительно prefetch'ятся в idle-time; это хороший компромисс между TTI и perceived responsiveness.
- Текущий стек сам по себе современный и поддерживаемый: React 19 + Vite 7 + TypeScript + TanStack Query 5 + Tailwind 4 + Radix/shadcn дают нормальную платформу для дальнейшего refactor-first развития.

## Слабые места и риски

### Maintainability

- Основной риск - oversized page components. Логика загрузки данных, мутаций, derived state, UI-композиция и локализационный текст часто смешаны внутри одной страницы.
- Query keys и invalidation-паттерны не стандартизованы. В коде встречаются вручную прописанные строковые ключи вроде `['subscriptions']`, `['user-profile']`, `['partner-info']`, `['promocode-activations']`; это работает, но плохо масштабируется и создает риск contract drift между фичами.
- Между `lib/api.ts` и page-level UI мало промежуточных feature hooks/queries/commands. Из-за этого orchestration живет прямо в страницах и плохо переиспользуется.

### DX

- В `web-app/package.json` нет test runner и нет test scripts; по коду не видны `vitest`, `jest`, `playwright` или `cypress` конфиги. Разработка сейчас опирается почти только на lint/type-check/manual QA.
- Есть риск неверного чтения устаревших документов как актуальных: исторический `web-app/README.md` все еще описывает Zustand, React Hook Form/Zod, Vite 6 и JWT/localStorage auth, а `web-app/AUTH_SYSTEM.md` описывает возврат JWT токенов и refresh body, что уже не соответствует cookie-first реализации.
- OpenAPI setup описан и npm-скрипт `generate:api` существует, но каталога `web-app/src/generated` нет. То есть автоматизированный contract-sync задекларирован, но не встроен в текущий рабочий процесс.

### Performance

- Lazy routes уже помогают, но большие page-файлы затрудняют более тонкое code splitting на уровне feature sections, dialogs, tables и transactional flows.
- Большие locale-файлы тоже увеличивают стоимость навигации и review-нагрузку; i18n-слой сейчас скорее монолитный, чем модульный.
- В `web-app/src/hooks/useTelegramWebApp.ts` есть poll/retry логика для ожидания Telegram runtime. Это оправдано, но требует дисциплины по instrumentation и bounds, чтобы не создавать лишнюю фоновую активность при edge-сценариях.

### Accessibility

- В проекте есть качественные Radix primitives, что создает хороший baseline для accessible UI.
- При этом отсутствие frontend tests и визуально-семантических проверок означает, что реальное состояние keyboard navigation, focus management, aria-label coverage и toast/notification announcements ничем системно не защищено.
- По `sonner` видны активные вызовы `toast(...)`, но точка монтирования `Toaster` по быстрому обзору не обнаружена. Это не доказанный runtime bug, а проверочный пункт: если `Toaster` действительно не смонтирован, часть feedback UX и screen-reader announcement path может не работать.

### Contract drift

- Самый заметный drift уже между кодом и docs: runtime ушел в cookie-first auth, docs частично остались в token-first модели.
- Типы API в `web-app/src/types/index.ts` поддерживаются вручную, а не generated client'ом; при активном backend development это увеличивает риск тихого расхождения форматов.
- Инвалидация query-кеша по строковым ключам дополнительно усиливает риск скрытых контрактных ошибок после backend/frontend изменений.

## Самые крупные frontend-файлы

Крупнейшие файлы, влияющие на поддерживаемость:

- `web-app/src/pages/dashboard/PurchasePage.tsx` - 2396 LOC;
- `web-app/src/pages/dashboard/SubscriptionPage.tsx` - 1903 LOC;
- `web-app/src/pages/dashboard/SettingsPage.tsx` - 1801 LOC;
- `web-app/src/pages/dashboard/PartnerPage.tsx` - 1702 LOC;
- `web-app/src/i18n/locales/en.ts` - около 1.15k LOC;
- `web-app/src/i18n/locales/ru.ts` - около 1.15k LOC.

Почему это проблема:

- ухудшается reviewability: одно изменение затрагивает слишком много контекста;
- растет риск побочных эффектов при правках mutation flows, условного рендера и query invalidation;
- падает переиспользуемость: логика не извлекается в composable hooks/components;
- усложняется тестирование: даже при добавлении test harness такие страницы будет трудно покрывать адресно;
- локали в виде крупных монолитов повышают вероятность пропуска ключей, дублирования и конфликтов при merge.

## Оценка data-fetching, state и routing

### Data fetching

TanStack Query используется как основной data layer и это правильный выбор. Базовые паттерны хорошие: есть отдельные hooks вроде `web-app/src/hooks/useSubscriptionsQuery.ts` и `web-app/src/hooks/useAccessStatusQuery.ts`, есть lazy routes, есть разумные `staleTime` и controlled refetching.

Проблема в том, что дисциплина применения непоследовательна:

- часть query logic вынесена в hooks, часть остается внутри страниц;
- query keys не оформлены в factories/constants;
- invalidation часто перечисляется вручную списками после мутаций;
- нет единого слоя feature queries/commands, который бы кодировал инварианты кэша.

Итог: data-fetching слой функционален, но пока недостаточно стандартизован для безопасного роста.

### State management

Фактическое состояние приложения сейчас опирается на React state + TanStack Query. Это выглядит проще и полезнее, чем тащить глобальный store без необходимости.

При этом `zustand` заявлен в зависимостях и даже учитывается в `web-app/vite.config.ts`, но по быстрому коду реального использования не видно. Это косвенно подтверждает, что текущая архитектура уже живет без явного client-state store, а package/deploy surface остался шире реальной потребности.

### Routing

Routing в `web-app/src/App.tsx` в хорошем состоянии:

- routes разделены на public/protected;
- используется lazy-loading по страницам;
- есть post-login redirection logic;
- для dashboard есть nested routing через layout.

Ограничение здесь скорее не в router, а в том, что route boundaries слишком крупные: каждая большая страница остается одним heavy entry chunk для своей фичи.

## Состояние тестирования и риски отсутствия test harness

На frontend сейчас не видно рабочего test harness:

- нет `vitest`/`jest`/`playwright`/`cypress` конфигурации;
- не найдены `*.test.*` или `*.spec.*` файлы в `web-app`;
- в `web-app/package.json` отсутствуют test scripts.

Риски такого состояния:

- регрессии в cookie auth, refresh, protected routing и Telegram integration будут ловиться поздно и вручную;
- refactor крупных страниц почти неизбежно будет тормозиться страхом сломать продовые сценарии;
- accessibility и error-handling остаются непроверяемыми на системном уровне;
- contract drift между backend и frontend не имеет быстрого smoke-слоя.

Минимально необходимый baseline: unit/integration tests для `lib/api.ts`, auth flows, route guards, query hooks и smoke tests для ключевых dashboard-сценариев.

## Dead deps и неиспользуемые артефакты

По быстрому аудиту легко видны вероятные кандидаты на cleanup:

- `jwt-decode` - присутствует в dependencies и chunking rules, но импортов в `web-app/src` не видно;
- `react-hook-form` - заявлен, но импортов в `web-app/src` не видно;
- `@hookform/resolvers` - заявлен, но импортов в `web-app/src` не видно;
- `zod` - заявлен, но импортов в `web-app/src` не видно;
- `zustand` - заявлен и выделен в vendor chunk, но использование в `web-app/src` не видно;
- часть Radix deps (`@radix-ui/react-separator`, `@radix-ui/react-slider`, `@radix-ui/react-switch`, `@radix-ui/react-tabs`) по быстрому поиску не выглядит используемой.

Неиспользуемые артефакты и structural drift:

- `web-app/src/generated` отсутствует, хотя генерация клиента описана в docs и scripts;
- `web-app/README.md` - исторический файл с устаревшими утверждениями о структуре проекта, сторе и auth model;
- `web-app/AUTH_SYSTEM.md` документирует уже неактуальный JWT/localStorage контракт.

Это нужно трактовать как кандидатов на подтверждение и cleanup, а не как автоматически безопасное удаление без финального dependency audit.

## Приоритизированные findings

### P1

- P1. Oversized dashboard pages создают главный bottleneck по maintainability и безопасному refactoring: `PurchasePage.tsx`, `SubscriptionPage.tsx`, `SettingsPage.tsx`, `PartnerPage.tsx` уже слишком крупные для предсказуемой эволюции.
- P1. Frontend test harness отсутствует; критические сценарии auth, Telegram WebApp и dashboard mutation flows не защищены автоматическими проверками.
- P1. Documentation/runtime drift по auth и frontend stack уже материален: исторический `web-app/README.md` и `web-app/AUTH_SYSTEM.md` могут быть ошибочно прочитаны как актуальные и ввести в заблуждение относительно cookie-first runtime и реально используемых библиотек.

### P2

- P2. Query key/invalidation pattern непоследователен; вручную управляемые ключи и массовые invalidate-списки будут все чаще давать кэш-рассинхрон и хрупкие побочные эффекты.
- P2. OpenAPI generation задекларирован, но generated client отсутствует; ручные типы и ручной API слой повышают риск contract drift с backend.
- P2. Вероятные dead deps расширяют bundle/governance surface и маскируют реальную архитектуру проекта.

### P3

- P3. Монолитные locale-файлы ухудшают reviewability и осложняют локализационный контроль качества.
- P3. По `sonner` нужен явный confirm-check на наличие `Toaster`; сейчас это не подтвержденная ошибка, но полезный reliability/accessibility checkpoint.
- P3. Current route-level lazy-loading уже есть, но finer-grained splitting внутри тяжелых страниц пока ограничен их структурой.

## Quick wins

- Вынести query keys в единый `queryKeys`/factory layer и убрать строковые ключи из page-level кода.
- Добавить базовый frontend test stack: `vitest` + Testing Library для unit/integration и хотя бы один smoke e2e-контур для auth/dashboard.
- Обновить `web-app/README.md` и `web-app/AUTH_SYSTEM.md` под текущую cookie-first модель, реальный stack и фактическую структуру проекта.
- Провести dependency audit и удалить подтвержденные unused deps после проверки lockfile/build.
- Проверить и явно задокументировать mount-point для `sonner`.
- Разбить locale-монолиты по доменам или namespaces, сохранив текущий runtime API.

## Refactor-кандидаты

- `web-app/src/pages/dashboard/PurchasePage.tsx` - первый кандидат на декомпозицию в feature sections, pricing/purchase hooks, payment option blocks и query command layer.
- `web-app/src/pages/dashboard/SubscriptionPage.tsx` - вынести subscription actions, promocode activation, usage widgets и mutation handling в отдельные модули.
- `web-app/src/pages/dashboard/SettingsPage.tsx` - отделить account profile, Telegram linking, password reset и operation history в самостоятельные feature-компоненты/hooks.
- `web-app/src/pages/dashboard/PartnerPage.tsx` - разделить overview, earnings, referrals, withdrawals и payout actions.
- `web-app/src/lib/api.ts` - не требует срочного переписывания, но вокруг него стоит построить generated-contract layer или typed adapters, а не продолжать разрастание page-level API orchestration.

## Рекомендуемая последовательность действий

1. Сначала закрыть P1 по test harness и page decomposition strategy.
2. Затем стандартизовать query keys/invalidation и решить, внедряется ли generated OpenAPI client полностью или частично.
3. После этого зачистить docs drift и dead deps, чтобы документация и dependency graph снова отражали реальное состояние `web-app`.
