---
title: Аудит PatientCapital
type: audit
status: active
updated: 2026-08-16
---

# Аудит PatientCapital

## Вывод о достаточности контекста

**Sufficient для начала локального single-user Assistant-first MVP v2 без broker execution.**
Пользователь подтвердил amount-only interaction, стратегические карточки, progressive disclosure,
text/image transaction intake, richer overview, более широкий research universe и регулярное
наблюдение. ADR 0004 ограничивает опасные интерпретации: модель не владеет финансовыми фактами,
extraction не равен confirmation, наблюдение не равно сделке, а новый asset class требует policy.

Конкретный screenshot extractor и dividend-stock selection policy пока не admitted. Это не блокирует
первый product-shell checkpoint: core-карточка строится на проверенном v1. Соответствующие stages
останавливаются fail-loud, если admission/evidence не пройдены. Контекста по-прежнему недостаточно
для commercial/multi-user SaaS, broker execution, real-time feed или допуска внешней модели.

## Аудит уточнённого продуктового направления

| Предложение владельца | Решение | Ограничение реализации |
| --- | --- | --- |
| В обычном пополнении вводится только сумма | принято | профиль/holdings/fees должны быть известны; material unknown блокирует |
| Показать предложения `1..3` карточками | принято как strategy set | не генерировать три случайных ответа; одна core-карточка допустима |
| Убрать технические детали с первого слоя | принято | exact evidence остаётся доступным и accessible в details |
| Записывать операции текстом/скриншотом | принято | extraction создаёт draft; exact user confirmation обязателен |
| Удалить ручной ledger | отклонено как полное удаление | убрать из primary IA, сохранить advanced/recovery fallback |
| Искать акции и дополнительный контекст | принято по классам | typed sources + versioned policy/eval, не LLM stock picking |
| Проверять рынок `3..4` раза в день | принято как observation | alerts только по threshold/event, без auto SELL/order |
| Перекладываться ради ближайшего дивиденда | отклонено как core default | только отдельная tactical policy после cost/tax/gap/backtest/risk gate |

Основной gap не является ошибкой пользователя: текущий web действительно выдаёт один подробный run,
показывает служебные candidate fields сразу, требует dropdown ledger и ограничивает automatic policy
ОФЗ/широкими индексными фондами. Это подтверждённое расхождение v1 с новым product intent, а не
визуальный дефект одного экрана.

## Источники и доступность контекста

| Область | Статус | Источник/evidence | Влияние неизвестного | Следующее действие |
| --- | --- | --- | --- | --- |
| Бизнес-задача и ожидаемый результат | confirmed | User objective, `docs/README.md` | — | Проверять через capability/E2E evidence |
| Пользователь и operator model | confirmed | Local web tool, profile/manual ledger requirements | — | Single-user/loopback boundary сохраняется |
| Codex decision mode | confirmed | User objective; `codex mcp get patientcapital --json`; ADR 0001/0002 | — | Allowlisted MCP поверх application services; выбран chat/sub-agent path |
| GigaChat mode | confirmed | Условие «только если аудит пригодности»; live report | — | Текущую модель не подключать |
| Финансовые inputs | confirmed | Capital, five-year horizon, holdings, broker/fees из objective | — | Automatic source-backed universe; versioned policy; strict freshness |
| Market discovery | confirmed | Уточнение пользователя; controlled MOEX ISS inspection; ADR 0003 | Provider/schema/licensing failure | Delayed MOEX facts, allowlist, typed fail-closed boundary |
| Broker execution | confirmed out of scope | User не требовал execution | Proposal мог бы выглядеть как сделка | Только proposal и separate manual transaction |
| GigaChat credentials | confirmed available, secret values uninspected | Имена переменных подтверждены; `.env` ignored | Утечка или accidental runtime enablement | Env-only eval; no Compose credentials |
| Развёртывание | confirmed | Docker constraint; `compose.yaml` | — | Local loopback Compose |
| Git | confirmed | User-provided GitHub URL; explicit export approval; local/remote inspection | — | Keep verified `main` synchronized without rewriting history |
| Public/commercial compliance | unknown | `docs/SECURITY.md`, official sources in `docs/README.md` | Может изменить product/legal boundary | Public mode blocked pending legal opinion |
| Capacity/SLO/recovery rehearsal | unknown | `docs/QUALITY.md`, `docs/OPERATIONS.md` | Data loss or degraded large-ledger behavior | Visible limits; benchmark/restore before scope expands |

