---
title: Эксплуатация PatientCapital
type: operations
status: stable
updated: 2026-08-15
---

# Эксплуатация PatientCapital

## Поддерживаемый контур

MVP поддерживает только локальный single-user Docker Compose на доверенном host. `api` делает
исходящие HTTPS-запросы только к allowlisted delayed MOEX ISS endpoint; `db`, `api` и
`web` публикуются на `127.0.0.1`; Internet exposure, reverse proxy и remote access не поддерживаются.
PostgreSQL named volume — единственное persisted product state. API и web images non-root,
read-only; `/tmp` — ephemeral tmpfs. GigaChat credentials не передаются контейнерам.

PC2 планирует отдельный `worker` process из того же Python image для scheduled read-only evidence
refresh и alert evaluation. Он не получает broker/order capability и не пишет transactions. До
реализации worker не добавляется в Compose. Upload bytes обрабатываются только в bounded API tmpfs;
в backup попадают extracted drafts/evidence, но не raw images.

Нужны Docker Compose v2. Для `scripts/docker-smoke.sh` дополнительно нужны host `curl`, `jq` и
свободные ports `53000`, `58000`, `55433` либо соответствующие `PATIENTCAPITAL_SMOKE_*` overrides.

## Конфигурация

Без `.env` Compose использует local defaults. Для изменения ports/PostgreSQL credentials скопируйте
`.env.example` в ignored `.env` и смените `POSTGRES_PASSWORD`. Значение host `DATABASE_URL` в
example предназначено для запуска Python с host; Compose всегда передаёт API внутренний адрес `db`.
GigaChat fields не включают runtime mode и используются только при явно запущенном future re-eval.
`MOEX_ISS_BASE_URL` allowlisted кодом и не может быть перенаправлен на произвольный host;
`MOEX_TIMEOUT_SECONDS` и `MOEX_MAX_AGE_SECONDS` задают fail-closed transport/freshness границы.

Планируемая PC2 config должна иметь безопасные явные defaults: `MONITOR_RUNS_PER_DAY` принимает
только `3` или `4`; расписание хранится с timezone, а missed/duplicate ticks идемпотентны. Upload
bytes/pixels/TTL и extractor mode задаются отдельными bounded settings. External extractor остаётся
disabled, пока его data contract и admission не приняты; отсутствие extractor показывает
`unavailable`, не маскируется ручным успехом.

## Startup и health

```bash
docker compose up --build --wait
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
curl --fail http://127.0.0.1:3000/
docker compose ps
```

PostgreSQL должен стать healthy до API. API entrypoint выполняет idempotent `alembic upgrade head`,
затем readiness проверяет DB query. Web стартует только после healthy API. Ошибка migration/health
останавливает dependency chain и не должна маскироваться ручным restart loop.

## Logs и диагностика

```bash
docker compose logs --tail=200 db api web
docker compose ps
docker compose config --quiet
```

`/health/live` доказывает только процесс API; `/health/ready` отдельно доказывает DB dependency.
Product metrics/SLO/alerts не реализованы и обязательны до любого production/public режима.

После PC2 monitor health/readiness должны различать scheduler process, last successful evidence
refresh и provider degradation. Provider failure не делает существующий ledger недоступным и не
создаёт повторный alert; stale status остаётся видимым в web.

## Shutdown и очистка

```bash
docker compose down
```

Обычный `down` сохраняет named volume. `docker compose down --volumes` удаляет все product data и
допустим только для осознанного reset после проверенного backup. Изолированный smoke безопаснее:

```bash
./scripts/docker-smoke.sh
```

Smoke создаёт уникальный Compose project, проверяет health → profile → live automatic proposal →
отдельный явно помеченный simulated transaction fact → dashboard и cleanup удаляет только его
containers/network/volume. Числа proposal не преобразуются в transaction автоматически.

## Backup

Создавайте logical dump до upgrade, destructive reset или работы с volume. Команда пишет
конфиденциальный файл на host; хранение, encryption и access control принадлежат оператору.

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > patientcapital.dump
docker compose exec -T db pg_restore --list < patientcapital.dump >/dev/null
```

`.env`, GigaChat credentials и Codex global registration в dump не входят.

## Restore и rollback

Restore **destructive** для target DB. В текущем handoff full restore rehearsal не выполнялся;
поэтому recovery time и data-loss window являются `unknown`. Перед реальным restore остановите
`api`/`web`, сохраните текущий dump и используйте отдельный Compose project/volume для rehearsal.

```bash
docker compose stop api web
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' \
  < patientcapital.dump
docker compose up --wait api web
```

Application rollback безопасен только если старая версия понимает текущую DB schema. Migration
downgrade удаляет tables/data и не является operational rollback. При несовместимой migration
возвращайтесь к pre-upgrade dump в новом volume; не запускайте старый image поверх неизвестной schema.

## Upgrade procedure

1. Проверить clean Git checkpoint, changelog/decision и backup.
2. Выполнить `docker compose build --pull` и deterministic checks из `docs/QUALITY.md`.
3. Выполнить isolated `scripts/docker-smoke.sh`.
4. Запустить основной `docker compose up --wait`; проверить health и UI.
5. При failure сохранить logs и не менять данные вручную; rollback по правилам выше.

## Известные operational limits

- Auth, RBAC, TLS termination, remote access, HA, automated backups, monitoring и alerting отсутствуют.
- PC2 worker, upload extractor и alert persistence пока planned; документ не утверждает их наличие.
- Capacity выше 10 000 ledger events и proposal latency на 100 assets не измерены.
- PostgreSQL backup artifact проверен на читаемый catalog; destructive restore rehearsal не запущен.
- Base-image/dependency audit — point-in-time evidence 15.08.2026, а не бессрочная гарантия.
- GitHub `origin/main` опубликован после явного разрешения владельца; upstream/default branch
  проверены. Force-push, tags и release automation не входят в текущий operational contract.
