# Issue #953 — Evidence: The Clone-Shared Store Has No Size Advisory: Requirements

`status: draft · stage: requirements · area: governance/telemetry · added: 2026-10-04 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/953`

Related: #948 (wave 1 telemetry, the producers this item gives a lifecycle), `.prawduct/artifacts/data-model.md`
(per-kind **Droppability** clauses), `nonfunctional-requirements` norm (growth is an advisory, never a
hard limit), `plugin/lib/oversized_state_probes.py` (the advisory pattern to copy).

## Problem

`<git-common-dir>/prawduct/evidence.jsonl` is append-only and nothing ever shortens it. `read_facts`
parses every line on every gate call. Wave 1 added two more unbounded producers: a `session-start`
fact per session boundary and a `stop-gate:` `guard-refusal` fact per blocking gate. The data model
calls both droppable; no code drops them. This repo's store held 5,205 lines on 2026-10-03.

Success: a store that has grown past a stated size tells the session so once, dismissibly, and a
single command can shrink it by removing only facts whose loss changes no governance answer.

## Grounding facts (verified 2026-10-04)

- **A size signal exists, but for a different quantity and on a different channel.**
  `evidence.TREE_COUNT_ADVISORY = 10_000` (`plugin/lib/evidence.py`) prints a NOTE only inside
  `prawduct-hook evidence status`, which nobody runs unprompted. It counts distinct *review* trees
  (the cost of coverage composition), not lines or bytes (the cost of `read_facts`). Neither
  observational kind moves it. So the store can pass any sensible size with that NOTE silent.
- **The advisory machinery to reuse exists.** `oversized_state_probes.py` registers per-file probes
  through `advisory_store.register_probe` / `probe_families.register_all`, with a threshold that is
  repo-configurable (`core.oversized_file_threshold`) and evidence that carries the path only, never
  the size, so the advisory id stays stable while the file changes and a dismissal sticks. That module's
  docstring states each of those choices and why; this item inherits them rather than re-deciding.
- **The store is clone-shared and appends take no lock.** `append_fact` writes one `os.write()` on an
  `O_APPEND` fd. Any compaction that rewrites the file races every concurrent appender in every
  worktree of the clone: an append landing between the compactor's read and its rename is lost.
  A lost `review` or `resolution` fact is a governance answer silently erased.
- **"Observational" is not the same as "droppable without changing a verdict".**
  `OBSERVATIONAL_KINDS = {guard-refusal, test-run, session-start}` is a claim about
  `coverage_algebra` inputs only. But `gates._store_run_vouching` reads `test-run` facts to let a run
  recorded on another branch vouch for a judgeably identical tree. Dropping such a fact can flip a
  test-evidence freshness verdict from fresh to stale (a re-run, not a wrong answer). data-model.md's
  "droppable at any time" for `test-run` is true of coverage and false of that gate's verdict, so
  acceptance #2 ("every gate verdict is unchanged") cannot be met by kind alone.
- **Dropped observational facts are also a telemetry input.** Stop-block rates are
  `guard-refusal` count over `session-start` count. Dropping one kind without the other, or dropping
  by a horizon that differs per kind, skews the rate the wave-1 metrics report.
