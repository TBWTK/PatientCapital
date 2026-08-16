---
title: PatientCapital
project: PatientCapital
type: project
status: active
updated: 2026-08-16
---

# PatientCapital

PatientCapital — локальный инвестиционный ассистент для пятилетнего портфеля. Владелец сообщает
только сумму нового взноса, а приложение исследует допустимый рынок, учитывает профиль и уже
купленные активы и показывает от одной до трёх понятных стратегических карточек. Каждая карточка
сначала отвечает «что сделать, почему и каков риск», а технические факты и версии расчёта раскрывает
по запросу. Выбранное предложение никогда не считается исполненным: реальная покупка отдельно
подтверждается из свободного текста, скриншота или advanced-ввода.

Все идентификаторы, цены, лоты, комиссии, суммы и портфельные эффекты принадлежат проверенным
источникам, версионированным политикам и детерминированному движку. Агент исследует контекст и
объясняет результат, но не может выдумать финансовый факт или провести брокерскую операцию.

## Акторы и сценарии

- **Владелец портфеля** один раз задаёт профиль, затем в обычном сценарии сообщает только сумму,
  выбирает подходящую стратегию и отдельно подтверждает фактически совершённую покупку.
- **Codex-агент** по запросу пользователя читает тот же проверенный portfolio snapshot и вызывает
  узкие read/propose/draft/record tools; он может исследовать и объяснять evidence, но не владеет
  формулой распределения и не исполняет сделки.
- **Оператор** запускает Docker-контур, управляет секретами и проверяет health/eval результаты.
- **GigaChat** проверен как экспериментальный внешний provider и отклонён live-gate; runtime mode
  отсутствует. Другая модель/версия может появиться только после нового admission по тем же порогам.

## Текущее состояние и Market Intelligence MVP

Текущий проверенный v1 уже имеет одного локального пользователя, профиль брокера и комиссий,
amount-only discovery рублёвых ОФЗ и фондов широкого индекса через delayed MOEX ISS,
версионированную пятилетнюю policy, журнал BUY/SELL с отдельным НКД, портфельную аналитику,
immutable recommendation runs, web и Codex tools.

**Assistant-first MVP v2** реализован по проверяемым checkpoint: product shell/proposal sets,
transaction assistant, explainable analytics, первый research-universe gate и scheduled monitoring
работают в одном локальном контуре:

1. `amount → proposal set`: одна рекомендуемая и до двух альтернативных стратегических карточек;
   неподдерживаемые варианты не генерируются для количества.
2. `proposal → execution draft`: свободный текст или изображение превращаются только в проверяемый
   draft; запись появляется после явного подтверждения всех материальных полей.
3. `evidence → broader research`: новые классы активов допускаются только зарегистрированной
   source-backed policy со своими eligibility/risk/eval gates; первой расширяемой категорией
   являются дивидендные акции, но не краткосрочный dividend capture как core-стратегия.
4. `observe → alert`: отдельный worker собирает данные четыре раза в день; immutable alert появляется
   только по версионированному событию/порогу, подтверждение означает лишь ознакомление и никогда не
   создаёт transaction или broker order.

Первая допущенная dividend-stock policy — `dividend-quality-v1`: только профиль «рост», максимум
20% target на категорию, минимум три прибыльных и три дивидендных периода, покрытая выплата,
допустимый баланс, ликвидность, governance и отсутствие выявленного material corporate action.
Первый allowlisted инструмент — обыкновенная акция MOEX; цена/лот/оборот поступают из ISS, а
research context — из reviewed primary-source corpus. Policy не ранжирует акции по дивидендной
доходности и не реализует dividend capture.

Активный `PC3-MI` устраняет этот статический предел. Фоновый scanner четыре раза в день перечисляет
активные рублёвые инструменты MOEX, сохраняет immutable market snapshot, а запрос суммы использует
его только пока он свежий и иначе выполняет bounded live refresh. SECID ОФЗ и dividend-stock
кандидатов не перечисляются в коде. Versioned policy хранит trace: universe coverage, доступность
лота, maturity/yield/liquidity для ОФЗ и listing/dividend-history/liquidity для акций. MOEX-only
дивидендный screen явно не называется полным фундаментальным аудитом; неподтверждённые измерения
остаются `unknown`, а не заполняются моделью.

