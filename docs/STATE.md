---
title: Текущее состояние
type: state
status: active
updated: 2026-08-15
---

# Текущее состояние

## Active objective

Реализовать responsive web UI с четырьмя рабочими поверхностями: dashboard аналитики, ввод нового
пополнения и просмотр плана, ручная запись покупки, профиль/активы/цены/цели. UI использует только
versioned API и не повторяет финансовые формулы.

## Acceptance criteria

- [ ] Первый viewport показывает состояние портфеля и главное действие «распределить пополнение»,
  а не generic dashboard chrome.
- [ ] Dashboard отображает total value, cost basis, unrealized P&L, allocation/target drift и явный
  price as-of из `/v1/portfolio` без собственных вычислений.
- [ ] Contribution flow показывает lots, quantity, gross, fee, leftover, pre/post drift и immutable
  run id; proposal визуально не выдаётся за исполненную покупку.
- [ ] Portfolio flow записывает BUY/SELL с idempotency key и обновляет analytics после успеха.
- [ ] Profile flow поддерживает optimistic version, broker fee; asset flow — versions, target, lot и
  manual price freshness с понятными conflict/domain errors.
- [ ] Typecheck, component tests, production build, accessibility/responsive checks и browser
  user-flow QA проходят; API contracts не дублируются вручную без generated/typed boundary.

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
- Alembic head создаёт `profile_versions`, `assets/asset_versions`, append-only price/transaction и
  immutable recommendation tables; PostgreSQL triggers запрещают UPDATE/DELETE evidence rows.
- FastAPI `/v1` реализует profile/assets/prices/transactions/portfolio/recommendations и раздельные
  liveness/readiness. Optimistic versions, idempotency conflict и insufficient position проверены.
- PostgreSQL/API verification: полный suite `60 passed`, branch coverage `95%`; Ruff, strict mypy,
  package build, Compose config и project-control check прошли 15.08.2026. DB container healthy.

## Changed areas

- Foundation: root README, Git hygiene, восемь project-control документов, агентские правила и
  threat model.
- Domain: `src/patientcapital/domain`, test fixtures/example/boundary/property suite, Python package
  metadata и locked dev toolchain.
- Persistence/API: initial Alembic migration, SQLAlchemy mappings, application services, shared
  Pydantic contracts, FastAPI transport, PostgreSQL Compose service и integration suite.

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
- Profile и asset configuration append-only versioned; PostgreSQL advisory locks сериализуют
  конкурирующие writes, а stale `expected_version` возвращает `VERSION_CONFLICT`.
- Transaction idempotency key владеет exactly-once intent: точный replay возвращает исходную запись,
  другой payload с тем же ключом отклоняется. Ledger evidence и recommendation snapshots immutable
  на уровне БД.

## Next exact step

Запустить Sites web scaffold в существующем проекте, заменить starter на typed PatientCapital UI и
сначала зафиксировать component/user-flow tests для четырёх поверхностей.

## Blockers

- Публичный/коммерческий режим и формулировка персональных рекомендаций заблокированы до
  юридического анализа; это не блокирует локальный исследовательский MVP без исполнения.
- Пригодность GigaChat неизвестна до живого фиксированного eval corpus; это не блокирует
  детерминированный core.

## Non-goals

- Agent protocol, GigaChat и broker execution внутри Product UI stage.
- Auth/RBAC/multi-user и публичный production deployment.
- Перенос финансовых вычислений или source-of-truth состояния во frontend.

## Verification

```bash
pnpm test
pnpm build
pnpm typecheck
docker compose config
git diff --check
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py check .
```