- **Dispositions and resolutions are not observational but have a stated rule.** data-model.md: a
  `disposition` is droppable exactly when the review it targets is, never alone. The issue scopes
  compaction to observational kinds, so this item drops no review, resolution or disposition.
  The existing `TREE_COUNT_ADVISORY` text ("a fact may only be dropped if no surviving path can
  traverse it") is about that second, harder compaction and stays out of scope here.

## Requirements

### R1 — Size advisory (surfaces, never blocks)

- R1.1 A probe fires when the store exceeds a threshold. The threshold is **line count**, because the
  cost it guards is per-line parsing in `read_facts`; byte size is not used. Default to be set in
  design from a measurement of `read_facts` latency (5,205 lines is the one data point on record).
- R1.2 The threshold is overridable per repo through a `project-state.yaml` key, mirroring
  `oversized_file_threshold_kb`, for the same reason that key exists (a repo that has weighed the
  trade can stop being nagged).
- R1.3 Advisory evidence carries the store's identity only, never the count, so it is stable across
  appends and a dismissal is respected (inherits `oversized_state_probes` evidence rule).
- R1.4 The advisory names the one command that compacts (R2) and says what it will and will not drop.
- R1.5 The probe is cheap: it must not call `read_facts`. A line count over the file is enough, since
  a probe that parses the store pays the cost it is warning about on every session start.
- R1.6 No path in R1 or R2 returns a blocking result. A missing store, an unreadable store, or a
  store outside a git repo yields no advisory and no error.

### R2 — Compaction of observational kinds

- R2.1 Entry point: `prawduct-hook evidence compact [--older-than <duration>] [--dry-run]`. Default
  behaviour is `--dry-run`-equivalent reporting unless confirmed, since compaction is irreversible
  (design decides whether that is a flag or a prompt).
- R2.2 Droppable set is exactly `guard-refusal` and `session-start`, aged past a horizon. `review`,
  `resolution`, `disposition` and unknown kinds are never dropped, and a schema-ahead line of any kind
  is kept (same rule as `_is_observational`: an unparseable or newer line is treated as load-bearing).
- R2.3 `test-run` is **not in the droppable set by default**. Either it is excluded outright, or it
  is dropped only when design shows the freshness fallback cannot be affected (for example, a tree no
  live branch or worktree still carries). Open question 2.
- R2.4 `guard-refusal` and `session-start` use **one shared horizon**, so the stop-block-per-session
  rate stays computed over matching windows after compaction.
- R2.5 Compaction is safe against concurrent appenders from other worktrees (open question 1). A
  compaction that cannot guarantee no lost append refuses and says why; it never proceeds optimistically.
- R2.6 After compaction the command reports counts dropped per kind and kept per kind, so a reader can
  see that nothing outside the droppable set moved.
- R2.7 Idempotent: running it twice drops nothing the second time.

### R3 — Verdict preservation (the acceptance test, made specific)

- R3.1 For a fixture store containing every kind, compaction leaves `coverage_algebra` verdicts and the
  `coverage_fingerprint` unchanged (the fingerprint already excludes observational lines, so this is
  checkable directly).
- R3.2 For the same fixture, `gates._store_run_vouching` returns the same answer before and after.
  This leg exists because of the `test-run` finding above and must be red-verifiable: it must fail
  when `test-run` is added to the droppable set with a fact the fallback depends on.
- R3.3 The data-model.md Droppability clause for `test-run` is corrected in the same change to say
  what is true (coverage-neutral, not freshness-neutral), and data-model.md's `session-start` and
  `guard-refusal` clauses name the compaction command as their consumer.

### Out of scope

- A per-kind cap (issue scope-out; the norm forbids a hard limit).
- Dropping `review`, `resolution` or `disposition` facts (reachability-based compaction, the harder
  problem `TREE_COUNT_ADVISORY`'s note anticipates).
- Moving or splitting the store file, or changing `read_facts` to be incremental.
- Scheduled or automatic compaction. The advisory prompts; a person or session runs the command.

## Acceptance (restated, testable)

1. A store over the threshold produces a dismissible advisory at session start; under it, none; a
   missing or unreadable store, none. No outcome blocks a Stop.
2. After `evidence compact`, a store of mixed kinds keeps every review, resolution, disposition, unknown
   and schema-ahead line byte-for-byte, and the R3.1 and R3.2 checks hold.
3. A concurrent append during compaction is either preserved or the compaction refuses (R2.5), proved
   by a test that interleaves an append, not by reading the code.
4. Dismissing the advisory survives further appends (R1.3).

## Open for design

1. **Concurrency mechanism.** Appenders hold no lock, so options are: take a lock all appenders also
   honor (changes the hot append path), rewrite via rename and re-scan the old file for lines appended
   since the read, or compact only when the store's size and mtime are unchanged across the rewrite.
   The cheapest that is provably safe wins; rename-and-reconcile touches no appender.
2. **`test-run` policy.** Exclude entirely, or age-drop with a reachability check. Depends on how often
   the freshness fallback actually uses an old run; measure before deciding.
3. **Default threshold and horizon.** Measure `read_facts` cost at 5k, 20k and 50k lines; pick the
   threshold where it is a noticeable share of a gate call, and a horizon (days) that leaves enough
   history for the stop-block-per-session metric's reporting window.
4. **Where the probe lives.** A new module beside `oversized_state_probes.py` or a second family inside
   it. The probe reads the store under the git common dir, which that module's file-based probes do not.
5. **Relation to `TREE_COUNT_ADVISORY`.** Keep the status NOTE as a separate, tree-based signal, or fold
   both into the new advisory. Folding risks hiding that the two measure different costs.
