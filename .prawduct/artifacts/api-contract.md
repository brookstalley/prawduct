---
artifact: api-contract
version: 1
depends_on:
  - artifact: product-brief   # vision lives in README.md + CLAUDE.md
  - artifact: data-model
  - artifact: security-model
last_validated: null
---

# API Contract

<!-- Triggered by classification.structural.exposes_programmatic_interface (consumers: both).
     The surface is the `prawduct-hook` CLI plus the Claude Code hook lifecycle contracts and the
     `--json` machine outputs. Written toward the contract we want to hold; where the code applies a
     convention inline rather than as a documented whole, the text says so. -->

## Overview & Surface Type

Prawduct exposes **two related programmatic surfaces**, both local:

- **A CLI** — `prawduct-hook <subcommand>`: flags, stdin JSON, exit codes, and stdout/stderr format
  are the contract.
- **A platform↔app hook interface** — the Claude Code harness invokes a fixed set of subcommands on
  lifecycle events (SessionStart, UserPromptSubmit, Stop, SubagentStop), passing event payloads as
  JSON on stdin and consuming the exit code and stdout.

**Consumers: both.** The **harness** (external) calls the hook subcommands via the repo's
`settings.json`; prawduct's own **skills** (internal) call the wider CLI. Note the asymmetry that
shapes every decision below: the *hook* contract is external and its shape is set by Claude Code;
the *rest of the CLI* is an **internal** surface consumed by skills that ship in the same plugin
version. There is no supported third-party consumer of `prawduct-hook` today.

The canonical contract lives in: `hooks/hooks.json` (which events invoke which subcommands), the CLI
usage string and each subcommand's argv parsing, and the `--json` output shapes documented here and
in `docs/governance-telemetry.md`.

## Direction

<!-- Ratified norms (2026-07-17). The Versioning, Error Model, and Deprecation sections below hold
     the full descriptive detail; these are their binding form. See docs/norms.md. -->

- **Whole-surface semantic versioning on the plugin; the internal CLI subcommand surface carries no per-subcommand version; persisted data that outlives a plugin version (the evidence store) is independently schema-versioned with forward-incompatibility detection.** (recorded decision `api_versioning_approach`)
  Why: the plugin semver is the auto-update cache key and the one versioning handle a consumer sees; the CLI is an internal surface carried at the same version as its skill callers, so per-subcommand versioning would be ceremony without a consumer; the evidence store is the one contract that must survive across versions, so it is versioned independently and a schema-ahead fact blocks loudly. Revisit trigger: the first non-prawduct caller of `prawduct-hook` — add a stability tier + a `--version` handle before it ships.
  Status: steady-state (mirrored in `project-state.yaml` `design_decisions.api_versioning_approach` / `api_versioning_decided`).
- **Exit codes are the contract, on a documented and consistent scheme; message severity is a stable prefix vocabulary; errors are attributed, never raised as stack traces across the boundary.** (recorded decision `api_error_model_approach`)
  Why: skills bind to exit codes, not parsed text, so a stable exit-code scheme + prefix vocabulary is what lets a narrow command be allowlisted instead of arbitrary `python3 -c`; a leaked stack trace across the boundary is an unattributed failure a caller cannot act on.
  Status: steady-state. Current state: applied inline per subcommand rather than centralized behind named constants — this artifact is the canonical statement, and new subcommands cite it rather than inventing a return convention.
- **Additive-first evolution: new subcommands and flags are added; existing flag names, exit-code meanings, and `--json` keys are never repurposed, and `--json` readers tolerate unknown keys.**
  Why: additive-first plus tolerant readers is what keeps new versions rare and keeps a skill shipped at version N from breaking when the CLI grows at N+1; deprecation is signalled (stderr notice, kept working, removal deferred to a major), never silent.
  Status: steady-state.

## Operations

The CLI groups by responsibility. Every subcommand is read-only unless marked mutating.

- **Hook lifecycle** — `clear` (orientation always; session reset only at a boundary — `--brief-only` skips it, mutating), `build-index`,
  `user-prompt-submit`, `stop` (session-end gate), `subagent-stop` (consolidate, mutating). Called
  by the harness, not by humans.
