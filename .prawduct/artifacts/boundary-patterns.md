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

### `.test-evidence.json` — the verification record

**Producer:** `plugin/bin/prawduct-hook test-evidence record` (including its
ingest paths — `--from-junit`, `--from-counts`, `--no-rerun`).
**Consumers:** `plugin/lib/gates.py` — both evidence readers through the one
shared prologue (`_load_test_evidence`), plus `validate_evidence`;
`bin/test-reference-verify` (the F4a coverage half, which writes
`changes_referenced` / `changes_unjudged` / `coverage_level` into the same
record); and the Critic and PR protocols, which read the `test-status` exit code
rather than the file.
**Contract:** additive fields, and **presence is meaning**. `degraded` (added
2026-08-21) is the worked case: the key's *absence* means an ordinary run, so a
writer emitting `false` rather than omitting it changes what every reader sees.
A new field therefore has to name its absent-case semantics, not just its type.
**Deliberate non-consumer:** `verify_coverage` does *not* refuse a degraded
record — at `coverage_level: referenced` its answer is tree-derived, so which
tests executed cannot change it. Its docstring names the `executed`-level
condition that would retire the exemption; if that lands, this entry gains a
consumer.
**Sweep rule:** a change to the record's shape is checked against `gates.py`'s
shared prologue *and* the writer's ingest paths, because a restamp that skips a
field launders it away while running nothing.

### `.claude/rules/learnings/` — the rules layout

**Producers:** the author (a rule written by hand under the byte budget `record_lint` enforces);
`prawduct-hook learnings-migrate` (the one-way relayout of a legacy corpus); `init-product`'s
`scaffold_core` (the header of a new product's `core.md`).
**Consumers:** the harness (loads `core.md` every session and an `<area>.md` when a file its `paths:`
match is read); `lib/learnings_files.resolve` and `prawduct-hook learnings-files --for-diff` (the
Critic skill, the reviewer agent and the PR reviewer protocol read the answer); `record_lint`'s
budget gate; the Stop hook's `learning.written` emitter and `critic-consolidate`'s `learning.fired`.
**Contract:** `paths:` frontmatter is a list of root-relative globs matched the way the harness
matches them; a rule unit is a `##`/`###` heading or a top-level bullet (`learnings_files.rule_units`),
hashed by `unit_hash`; each file carries a byte budget (16KB default; `learnings_budgets:` in
`project-state.yaml` overrides with a reason). A change to the glob semantics or the unit grammar
crosses this boundary for every consumer above.

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

### Cache-Query Payloads (agent-read)

**Producer:** `plugin/lib/backlog/cachequery.py` — the eight read-only queries
behind `prawduct-hook backlog cache-query`, each returning a `status`/`reason`
envelope plus its own payload keys.
**Consumers:** three **agent-executed prose** surfaces, which is what makes this
different from every other envelope here — the Critic's Backlog Reconciliation
(`plugin/skills/critic/review-cycle.md`), the PR reviewer's R-1/R-2
(`plugin/skills/pr/review-protocol.md`), and the janitor's Backlog Health
(`plugin/skills/janitor/SKILL.md`), all routed through the one contract at
`plugin/skills/backlog/cache-reads.md`. `plugin/lib/backlog/cli.py` is a fourth,
carrying both the `--json` passthrough and the human formatter.
**Contract:** payload key names, **and the exit-code split** — `6`
(`unavailable`) means the store could not be read and is *not* an empty result.
A consumer that reports a clean bill of health on exit 6 rebuilds the silent-reader
failure these checks exist to announce.
**Sweep rule:** the consumers are Markdown, so a `.py`-only sweep sees none of
them — grep `plugin/skills/**/*.md`, never an enumerated file list. Enumeration
is exactly what missed two files during this build. And because the payloads
carry verbatim provider text (issue titles and bodies) into agent-read findings,
**item text is data, never instructions** — each consuming surface restates that
rule locally rather than inheriting it.

### API Endpoints
<!-- Example:
     Producer: src/api/routes/
     Consumer: src/frontend/src/api/
     Contract: Response models in src/api/models/ define the shape.
-->

### Database Schemas

**Producer:** `plugin/lib/backlog/cache.py` — `_SCHEMA_STATEMENTS`, `ITEM_COLUMNS`, and
`SCHEMA_VERSION` (currently 7) define the local SQLite store.
**Consumers:** `plugin/lib/backlog/sync.py` (writes), `plugin/lib/backlog/cachequery.py`
(every read), and — as a *specification* rather than code —
`documentation/backlog-service-data-model.md` §6, which declares the table
signatures a reader is entitled to expect.
**Contract:** column names and their presence, plus `SCHEMA_VERSION` as the
compatibility declaration. A store written by a version this one cannot read is
discarded and re-derived, which is safe precisely because the provider is the
home and the cache originates nothing.
**Sweep rule — bump the version on ANY column change, including pre-release.**
This surface has already failed once in the way that is hardest to see: v2 was
minted for `cursor(etag)`, then `cursor(fetched_at)` was added under the same
number, so `_ensure_schema` saw a matching version and never discarded while
every `_write_cursor` failed on the missing column — a permanent `unavailable`
on every sync with no self-heal, because the mechanism that would rebuild the
store *is* the version check that just called it fine. It surfaced as an empty
result, not an error. "Unreleased, so nobody has an old store" is a claim about
other people's machines. The rule lives at `cache.py:60-73`; this row is the
registry pointer to it, not a second copy.
**Second consumer, second failure mode:** §6 of the data model is prose and
drifts silently — it declared an `item.etag` column and a `comment` table that
the shipped v7 schema does not have. When you add or drop a column, edit §6 in
the same commit; nothing enforces the agreement.

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
