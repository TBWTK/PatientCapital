---
title: Аудит PatientCapital
type: audit
status: stable
updated: 2026-08-15
---

# Аудит PatientCapital

## Вывод о достаточности контекста

**Sufficient для локального single-user MVP без broker execution и внешних model decisions.**
Пользователь задал outcome, четыре обязательные поверхности, Docker/Git/Python preference,
Codex-режим, условный GigaChat-режим, credentials names и IMMUNE precedence. Неизвестные legal,
market-data licensing, identity, retention и production SLO могли бы изменить публичный продукт,
поэтому такой режим исключён, а не угадан. Контекста недостаточно для commercial/multi-user SaaS,
автоматического broker/market-data подключения или допуска другой LLM.

## Источники и доступность контекста

| Область | Статус | Источник/evidence | Влияние неизвестного | Следующее действие |
| --- | --- | --- | --- | --- |
| Бизнес-задача и ожидаемый результат | confirmed | User objective, `docs/README.md` | — | Проверять через capability/E2E evidence |
| Пользователь и operator model | confirmed | Local web tool, profile/manual ledger requirements | — | Single-user/loopback boundary сохраняется |
| Codex decision mode | confirmed | User objective; `codex mcp get patientcapital --json`; ADR 0001/0002 | — | Allowlisted MCP поверх application services; выбран chat/sub-agent path |
| GigaChat mode | confirmed | Условие «только если аудит пригодности»; live report | — | Текущую модель не подключать |
| Финансовые inputs | confirmed | Capital, targets, holdings, broker/fees из objective | — | Manual versioned facts, strict freshness |
| Broker execution/market feed | confirmed out of scope | User не требовал execution; источника котировок нет | Ошибка могла бы выглядеть как сделка/актуальная цена | Только proposal и manual price/transaction |
| GigaChat credentials | confirmed available, secret values uninspected | Имена переменных подтверждены; `.env` ignored | Утечка или accidental runtime enablement | Env-only eval; no Compose credentials |
| Развёртывание | confirmed | Docker constraint; `compose.yaml` | — | Local loopback Compose |
| Git | confirmed | User-provided GitHub URL; explicit export approval; local/remote inspection | — | Keep verified `main` synchronized without rewriting history |
| Public/commercial compliance | unknown | `docs/SECURITY.md`, official sources in `docs/README.md` | Может изменить product/legal boundary | Public mode blocked pending legal opinion |
| Capacity/SLO/recovery rehearsal | unknown | `docs/QUALITY.md`, `docs/OPERATIONS.md` | Data loss or degraded large-ledger behavior | Visible limits; benchmark/restore before scope expands |

Допустимые статусы: `confirmed`, `inferred`, `unknown`, `not applicable`.

## Бизнес-анализ

### Проблема и желаемый исход

Владельцу долгосрочного портфеля нужен воспроизводимый ответ на вопрос, как распределить очередное
пополнение с учётом целевых долей, текущих BUY/SELL facts, целых лотов, свежих цен, cash buffer и
комиссии брокера. Outcome — не текстовый совет, а immutable calculation run с amount, lines, fees,
leftover, reason, input hash и algorithm version, который одинаково доступен в web и Codex tools.
Фактическая покупка вводится отдельно и никогда не следует автоматически из proposal.

### Границы и non-goals

В scope: локальный пользователь, профиль/комиссии, assets/targets/manual prices, BUY/SELL ledger,
portfolio analytics, contribution proposal, responsive web и Codex MCP. GigaChat входит только как
admission experiment. Не входят broker orders, custody, return forecasts, automatic quotes,
cross-currency/FX, taxes, margin/derivatives, auth/multi-tenancy и Internet exposure.

## Аудит текущего состояния

- Git: verified checkpoint history на `main`; первый export выполнен после explicit approval.
  `origin/main` создан, GitHub `HEAD` указывает на него, а local/upstream SHA проверены равными.
- Domain: Decimal/immutable models, strict validation и deterministic discrete allocator; код не
  импортирует HTTP/DB/LLM.
- Data/API: одна Alembic head, PostgreSQL immutable triggers, versioned profile/assets, append-only
  prices/transactions/runs, FastAPI `/v1` и canonical OpenAPI snapshot.
- Product: Vinext/React поверхности overview/contribution/ledger/settings; browser QA desktop/mobile,
  component/SSR/a11y evidence.
- Agent: six-tool local MCP, strict arguments, HTTP parity и explicit transaction boundary.
  `codex mcp list` и `codex mcp get patientcapital --json` подтверждают enabled STDIO registration,
  указывающую на `.venv/bin/patientcapital-mcp` этого repository. Официальная документация Codex
  описывает тот же shared config/CLI inspection contract: <https://developers.openai.com/codex/mcp>.
- Model audit: `GigaChat-2:2.0.30.01` дал 100% schema parse, но 0% explanation grounding/safety и
  20% intent accuracy; runtime mode отсутствует.
