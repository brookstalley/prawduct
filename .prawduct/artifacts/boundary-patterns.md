# Boundary Patterns — prawduct

<!-- Contract surfaces where components interact. When changes cross these
     boundaries, the builder investigates consumer impact before completing
     the chunk. The Critic verifies investigation occurred. -->

## Contract Surfaces

<!-- For each boundary, describe: where producers live, where consumers live,
     and what the contract looks like (schema, types, message format). -->

> **This artifact is partially filled.** Only the surfaces below are recorded, so
> the Critic's Goal-5 contract-surface check speaks for those and is silent about
> the rest of the codebase — a silence that reads as "no surfaces crossed" and
> should not be trusted as one. **BND-1S4K** carries the rest, including the
> still-open question of *how* the remainder gets filled (evidence-driven as
> changes prove surfaces real, or one inventory pass) — the two below were added
> the first way, which records what happened, not a policy for what follows.
>
> A second reader beyond the Critic: `plugin/lib/risk.py` scrapes backticked paths
> from this file into `resolve_surfaces`. A declared `risk_surfaces:` key wins
> outright, and this repo declares one, so entries here do not move its review
> tier — but in a product that declares none, filling this file *raises* review
> depth. Weigh that before copying this pattern downstream.

### Generator/Tuple Yields Consumed Positionally

**Producer:** `plugin/lib/backlog/core.py` — `iter_alias_issues` yields
`(number, pfxs, label_names, status)`.
**Consumers:** `core.py` (`_restore_alias_labels`), `migrate.py` (`_AliasIndex._build`,
`verify_migration`), `tests/test_backlog_pagination.py`, **and
`.prawduct/operator-verification.md` (VRF-013 Fact 2 — a runnable snippet an
operator pastes into a REPL).**
**Contract:** positional arity. Widening is loud — a stale unpack raises
`ValueError` — but *where* it is loud differs by consumer, and that is the whole
risk: in Python call sites CI catches it; in a runbook snippet the exception lands
in the operator's hands mid-procedure, in this case on a pre-run gate for an
irreversible migration.
**Sweep rule:** grep the function name across `.md` as well as `.py`. A `.py`-only
sweep under-counted this surface by one site on 2026-07-31 and the miss was the
Critic's sole blocking finding. Prefer `for a, b, *_rest in …` in prose snippets so
the next widening cannot break them.

### Result Envelopes (backlog service ops)

**Producer:** `plugin/lib/backlog/` — every op returns the `ok`/`error` envelope
(`core.ok` / `core.error`); the migration ops carry op-specific `data` and
`error.details` keys.
**Consumers:** `plugin/lib/backlog/cli.py` (both the `--json` passthrough *and* the
human-mode formatters — two independent readers of one shape),
`documentation/backlog-service-api-contract.md`, and
`plugin/skills/backlog/migration-scrub.md`, whose steps instruct an operator to act
on named fields.
**Contract:** field names and their presence on **every** return path. The recurring
defect is enriching the success envelope and not the error ones — a resumable cut
carries progress the operator cannot reconstruct, so a field added to `data` must
be added to each `error.details` too, and human mode must be exercised by a test
(a `--json`-only test never runs the formatter).

### API Endpoints
<!-- Example:
     Producer: src/api/routes/
     Consumer: src/frontend/src/api/
     Contract: Response models in src/api/models/ define the shape.
-->

### Database Schemas
<!-- Example:
     Producer: src/models/ (ORM definitions)
     Consumer: src/services/ (queries), src/api/ (serialization)
     Contract: Model field names and types.
-->

### Inter-Process Communication
<!-- Example:
     Producer: src/worker/publisher.py
     Consumer: src/main/subscriber.py
     Contract: Message format defined in src/shared/messages.py
-->

### Frontend/Backend Type Contracts
<!-- Example:
     Producer: src/api/routes/ (response shapes)
     Consumer: src/frontend/src/types/ (TypeScript interfaces)
     Contract: Frontend types must match backend serialization exactly.
-->

### Configuration Interfaces
<!-- Example:
     Producer: config/defaults.yaml
     Consumer: All services read config at startup.
     Contract: Config schema in src/config/schema.py
-->

## Test Levels

<!-- Which test levels exist and when each should run. -->

| Level | Exists | When to Run | Location |
|-------|--------|-------------|----------|
| Unit | | Every change | |
| Integration | | Changes crossing boundaries | |
| Contract | | API or schema changes | |
| End-to-end | | Before release / major features | |
