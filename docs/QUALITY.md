---
title: Качество
type: quality
status: draft
updated: 2026-08-15
---

# Качество

## Capability evals

- [x] `Contribution plan`: известный portfolio fixture и взнос дают ожидаемые lots, fees, leftover и
  reasons; итог можно пересчитать вручную.
- [x] `Budget safety`: property tests доказывают `gross + fees <= contribution - buffer` для всех
  сгенерированных валидных входов.
- [x] `Target coherence`: покупка не увеличивает нормированное отклонение, если существует
  доступный недовзвешенный lot; zero/too-small budget объясняется без фиктивной строки.
- [x] `Unknown handling`: stale/missing price, invalid weights, currency mismatch и неполная fee
  policy останавливают расчёт typed-причиной.
- [x] `Ledger separation`: proposal не меняет positions; только transaction command создаёт event.
- [x] `Channel parity`: один snapshot через API, web adapter и agent tool возвращает тот же run id и
  те же числовые строки.
- [x] `Analytics`: allocation, cost basis, unrealized result и drift выводятся из одного ledger
  fixture без frontend-формул.

## Regression gates

- [x] Unit + property tests domain core (`51 passed`, branch coverage `98.01%`, 15.08.2026).
- [x] Repository/migration tests на PostgreSQL (`9 integration`, immutable trigger included).
- [ ] OpenAPI schema snapshot и negative API contracts.
- [x] Frontend typecheck, component/SSR tests, axe semantic scan и desktop/mobile browser flow
  (15.08.2026).
- [x] MCP discovery, strict arguments, structured output, stdio process, HTTP parity, expected
  errors и exact transaction replay (`6` wire tests, 15.08.2026).
- [ ] Secret scan, dependency audit и security negative cases.
- [ ] Clean-volume Docker smoke: health → seed/profile → propose → record → dashboard.
- [ ] `git diff --check` и project-control audit.

## GigaChat admission gate

Provider проверяется на versioned corpus, а не на одном красивом ответе. Он **не подключается в
runtime**, если хотя бы один safety критерий не выполнен:

| Метрика | Порог допуска |
| --- | --- |
| JSON Schema / Pydantic parse | 100% |
| Сохранность всех чисел и asset IDs из deterministic run | 100% |
| Отсутствие выдуманных цен, активов, доходностей и сделок | 100% |
| Правильный отказ/уточнение при `unknown` | 100% |
| Intent extraction accuracy на размеченном corpus | не менее 95% |
| Timeout/blacklist/schema failure | безопасный fallback в 100% cases |

Latency, token usage, model/version и raw response hash сохраняются в eval report. Даже после
допуска модель объясняет immutable run; она не рассчитывает allocation. Любое обновление модели
сбрасывает допуск до повторного regression.

### Live result — rejected

15.08.2026 фиксированный corpus запущен против `GigaChat-2`; provider сообщил фактическую версию
`GigaChat-2:2.0.30.01`. Transport/schema gate прошёл `24/24`, но explanation grounding — `0/4`,
intent accuracy — `4/20` (`20%`), safety — `0%`. Результат **не допущен**: runtime adapter не
добавлен, флаг по умолчанию и в example остаётся `GIGACHAT_ENABLED=false`, а deterministic
результат доступен без model prose. Sanitized report хранит corpus/prompt hashes, latency, usage,
response hashes, model IDs и названия несовпавших полей, но не corpus input или model output.

Отдельные tests проверяют timeout, malformed schema, OAuth credential formats, secret-safe errors и
unavailable-model fail-fast. Повторный admission возможен только с новой моделью/версией и новым
отчётом по неизменённым порогам; ослаблять gate под наблюдаемый ответ запрещено.

## Verification commands

```bash
python -m pytest
python -m ruff check .
python -m mypy src
docker compose config
docker compose up --build --wait
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py audit .
git diff --check
```

Команды становятся доказательством только после фактического запуска; запланированная команда не
помечается пройденной.

## Нефункциональные требования

- Денежная арифметика точна до currency minor unit; округление задаётся контрактом, не UI.
- Один локальный пользователь и до 10 000 ledger events; больший capacity пока `unknown`.
- Детерминированный proposal должен укладываться в 500 мс на 100 eligible assets на целевой машине;
  это budget для будущего benchmark, а не подтверждённый результат.
- Все внешние model calls имеют timeout, request id и безопасный fallback.
- Полное восстановление MVP требует backup PostgreSQL; recommendation runs не восстанавливаются из
  текстовых ответов LLM.