Целевая web-навигация: **Обзор**, **Пополнить**, **Ассистент**, **Профиль**. Ручной ledger editor
остаётся доступным как advanced/recovery fallback, но не является основным пользовательским путём.

## Границы

Не входят исполнение поручений, custody денежных средств, обещание или прогноз доходности,
real-time feed, свободный LLM-owned stock picking, автоматическая ротация ради дивиденда,
налоговая оптимизация,
деривативы, маржинальная торговля, несколько пользователей и публичный SaaS. Публичное или коммерческое
предоставление персонализированных рекомендаций блокируется до отдельного юридического заключения
по статусу инвестиционного советника и требованиям к robo-adviser ПО.

## Как поставить единую цель реализации

После документационного checkpoint пользователь может задать одну цель:

> Реализуй PatientCapital Assistant-first MVP v2 по `docs/STATE.md`, `docs/ROADMAP.md` и ADR 0004.

Агент должен сам восстановить состояние из репозитория, идти по этапам ROADMAP, сначала создавать
проверки, затем реализацию, сохранять releasable checkpoints и останавливаться только на материальном
unknown, который нельзя безопасно разрешить из доступных источников. Формулировка цели не разрешает
broker execution, публикацию, ослабление quality gates или угадывание финансовых параметров.

## Источники первичного аудита

- Официальная документация OpenAI: [Codex SDK](https://developers.openai.com/codex/sdk) описывает
  SDK как интерфейс для coding-focused threads; поэтому доменная логика не встраивается в Codex.
- Официальная документация GigaChat: [авторизация](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api),
  [структурированный вывод](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output),
  [functions](https://developers.sber.ru/docs/ru/gigachat/guides/functions/overview),
  [ограничения](https://developers.sber.ru/docs/ru/gigachat/limitations) и
  [сертификаты](https://developers.sber.ru/docs/ru/gigachat/certificates).
- Банк России: [инвестиционные советники](https://www.cbr.ru/explan/invest/) и
  [требования к автоматическим советникам](https://www.cbr.ru/eng/press/event/?id=11066).
- Primary dividend corpus: [карточка и листинг MOEX](https://www.moex.com/en/stocks/moex),
  [МСФО-результаты 2025](https://www.moex.com/n98156),
  [дивидендная история](https://www.moex.com/a2656),
  [программа корпоративного управления](https://www.moex.com/programma-sozdaniya-aktsionernoj-stoimosti-publichnyh-aktsionernyh-obschestv)
  и [материалы собрания 2026](https://www.moex.com/povtornoe-godovoe-zasedanie-obschego-sobraniya-aktsionerov).

## Навигация

- [Текущее состояние](STATE.md)
- [Этапы](ROADMAP.md)
- [Архитектура](ARCHITECTURE.md)
- [Качество](QUALITY.md)
- [Технический долг](DEBT.md)
- [Данные](DATA.md)
- [Модель угроз](SECURITY.md)
- [Эксплуатация и восстановление](OPERATIONS.md)
- [ADR 0001: локальная MCP agent surface](decisions/0001-local-mcp-agent-surface.md)
- [ADR 0002: deterministic core и model admission](decisions/0002-deterministic-core-and-model-admission.md)
- [ADR 0003: автоматический подбор через MOEX](decisions/0003-automatic-moex-discovery.md)
- [ADR 0004: assistant-first продуктовый цикл](decisions/0004-assistant-first-product-loop.md)
- [ADR 0005: динамический Market Intelligence](decisions/0005-dynamic-market-intelligence.md)

<!-- immune-project-engineering:docs:start -->
- [Аудит и достаточность контекста](AUDIT.md)
- [Инженерные принципы IMMUNE](IMMUNE.md)
<!-- immune-project-engineering:docs:end -->
