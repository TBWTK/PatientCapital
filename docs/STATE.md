---
title: Текущее состояние
type: state
status: stable
updated: 2026-08-16
---

# Текущее состояние

## Active objective

**Completed:** покупка облигации сохранена без искажения подтверждённых фактов: clean unit price,
общий НКД и комиссия хранятся отдельно, а cost basis включает все три компонента. Screenshot-backed
BUY `SU26226RMFS9` от 13.08.2026 записан после backward-compatible migration и полного gate.

## Acceptance criteria

- [x] `TransactionCreate/Response`, PostgreSQL и MCP имеют явный `accrued_interest_total >= 0`;
  старые payload/rows совместимы через доказанный default `0.00`.
- [x] BUY cost basis равен `clean price × quantity + accrued_interest_total + fee`; clean price и
  НКД не сворачиваются в выдуманную unit price.
- [x] Screenshot fixture `7 × 992.04 + 195.16 + 3.47` даёт cost basis `7 142.91 RUB`, quantity `7`
  и сохраняет timestamp `2026-08-13T13:34:00Z` без автоматического broker execution.
- [x] Web manual-ledger form и generated OpenAPI client принимают НКД отдельно; idempotency hash
  различает операции с разным НКД.
- [x] Migration на существующем Docker volume, full Python/web regression, MCP/API contracts,
  project/IMMUNE checks и локальная portfolio inspection проходят до записи факта.
- [x] PostgreSQL integration tests fail closed unless the database name ends with `_test`; their
  cleanup cannot truncate the persistent local `patientcapital` database.
- [x] Пользователь с настроенным profile вводит только сумму (reference case `8 000 RUB`) и получает
  proposal без предварительного ручного создания assets/prices/targets.
- [x] Default horizon в новом UI — 5 лет; risk/fees/holdings берутся из profile, неизвестные
  material inputs блокируют расчёт, а не получают hidden defaults.
- [x] MOEX adapter валидирует RUB, active status, type, lot, price, timestamp и источники; для ОФЗ
  dirty unit cost и maturity evidence воспроизводимы, provider/network failure виден.
- [x] Versioned policy выбирает source-backed ОФЗ и broad-index equity fund; LLM не владеет
  universe/weights/prices/lots/totals и не создаёт transaction.
- [x] HTTP, web и MCP возвращают один сохранённый run с source/policy evidence; предложение явно
  отличается от исполнения, а выбранный инструмент доступен для отдельного manual ledger record.
- [x] Unit/contract/integration/web/MCP/Docker/live-provider проверки проходят и записаны ниже.
- [x] `AUDIT.md` классифицирует исходный контекст, аудит идеи/архитектуры/рисков/GigaChat,
  альтернативы, достаточность контекста и оставшиеся unknown по inspectable evidence.
- [x] `IMMUNE.md` владеет принципами и mutation protocol; `AGENTS.md` ссылается на него без
  дублированного authority.
- [x] `DATA.md` и новый operator contract описывают только фактическую schema, Docker lifecycle,
  persistence/recovery и явно маркированные непроверенные ограничения.
- [x] `QUALITY.md` отображает каждое требование/существенный риск в named evidence и честный status.
- [x] IMMUNE/project-control handoff checks, docs links, `git diff --check` и релевантный regression
  проходят; checkpoint находится на чистом локальном `main`.
- [x] После явного разрешения владельца `origin/main` опубликован; GitHub `HEAD` указывает на
  `refs/heads/main`, а local/upstream revisions совпадают.

## Current verified state

- Screenshot inspection подтвердил две сделки `2 + 5` шт. по clean price `992.04 RUB`, общий НКД
  `195.16 RUB`, debit до комиссии `7 139.44 RUB`, fee `3.47 RUB` и время 13.08.2026 16:34 МСК.
- Additive migration `20260816_0002` прошла на существующем named volume. Transaction
  `cbf1d309-0597-4415-aa35-675bc2fce3df` сохранён с idempotency key
  `t-invest-20260813-su26226-buy-7-1634`; API portfolio inspection вернул quantity `7`, cost basis
  `7 142.91 RUB`, clean-price market value `6 964.09 RUB` при подтверждённой цене `994.87 RUB`.
- Финальный Python regression: `141 passed`, branch coverage `94.46%`; Ruff format/check, strict
  mypy (`51` source files), offline sdist/wheel и canonical OpenAPI snapshot прошли 16.08.2026.
- Web: `4` component tests, TypeScript, ESLint, SSR и production build прошли локально и в pinned
  Node container. Desktop и `390×844` browser inspection подтвердили отдельный `НКД всего`, только
  active asset в ledger selector и итоговый dashboard; console warnings/errors отсутствуют.
- Clean-volume Docker smoke `patientcapital-smoke-10952` прошёл и удалил scoped containers/network/
  volume. Main Compose после rebuild healthy; profile восстановлен как 5 лет / growth /
  Т-Инвестиции / `0.05%` после обнаруженного прежнего test-data contamination.
- Причина contamination устранена на уровне генератора: destructive integration fixture создаёт
  `patientcapital_test` и fail closed для database name без `_test`. Проверка на отдельной БД прошла;
  inactive fixtures больше не показываются в ledger selector.
