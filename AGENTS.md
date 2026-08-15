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

## PatientCapital MCP tools

- Read tools (`get_profile`, `list_assets`, `get_portfolio`, `get_recommendation`) may be used to
  answer questions about the local portfolio, but their numbers must be quoted without model-side
  recalculation or substitution.
- `propose_contribution` may run only for a user-supplied contribution. Always call the result a
  proposal, show its run id/algorithm version, and never imply that a trade happened.
- `record_transaction` may run only when the user explicitly confirms the actual BUY/SELL facts.
  Never convert recommendation lines into transactions automatically; send a fresh idempotency key
  with the actual quantity, clean unit price, total accrued interest when applicable, fee, currency,
  and timezone-aware occurrence time.
- Any tool error, stale/missing price, version conflict, or unknown state stays visible. Do not
  retry with guessed inputs. No PatientCapital tool may access shell, arbitrary SQL, broker APIs, or
  GigaChat credentials.

<!-- immune-project-engineering:start -->
## IMMUNE engineering contract

- Treat `docs/IMMUNE.md` as the authority for engineering principles and precedence.
- Work in this order: verified business intent → architecture → tests/evals → implementation.
- Before editing, read `docs/README.md`, `docs/STATE.md`, `docs/AUDIT.md`, `docs/IMMUNE.md`, and the directly relevant owner documents.
- Change concepts coherently across requirements, code, schemas/data, APIs/events, config, Docker/operations, docs, tests/evals, migrations, security, and observability.
- Expose unexpected and unknown states; do not silently guess or hide failures behind broad exception handling.
- Keep one owner per truth. Keep this file concise and link to durable docs instead of copying product rules.
- Treat Docker and Git as product contracts. Keep the actual default branch releasable and preserve unrelated user changes.
- Update agent instructions when repository commands, layout, invariants, ownership, or verification gates change.
<!-- immune-project-engineering:end -->
