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
  Ruling [[deprecation-requires-an-inert-retention-window]] (homed here since 2026-09-24): when you
  retire a harness-invoked subcommand, unregister it now and keep it INERT until no supported install
  still registers it, because plugin pins are per-project and lazy. The rule this makes fully written is
  what unblocks #644's conformance leg from `stage: requirements`.

  **Ruled 2026-08-26 (v3.4.1-dev) — a default that violates a higher norm is withdrawn outright, not
  retained inertly.** `audit-learnings`' sentinel runner hardcoded `sys.executable -m pytest`, an
  uninventoried instance of `architecture.md`'s **"never be specific to Python"** norm. Products now
  declare `sentinel_command:`, and the pytest fallback was **deleted rather than deprecated** —
  withdrawing working behaviour, which this clause normally defers to a major.
  Owner decision, stated directly on a direct question about this fix: *"NEVER python specific, never
  requiring a specific implementation of testing or anything else. We provide absolute business
  requirements, consuming repos decide the best way to implement for their project."*
  `[DECISION: withdraw the implicit pytest runner immediately rather than holding it through an
  inert-retention window | the clause's Why is protecting callers from breakage, and this withdrawal
  fails CLOSED — an ungraded sentinel withholds a retirement and destroys nothing, where the
  harness-only case it is modelled on broke every session at startup; and the retention window's own
  remedy is unavailable here, because what would be retained IS the violation | user can veto/override]`
  **Why this does not follow [[deprecation-requires-an-inert-retention-window]]**, which is live and
  governs the neighbouring case: that ruling's bargain is that inert retention is *cheap* — "an inert
  subcommand is a `return 0` and a docstring" — and costs nothing to hold. Here the thing to hold is
  a Python-specific default, so every day of the window is a day the architecture norm is still
  violated. The two norms cannot both be satisfied by waiting, and the retention window is the one
  whose cost changed. Signalled rather than silent, per this clause's own requirement: an ungraded
  sentinel prints a `notice:` to stderr naming the knob, and reports `ungraded` rather than the
  pre-fix loud-and-false `failed`.
  **Scope of the exception, kept narrow:** immediate withdrawal is in-bounds only where the retained
  behaviour would itself perpetuate a ratified norm violation AND its removal fails closed. A default
  that is merely *unfashionable*, or whose removal fails open, still takes the window.
  Category-level: **an inert-retention window is a courtesy the deprecating norm extends, not one it
  can extend on another norm's behalf** — when two norms collide the question is not which is senior,
  but which one's stated *warrant* has stopped holding.
  Ruling [[inert-retention-cannot-be-extended-across-norms]] (homed here since 2026-09-24): when the
  behaviour an inert-retention window would preserve IS a violation of another ratified norm,
  withdraw it outright, and the withdrawal must fail CLOSED. Qualifies, and does not retire,
  [[deprecation-requires-an-inert-retention-window]] — that ruling still governs every retirement
  whose retained behaviour is inert rather than itself non-conforming.

  Decision: 2026-10-25 (evidence-transport) — `[DECISION: one router and one exit convention for every `evidence` op (0 ok / 1 failure / 2 usage), which moves `evidence list`'s bad-flag exit and the unknown-op exit from 1 to 2 | the Critic's cumulative found two routers with two conventions on a surface this branch doubled in size, and a usage error on `list` was never documented as a meaning distinct from a failure — but it IS an existing exit code changed, so it is recorded here as the departure it is rather than as "nothing repurposed"; the consumer note names it | user can veto/override — reverting restores exit 1 for those two cases and keeps the router]`
## Operations

The CLI groups by responsibility. Every subcommand is read-only unless marked mutating.

