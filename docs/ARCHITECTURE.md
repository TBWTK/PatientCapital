---
title: Архитектура
type: architecture
status: stable
updated: 2026-08-16
---

# Архитектура

## Контекст

PatientCapital — локальное приложение с web-клиентом, Python API, PostgreSQL, MOEX ISS adapter и
общим чистым domain core. В основном потоке пользователь вводит сумму, а система сама получает
source-backed security/price/lot facts и применяет версионированную пятилетнюю policy. Пользователь
по-прежнему владеет broker fees, risk profile и фактическими BUY/SELL. Domain core рассчитывает
snapshot, drift и предложение покупок. API сохраняет входы и доказательства calculation run; web UI
и agent tools являются равноправными клиентами одного application service.

Codex работает с приложением через ограниченные tools и может объяснять результат в чате или
sub-agent flow. Это выбранная реализация допускавшегося objective agent mode; web UI не запускает
Codex и не зависит от доступности агента. Оба канала вызывают один application service независимо.
GigaChat был проверен как внешний экспериментальный provider для strict intent/explanation, но не
прошёл live quality gate и не входит в runtime. Ни один LLM не владеет данными, математикой и
исполнением.

Assistant-first MVP v2 расширяет этот контур без замены core: strategy registry собирает от одного
до трёх независимых deterministic runs в proposal set; research adapters поставляют типизированное
evidence; transaction intake создаёт подтверждаемый draft; monitor отделяет регулярное наблюдение от
редких alerts. Контракты и порядок перехода принадлежат ADR 0004 и `docs/ROADMAP.md`.

## Инварианты

- Денежные значения используют `Decimal` и явную валюту; binary float запрещён в domain/DB/API.
- План не расходует больше доступного взноса с учётом всех комиссий и cash buffer.
- Количество покупаемого актива кратно lot size; цена, lot и fee обязаны иметь источник/версию.
- Automatic discovery принимает market facts только от allowlisted MOEX HTTPS adapter; LLM output
  не может стать security master или price snapshot.
- Target weights должны быть неотрицательны и составлять ровно 100% в пределах заданного допуска.
- Отсутствующая/просроченная цена, неизвестная валюта, неполная fee policy или неоднозначная цель
  блокирует затронутый расчёт видимой ошибкой; система не подставляет удобный default.
- Один calculation run является immutable snapshot: входы, версия алгоритма, результат, причины
  пропуска и время сохраняются вместе.
- LLM не может создать/подменить asset, изменить policy/числовой результат core или пометить план
  исполненным. Материализация валидированного MOEX instrument выполняется только application service.
- `proposed` не равно `executed`: позиция меняется только после отдельной ручной записи операции.
- `extracted` не равно `confirmed`: текст, OCR или vision никогда напрямую не меняют ledger.
- Proposal set содержит только зарегистрированные и прошедшие policy gates стратегии; количество
  карточек не является целевым показателем и не дополняется LLM-вариантами.
- Research evidence имеет source URI/provider, observed/fetched time, schema/policy version и
  freshness. Непроверенный текст не материализует security fact.
- Scheduled observation не равно advisory action: monitor не создаёт transaction и не вызывает
  broker/order capability.
- Облигационная BUY хранит clean unit price, общий НКД и fee раздельно; cost-basis projection
  складывает их детерминированно и не подменяет clean price синтетической dirty unit price.
- MVP не вызывает broker order API и не обещает доходность.
- Секреты не хранятся в БД, не возвращаются API и не попадают в logs/commits.

## Компоненты и границы

| Компонент | Единственная ответственность | Поведение при отказе |
| --- | --- | --- |
| `domain` | Money, targets, positions, fees, drift, discrete allocation, reasons | typed validation/domain error; частичный правдоподобный план запрещён |
| `application` | use cases и транзакционные границы | rollback и явный failure result |
| `api` | versioned HTTP contracts и input validation | 4xx для входа, 409 для version conflict, 503 для dependency |
| `persistence` | PostgreSQL repositories и migrations | health degraded; запись не подтверждается |
| `marketdata` | allowlisted MOEX ISS transport и strict mapping в immutable candidate facts | timeout/schema/stale/unknown блокирует automatic run typed-ошибкой |
| `selection policy` | versioned eligibility, maturity/liquidity ranking и class targets | пустой eligible set блокирует proposal; LLM fallback запрещён |
| `strategy registry` | упорядоченный набор admitted policies и выбор единственной recommended | недоступная policy исключается с видимой причиной; случайная замена запрещена |
| `research` *(PC2)* | typed source adapters и immutable evidence для новых классов активов | stale/conflict/provider failure блокирует затронутую policy |
| `transaction intake` *(PC2)* | text/image extraction, resolver, unknowns и explicit confirmation | draft остаётся unconfirmed; ledger write запрещён |
| `monitor` *(PC2)* | scheduled evidence refresh и threshold/event alerts | idempotent no-op без trigger; transactions/orders недоступны |
| `web` | Обзор, Пополнить, Ассистент, Профиль и progressive-disclosure UX | сохраняет draft или показывает точную ошибку API |
| `agent tools` | узкие get/propose/record операции для Codex chat/sub-agent | те же схемы/permissions, что application service |
| `GigaChat eval adapter` | offline admission нового provider/model | любой провал оставляет runtime выключенным; deterministic result не зависит от model prose |

