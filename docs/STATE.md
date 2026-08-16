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
- [ ] LLM/search может добавлять цитируемый research context, но инструмент, цена, lot, target,
  quantity, fee и totals материализуются только после typed validation и deterministic calculation.
- [ ] Свободный текст и поддержанное изображение создают unconfirmed transaction draft. Перед
  записью пользователь подтверждает side, resolved asset, quantity, clean unit price, НКД, fee,
  currency и timezone-aware occurred_at; неизвестность блокирует confirm.
- [ ] Proposal line никогда не превращается в transaction автоматически; advanced manual editor
  остаётся recovery fallback и использует тот же confirmation/validation contract.
- [ ] Обзор объясняет капитал: market value, contributions/cost basis, realized/unrealized result,
  income, allocation/drift, freshness и recent activity. Неподдерживаемая метрика показывается как
  `unknown/not configured`, а не рассчитывается правдоподобной заглушкой.
- [ ] Новый asset class допускается только отдельной versioned research/selection policy и eval.
  Dividend-stock policy проверяет фундаментальные, дивидендные, liquidity, governance,
  corporate-action и concentration facts; dividend capture не является core default.
- [ ] Monitor может собирать данные `3..4` раза в день, но создаёт alert/proposal только по
  зарегистрированному событию или threshold; SELL и broker order никогда не выполняются самими.
- [ ] Web использует четыре основных раздела — Обзор, Пополнить, Ассистент, Профиль — и проходит
  desktop/mobile, keyboard, screen-reader, error-recovery и sensitive-upload проверки.
- [ ] Schema/API/MCP/data/retention/security/Docker/docs обновлены согласованно; migration совместима
  с существующим ledger, full regression и isolated Docker E2E проходят на releasable `main`.

## Current verified state

- `PC2-1 Product shell` завершён: `POST/GET /v1/proposal-sets`, immutable `proposal_sets`, registry
  только из admitted strategies, API/MCP parity и compact-first web-карточка поверх неизменённого
  v1 deterministic run.
- Основная навигация уже использует Обзор, Пополнить, Ассистент, Профиль; ручной ledger editor
  сохранён внутри «Расширенного ввода операции», но transaction drafts/uploads ещё не реализованы.
- Локальный portfolio содержит подтверждённую BUY `SU26226RMFS9`; его числовая evidence не должна
  измениться при migration v2.
- Оставшийся product-gap: нет transaction drafts/uploads, richer analytics, dividend research policy
  и recurring monitoring.
- PC2-1 evidence 16.08.2026: `145 passed`, branch coverage `94.23%`; Ruff/mypy/OpenAPI; web build,
  typecheck, lint, SSR, `4` component tests + axe; MCP/API/migration tests; healthy Compose; browser
  desktop `1440px` и mobile `390px` без horizontal overflow.

## Changed areas

- Additive `proposal_sets` migration/model, strategy registry/application/API/MCP contracts,
  generated web types, compact strategy/progressive-evidence UI, новая IA, tests и документы.

## Decisions made

- Пользователь выбирает стратегию; алгоритм и его версия остаются техническим evidence.
- Proposal set содержит от одной до трёх реально зарегистрированных стратегий, а не обязательные
  три случайных тикера или LLM-ответа.
- Текст/OCR/vision создаёт только draft; ledger меняется после отдельного явного confirmation.
- Частое наблюдение отделено от редкого threshold/event-driven предложения; автоторговли нет.
- Расширение universe выполняется policy-by-policy; текущая безопасная core policy не ослабляется.

## Next exact step

Начать `PC2-2 Transaction assistant` с versioned parser corpus: принять Russian text и supplied
T-Invest screenshot как два intake transport, доказать draft-only/ambiguity/upload-safety contract,
затем добавить additive draft/decision schema и UI confirmation flow.

## Blockers

- Конкретный screenshot extractor ещё не допущен. `PC2-2` сначала проводит admission на versioned
  screenshot corpus; непрошедший extractor не подключается, а text draft остаётся рабочим.
- Дополнительные стратегии и dividend-stock universe не появляются до собственных policy/evidence
  gates. Это не блокирует уже готовую core-карточку.
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
