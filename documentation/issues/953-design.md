# Issue #953 — Evidence: The Clone-Shared Store Has No Size Advisory: Design

`status: draft · stage: design · area: governance/telemetry · added: 2026-10-05 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/953`

Requirements: `documentation/issues/953-requirements.md` (R1–R3, five open design questions).
This document answers each of the five and states the build and test plan.

## Decisions

### D1 — Concurrency: cooperative lock plus post-rename reconcile (open question 1)

Appenders (`evidence.append_fact`) write one `os.write()` on an `O_APPEND` fd and hold no lock.
Compaction is a rewrite, so it races them. Two mechanisms, used together because the clone's
worktrees can run different plugin versions:

1. **Cooperative lock.** A sidecar `<git-common-dir>/prawduct/evidence.lock`. `append_fact` takes
   `flock(LOCK_SH)` around its open-write-close; `compact` takes `flock(LOCK_EX)` with a bounded wait
   (5 s) and **refuses** if it cannot get it (R2.5). Shared mode keeps appenders concurrent with each
   other; only compaction excludes them. The hot path gains two syscalls per append; appends are
   per-event, not per-line-read, so the cost is not on `read_facts`.
2. **Reconcile against old-version writers.** Compact holds the old file open (`fd_old`), records
   `size0`, writes the filtered copy to `evidence.jsonl.compact.<pid>` in the same directory, and then:
   re-reads `fd_old` from `size0` to EOF and appends those bytes verbatim to the temp file (they are
   appends that landed during the rewrite); `os.replace`s temp over the store; re-checks `fd_old`'s
   size once more and appends any further tail to the new file. An appender that opened the old inode
   before the rename and writes after the final check is the residual window.

**Residual risk, stated plainly.** A writer running a pre-lock plugin version, in a window of
microseconds after the final check, loses one fact. The cooperating path has no window. We accept this
rather than add a mechanism, because (a) the lost fact is a single append, and (b) the alternative of
refusing compaction whenever any other plugin version has written recently cannot be detected
(`actor.plugin` records writers only after the fact). The residual is documented in the command's help
and in data-model.md, not hidden. If the owner will not accept it, the fallback is to compact only when
no other worktree is registered (`git worktree list` length 1), which is provable but makes the command
useless in this repo's usual multi-worktree state.

Platform: `fcntl` is POSIX. Where it is unavailable, `compact` refuses with that reason; the advisory
still fires (counting lines needs no lock) and names the limitation.

### D2 — `test-run` is excluded outright (open question 2)

`gates._store_run_vouching` keeps the newest fact per `tree`, per `head` and per `branch`, then picks
candidates for an arbitrary `target_tree`. Which old fact is the newest for some future target tree
cannot be known, so no age or reachability rule makes a drop provably verdict-neutral. `test-run` is
therefore **not droppable by compaction**, and `OBSERVATIONAL_KINDS` is not reused as the droppable
set. A new constant, `COMPACTABLE_KINDS = frozenset({"guard-refusal", "session-start"})`, is defined
beside it with a comment stating why the two differ. `test-run` volume is one fact per recorded suite
run, which is low next to per-session and per-Stop producers; the build task measures this repo's
kind mix and files a follow-up only if `test-run` dominates.

### D3 — Threshold and horizon (open question 3)

Measured 2026-10-05 on synthetic stores of ~350-byte lines, mixed kinds, `read_facts` cold, this
container:

| lines | `read_facts` | line count (raw bytes) |
|---|---|---|
| 5,000 | 43 ms | 1 ms |
| 20,000 | 545 ms | 4 ms |
| 50,000 | 1,285 ms | 9.5 ms |

`read_facts` is called per gate call, so half a second is a noticeable share of a Stop. The growth
from 5k to 20k is 4x lines for 12.7x time (superlinear); the cause was not isolated here and the
build task should re-measure with a real store before fixing the number.

- **Threshold: 20,000 lines**, key `evidence_store_line_threshold` in `project-state.yaml`, parsed like
  `oversized_file_threshold` (missing, non-integer, zero or negative fall back to the default).
  Rationale: this repo's store was 5,205 lines after about a day of wave-1 producers, so 20k is
  roughly a few days to weeks of activity, late enough not to nag and early enough to act before the
  ~0.5 s point.
- **Horizon: 30 days**, shared by both kinds (R2.4), overridable per run by `--older-than 14d`.
  `--older-than` accepts `<n>d` only; one unit avoids a parser. A fact is dropped when its `ts` is
  strictly older than `now - horizon`; a fact whose `ts` does not parse is kept (load-bearing by
  default).

### D4 — Probe location (open question 4)

A new module `plugin/lib/evidence_size_probe.py` beside `oversized_state_probes.py`, registered from
`probe_families.register_all` the same way. A second family inside `oversized_state_probes` would mix
two roots: that module measures files under `.prawduct/`, this one measures a file under the git
common dir resolved by `evidence.store_path(Path(codebase.root))`. The probe:

- type `oversized-evidence-store`, one advisory;
- counts newline bytes in 64 KB chunks and never calls `read_facts` (R1.5);
- `evidence` is a fixed identity string (`"evidence.jsonl"`), no count or size, so the advisory id is
  stable and a dismissal survives appends (R1.3, same rule as `oversized_state_probes`);
- yields nothing when `store_path` is `None`, the file is absent, or it cannot be read (R1.6);
- `recommended_action`: `prawduct-hook evidence compact` (dry run, so safe for the runtime to run);
  `owner_action`: one or two sentences saying it removes only Stop-block and session-start records
  older than the horizon, that review, resolution and disposition records and test runs stay, and
  that it is irreversible once confirmed. No command in `owner_action`.

