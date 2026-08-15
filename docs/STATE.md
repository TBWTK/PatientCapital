---
title: Текущее состояние
type: state
status: active
updated: 2026-08-15
---

# Текущее состояние

## Active objective

Добавить узкую agent surface для Codex поверх тех же application contracts: безопасные read,
propose и record tools без доступа к секретам и без отдельной финансовой арифметики. Доказать
паритет результата между HTTP/UI и tool adapter contract-тестом.

## Acceptance criteria

- [ ] Agent adapter предоставляет только перечисленные read/propose/record operations и валидирует
  аргументы теми же Pydantic contracts, что HTTP.
- [ ] Tool output сохраняет decimal-строки, error envelope, algorithm version, input hash и run id;
  proposal не может быть помечен исполненным.
- [ ] Один seeded snapshot через HTTP и agent adapter даёт один и тот же сохранённый run и числовые
  поля; replay transaction сохраняет exactly-once semantics.
- [ ] Codex-facing инструкция описывает permissions, unknown handling и запрет LLM-арифметики.
- [ ] Negative contract tests закрывают неизвестные tool names, лишние поля, stale price, version и
  idempotency conflicts; Ruff, mypy и полный regression проходят.

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

## Changed areas

- Foundation: root README, Git hygiene, восемь project-control документов, агентские правила и
  threat model.
- Domain: `src/patientcapital/domain`, test fixtures/example/boundary/property suite, Python package
  metadata и locked dev toolchain.
- Persistence/API: initial Alembic migration, SQLAlchemy mappings, application services, shared
  Pydantic contracts, FastAPI transport, PostgreSQL Compose service и integration suite.
- Product UI: `web/app`, generated OpenAPI types, responsive interaction design, component/SSR/a11y
  tests и project-bound social preview asset.

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

## Next exact step

Реализовать in-process/CLI agent adapter над application services и сначала зафиксировать contract
tests на перечисление tool schemas, proposal parity, record replay и запрещённые аргументы.

## Blockers

- Публичный/коммерческий режим и формулировка персональных рекомендаций заблокированы до
  юридического анализа; это не блокирует локальный исследовательский MVP без исполнения.
- Пригодность GigaChat неизвестна до живого фиксированного eval corpus; это не блокирует
  детерминированный core.

## Non-goals

- GigaChat, broker execution и agent-driven изменение profile/asset universe внутри Agent stage.
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