- Исходный product gap был воспроизведён: legacy `/v1/recommendations` требовал ручной universe, а
  web Settings просил ticker/name/lot/target/price/source. Основной UI теперь amount-only и 5-летний.
- Controlled read-only MOEX ISS inspection 15.08.2026 подтвердил active boards `TQOB`/`TQBR`,
  RUB OFZ price/face/accrued-interest/maturity/yield/turnover fields и active index-fund candidates
  `TMOS`, `SBMX`, `EQMX` с lot/price/turnover timestamps; adapter воспроизводит эти поля fixtures.
- Requirements/architecture checkpoint записан в README/AUDIT/ARCHITECTURE/QUALITY и ADR 0003;
  project-control structural check: `PASS errors=0 warnings=0`, 14 документов, 3 Mermaid blocks.
- Backend discovery checkpoint: versioned `five-year-moex-v1` policy, strict MOEX ISS adapter,
  amount-only HTTP use case, market evidence materialization и MCP method реализованы. Targeted
  evidence: `12 passed`; Ruff и strict mypy (`31` source files) прошли 15.08.2026.
- Финальный automatic-discovery regression: `138 passed`, branch coverage `94.45%`; Ruff
  format/check, strict mypy (`51` source files), offline sdist/wheel и canonical OpenAPI snapshot
  прошли 15.08.2026. Boundary suite проверяет malformed/empty MOEX blocks, invalid decimal/lot/time,
  stale/non-RUB/unsupported facts и отсутствие silent fallback.
- Web production build, SSR, `3` component/a11y tests, TypeScript и ESLint прошли. Живой browser QA
  на desktop и `390×844` выполнил amount-only `8 000 RUB` flow; console errors/warnings отсутствуют.
- Контролируемый live run на delayed MOEX data от 14.08.2026 выбрал `SU26218RMFS6` и `EQMX`, сохранил
  policy/source/as-of evidence и предложение: spent `6 914,36 RUB`, leftover `85,64 RUB`; число
  transactions после proposal осталось `0`.
- Isolated clean-volume smoke `patientcapital-smoke-86380` прошёл build/health/migrate/profile →
  live discovery → proposal → отдельно подтверждённый simulated ledger fact → dashboard; все его
  containers/network/volume удалены scoped cleanup.
- После явного разрешения владельца первый export выполнен командой `git push -u origin main`.
  GitHub создал `main`, назначил его `HEAD`, upstream настроен; read-only verification показала
  одинаковый local/remote SHA `7b0ba814b614206fd0ff289278858e2b80ae2e04` до evidence-update.
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
- Codex agent surface реализован как локальный Python MCP 2.0 stdio server с семью allowlisted
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
- Completion audit сохранён в checkpoints `d6904ad` и `7b0ba81`; после commit worktree clean.
  Repository-owner разрешил первый export, GitHub publication проверена и больше не является
  blocker. Новый automatic-discovery checkpoint остаётся локальным до отдельного решения владельца
  о публикации; это не ослабляет требование clean/releasable `main`.

## Changed areas

- Fixed-income ledger: transaction schema/contract, cost-basis projection, migration, API/MCP/web
  adapters, test-database isolation, tests and owner docs.
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

- Для облигаций `unit_price` означает подтверждённую clean price, а `accrued_interest_total` — общий
  НКД всей операции. BUY cost basis добавляет оба значения и fee; поле не выводится из тарифа или
  текста модели. Для non-bond/backward-compatible events НКД равен `0.00`.
- Destructive PostgreSQL integration cleanup разрешён только для отдельной базы с именем `_test`;
  постоянная local product database никогда не является тестовой fixture.
- MVP локальный, single-user и не исполняет сделки.
- Формулы и ограничения принадлежат чистому Python domain core; БД, API, UI и LLM — адаптеры.
- GigaChat не допускается к вычислению/изменению плана; текущая версия отклонена live eval и
  остаётся выключенной.
- Codex подключается как внешний tool client; встроенный Codex app-server не является runtime
  финансовой логики. Из разрешённых objective вариантов выбран chat/sub-agent MCP path; web UI
  не запускает агента и остаётся независимым client того же application service.
- Основной market-data source — delayed MOEX ISS через allowlisted HTTPS adapter; ручная цена
  остаётся legacy/advanced surface и не является prerequisite amount-only сценария.
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

При следующем пополнении пользователь сообщает только сумму; выполнить deterministic proposal на
текущем profile/portfolio и показать run id, algorithm/policy versions и source evidence.

## Blockers

- Публичный/коммерческий режим и формулировка персональных рекомендаций заблокированы до
  юридического анализа; это не блокирует локальный исследовательский MVP без исполнения.
- GigaChat-2 непригоден для текущего режима по live admission; требуется другая модель/provider или
  новая версия, но это не блокирует deterministic MVP.

## Non-goals

- Полный coupon schedule, налоговый учёт НКД, realized P&L и автоматическая broker reconciliation.
- Вычисление allocation, broker execution и отправка полного portfolio/ledger во внешний provider.
- Свободный подбор отдельных акций по LLM-тексту, прогноз доходности и real-time quotation claim.
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
