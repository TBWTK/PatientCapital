---
title: "ADR 0006: контур допуска актива"
type: decision
status: accepted
updated: 2026-08-16
---

# ADR 0006: контур допуска актива

## Контекст

`market-intelligence-v1` перечисляет рынок MOEX, но для акций использует однодневный `VALTODAY`
как top-N prefilter и исторические дивиденды как достаточный `market_screen`. Это ограничивает
research queue случайным торговым днём и позволяет выбрать акцию при явно неизвестных
profitability, payout, balance, governance и corporate actions. Свежесть загрузки dividend history
также не доказывает свежесть последней выплаты. Такой screen полезен для discovery, но не является
ни полноценной ликвидностью, ни инвестиционным допуском.

Мнения владельца о Газпроме, Полюсе, Самолёте, ФосАгро, Татнефти, X5, Ozon и других эмитентах —
research hypotheses и личные предпочтения, а не факты. Тикер не может быть разрешён или запрещён
production policy без воспроизводимого evidence.

## Решение

Вводится общий `asset-admission-v2` boundary с четырьмя независимыми осями:

1. `market-liquidity-v2` отвечает только на вопрос, можно ли нормально купить и продать инструмент.
   Он использует completed-session rolling observations, а не текущий однодневный оборот.
2. Class/strategy policy отвечает, подходит ли инструмент пятилетней стратегии:
   `ofz-admission-v1`, `broad-index-fund-admission-v1`, `equity-dividend-quality-v1` и в будущем
   отдельные `equity-growth-quality`/`corporate-bond-admission`. Отсутствие дивиденда блокирует
   dividend strategy, но само по себе не доказывает плохое growth quality.
3. `budget-feasibility-v1` проверяет стоимость целого лота только после допуска актива. Стоимость
   лота не является свойством ликвидности.
4. `owner-exclusion` является отдельным пользовательским ограничением. Оно исключает покупку, но
   не меняет объективные market/admission evidence и status.

Каждая ось возвращает `eligible`, `watch`, `reject` или `unknown`. Композиция имеет приоритет
`reject > unknown > watch > eligible`; только итоговый `eligible` может попасть в предложение.
`watch`, `reject` и `unknown` остаются видимыми с gates, source/as-of, version и причиной.

### Market liquidity v1

Минимальная evidence window — 20 последних завершённых торговых сессий. Gate учитывает:

- активный board/security status;
- число сессий с торгами и достаточность observation window;
- median daily RUB turnover по типизированным class-specific thresholds;
- median bid/offer spread по доступным завершённым samples; пока ISS history не отдаёт spread,
  допускается отдельный current/last-completed quote sample с явным sample count. Отсутствие
  sample записывается как non-material `unknown` advisory в `market-liquidity-v2`, чтобы закрытый
  рынок не блокировал ОФЗ/фонд при полном 20-session turnover/coverage evidence; высокий
  подтверждённый spread остаётся material gate;
- свежесть последней завершённой сессии и quote snapshot.

Thresholds принадлежат versioned policy и калибруются отдельным snapshot/eval. До калибровки
инструмент не повышается из `unknown` догадкой. Предварительные defaults:

| Класс | `eligible` trade coverage | `eligible` median turnover | `watch` floor |
| --- | ---: | ---: | ---: |
| акция | `18/20` | `50m RUB` | `10m RUB` |
| ОФЗ | `18/20` | `25m RUB` | `5m RUB` |
| фонд | `18/20` | `5m RUB` | `1m RUB` |

Top-N остаётся только ограничителем дорогого issuer enrichment после rolling liquidity gate. Оно
больше не определяет eligible universe. Новый инструмент с неполной историей получает `unknown`,
а не автоматический pass или reject.

`market-liquidity-v2` отдельно проверяет время получения evidence и фактическую дату последней
завершённой сессии. Свежая загрузка старого ряда больше не делает market facts свежими; это
материальное отличие от первого локального pre-release evaluation и причина нового policy version.

