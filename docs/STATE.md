---
title: Текущее состояние
type: state
status: active
updated: 2026-08-15
---

# Текущее состояние

## Active objective

Закрыть выявленные IMMUNE handoff gaps: сделать аудит и принципы каноническими документами,
синхронизировать data/operations contracts с фактической schema, построить requirement→evidence
mapping и повторно доказать releasable local `main`.

## Acceptance criteria

- [x] `AUDIT.md` классифицирует исходный контекст, аудит идеи/архитектуры/рисков/GigaChat,
  альтернативы, достаточность контекста и оставшиеся unknown по inspectable evidence.
- [x] `IMMUNE.md` владеет принципами и mutation protocol; `AGENTS.md` ссылается на него без
  дублированного authority.
- [x] `DATA.md` и новый operator contract описывают только фактическую schema, Docker lifecycle,
  persistence/recovery и явно маркированные непроверенные ограничения.
- [x] `QUALITY.md` отображает каждое требование/существенный риск в named evidence и честный status.
- [ ] IMMUNE/project-control handoff checks, docs links, `git diff --check` и релевантный regression
  проходят; checkpoint находится на чистом локальном `main`.
- [ ] GitHub push выполняется только после явного разрешения пользователя; до него remote state
  остаётся видимым, а не выдаётся за synced.

## Current verified state

- Указанный GitHub remote доступен, но не содержит ни одного commit/ref; локально создан `main`.
- До инициализации в workspace находился только пользовательский `.env`; он исключён из Git и не
  читался как набор значений.
- В `.env` подтверждено наличие имён `GIGACHAT_API_KEY`, `GIGACHAT_CLIENT_ID`,
  `GIGACHAT_SCOPE`; значения и токены не выводились.
- В примере RAG найден `russian_trusted_root_ca_pem.crt`. OpenSSL подтверждает subject/issuer
  Russian Trusted Root CA, срок до 27.02.2032 и SHA-256 `D2:6D:2D:02:31:B7:C3:9F:92:CC:73:85:12:BA:54:10:35:19:E4:40:5D:68:B5:BD:70:3E:97:88:CA:8E:CF:31`.
- Официальные источники подтверждают GigaChat JSON Schema и function calling, но одновременно
  требуют проверять ответы из-за возможной неактуальности/искажения; live quality измерена ниже.
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
  `patientcapital` entrypoint без дополнительных env/secrets. Повторная host inspection через
  `codex mcp list` и `codex mcp get patientcapital --json` подтвердила enabled STDIO command
  `/Users/tbwtk/Documents/CODEX_PREP/PatientCapital/.venv/bin/patientcapital-mcp` 15.08.2026.
- MCP verification: `6` wire tests проверяют discovery/schema/annotations, реальный subprocess
  negotiation, persisted HTTP parity, exact idempotent replay, stale/extra/unknown fail-loud.
  Полный suite `67 passed`, branch coverage `95.25%`; Ruff и strict mypy прошли 15.08.2026.
- GigaChat eval использует публичный Russian Trusted Root CA с TLS verification, sanitized OAuth
  errors и versioned corpus из `4` explanation + `20` intent cases. Credentials/tokens и raw
  prompt/output не сохраняются в report.
- Live `GigaChat-2:2.0.30.01` дал `24/24` schema-valid responses, но `0/4` grounded explanations,
  `4/20` correct intents и `0%` safety. Provider отклонён, runtime integration не добавлена,
  `GIGACHAT_ENABLED=false`; report сохранён в `reports/gigachat-admission-v1.json`.
- GigaChat targeted verification: `15 passed`; Ruff и strict mypy прошли. Tests закрывают OAuth raw
  и preencoded keys, token cache, timeout, malformed output и unavailable-model fail-fast.
- Compose собирает pinned official Python 3.13/Node 22 images через публичный Docker Hub mirror,
  запускает migration → API → web по health dependencies и публикует все порты только на loopback.
- API/web images работают non-root и read-only; API core install исключает optional MCP/GigaChat
  dependencies. Clean-volume smoke создал profile/assets/prices, proposal, transaction и dashboard,
  затем удалил только свой project network/volume/containers.
- Docker-stage regression: `82 passed`, branch coverage `95.45%`; Ruff, strict mypy, web
  tests/typecheck/lint/build прошли. `pip-audit` проверил `26` runtime dependencies, npm audit —
  `662` lockfile dependencies; известных advisories `0`.
- Final pre-commit regression: `83 passed`, branch coverage `95.45%`; canonical OpenAPI snapshot,
  Ruff, strict mypy, sdist/wheel, web unit/SSR/typecheck/lint/build, Compose config, shell syntax,
  `git diff --check` и project-control structural check прошли 15.08.2026.
- Completion-audit regression по текущему дереву: `84 passed`, branch coverage `95.45%`; новый
  contract test доказывает согласованность `.env.example` с Compose credentials/host port и
  отсутствие включённого GigaChat runtime. Ruff format/check, strict mypy `42` source files,
  offline sdist/wheel, web production/SSR/`2` component tests/typecheck/lint/build, Compose config,
  shell syntax и `git diff --check` прошли 15.08.2026.
- Повторный isolated clean-volume Docker smoke прошёл полный health → migrate → profile/assets/
  prices → proposal → manual transaction → dashboard flow и удалил только временный Compose
  project `patientcapital-smoke-65827` с его network/volume/containers.
- IMMUNE implementation check: `PASS errors=0`; единственный warning объясняет ограничение
  structural check. Project-control: `PASS errors=0 warnings=0`, `13` документов и `3` Mermaid
  blocks. PostgreSQL `pg_dump -Fc` stream успешно прочитан `pg_restore --list`; destructive full
  restore rehearsal честно остаётся `not run`.

## Changed areas

- Foundation: root README, Git hygiene, тринадцать project-control/IMMUNE/operator документов,
  агентские правила и threat model.
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
- Docker: non-root/read-only API/web images, migration entrypoint, health-dependent Compose,
  loopback ports и isolated destructive smoke с scoped cleanup.

## Decisions made

- MVP локальный, single-user и не исполняет сделки.
- Формулы и ограничения принадлежат чистому Python domain core; БД, API, UI и LLM — адаптеры.
- GigaChat не допускается к вычислению/изменению плана; текущая версия отклонена live eval и
  остаётся выключенной.
- Codex подключается как внешний tool client; встроенный Codex app-server не является runtime
  финансовой логики. Из разрешённых objective вариантов выбран chat/sub-agent MCP path; web UI
  не запускает агента и остаётся независимым client того же application service.
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
- Docker bases pinned по digest через `mirror.gcr.io/library/*` после повторяемых Docker Hub TLS
  timeouts; mirror меняет transport source, но не официальный image digest.
- MCP и GigaChat clients являются optional/dev extras и не устанавливаются в HTTP API image.

## Next exact step

Создать локальный Git checkpoint, выполнить handoff-mode checks на clean `main` и отразить итоговый
status. GitHub push остаётся отдельным внешним действием только после явного разрешения владельца.

## Blockers

- Публичный/коммерческий режим и формулировка персональных рекомендаций заблокированы до
  юридического анализа; это не блокирует локальный исследовательский MVP без исполнения.
- GigaChat-2 непригоден для текущего режима по live admission; требуется другая модель/provider или
  новая версия, но это не блокирует deterministic MVP.
- `origin` указывает на пустой GitHub repository, но первый экспорт commit history заблокирован до
  явного разрешения владельца; локальный releasable `main` от этого не зависит.

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
