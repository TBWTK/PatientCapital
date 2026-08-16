---
title: Текущее состояние
type: state
status: active
updated: 2026-08-16
---

# Текущее состояние

## Active objective

**`PC4-ADMISSION` complete; next objective ready — `PC5-ISSUER`.** Контур отделяет rolling market
liquidity, class-specific investment admission и budget feasibility; следующий этап — подключить
trusted typed issuer adapter для официальных отчётностей, решений и corporate events.

## Acceptance criteria

- [x] Каждый кандидат получает versioned `market_liquidity` из 20 завершённых сессий; изменение
  coverage/median turnover/spread меняет status, а перестановка входа — нет.
- [x] `market_screen` формирует только research queue и не может попасть в proposal; для акции нужен
  fresh full-quality dividend admission, а missing/stale/conflicting facts дают `unknown`.
- [x] Профиль хранит immutable gates/sources/as-of/reasons и возвращает
  `eligible/watch/reject/unknown`; только overall `eligible` участвует в allocation.
- [x] Dynamic rolling screen проверяет весь RUB TQBR universe; top-N ограничивает только дорогой
  enrichment, поэтому ФосАгро/Татнефть/Novabev-подобный актив не исключается однодневным top-12.
- [x] Существующий worker обновляет broad pool и 20-session aggregates четыре раза в день; outage/
  stale evidence остаётся видимым и не создаёт trade/order. Отдельный weekly optimization не нужен
  при текущем bounded live scan.
- [x] API, MCP и web показывают профиль, причины допуска/отказа/unknown, freshness и research queue.
- [x] Additive migration сохраняет профиль, BUY ОФЗ 26226, старые runs/proposal sets/alerts/drafts;
  domain/provider/integration/web/Docker/live gates проходят.

## Current verified state

- `PC4-ADMISSION` реализован: `moex-board-scan-v3`, `market-liquidity-v2` и
  `asset-admission-v2` разделяют research queue и selectable pool.
- Локальный portfolio содержит подтверждённую BUY `SU26226RMFS9`: `7 × 992.04`, НКД `195.16`,
  fee `3.47`, cost basis `7 142.91 RUB`; Docker migration сохранила эти факты без изменения.
- Live MOEX scan `2026-08-16`: universe `537`, admission profiles `134` = `32` ОФЗ + `3` фонда +
  `99` public equities; `35 eligible`, `98 unknown`, `1 reject`. Top-12 ограничивает только dividend
  history enrichment, а BELU/DOMRF/GAZP/OZON/PHOR/PIKK/PLZL/SMLT/TATN остаются в research queue.
- Для `8 000 RUB` run `e61ce3a1` выбрал только eligible `EQMX` и `SU26249RMFS1`; прежний дефект,
  когда `SMLT` попадал в proposal из `market_screen`, закрыт.

## Changed areas

- Добавлены domain policy, rolling MOEX history adapter, immutable admission run/assessment schema,
  API/MCP contracts, progressive web evidence и additive migration `20260816_0008`.

## Decisions made

- Liquidity, investment admission, budget feasibility и owner exclusion — разные authorities.
- Статусы: `eligible/watch/reject/unknown`, композиция `reject > unknown > watch > eligible`.
- `market_screen` остаётся discovery-only; issuer facts требуют typed validation и primary source.
- Dividend и growth equity используют разные policies; corporate bonds fail closed до credit gate.

## Next exact step

Реализовать `PC5-ISSUER`: начать с failing versioned corpus для official issuer financials,
binding/non-binding dividend events и конфликтующих primary sources; до его допуска акции остаются
`unknown`, а не выбираются по красивой истории выплат.

## Blockers

- Публичный/коммерческий режим заблокирован до legal, identity, privacy и market-data licensing
  review.
- Runtime не имеет доверенного arbitrary-web issuer adapter; open-web/LLM research остаётся draft
  до typed validation, поэтому неподтверждённые акции должны быть `unknown`, а не selected.

## Non-goals

- Broker orders, автоматическое превращение proposal в transaction, SELL/rebalance, гарантии
  доходности и LLM-owned financial facts.
- Public SaaS, auth/RBAC/multi-user, derivatives, margin, tax optimization и real-time claim.
- Прогноз цены/дивиденда, универсальный sector valuation и превращение слов менеджера либо мнения
  владельца в financial fact без source/decision validation.

## Verification

```bash
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
python3 /Users/tbwtk/.codex/skills/immune-project-engineering/scripts/immune_project.py check . --phase docs
git diff --check
```

PC4 evidence: `272 passed`, branch coverage `94.31%`; Ruff и mypy green; OpenAPI snapshot green;
web typecheck/build/SSR/`7` component tests/ESLint green; Docker api/db/web/monitor healthy;
desktop + `390×844` browser flow green, console warnings/errors `0`. Live admission run
`e7543bb8-0319-4e1d-8fdc-27063cb88720`; portfolio/profile inspection сохранила `7` ОФЗ 26226,
cost basis `7 142.91 RUB`, горизонт `5`, growth, Т-Инвестиции и fee `0.05%`.
