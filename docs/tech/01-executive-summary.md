# Executive Summary

Проверено по коду: 2026-04-08

## Роль документа

Этот документ даёт короткую управленческую и инженерную оценку текущего состояния AltShop. Он относится к audit-layer в `docs/tech/` и должен читаться вместе с каноническими документами `docs/02-architecture.md`, `docs/05-api.md`, `docs/09-deployment.md`, `docs/10-development.md`, а не вместо них.

## Общая оценка

Проект находится в заметно более здоровом состоянии, чем в мартовских срезах. На backend уже снята часть emergency-level проблем, стек в целом зрелый, а базовые архитектурные решения по backend, web auth, Telegram/WebApp и deployment model выглядят рабочими.

Текущий профиль риска сместился: система уже меньше похожа на unstable backend under repair и больше — на продукт, которому теперь мешают крупные change surfaces, слабая регрессия на границах системы и накопившийся operational/documentation drift.

## Strengths

| Область | Сильная сторона | Почему это важно |
| --- | --- | --- |
| Backend foundation | Явный service layer, DI, зрелый application stack | Базовая архитектура уже пригодна для production evolution, а не требует полной пересборки |
| Auth/runtime | Cookie-first auth, CSRF, token versioning, refresh control | Критичный пользовательский контур собран существенно лучше, чем типичный ad-hoc SPA/API auth |
| Integrations | Remnawave startup checks, fallback и защитные механизмы уже есть | Внешняя интеграция не выглядит полностью хрупкой и уже имеет safeguards |
| Frontend platform | React/Vite/TypeScript/TanStack Query stack и lazy routing адекватны задаче | Платформенный слой frontend не является главным ограничением роста |
| Delivery baseline | Compose, image publishing, beta/stable flows и pinned base images уже существуют | У проекта есть рабочая operational база, которую нужно улучшать, а не строить с нуля |

## Что уже улучшено с марта

- Backend стал заметно здоровее по сравнению с мартом: часть критичных backend-рисков и emergency findings уже закрыта.
- Переход к cookie-first auth фактически состоялся и больше не выглядит незавершённым экспериментом.
- Критичные мартовские замечания по backend stability и отдельным integration-path больше не доминируют общую картину.
- Основной engineering debt сместился с аварийной корректности на maintainability, regression safety и operational consistency.

## Top risks

| Приоритет | Риск | Почему это сейчас главное ограничение |
| --- | --- | --- |
| P0 | Слабый regression net на API/frontend границах | Критичные status codes, cookie/CSRF contract, webhook semantics и dashboard flows плохо защищены от регрессий |
| P1 | Oversized modules в backend и frontend | Изменения дороги, review тяжелый, blast radius высокий, локализовать поломки трудно |
| P1 | Infra health и config drift | readiness, healthcheck, env/config consistency и backup/runtime semantics пока недостаточно формализованы |
| P1 | Docs/contract drift | Код, runtime и часть документации уже расходятся по auth, generated client и operational конфигурации |

## Главные bottleneck'и сейчас

### 1. Oversized modules

Ключевые backend и frontend сценарии сосредоточены в слишком крупных файлах: orchestration-сервисы, auth endpoint layer, subscription/purchase flows, тяжелые dashboard pages. Это повышает стоимость любой правки и делает безопасный refactor медленным.

### 2. Слабая проверяемость границ системы

Service-level тесты на backend уже есть, но route-level/API integration tests почти отсутствуют, а frontend automated tests не видны вовсе. В результате самое рискованное место — не отдельная функция, а поведение системы на boundary-layer.

### 3. Infra health и operational consistency

Compose/runtime уже рабочие, но app-level readiness, health semantics, config conformance, backup persistence и shared operational surfaces пока не доведены до production-grade дисциплины.

### 4. Docs и contract drift

Часть документации и tooling assumptions отстают от реального runtime: это уже не cosmetic issue, а фактор, который замедляет onboarding, integration work и изменения на стыке backend/frontend/ops.

## Сжатая приоритизация

| Волна | Фокус | Смысл |
| --- | --- | --- |
| Первая | Закрыть boundary-risk | Исправить webhook/error semantics, health/readiness gaps и добавить минимальный regression net на API/auth/frontend critical paths |
| Вторая | Уменьшить размер change surfaces | Начать декомпозицию крупнейших backend/frontend модулей и стандартизовать query/cache/contracts |
| Третья | Убрать системный drift | Свести docs, config, generated-contract/tooling и operational conventions к одному актуальному состоянию |
| Четвёртая | Укрепить платформу | Развести shared infra surfaces, улучшить observability и перевести часть remediation в устойчивые engineering practices |

## Итоговый вывод

AltShop сейчас не выглядит проектом в кризисе архитектуры. Он выглядит проектом, у которого базовая платформа уже достаточно зрелая, но скорость дальнейшего безопасного развития упирается в oversized modules, слабый API/frontend regression net, infra health/config drift и docs/contract drift. Поэтому ближайший фокус должен быть не на полной перестройке стека, а на усилении safety net, снижении change surface и выравнивании operational/documentation дисциплины.
