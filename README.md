# PatientCapital

PatientCapital — локальный single-user инструмент для долгосрочного портфеля. Пользователь задаёт
сумму нового пополнения, целевые доли, текущие позиции, цены, лоты и комиссии; система строит
воспроизводимый план покупок, показывает отклонение портфеля от целей и сохраняет фактически
совершённые операции.

На этапе MVP продукт является **инструментом поддержки решения**, не отправляет поручения брокеру
и не обещает доходность. Арифметикой и ограничениями владеет детерминированный доменный движок.
Codex может получать факты через узкие tools и объяснять результат; модель не имеет права подменять
сумму, инструмент, цену, комиссию или решение о возможности расчёта. Проверенный GigaChat-режим в
runtime отсутствует, потому что модель не прошла admission eval.

## Статус

Локальный MVP проверен: deterministic domain core, versioned PostgreSQL/API, responsive web UI,
Codex MCP и Docker-контур. Live-аудит `GigaChat-2` отклонил экспериментальный режим. Точная линия
исполнения, критерии и доказательства находятся в
[docs/STATE.md](docs/STATE.md).

## Документация

- [Назначение и границы](docs/README.md)
- [Аудит идеи, контекста и рисков](docs/AUDIT.md)
- [IMMUNE-принципы](docs/IMMUNE.md)
- [Текущее состояние](docs/STATE.md)
- [Roadmap](docs/ROADMAP.md)
- [Архитектура и первичный аудит](docs/ARCHITECTURE.md)
- [Данные](docs/DATA.md)
- [Качество и evals](docs/QUALITY.md)
- [Модель угроз](docs/SECURITY.md)
- [Эксплуатация и восстановление](docs/OPERATIONS.md)
- [Технический долг](docs/DEBT.md)

## Проверенный backend-контур

```bash
uv sync --group dev
docker compose up -d db
TEST_DATABASE_URL=postgresql+psycopg://patientcapital:patientcapital@localhost:55432/patientcapital \
  .venv/bin/pytest -q tests
```

На 15.08.2026 чистая Alembic migration, PostgreSQL integration и полный Python regression проходят:
`82 passed`, branch coverage `95.45%`.

## Web UI

```bash
uv run uvicorn patientcapital.api.app:app --host 127.0.0.1 --port 8000
cd web
npm ci
npm run dev
```

Интерфейс доступен на `http://localhost:3000`, API — на `http://127.0.0.1:8000`.

## Docker MVP

```bash
docker compose up --build --wait
# web: http://127.0.0.1:3000, API: http://127.0.0.1:8000
docker compose down
```

PostgreSQL data остаются в named volume после обычного `down`. Изолированный destructive smoke
создаёт отдельный project/volume, проверяет полный flow и удаляет только свои ресурсы:

```bash
./scripts/docker-smoke.sh
```

## Codex agent mode

Локальный MCP server предоставляет шесть allowlisted tools: чтение профиля/активов/аналитики/run,
создание неизменяемого proposal и отдельная идемпотентная запись подтверждённой сделки.

```bash
docker compose up -d db
uv sync --group dev
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