Допустимые статусы: `confirmed`, `inferred`, `unknown`, `not applicable`.

## Бизнес-анализ

### Проблема и желаемый исход

Владельцу долгосрочного портфеля нужен воспроизводимый ответ на вопрос «у меня есть сумма X и пять
лет — какие инструменты подходят и что купить с учётом портфеля?». Система, а не пользователь,
ищет доступные security facts и собирает source-backed universe; затем учитывает текущие BUY/SELL,
целые лоты, delayed prices, cash buffer и комиссию. Outcome — не свободный текстовый совет, а
immutable calculation run с amount, lines, evidence, fees, leftover, reason, input hash и версиями
policy/algorithm, одинаковый в web и Codex tools.
Фактическая покупка вводится отдельно и никогда не следует автоматически из proposal.

### Реализованные и целевые границы

В реализованном v1: локальный пользователь, профиль/комиссии, automatic MOEX discovery для RUB ОФЗ и
broad-index funds, versioned five-year target policy, BUY/SELL ledger, portfolio analytics,
contribution proposal, responsive web и Codex MCP. Manual asset/price entry — advanced fallback.
GigaChat входит только как admission experiment.

Целевой PC2-MVP добавляет proposal sets/cards, transaction drafts/confirmation, richer derived
analytics, admitted dividend-stock research policy и event/threshold monitoring. Не входят broker
orders, custody, return forecasts, real-time quotes, cross-currency/FX, taxes, margin/derivatives,
auth/multi-tenancy и Internet exposure.

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
| Allowlisted delayed MOEX ISS + deterministic selection policy | Нет обязательного manual universe; official machine-readable provenance | Network/schema/licensing risk, policy needs evidence | **Выбран** для local MVP; execution отсутствует |
| Broker API/full real-time feed | Точнее execution facts | Credentials, licensing, availability, execution/regulatory risk | Отклонён; не нужен для proposal MVP |
| General optimizer вместо greedy baseline | Потенциально лучше для сложных constraints | Новая authority/complexity без disconfirming evidence | Отложен; текущий algorithm проходит defined capability |
| Public Sites deployment | Удобный URL | Private API недоступен, no auth, misleading financial surface | Отклонён для local-only product |

## Рекомендация и обоснование

Развивать local deterministic product через ADR 0003 и assistant-first loop ADR 0004. MOEX ISS
получает только рыночные facts,
versioned policy владеет eligible universe/targets, а старый allocator — деньгами/лотами/fees.
Python выбран из-за `Decimal`, Pydantic/FastAPI,
SQLAlchemy/Alembic, Hypothesis и компактной реализации проверяемой financial logic; trade-off —
отдельный TypeScript web build и ограниченная raw CPU производительность, которая для MVP не
доказана проблемой. PostgreSQL владеет ledger/version/run evidence. Vinext/React даёт typed
responsive UI, но OpenAPI остаётся source contract. Docker Compose фиксирует одинаковый runtime.
Codex подключается только через MCP allowlist. GigaChat-2 не использовать; следующую модель
пропускать через неизменённый versioned admission corpus.

Codex chat/sub-agent и web остаются независимыми clients общих proposal/draft/ledger use cases.
Codex может расширять исследование источниками, но его текст не materialизуется как price, lot,
target или transaction. Coding-focused Codex runtime в web не встраивается.

