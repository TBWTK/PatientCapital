---
title: Текущее состояние
type: state
status: active
updated: 2026-08-15
---

# Текущее состояние

## Active objective

Собрать воспроизводимый Docker Compose-контур для web, API и PostgreSQL, затем проверить clean-volume
health и сквозной flow profile/assets/prices → contribution proposal → transaction → dashboard.

## Acceptance criteria

- [ ] `docker compose up --build --wait` поднимает db, migration/API и production web без ручных
  host-процессов; published ports привязаны только к loopback.
- [ ] API readiness зависит от PostgreSQL, web health проверяет HTTP, startup не маскирует failure.
- [ ] Clean-volume smoke создаёт конфигурацию и выполняет proposal/record/dashboard через public API.
- [ ] CA доступен eval tooling, но GigaChat credentials не вшиты в image/compose/config; `.env`
  остаётся ignored.
- [ ] Полный regression, Compose config, dependency/secret scan, `git diff --check` и
  project-control audit проходят.

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
- PostgreSQL/API verification: полный suite `61 passed`, branch coverage `95%`; Ruff, strict mypy,
  package build, Compose config и project-control check прошли 15.08.2026. DB container healthy.
- Responsive Vinext/React UI реализует обзор, расчёт пополнения, BUY/SELL journal и versioned
  profile/assets/prices. TypeScript contracts генерируются из OpenAPI; денежной логики во frontend
  нет. Известные API errors локализуются с сохранением машинного кода.
- Web verification: TypeScript strict check, ESLint, production Vinext build, SSR test, `2`
  component tests и axe semantic scan прошли 15.08.2026. Живой browser QA пройден на desktop и
  `390×844`; CORS/API loading, navigation, stale-price fail-loud и четыре поверхности проверены,
  console warnings/errors отсутствуют.
- Codex agent surface реализован как локальный Python MCP 2.0 stdio server с шестью allowlisted
  read/propose/record tools и structured output. Codex global config содержит enabled
  `patientcapital` entrypoint без дополнительных env/secrets.
- MCP verification: `6` wire tests проверяют discovery/schema/annotations, реальный subprocess
  negotiation, persisted HTTP parity, exact idempotent replay, stale/extra/unknown fail-loud.
  Полный suite `67 passed`, branch coverage `95.25%`; Ruff и strict mypy прошли 15.08.2026.
- GigaChat eval использует публичный Russian Trusted Root CA с TLS verification, sanitized OAuth
  errors и versioned corpus из `4` explanation + `20` intent cases. Credentials/tokens и raw
  prompt/output не сохраняются в report.
- Live `GigaChat-2:2.0.30.01` дал `24/24` schema-valid responses, но `0/4` grounded explanations,
  `4/20` correct intents и `0%` safety. Provider отклонён, runtime integration не добавлена,
  `GIGACHAT_ENABLED=false`; report сохранён в `reports/gigachat-admission-v1.json`.
- GigaChat targeted verification: `7 passed`; Ruff и strict mypy прошли. Tests закрывают OAuth raw
  и preencoded keys, token cache, timeout, malformed output и unavailable-model fail-fast.

## Changed areas

- Foundation: root README, Git hygiene, восемь project-control документов, агентские правила и
  threat model.
- Domain: `src/patientcapital/domain`, test fixtures/example/boundary/property suite, Python package
  metadata и locked dev toolchain.
- Persistence/API: initial Alembic migration, SQLAlchemy mappings, application services, shared
  Pydantic contracts, FastAPI transport, PostgreSQL Compose service и integration suite.
- Product UI: `web/app`, generated OpenAPI types, responsive interaction design, component/SSR/a11y
  tests и project-bound social preview asset.
- Agent surface: transport-neutral `AgentTools`, strict MCP stdio adapter, contract tests, console
  entrypoint и зарегистрированная локальная Codex connection.
- Provider audit: публичный CA, fail-closed HTTPX OAuth/JSON Schema adapter, versioned synthetic
  corpus, evaluator tests и sanitized rejected live report; runtime connection отсутствует.

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
- PostgreSQL остаётся authority для product state; Sites D1/R2 bindings не используются. Браузер
  не сохраняет финансовые факты в local storage и не пересчитывает значения API.
- Product не публикуется на Sites: заявленный MVP является локальным, а опубликованный web без
  доступного частного API создаст неработающую и потенциально вводящую в заблуждение поверхность.
- MCP SDK 2.0 по умолчанию игнорирует лишние top-level arguments; PatientCapital расширяет server
  fail-closed моделью `extra=forbid`, чтобы advertised schema совпадала с runtime validation.
- Agent tools не изменяют profile/asset universe. `record_transaction` принимает только явно
  подтверждённый факт, имеет idempotency annotation и никогда не вызывается из proposal автоматически.
- `GigaChat-2` отклонён по grounding/intent/safety, несмотря на 100% schema parse. Gate не ослабляется;
  следующий provider/model должен пройти тот же versioned corpus до появления runtime adapter.

## Next exact step

Добавить production Dockerfiles для API и web, Compose health/startup dependencies и затем выполнить
clean-volume HTTP smoke полного пользовательского flow.

## Blockers

- Публичный/коммерческий режим и формулировка персональных рекомендаций заблокированы до
  юридического анализа; это не блокирует локальный исследовательский MVP без исполнения.
- GigaChat-2 непригоден для текущего режима по live admission; требуется другая модель/provider или
  новая версия, но это не блокирует deterministic MVP.

## Non-goals

- Вычисление allocation, broker execution и отправка полного portfolio/ledger во внешний provider.
- Auth/RBAC/multi-user и публичный production deployment.
- Перенос финансовых вычислений или source-of-truth состояния во frontend.

## Verification

```bash
uv run pytest --cov=patientcapital --cov-branch --cov-fail-under=94
uv run ruff check .
uv run mypy src tests
(cd web && npm test && npm run typecheck && npm run lint)
docker compose config
git diff --check
python3 /Users/tbwtk/.codex/skills/project-control/scripts/project_control.py check .
```
