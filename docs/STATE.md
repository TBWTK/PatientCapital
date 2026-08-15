---
title: Текущее состояние
type: state
status: active
updated: 2026-08-15
---

# Текущее состояние

## Active objective

Реализовать versioned HTTP API и PostgreSQL persistence для профиля, assets/prices/targets,
append-only transactions, analytics snapshot и immutable recommendation runs поверх проверенного
domain core.

## Acceptance criteria

- [ ] Alembic создаёт PostgreSQL schema с numeric money, constraints, versioned facts, append-only
  transaction semantics и immutable recommendation snapshot.
- [ ] API позволяет получить/изменить single-user profile, broker fee policy, assets, prices и
  targets с optimistic versioning и stable error contracts.
- [ ] Идемпотентная запись buy/sell/deposit/fee события обновляет analytics projection; повторный
  idempotency key не создаёт вторую операцию.
- [ ] `POST /v1/recommendations` строит domain input из committed snapshot, сохраняет immutable run
  и возвращает те же numbers/reasons, что pure core.
- [ ] Health различает process/database readiness; секреты и account identifiers не возвращаются.
- [ ] Migration, repository, API integration и negative tests проходят на PostgreSQL в Docker;
  Ruff, strict mypy, branch coverage и project-control check зелёные.

## Current verified state

- Указанный GitHub remote доступен, но не содержит ни одного commit/ref; локально создан `main`.
- До инициализации в workspace находился только пользовательский `.env`; он исключён из Git и не
  читался как набор значений.
- В `.env` подтверждено наличие имён `GIGACHAT_API_KEY`, `GIGACHAT_CLIENT_ID`,
  `GIGACHAT_SCOPE`; значения и токены не выводились.
- В примере RAG найден `russian_trusted_root_ca_pem.crt`. OpenSSL подтверждает subject/issuer
  Russian Trusted Root CA, срок до 27.02.2032 и SHA-256 `D2:6D:2D:02:31:B7:C3:9F:92:CC:73:85:12:BA:54:10:35:19:E4:40:5D:68:B5:BD:70:3E:97:88:CA:8E:CF:31`.
- Официальные источники подтверждают GigaChat JSON Schema и function calling, но одновременно
  требуют проверять ответы из-за возможной неактуальности/искажения; live quality ещё не измерена.
- Официальные материалы Банка России подтверждают отдельные требования к персональным
  инвестиционным рекомендациям и автоматическим советникам; применимость к будущему способу
  эксплуатации требует профильного юридического заключения.
- Схемы БД, migrations, HTTP API и запускаемого UI пока нет.
- Foundation gate закрыт: project-control check `PASS errors=0`, `git diff --check` прошёл, `.env`
  подтверждённо ignored; единственное предупреждение исправлено до перехода этапа.
- Domain core реализован как immutable Python package без БД/HTTP/LLM. Он валидирует currency,
  freshness, targets и fees; рассчитывает целые lots с percentage/minimum commission и cash buffer;
  сохраняет SHA-256 input hash, версию алгоритма, pre/post drift и explicit reason.
- Domain verification: `51 passed`, branch coverage `98.01%`; Ruff, strict mypy, offline sdist/wheel
  build и `git diff --check` прошли 15.08.2026.

## Changed areas

- Foundation: root README, Git hygiene, восемь project-control документов, агентские правила и
  threat model.
- Domain: `src/patientcapital/domain`, test fixtures/example/boundary/property suite, Python package
  metadata и locked dev toolchain.

## Decisions made

- MVP локальный, single-user и не исполняет сделки.
- Формулы и ограничения принадлежат чистому Python domain core; БД, API, UI и LLM — адаптеры.
- GigaChat не допускается к вычислению/изменению плана и остаётся выключенным до live eval.
- Codex подключается как внешний tool client; встроенный Codex app-server не является runtime
  финансовой логики.
- Начальный market-data source — явно датированная ручная цена. Автоматический provider не
  выбирается без отдельного requirements/eval этапа.
- MVP округляет вычисленные денежные значения до `0.01` методом `ROUND_HALF_UP`; пользовательский
  `Money` с лишними знаками отклоняется вместо silent rounding.
- Если ни один целый lot не улучшает drift в доступном бюджете, run получает
  `BUDGET_BELOW_ANY_LOT`; строка с нулевой покупкой не создаётся.

## Next exact step

Создать failing PostgreSQL migration/repository/API tests для идемпотентного ledger, optimistic
profile version и сохранения deterministic recommendation run.

## Blockers

- Публичный/коммерческий режим и формулировка персональных рекомендаций заблокированы до
  юридического анализа; это не блокирует локальный исследовательский MVP без исполнения.
- Пригодность GigaChat неизвестна до живого фиксированного eval corpus; это не блокирует
  детерминированный core.

## Non-goals

- UI, agent protocol и GigaChat provider внутри Persistence/API stage.
- Автоматическое получение market prices и broker execution.
- Auth/RBAC/multi-user; API bind остаётся локальным до отдельного этапа security.

## Verification

```bash
docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/pytest --cov=patientcapital --cov-branch
.venv/bin/ruff check src tests
.venv/bin/mypy --strict src tests
git diff --check
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py check .
```
