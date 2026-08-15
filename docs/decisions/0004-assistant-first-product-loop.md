---
title: "ADR 0004: assistant-first продуктовый цикл"
type: decision
status: accepted
updated: 2026-08-16
---

# ADR 0004: assistant-first продуктовый цикл

## Контекст

Проверенный v1 устранил обязательное ручное создание universe, но сохранил интерфейс калькулятора:
один технически подробный result, отдельный ledger dropdown и ограниченный набор ОФЗ/индексных
фондов. Владелец ожидает иной mental model: сообщить сумму, сравнить понятные способы действия,
зафиксировать фактическую покупку разговором или скриншотом и видеть объяснимое изменение капитала.

Изменение пересекает product language, policy, API, schema, web, agent tools, uploads, privacy,
schedule и verification. Поэтому оно не реализуется как изолированный frontend patch.

## Решение

### Четыре разные сущности

- **Стратегия** — пользовательское намерение и versioned policy. Пользователь может выбрать её.
- **Предложение** — точный immutable расчёт стратегии на конкретном snapshot и сумму.
- **Алгоритм** — внутренний deterministic calculator; его не предлагают выбрать вместо стратегии.
- **Исполнение** — подтверждённые факты реальной брокерской операции; оно отделено от предложения.

### Proposal set и progressive disclosure

Один запрос суммы возвращает proposal set из `1..3` зарегистрированных стратегий. Ровно одна
допустимая стратегия рекомендуется по сохранённому профилю и policy priority. Если валидна только
core policy, отображается одна карточка; система не создаёт альтернативу ради интерфейса.

Карточка compact layer содержит действие, краткое «почему», сумму/остаток и ключевые trade-offs.
Exact instruments, lots, prices, fees, freshness, sources, rejected candidates, run/algorithm/policy
versions находятся в доступном раскрываемом evidence layer. Числовые поля приходят из сохранённых
runs и не пересчитываются в web/LLM.

### Research и расширение universe

Search/research является недоверенным evidence-enrichment boundary. Он может найти issuer filings,
corporate actions, dividend history, liquidity и другой контекст, но материализация asset и
числового факта разрешена только typed source adapter. Каждый новый класс активов получает
собственную eligibility/risk/selection policy и capability corpus. Отказ источника, stale evidence
или неполная policy блокирует только затронутую стратегию и остаётся видимым.

Первая планируемая категория — дивидендные акции. Dividend capture не становится core default:
тактическая стратегия возможна только отдельной policy после cost/tax/gap/backtest/risk evidence.

### Transaction assistant

Text/image input создаёт immutable transaction draft и список `unknown/conflict`, а не ledger event.
Instrument resolver обязан связать упоминание с validated security identity. Пользователь видит и
явно подтверждает side, asset, quantity, clean unit price, total accrued interest, fee, currency и
timezone-aware occurrence time. Только exact confirmed payload с новым idempotency key вызывает
существующий ledger command. Proposal может предзаполнить ожидания, но не подтверждает исполнение.

Raw upload обрабатывается как конфиденциальный недоверенный файл. Он не отправляется внешнему
provider без отдельного approved data contract. Advanced manual editor сохраняется как recovery
surface, но использует тот же draft/confirm contract.

### Monitoring

Наблюдение и действие разделены. Scheduler может обновлять allowlisted evidence три-четыре раза в
день. Alert/proposal создаётся только по versioned threshold/event policy: material drift,
risk/eligibility change, validated corporate action, freshness transition или другой явный rule.
Отсутствие события означает отсутствие рекомендации. Monitor не вызывает transaction или order API.

## Последствия

- Основная web IA сокращается до Обзор/Пополнить/Ассистент/Профиль.
- Потребуются новые proposal-set, research-evidence, transaction-draft/decision и monitor/alert
  contracts; существующие runs/transactions остаются backward-compatible authorities.
- Screenshot extraction требует отдельного admission corpus и fail-loud ambiguity behavior.
- Более богатая аналитика требует cash-flow/income facts; неподдерживаемые метрики нельзя выводить
  из market value приблизительно.
- UI можно реализовать первым поверх текущего core, показывая одну core-карточку до допуска новых
  policies. Это сохраняет releasable checkpoints.

## Отклонённые варианты

- Три свободных LLM stock picks: невоспроизводимы и нарушают authority финансовых фактов.
- Автозапись рекомендации как покупки: смешивает proposal и execution.
- Удаление manual fallback: ухудшает recovery при ошибке extraction/resolver.
- Сделка при каждом scheduled run: создаёт churn и не следует долгосрочной пятилетней цели.
- Dividend capture как базовая стратегия: выплата не устраняет price/tax/fee/event risk.

## Evidence и gate

Acceptance mapping находится в `docs/QUALITY.md`, данные и retention — в `docs/DATA.md`, угрозы
upload/research/monitor — в `docs/SECURITY.md`, этапы — в `docs/ROADMAP.md`. Реализация начинается с
failing contracts и не считается готовой по наличию экранов без migration, negative-path и E2E
evidence.