### Investment admission

- ОФЗ требует active RUB issue, валидные cash-flow/maturity facts и соответствие пятилетнему
  горизонту. Суверенный риск маркируется явно; фраза «государство всегда платит» не является gate.
- Broad-index fund требует reviewed benchmark/classification evidence. Биржевой `IFTF` не
  доказывает широкий индекс.
- Dividend equity требует свежие официальные отчётность/дивидендную policy и решения,
  регулярность и recency выплат, payout/FCF coverage, устойчивость баланса, governance и отсутствие
  material shareholder-return/corporate-action hard kill. Старый `market_screen` остаётся
  discovery-only и всегда даёт admission `unknown`.
- Growth equity не сравнивается со Сбером по dividend score. До отдельной versioned sector-aware
  policy Ozon/Yandex/IPO-кейсы остаются `unknown`, а не выдуманно хорошими или плохими.
- Corporate bonds до credit/default/covenant/offer/amortization adapter не входят в предложения;
  торговая ликвидность сама по себе не доказывает credit quality.

Официальное binding-решение о приостановке shareholder distributions является hard kill для
dividend strategy на effective horizon. Интервью или комментарий менеджера без решения создаёт
`watch`/`unknown`, но не ticker blacklist. Конфликтующие primary facts всегда дают `unknown`.

### Evidence и автоматизация

Market facts поступают только из allowlisted MOEX ISS adapter. Issuer events имеют typed taxonomy:
dividend suspension/resumption, default/covenant, delisting, issuance/dilution, related-party,
governance change и restructuring. Запись содержит asset identity, decision status, primary URL,
published/observed/valid-until и source hash.

Открытый web и LLM/subagent используются для discovery и summary, но не являются authority.
Модель не может создать или изменить asset identity, цену, turnover, dividend amount, financial
metric, threshold или status. До typed validation/admission любой найденный issuer fact остаётся
research draft, а профиль — `unknown`.

Worker четыре раза в день обновляет текущий pool и material events; completed-session aggregates
пересчитываются ежедневно. Broad-universe discovery запускается отдельным weekly slot. Provider
outage не повышает status и не превращает старый snapshot в свежий.

### Объяснение

Immutable evaluation хранит `evaluation_id`, asset/ISIN/kind/strategy, overall status, policy
versions, trigger, timestamps/next review, liquidity/admission/feasibility gates, hard kills,
unknowns, conflicts, changes и sources. Каждый gate фиксирует observed value/unit,
threshold/operator, source ids, observed/valid-until и reason code. Narrative хранится отдельно и
не входит в decision hash.

## Миграция PC3

Текущий `dividend-market-screen-v1` сохраняется как discovery evidence для обратной совместимости,
но больше не может быть selected candidate. Сначала rolling screen формирует широкий research
queue; затем только fresh full-quality profile материализует eligible candidate. Если eligible
акции нет, её target безопасно перераспределяется между допущенными ОФЗ/фондами. Ledger и broker
order path не меняются.

## Отклонённые варианты

- Hardcoded whitelist/blacklist из текущих предпочтений владельца: скрывает причины и быстро
  устаревает.
- Общий «рейтинг качества» для дивидендных и growth компаний: сравнивает разные тезисы ложной
  точностью.
- Однодневный turnover как liquidity gate: чувствителен к конкретной сессии.
- Свободный web/LLM verdict: невоспроизводим и нарушает deterministic financial authority.
- Автоматическая продажа после hard kill: наблюдение не является сделкой.

## Evidence gate

Acceptance mapping принадлежит `docs/QUALITY.md`; lineage — `docs/DATA.md`; boundaries и
composition — `docs/ARCHITECTURE.md`; amplification/source controls — `docs/SECURITY.md`;
расписание и recovery — `docs/OPERATIONS.md`. Production code начинается с failing domain/provider/
persistence/API tests. Ни один старый `market_screen` не должен попасть в proposal после миграции.
