---
title: Качество
type: quality
status: stable
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
- [x] Canonical OpenAPI SHA-256 snapshot, generated TypeScript surface и negative API contracts.
- [x] Frontend typecheck, component/SSR tests, axe semantic scan и desktop/mobile browser flow
  (15.08.2026).
- [x] MCP discovery, strict arguments, structured output, stdio process, HTTP parity, expected
  errors и exact transaction replay (`6` wire tests, 15.08.2026).
- [x] Committed-secret scan, container negative assertions и dependency audits: `0` Python/npm
  advisories (15.08.2026).
- [x] Clean-volume Docker smoke: health → seed/profile → propose → record → dashboard (15.08.2026).
- [x] `git diff --check` и project-control structural audit (15.08.2026).

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
uv run pytest --cov=patientcapital --cov-branch --cov-fail-under=94
uv run ruff check .
uv run mypy src tests
docker compose config
docker compose up --build --wait
./scripts/docker-smoke.sh
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

<!-- immune-project-engineering:quality:start -->
## Карта acceptance и evidence

| Требование/риск | Тип evidence | Fixture/среда | Команда или inspection | Ожидаемый результат | Статус |
| --- | --- | --- | --- | --- | --- |
| PC-REQ-01 capital/targets/holdings/fees → exact proposal | capability + property + API E2E | deterministic domain fixtures + PostgreSQL | `uv run pytest tests/domain tests/integration/test_recommendation_api.py` | Budget/lot/fee/drift invariants и exact known plan | passing |
| PC-REQ-02 analytics/profile/manual ledger/web | integration + component + browser | PostgreSQL, desktop и 390×844 browser | integration suite; web unit/SSR/a11y; recorded browser QA | Four product surfaces read/write same API facts | passing |
| PC-REQ-03 proposal ≠ execution | negative contract + DB trigger | API/MCP + PostgreSQL | ledger/recommendation/MCP tests | Proposal не меняет position; only explicit idempotent BUY/SELL does | passing |
| PC-REQ-04 Codex decision mode | MCP wire/subprocess parity + host registration | local stdio MCP + PostgreSQL + Codex config | MCP tests; `codex mcp list`; `codex mcp get patientcapital --json` | Exact allowlist/schema, HTTP parity, fail-loud errors; enabled repository entrypoint | passing |
| PC-REQ-05 GigaChat only if adequate | versioned live admission | 24 synthetic cases, real `GigaChat-2` | report + provider/eval tests | Reject unless schema/grounding/safety 100%, intent ≥95% | passing |
| PC-REQ-06 Dockerized local MVP | operational E2E | clean isolated Compose volume | `./scripts/docker-smoke.sh` | build/health/migrate/web/propose/record/dashboard/cleanup | passing |
| PC-RISK-01 hidden unknown/stale/wrong currency | boundary/property/negative API | generated and explicit invalid facts | domain validation + stale API/MCP tests | Typed visible error; no plausible partial plan | passing |
| PC-RISK-02 contract/data drift | snapshot + migration/immutability | OpenAPI, generated TS, clean PostgreSQL | full pytest + OpenAPI snapshot + project audit | Schema/client match; evidence rows reject mutation | passing |
| PC-RISK-03 secrets/provider/container | static scan + dependency/container inspection | committed tree + built images | commands recorded in `STATE.md` | No committed secrets/model creds; loopback/non-root/read-only; 0 advisories | passing |
| PC-OPS-01 PostgreSQL backup | artifact inspection | current local DB stream | `pg_dump -Fc` → `pg_restore --list` | Logical backup catalog readable without persisted dump | passing |
| PC-OPS-02 PostgreSQL restore | recovery rehearsal | isolated disposable volume | destructive restore procedure in `OPERATIONS.md` | Restored facts/runs equal source; measured RTO/RPO | not run |
| PC-NFR-01 10k ledger / 100-asset latency | performance/capacity | target host | benchmark not implemented | 10k events supported; proposal <500 ms | not run |
| PC-COMP-01 public personalized advice | human legal review | intended jurisdiction/operating model | external legal opinion | Public/commercial boundary approved | blocked |
| PC-GIT-01 releasable default branch | Git + full gates | local `main` | status/log + handoff checks | Verified checkpoints, clean worktree after commit | passing |
| PC-GIT-02 GitHub publication | external release | user-provided empty remote | `git push origin main` | Export only after repository-owner approval | blocked |

## Портфель проверок

Применены materially different layers: business capability fixtures; static format/type/build/link and
secret/dependency checks; unit/boundary/Hypothesis properties; OpenAPI/MCP/provider contracts;
PostgreSQL migration/trigger/application integration; GigaChat data/ML admission; responsive
browser/component/SSR/a11y journeys; timeout/schema/readiness resilience; advisory lock/version and
idempotency consistency; clean-volume Docker operational E2E; controlled live provider eval.

Честно не выполнены:

- stakeholder investment-domain walkthrough и legal review — обязательны до public/commercial use;
- mutation testing — текущий risk покрыт exact capability/boundary/property layers, но mutation gate
  нужен при замене allocation algorithm;
- parallel-write stress — single-user scope и DB locks проверены функционально, не под нагрузкой;
- destructive restore rehearsal — documented, но RTO/RPO остаются unknown;
- 10k-ledger/100-asset performance и saturation — expansion gate, а не доказанный MVP property.
<!-- immune-project-engineering:quality:end -->