### D5 — Relation to `TREE_COUNT_ADVISORY` (open question 5)

Kept, unchanged, and separate. It measures distinct review trees (composition cost) and the new probe
measures lines (parse cost); they respond to different remedies, and only the second has a remedy this
item ships. `evidence status` gains one line, `lines: <n>`, beside the tree count so a person reading
status sees both numbers, and the existing NOTE text is untouched.

## Command

`prawduct-hook evidence compact [--older-than <n>d] [--yes]`

- Without `--yes`: dry run. Takes no lock, writes nothing, prints the counts below and the sentence
  "re-run with --yes to apply". (Resolves R2.1: a flag, not a prompt, because the runtime and
  scheduled sessions have no one to answer a prompt.)
- With `--yes`: D1, then prints the same counts.
- Output (R2.6): `dropped: guard-refusal=<n> session-start=<n>` and `kept: <kind>=<n> ...` for every
  kind present, plus `unparseable/schema-ahead kept=<n>`.
- Selection reads raw lines, not `read_facts` output: a line is dropped only if it parses as an object,
  has `schema == SCHEMA_VERSION`, its `kind` is in `COMPACTABLE_KINDS`, and its `ts` is older than the
  horizon. Everything else, including unparseable, non-object, schema-ahead and unknown-kind lines, is
  copied **byte-for-byte** (R2.2, acceptance 2). This is the inverse of `_is_observational`'s
  conservative direction: any doubt keeps the line.
- Exit codes: 0 applied or dry-run; 1 usage; 3 refused (lock not obtained, `fcntl` missing, store
  unreadable, store outside a git repo). Never a Stop-blocking path (R1.6): nothing here is called from
  a gate.
- Idempotent (R2.7): a second run finds nothing older than the horizon and rewrites nothing; with
  zero droppable lines it skips the rewrite entirely, so it takes no lock and touches no file.

## Write-boundary change

`append_fact` is the only change to an existing hot path: wrap its `os.open`/`os.write`/`os.close` in
a shared lock on the sidecar file. If the lock file cannot be opened or locked (read-only common dir,
`fcntl` missing), the append proceeds without it exactly as today, so a lock failure never converts into
a lost fact or a gate error, matching that function's existing error posture. `append_guard_refusal`
and `append_stop_block` go through `append_fact`, so they inherit it.

## Document changes (same change as the code, R3.3)

- `.prawduct/artifacts/data-model.md`: the `test-run` Droppability clause becomes "coverage-neutral,
  not freshness-neutral: `gates._store_run_vouching` reads it, so compaction never drops it". The
  `guard-refusal` and `session-start` clauses name `evidence compact` as their consumer and state the
  shared horizon. The Evidence Store section describes the lock and the residual window from D1.
- `plugin/lib/evidence.py` comment above `TREE_COUNT_ADVISORY` names the new line-count signal as its
  sibling.
- CLI usage string, `plugin/docs/` hook reference and the change-log entry, found by searching for
  `evidence {status|list` and "droppable at any time", not by file name.

## Test plan (each red-verifiable)

1. **Probe**: store of `threshold + 1` lines yields one advisory; `threshold` lines yields none; missing,
   unreadable, and not-a-repo yield none and no error; appending lines leaves the advisory id equal
   (dismissal survives). Red check: make the evidence include the count, and the id-stability test fails.
2. **Threshold key**: absent, `0`, `-5`, `abc` fall back to 20,000; `50` is honored.
3. **Selection**: a fixture holding every kind, at ages on both sides of the horizon, plus an
   unparseable line, a non-object line, a schema-ahead `guard-refusal`, an unknown kind and a
   `test-run`. After `--yes`, only old `guard-refusal` and `session-start` are gone; every other line is
   byte-identical and in the same order.
4. **Verdict preservation (R3.1)**: `coverage_fingerprint` and the `coverage_algebra` verdict equal
   before and after.
5. **Vouching (R3.2)**: `_store_run_vouching` returns the same answer before and after on a fixture
   whose only vouching run is an old `test-run`. Red check: add `test-run` to `COMPACTABLE_KINDS` and
   the test must fail.
6. **Concurrency (acceptance 3)**: with a hook injected between the rewrite and the rename that appends
   a fact (a) through `append_fact` (cooperating) and (b) by a raw `O_APPEND` write (non-cooperating):
   (a) must make `compact` wait or refuse, and (b) must be present after compaction. A third case holds
   `LOCK_EX` from the test and asserts `compact` exits 3 within the bounded wait.
7. **Dry run and idempotence**: dry run leaves the file byte-identical and takes no lock; a second
   `--yes` reports `dropped: 0` and does not rewrite (mtime unchanged).
8. **Write path**: `append_fact` still appends when the lock file cannot be created.

## Build order (for the plan)

1. `COMPACTABLE_KINDS`, line counter, threshold reader, probe, registration, tests 1–2.
2. Selection function and `compact` command, tests 3–5 and 7.
3. Lock in `append_fact`, reconcile in `compact`, tests 6 and 8.
4. Docs and `evidence status` line.

## Still open (for the owner or the builder)

- Whether the D1 residual window is acceptable (the fallback is stated above).
- The 5k to 20k superlinearity: re-measure on a real store before fixing 20,000.
- This repo's actual kind mix, to confirm `test-run` volume does not make D2 hollow.
