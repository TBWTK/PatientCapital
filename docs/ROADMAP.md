---
title: Этапы проекта
type: roadmap
status: stable
updated: 2026-08-16
---

# Этапы проекта

| Этап | Проверяемый результат | Критерий завершения | Статус |
| --- | --- | --- | --- |
| Foundation | Требования, IMMUNE, аудит, архитектурные/data/security/quality contracts | Project-control check; placeholders и секреты отсутствуют | done |
| Domain | Чистый движок превращает snapshot и взнос в объяснимый дискретный план | Capability/property tests: бюджет, веса, комиссии, unknown | done |
| Persistence/API | Профиль, цели, активы, цены, операции и runs доступны через versioned API | Migration + repository + API integration tests | done |
| Product UI | Пополнение, аналитика, ручная покупка и профиль работают в web UI | Component tests + user-flow browser QA | done |
| Agent surface | Codex использует узкие read/propose/record tools поверх того же core | Contract test доказывает parity UI/API/tool output | done |
| GigaChat gate | Provider проверен на фиксированном corpus и либо допущен только к объяснению, либо отклонён | 100% schema/safety/math-grounding gates + отчёт | done |
| Docker | Web, API и PostgreSQL поднимаются одним Compose-контуром | Clean-volume smoke + health + e2e contribution flow | done |
| MVP handoff | Реализация, docs, tests и Git описывают одну правду | Full regression, IMMUNE/project audit, clean releasable `main` | done |
| Automatic discovery | Сумма и profile без ручного universe дают source-backed пяти-летний proposal | MOEX/policy/API/MCP/web capability, negative provider paths и Docker E2E | done |
| Fixed-income ledger | Clean price, НКД и fee сохраняются раздельно и дают точный cost basis | Additive migration + screenshot capability + API/MCP/web/Docker regression | done |
| PC2 intent contract | Assistant-first сценарий восстановим без истории чата | README/ADR 0004/architecture/data/security/quality coherence + docs audit | done |
| PC2-1 Product shell | Сумма даёт `1..3` стратегические карточки с compact-first explanation; новая IA не требует manual ledger | Capability/component/a11y/browser tests; v1 numeric parity | done |
| PC2-2 Transaction assistant | Text/image создают draft, exact confirmation — ledger event; advanced fallback сохранён | Parser/admission corpus + ambiguity/security/API/MCP/web E2E + migration | done |
| PC2-3 Analytics | Главная объясняет стоимость, денежные потоки, результат, доход, drift и freshness | Ledger/cashflow fixtures + API/component/chart/a11y/browser evidence | done |
| PC2-4 Research universe | Dividend-stock category доступна только через source-backed versioned policy | Source contracts + policy/capability/negative/live-read-only gates | done |
| PC2-5 Monitoring | Сбор `3..4/day` создаёт только threshold/event alerts и никогда не торгует | Clock/idempotency/provider-failure/no-order/resilience/Docker worker tests | done |
| PC3 intent/architecture | Динамический search отделён от ranking/calculation и восстановим без чата | ADR 0005 + state/data/security/quality coherence + docs audit | done |
| PC3-1 Dynamic scanner | TQOB/TQBR и dividend history дают persisted immutable snapshot без ticker allowlist | Provider contracts + migration + cache/failure/capacity tests | done |
| PC3-2 Budget ranking | Сумма и portfolio snapshot выбирают инструменты по versioned market evidence | Capability/property/metamorphic tests + exact trace | done |
| PC3-3 Background/on-demand | Worker обновляет `4/day`, stale request делает bounded live refresh | Clock/idempotency/resilience/API/MCP tests | done |
| PC3-4 Explainable product | Web показывает scan freshness/coverage/why/rejected alternatives | Generated types + component/a11y/browser/Docker live journey | done |
| PC3 handoff | PC3 contracts, implementation, data и operations говорят одну правду | Full regression, live MOEX inspection, clean releasable checkpoint | done |
| PC2-MVP handoff | Все PC2 acceptance доказаны, existing ledger сохранён, docs/code/Git согласованы | Migration rehearsal + full regression + Docker E2E + browser QA + IMMUNE audit | done |

Допустимые статусы: `planned`, `active`, `blocked`, `done`.