## HTTP API v1

| Метод | Путь | Authority / эффект |
| --- | --- | --- |
| `GET/PUT` | `/v1/profile` | latest/next immutable profile version; optimistic concurrency |
| `GET/PUT` | `/v1/assets[/{id}]` | latest/next asset/target version |
| `POST` | `/v1/assets/{id}/prices` | append-only manual price snapshot |
| `POST` | `/v1/transactions` | idempotent append-only BUY/SELL с отдельным total НКД |
| `POST` | `/v1/transaction-drafts/text` | immutable unconfirmed draft из русского текста; ledger не меняется |
| `POST` | `/v1/transaction-drafts/image` | bounded JPEG/PNG → local Tesseract → immutable draft; raw bytes удаляются |
| `POST` | `/v1/transaction-drafts/manual` | advanced exact input использует тот же draft contract |
| `GET` | `/v1/transaction-drafts/{id}` | сохранённые fields, unknowns/conflicts, confidence и decision |
| `POST` | `/v1/transaction-drafts/{id}/decisions` | explicit confirm/reject; только confirm атомарно создаёт один transaction |
| `GET` | `/v1/portfolio` | derived quantities, cost basis, value, P&L, allocation/drift |
| `GET` | `/v1/analytics/overview` | server-derived metrics/status, price freshness и recent activity |
| `POST/GET` | `/v1/recommendations[/{id}]` | calculate/store or retrieve immutable domain run |
| `POST` | `/v1/discovery/recommendations` | fetch/validate MOEX candidates, apply policy and persist deterministic proposal |
| `POST/GET` | `/v1/proposal-sets[/{id}]` | create/retrieve immutable `1..3` admitted strategy refs; ledger не меняется |
| `GET` | `/health/live`, `/health/ready` | process health отдельно от PostgreSQL readiness |

Все денежные JSON-поля сериализуются decimal-строками. Ошибка имеет один envelope
`{"error":{"code","message"}}`; transport не превращает domain unknown в HTTP 200.

## Additive API contracts PC2

Существующий `/v1` остаётся совместимым. Имена уточняются canonical OpenAPI contract test до
implementation, но capability boundaries фиксированы:

| Capability | Команда/запрос | Authority / эффект |
| --- | --- | --- |
| Proposal set *(implemented)* | `POST/GET /v1/proposal-sets[/{id}]` | сохраняет amount/profile version и `1..3` run refs; ledger не меняется |
| Transaction draft *(implemented)* | `POST text/image/manual`, `GET` by id | сохраняет extraction, resolver evidence, confidence/unknowns; transaction не создаёт |
| Draft decision *(implemented)* | `POST /{id}/decisions` с expected version | confirm принимает полный exact payload и единственный вызывает idempotent ledger command |
| Analytics overview *(implemented)* | `GET /v1/analytics/overview` | server-derived value/cost/realized/unrealized/drift/freshness/activity; unsupported cashflow/income explicit |
| Alerts | list/acknowledge | immutable monitor evidence и user acknowledgement; trade side effects отсутствуют |

Transport для image — bounded multipart upload. JPEG/PNG проверяются по MIME, magic bytes, размеру
и pixels; local Tesseract имеет timeout, а private tmpfs artifacts удаляются сразу после OCR.
OpenAPI, generated TypeScript и MCP schemas проецируют одни application contracts; ни один transport
не реализует собственную financial logic.

## Первичный аудит решений

### Что может работать

- Долгосрочное пополнение хорошо раскладывается на детерминированную задачу сведения target drift с
  дискретными лотами и комиссиями; результат можно проверить независимо.
- Delayed MOEX ISS позволяет убрать обязательный ручной ticker/price/lot input и сохранить
  provenance без broker credentials; availability/licensing остаются отдельными ограничениями.
- GigaChat технически поддерживает JSON Schema, но live eval показал, что schema compliance не
  гарантирует grounded intent/explanation. Текущая версия отклонена как runtime adapter.

### Что нельзя обещать

- Текстовая LLM не является источником котировок, не доказывает пригодность инструмента и может
  выдавать искажённые сведения; официальная документация GigaChat прямо требует проверять ответы.
- Простое предупреждение «не инвестиционная рекомендация» не устраняет возможный регулируемый
  характер персонального buy-list. До legal review продукт остаётся личным локальным прототипом.
- «Оптимальная» покупка не определена без target policy, горизонта, риска, ликвидности, налогов и
  допустимого universe. MVP оптимизирует только отклонение от введённых пользователем target
  weights в известных ограничениях и честно называет это rebalancing contribution plan.

### Stack decision

- **Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, Hypothesis, Ruff, mypy**: Python
  делает денежный domain и property tests компактными; явные модели и миграции сохраняют authority.
- **PostgreSQL**: транзакции, numeric types и JSON evidence позволяют хранить ledger и immutable
  runs в одной модели восстановления.
