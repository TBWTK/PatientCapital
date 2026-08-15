# PatientCapital

PatientCapital — локальный single-user инструмент для долгосрочного портфеля. Пользователь задаёт
сумму нового пополнения, целевые доли, текущие позиции, цены, лоты и комиссии; система строит
воспроизводимый план покупок, показывает отклонение портфеля от целей и сохраняет фактически
совершённые операции.

На этапе MVP продукт является **инструментом поддержки решения**, не отправляет поручения брокеру
и не обещает доходность. Арифметикой и ограничениями владеет детерминированный доменный движок.
Codex и потенциальный GigaChat могут только получать его факты и объяснять результат; модель не
имеет права подменять сумму, инструмент, цену, комиссию или решение о возможности расчёта.

## Статус

Детерминированный domain core, versioned PostgreSQL/API, responsive web UI и Codex MCP проверены.
Live-аудит `GigaChat-2` отклонил экспериментальный режим; активен Docker gate. Точная линия
исполнения, критерии и доказательства находятся в
[docs/STATE.md](docs/STATE.md).

## Документация

- [Назначение и границы](docs/README.md)
- [Текущее состояние](docs/STATE.md)
- [Roadmap](docs/ROADMAP.md)
- [Архитектура и первичный аудит](docs/ARCHITECTURE.md)
- [Данные](docs/DATA.md)
- [Качество и evals](docs/QUALITY.md)
- [Модель угроз](docs/SECURITY.md)
- [Технический долг](docs/DEBT.md)

## Проверенный backend-контур

```bash
uv sync --group dev
docker compose up -d db
TEST_DATABASE_URL=postgresql+psycopg://patientcapital:patientcapital@localhost:55432/patientcapital \
  .venv/bin/pytest -q tests
```

На 15.08.2026 чистая Alembic migration, PostgreSQL integration и domain regression проходят:
`67 passed`, branch coverage `95.25%`.

## Web UI

```bash
uv run uvicorn patientcapital.api.app:app --host 127.0.0.1 --port 8000
cd web
npm ci
npm run dev
```

Интерфейс доступен на `http://localhost:3000`, API — на `http://127.0.0.1:8000`. Полный web/API
Compose-запуск будет добавлен на Docker gate; документация не выдаёт планируемую команду за
работающую.

## Codex agent mode

Локальный MCP server предоставляет шесть allowlisted tools: чтение профиля/активов/аналитики/run,
создание неизменяемого proposal и отдельная идемпотентная запись подтверждённой сделки.

```bash
docker compose up -d db
codex mcp add patientcapital -- "$(pwd)/.venv/bin/patientcapital-mcp"
codex mcp get patientcapital --json
```

MCP работает через stdio, не открывает порт и не получает произвольный SQL, shell, broker access или
GigaChat credentials. Точные agent permissions и обязательное разделение proposal/execution заданы
в [AGENTS.md](AGENTS.md).

## GigaChat audit

Экспериментальный provider технически вернул валидный JSON Schema для всех 24 synthetic cases, но
не прошёл продуктовый admission: `0/4` grounded explanations, `4/20` intent cases и `0%` safety.
Поэтому GigaChat не подключён к runtime и `GIGACHAT_ENABLED=false`; deterministic API, web и Codex
режимы не зависят от него. Воспроизводимый отчёт без prompt/output/secret payload находится в
[`reports/gigachat-admission-v1.json`](reports/gigachat-admission-v1.json).
