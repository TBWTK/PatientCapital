---
title: Текущее состояние
type: state
status: active
updated: 2026-08-16
---

# Текущее состояние

## Active objective

**In progress — Assistant-first MVP v2 (`PC2-MVP`).** Превратить проверенный amount-only v1
в лаконичный продуктовый цикл `сумма → выбор стратегии → подтверждение исполнения → обновлённая
аналитика`, добавить source-backed расширение universe и наблюдение без автоматической торговли.

## Acceptance criteria

- [x] Один денежный input создаёт immutable proposal set из `1..3` зарегистрированных стратегий;
  одна допустимая карточка помечена рекомендуемой, а отсутствующие варианты не выдумываются.
- [x] Карточка сначала показывает действие, обоснование, вложенную сумму/остаток и риски; security,
  lot/price/fee, freshness, sources, rejected candidates и policy/run versions скрыты в доступном
  progressive-disclosure блоке.
- [x] LLM/search может добавлять цитируемый research context, но инструмент, цена, lot, target,
  quantity, fee и totals материализуются только после typed validation и deterministic calculation.
- [x] Свободный текст и поддержанное изображение создают unconfirmed transaction draft. Перед
  записью пользователь подтверждает side, resolved asset, quantity, clean unit price, НКД, fee,
  currency и timezone-aware occurred_at; неизвестность блокирует confirm.
- [x] Proposal line никогда не превращается в transaction автоматически; advanced manual editor
  остаётся recovery fallback и использует тот же confirmation/validation contract.
- [x] Обзор объясняет капитал: market value, contributions/cost basis, realized/unrealized result,
  income, allocation/drift, freshness и recent activity. Неподдерживаемая метрика показывается как
  `unknown/not configured`, а не рассчитывается правдоподобной заглушкой.
- [x] Новый asset class допускается только отдельной versioned research/selection policy и eval.
  Dividend-stock policy проверяет фундаментальные, дивидендные, liquidity, governance,
  corporate-action и concentration facts; dividend capture не является core default.
- [x] Monitor собирает данные `4` раза в день, но создаёт alert только по
  зарегистрированному событию или threshold; SELL и broker order никогда не выполняются самими.
- [x] Web использует четыре основных раздела — Обзор, Пополнить, Ассистент, Профиль — и проходит
  desktop/mobile, keyboard, screen-reader, error-recovery и sensitive-upload проверки.
- [ ] Schema/API/MCP/data/retention/security/Docker/docs обновлены согласованно; migration совместима
  с существующим ledger, full regression и isolated Docker E2E проходят на releasable `main`.

## Current verified state

- `PC2-1 Product shell` завершён: `POST/GET /v1/proposal-sets`, immutable `proposal_sets`, registry
  только из admitted strategies, API/MCP parity и compact-first web-карточка поверх неизменённого
  v1 deterministic run.
- `PC2-2 Transaction assistant` завершён: text/manual/image создают immutable unconfirmed draft;
  exact confirm атомарно создаёт один ledger event; reject не меняет positions. HTTP/OpenAPI/web и
  MCP используют один application contract.
- Реальный supplied T-Invest JPEG допущен в Docker: local Tesseract точно извлёк ОФЗ 26226, 7,
  992.04, НКД 195.16, fee 3.47 и timezone-aware время; `/tmp` после ответа пуст.
- `PC2-3 Analytics` завершён: `analytics-ledger-v1` возвращает typed metric status, market/cost,
  realized/unrealized result, freshness, allocation и recent activity. Неподдерживаемые cashflow и
  income остаются `not_configured`, не нулём.
- `PC2-4 Research universe` завершён: `five-year-moex-v2` композиционно использует
  `dividend-quality-v1`; акция MOEX допускается только для профиля «рост» с cap `20%` после typed
  profitability/dividend/coverage/balance/liquidity/governance/corporate-action/freshness gates.
  Primary citations и server-owned summary входят в immutable run, но calculation получает только
  validated ISS security/price/lot и deterministic target.
- Локальный portfolio содержит подтверждённую BUY `SU26226RMFS9`; его числовая evidence не должна
  измениться при migration v2.
- `PC2-5 Monitoring` завершён: `monitor-threshold-v1`, четыре московских слота, immutable
  run/alert/acknowledgement, daily dedupe, явный provider-error и API/MCP/web read/ack surfaces.
  Worker не импортирует transaction/order use case.