- **Critic data plane** — `critic-begin` (write dispatch manifest, mutating), `critic-consolidate`
  (merge partials → evidence fact, mutating), `critic-end`, `evidence status|list`, `ledger-append`
  (single-writer, mutating), `review-stats`, `disposition` (append a finding's ACCEPT/FILE
  disposition fact, mutating), `render-dispositions` (derive the disposition census), plus the
  coverage/mode gate wrappers (`verify-coverage`, `check-cumulative-critic`, `infer-critic-mode`,
  `classify-diff-risk`, `verify-chunk-refs`), plus `verify-records` (the deterministic record
  checks, read-only and advisory — `critic-begin` runs the same pass into the manifest).
- **Test evidence** — `test-evidence record` (mutating), `test-status` (freshness), `validate-evidence`.
- **Session handoff** — `handoff preview`: renders the handoff the next session would receive,
  through the same function `clear` uses, without writing it or consuming the forward notes.
- **PR / release gates & views** — `check-pr-doc-only`, `check-change-log-entry`,
  `check-releasability [--release vX.Y.Z]`, `resolve-base`,
  `regen-views` (mutating), `stamp-merged` (deprecated, mutating).
- **Operator verification** — `check-operator-verification`, `accept-operator-verification`,
  `verify-operator-verification` (both mutating).
- **Advisory** — `advisory list|show|dismiss|undismiss|resolve`.
- **Coverage & jurisdiction** — `coverage-status`, `coverage-scaffold` (mutating with `--apply`),
  `jurisdiction`.
- **Repo lifecycle** — `migrate-plugin`, `init-product`, `update-gitignore`, `audit-learnings`,
  `repo-disable`, `bug-inbox` (all dry-run-by-default where they mutate).

Safe/idempotent notes: consolidation and fact-appends are **idempotent** (identity fixed at
dispatch); state-mutating lifecycle commands (`migrate-plugin`, `init-product`, `coverage-scaffold`,
`repo-disable`, `audit-learnings`) default to a **dry run** and require `--apply` to write.

## Inputs & Outputs

- **Inputs:** subcommand argv (each subcommand parses its own flags; unknown flags are rejected),
  and — for the hook subcommands — a JSON event payload on **stdin** (e.g. `stop` reads
  `background_tasks`; `subagent-stop` reads `cwd`/`agent_type`; `user-prompt-submit` reads
  `prompt`).
- **Human-readable output:** most subcommands print prefixed text (see Error Model). Skills consume
  their **exit codes**, not parsed text.
- **Machine-readable output (`--json`):** a defined subset emits structured JSON on stdout, each with
  a documented key set, consumed by a specific skill:
  - `coverage-status --json` / `coverage-scaffold --json` → doctor (`structural_recorded`,
    `missing_artifacts[]`, `norms_unratified`, `active_layer`, `fix` / `applied`, `created[]`).
  - `migrate-plugin --json` → migrate skill; `init-product --json` → onboard skill;
    `audit-learnings --json` → doctor; `repo-disable --json` → repo-disable skill.
  - `review-stats --json` → the cross-project telemetry aggregator, carrying a top-level
    `schema_version` (see Versioning).
  - `render-dispositions --json` → the disposition census, for a change-log entry, a PR body, or any
    consumer that would otherwise recount findings by hand. Top-level `schema_version` (the second
    report to carry one), `reviews[]` (each `review_id`, `ts`, `mode`, `scope`, `chunk`, `rows[]`),
    and `summary` (`findings`, `by_severity`, `by_state`, `undispositioned`, `owner_ruled`,
    `conflicts`). Each row: `fid`, `severity`, `goal`, `title`, `state`, `reason`, `backlog_id`,
    `owner_ruling`, `conflict`.
  - **Hook context channel:** SessionStart digest and UserPromptSubmit emit the Claude Code
    `{"hookSpecificOutput":{"hookEventName":…,"additionalContext":…}}` injection shape.

## Error Model   <!-- recorded decision → api_error_model_approach -->

**Recorded decision — `api_error_model_approach`: exit codes are the contract, on a documented,
consistent scheme; message severity is a stable prefix vocabulary; errors are attributed, never
raised as stack traces across the boundary.** The intended scheme:

| Channel | 0 | 1 | 2 |
|---|---|---|---|
| **Harness hook** (`stop`, `clear` refusal) | allow / clean | — | **block** |
| **CLI gate / query** (`test-status`, `verify-coverage`, `check-*`, `resolve-base`, `bug-inbox`) | satisfied / pass | not satisfied / fail | — |
| **CLI advisory report** (`verify-records`) | ran — findings, if any, are on stdout | **could not run** (unresolvable interval, unreadable state) | usage error |
| **State-mutating writer** (e.g. `disposition`) | written, or an idempotent no-op | **refused** — validation failed, nothing written | **usage error** |
| **Usage / arg error** (any subcommand) | — | — | **usage error** |

