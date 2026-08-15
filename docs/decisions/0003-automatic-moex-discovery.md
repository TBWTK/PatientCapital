---
title: "ADR 0003: автоматический подбор через MOEX и deterministic policy"
type: decision
status: accepted
updated: 2026-08-15
---

# ADR 0003: автоматический подбор через MOEX и deterministic policy

## Контекст

Первый MVP отвечал только на вопрос «как распределить взнос по уже настроенным активам» и требовал
от пользователя вручную вводить ticker, lot, цену и target weight. Это противоречит уточнённому
бизнес-сценарию: пользователь хочет ввести, например, `8 000 RUB` и получить предложение для
пятилетнего горизонта, а поиск доступных ОФЗ/акций и проверку торговых параметров должна выполнить
система.

Рассмотрены три варианта: дать LLM право свободно выбирать и оценивать бумаги; встроить Codex SDK в
web runtime; либо разделить исследование рынка и финансовый расчёт. Первые два не подходят: текстовая
модель не является authority для цены/лота/суммы, а Codex SDK предназначен для coding-focused threads
и потребовал бы новый credential/open-world boundary внутри финансового API.

## Решение

- Основной сценарий — `amount → automatic discovery → deterministic proposal`; ручной asset editor
  не является prerequisite и остаётся только legacy/advanced surface.
- MOEX ISS — runtime authority для идентификатора, режима торгов, валюты, размера лота, delayed
  market snapshot, ликвидности и параметров ОФЗ. Недоступный, неполный или устаревший ответ блокирует
  расчёт typed-ошибкой; cached/LLM fallback запрещён.
- Equity-кандидаты ограничены source-backed реестром рублёвых фондов широкого индекса МосБиржи.
  Runtime проверяет, что инструмент активен, является фондом, имеет цену и помещается в бюджет, а
  затем выбирает наиболее ликвидный допустимый вариант. Это candidate policy, не утверждение о
  будущей доходности.
- Для ОФЗ runtime рассматривает активные рублёвые выпуски, выбирает ликвидный выпуск с погашением,
  наиболее близким к заданному горизонту, и рассчитывает indicative dirty unit cost только из
  `face value × quote / 100 + accrued interest`.
- Версионированная пятилетняя policy задаёт классовые доли по сохранённому risk profile:
  `conservative 80/20`, `balanced 60/40`, `growth 40/60` для ОФЗ/equity-index. Доли — явная
  продуктовая эвристика, а не вывод LLM или обещание suitability/доходности.
- Выбранные security facts материализуются в локальный каталог и append-only price snapshots, чтобы
  пользователь мог отдельно записать фактическую покупку. Proposal не меняет ledger и не вызывает
  broker API.
- Codex/MCP получает отдельный automatic-proposal tool. Codex может искать дополнительные публичные
  сведения и объяснять source-backed результат, но не менять universe, веса, цену, lot или totals.
- Web показывает источник, `as_of`, задержанный характер данных, policy/run versions и понятное
  различие между предложением и исполнением. Цитаты/ссылки остаются кликабельными.

## Последствия

- Пользователю больше не нужно знать ticker, lot или target weight до первого расчёта.
- В API image появляется outbound HTTPS dependency только к allowlisted `iss.moex.com`; отказ сети
  становится видимым product state.
- Подбор воспроизводим по market snapshot и policy version, но не является фундаментальным анализом
  эмитентов и не гарантирует лучший или доходный актив. Individual-stock picking пока не допускается:
  public-equity screen может сформировать shortlist для дальнейшего исследования, но не заменяет
  доказательство suitability.
- MOEX ISS free/delayed access, licensing и публичная/коммерческая эксплуатация требуют отдельной
  проверки перед выходом за local single-user scope.
- Новая LLM/web-search integration возможна только как недоверенное evidence enrichment после
  отдельного admission и minimal-data contract; отсутствие model key не блокирует основной поток.

## Источники и evidence

- MOEX ISS: <https://www.moex.com/a2920>.
- Список и benchmark биржевых фондов MOEX: <https://www.moex.com/msn/etf>.
- OpenAI Web Search требует отдельного Responses API runtime и отображения citations:
  <https://developers.openai.com/api/docs/guides/tools-web-search>.
- Codex SDK описан как API для coding-focused threads:
  <https://developers.openai.com/codex/sdk>.
- Contract/provider/policy/API/MCP/UI tests и controlled live MOEX inspection перечисляются в
  `docs/QUALITY.md` и фактически запущенные результаты — в `docs/STATE.md`.
