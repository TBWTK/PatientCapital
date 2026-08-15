---
title: "ADR 0001: локальная MCP agent surface"
type: decision
status: accepted
updated: 2026-08-15
---

# ADR 0001: локальная MCP agent surface

## Контекст

Codex должен читать локальный портфель, создавать тот же deterministic contribution proposal и по
явному запросу записывать фактическую операцию. Встраивание финансовой логики в prompt/модель
создало бы второй источник истины. Remote agent endpoint потребовал бы authentication и публикации
конфиденциальных финансовых данных, которых нет в scope single-user MVP.

MCP определяет model-controlled tools, structured content/output schema и annotations для
read-only/idempotent/destructive semantics. Для локальных интеграций stdio позволяет host запускать
server как дочерний процесс без слушающего сетевого порта. Официальный Python SDK v2 обслуживает
современную и handshake-era ревизии одним entrypoint.

## Решение

- Использовать `mcp>=2,<3`, Python `MCPServer` и stdio entrypoint `patientcapital-mcp`.
- Предоставить только `get_profile`, `list_assets`, `get_portfolio`, `propose_contribution`,
  `get_recommendation`, `record_transaction`.
- Вызывать существующие application services через injected SQLAlchemy session factory; HTTP и MCP
  не дублируют формулы или persistence rules.
- Возвращать Pydantic structured output с decimal-строками. Expected business errors кодируются тем
  же `{"error":{"code","message"}}`, что HTTP, и остаются MCP tool errors.
- Принудительно использовать `extra=forbid` для top-level arguments: SDK 2.0 создаёт dynamic input
  models с `extra=ignore`, что не соответствует fail-loud инварианту PatientCapital.
- Пометить read tools read-only/idempotent/closed-world; proposal — non-idempotent audit write;
  transaction — append-only idempotent write. Запись требует явно подтверждённых пользователем
  фактов и не может автоматически следовать из proposal.
- Зарегистрировать локальный absolute entrypoint в Codex. Credentials GigaChat, shell, SQL и broker
  capability server не получает.

## Последствия

- Codex/ChatGPT UI может работать с портфелем через стандартный tool contract; отдельный чат runtime
  в приложении не нужен.
- Перемещение workspace требует повторной регистрации absolute entrypoint. Для распространяемой
  версии возможен MCP bundle, но он не нужен локальному MVP.
- PostgreSQL должен быть доступен до data tools; discovery работает без подключения к БД.
- Model annotations являются подсказками host, а не authorization. Обязательная защита остаётся в
  allowlist, Pydantic/DB contracts и правилах `AGENTS.md`.

## Доказательства

- MCP wire suite проверяет exact tool set/schema/annotations, реальный stdio subprocess, structured
  output, HTTP retrieval parity, idempotent replay и stale/extra/unknown errors.
- Полный regression на дату решения: `67 passed`, branch coverage `95.25%`, Ruff и strict mypy.
- Источники: [MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools),
  [официальный Python SDK](https://github.com/modelcontextprotocol/python-sdk).