- **TypeScript web client**: typed contracts и зрелые chart/form primitives; frontend не повторяет
  формулы core.
- **Docker Compose**: одинаковый API/web/DB runtime для разработки и передачи.
- Тяжёлый optimizer не добавляется до eval-доказательства, что deterministic greedy baseline не
  проходит продуктовые критерии; meta-механизмом является corpus/property gate, а не библиотека.

## Основной flow

```mermaid
flowchart LR
  User["Владелец портфеля"] --> Web["Web UI"]
  Codex["Codex chat / sub-agent"] --> Tools["PatientCapital tools"]
  Web --> App["Application service"]
  Tools --> App
  App --> MOEX["MOEX ISS delayed facts"]
  MOEX --> Policy["Versioned discovery policy"]
  Policy --> App
  App --> Core["Deterministic allocation core"]
  App --> DB[("PostgreSQL ledger + snapshots")]
  Core --> Run["Immutable recommendation run"]
  Run --> Web
  Run --> Tools
  Giga["GigaChat — rejected eval-only adapter"] -.-> Gate["Offline admission report"]
```

Agent path заканчивается на MCP boundary: зарегистрированный Codex STDIO client запускает
`patientcapital-mcp`, а adapter обращается к тому же HTTP/application contract, что web. UI не
встраивает Codex app-server и не имеет скрытой кнопки, которая может инициировать сделку.

## Flow нового пополнения

```mermaid
sequenceDiagram
  participant U as Пользователь
  participant C as Web/Codex client
  participant A as Application service
  participant D as Domain core
  participant P as PostgreSQL
  U->>C: сумма пополнения
  C->>A: discover_and_propose(amount)
  A->>P: profile + positions + fees
  A->>A: validate MOEX facts + apply policy
  A->>P: append instrument/price evidence
  A->>D: immutable validated input
  D-->>A: lines + leftover + reasons + algorithm version
  A->>P: save recommendation run
  A-->>C: explainable proposal, not execution
  U->>C: фактически купленные quantities/prices
  C->>A: record transaction (separate command)
  A->>P: append ledger event
```

## Целевой assistant-first flow PC2

```mermaid
flowchart LR
  Amount["Сумма"] --> Evidence["Validated market + research evidence"]
  Evidence --> Registry["Admitted strategy registry"]
  Registry --> Runs["1..3 deterministic runs"]
  Runs --> Cards["Compact proposal cards + evidence details"]
  Cards --> Choice["Выбор стратегии"]
  Choice --> Draft["Text/image transaction draft"]
  Draft --> Confirm["Exact user confirmation"]
  Confirm --> Ledger["Immutable ledger event"]
  Ledger --> Analytics["Explainable overview"]
  Monitor["3..4 observations/day"] --> Evidence
  Monitor --> Alerts["Threshold/event alerts only"]
```

## Значимые решения

- Принята дорогая межкомпонентная граница: deterministic core — единственный владелец финансовой
  арифметики; LLM — недоверенный adapter. До стабилизации интерфейсов rationale хранится здесь;
  при принятии конкретного provider/tool protocol будет создан ADR.
- Market lookup происходит до domain calculation; валидированный ответ материализуется как
  versioned input snapshot, а network call никогда не скрыт внутри чистого allocator.
- Portfolio — производная ledger + price snapshot; recommendation никогда не мутирует ledger.

<!-- immune-project-engineering:architecture:start -->
## Технологический выбор

Stack rationale принадлежит разделу `Stack decision` выше, а alternatives — `docs/AUDIT.md`.
Ключевой trade-off: Python/Decimal/Pydantic/PostgreSQL дают компактную проверяемую financial/data
boundary, но требуют отдельного TypeScript build и не доказывают performance без benchmark. Новая
runtime technology не добавляется без требования, owner boundary и independent evidence.

## Docker-контур

| Service | Build/runtime | Dependency/health | State и exposure |
| --- | --- | --- | --- |
| `db` | pinned `postgres:17-alpine` | `pg_isready` | named volume; loopback port 55432 |
| `api` | pinned Python 3.13 slim, Tesseract rus/eng, non-root/read-only | healthy DB → Alembic head → DB readiness query | stateless; loopback port 8000; bounded OCR в `/tmp` tmpfs |
| `web` | pinned Node 22 multi-stage Vinext build, non-root/read-only | healthy API → HTTP root health | generated bundle; loopback port 3000; `/tmp` tmpfs |

Compose передаёт API application/DB/CORS, allowlisted MOEX и bounded upload/OCR config, а также
`GIGACHAT_ENABLED=false`; model keys не входят в images/environment. Browser-visible API URL
bake-time и указывает на host loopback.
`scripts/docker-smoke.sh` создаёт изолированный project/volume и доказывает full HTTP flow. Logs,
startup/shutdown, backup, destructive restore caveats, upgrade/rollback и непроверенные limits
принадлежат `docs/OPERATIONS.md`. Public rollout, SLO/alerts, HA и automatic recovery отсутствуют.
<!-- immune-project-engineering:architecture:end -->
