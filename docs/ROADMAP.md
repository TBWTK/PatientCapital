---
title: Этапы проекта
type: roadmap
status: draft
updated: 2026-08-15
---

# Этапы проекта

| Этап | Проверяемый результат | Критерий завершения | Статус |
| --- | --- | --- | --- |
| Foundation | Требования, IMMUNE, аудит, архитектурные/data/security/quality contracts | Project-control check; placeholders и секреты отсутствуют | done |
| Domain | Чистый движок превращает snapshot и взнос в объяснимый дискретный план | Capability/property tests: бюджет, веса, комиссии, unknown | done |
| Persistence/API | Профиль, цели, активы, цены, операции и runs доступны через versioned API | Migration + repository + API integration tests | active |
| Product UI | Пополнение, аналитика, ручная покупка и профиль работают в web UI | Component tests + user-flow browser QA | planned |
| Agent surface | Codex использует узкие read/propose/record tools поверх того же core | Contract test доказывает parity UI/API/tool output | planned |
| GigaChat gate | Provider проверен на фиксированном corpus и либо допущен только к объяснению, либо отклонён | 100% schema/safety/math-grounding gates + отчёт | planned |
| Docker | Web, API и PostgreSQL поднимаются одним Compose-контуром | Clean-volume smoke + health + e2e contribution flow | planned |
| MVP handoff | Реализация, docs, tests и Git описывают одну правду | Full regression, project audit, clean releasable `main` | planned |

Допустимые статусы: `planned`, `active`, `blocked`, `done`.
