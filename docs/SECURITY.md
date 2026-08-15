---
title: Модель угроз
type: security
status: active
updated: 2026-08-15
---

# Модель угроз

## Защищаемые активы

Финансовый профиль, брокерские параметры, ledger, holdings, суммы пополнений, price snapshots,
recommendation runs, GigaChat credentials, Codex permissions и доказательства eval.

## Trust boundaries

- Browser → local API: недоверенный ввод, даже в single-user режиме.
- API → PostgreSQL: транзакционная граница и least-privilege credentials.
- Application → GigaChat eval: внешняя сеть; live-аудит использует только synthetic corpus.
  Runtime connection отклонён и отсутствует.
- Application → MOEX ISS: единственный runtime outbound HTTPS host для delayed public market facts;
  портфель/ledger/profile не отправляются, request содержит только публичные board/security IDs.
- Codex/agent → tools: модельный клиент не получает произвольный SQL, shell или broker capability.
- Host → Docker: `.env`, CA bundle, volumes и published ports принадлежат оператору.

PC2 добавляет trust boundaries: browser → bounded upload parser; extractor/resolver → unconfirmed
draft; research adapters → typed evidence; scheduler → monitor policy. Ни одна из них не получает
broker order capability.

## Угрозы и обязательные контроли

| Угроза | Контроль MVP | Остаточный риск |
| --- | --- | --- |
| Утечка ключей | `.env` ignored; secrets не логируются/API; env-only injection | администратор host/container видит env |
| Ошибочная/выдуманная LLM рекомендация | deterministic run SSOT; текущий Giga runtime отсутствует | future model prose остаётся недоверенным даже после gate |
| Скрытая неполнота данных | typed `unknown`, freshness и blocked run | пользователь может ввести неверный факт |
| Несанкционированное изменение ledger | append-only events, idempotency, DB transaction | single-user MVP без identity audit |
| Повторная запись покупки | idempotency key и 409 conflict | ручной ввод с новым ключом остаётся возможен |
| Подмена цены/fee | versioned source/effective date, immutable run snapshot | manual source не подтверждает рыночную истинность |
| Подмена/отказ MOEX payload | fixed HTTPS host, strict status/type/currency/schema/as-of validation, no fallback | DNS/TLS/provider availability и delayed nature feed |
| Prompt/tool injection | allowlisted typed tools; no shell/SQL/broker tool; output validation | социальная инженерия пользователя |
| TLS downgrade GigaChat | CA bundle и verify=true; fail closed | ротация CA требует обновления |
| Публикация локального MVP | bind localhost по умолчанию; docs запрещают Internet exposure | оператор может изменить Compose |
| Регуляторный/consumer harm | no execution, no return forecast, explicit scope, legal gate | disclaimer не гарантирует выход из регулирования |
| Malicious/oversized image | MIME/magic-byte/dimension/size limits, generated filename, private tmpfs, timeout | parser/library vulnerability |
| OCR/vision hallucination | output is unconfirmed draft, field confidence/unknowns, exact human confirmation | пользователь может подтвердить неверный draft |
| Sensitive screenshot retention | raw file never in DB/Git/backup; delete on decision or 24h expiry | host administrator can inspect live tmpfs |
| Research/source injection | allowlisted typed adapters, provenance/freshness, prose cannot materialize facts | issuer/public source can be misleading |
| Monitoring churn or duplicate alert | versioned thresholds, idempotent run/alert keys, no transaction/order tool | noisy but non-executing recommendations |

## Условия эксплуатации MVP

Контур запускается локально и не публикуется в Интернет. У него нет production authentication,
CSRF/RBAC, tenant isolation, broker order capability или юридически утверждённого процесса
инвестиционного консультирования. Поэтому доступ за пределами доверенного host запрещён. Живой
GigaChat не прошёл quality gate и остаётся выключенным. Повторный eval разрешён только с TLS
verification; `verify=false` запрещён.

Compose публикует db/API/web только на `127.0.0.1`. API и web работают non-root с read-only root
filesystem и отдельным `/tmp`; readiness API зависит от PostgreSQL, а web стартует после API.
MCP/GigaChat credentials не передаются в Compose. HTTPX входит в API только для allowlisted MOEX
adapter; URL нельзя переопределить на другой host. Python runtime и npm lockfile audit 15.08.2026
дали `0` известных advisories до этого product change; повторный audit обязателен перед handoff.

PC2 upload/extractor остаётся local-only, пока отдельный admission и data-flow review не разрешат
конкретного внешнего provider. Upload parser должен ограничивать bytes, pixels, media types и время,
не доверять filename/metadata, не исполнять embedded content и очищать temp artifacts по retention.
Monitor получает только read/evidence capabilities и технически не импортирует ledger/order command.

## Production blockers

До коммерческого или многопользовательского режима необходимы legal opinion, identity/RBAC,
tenant isolation, encryption/backup/retention policy, audit-log protection, incident response,
data-processing agreement для внешних providers, market-data licensing и анализ требований к
аккредитации robo-adviser ПО.
