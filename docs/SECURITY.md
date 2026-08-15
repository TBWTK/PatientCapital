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
- Codex/agent → tools: модельный клиент не получает произвольный SQL, shell или broker capability.
- Host → Docker: `.env`, CA bundle, volumes и published ports принадлежат оператору.

## Угрозы и обязательные контроли

| Угроза | Контроль MVP | Остаточный риск |
| --- | --- | --- |
| Утечка ключей | `.env` ignored; secrets не логируются/API; env-only injection | администратор host/container видит env |
| Ошибочная/выдуманная LLM рекомендация | deterministic run SSOT; schema + numeric grounding + fallback | убедительный, но неуместный prose после допуска |
| Скрытая неполнота данных | typed `unknown`, freshness и blocked run | пользователь может ввести неверный факт |
| Несанкционированное изменение ledger | append-only events, idempotency, DB transaction | single-user MVP без identity audit |
| Повторная запись покупки | idempotency key и 409 conflict | ручной ввод с новым ключом остаётся возможен |
| Подмена цены/fee | versioned source/effective date, immutable run snapshot | manual source не подтверждает рыночную истинность |
| Prompt/tool injection | allowlisted typed tools; no shell/SQL/broker tool; output validation | социальная инженерия пользователя |
| TLS downgrade GigaChat | CA bundle и verify=true; fail closed | ротация CA требует обновления |
| Публикация локального MVP | bind localhost по умолчанию; docs запрещают Internet exposure | оператор может изменить Compose |
| Регуляторный/consumer harm | no execution, no return forecast, explicit scope, legal gate | disclaimer не гарантирует выход из регулирования |

## Условия эксплуатации MVP

Контур запускается локально и не публикуется в Интернет. У него нет production authentication,
CSRF/RBAC, tenant isolation, broker order capability или юридически утверждённого процесса
инвестиционного консультирования. Поэтому доступ за пределами доверенного host запрещён. Живой
GigaChat не прошёл quality gate и остаётся выключенным. Повторный eval разрешён только с TLS
verification; `verify=false` запрещён.

## Production blockers

До коммерческого или многопользовательского режима необходимы legal opinion, identity/RBAC,
tenant isolation, encryption/backup/retention policy, audit-log protection, incident response,
data-processing agreement для внешних providers, market-data licensing и анализ требований к
аккредитации robo-adviser ПО.