Fail-direction is deliberate and per-purpose:

- **Unevaluable *advisory* gate** (an optional lib path failed to import) → **fail-open, exit 0**: an
  ungradeable gate must never false-block (`classify-diff-risk`, `check-operator-verification`).
- **Unevaluable *writer*** (a state-mutating command whose lib failed to import) → **fail-closed,
  exit 1**: never report a false success. `regen-views` escalates to **2** for
  validation/IO errors (nothing written).
- **Advisory report** (`verify-records`) → **exit 0 even with findings**, because it advises the
  builder and gates nothing; **exit 1 only when it could not run.** Findings are not a failure
  state, but an unrun check must never read as a clean one — inside a single run, the same rule
  appears per check as the `unchecked` list rather than a silently absent result.
- **Special sentinels** (documented, not general): `critic-begin` **2** = scope-widened;
  `evidence status` **2** = schema-ahead records present (gates can't be trusted until update).

**Message vocabulary:** `CRITICAL:` / `WARNING:` / `NOTE:` / `PRAWDUCT:` / `BLOCKED —…`, with a
channel split — **stdout is agent-facing** (composed into model context), **stderr is
user/diagnostics** (warnings, blocker text, fail-soft attribution). No internal stack trace leaks to
the contract surface; a failure is caught, attributed, and turned into an exit code + prefixed note.

*Current state (honest):* this scheme is real and consistent in behavior, but it is currently
**applied inline per subcommand** rather than centralized behind named constants or a single spec —
this artifact is the intended canonical statement of it. The direction we want is that every new
subcommand cites this table rather than inventing a return convention.

## Versioning   <!-- recorded decision → api_versioning_approach -->

**Recorded decision — `api_versioning_approach`: whole-surface semantic versioning on the plugin
(the auto-update cache key); the CLI subcommand surface is an internal contract carried at the same
plugin version as its skill callers, so it takes no per-subcommand version; persisted data that
outlives a plugin version (the evidence store) is independently schema-versioned with
forward-incompatibility detection. Status: active.**

- **Plugin semver** (`version` in the manifest, mirrored in `VERSION`) is the versioning handle and
  the **auto-update cache key** — a release that doesn't bump it doesn't ship. Granularity is
  whole-surface.
- **Evidence-store schema version** is the one contract that must survive across plugin versions,
  because facts persist. It is integer-versioned with a supported-set; a fact written by a **newer**
  plugin than the reader is flagged **schema-ahead** and surfaced as a loud block (`evidence status`
  exit 2), never silently dropped — forward-incompatibility must be visible. This is the explicit
  cross-version compatibility mechanism.
- **New-gate attribution:** each gate carries a `since` version; a block from a gate new in the
  current release is labelled as such, so a newly-enforced rule is never a silent surprise.
- **Telemetry report** carries its own `schema_version`, bumped on breaking key changes, so a
  cross-project aggregator can trust the shape.

**Deferral with a revisit trigger:** no external-consumer versioning of the CLI subcommand surface
is offered, because there is no supported external consumer. **Revisit trigger:** the first time a
tool *other than prawduct's own skills* is meant to call `prawduct-hook`, add a documented stability
tier and a `--version` handle to the CLI before that consumer ships. This is a dated decision to
*not* version an internal surface, not an oversight.

## Deprecation & Compatibility   <!-- part of api_versioning_approach -->

Evolution rules we want to hold, so new versions stay rare:

- **Additive-first.** New subcommands and new flags are added; existing flag names, exit-code
  meanings, and `--json` keys are not repurposed. `--json` consumers should tolerate unknown keys.
- **Tolerant readers.** State/format readers self-heal or skip malformed input with attribution
  rather than hard-failing (evidence torn-tail repair; advisory corrupt-file quarantine).
- **Deprecation is signalled, not silent.** The established pattern: mark the subcommand deprecated
  in its help, print a deprecation notice to stderr on use, keep it working, and defer removal to a
  future **major** version (the current `stamp-merged` deprecation is the reference example).
- **Backward-compatibility commitment by tier:** *stable* surface changes only additively within a
  major; *internal* surface may change with its plugin version but must not silently break a
  skill shipped in the same version.

## Surface Inventory & Stability Tiers

- **Stable, allowlistable surface** (intended to be depended on, and scoped into skill
  `allowed-tools`): `evidence status|list`, `review-stats --json`, `render-dispositions`,
  `disposition`, and the query/gate subcommands skills bind to (`test-status`, `verify-coverage`,
  `check-*`, `resolve-base`, `coverage-status`, `advisory *`, `infer-critic-mode`). Several of these
  exist *specifically* to give skills a narrow, stable command to allowlist instead of arbitrary
  `python3 -c`. **`disposition` and `render-dispositions` are in this tier for a different reason
  than the rest:** no skill allowlists them, because their caller is the **main session** — the
  builder, whom `methodology/building.md` instructs to run them by name. Documented instruction to
  the builder is the dependency, so their flags, exit codes and `--json` keys are a contract exactly
  as a skill-bound query's are. `disposition` is the tier's one *writer*.
  **`verify-records` joins on a third footing:** its real caller is `critic-begin`, which computes
  the same result into the dispatch manifest, so the CLI exists as the *by-hand* form — a builder
  answering the record checks before dispatch rather than paying a review round to be told. Its
  `--json` shape is the manifest's `record_lint` block verbatim, which is what makes it a contract:
  a consumer reading either surface reads the same keys.
- **Internal / lifecycle surface** (called by the harness or by consolidation, not a public
  contract): `clear`, `stop`, `subagent-stop`, `critic-begin`, `critic-consolidate`, `build-index`.
- **Deprecated:** `stamp-merged` (removal deferred to a major).

*Current state (honest):* the stable/internal split above is the intended inventory and is reflected
in how skills allowlist commands, but there is **no formal stability-tier table in the code and no
`--version` flag** yet — filing those is the concrete next step toward this contract, gated on the
external-consumer trigger in Versioning.

## Conventions

- **Exit codes over parsed stdout** for gate/query results — the stable, allowlist-friendly signal.
- **`--json` for structured output**, human text otherwise; `--apply` to move a mutating lifecycle
  command from dry-run to write.
- **stdin JSON** for harness event payloads.
- **Argv is argv** — arguments passed as a list, never a shell string (see `security-model.md`);
  unknown flags rejected with a usage error (exit 2).
- **Timestamps** in facts/events are ISO-8601 UTC.

## Security

Per `security-model.md` — the API-boundary specifics:

- **No authentication/authorization** — single local actor; the surface is not network-reachable, so
  there is no BOLA/mass-assignment/rate-limit surface to defend.
- **Input validation at the boundary:** every subcommand parses defensively, rejects unknown flags,
  and treats stdin/state content as **data, not instructions**. Malformed input fails soft (skip +
  attribute), never executes.
- **Least authority:** the CLI writes only under the governed repo's `.prawduct/` (and the shared
  evidence store, `.gitignore`, `.claude/settings*.json` it must reconcile); it never writes
  framework files into a repo and makes no network calls.
