---
title: Модель угроз
type: security
status: active
updated: 2026-08-16
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
| Sensitive screenshot retention | raw file never in DB/Git/backup; private temp удаляется до ответа draft | host administrator can inspect live process/tmpfs во время OCR |
| Research/source injection | primary-host allowlist, four typed gate citations, provenance/freshness/schema/policy; prose cannot materialize facts | exchange/issuer source can still be wrong or incomplete |
| Monitoring churn or duplicate alert | versioned thresholds, idempotent run/alert keys, no transaction/order tool | noisy but non-executing recommendations |
| Market-wide request amplification | board fetch + deterministic liquidity prefilter + bounded dividend fan-out/timeouts | MOEX availability/rate limits can block a cold proposal |
| Screen presented as fundamental audit | typed `market_screen` scope, explicit unknown fields and source URLs | historical dividends do not predict future payments |
| Stale cache silently reused | persisted expiry, fail-loud stale/provider error, immutable scan id in proposal | delayed MOEX facts remain non-real-time even when fresh by policy |
| Однодневный spike принят за ликвидность | 20 completed-session coverage/median turnover и class thresholds; top-N только enrichment queue | thresholds требуют периодической калибровки под режим рынка |
| LLM/opinion превращён в issuer verdict | typed primary evidence, exact security/ISIN, source hashes, immutable gates и deterministic status; narrative не входит в decision hash | reviewed runtime packet пока есть только для MOEX; остальные equity остаются unknown |
| Старый PC3 cache обходит новый gate | cache namespace фильтрует provider/scan policy и требует matching admission run | ошибочная ручная DB-операция вне приложения остаётся operator risk |

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

PC2 upload/extractor local-only: Pillow проверяет decoded JPEG/PNG, MIME/magic, bytes/pixels; generated
0600 files находятся в 0700 tmpfs directory, Tesseract rus/eng ограничен timeout, а context manager
очищает artifacts до ответа. Filename не используется как путь, raw image внешнему provider не
передаётся; любой будущий внешний extractor требует нового admission и data-flow review.
Monitor получает только read/evidence capabilities и технически не импортирует ledger/order command.

Issuer provider допускает только HTTPS hosts MOEX/ISS/Банка России, exact security/ISIN и документы
с publication/effective/retrieval times и content SHA-256. Research summary отображается как
контекст, но не входит в evidence hash, verdict или арифметику. Identity mismatch, конфликт,
просрочка, неизвестный balance/governance, непокрытая выплата, adverse action или недостаточная
ликвидность не становятся `eligible`. Добавление issuer domain/adapter требует отдельного review и
eval, а не расширения через prompt. Открытые новости могут быть discovery lead, но не typed fact.

## Production blockers

До коммерческого или многопользовательского режима необходимы legal opinion, identity/RBAC,
tenant isolation, encryption/backup/retention policy, audit-log protection, incident response,
data-processing agreement для внешних providers, market-data licensing и анализ требований к
аккредитации robo-adviser ПО.
