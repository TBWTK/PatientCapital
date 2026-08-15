---
title: Этапы проекта
type: roadmap
status: stable
updated: 2026-08-15
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

Допустимые статусы: `planned`, `active`, `blocked`, `done`.