- **No secret/PII exposure** in output — there is none in scope, and signals log operation + id, not
  payloads.

## Conditional Patterns

- **Decoupled async completion:** the Critic review is an async, multi-process operation whose
  completion is *not* a held-open call — reviewers write partials and consolidation runs from
  whichever of three triggers fires first (see `architecture.md` for which, and for the per-output
  limits of their idempotency). This is the "202 + status resource" analogue for a local CLI.
- **Idempotency, per output — not "exactly once" across the board:** the **review fact** collapses to
  one by `(kind, id)` first-wins dedupe under identity fixed at dispatch. The **ledger anchor** is
  weaker: `ledger.review_event_exists` closes the *replay* path (a re-materialized same-id manifest,
  or a crash between the fact append and `remove_partials`) but only *narrows* the *overlap* path,
  because the probe is read-then-write with no lock. So the multi-trigger race collapses to one
  result for the fact, and to one result on the replay path for the ledger — a concurrent overlap can
  still double-anchor. Observed live 2026-07-29 (one fact, two `review.critic` events a second
  apart); residual tracked at CRT-8L3Q, whose trigger is a second duplicated `review.fact_id`. Do not
  read this row as licence to close that item.
- **Correlation handle:** facts and ledger events carry the git tree/commit SHA + scope/chunk/actor,
  the local analogue of a request/trace id (ties to `observability-strategy.md`).
