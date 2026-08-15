---
title: PatientCapital
project: PatientCapital
type: project
status: active
updated: 2026-08-15
---

# PatientCapital

PatientCapital помогает владельцу долгосрочного портфеля ответить на конкретный вопрос: «у меня есть
`8 000 ₽` и пятилетний горизонт — какие доступные инструменты рассмотреть и что помещается в мой
бюджет с учётом уже купленного, лотов и комиссии?». Основной поток сам ищет source-backed кандидатов
на MOEX и передаёт подтверждённые торговые факты детерминированному движку. Проверяемый результат —
локальный Docker-запуск с объяснимым, арифметически воспроизводимым предложением без автоматического
исполнения у брокера.

## Акторы и сценарии

- **Владелец портфеля** задаёт денежное пополнение и профиль риска; пятилетний горизонт является
  новым default. Система сама подбирает проверяемые кандидаты и лоты, а владелец отдельно вносит
  только фактически совершённые покупки.
- **Codex-агент** по запросу пользователя читает тот же проверенный portfolio snapshot и вызывает
  узкие read/propose tools; он не владеет формулой распределения и не исполняет сделки.
- **Оператор** запускает Docker-контур, управляет секретами и проверяет health/eval результаты.
- **GigaChat** проверен как экспериментальный внешний provider и отклонён live-gate; runtime mode
  отсутствует. Другая модель/версия может появиться только после нового admission по тем же порогам.

## Границы

В MVP входят один локальный пользователь, профиль брокера и комиссий, автоматический discovery
рублёвых ОФЗ и фондов широкого индекса через delayed MOEX ISS, версионированная пятилетняя policy,
журнал операций, расчёт позиций и отклонений, план нового взноса, аналитическая панель, immutable
recommendation evidence и agent-facing инструменты. Ручной справочник остаётся advanced/legacy
fallback, но не является prerequisite основного сценария.

Не входят исполнение поручений, подключение к брокерскому кабинету, custody денежных средств,
прогноз доходности, real-time feed, свободный LLM-owned stock picking, налоговая оптимизация,
деривативы, маржинальная торговля, несколько пользователей и публичный SaaS. Публичное или коммерческое
предоставление персонализированных рекомендаций блокируется до отдельного юридического заключения
по статусу инвестиционного советника и требованиям к robo-adviser ПО.

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

<!-- immune-project-engineering:docs:start -->
- [Аудит и достаточность контекста](AUDIT.md)
- [Инженерные принципы IMMUNE](IMMUNE.md)
<!-- immune-project-engineering:docs:end -->