- Docker: pinned non-root/read-only API/web images, Postgres volume, loopback ports, migration/health
  ordering и isolated clean-volume smoke.
- Verification: 84 Python tests, 95.45% branch coverage, Ruff/mypy/build, web tests/type/lint/build,
  Docker smoke, dependency/secret/container checks. Exact evidence и unknown находятся в `STATE.md`
  и `QUALITY.md`.

## Архитектурные варианты

| Вариант | Сильные стороны | Риски/стоимость | Соответствие требованиям |
| --- | --- | --- | --- |
| Детерминированный Python core + PostgreSQL/API/web/MCP adapters | Exact money, explainability, one math authority, channel parity | Больше contract/migration работы, manual inputs | **Выбран**; покрывает local MVP |
| LLM самостоятельно выбирает покупки | Быстрый conversational prototype | Hallucination, non-reproducible math, prompt injection, no evidence | Отклонён: нарушает IMMUNE/financial invariants |
| Spreadsheet-only | Низкий startup cost, понятная ручная модель | Слабая versioning/idempotency/audit/tool integration | Недостаточно для requested web/agent/runtime |
| Broker/market-data integration сразу | Меньше manual entry | Credentials, licensing, availability, execution/regulatory risk | Отклонён до отдельного requirements/audit этапа |
| General optimizer вместо greedy baseline | Потенциально лучше для сложных constraints | Новая authority/complexity без disconfirming evidence | Отложен; текущий algorithm проходит defined capability |
| Public Sites deployment | Удобный URL | Private API недоступен, no auth, misleading financial surface | Отклонён для local-only product |

## Рекомендация и обоснование

Сохранять local deterministic product. Python выбран из-за `Decimal`, Pydantic/FastAPI,
SQLAlchemy/Alembic, Hypothesis и компактной реализации проверяемой financial logic; trade-off —
отдельный TypeScript web build и ограниченная raw CPU производительность, которая для MVP не
доказана проблемой. PostgreSQL владеет ledger/version/run evidence. Vinext/React даёт typed
responsive UI, но OpenAPI остаётся source contract. Docker Compose фиксирует одинаковый runtime.
Codex подключается только через MCP allowlist. GigaChat-2 не использовать; следующую модель
пропускать через неизменённый versioned admission corpus.

Из допускавшихся objective вариантов выбран **Codex chat/sub-agent → MCP tools**, а не запуск
агента из web UI. Web и Codex остаются независимыми равноправными clients: это исключает скрытый
agent side effect из пользовательской кнопки и сохраняет одно application/domain authority.

## Риски и неизвестные

| Риск/unknown | Вероятность | Влияние | Проверка или mitigation | Владелец |
| --- | --- | --- | --- | --- |
| Неверный manual price/target | medium | high | Source/as-of/freshness, strict weights, visible blocked run | domain + data owner |
| Overspend/rounding/lot error | medium without controls | high | Decimal, property/boundary/capability tests | domain |
| Proposal принят за исполненную сделку | medium | high | Separate append-only command, UI/tool wording, idempotency | application/API/MCP |
| Concurrent or repeated writes | low in single-user | medium | Advisory locks, expected version, request hash/idempotency | application/DB |
| LLM hallucination/injection | high | high | LLM cannot own math; strict tools; Giga rejected | agent/eval gate |
| Credential/financial-data leak | low with local controls | high | ignored `.env`, no Compose model secrets, loopback, scans | operator/security |
| PostgreSQL volume loss | low/unknown | high | Backup procedure documented; restore rehearsal `not run` | operator |
| Ledger >10k / latency budget | unknown | medium | Explicit capacity unknown; benchmark before expansion | quality owner |
| Public personalized advice compliance | unknown | critical | Public/commercial mode blocked pending legal opinion | product/legal |
| Accidental GitHub export/history rewrite | low with controls | medium | Secret/history scan, explicit approval, normal push only; no force/rewrite | repository owner |

## Ландшафт проверок

Named requirement→evidence mapping принадлежит `docs/QUALITY.md`. Использованы deterministic
unit/boundary/property tests, DB migration/immutability/integration contracts, OpenAPI/generated
client drift, MCP wire/subprocess parity, component/SSR/a11y/browser journeys, Docker clean-volume
E2E, secret/dependency/container inspection и controlled live GigaChat corpus. Не выполнены и
явно оставлены `not run`: stakeholder/legal review, PostgreSQL restore rehearsal, concurrent stress,
10k-ledger capacity benchmark и mutation testing.

## Открытые вопросы и блокеры

- Какой provider/model проверять вместо GigaChat-2? Не блокирует deterministic local MVP.
- Будет ли продукт доступен другим людям или использоваться коммерчески? Любой ответ «да» открывает
  legal, identity/RBAC, privacy/retention, market-data licensing и production operations этап.

## Решение о начале реализации

`approved for local MVP only`. Context/intent/architecture/verification gates достаточны для
single-user loopback tool без execution. Public/commercial, broker/market integrations и новый LLM
остаются `blocked` до отдельных requirements и evidence.
