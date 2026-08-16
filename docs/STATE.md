---
title: Текущее состояние
type: state
status: active
updated: 2026-08-16
---

# Текущее состояние

## Active objective

**Active — validate `PC3-MI` ranking with real user feedback.** Dynamic Market Intelligence MVP
реализован и проверен; следующий продуктовый цикл должен решить, достаточно ли MOEX market screen
или нужен отдельный issuer-fundamentals adapter до допуска дивидендных акций.

## Acceptance criteria

- [x] Cold scan без заранее перечисленных SECID получает активные рублёвые TQOB ОФЗ и TQBR акции,
  ограничивает внешние dividend-запросы детерминированным liquidity prefilter и сохраняет exact
  source/as-of/universe counts в immutable snapshot.
- [x] `market-intelligence-v1` ранжирует доступные целые лоты: fixed-rate ОФЗ — по пятилетнему
  maturity fit, доходности и ликвидности; дивидендные акции — по listing/liquidity, подтверждённой
  истории выплат и исторической доходности, с явным scope/unknown фундаментального research.
- [x] Proposal использует snapshot не старше `4h`; при отсутствии/просрочке делает bounded live
  refresh, а provider/schema/freshness failure остаётся видимым и не откатывается к старому набору.
- [x] Один run показывает scan id/mode/time, сколько инструментов просмотрено/допущено, критерии
  выбранных активов и причины отклонения ближайших альтернатив; immutable GET воспроизводит ответ.
- [x] Worker четыре раза в день обновляет market snapshot до portfolio alert evaluation; повторный
  slot идемпотентен и никакой scan/proposal не создаёт transaction или broker order.
- [x] API, MCP и web используют один contract; web объясняет, что идёт исследование, показывает
  свежесть/охват и не обещает, что новый день обязан дать другой тикер без изменения evidence.
- [x] Additive migration сохраняет профиль, единственную BUY ОФЗ 26226, старые runs/proposal sets,
  alerts и transaction drafts; relevant unit/integration/web/Docker/live gates проходят.

## Current verified state

- `PC3-MI` реализован в `codex/market-intelligence-mvp`: dynamic TQOB/TQBR scan, top-12 dividend
  enrichment, immutable cache, ranking trace, API/MCP/web status и four-slot worker integration.
- Локальный portfolio содержит подтверждённую BUY `SU26226RMFS9`: `7 × 992.04`, НКД `195.16`,
  fee `3.47`, cost basis `7 142.91 RUB`; Docker migration сохранила эти факты без изменения.
- Live MOEX scan `2026-08-16`: universe `537`, candidates `47` = `32` ОФЗ + `3` фонда + `12`
  акций; cold scan завершился за ~3.5 s. Docker snapshot воспроизвёл те же coverage counts.
- Для `8 000 RUB`, growth, cash buffer `1 000 RUB` live Docker proposal использовал fresh cache и
  выбрал `SU26249RMFS1` / `EQMX` / `SMLT`; последний явно помечен `market_screen`, а profitability,
  payout, balance, governance и corporate actions остаются `unknown`.

## Changed areas

- ADR/docs, migration/schema, provider, deterministic policy, cache service, API/MCP, worker,
  generated TypeScript, web карточки и tests/evals изменены согласованно.

## Decisions made

- Источник universe — dynamic board enumeration, а не SECID allowlist; classification и policy
  остаются typed/versioned.
- Используется hybrid refresh: `4/day` persisted snapshot и live refresh при stale/missing cache.
- Broad-index fund classification пока остаётся reviewed registry: TQBR `IFTF` не доказывает
  underlying strategy. OFZ и dividend-stock identities не перечисляются.
- Dynamic dividend evidence называется `market_screen`; историческая выплата не является прогнозом.
- Одинаковый результат допустим только с новым/свежим evidence и сохранённым ranking trace.

## Next exact step

Собрать обратную связь по реальным предложениям для нескольких бюджетов и решить, нужен ли
issuer-fundamentals adapter как обязательный admission gate для дивидендных акций.

## Blockers

- Публичный/коммерческий режим заблокирован до legal, identity, privacy и market-data licensing
  review.
- Полный cross-source fundamental issuer audit не входит в MOEX-only PC3 screen и требует будущего
  adapter/admission gate; unknown остаётся видимым.

## Non-goals

- Broker orders, автоматическое превращение proposal в transaction, SELL/rebalance, гарантии
  доходности и LLM-owned financial facts.
- Public SaaS, auth/RBAC/multi-user, derivatives, margin, tax optimization и real-time claim.
- Arbitrary open-web crawling внутри API, прогноз будущего дивиденда и утверждение, что историческая
  дивидендная доходность является обещанной будущей доходностью.

## Verification

```bash
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
python3 /Users/tbwtk/.codex/skills/immune-project-engineering/scripts/immune_project.py check . --phase docs
git diff --check
```

Дополнительно подтверждено: `224 passed`, branch coverage `94.06%`; Ruff/mypy/OpenAPI зелёные;
web typecheck/lint `7 passed`, SSR и production build зелёные; Compose `api/db/web` healthy,
monitor создал наблюдение; desktop/mobile browser QA без console warnings/errors.
