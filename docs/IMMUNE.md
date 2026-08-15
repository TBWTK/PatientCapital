---
title: IMMUNE — инженерные принципы
type: engineering-principles
status: stable
updated: 2026-08-15
---

# IMMUNE — инженерные принципы

Этот документ — единственный источник проектных принципов разработки. `AGENTS.md` и остальные документы ссылаются на него, а не копируют правила.

## I — Intent before implementation

Требования важнее архитектуры, архитектура важнее реализации. Если требование зафиксировано и проверяемо, модуль можно снести и восстановить по документации и тестам.

Контрольный вопрос: что сломается, если удалить файл и попросить агента написать его заново по требованиям, архитектуре и тестам? Если ответ «всё», знание жило в коде.

## M — Mutations preserve coherence

Меняется не файл, а понятие со всеми его проекциями: требования, код, схема и данные, API и события, конфигурация, Docker и эксплуатация, документация, тесты и evals, миграции, безопасность и наблюдаемость. Изменение закончено, только когда затронутые проекции снова говорят одну правду.

## M — Meta over patch

Для повторяемого класса ошибок исправлять механизм, который его порождает: контракт, генератор, валидатор, абстракцию, fixture или feedback loop. Выбирать компаунд-эффект, но не строить инфраструктуру ради единичной опечатки.

## U — Unexpected states fail loud

В неожиданном состоянии система останавливается или явно показывает неопределённость. `unknown` допустим, скрытый `unknown` — нет. Не угадывать удобный ответ и не маскировать ошибки нагромождением широких `try/except`. Обработчик исключения допустим только с явной ответственностью за восстановление, перевод ошибки, cleanup, retry или сохранение evidence.

## N — No duplicated authority, no indispensable parts

У каждой истины один владелец, у каждого решения один авторитетный модуль или документ; остальные места ссылаются или генерируются. Компонент можно заменить, не потеряв знание системы. Расширять новыми владельцами за стабильными контрактами, а не разносить право решения по старым модулям.

## E — Every state is explainable

Любое важное состояние восстанавливается по сохранённым свидетельствам: что произошло, почему, что изменилось, что проверено, что пропущено и что неизвестно. Если система не может объяснить своё состояние, она его не знает.

## Порядок разработки

`бизнес-цели и задачи → архитектурный подход → тесты и evals → разработка и код`

Этот порядок действует только вместе с IMMUNE; при конфликте IMMUNE имеет приоритет. Требование меняется только явным документированным бизнес-решением, а не подгонкой под существующий код.

## Владельцы истины в PatientCapital

| Понятие | Единственный владелец | Производные проекции |
| --- | --- | --- |
| Бизнес-границы и акторы | `docs/README.md` | root `README.md`, UI copy |
| Активная работа и evidence | `docs/STATE.md` | roadmap status, handoff summary |
| Инварианты и component boundaries | `docs/ARCHITECTURE.md` | adapters, Docker topology |
| Денежная арифметика и allocation | `src/patientcapital/domain` | API, web, MCP |
| HTTP/tool contracts | `src/patientcapital/contracts.py` и OpenAPI | generated `web/app/api-types.ts` |
| Persisted facts | Alembic migration + SQLAlchemy mappings | analytics/portfolio projections |
| Quality/admission thresholds | `docs/QUALITY.md` + versioned eval corpus | reports and release decisions |
| Эксплуатация | `docs/OPERATIONS.md` + `compose.yaml` | README quick start |

## Mutation protocol

Для изменения, пересекающего границы, до правки фиксируется compact impact map. Каждая проекция
помечается `affected` либо `not affected` с причиной:

| Проекция | Контрольный вопрос |
| --- | --- |
| Intent | Какое бизнес-правило или acceptance меняется? |
| Ownership/code | Какой owner и какие adapters проецируют решение? |
| Schema/data | Нужны ли migration, backfill, versioning, retention или recovery? |
| API/events | Меняются ли contract, generated client, compatibility или idempotency? |
| Config/Docker/ops | Меняются ли env, images, health, rollout, rollback или capacity? |
| Security | Меняются ли trust boundary, secrets, validation или abuse cases? |
| Tests/evals | Какие business, failure и non-functional proofs должны измениться? |
| Docs/agents | Какие owner documents и operational instructions затронуты? |

## Close gate

Состояние закрывается только после inspectable business evidence, relevant regression/Docker/security
checks, semantic documentation audit, чистого releasable default branch и явного списка `not run`,
`blocked` и `unknown`. Документация или coverage сами по себе завершение не доказывают.
