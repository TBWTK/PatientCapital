<!-- project-control:start -->
## Project continuity

- Before planning or editing, read `docs/README.md`, `docs/STATE.md`, and documents directly relevant to the task.
- Reconstruct current state from repository files, Git diff/status, and fresh verification; do not rely on chat history alone.
- Define acceptance criteria and non-goals before implementation.
- Work in independently verifiable checkpoints and update `docs/STATE.md` after each verified checkpoint or before handoff.
- Keep `docs/STATE.md` compact: one active objective and one exact next step.
- Do not mark work complete without recorded test, eval, or inspection evidence.
- Do not convert unfinished acceptance criteria into technical debt.
- Create new project documents only when the project-control contract defines a trigger.
<!-- project-control:end -->

## Product authority

- Business requirements and acceptance evidence precede architecture and implementation.
- Read `docs/README.md`, `docs/STATE.md`, `docs/ARCHITECTURE.md`, `docs/QUALITY.md`, and the
  directly affected contracts before changing product code.
- Keep `main` releasable: every checkpoint must leave its in-scope verification green.
- Never commit `.env`, credentials, access tokens, broker identifiers, or private certificate keys.
- Never let an LLM invent or mutate an amount, asset, price, target, fee, lot size, or trade. Models
  may explain only validated output owned by the deterministic allocation engine.
- Unexpected or incomplete financial state must be explicit (`unknown`, validation error, or a
  blocked recommendation); do not silently default material inputs.
- The MVP never places broker orders and must not present itself as a licensed investment adviser.

## IMMUNE engineering principles

- **I — Intent before implementation.** Requirements outrank architecture; architecture outranks
  implementation. Durable intent must be recoverable from docs, tests, and contracts.
- **M — Mutations preserve coherence.** Change a concept across code, schema, API, docs, and tests;
  a file-only patch is incomplete when other projections become stale.
- **M — Meta over patch.** Fix the mechanism that produces a recurring class of errors; use a
  local patch for genuinely isolated mistakes.
- **U — Unexpected states fail loud.** Unknown is valid only when visible. Avoid broad exception
  handling that turns a failure into a plausible-looking financial result.
- **N — No duplicated authority, no indispensable parts.** One owner per truth and decision;
  consumers reference or derive it. Prefer replaceable components behind explicit contracts.
- **E — Every state is explainable.** Persist inputs, versions, evidence, decisions, and verification
  so every important state can be reconstructed.

## Delivery order

Business goals and constraints → architecture and invariants → capability/regression tests → code →
fresh verification → compact `docs/STATE.md` checkpoint.
