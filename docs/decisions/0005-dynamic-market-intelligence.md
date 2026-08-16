---
title: "ADR 0005: динамический Market Intelligence"
type: decision
status: accepted
updated: 2026-08-16
---

# ADR 0005: динамический Market Intelligence

## Контекст

Assistant-first MVP v2 обновляет цены MOEX, но фактически выбирает один ОФЗ по простому ranking,
один из трёх фондов и единственную заранее исследованную акцию MOEX. Изменение суммы обычно меняет
количество лотов, а не market choice. Это не соответствует mental model владельца: сообщить сумму,
подождать исследование и получить актив, выбранный из текущего рынка с объяснением, почему он
предпочтительнее сегодня.

## Решение

Вводится отдельный `market-intelligence-v1` boundary:

1. Scanner получает batch TQOB/TQBR facts только с fixed HTTPS MOEX ISS host. SECID ОФЗ и акций не
   перечисляются в production code. Broad-index fund classification пока остаётся reviewed
   registry, потому что TQBR `IFTF` не доказывает underlying strategy.
2. Перед expensive per-security enrichment применяется deterministic liquidity/listing/type
   prefilter с versioned top-N limit. Для акций scanner получает официальную dividend history;
   missing/invalid response исключает кандидата или блокирует scan по записанному failure contract.
3. Каждый scan сохраняется immutable: idempotency key/slot, provider/policy, requested/observed
   time, expiry, status/error, counts и typed candidate snapshot. Пользовательские деньги и позиции
   не входят в market snapshot.
4. Proposal использует свежий snapshot не старше четырёх часов; missing/stale snapshot запускает
   bounded live scan. Нет fallback на прежний allowlist или stale-success.
5. Ranking остаётся deterministic. Для fixed-rate ОФЗ учитываются affordability, пятилетнее окно,
   MOEX yield и liquidity; ближайшие альтернативы и их scores/reasons сохраняются. Для dividend
   stock используются listing/liquidity, подтверждённые годы выплат и историческая выплата к
   текущей цене. Это `market_screen`, не прогноз и не полный fundamental audit.
6. Dynamic stock exposure допускается только growth profile и concentration cap. Unknown
   profitability/payout/governance/corporate-action evidence видимы в карточке; модель не заменяет
   их правдоподобным текстом. Полный cross-source issuer audit является отдельной будущей policy.
7. Worker обновляет snapshot четыре раза в день до monitor evaluation. Ни scanner, ни scheduler,
   ни proposal не имеют transaction/order capability.

## Почему hybrid, а не только live или только cron

Только live делает каждый запрос медленным и создаёт лишний fan-out; только cron может вернуть
просроченный результат после outage. Свежий immutable cache даёт быстрый обычный путь, а bounded
live refresh сохраняет актуальность и fail-loud поведение.

## Отклонённые варианты

- Расширять вручную ticker allowlist: повторяет исходный продуктовый дефект.
- Свободный LLM stock picking: не воспроизводит цену, lot, score и источник и нарушает authority.
- Считать каждый TQBR ETF широким индексом: биржевая classification этого не доказывает.
- Называть dividend-history screen фундаментальным анализом: создаёт скрытую неизвестность.
- Автоматически менять портфель при каждом scan: наблюдение не является исполнением.

## Evidence gate

Acceptance mapping принадлежит `docs/QUALITY.md`; lineage — `docs/DATA.md`; amplification/staleness
controls — `docs/SECURITY.md`; эксплуатация — `docs/OPERATIONS.md`. Production implementation
начинается с failing provider/policy/cache contracts и завершается controlled live MOEX и Docker
journey без изменения ledger.