- Оставшийся product-gap: финальный cross-surface/Git handoff audit.
- PC2-1 evidence 16.08.2026: `145 passed`, branch coverage `94.23%`; Ruff/mypy/OpenAPI; web build,
  typecheck, lint, SSR, `4` component tests + axe; MCP/API/migration tests; healthy Compose; browser
  desktop `1440px` и mobile `390px` без horizontal overflow.
- PC2-2 evidence 16.08.2026: `162 passed`; Ruff/mypy/OpenAPI; web build, typecheck, lint, SSR,
  `6` component tests + axe; `19` focused API/MCP/migration/config tests; healthy Compose; exact real
  OCR admission and browser incomplete-draft/disabled-confirm inspection.
- PC2-3 evidence 16.08.2026: `164 passed`; exact BUY→SELL realized fixture, stale freshness,
  API/MCP parity; web build/typecheck/lint/SSR/`6` component tests + axe; healthy Docker and browser
  inspection of current portfolio analytics/recent BUY.
- PC2-4 evidence 16.08.2026: `191 passed`, branch coverage `94.12%`; Ruff/mypy/OpenAPI/generated TS;
  web build/typecheck/lint/SSR/`6` component tests + axe; healthy Compose; controlled live MOEX run
  returned OFZ `40%`, broad-index fund `40%`, dividend stock MOEX `20%`, spent `6 914.15 RUB` from
  `8 000 RUB` after the configured buffer, and created `0` transactions. Browser exposed research
  only inside nested details with four primary citations. Existing OFZ 26226 stayed `7` units,
  cost basis `7 142.91 RUB`, market value `7 143.71 RUB`, unrealized `0.80 RUB`.
- PC2-5 evidence 16.08.2026: `214 passed`, branch coverage `94.49%`; Ruff/mypy/OpenAPI/generated TS;
  web build/typecheck/lint/SSR/`7` component tests + axe; migrations `20260816_0005..0006`; healthy Compose
  с отдельным worker. Live worker сохранил threshold alert для `SU26226RMFS9`, создал `0`
  transactions; browser показал compact alert и exact evidence. Ledger остался одной BUY:
  `7 × 992.04`, НКД `195.16`, fee `3.47`, cost basis `7 142.91 RUB`.

## Changed areas

- `monitor-threshold-v1`, worker schedule, additive immutable monitor schema, API/MCP alert surfaces,
  Assistant observation UI и Docker monitor role.

## Decisions made

- Пользователь выбирает стратегию; алгоритм и его версия остаются техническим evidence.
- Proposal set содержит от одной до трёх реально зарегистрированных стратегий, а не обязательные
  три случайных тикера или LLM-ответа.
- Текст/OCR/vision создаёт только draft; ledger меняется после отдельного явного confirmation.
- Частое наблюдение отделено от редкого threshold/event-driven предложения; автоторговли нет.
- Расширение universe выполняется policy-by-policy; текущая безопасная core policy не ослабляется.
- Dividend-stock class пока допускается только для профиля «рост», не более `20%`; отсутствие или
  просрочка любого research gate исключает акцию, а не вызывает LLM fallback.

## Next exact step

Завершить `PC2-MVP handoff`: выполнить full web/Python/docs/IMMUNE/Git gates, isolated Docker
migration smoke, подтвердить clean releasable branch и синхронизировать `main` с `origin/main`.

## Blockers

- Новые dividend-stock кандидаты не появляются без отдельного reviewed corpus и policy regression;
  текущий allowlist намеренно состоит из одного инструмента.
- Публичный/коммерческий режим остаётся заблокирован до legal, identity, privacy и licensing review.

## Non-goals

- Broker orders, автоматическое превращение proposal в transaction, SELL/rebalance, гарантии
  доходности и LLM-owned financial facts.
- Public SaaS, auth/RBAC/multi-user, derivatives, margin, tax optimization и real-time claim.

## Verification

```bash
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
python3 /Users/tbwtk/.codex/skills/immune-project-engineering/scripts/immune_project.py check . --phase docs
git diff --check
```

После начала реализации к каждому checkpoint добавляются затронутые команды из `docs/QUALITY.md`.
