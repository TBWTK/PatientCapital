---
title: Текущее состояние
type: state
status: active
updated: 2026-08-16
---

# Текущее состояние

## Active objective

**`PC5-ISSUER` verified.** Versioned issuer-evidence contour связывает official
financial/dividend/governance/event facts с exact security/ISIN, сохраняет immutable source hashes
и пересчитывает dividend admission без LLM/ticker opinions как источника истины.

## Acceptance criteria

- [x] `issuer-evidence-v2` хранит exact asset/ISIN, typed issuer fields,
  source/effective/published/observed times, document hash, official event authority и conflicts;
  неверная identity, stale/missing/conflicting evidence fail closed.
- [x] `equity-dividend-quality-v2` детерминированно отделяет binding decision от proposal/comment,
  проверяет latest-due financials, profitability, dividend continuity, payout basis, balance,
  audit/governance/event coverage и никогда не использует narrative/ticker preference как gate.
- [x] Runtime scanner подключает reviewed official issuer packets после rolling liquidity screen;
  старые `market_screen`/`dividend-quality-v1` не становятся selectable, а top-N остаётся только
  ограничителем дорогого discovery enrichment.
- [x] Immutable admission identity включает hash набора issuer evidence; новый официальный факт
  может переоценить свежий market snapshot без перезаписи старого run и cache collision.
- [x] Proposal использует ровно persisted matching profiles: только `eligible`; watch/reject/unknown
  видимы с reason/source/conflict, budget не меняет issuer verdict, ledger/order/SELL не создаются.
- [x] Additive migration/API/MCP/web сохраняют текущий профиль и BUY ОФЗ 26226; corpus, regression,
  Docker/live-source и desktop browser gates проходят.

## Current verified state

- Runtime версии: `moex-board-scan-v4`, `market-liquidity-v2`, `asset-admission-v3`,
  `issuer-evidence-v2`, `equity-dividend-quality-v2`.
- Локальный portfolio содержит подтверждённую BUY `SU26226RMFS9`: `7 × 992.04`, НКД `195.16`,
  fee `3.47`, cost basis `7 142.91 RUB`; Docker migration сохранила эти факты без изменения.
- Live MOEX scan `2026-08-16`: universe `537`, admission profiles `134` = `32` ОФЗ + `3` фонда +
  `99` public equities; `36 eligible`, `97 unknown`, `1 reject`. Только exact
  `MOEX/RU000A0JR4A1` имеет succeeded reviewed packet; остальные equity fail closed.
- Browser run для `8 000 RUB` показал основной план `SU26249RMFS1` + `EQMX` + `MOEX`, evidence hash
  `a7303ee8…`, admission run `034d6656…`; `131` невыбранный profile доступен в details. Proposal не
  создал операцию, ledger по-прежнему содержит ровно одну подтверждённую BUY ОФЗ 26226.

## Changed areas

- Research schema/provider/corpus, admission policy/selection, market-intelligence cache, additive
  migration `0009`, API/MCP/web contracts, operations/docs и corpus/integration/browser tests.

## Decisions made

- Liquidity, investment admission, budget feasibility и owner exclusion — разные authorities.
- Статусы: `eligible/watch/reject/unknown`, композиция `reject > unknown > watch > eligible`.
- `market_screen` остаётся discovery-only; issuer facts требуют typed validation и primary source.
- Dividend и growth equity используют разные policies; corporate bonds fail closed до credit gate.

## Next exact step

Расширить trusted coverage вторым exact reviewed issuer packet либо подключить credentialed
NSD/Interfax adapter; до этого все остальные equity должны оставаться `unknown`.

## Blockers

- Публичный/коммерческий режим заблокирован до legal, identity, privacy и market-data licensing
  review.
- Бесплатного универсального official financial/event API без credentials не подтверждено: NSD и
  Интерфакс предоставляют typed API по ключу. PC5 начинает с reviewed primary-source packets и
  fail-closed provider boundary; open-web/LLM research остаётся discovery draft.

## Non-goals

- Broker orders, автоматическое превращение proposal в transaction, SELL/rebalance, гарантии
  доходности и LLM-owned financial facts.
- Public SaaS, auth/RBAC/multi-user, derivatives, margin, tax optimization и real-time claim.
- Прогноз цены/дивиденда, growth/sector/credit policy, универсальный valuation, arbitrary-web
  scraping и превращение слов менеджера либо мнения владельца в financial fact.

## Verification

```bash
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
python3 /Users/tbwtk/.codex/skills/immune-project-engineering/scripts/immune_project.py check . --phase docs
git diff --check
```

PC5 evidence: `280 passed`; Ruff, mypy, OpenAPI snapshot и PostgreSQL integration green; web
typecheck/build/SSR/`7` component tests/ESLint green; Docker db/api/web/monitor healthy. Desktop
browser amount-only flow показал exact v2 issuer gates и progressive details. Live DB содержит
`1` transaction, `99` immutable issuer-evidence outcomes и matching `asset-admission-v3` run;
профиль сохранил горизонт `5`, growth, Т-Инвестиции и fee `0.05%`.
