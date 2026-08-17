---
artifact: api-contract
version: 1
depends_on:
  - artifact: product-brief   # purpose lives in documentation/purpose.md
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
  lifecycle events (SessionStart, Stop, SubagentStop), passing event payloads as
  JSON on stdin and consuming the exit code and stdout.

**Consumers: both.** The **harness** (external) calls the hook subcommands via the repo's
`settings.json`; prawduct's own **skills** (internal) call the wider CLI. Note the asymmetry that
shapes every decision below: the *hook* contract is external and its shape is set by Claude Code;
the *rest of the CLI* is an **internal** surface consumed by skills that ship in the same plugin
version. **One exception as of 2026-08-02:** the two-command "Published surfaces" group below
(`print-install-reference` and `version`) is supported for third-party callers — see the ruling
under Direction. Every other subcommand remains internal, and calling one from outside prawduct is
unsupported rather than merely undocumented.

The canonical contract lives in: `hooks/hooks.json` (which events invoke which subcommands), the CLI
usage string and each subcommand's argv parsing, and the `--json` output shapes documented here and
in `docs/governance-telemetry.md`.

## Direction

<!-- Ratified norms (2026-07-17). The Versioning, Error Model, and Deprecation sections below hold
     the full descriptive detail; these are their binding form. See docs/norms.md. -->