- **Hook lifecycle** — `clear` (orientation always; session reset only at a boundary, which also ingests the branch's notes and prints `N evidence fact(s) ingested from refs/notes/prawduct` when N > 0 — `--brief-only` skips both, mutating),
  `stop` (session-end gate), `subagent-stop` (consolidate, mutating). Called
  by the harness, not by humans.
- **Critic data plane** — `critic-begin [--force] [--chunks a,b]` (write dispatch manifest, mutating;
  `--force` overrides both pre-dispatch refusals, exit-3 no-review-needed and exit-4 budget-exhausted
  — see § Error Model; `--chunks` names the build-plan chunks the review certifies — a comma list,
  repeatable, de-duplicated, normalised to the plan's spelling; `--chunk` stays as a one-element
  alias for one release; omitted, the declared set is the code-derived proposal; an id the plan
  does not declare is refused before the tree capture as `unknown-chunk` (exit 1); an empty id is a
  usage error (exit 1); a declared id outside the proposal is recorded with a `WARNING:` note),
  `critic-consolidate`
  (merge partials → evidence fact, mutating; reads the Critic's dispatch mark WITHOUT consuming it
  and writes the optional `dispatched_at` review-fact body key when the mark is this review's —
  the ledger append after it still consumes the mark), `critic-end`, `critic-discard` (archive-then-remove a
  stranded review's partials, mutating), `critic-restore <review-id>` (copy an archived review's
  manifest + partials back so it consolidates under its own id, mutating — `critic-discard`'s
  inverse), `evidence status|list` (`status` also prints `N transported fact(s) with no note on
  their commit` — what `evidence sync` re-attaches, for the branch's commits, before it pushes;
  every `evidence` op exits 0 ok, 1 a reported failure, 2 usage — an unknown op or a bad flag —
  and `status`, which takes no flags, keeps its 2 = schema-ahead sentinel below), `ledger-append`
  (single-writer, mutating — consumes the dispatch mark belonging to the APPENDING KIND, `review.critic`
  as well as `review.pr`, and writes the optional `dispatched_at` envelope key when one is present;
  `--trigger subagent-stop|explicit|session-end-backstop` is required for `review.critic` and
  refused for `review.pr`, and lands as the `trigger` envelope key (a required flag on a
  shipped verb, safe because `critic-consolidate` is the only `review.critic` appender and no
  skill or doc tells a human to append one);
  each kind owns its own marker, so an append can never reach another kind's — `data-model.md`
  § Direction), `pr-review-dispatch --begin` (write the PR reviewer's dispatch mark, mutating — a
  per-clone stopwatch, never an answer; the Critic's equivalent is written by `critic-begin` itself
  and has no separate verb), `pr-review-payload [--json] [<project dir>]`
  (assemble the PR reviewer's context in one pass; read-only, emits no verdict, fails soft per
  section with each degradation named), `review-stats`, `stats` (cost and yield per plugin version from the evidence store; read-only), `contribute [--json]` (preview the anonymous stats reports this clone would contribute, as their exact bytes and one digest; read-only, opens no socket) and `contribute --send [--approve sha256:<digest>]` (send them to the pinned collector, mutating the per-clone sent record; exit 2 when the product has not opted in, the digest does not match, or no collector is pinned, and 1 when a send fails), `disposition` (append a finding's ACCEPT/FILE/FIXED
  disposition fact, mutating — `--fixed <paths>` records a fix that bought no round and is refused
  on any judgeable path or any BLOCKING finding; the id argument takes a finding's `fid` **or** an
  observation's `oid`, the flags meaning exactly what they mean for a finding),
  `render-dispositions` (derive the disposition census), plus the
  coverage/mode gate wrappers (`verify-coverage`, `check-cumulative-critic`, `infer-critic-mode`,
  `classify-diff-risk`, `verify-chunk-refs`), plus `verify-records` (the deterministic record
  checks, read-only and advisory — `critic-begin` runs the same pass into the manifest).
- **Test evidence** — `test-evidence record` (mutating), `test-status` (freshness), `validate-evidence`.
  From a harness scratch worktree, `test-evidence record` is admitted through the ephemeral guard
  into the shared store only: it appends the `test-run` fact with `narrowed: true` and `ceiling`
  (the paths/args run) and writes no per-worktree `.test-evidence.json`; `--no-rerun` and
  `--from-counts` there exit 2, since neither records a fact. A narrowed fact is attribution only —
  the freshness fallback neither vouches nor denies by it. `test-status` prints its verdict line
  first, then one line per scratch worktree's newest narrowed run (at most 10); its exit code is
  unchanged.
- **Evidence transport** — `review`, `resolution`, `chunk-imported` and `chunk-retracted` facts travel between clones
  as their store lines in notes on `refs/notes/prawduct` (`data-model.md` § Evidence Store).
  `evidence ingest [--all] [--json]` (mutating) appends the note lines the store lacks, bounded to
  the branch's commits from the merge base, or every note with `--all`; it prints how many records
  it appended of how many it saw on how many commits, and a skipped class (malformed lines, kinds
  not transported) is counted in `reason`. Exit 0 when the ingest ran, appending nothing included;
  1 on an error; 2 usage. A data-plane write: refused (exit 1) from a scratch
  worktree, so a disposable tree never races the main checkout's ingest, and by a foreign binary; session start
  runs it bounded at a session boundary. `evidence sync [--no-push] [--json]` (mutating; network)
  fetches the remote's notes into the tracking ref `refs/notes/<remote>/prawduct`, merges them into
  `refs/notes/prawduct` with `cat_sort_uniq`, reconciles (re-attaches any transported fact in the
  bound whose note is missing), ingests, and pushes the ref unless `--no-push`, then moves the
  tracking ref to what it pushed; a remote with no notes yet is not an error. Note lines carry the
  store line with the actor's locator fields reduced: `actor.worktree` cut to its basename, or to
  `.claude/worktrees/<name>` for a harness scratch worktree (so the receiving clone classifies the
  fact as ephemeral too), never the path above it; `actor.session` dropped. Exit 0 ok; 1 a reported failure naming the failing `step`
  (`fetch`, `merge`, `reconcile`, `ingest`, `push`), git's stderr scrubbed of credentials and
  nothing retried; 2 usage.
  `/prawduct:pr create|update` runs it after the branch push, and a failure there is reported
  without blocking the PR; `evidence status` then shows it as `N note commit(s) not yet pushed`
  (the local ref against the push remote's tracking ref), or, when no tracking ref exists — a
  first push that failed or never ran — `N note commit(s) never pushed from this clone` (every
  commit on the local ref); with no local ref, no line.
  `evidence configure [--apply] [--json]` previews, and with `--apply`
  writes, the clone's two keys: the fetch refspec
  `+refs/notes/prawduct*:refs/notes/<remote>/prawduct*` in `remote.<remote>.fetch` — a pattern,
  because a configured exact refspec makes every plain `git fetch` fail while the remote has no
  notes (so a plain `git fetch` brings the remote's notes into the tracking ref, which
  `evidence ingest`, session start and `evidence status` read beside the local ref; `evidence sync`
  merges it before pushing) and
  `notes.rewriteRef=refs/notes/prawduct` (so amend and rebase carry them); a repo with no remote
  reports so and changes nothing. Exit 0 ok; 1 a failure; 2 usage. `/prawduct:doctor` offers it
  and `/prawduct:onboard` runs it.
- **Session handoff** — `handoff preview`: renders the handoff the next session would receive,
  through the same function `clear` uses, without writing it or consuming the forward notes.
- **Stranded work** — `worktrees [--json]` (read-only): every worktree with its inferred liveness
  (active / recent / idle / unknown / missing, and which signal decided it) and uncommitted-file
  count, plus the local branches checked out nowhere whose tip no remote-tracking ref reaches, with
  their commit counts. The session briefing renders the worktree half as counts that name nothing;
  each stranded branch is a `branch-landing:stranded-branch` advisory. Exit 0 whenever a report was
  produced — a partial one names its failed probes in it — and 2 on an unknown argument.
- **Git hygiene** — `git-tidy [--offline] [--json] [--apply <fingerprint>]` (mutating under
  `--apply`): the dry run lists the merged branches, merged remote branches, dead worktree entries
  and finished idle sibling worktrees whose removal loses nothing, each with the commit it is
  about, its proof, the exact git command, and a fingerprint naming the whole set. Online (the
  default) it first runs `git fetch --prune` and asks `gh` which branches open pull requests use;
  `--offline` skips both and marks remote removals unchecked. `--apply <fingerprint>` removes
  exactly that set, re-checking each proof first, and changes nothing when the set has changed.
  What counts as proof and what is never a candidate is `lib/git_hygiene.py`'s docstring. Dry
  run: exit 0 whenever a plan was produced, an empty one included, and 3 when git could not be
  read, which is never reported as "nothing to tidy". `--apply`: 0 when every approved removal
  happened, 1 when the set changed or any removal was kept, skipped or failed. Two targeted modes
  name their object: `--after-merge <branch> [--pr <n>]` is `/prawduct:pr` merge's cleanup step,
  and `--reap <worktree>` removes an integrated delegate's worktree and branch. Both exit 1 only
  when a step failed; a kept or skipped step is an expected outcome and gives its reason. 2 on bad
  usage, including two modes at once.
- **Stale plugin caches** — `stale-plugin-caches [--json]` (read-only): the prawduct plugin cache
  version directories, in every config profile on the machine, that no install record uses, with
  disk sizes and a delete command for each; it deletes nothing. What counts as in use, and why a
  profile with an unreadable record is ungraded, is `lib/plugin_caches.py`'s docstring.
  `/prawduct:doctor` Health Check #21 relays it. Exit 0 whenever a report was produced, ungraded
  profiles included, and 2 on an unknown argument. `--json` keys: `schema_version`,
  `stale_count`, `stale_bytes`, and `profiles[]`, each with `config_roots[]`, `cache`,
  `cache_readable`, `manifest` (`ok` | `missing` | `unreadable`), `ungraded_reason` (`null` when
  graded), `in_use[]`, `stale[]{path, bytes}`, `stale_bytes` and `ungraded[]`.
- **PR / release gates & views** — `check-pr-doc-only`, `check-change-log-entry`,
  `check-branch-pushed` (0/1/**3**),
  `check-releasability [--release vX.Y.Z]`, `check-released vX.Y.Z [--json] [--allow-unverifiable]`,
  `resolve-base`. (`regen-views` and `stamp-merged` were removed — § Direction, #303.)
- **Learnings layout (learnings v2)** — `learnings-files [--for-diff] [--json]` (read-only: the one
  resolver's answer — the rules files under `.claude/rules/learnings/`, and with `--for-diff` the
  core file plus every area file whose `paths:` intersect the diff; two `allowed-tools` grants bind
  it and the PR reviewer protocol instructs it, so it sits in the stable tier) and `learnings-migrate [--apply] [--map <file>] [--propose-map]
  [--json] [--local]` (mutating with `--apply`: the one-way relayout of a legacy `.prawduct/learnings.md` into
  the rules files, byte-accounted against the tree it writes; refuses on a dirty tree, an uncommitted or
  ignored corpus, or an ignored destination, because a commit is its undo — except under `--local`,
  for a repo that keeps its learnings out of git, whose undo is a byte-verified backup under
  `<git-common-dir>/prawduct/learnings-backup/`, reported as `backup_dir` in `--json`; exit 0 written,
  1 refused or could not run, 2 usage — the sibling repairs' scheme). **The contract change, in one
  place:** two verbs added; three retired to deprecated-inert (below) rather than removed, because the
  deprecation norm above governs every verb a human or a skill can call and the release is a minor;
  `ledger-append` gained two event kinds it refuses at the CLI; `review-stats --json` moved to
  `schema_version` 5 (a `learning` block added, then its `units_uncited` key, then the verify-pass `observations` counts, then a `by_stage` grouping; no key repurposed). Nothing a consumer allowlisted
  changed meaning.
  **learnings-one-line (2026-09-24)** adds `learnings-compact [--plan [--force]|--apply] [--local]
  [--json]` (mutating with `--apply`): `--plan` writes a worksheet under
  `<git-common-dir>/prawduct/learnings-compact/`, the agent records one decision per rule, the bare
  form validates it as a dry run, and `--apply` writes one-line rules under the caps and records a
  `learning.compacted` event per rewritten rule. It refuses an undecided row, an unapproved drop, a
  `moved-to` whose text is not at its destination, a corpus edited since `--plan`, an area file over
  its budget, and uncommitted rules files (the commit is the undo; `--local` keeps a verified backup
  instead). Exit 0 written or would write, 1 refused or could not run, 2 usage, as its siblings.
  `learnings_budgets.core.md` now needs an `owner_approved: YYYY-MM-DD` date to count, and
  `ledger-append` refuses the new `learning.compacted` kind like the other two. Additive: no flag,
  exit code or key changed meaning.
- **Learnings lifecycle (retired with learnings v2)** — `audit-learnings`, `learnings-obligation`,
  `check-learnings-pairing` (deprecated, inert): the corpus they graded — `.prawduct/learnings.md`
  and its detail/history pair — no longer exists; rules are harness-loaded from
  `.claude/rules/learnings/`. Kept dispatchable under the deprecation norm above because a doctor
  skill on an older per-project pin or a copied runbook can still call them: exit 0 for any
  flags, one `WARNING:` on stderr naming the replacement, nothing on stdout, nothing written.
  `ledger-append --event learning.*` is REFUSED (exit 1): those two kinds are emitted by the Stop
  hook and `critic-consolidate`, never by hand (`docs/governance-telemetry.md`).
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
  preview cannot promise what the write declines. It also carries
  `unevaluated[{path}]` — build plans that declare no frontmatter `scope:` and so were never
  candidates for any bucket, since the whole shipped test is a lookup on that key. Reported, and
  named on stdout under both arms of the release-tag fork, because the other three counts read as
  a description of `artifacts/` and without this one they are not. Diagnostic only: no exit code
  and no gate reads it. **Exit 1 on `--apply` when anything is `blocked`
  or `refused`** — an apply that could not move work the change log says shipped is not a clean run;
  a preview stays 0, having attempted nothing.
  `plan new [<scope>] [--branch B] [--base BASE] [--title T] [--kind K] [--working]`, `plan bind <path>
  --branch B` and `plan resolve [--json]` are the work-unit surface. `new` and `bind` are
  state-mutating writers of tracked files: exit 0 when written or already so, 1 refused
  (`refused: <code>: <detail>` — a taken scope, a second claim on the branch, the harness scratch
  branch, a scope one spelling from an existing one, or `no-scope-suggestion` when the scope is
  omitted and the branch name yields no slug), 2 usage. With the scope omitted, `new` derives it
  from the branch and says so on stdout. `plan resolve` is the read-only query
  every skill told to "resolve the plan the way governance does" runs; it is allowed inside a scratch
  worktree. Exit 0 for `bound` and `unbound` (both are ordinary answers), 1 for `broken` — the query
  returned, and the failing answer is that no binding can be decided until the plans it names are
  repaired; 3 is not used because two clean claimants read fine. Its `--json` carries the `Binding`
  keys and nothing else: `state` (`bound|unbound|broken`), `scope` (string or null — null when the
  bound plan declares no `scope:` or the binding is a legacy one), `plan_path` (repo-relative or
  null), `role` (`integration|working|null`), `reason` (one sentence or null), `chosen_by`
  (`binding|legacy-pointer|legacy-default|none`), `claimants` (repo-relative paths, empty unless
  bound or broken), `case` (the stable route code the resolver decided by — `claim`,
  `legacy-pointer`, `legacy-default`, `no-claim`, `pointer-dangling`, `scratch-worktree`,
  `detached-head`, `no-work-tree`, `two-claimants`, `unreadable-plan` — the one key a consumer
  branches on, never the `reason` prose) and `base` (the bound plan's declared base branch or
  null; base-branch resolution for the gates and the PR payload consults it first). Additive-first binds here as everywhere: `chosen_by` values are added, never
  repurposed, and readers of historical review facts still meet the retired `branch-name` and
  `not-resolved`.
  `plan status [<path>] [--json] [--probe-pr]` is the read-only rendering of chunk progress — the one view of
  `plan_status.chunk_states` (the sole walker of a plan's chunk states; no gate reads this view).
  `<path>` defaults to the bound plan. Exit 0 with the table; 1 when no plan resolves (an unbound
  checkout and no path given — one reason line); 2 on a path that is not a plan. Allowed inside a
  scratch worktree. `--json` carries `plan_path` (repo-relative), `scope`, `finished` (bool),
  `built_unavailable` (null when git answered, else the cause — the plan unreadable, a declared
  `base:` naming no ref, `git log` failing — and the table ends with `built: unavailable (<cause>)`)
  and `chunks`, a list in plan order of `{id, state (open|done|dropped), fact_id, date, imported,
  built, reason}`; `imported` marks a chunk completed by a `chunk-imported` fact or a legacy
  `## Status` tick read in memory, `built` is git-derived and certifies nothing (a commit naming the
  chunk in its subject or touching its deliverables, a change fragment still the `plan new` stub
  touching nothing; the short-plan Stop gate reads it only to arm its last-chunk block) and `reason` says why an entry that looked like an answer was not one (an
  unreadable `dropped:` line, a fact whose anchor is not in the branch's history). It also
  prints `lifecycle: <state>[ <released_in>] — <reason>`, and `--json` carries the same as
  `lifecycle: {state, reason, released_in, probed}` — `state` one of `in-progress`,
  `merged-unreleased`, `released`, `superseded`, `unknown`, observed from git, the review facts'
  anchors, the change record and the archive stamp (`plan_lifecycle.observe`, the one derivation;
  nothing is stored). `--probe-pr` lets an `unknown` answer ask `gh pr list` for a merged PR on the
  plan's branch (`probed: true`) — the one network call here, never made by a hook or the
  briefing. Keys are added, never repurposed; both `state` enums are closed sets that grow
  additively.
  `plan import-status <path> [--apply] [--remove-block] [--json]` (mutating with `--apply`) is the
  MG2 migration: for each chunk `chunk_states` reads as done-by-tick with no fact yet, it appends
  one `chunk-imported` fact, code-written from the box; `--remove-block` then rewrites the plan
  without its `## Status` section — opt-in, because the imported facts reach another clone only once
  their notes are pushed (`evidence sync`) and ingested there; until then that clone reads a plan
  with no block as every chunk open. Facts are written first and the block edited only after all succeed; every block
  refusal precedes any write. Exit 0 for a preview or a successful write; 1 `refused: <code>` for
  `archived-plan`, `no-scope`, `store-unreadable`, `status-block-ambiguous`,
  `status-block-undelimited`, `status-block-trailing-comment`, `fact-append-failed`,
  `plan-write-failed`; 2 usage or a path that is not a build plan. The preview is allowed inside a
  scratch worktree; `--apply` is a governance write and is refused there.
  `plan retract <chunk> --reason R [--fact ID] [--plan <path>] [--json]` (mutating) withdraws one
  fact's certification of one chunk by appending a `chunk-retracted` fact (`{scope, chunk,
  fact_id, reason, retracted_at}`), attached as a note on HEAD like an import. `--fact` omitted
  names the fact certifying the chunk now; `--plan` omitted, the bound plan. It can only reopen a
  chunk, so it needs no authority beyond the reason it records. Exit 0 written or already
  retracted (nothing written — the same command re-run included; `--json` `action` is `retracted` | `already-retracted`, beside
  `plan_path`, `scope`, `chunk`, `fact_id`, `retraction_id`, and `state` / `certified_by` — what the
  chunk reads after); 1 `refused: <code>` for `no-plan`, `archived-plan`, `store-unreadable`,
  `no-scope`, `unknown-chunk`, `box-import` (the chunk's `## Status` box is ticked, and certifies it
  after any withdrawal: untick it first), `not-certified`,
  `unknown-fact`, `other-scope`, `not-named`, `fact-append-failed`; 2 usage or a path that is not
  a build plan. Refused inside a scratch worktree.
  `plan check-claims [--json]` (read-only) asks, for every live plan declaring `branch:` or
  `working-branches:`, whether each named branch exists locally or on a remote. Three outcomes per
  claim, each reported distinctly and carried in `--json` as `outcome`: `exists` (nothing printed);
  `release-pending` (the branch is gone and the plan is observed merged and unreleased by
  `plan_lifecycle.observe` — the derivation `plan status` prints: a review anchored in the base's
  history, the integration branch merged, or a pending change record for the scope — the gitflow
  retention policy working, printed as `<plan>: <field> claims <branch>, which no longer exists;
  merged-unreleased (<reason>) — archive at the release`, never a defect); `missing` (gone, and the
  plan is in any other lifecycle state — so a `working-branches:` entry that is gone while the
  integration branch is still in progress is `missing`, whatever pending record the scope has),
  printed as `<plan>: <field> <branch> does not exist`, with one stderr line per plan that has a
  miss: `plan check-claims: <plan> is not release-pending (<state>: <reason>)`. A plan whose claim
  cannot be read is listed too, and is not a resolving claim. Exit 0 when nothing is `missing` and
  nothing is unreadable, 1 otherwise, 3 when git cannot list branches (nothing checked), 2 usage.
  `--json`: `{ok, claims: [{plan, field, branch, where, outcome}], unreadable: [{plan, reason}]}`,
  `where` being `local`, `remote` or null.
  `archive-change-log [--apply] [--json]` (mutating with `--apply`) keeps `.prawduct/change-log.md`
  bounded: past the repo's oversized threshold it moves entries verbatim into
  `.prawduct/change-log-archive/YYYY-MM.md` until the live log is at most half the threshold,
  never moving a release-pending entry in a product that versions. A state-mutating writer: exit 0
  when it ran (moved, would move, or nothing to do), **1 `refused:`** — nothing written — when a tag
  fails the release validator, when the release gate's own readers would see the resulting live log
  differently, when git tracks the live log but would ignore the archive, when the log is unreadable,
  or when a write fails (every file is restored); 2 on a usage error. `--json` keys:
  `applied`, `threshold_bytes`, `live_bytes_before`, `live_bytes_after`, `product_versions`, `kept`,
  `moved`, `pinned_bytes`, `buckets{YYYY-MM: count}`, `written[]`.
  `cut-change-log --release vX.Y.Z [--scope S]... [--apply]` (mutating with `--apply`) ships
  pending change fragments: the release plan's `ships` rows, or exactly the named scopes. It
  renders each into the archive's month bucket tagged `release=` and removes it; a `withheld`
  fragment stays. Where the repo declares `consumer_digest:` (`plugin/lib/consumer_digest.py`), it
  also renders the shipping consumer notes, under a generated heading and
  `.prawduct/release-headline.md`'s headline, into `.prawduct/releases/vX.Y.Z.md`, and inserts that
  section into the declared changelog above the newest release, changing no other byte. The dry
  run prints that section verbatim and lists every `none:` consumer note with its reason.
  Exit 0 when it ran or had nothing to cut; **1 `refused: <code>:`** with nothing written
  (`bad-version`, `no-change-log`, `invalid-pending-set`, `archive-ignored`, `unknown-scope`,
  `no-release-plan`, `bad-release-plan`, `unclassified-fragment`, `digest-declaration-invalid`,
  `digest-missing`, `digest-unreadable`, `marker-missing`, `release-in-changelog`, `no-headline`,
  `releases-ignored`, `release-already-cut`, `write-failed`), or `removal-failed` after the writes
  landed, which a re-run completes without duplicating because the release file marks the release
  cut; 2 on a usage error. No `--json`. *2026-10-26 (#733): `wrong-section` retired with the
  open-section model it guarded. This is a Repo-lifecycle command, not the stable tier, so the
  code set may change at a minor.*
  `migrate-change-log [--apply]` (mutating with `--apply`) converts the legacy log's
  release-pending entries into fragments and removes them from the log; shipped and untagged
  entries stay. Exit 0 when it ran or had nothing to convert; **1 `refused: <code>:`** with
  nothing written, one line per entry its author must decide about (the codes are
  `change_fragments.legacy_entries_as_fragments`' and any fragment validation code), or
  `fragment-exists`, `fragments-ignored`, `unreadable`, `write-failed`; 2 on a usage error.
  No `--json`.
- **Derived-view convergence** — `lifecycle-repair [--apply] [--json]` (mutating with `--apply`):
  removes the retired `views_enabled` key and `scope_rollups` block, labels a derived
  `release-notes.md` as history, and deletes `## Status` notes instructing readers not to hand-edit
  checkboxes. `--json` keys: `applied`, `edits[{path,kind,reason,detail}]`, `unreadable[{path,
  reason}]`, `unscoped[path]`, `retired_flag{status,path,line}`, `plans_to_review[{path,chunks}]`,
  `outcome`.
  **`unreadable`, `unscoped`, `retired_flag` and `plans_to_review` all have a live consumer** —
  `skills/doctor/SKILL.md` Health Checks #15 and #16 grade on them — so renaming any of them is a
  consumer break, not an internal edit. `unscoped` is the one that is graded **healthy**: build
  plans that decode fine and declare no frontmatter `scope:`, so the plan scan does not yield them
  and the repair never read them. Reported so a clean `edits` list is not read as "everything was
  checked", and deliberately outside both exit-code expressions — `--apply` cannot add a `scope:`
  key, so grading it would pin a repo at degraded with no route out. `unreadable` is the plans under `artifacts/` that could not
  be decoded as text: the walk that builds `edits` deliberately swallows them (one malformed file
  must not blind the scan), so a non-empty `unreadable` means the repair reports on a set it did not
  fully read. It was emitted before it was documented or graded, which is how a repo with an unread
  plan could be reported converged — the "path that cannot answer, reporting as one that answered"
  shape this command was written to end.
- **Operator verification** — `check-operator-verification`, `accept-operator-verification`,
  `verify-operator-verification` (both mutating). The check is three-way: 0 satisfied, 1 pending
  entries, **3** the queue could not be parsed (see the third-outcome rule under § Error Model).
  `accept-operator-verification` refuses on that same unparsed queue rather than recording a bypass
  that covers no entries — an override reached by a different door must not inherit the defect the
  check just closed.
- **Plugin activation** — `check-plugin-active [--path P] [--context onboard|doctor] [--json]`
  (read-only). Answers whether the harness will actually LOAD the plugin for a repo, which
  project-scope enablement in `.claude/settings.json` does not settle on its own. **Three-way by
  construction**: `active` exit 0, `inactive` exit 1, `unknown` exit **3** — the third-outcome
  shape below, for the reason given there. `--context` selects the WORDING, not the verdict: the
  same `inactive` means "this repo loads nothing" to an onboarding session and "the manifest
  record does not name this path" to a doctor run, which by construction executes inside a
  session where the plugin did load. `--json` carries `status` for a caller that must branch.
- **Learnings pairing** — `check-learnings-pairing [--json]` (**deprecated, inert** since the v2
  cutover). Exits **0** always and writes nothing; `--json` yields empty stdout. It graded
  `.prawduct/learnings.md` against `learnings-detail.md`, and that corpus no longer exists — rules
  are `.claude/rules/` files the harness loads by path match. **Its former contract (0 clean, 1 a
  duplicate active heading, 3 the pair unreadable) is RETIRED, not merely unused**: a stub that
  returns 0 cannot raise 1 or 3, so a caller still branching on them takes the clean arm forever.
  The notice on stderr names where rules live now. `audit-learnings` and `learnings-obligation`
  are inert on the same terms.
- **Advisory** — `advisory list|show|dismiss|undismiss|resolve`.
- **Backlog service** — `backlog <op>`: a subcommand *group*, not a single command. The op set is
  `_ALL_OPS` in `lib/backlog/cli.py` — the same tuple the CLI builds its unknown-op message from, so
  the enumeration cannot drift from what dispatches — and `_WRITE_OPS` inside it is the
  provider-mutating half; the rest read, some writing only the local cache (`sync`).
  **This artifact deliberately restates none of the ops, the `--json` envelope, or the error
  vocabulary.** `documentation/backlog-service-api-contract.md` is the operational contract for all
  three (§ 2 the operations, § 3 inputs and outputs, § 4 the error model), and
  `skills/backlog/adapter-mode.md` is the form an agent binds to. A copy here would be a second
  thing to drift. What this entry owes instead is the **promise**, which neither of those documents
  can settle for the product: a surface described in detail elsewhere and unnamed here still leaves
  the reader who asks "what does prawduct expose, and under what promise?" a confidently incomplete
  answer, and that silence is the drift nobody can see.
  **The promise is the one this artifact already makes for the rest of the CLI.** `backlog` is
  internal/unstable (§ Surface Inventory), carried at the plugin version like its skill callers, and
  outside the two-member stable tier § Direction's 2026-08-02 ruling enumerates. Adopter agents do
  call it — a real dependency, and still not a promise: a request to bind a third party to its
  `--json` envelope is exactly the second of the two conditions that ruling names as its next
  revisit trigger, and it has not been made. Where the feature-local contract's own stability
  language is more generous than that, **this artifact governs the tier and that document governs
  the operational detail.** Exit classes: § Error Model.
- **Coverage & jurisdiction** — `coverage-status`, `coverage-scaffold` (mutating with `--apply`),
  `jurisdiction`, `cost-of-commit [--json] [<paths>...]` (does committing these paths — the
  working tree by default — buy a review round? Asks the gates' own `is_judgeable_path`, so it
  cannot disagree with the gate that charges afterwards; with no path arguments, judgeable paths
  price `free` when the gates' coverage composition already covers the working tree
  (`gates.commit_coverage`); verdict token leads on stdout, degrades to `unknown` rather than a
  reassuring `free`).
- **Repo lifecycle** — `migrate-plugin`, `init-product`, `update-gitignore [--dry-run]`,
  `audit-learnings`, `learnings-obligation`, `norm-index-scaffold`, `reanchor`,
  `lifecycle-repair`, `plan-backfill`, `archive-change-log`, `cut-change-log`, `migrate-change-log`, `repo-disable` (dry-run-by-default where they mutate, with
  one stated exception). **`update-gitignore` is the exception: it repairs by default and
  previews only under `--dry-run`.** It is called as a repair step by `/prawduct:doctor`,
  which is why the default is the mutating one — but a reader who assumed the blanket
  claim above got the opposite of the truth, and for a while so did the command: it took
  no argv at all, so `--dry-run` could not reach it and the reconcile ran anyway. Both
  halves are fixed; the asymmetry that remains is deliberate and is stated here rather
  than left for the next reader to discover by running it.

**Argument shape is checked before dispatch, for every subcommand.** An argument a
subcommand has no parameter to receive is refused with exit 2 and nothing runs — the
usage-error convention already used by `_reject_unknown_args`. The check sits ahead of
the dispatch chain (and ahead of project-dir resolution) rather than inside each command,
because a per-command guard misses whichever command nobody thought of; that is the same
placement `_check_binary_skew` and `_check_ephemeral_worktree` already use. One carve-out
is deliberate and is the only one:

- **`stop` / `subagent-stop` name the stray argument on stderr and still run.** These are
  the harness's own calls, never typed. A usage error on a Stop hook does not protect a
  caller — it blocks the session and feeds the refusal back as a turn, which is a worse
  failure than the silence it would close.
  (A second, `stamp-merged` passing any argument silently as an inert command, went with
  the command in #303.)

**Commands that DO receive `argv` refuse their own unknown tokens** — the dispatcher cannot
speak for them, because they can see their arguments and it cannot know their vocabulary.
Flag-only ones (`--json` / `--apply` style, detected with `"--flag" in argv`) call
`_reject_unknown_args`, because that idiom reads an unrecognised token as *absent*.

That bucket is the part worth reading carefully, because it was filled twice by
enumeration and was wrong both times. `update-gitignore` was fixed and `coverage-scaffold`
was missed — it mutates under `--apply`, and `--apply --dry-run` wrote the stub artifacts
while the caller believed they had asked for a preview. Those two were fixed and
`migrate-plugin` and `init-product` were missed: the cutover and the scaffolder, the two
most destructive commands on the surface. A list is something the next command is not on,
so the coverage is now asserted structurally —
`tests/test_hook_argument_shape.py::test_every_argv_taking_command_refuses_what_it_cannot_read`
derives the argv-taking set from `_dispatch`'s own source and fails for any member with
neither a guard nor a recorded reason.

**Nine of those recorded reasons are honest gaps, not clearances.** `backlog`,
`test-evidence`, `advisory`, `ledger-append`, `critic-begin`, `critic-restore`, `handoff`,
`disposition` and `archive-plan` each error on a bare invocation, so the bare-vs-unknown
probe cannot distinguish a refusal from that pre-existing error, and they were not
individually audited. They are named in the test rather than folded into a confident-looking
allowlist; `#667` carries the audit.
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
`reanchor`, `lifecycle-repair`, `plan-backfill`, `archive-change-log`, `cut-change-log`,
`migrate-change-log`) default to a
**dry run** and require
`--apply` to write. The split is **scope, not danger**: a command acting on one file the operator
named writes on invocation (`archive-plan`), one that walks a tree and decides for itself which
files to touch previews first. That framing is descriptive — the binding rule is
`security-model.md` § Direction's operation-level approval.

## Inputs & Outputs

- **Inputs:** subcommand argv (each subcommand parses its own flags; unknown flags are rejected
  except where § Operations records otherwise — five deliberate non-refusers and nine unaudited),
  and — for the hook subcommands — a JSON event payload on **stdin** (e.g. `stop` reads
  `background_tasks` and `last_assistant_message`, the second only for the turn's closing block — its
  clear verdict and disposition;
  `subagent-stop` reads `cwd`/`agent_type`). Every payload key, host environment variable,
  structured hook response and the Stop's blocking exit is read or written in one module,
  `plugin/lib/host.py`, chosen by `PRAWDUCT_HOST` (unset means `claude`, the only host
  implemented). Plain text the hooks print in place (the briefing, the banner, the Stop's notes
  ahead of its block) is not yet routed there. An unknown value blocks
  `stop` (exit 2, naming the variable) and makes the SessionStart and SubagentStop hooks note it
  on stderr and do nothing.
- **Human-readable output:** most subcommands print prefixed text (see Error Model). Skills consume
  their **exit codes**, not parsed text.
- **Machine-readable output (`--json`):** a defined subset emits structured JSON on stdout, each with
  a documented key set, consumed by a specific skill:
  - `coverage-status --json` → doctor, **partly**: Health Check #11 runs the bare command and
    relays its human form, reaching for `--json` only to distinguish `discovery_expected` false from
    null. **`coverage-scaffold --json` has no consumer** — #11 runs it bare and with `--apply`.
    Keys (`structural_recorded`,
    `discovery_expected`, `missing_artifacts[]`, `norms_unratified`, `active_layer`, `fix` /
    `applied`, `created[]`, and `risk_surfaces: {status, fix}` — outside the chain; `status` is
    `declared` / `undeclared` / `unparseable` / `not-owed`, or null when the check could not run
    (`lib/risk.risk_surfaces_status`); Health Check #20 consumes it. Since 2026-09-26 nothing asks
    for the key, so `fix` is set for `unparseable` only — `undeclared` stopped being a finding; the
    key and its status values are unchanged, per the additive-first norm). `discovery_expected` is the layer-0 staging half, and it has **three**
    states, not two. **False** = no product work *this scan recognises* — it reads source by suffix
    allowlist (`#561`), so a repo in an unlisted language reads the same as an empty one; with
    `active_layer: null` that means "nothing owed yet", never "chain satisfied". **Null** on
    `discovery_expected` or `structural_recorded` = the staging check **could not run**, and in that
    state `missing_artifacts: []` means *nothing was looked at*, not *nothing is missing* — a
    consumer must not read it as a clean layer 1.
  - `norm-index-scaffold --json` → **no JSON consumer today** — Health Check #14 runs the command
    and relays its human form, the same as #4. The shape is published for programmatic consumers:
    `status` — one of `ok` / `leftover` / `absent` / `unreadable` / `unwritable` — plus `rows`,
    `path`, `detail`, `applied`, `removed`. Dry run exits 0 when it ran and 1 only when it could not; `--apply` exits 0 on a
    write or idempotent no-op and 1 on refusal.
  - `reanchor --json` → **no JSON consumer today.** `/prawduct:doctor` Health Check #4 runs the
    command and relays its human form; the `--json` shape is published for programmatic consumers
    and carries `status` — one of `ok` / `stale` / `stale-modified` / `legacy-layout` /
    `import-missing` / `legacy-block` / `absent` / `unreadable` / `unwritable` — plus `path`,
    `repairable`, `detail`, `applied`, `replacement` (the anchor text), and `writes` (each file
    the repair would write: `path`, `how`, and the exact `text`).
    **A successful `--apply` returns `ok`**, not the status it repaired: a graded status describes
    the state on the way IN, and a consumer reading it back after a write would report the condition
    that was just fixed.
    **HC#4 is not the JSON consumer** — it parses nothing, and a contract asserting a consumer it
    does not have is how a `--json` shape drifts from the command that emits it.
    Dry run exits 0 when it ran and 1 only when it could not; `--apply`
    exits 0 on a write or idempotent no-op and 1 on refusal. **`stale` and `stale-modified` are
    separate statuses on purpose** and a consumer must not collapse them: the first is prawduct's
    to repair, the second is an anchor the owner has edited, which this command reports and
    declines to overwrite.
  - `stale-plugin-caches --json` → **no JSON consumer today.** `/prawduct:doctor` Health Check #21
    runs the command and relays its human form. The key set is listed once, in the § Operations
    "Stale plugin caches" entry. A profile with a non-null `ungraded_reason` has nothing in it
    graded, so its empty `stale[]` means *not looked at*, not *nothing unused*.
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
    `judgeable[]`, `free[]`, `covered_by[]` (review ids whose coverage made a judgeable working
    tree `free`; empty otherwise), and `round_price` (the `telemetry.round_price` dict: `status` of
    `priced` / `unavailable`, with `mode`/`median_seconds`/`reviews`/`basis` — `measured` or `self-reported` — or `reason`); `reason` appears
    at top level only on the degraded path). Named as unconsumed on purpose, per the rule this list
    already applies to `learnings-obligation` and `check-released`. The **human** form is what an
    agent reads — the verdict token leads stdout so a caller can branch on one word — and the exit
    code is deliberately NOT the contract here: 0 means "answered", including `unknown`, because
    the command gates nothing; 1 is reserved for bad arguments.
  - `migrate-plugin --json` → migrate skill (a `refused` reason — the anchor cannot be placed —
    exits 1 having touched nothing); `init-product --json` → onboard skill;
    `audit-learnings --json` → doctor. **`repo-disable --json` has no consumer** — the
    repo-disable skill documents and runs only the bare form. A row naming a consumer that parses
    nothing is inert, which is exactly why it does not fail — so this list is checked by re-running
    its own premise against each row, not by reading it.
  - `worktrees --json` → **no skill consumer today**: top-level `schema_version`, `worktrees[]`
    (`path`, `branch` — null when detached — `is_current`, `ephemeral`, `state`, `last_activity`
    as `{source, at}` or null, `dirty` — null when git could not be asked), `branches[]` (`name`,
    `last_commit`, `unique_commits` — null when the count failed), `worktrees_checked` (false when
    git could not list worktrees: every count is then "not checked", never "none"), `has_remotes`,
    `problems[]`. The briefing and the advisory read the report in-process, not this payload.
    Named as unconsumed on purpose, like `cost-of-commit`; the key set is pinned by a test.
  - `git-tidy --json` → **no skill consumer today**: top-level `schema_version`, `fingerprint`,
    `fully_checked` (false when any part went unchecked, so an empty `actions[]` with it false means
    *not looked at*, never *nothing to tidy*), `remote`, `online`, `long_lived[]`, `actions[]`
    (`kind` — one of `remove-worktree` / `prune-worktree` / `delete-branch` /
    `delete-remote-branch` — `target`, `sha`, `proof`, `command[]`, `unchecked`, null or the reason
    the action awaits a network check, and `proven_by`, the full ref whose reach is the proof or
    `pull-request:<n>`), `notes[]`, `problems[]`. With `--apply` the keys are `schema_version`,
    `approved`, `fingerprint`, `applied` (false when the set changed and nothing was touched),
    `outcomes[]` (`kind`, `target`, `result` — one of `removed` / `kept` / `skipped` / `failed` —
    and `detail`), and `problems[]`. With `--after-merge` or `--reap` the keys are `schema_version`
    and `steps[]` (`name`, `result` — one of `removed` / `done` / `kept` / `skipped` / `failed` —
    and `detail`). Named as unconsumed on purpose, like `worktrees`.
  - `review-stats --json` → the cross-project telemetry aggregator, carrying a top-level
    `schema_version` (see Versioning).
  - `stats --json` → **no skill consumer today**. `/prawduct:janitor` reads the human form, and the
    opt-in contribution payload a later wave builds is derived from this shape: top-level `schema_version`, `project`, `generated_at`, `window` (`since`, `until`),
    `schema_ahead`, and `by_version` keyed by plugin `major.minor`. The per-version keys are defined
    in `docs/governance-telemetry.md` § `prawduct-hook stats`, their one home.
  - `aggregate-stats --json` → **no skill consumer today**: top-level `schema_version`,
    `generated_at`, `sources` (`local`, `local_skipped`, `contributed` — `bundles`, `lines`,
    `refused`, `schema_ahead`) and `by_version`, keyed by plugin `major.minor` like `stats`.
  - `change-record --json` → **no skill consumer today**: an object keyed by the scope argument,
    each value `null` when the scope has no record, else `{source, path, closes[]}`.
  - `render-dispositions --json` → the disposition census, for a change-log entry, a PR body, or any
    consumer that would otherwise recount findings by hand. Top-level `schema_version` (the second
    report to carry one), `reviews[]` (each `review_id`, `ts`, `mode`, `scope`, `chunk`, `rows[]`,
    `observations[]`), and `summary` (`findings`, `by_severity`, `by_state`, `undispositioned`,
    `owner_ruled`, `conflicts`, `observations`, `observations_answered`). Each row: `fid`,
    `severity`, `goal`, `title`, `state`, `reason`, `backlog_id`, `owner_ruling`, `conflict`. Each
    observation row: `oid`, `goal`, `title`, `state`, `reason`, `backlog_id`, `paths` — no
    severity, and its unanswered state is `noted` rather than `undispositioned`, because an
    observation is explicitly not work the record demands. The two lists and the two tallies stay
    separate: a consumer that summed them would report more findings than the review made.
    **This report bumps `schema_version` on any change to its key SET, not only a breaking one**
    (the telemetry report below follows the same rule). The reason
    is specific to a report of optional-by-nature lists: without a bump, a consumer meeting a
    report with no `observations` key cannot tell whether the review demoted nothing or the writer
    predates the field, and those call for opposite handling. Version 2 added the observation list
    and its two summary counts.
  - **Hook context channel:** the SessionStart digest emits the Claude Code
    `{"hookSpecificOutput":{"hookEventName":…,"additionalContext":…}}` injection shape.

## Error Model   <!-- recorded decision → api_error_model_approach -->

**Recorded decision — `api_error_model_approach`: exit codes are the contract, on a documented,
consistent scheme; message severity is a stable prefix vocabulary; errors are attributed, never
raised as stack traces across the boundary.** The intended scheme:

| Channel | 0 | 1 | 2 |
|---|---|---|---|
| **Harness hook** (`stop`, `clear` refusal) | allow / clean | — | **block** |
| **CLI gate / query** (`test-status`, `verify-coverage`, `check-*`, `resolve-base`) | satisfied / pass | not satisfied / fail | — |
| **CLI advisory report** (`verify-records`) | ran — findings, if any, are on stdout | **could not run** (unresolvable interval, unreadable state) | usage error |
| **State-mutating writer** (e.g. `disposition`) | written, or an idempotent no-op | **refused** — validation failed, nothing written | **usage error** |
| **Usage / arg error** (any subcommand) | — | — | **usage error** |

`check-released --json` emits `{release, verdict, checks[]{check, state, detail}}`, where
`verdict` is one of `released` | `not-released` | `unverified` and each `state` is
`ok` | `failed` | `unverifiable`. Registered here because the `--json` emitters are enumerated in
this section, and a payload documented only by its exit code is a shape a caller has to reverse-engineer.

**A gate whose SUBJECT could not be read takes a third outcome — exit 3 — rather than folding into
0 or 1.** This is a standing rule, not a list to maintain: 0 would report a clean bill off a check
that never ran, and 1 would put a new meaning on a number that already carries a specific remedy,
sending the caller to a fix that cannot apply. Each command below states what its own two foldings
would have said, because the argument is only convincing in the concrete.

- `check-plugin-active` (2026-08-27), *unknown* — folded into 1 it reports a broken install
  because a harness-internal file would not parse, sending an operator to reinstall something that
  works; folded into 0 it reports a clean bill off a check that never ran.
- `check-operator-verification` (2026-08-27), *unreadable queue* — folded into 0 it reports a
  drained queue on a queue nobody parsed, which is the defect it was written to close; folded into
  1 it inherits "there are pending entries, drain or override the first one", and both remedies are
  inapplicable to a file that yielded no entries, leaving the caller at the queue file — the one
  move the refusal forbids. It still BLOCKS: 3 is non-zero, so the gate fails closed.
- `check-learnings-pairing` (2026-08-27), *unreadable pair* — folded into 0 it reports a clean
  pairing off a corpus it could not decode, which is this scope's own subject; folded into 1 it
  claims a duplicate heading it never saw, sending an operator to hand-edit a file that is fine.
- `check-released` (2026-08-04), *unverified* — see below.
- `check-branch-pushed` (2026-09-12), *detached HEAD / git unreadable* — folded into 0 it reports
  the branch safe to merge off a check that never ran, which is the silent short merge the gate
  exists to stop; folded into 1 it inherits "push before merging", and there is nothing to push
  from a detached HEAD and no git to push it with. Its exit **1** is reserved for a push state it
  *did* read and found unsatisfied (`unpushed-commits`, `local-behind-remote`, `diverged`,
  `no-upstream`, `upstream-ref-missing`), where a push or an integrate-then-push is the remedy in
  every case. Both codes BLOCK — the third outcome buys the caller an applicable remedy, not a
  different verdict.

`check-released` (2026-08-04) exits **3** for
*unverified*: nothing failed, but a check could not run — no `gh`, no `origin/main` in a
shallow checkout, or a declared `toml` version file on a pre-3.11 interpreter (no `tomllib`).
It is a distinct code rather than folded into 0 or 1 because both foldings are
wrong in the environment the command exists for. Folded into 1 it reports a broken release on a
fresh clone; folded into 0 it reports success on a tag-push CI job, which has no `origin/main` by
default and may have no token — precisely the case where an unpublished Release must turn the
build red. Its `--json` `verdict` therefore has three values: `released`, `not-released`,
`unverified`. `--allow-unverifiable` collapses 3 to 0 for an operator who wants the local subset.
CI binds to the exit code, so any non-zero is red without special-casing.

**The third outcome is scoped to gates, and the queue mutators are the worked counter-example
(2026-09-12).** `verify-operator-verification` and `accept-operator-verification` refuse an entry whose
`**Status:**` line cannot be read — it is not on a line of its own, carries an unrecognised token, or is
absent — writing nothing and naming the edit that fixes it. That refusal exits **1**, not 3, and the
reasoning is worth keeping because the first attempt got it backwards by generalising from
`check-operator-verification`'s exit 3 above.

These two are **state-mutating writers**, not gates. Their row in the table reads `1 = refused,
validation failed, nothing written`, which is exactly and only what happens, so 1 carries no competing
remedy to be displaced — the condition that earns `check` its third outcome is absent. Adding a 3 here
would put a new meaning into the scheme that the scheme does not need, and owe the registry a row for a
member that should not exist. **The rule this states: read the row for the channel the refusal reaches,
not the one for the nearest command that looks similar.** A gate and a writer over the same subject
take different codes for the same underlying fault, and that is the scheme working rather than an
inconsistency to iron out.

Fail-direction is deliberate and per-purpose:

- **Unevaluable *advisory* gate** (an optional lib path failed to import) → **fail-open, exit 0**: an
  ungradeable gate must never false-block (`classify-diff-risk`, `check-operator-verification`,
  `check-plugin-active`). Scope check, because it is easy to over-read: this covers the **plugin's
  own lib** failing to import, where prawduct itself is broken and blocking the caller helps nobody.
  A command whose *subject* could not be read is a different case and takes the third outcome below.
- **Unevaluable *writer*** (a state-mutating command whose lib failed to import) → **fail-closed,
  exit 1**: never report a false success. (`regen-views` used to be the worked example, escalating
  to **2** for validation/IO errors; it has since been removed (#303), so the rule's subjects are the
  operator-verification and coverage writers.)
- **Advisory report** (`verify-records`) → **exit 0 even with findings**, because it advises the
  builder and gates nothing; **exit 1 only when it could not run.** Findings are not a failure
  state, but an unrun check must never read as a clean one — inside a single run, the same rule
  appears per check as the `unchecked` list rather than a silently absent result.
- **Special sentinels** (documented, not general): `critic-begin` **2** = scope-widened;
  `critic-begin` **3** = no review needed (added 2026-08-06);
  `critic-begin` **4** = round budget exhausted (added 2026-09-09);
  `critic-begin` **6** = evidence store unusable for `verify-resolutions` (added 2026-09-22) —
  unreadable, or schema-ahead records present. Distinct from **1** because the skill's exit-1
  row on `verify-resolutions` demotes and re-dispatches, and no review repairs a store or updates
  a plugin; a demoted one would append its fact to a store nothing can parse. **5 is withdrawn,
  not free:** #167's `self-inflicted-refusal` held it on `develop` until its 2026-09-20 revert,
  and never shipped in a release, so it is left unclaimed rather than given a new meaning;
  `evidence status` **2** = schema-ahead records present (gates can't be trusted until update).
  (`regen-views` **2** and **3** are RETIRED, not repurposed: the command went inert and was
  then removed (#303), so those two meanings were removed rather than given new ones. Retiring a
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
  inert by construction (no gate reads a non-`review` kind), so it changes no verdict. A
  `verify-resolutions` anchored to an unchanged tree with nothing outstanding takes the same 3, for
  the same reason — it used to fall out as a bare 1, which the skill's exit table routes to
  "re-dispatch per the demotion property", manufacturing a full round the gate did not want.

  **`critic-begin` 4 — round budget exhausted.** This build-plan SCOPE has already bought the full
  rounds `review_round_budget` allows (`.prawduct/project-state.yaml`, default 6, `null` disables).
  A distinct code rather than folded into 3: both refuse a dispatch, but a 3 says the *gate* does not
  want this round and a 4 says the *loop* has run out while the gate may still be unsatisfied, and
  the caller's next move differs — a 3 is "you are done", a 4 is "you are done buying rounds, and any
  BLOCKING findings still need `verify-resolutions`". Folded into 1 it would read as a dispatch
  failure and invite a retry in another mode, which is the round it exists to refuse. The refusal
  auto-ACCEPTs the outstanding **non-blocking** findings, renders the census to stdout, and appends
  one `guard-refusal` fact; `verify-resolutions` is never counted and never refused, and no BLOCKING
  finding is ever swept — so the budget can end a review loop and can never open a gate. `--force`
  dispatches anyway. No session state is written, so a 4 needs no `critic-end`. It is checked
  BELOW the free-interval refusal, so an interval that needs no review still answers 3: "the loop
  is over" and "there was nothing to review" stay distinct, which is why they are two codes.
  Rounds are counted per build-plan **scope** (intersected with this branch's lineage, since the
  store is clone-wide); a dispatch that resolves no scope is not budgeted, because there is no
  body of work to bound and the census the refusal renders is selected from the same set.
  **Where the lineage span holds no commits the bound is this `actor.worktree` instead.** An
  intersection with an empty set is empty, so wherever that span is empty the ceiling was
  unreachable — declared, on by default and silently inert. A trunk-based repo is the case that
  motivated it (every push restores the state), but the predicate is the SPAN, not the repo shape:
  a branch cut and not yet committed to takes the same route, so a branch resuming a scope inherits
  that scope's rounds from this worktree. The clone-wide reason is unchanged and is why this is a
  second bound rather than a dropped one; keying on the span rather than on a zero count is what
  leaves a branch with commits and no rounds yet answering by lineage. The verdict and the
  `critic-dispatch-round-budget` guard-refusal fact both carry `bound` (`lineage` | `worktree`),
  because the two count different sets and the control's retirement question needs to tell them
  apart. **Nothing resets the worktree-bounded count** — a branch cut resets the lineage one, and
  trunk has no cut, so a reused scope name inherits the previous body of work's rounds, and can
  refuse its first dispatch while auto-accepting the older work's outstanding findings. Give each
  body of work its own scope name, or raise `review_round_budget`.

**The `backlog` group carries its own exit-class set — a documented scheme, not an exception to the
table above.** `lib/backlog/cli.py`'s `_EXIT_CLASS` maps every error `code` the group can return onto
a fixed class: **2** validation, **3** not-found, **4** conflict, **5** auth, **6** unavailable, with
**0** for success and **1** reserved for a code that reaches the map unlisted. The discipline is this
section's — exit codes are the contract, the failure is attributed inside the envelope, no stack
trace crosses the boundary — and the wider vocabulary is what a caller needs in order to branch on
*why* a write failed, which 0/1/2 cannot carry. `backlog verify-migration`'s **4** is that ordinary
`conflict` class applied to a completeness disagreement (a source item with no target issue), not a
sentinel meaning of its own, which is why the class set belongs here rather than one member of it.
Which `code` maps to which class, and the envelope the code rides in, are
`documentation/backlog-service-api-contract.md` § 4.

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
- **Telemetry report** carries its own `schema_version`, bumped on any change to its key set
  (`plugin/docs/governance-telemetry.md`, pinned by `tests/test_review_stats.py`), so a
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
  future **major** version. `bug-inbox` is in this state: it stays callable, prints its notice,
  does nothing, and exits 0. It joined the tier
  2026-09-08 with the upstream drop-box it resolved — and it is the member that shows the clause
  binding rather than merely describing, because the 2026-08-11 departure below did **not** reach
  it: that departure is scoped to a caller which is a stale hook registration, and this one's
  caller is a person.

  **REMOVED 2026-10-21 (#303, owner ruling 2026-09-28: "do").** `stamp-merged` and `regen-views` were deleted outright — the deprecate-then-remove path's *remove* step, taken by owner ruling rather than at a major boundary. Neither was ever registered by a shipped `hooks.json`, so the harness-skew retention rule below does not reach them; a copied script that still calls one now gets the usage error. The clause's "defer removal to a major" makes this a release-time obligation: the release carrying it should be a major, or the release notes must say why not. The parser's special cases for the retired `chunks=` key (comma-split, cross-line union) went in the same change.

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
  `allowed-tools`): `evidence status|list`, `review-stats --json`, `stats --json`, `render-dispositions`,
  `learnings-files` (bound by the Critic skill, the PR reviewer protocol and the reviewer agent),
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
  contract): `clear`, `stop`, `subagent-stop`, `critic-begin`, `critic-consolidate`,
  `learnings-migrate` (run once per repo from the session-start directive), `learnings-compact`
  (run from the session-start directive when a corpus is over its limits).
  **`backlog <op>` sits in this tier on different grounds:** its callers are the
  `/prawduct:backlog` skill and adopter agents rather than the harness, and § Direction's 2026-08-02
  ruling puts every subcommand outside the two published surfaces here. Unpromised, not unused —
  § Operations, "Backlog service", is the entry, and it names what would move it.
- **Consumer-authored configuration: the project-state key surface** (declare a chunk that adds,
  renames or removes one as `**Exposed API:** project-state keys`). The keys a product writes in its
  `.prawduct/project-state.yaml` and the plugin reads — `test_command`, `tests_dirs`,
  `release_version_files`, `backlog_service_repo`, `base_branch`, `risk_surfaces`, `learnings_budgets`
  and the rest of those `plugin/templates/project-state.yaml` documents. **Tier: supported, not
  `stable`.** The `stable` tier is exactly the two published subcommands (§ Direction), and nothing
  here promises a major for a key change; what it promises is the compatibility norms below, because
  a product's committed file is written once and read by every later plugin version. A key the
  template documents is supported; one the plugin reads but the template does not is internal.
  **Cost of a change:** adding a key is additive and free, and an absent key must keep meaning what
  it meant before it existed. Removing or repurposing one is a breaking change to every product that
  set it, so the **additive-first and deprecation norms apply** (§ Deprecation & Compatibility): keep
  reading the old key, say so with attribution, and defer removal to a major. Readers stay tolerant of
  unknown keys. Versioning the file format itself is out of scope.
- **Deprecated and inert** (callable, writes nothing, exits 0; removal deferred to a major). The
  members § Operations marks so, in two sub-shapes, split by **who calls them** — which decides whether they announce
  themselves:

  - *Announcing* — `bug-inbox`, and since learnings v2
    `audit-learnings`, `learnings-obligation`, `check-learnings-pairing` (their notice names the
    rules layout that replaced the corpus they graded). Notice on stderr. `stamp-merged` and
    `regen-views` were members until their removal (#303); they lost their bodies when derived
    views were retired. `bug-inbox` resolved the local
    `incoming-bugs/` drop-box for `/prawduct:report-bug`, which files GitHub issues instead, so
    there is no directory left to resolve. **Prawduct's own release runbook no longer calls any of
    them**, so the remaining reason to keep them callable is the one that cannot be audited from
    here: a consumer's copied operator script or a person's habit, where a non-zero exit would break
    a pipeline mid-release. The notice tells such a caller to drop the call. `bug-inbox` also moved
    its exit code, 1 → 0: the 1 meant *no inbox is configured*, a condition a caller could branch
    on, and nothing can be configured now.

  - *Silent* — `build-index`, `user-prompt-submit` (inert since v3.3.3). **No output on either
    stream.** Their caller is a pre-3.3.2 `hooks.json` registration, not a person: a notice has no
    reader who can act on it, and the next plugin update replaces the registration anyway. On
    stdout silence is a correctness requirement rather than a preference — a hook exiting 0 has its
    stdout **injected into the model's context** (SessionStart into the session, UserPromptSubmit
    ahead of every turn), so a deprecation notice printed the ordinary way would be read as
    instruction.

  The split is a **recorded departure pending owner ratification**, not a settled rule — see
  § Deprecation & Compatibility, where the norm it departs from still stands unamended and the
  proposed *silent-when-the-caller-is-a-registration* clause is the question put to the owner.
  Every member of the tier is in `_EPHEMERAL_SAFE_COMMANDS` — without it the fail-closed disposable-worktree guard treats an
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