## Риски и неизвестные

| Риск/unknown | Вероятность | Влияние | Проверка или mitigation | Владелец |
| --- | --- | --- | --- | --- |
| Неверный/изменённый MOEX payload | medium | high | Allowlisted TLS, strict schema/type/currency/status/freshness, snapshot evidence | marketdata + domain owner |
| Ошибочная selection policy | medium | high | Explicit version, small source-backed universe, capability fixtures, visible rationale | product + policy owner |
| Overspend/rounding/lot error | medium without controls | high | Decimal, property/boundary/capability tests | domain |
| Proposal принят за исполненную сделку | medium | high | Separate append-only command, UI/tool wording, idempotency | application/API/MCP |
| Concurrent or repeated writes | low in single-user | medium | Advisory locks, expected version, request hash/idempotency | application/DB |
| LLM hallucination/injection | high | high | LLM cannot own math; strict tools; Giga rejected | agent/eval gate |
| Credential/financial-data leak | low with local controls | high | ignored `.env`, no Compose model secrets, loopback, scans | operator/security |
| PostgreSQL volume loss | low/unknown | high | Backup procedure documented; restore rehearsal `not run` | operator |
| Ledger >10k / latency budget | unknown | medium | Explicit capacity unknown; benchmark before expansion | quality owner |
| Public personalized advice compliance | unknown | critical | Public/commercial mode blocked pending legal opinion | product/legal |
| Accidental GitHub export/history rewrite | low with controls | medium | Secret/history scan, explicit approval, normal push only; no force/rewrite | repository owner |
| Screenshot extraction ошибается | high before admission | high | Versioned corpus, confidence/unknowns, explicit full-field confirmation | transaction intake owner |
| Research prose подменяет security fact | medium | high | Typed adapters/provenance; policy consumes only validated evidence | research/policy owner |
| Частый monitor создаёт churn | medium | medium | Threshold/event rules, idempotent alerts, no transaction/order capability | monitor owner |
| Analytics смешивает market move и cash flow | medium | high | Server-owned cashflow/income fixtures; unsupported metrics explicit | portfolio query owner |

## Ландшафт проверок

Named requirement→evidence mapping принадлежит `docs/QUALITY.md`. Использованы deterministic
unit/boundary/property tests, DB migration/immutability/integration contracts, OpenAPI/generated
client drift, MCP wire/subprocess parity, component/SSR/a11y/browser journeys, Docker clean-volume
E2E, secret/dependency/container inspection и controlled live GigaChat corpus. Не выполнены и
явно оставлены `not run`: stakeholder/legal review, PostgreSQL restore rehearsal, concurrent stress,
10k-ledger capacity benchmark и mutation testing.

## Открытые вопросы и блокеры

- Какой local/external extractor проходит screenshot corpus? До admission image draft unavailable;
  text draft и PC2-1 не блокируются.
- Какие дополнительные стратегии и dividend-stock policy проходят domain review? До этого registry
  честно возвращает только существующую core strategy.
- Целевая сумма капитала и предпочтение cash income не заданы. Goal-progress/income-preference UI
  показывает `not configured` и не влияет на core proposal скрытым default.
- Какой provider/model проверять вместо GigaChat-2? Не блокирует deterministic local MVP.
- Допустима ли бесплатная delayed MOEX ISS лицензия для будущего commercial use? Не блокирует
  local single-user prototype, но блокирует публичную эксплуатацию.
- Будет ли продукт доступен другим людям или использоваться коммерчески? Любой ответ «да» открывает
  legal, identity/RBAC, privacy/retention, market-data licensing и production operations этап.

## Решение о начале реализации

`approved to start PC2-MVP locally`. Product shell можно строить поверх verified v1 немедленно;
extractor, новые strategies и monitor переходят свои gates последовательно. Public/commercial,
broker/order, real-time feed и новый LLM остаются `blocked` до отдельных requirements и evidence.