- **Whole-surface semantic versioning on the plugin; the internal CLI subcommand surface carries no per-subcommand version; persisted data that outlives a plugin version (the evidence store) is independently schema-versioned with forward-incompatibility detection.** (recorded decision `api_versioning_approach`)
  Why: the plugin semver is the auto-update cache key and the one versioning handle a consumer sees; the CLI is an internal surface carried at the same version as its skill callers, so per-subcommand versioning would be ceremony without a consumer; the evidence store is the one contract that must survive across versions, so it is versioned independently and a schema-ahead fact blocks loudly. Revisit trigger: the first non-prawduct caller of `prawduct-hook` — add a stability tier + a `--version` handle before it ships.
  Status: steady-state (mirrored in `project-state.yaml` `design_decisions.api_versioning_approach` / `api_versioning_decided`).

  **Ruling 2026-08-02 — the revisit trigger fired, and the answer is a narrow tier, not a new versioning scheme.** `print-install-reference` (#533) ships *for* non-prawduct callers, so the trigger's "first non-prawduct caller" condition is met deliberately rather than by accident. The trigger asks for a stability tier and a `--version` handle before such a thing ships; both are satisfied without amending the decision:
    - **Stability tier — `stable`, covering exactly two subcommands: `print-install-reference` and `version`.** Both are read-only, both print one value on stdout and exit 0, keys are additive-only and never repurposed (already the third Direction norm), and removal of either would require a major. They are deliberately the *easiest possible* things to promise — each reads one value and prints it, so neither has behaviour that can regress independently of the value it publishes. `version` is listed because the trigger's second half makes it load-bearing: naming it as the version handle for an external consumer *is* binding a third party to it, and a handle a consumer may not rely on is not a handle. It was already relied on informally (the upstream bug-report path stamps it). **Everything else in the CLI stays internal/unstable** — a consumer that binds to another subcommand gets no promise, and the § Operations "Published surfaces" group is the enumeration.
    - **`--version` handle — the existing `prawduct-hook version`.** It prints the bare plugin semver, which is the one versioning handle a consumer sees (the decision's own rationale), so a caller can gate on plugin version today. A per-subcommand `--version` would be the ceremony this decision exists to avoid; adding one for two read-only commands would make the surface *less* uniform, not more.
  Why a ruling rather than an amendment: the recorded decision's content is unchanged — whole-surface semver, no per-subcommand version, evidence store versioned independently. What changed is that the surface now has **two** externally-supported members, which the decision anticipated and asked to be *stated* rather than avoided. Next revisit trigger: a **third** subcommand needing the stable tier, or any request to bind a third party to a `--json` shape — either means the tier needs a real definition rather than an enumerated exception. (The first draft of this ruling said "one subcommand" and set the trigger at "a second", which fired the moment `version` was correctly counted; the enumeration in § Operations is the authority, and this sentence tracks it.)

  Rulings: [[install-reference-is-published]] — the `api_versioning_approach` deferral said no external-consumer versioning is offered *because there is no supported external consumer*. Publishing `print-install-reference` makes that premise false without making the decision wrong. **Precedence: the deferral still governs every subcommand outside the § Operations "Published surfaces" group**; inside it, the stable tier binds. Category-level: **a deferral justified by the absence of a consumer is scoped to the surfaces that consumer does not touch, not retired wholesale when one appears.**
- **Exit codes are the contract, on a documented and consistent scheme; message severity is a stable prefix vocabulary; errors are attributed, never raised as stack traces across the boundary.** (recorded decision `api_error_model_approach`)
  Why: skills bind to exit codes, not parsed text, so a stable exit-code scheme + prefix vocabulary is what lets a narrow command be allowlisted instead of arbitrary `python3 -c`; a leaked stack trace across the boundary is an unattributed failure a caller cannot act on.
  Status: steady-state. Current state: applied inline per subcommand rather than centralized behind named constants — this artifact is the canonical statement, and new subcommands cite it rather than inventing a return convention.
- **Additive-first evolution: new subcommands and flags are added; existing flag names, exit-code meanings, and `--json` keys are never repurposed, and `--json` readers tolerate unknown keys.**
  Why: additive-first plus tolerant readers is what keeps new versions rare and keeps a skill shipped at version N from breaking when the CLI grows at N+1; deprecation is signalled (stderr notice, kept working, removal deferred to a major), never silent.
  Status: steady-state.
  Rulings: [[harness-only-removal-is-not-a-major]] — **owner exception, 2026-08-11 (v3.3.2): the
  major-deferral clause governs the *externally-callable* surface, not the harness-only one.**
  (Taken in session on a direct question about THIS clause — distinct from the 2026-07-12 #257
  ruling, which authorized the deletion itself and says nothing about the deprecation posture.) `build-index` and `user-prompt-submit`
  were removed outright in a patch. The clause's Why is protecting *callers* across versions, and
  these two had exactly one caller — `hooks.json`, which ships inside the same plugin at the same
  version and was updated in the same commit, so no caller could observe the gap. This artifact
  already classes them "called by the harness, not by humans" (§ Operations) and already records,
  as a dated decision, that there is **no supported external consumer** of the subcommand surface
  (§ Versioning). Honouring the letter would have spent a major version number on a change that
  breaks nothing for anyone, and would set the precedent that harness-internal cleanup is a major.
  **Scope of the exception:** removal without deprecation is in-bounds at any tier *only* for
  subcommands the harness alone invokes. The deprecate-then-remove path still governs everything a
  human or a skill can call — `stamp-merged` and `regen-views` remain inert-and-deferred exactly
  as before, which is the contrast that keeps this exception narrow rather than a loophole.
  Recorded rather than amended deliberately: editing the norm's own text to permit this change is
  the shape `docs/norms.md` warns against, and the departure is better carried as a ruling the next
  reader meets beside the rule.
  **Premise falsified 2026-08-11 (v3.3.3), same day — this is a fact, not a re-decision.** The
  sentence "no caller could observe the gap" is false, and the field disproved it within hours: every
  product repo running a pre-3.3.2 `hooks.json` against the 3.3.2 binary printed usage text and
  exited 1 at session start and on every prompt. The error is in treating "ships in the same plugin
  at the same version, updated in the same commit" as implying the caller updates atomically. It does
  not: the **harness pins a plugin version per project and updates those pins lazily**, then resolves
  the binary independently of the registration — so a hooks.json caller is the one caller that
  *routinely* observes a version gap, rather than the one that cannot. Same shape as
  [[install-reference-is-published]] above: a premise falsified without the decision necessarily
  becoming wrong.
  **What survives.** Untouched: that harness-only removal need not spend a major (the tier question
  the owner actually ruled on), and the narrowness that keeps `stamp-merged`/`regen-views` deferred.
  **Ruled 2026-08-11 (v3.3.4) — the exception requires an inert-retention window.** Put to the owner
  as the open question this paragraph previously carried, and answered: **unregistering a hook is
  free and immediate; deleting its subcommand waits until no supported install still registers it.**
  The two halves are separable and their costs are not alike — dropping the registration costs a
  line and takes effect at the consumer's next resolve, while dropping the dispatch branch breaks
  every pin that has not yet caught up. So the exception permits the first half at any tier and
  defers the second, which is precisely the shape the falsified atomic-update warrant used to stand
  in for: what made the deletion look safe was the belief that the caller updates with the binary,
  and the retention window is what actually delivers the safety that belief assumed.
  **What "no supported install" means in practice:** the window closes when no version a consumer
  could still be pinned to registers the command — in this repo's `directory:` marketplace that is
  bounded by how lazily pins update, so the honest floor is *at least one release after the
  registration is dropped*, and longer if any evidence says a pin is older. Cheap to hold: an inert
  subcommand is a `return 0` and a docstring.
  This ratifies the reading v3.3.3 restored both commands under — that release was the repair, and
  this is the ratification it explicitly said it lacked. The tier permission stands unchanged; the
  atomic-update warrant stays withdrawn, replaced rather than restored.
  Case law: [[deprecation-requires-an-inert-retention-window]]. The rule this makes fully written is
  what unblocks #644's conformance leg from `stage: requirements`.

## Operations

The CLI groups by responsibility. Every subcommand is read-only unless marked mutating.

- **Hook lifecycle** — `clear` (orientation always; session reset only at a boundary — `--brief-only` skips it, mutating),
  `stop` (session-end gate), `subagent-stop` (consolidate, mutating). Called
  by the harness, not by humans.
- **Critic data plane** — `critic-begin [--force]` (write dispatch manifest, mutating; `--force`
  overrides the exit-3 no-review-needed refusal — see § Error Model), `critic-consolidate`
  (merge partials → evidence fact, mutating), `critic-end`, `critic-discard` (archive-then-remove a
  stranded review's partials, mutating), `critic-restore <review-id>` (copy an archived review's
  manifest + partials back so it consolidates under its own id, mutating — `critic-discard`'s
  inverse), `evidence status|list`, `ledger-append`
  (single-writer, mutating), `review-stats`, `disposition` (append a finding's ACCEPT/FILE
  disposition fact, mutating), `render-dispositions` (derive the disposition census), plus the
  coverage/mode gate wrappers (`verify-coverage`, `check-cumulative-critic`, `infer-critic-mode`,
  `classify-diff-risk`, `verify-chunk-refs`), plus `verify-records` (the deterministic record
  checks, read-only and advisory — `critic-begin` runs the same pass into the manifest).
- **Test evidence** — `test-evidence record` (mutating), `test-status` (freshness), `validate-evidence`.
- **Session handoff** — `handoff preview`: renders the handoff the next session would receive,
  through the same function `clear` uses, without writing it or consuming the forward notes.
- **PR / release gates & views** — `check-pr-doc-only`, `check-change-log-entry`,
  `check-releasability [--release vX.Y.Z]`, `check-released vX.Y.Z [--json] [--allow-unverifiable]`,
  `resolve-base`,
  `regen-views` (deprecated, inert), `stamp-merged` (deprecated, inert).
- **Retired hook subcommands** — `build-index`, `user-prompt-submit` (deprecated, inert since
  v3.3.3). No longer registered in `hooks.json`; kept dispatchable because a pre-3.3.2 registration
  still invokes them and plugin version pins update per project. Silent on **both** streams, unlike
  the two inert commands above: a hook's stdout is injected into the model's context on exit 0, and
  their caller is a stale registration with no reader to address.
- **Build-plan lifecycle** — `archive-plan <path> [--state completed|superseded] [--date YYYY-MM-DD]
  [--release vX.Y.Z] [--superseded-by <text>] [--dry-run]` (mutating): stamps a plan with its
  terminal state and moves it into `archive/`. Writes on invocation rather than defaulting to a dry
  run — the `--apply` default belongs to the repo-wide lifecycle commands below, and this one acts on
  a single file the operator named; `--dry-run` is the preview. Refuses (exit 1, nothing written)
  rather than half-completing: a plan stamped but not moved still reads as live to every directory
  scan, and one moved but not stamped answers "is this current?" only to a reader who noticed the
  path. The archived copy is written first and the source removed last, and a failure to remove the
  source **rolls the copy back**, which is what makes "nothing written" true rather than aspirational.
  **The one disclosed exception:** if that rollback ALSO fails, the stamped copy survives and the
  reason says so by name — two failing filesystem operations cannot be undone by a third, and a
  refusal that quietly left an orphan would be the worse answer. The live plan is intact either way.
  Status checkboxes are never touched — but since v3.3.4 what they *said* is recorded, as an
  additive `unbuilt_at_archive:` frontmatter key naming the chunks a build plan had not finished
  (absence means clean; a document declaring a non-build-plan `artifact:` type is never stamped,
  having no roster to read). `--dry-run` previews it, so the preview and the write agree.
  `plan-backfill [--apply] [--json] [--date YYYY-MM-DD]` (mutating with `--apply`) is the
  repo-wide counterpart the sentence above points at: it archives every live plan whose `scope=`
  carries a `release=` tag in the change log, so it decides for itself which files to touch and
  therefore previews first. A product whose change log records no releases gets **nothing moved** —
  the set is proposed and the operator archives each with `archive-plan`. Checkbox state is neither
  a precondition nor corrected on the way in. `--json` adds `blocked[{path,scope,release,reason}]`:
  plans the change log records as shipped that the archival predicate refuses, split out so the
  preview cannot promise what the write declines. **Exit 1 on `--apply` when anything is `blocked`
  or `refused`** — an apply that could not move work the change log says shipped is not a clean run;
  a preview stays 0, having attempted nothing.
- **Derived-view convergence** — `lifecycle-repair [--apply] [--json]` (mutating with `--apply`):
  removes the retired `views_enabled` key and `scope_rollups` block, labels a derived
  `release-notes.md` as history, and deletes `## Status` notes instructing readers not to hand-edit
  checkboxes. `--json` keys: `applied`, `edits[{path,kind,reason,detail}]`, `unreadable[{path,
  reason}]`, `retired_flag{status,path,line}`, `plans_to_review[{path,chunks}]`, `outcome`.
  **`unreadable`, `retired_flag` and `plans_to_review` all have a live consumer** —
  `skills/doctor/SKILL.md` Health Checks #15 and #16 grade on them — so renaming any of them is a
  consumer break, not an internal edit. `unreadable` is the plans under `artifacts/` that could not
  be decoded as text: the walk that builds `edits` deliberately swallows them (one malformed file
  must not blind the scan), so a non-empty `unreadable` means the repair reports on a set it did not
  fully read. It was emitted before it was documented or graded, which is how a repo with an unread
  plan could be reported converged — the "path that cannot answer, reporting as one that answered"
  shape this command was written to end.
- **Operator verification** — `check-operator-verification`, `accept-operator-verification`,
  `verify-operator-verification` (both mutating).
- **Advisory** — `advisory list|show|dismiss|undismiss|resolve`.
- **Coverage & jurisdiction** — `coverage-status`, `coverage-scaffold` (mutating with `--apply`),
  `jurisdiction`, `cost-of-commit [--json] [<paths>...]` (does committing these paths — the
  working tree by default — buy a review round? Asks the gates' own `is_judgeable_path`, so it
  cannot disagree with the gate that charges afterwards; verdict token leads on stdout, degrades
  to `unknown` rather than a reassuring `free`).
- **Repo lifecycle** — `migrate-plugin`, `init-product`, `update-gitignore [--dry-run]`,
  `audit-learnings`, `learnings-obligation`, `norm-index-scaffold`, `lifecycle-repair`,
  `plan-backfill`, `repo-disable`, `bug-inbox` (dry-run-by-default where they mutate, with
  one stated exception). **`update-gitignore` is the exception: it repairs by default and
  previews only under `--dry-run`.** It is called as a repair step by `/prawduct:doctor`,
  which is why the default is the mutating one — but a reader who assumed the blanket
  claim above got the opposite of the truth, and for a while so did the command: it took
  no argv at all, so `--dry-run` could not reach it and the reconcile ran anyway. Both
  halves are fixed; the asymmetry that remains is deliberate and is stated here rather
  than left for the next reader to discover by running it.
- **Published surfaces** (read-only, and the only ones third parties may bind to) —
  `version` (bare plugin semver on stdout) and `print-install-reference` (the canonical
  `.claude/settings.json` install reference as JSON on stdout, sorted keys, exit 0; exit 1 with an
  attributed stderr message if the constant is unreadable, and **nothing on stdout** in that case,
  so a caller can never merge a partial reference). `print-install-reference` publishes
  `migrate_plugin.INSTALL_REFERENCE` verbatim — it is the readable form of the value
  `init-product` and `migrate-plugin` already merge into a repo, not a second copy of it.

Safe/idempotent notes: consolidation and fact-appends are **idempotent** (identity fixed at
dispatch); state-mutating lifecycle commands (`migrate-plugin`, `init-product`, `coverage-scaffold`,
`repo-disable`, `audit-learnings`, `learnings-obligation`, `norm-index-scaffold`,
`lifecycle-repair`, `plan-backfill`) default to a
**dry run** and require
`--apply` to write. The split is **scope, not danger**: a command acting on one file the operator
named writes on invocation (`archive-plan`), one that walks a tree and decides for itself which
files to touch previews first. That framing is descriptive — the binding rule is
`security-model.md` § Direction's operation-level approval.

## Inputs & Outputs

- **Inputs:** subcommand argv (each subcommand parses its own flags; unknown flags are rejected),
  and — for the hook subcommands — a JSON event payload on **stdin** (e.g. `stop` reads
  `background_tasks`; `subagent-stop` reads `cwd`/`agent_type`).
- **Human-readable output:** most subcommands print prefixed text (see Error Model). Skills consume
  their **exit codes**, not parsed text.
- **Machine-readable output (`--json`):** a defined subset emits structured JSON on stdout, each with
  a documented key set, consumed by a specific skill:
  - `coverage-status --json` / `coverage-scaffold --json` → doctor (`structural_recorded`,
    `discovery_expected`, `missing_artifacts[]`, `norms_unratified`, `active_layer`, `fix` /
    `applied`, `created[]`). `discovery_expected` is the layer-0 staging half, and it has **three**
    states, not two. **False** = no product work *this scan recognises* — it reads source by suffix
    allowlist (`#561`), so a repo in an unlisted language reads the same as an empty one; with
    `active_layer: null` that means "nothing owed yet", never "chain satisfied". **Null** on
    `discovery_expected` or `structural_recorded` = the staging check **could not run**, and in that
    state `missing_artifacts: []` means *nothing was looked at*, not *nothing is missing* — a
    consumer must not read it as a clean layer 1.
  - `norm-index-scaffold --json` → consumed by `/prawduct:doctor` Health Check #14 (`status` —
    one of `ok` / `leftover` / `absent` / `unreadable` / `unwritable`; plus `rows`, `path`, `detail`, `applied`,
    `removed`). Dry run exits 0 when it ran and 1 only when it could not; `--apply` exits 0 on a
    write or idempotent no-op and 1 on refusal.
  - `learnings-obligation --json` → **no skill consumer today** (`status` — one of `ok` / `missing` /
    `misplaced` / `absent` / `unreadable` — plus `path`, `marker`, `marker_lines[]`,
    `first_rule_line`, `detail`, `repairable`, `applied`, `insert_before_line`, `insert_text`).
    Health Check #13 relays the **human** form, which carries everything it needs. Listed here so
    the key set is documented, and named as unconsumed on purpose: every sibling in this list binds
    a real reader that keeps its keys honest, and asserting a binding that does not exist is how a
    maintainer sizes a key change against a consumer that would never have noticed.
  - `check-released --json` → **no skill consumer today** (`release`, `verdict` — one of
    `released` / `not-released` / `unverified` — and `checks[]`, each `{check, state, detail}` with
    `state` in `ok` / `failed` / `unverifiable`). The **human** form is what
    `.github/workflows/verify-release.yml` and both release runbooks read, and what carries the
    verdict; CI consumes the **exit code** (0/1/3), not this payload. Named as unconsumed on
    purpose, per the rule this list already applies to `learnings-obligation`: asserting a binding
    that does not exist is how a maintainer sizes a key change against a reader that would never
    have noticed.
  - `cost-of-commit --json` → **no skill consumer today** (`verdict` — one of `free` /
    `costs-a-round` / `unknown` — plus `source` (`working-tree` / `arguments`), `paths[]`,
    `judgeable[]`, `free[]`, and `round_price` (the `telemetry.round_price` dict: `status` of
    `priced` / `unavailable`, with `mode`/`median_seconds`/`reviews` or `reason`); `reason` appears
    at top level only on the degraded path). Named as unconsumed on purpose, per the rule this list
    already applies to `learnings-obligation` and `check-released`. The **human** form is what an
    agent reads — the verdict token leads stdout so a caller can branch on one word — and the exit
    code is deliberately NOT the contract here: 0 means "answered", including `unknown`, because
    the command gates nothing; 1 is reserved for bad arguments.
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
  - **Hook context channel:** the SessionStart digest emits the Claude Code
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

`check-released --json` emits `{release, verdict, checks[]{check, state, detail}}`, where
`verdict` is one of `released` | `not-released` | `unverified` and each `state` is
`ok` | `failed` | `unverifiable`. Registered here because the `--json` emitters are enumerated in
this section, and a payload documented only by its exit code is a shape a caller has to reverse-engineer.

**One gate carries a third outcome, added 2026-08-04.** `check-released` exits **3** for
*unverified*: nothing failed, but a check could not run — no `gh`, no `origin/main` in a
shallow checkout, or a declared `toml` version file on a pre-3.11 interpreter (no `tomllib`).
It is a distinct code rather than folded into 0 or 1 because both foldings are
wrong in the environment the command exists for. Folded into 1 it reports a broken release on a
fresh clone; folded into 0 it reports success on a tag-push CI job, which has no `origin/main` by
default and may have no token — precisely the case where an unpublished Release must turn the
build red. Its `--json` `verdict` therefore has three values: `released`, `not-released`,
`unverified`. `--allow-unverifiable` collapses 3 to 0 for an operator who wants the local subset.
CI binds to the exit code, so any non-zero is red without special-casing.

Fail-direction is deliberate and per-purpose:

- **Unevaluable *advisory* gate** (an optional lib path failed to import) → **fail-open, exit 0**: an
  ungradeable gate must never false-block (`classify-diff-risk`, `check-operator-verification`).
- **Unevaluable *writer*** (a state-mutating command whose lib failed to import) → **fail-closed,
  exit 1**: never report a false success. (`regen-views` used to be the worked example, escalating
  to **2** for validation/IO errors; it writes nothing at all now, so the rule's subjects are the
  operator-verification and coverage writers.)
- **Advisory report** (`verify-records`) → **exit 0 even with findings**, because it advises the
  builder and gates nothing; **exit 1 only when it could not run.** Findings are not a failure
  state, but an unrun check must never read as a clean one — inside a single run, the same rule
  appears per check as the `unchecked` list rather than a silently absent result.
- **Special sentinels** (documented, not general): `critic-begin` **2** = scope-widened;
  `critic-begin` **3** = no review needed (added 2026-08-06);
  `evidence status` **2** = schema-ahead records present (gates can't be trusted until update);
  `backlog verify-migration` **4** = completeness failure (a source item with no target issue).
  (`regen-views` **2** and **3** are RETIRED, not repurposed: the command is inert and exits 0
  unconditionally, so those two meanings were removed rather than given new ones. Retiring a
  meaning is what the additive-first norm permits; the thing it forbids is a new meaning wearing
  an old number.)

  **`critic-begin` 3 — no review needed.** The dispatch interval holds no judgeable file
  (`coverage_algebra.is_judgeable_path`) and no finding this mode could resolve, so the coverage gate
  already composes it as a **free edge** and a review would record a fact nothing needs. It is a
  distinct code for the same reason `check-released` 3 is: both foldings are wrong. Folded into
  **0** the caller proceeds to spawn reviewers against a manifest that was never written; folded into
  **1** a correct, expected outcome reads as a dispatch failure and invites a retry in another mode —
  which is the review round this exit exists to prevent. Message goes to **stdout** (agent-facing:
  it is a normal outcome the caller acts on, not a diagnostic), names the free files, and names the
  override. `--force` dispatches anyway. **No session state is written** — no dispatch manifest, no
  critic-active marker, and the partials directory is not swept — so a 3 needs no `critic-end`. It is
  not a silent no-op, though: since 2026-08-06 a 3 appends exactly one `guard-refusal` fact to the
  clone-shared evidence store, which is what makes the guard's own yield falsifiable. That fact is
  inert by construction (no gate reads a non-`review` kind), so it changes no verdict.

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

> **Trigger FIRED 2026-08-02 — see the ruling under § Direction.** `print-install-reference` ships
> for non-prawduct callers, so the paragraph above is no longer true as written: there is now
> exactly **two** supported external consumer surfaces. The deferral still holds for the rest of the
> CLI, which stays internal and unversioned. The tier is documented under § Direction and § Operations
> ("Published surfaces"), and the `--version` handle is the existing `prawduct-hook version` — the
> trigger asked for *a* handle, not a per-subcommand one, and the plugin semver is the handle this
> decision already names as the one a consumer sees.

## Deprecation & Compatibility   <!-- part of api_versioning_approach -->

Evolution rules we want to hold, so new versions stay rare:

- **Additive-first.** New subcommands and new flags are added; existing flag names, exit-code
  meanings, and `--json` keys are not repurposed. `--json` consumers should tolerate unknown keys.
- **Tolerant readers.** State/format readers self-heal or skip malformed input with attribution
  rather than hard-failing (evidence torn-tail repair; advisory corrupt-file quarantine).
- **Deprecation is signalled, not silent.** The established pattern: mark the subcommand deprecated
  in its help, print a deprecation notice to stderr on use, keep it working, and defer removal to a
  future **major** version. `stamp-merged` and `regen-views` are both in this state: each stays
  callable, prints its notice, does nothing, and exits 0.

  **DEPARTURE, recorded not amended — 2026-08-11 (v3.3.3), pending owner ratification.**
  `build-index` and `user-prompt-submit` join the inert tier printing **nothing on either stream**,
  which the clause above forbids as written. Recorded here rather than by softening the clause: the
  rule was stated for callers that can act on a notice, and rewriting it to fit the first two
  members that cannot is the amend-to-match-own-code shape `docs/norms.md` names — the more so on
  this branch, which declines to settle the adjacent retention-window scope for exactly that reason.
  **Why the departure:** their only caller is a pre-3.3.2 `hooks.json` registration, which has no
  reader who can drop the call, and a hook that exits 0 has its **stdout injected into the model's
  context** — so the notice would be read as instruction every turn rather than seen by anyone.
  Signalling is discharged by the help text and this artifact instead of by runtime output.
  **What the owner is being asked:** whether the norm should gain a *silent-when-the-caller-is-a-
  registration* clause (making this conformance), or whether these two stay a bounded exception. If
  neither, the remedy is to make them warn on stderr — never stdout. Full behavior in § Operations,
  "Deprecated and inert"; the deferral's reach and its falsified premise in § Direction under
  `[[harness-only-removal-is-not-a-major]]`.
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
  a consumer reading either surface reads the same keys. **Same keys is not enough — it must reach
  the same answer**, so it derives `scope` the way `critic-begin` does (branch name against declared
  plan scopes, pointer only as fallback) rather than resolving the plan its own way. A by-hand form
  that grades a different plan than the dispatch will is answering a different question in the shape
  of the real one. Its `counts` follow the same rule as the manifest's: an integer when a check ran,
  `null` when it produced no answer.
- **Internal / lifecycle surface** (called by the harness or by consolidation, not a public
  contract): `clear`, `stop`, `subagent-stop`, `critic-begin`, `critic-consolidate`.
- **Deprecated and inert** (callable, writes nothing, exits 0; removal deferred to a major). Four
  members in two sub-shapes, split by **who calls them** — which decides whether they announce
  themselves:

  - *Announcing* — `stamp-merged`, `regen-views`. Notice on stderr. Both lost their bodies when
    derived views were retired: `regen-views` had no views left to regenerate, and `stamp-merged`'s
    only output (`status=`) had no reader left. **Prawduct's own release runbook no longer calls
    either**, so the remaining reason to keep them callable is the one that cannot be audited from
    here: a consumer's copied operator script, where a non-zero exit would break a pipeline
    mid-release. The notice tells such a caller to drop the call.
  - *Silent* — `build-index`, `user-prompt-submit` (inert since v3.3.3). **No output on either
    stream.** Their caller is a pre-3.3.2 `hooks.json` registration, not a person: a notice has no
    reader who can act on it, and the next plugin update replaces the registration anyway. On
    stdout silence is a correctness requirement rather than a preference — a hook exiting 0 has its
    stdout **injected into the model's context** (SessionStart into the session, UserPromptSubmit
    ahead of every turn), so a deprecation notice printed the ordinary way would be read as
    instruction.

  The split is a **recorded departure pending owner ratification**, not a settled rule — see
  § Deprecation & Compatibility, where the norm it departs from still stands unamended and the
  proposed *silent-when-the-caller-is-a-registration* clause is the question put to the owner. All four are members of
  `_EPHEMERAL_SAFE_COMMANDS` — without it the fail-closed disposable-worktree guard treats an
  unlisted command as a write and exits 1, which would falsify "exits 0" exactly where a hook
  invokes it. Pinned in `tests/test_retired_hook_subcommands.py`.

  The `--check` flag's earlier state is worth keeping on the record: it was a *repurposing* rather
  than a clean deprecation — it performed a full regen where it documented "writes nothing" — and
  was recorded as a departure from the flag-repurposing clause above rather than as conformance.
  That departure is now closed by construction: nothing writes, so no flag can surprise anyone.

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
- **Least authority:** the CLI writes only what `architecture.md` § Direction's reconciled-files norm
  enumerates — that norm is the enumeration's one home and this contract does not restate its
  membership; it never writes framework files into a repo and makes no network calls.
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
