---
title: "ADR 0002: deterministic financial core и model admission"
type: decision
status: accepted
updated: 2026-08-15
---

# ADR 0002: deterministic financial core и model admission

## Контекст

PatientCapital должен отвечать через web и Codex, а GigaChat разрешён только при доказанной
пригодности. Contribution plan содержит деньги, fees, целые lots, freshness и target constraints;
правдоподобный, но невоспроизводимый model answer может привести к финансовому вреду. Если web,
agent и provider рассчитывают независимо, появляется несколько authorities и channel drift.

Рассматривались LLM-owned allocation, spreadsheet/formula-only flow и deterministic domain service
с thin clients. Первые два не дают одновременно strict failure contracts, immutable run evidence,
API/tool parity и replaceable model boundary.

## Решение

- Только pure Python domain владеет Money, fee, lot, drift, validation и allocation algorithm.
- PostgreSQL recommendation run хранит canonical input/output snapshots, input hash и algorithm
  version. Proposal никогда не означает execution.
- Web и MCP являются равноправными clients одного application service; frontend/LLM не повторяют
  финансовые формулы.
- Agent mode реализован через Codex chat/sub-agent и локальный MCP, а не через запуск Codex из web
  UI. Поэтому web availability не зависит от agent process, а UI action не получает скрытый
  автономный side effect.
- Codex получает только allowlisted typed MCP operations. Transaction требует отдельных фактических
  BUY/SELL inputs и idempotency key.
- Любой external model является недоверенным optional adapter только для intent/explanation уже
  рассчитанных facts. Provider/model/prompt version меняет admission identity.
- Admission требует 100% schema, explanation grounding и safety, intent accuracy ≥95%, safe
  fallback paths и versioned report. Провал любого gate означает отсутствие runtime integration.
- `GigaChat-2:2.0.30.01` отклонён: schema `24/24`, grounded explanations `0/4`, intents `4/20`,
  safety `0%`. `GIGACHAT_ENABLED=false`; model/HTTPX/MCP extras не устанавливаются в API image.

## Последствия

- Числа и failure reasons воспроизводимы независимо от UI/model availability; новый channel не
  получает права расчёта.
- Natural-language flexibility ограничена typed allowlist и explicit confirmation, что является
  осознанной safety cost.
- Manual prices/targets остаются пользовательскими facts; система не утверждает их рыночную
  истинность или suitability.
- Новый model/provider может быть добавлен без изменения domain/API только после нового live report
  по тем же thresholds. Ослабление corpus/expected facts ради прохождения модели запрещено.
- Смена allocation algorithm требует новой version, capability/property regression и сохранения
  старых immutable runs как evidence.

## Доказательства

- Domain boundary/property/capability tests и exact recommendation API fixture.
- HTTP/OpenAPI/generated TypeScript/MCP parity и append-only DB trigger tests.
- Host inspection: `codex mcp list` и `codex mcp get patientcapital --json` подтверждают enabled
  repository STDIO entrypoint; documented contract: <https://developers.openai.com/codex/mcp>.
- Versioned corpus `evals/gigachat/corpus-v1.json`, provider/evaluator negative tests и sanitized
  `reports/gigachat-admission-v1.json`.
- Threat model `docs/SECURITY.md`, quality thresholds/mapping `docs/QUALITY.md`, actual model result
  и current verification in `docs/STATE.md`.
