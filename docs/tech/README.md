# Tech Audit Layer

Проверено по коду: 2026-04-08

## Назначение

`docs/tech/` — это audit-layer для текущего технического состояния AltShop. Папка не заменяет канонические документы `docs/01-10`, а дополняет их инженерной оценкой: где система сильна, где накоплен operational и architectural debt, какие зоны сейчас ограничивают скорость безопасных изменений.

Эти документы нужно читать вместе с каноническими источниками, прежде всего:

- `docs/02-architecture.md`
- `docs/05-api.md`
- `docs/09-deployment.md`
- `docs/10-development.md`

Если возникает конфликт между audit-выводом и базовым описанием системы, каноническими источниками остаются документы `docs/01-10`, а `docs/tech/` следует использовать как слой актуальной оценки и приоритизации remediation.

## Quick navigation

| Файл | Назначение |
| --- | --- |
| `docs/tech/README.md` | Навигация по audit-layer и связь с каноническими docs |
| `docs/tech/01-executive-summary.md` | Сводная оценка проекта, strengths, риски, bottleneck'и и краткая приоритизация |
| `docs/tech/02-backend-audit.md` | Детальный аудит backend-слоя, интеграций, API и тестового покрытия |
| `docs/tech/03-frontend-audit.md` | Детальный аудит `web-app`, frontend architecture, contract drift и testability |
| `docs/tech/04-infra-ops-audit.md` | Аудит Docker/compose, CI/CD, readiness, config drift и operational model |
| `docs/tech/05-metrics-and-debt.md` | Cross-cutting snapshot по размерам, hotspots, TODO/FIXME, docs drift и техдолгу |
| `docs/tech/06-remediation-roadmap.md` | Приоритизированный roadmap remediation по волнам P0/P1/P2 |

## Как читать папку

- Сначала читать `docs/tech/01-executive-summary.md` для общей картины.
- Затем переходить в профильный аудит: backend, frontend или infra/ops.
- Для оценки масштаба debt и hotspot-ов использовать `docs/tech/05-metrics-and-debt.md`.
- Для planning и sequencing изменений использовать `docs/tech/06-remediation-roadmap.md`.

## Что это за слой, а что нет

Этот слой фиксирует:

- текущие engineering findings по коду на дату проверки;
- приоритеты стабилизации и refactor-first развития;
- cross-cutting риски, которые не всегда удобно описывать в продуктовых или канонических docs.

Этот слой не предназначен для:

- замены архитектурных описаний из `docs/02-architecture.md`;
- замены API-контракта из `docs/05-api.md`;
- замены deployment/runbook материалов из `docs/09-deployment.md`;
- замены developer onboarding и рабочих практик из `docs/10-development.md`.

## Текущий смысл audit-layer

По состоянию на 2026-04-08 backend стал заметно здоровее по сравнению с мартовскими аудитами, но основное ограничение скорости изменений сместилось в четыре системные зоны:

- oversized modules в backend и frontend;
- слабый API/frontend regression net;
- infra health и config drift;
- docs/contract drift между кодом, runtime и частью документации.

Эти темы развёрнуты в `docs/tech/01-executive-summary.md` и детализированы в последующих файлах.
