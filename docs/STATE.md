---
title: Текущее состояние
type: state
status: active
updated: 2026-08-16
---

# Текущее состояние

## Active objective

**Ready, not started — Assistant-first MVP v2 (`PC2-MVP`).** Превратить проверенный amount-only v1
в лаконичный продуктовый цикл `сумма → выбор стратегии → подтверждение исполнения → обновлённая
аналитика`, добавить source-backed расширение universe и наблюдение без автоматической торговли.

## Acceptance criteria

- [ ] Один денежный input создаёт immutable proposal set из `1..3` зарегистрированных стратегий;
  одна допустимая карточка помечена рекомендуемой, а отсутствующие варианты не выдумываются.
- [ ] Карточка сначала показывает действие, обоснование, вложенную сумму/остаток и риски; security,
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

- v1 завершён и проверен: deterministic five-year allocation, strict delayed MOEX discovery для
  ОФЗ/широких индексных фондов, immutable evidence, bond НКД, API/web/MCP и Docker smoke.
- Локальный portfolio содержит подтверждённую BUY `SU26226RMFS9`; его числовая evidence не должна
  измениться при migration v2.
- Product-gap воспроизведён: один технически перегруженный result, manual dropdown ledger, узкий
  universe, нет transaction drafts/uploads, richer analytics и recurring monitoring.
- Документационный контракт PC2-MVP закреплён в README, ROADMAP, ARCHITECTURE, QUALITY, DATA,
  SECURITY, OPERATIONS, AUDIT и ADR 0004. Product code в этом checkpoint не изменён.
- Docs evidence 16.08.2026: project-control audit `PASS` с ожидаемыми `10` unchecked PC2 criteria,
  IMMUNE docs phase `PASS`, resume summary восстановил objective/next step, `git diff --check` прошёл.

## Changed areas

- Только product/architecture/data/security/operations/quality/agent документация для PC2-MVP.

## Decisions made

- Пользователь выбирает стратегию; алгоритм и его версия остаются техническим evidence.
- Proposal set содержит от одной до трёх реально зарегистрированных стратегий, а не обязательные
  три случайных тикера или LLM-ответа.
- Текст/OCR/vision создаёт только draft; ledger меняется после отдельного явного confirmation.
- Частое наблюдение отделено от редкого threshold/event-driven предложения; автоторговли нет.
- Расширение universe выполняется policy-by-policy; текущая безопасная core policy не ослабляется.

## Next exact step

После пользовательской цели `Реализуй PatientCapital Assistant-first MVP v2` начать checkpoint
`PC2-1 Product shell`: написать failing capability/component contracts для proposal cards,
progressive disclosure и новой навигации, затем реализовать их поверх неизменённого v1 core.

## Blockers

- Конкретный screenshot extractor не выбран. `PC2-2` должен сначала провести admission на
  versioned screenshot corpus; непрошедший extractor не подключается, а text draft остаётся рабочим.
- Дополнительные стратегии и dividend-stock universe не появляются до собственных policy/evidence
  gates. Это не блокирует `PC2-1` и core-карточку.
- Публичный/коммерческий режим остаётся заблокирован до legal, identity, privacy и licensing review.

## Non-goals

- Product code, schema migration, provider connection или schedule в текущем docs-only checkpoint.
- Broker orders, автоматический SELL/rebalance, гарантии доходности и LLM-owned financial facts.
- Public SaaS, auth/RBAC/multi-user, derivatives, margin, tax optimization и real-time claim.

## Verification

```bash
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
python3 /Users/tbwtk/.codex/skills/immune-project-engineering/scripts/immune_project.py check . --phase docs
git diff --check
```

После начала реализации к каждому checkpoint добавляются затронутые команды из `docs/QUALITY.md`.
