# Issue #1096 — test-evidence: keep every run in a ledger and compose the suite state: Design

`status: draft · stage: design · area: test-evidence · added: 2026-10-29 · issue:
https://github.com/brookstalley/prawduct/issues/1096`

Acceptance (from the issue): the design names the ledger schema, the composition rules and the
flaky guard, and lists the consumer queries first. Nothing here is built before this is reviewed.

## What exists today (read, not recalled)

- `.prawduct/.test-evidence.json` is one record per worktree. `cmd_test_evidence`
  (`plugin/bin/prawduct-hook`) rewrites it whole when a record lands. Fields: counts,
  `command`, `evidence_tree`, optional `degraded`, optional `failed_tests` (capped list of ids).
- The shared store already has an append-only **`test-run`** fact kind
  (`evidence.append_test_run`, `plugin/lib/evidence.py`). Body: `tree`, `passed/failed/skipped`,
  `duration_seconds`, `source` (`run` | `from-junit`), `head`, `degraded`. It is **observational**
  to the coverage verdict (`OBSERVATIONAL_KINDS`). Its only deciding reader is
  `gates._store_run_vouching`, which asks of at most three facts (newest for the tree, the head,
  the branch) whether each *met* the target tree (`_tree_met`, the judgeable-path diff).
- `run_refusal(run)` is the one statement of "this run may not vouch": `failed > 0` or `degraded`.
- `flaky_policy` (named in #1087) is **not implemented**: `grep flaky_policy plugin/` is empty.
  #1087 closed as `scope:flaky-rerun`, but no flake path landed in the recorder. This design
  therefore specifies the flaky classification itself rather than plugging into one.

So the ledger is not a new store. It is the `test-run` kind, made per-test and composable. The
decision this design needs most is how far to extend that kind, and the answer is in the schema.

## Consumer queries (first, because a persisted format is a lock-in)

Every query takes a **target tree** (the working tree for the Stop gate, `HEAD^{tree}` for the PR
gate, as `suite_vouches_for_tree` already distinguishes) and answers from the ledger alone.

| # | Consumer | Query | Needs |
|---|---|---|---|
| Q1 | Stop gate, `test-status`, `/prawduct:pr` (`tests_are_current`, `suite_vouches_for_tree`) | Does the suite vouch for tree T? | verdict + reason |
| Q2 | Same readers' denial text | Which tests are red, flaky or unrun, named? | per-test ids and outcomes |
| Q3 | Critic / PR body / handoff | Which tests passed only on a retry, with history? | flake list with first-failure text |
| Q4 | `flaky_policy` (#1087) | Is a flake *touched* by the branch? (own file; covered lines per #1088) | flake ids + file of each |
| Q5 | Narrow-run author (`record --narrow`, replaces #1091's workaround) | Can this narrow run be accepted as a supersede, and for which tests? | base's test universe |
| Q6 | `stats`/`contribution` | Counts per tree: runs, flakes, narrow/full ratio | the `scope` and `flaky` fields only |

Q1 and Q2 are the hot path (every Stop). Q3-Q6 are cold. The schema keeps Q1 O(one tree's facts),
never O(store).

## Ledger schema

One `test-run` fact per recorded run (unchanged kind and id scheme). **Additive** body fields,
all optional so every existing fact and every older plugin reading the store stays valid
(`KNOWN_KINDS` is unchanged; unknown body keys are ignored by `_store_run_vouching` today):

```
scope:     "full" | "narrow"          # absent = "full" (every pre-ledger fact)
outcomes:  {test_id: "p"|"f"|"e"|"s"} # per-test results; "p"/"f"/"e"/"s" = passed/failed/error/skipped
selection: [str]                      # narrow only: the arguments that selected the tests
env:       {runner, host_class, python, platform}   # see "Environment"
base:      fact_id                    # narrow only: the full run it is a supersede of
flaky:     [{id, first_failure, env_differs: [str]}]  # filled by composition, not by the recorder
```

- **Why a per-test map, not just `failed_tests`.** A supersede is per test (Q5), so the base's
  *passes* matter as much as its failures. `failed_tests` is capped and failure-only; it stays as
  the human-readable field and is never the composition input.
- **Size.** `outcomes` is the only unbounded field. Ids are stored once per fact; at prawduct's
  ~10k tests an `outcomes` map is ~0.5 MB uncompressed. Mitigation: only a **full** fact carries
  every id; a **narrow** fact carries only the ids it ran. Store hygiene already caps evidence
  size (`evidence_size_probes.py`), and the compose step prunes — see "Retention".
- **`tree`** stays the judgeable-comparable tree capture. A narrow fact records the tree its run
  met, exactly as a full one does; nothing about the tree field changes.
- **No `flaky` written by the recorder.** A flake is a *relation between runs* (fail then pass on
  one tree), so it is derived at composition time. Persisting it per fact would duplicate a
  derivable and let it disagree with the runs it summarises.

### Environment

The owner's refinement (issue comment, 2026-10-27): a pass in a different environment than the
failing run is a flake by definition. `env` is therefore recorded on every fact:

- `runner` — `testament` runner id, or `local`. testament's `report.items[].runner` supplies it.
- `host_class` — `pool` | `local-fallback`. testament's `fallback` object says which.
- `python` / `platform` — interpreter version and `sys.platform`, cheap and always available.
- **Not recorded:** load, cache warmth, wall time. They cannot be compared reliably and recording
  them invites false precision. They are the *reason* flakes exist; the guard below does not try
  to detect them, it only refuses to *mask* them.

`env_differs` lists which `env` keys differ between the failing and the passing run. Same-env
fail→pass is a flake with `env_differs: []` (nondeterminism). Different-env fail→pass is a flake
with the difference named. Neither is ever plain green.

## Composition rules

`compose_suite_state(project_dir, target_tree) -> SuiteState`, a pure function in
`plugin/lib/evidence.py`'s sibling (new module `test_ledger.py`; `gates.py` is already the
largest file and these rules need their own tests). It reads facts for the tree, never the
worktree record.

1. **Base.** The newest `full` fact that *met* `target_tree` (`_tree_met`, unchanged). No base
   means no suite state, and Q1 answers "no vouching run" — the same denial as today.
2. **Overlay.** Narrow facts whose `base` is that fact (or whose tree met the same target, see
   Open question 1) apply in time order. For each test the narrow run reports, the *latest*
   outcome replaces the base outcome.
3. **A narrow run cannot add tests.** A test id not in the base's universe is dropped from the
   overlay and counted as `outside_base`; if any narrow run had such ids the reason says so.
   (Prevents a narrow run from papering over a test the base never saw.)
4. **A later failure beats an earlier pass; a later pass does NOT silently beat an earlier
   failure.** Per test, the outcome sequence is scanned in time order:
   - all pass → `passed`;
   - ends in fail/error → `failed`;
   - ends in pass after at least one fail on this tree → **`flaky`** (rule 5), not `passed`.
5. **The flaky guard.** A test that failed in any run on this tree and passed in a later one is
   composed `flaky` with its full history (run ids, outcomes, `env_differs`, first failure text).
   It does **not** count toward `passed`. Whether a flake blocks is `flaky_policy`:
   `accept` (vouch, note it), `warn` (vouch, Critic WARNING if touched), `block` (does not vouch).
   Default is `warn`. A test that fails on every attempt is `failed` regardless of policy.
6. **Environment sensitivity.** A fail→pass whose runs differ in `env` is a flake with the
   differing keys named, under the same policy. This is the owner's refinement, made explicit.
7. **Tree change needs a new base.** A tree that does not `_tree_met` the base voids the overlay;
   nothing carries across trees. (Same comparison the gates already trust, not equality.)
8. **`run_refusal` still applies per fact.** A `degraded` fact contributes nothing to
   composition; its tests read as unrun, which the denial then names (Q2).
9. **Verdict.** Vouches iff: a base exists, no test composes `failed`, no `degraded` input, and
   the flaky set is acceptable under `flaky_policy`. The reason string names the first failing
   or blocking-flaky ids using the existing `name_failing_tests` shape.

Determinism: composition sorts by fact `ts` then fact id, so equal timestamps resolve the same way
on every machine.

### Retention

The store is append-only and `evidence compact`-style pruning already exists for other kinds. For
this kind: per tree, keep the base and every narrow fact (they are the history the flaky guard
needs); drop whole trees only when no branch tip or open PR head still references them. Pruning is
a store-hygiene follow-up, not part of this change; Q1 stays cheap without it because facts are
indexed by tree.

## How this subsumes the neighbouring items

- **#1087 (`--rerun-failed`).** The rerun is just a narrow run on the same tree. The recorder's
  `--rerun-failed` becomes sugar for "run the failed ids as a narrow `record`", and the flake list
  falls out of composition instead of a second record format. Retire `test_rerun_commands`
  from #1087's scope.
- **#1091 (a narrow `testament run` replaces the full-suite JUnit).** Stops being a prawduct
  concern: a narrow report ingests as `scope: narrow` and cannot replace the base.
- **#679 (a run that cannot record leaves the old green standing).** Orthogonal but complementary:
  its write-ahead `void` must carry into composition as "this worktree's attempt did not complete".
  Specify `void` as a fact-level veto when #679 is built; it is not designed here.
- **#1088 (touched by covered code).** Consumes Q4. This design supplies the flake ids and their
  test file; #1088 supplies the covered-line intersection.
- **#653 (per-tree `test-run` facts).** Already shipped; this extends its kind.

## Integration surface

- `cmd_test_evidence record`: gains `--narrow` (ingest or run as `scope: narrow`, requires a base
  for the same tree or refuses with the command to make one) and writes `outcomes`/`env` on every
  fact. The per-worktree `.test-evidence.json` becomes a **cache of the composed state** for the
  worktree's current tree, rewritten after each fact; its `failed` count is the composed count, so
  every reader that does not know about the ledger keeps working. This is the compatibility seam:
  no gate changes in the first slice.
- `gates._store_run_vouching`: replaced by a call to `compose_suite_state`. `suite_vouches_for_tree`
  and `tests_are_current` keep their signatures.
- `run_refusal` is unchanged and remains the per-run rule.

## Build slices (each independently shippable)

1. **Schema + recorder.** Write `scope: full`, `outcomes`, `env` on every `test-run` fact. No
   reader change. Red-verify: a fact carries per-test ids for a JUnit with a known failure.
2. **`compose_suite_state` + tests**, including the rules table above as property tests (rule 3, 4
   and 5 each get a case that must fail without the rule). Not wired to any gate.
3. **Wire the readers** (`_store_run_vouching`) behind the composed verdict; the worktree record
   becomes the composed cache.
4. **`--narrow` + `flaky_policy` plumbing** (absorbs #1087's remaining scope).
5. **Surfacing**: flakes in `test-status`, the handoff and the PR body (Q3).

## Rejected alternatives

- **A new store file / schema version.** The `test-run` kind already exists, is append-only, is
  shared across worktrees and is observational to coverage. A parallel ledger would need its own
  tree index and its own hygiene.
- **Composing at write time into the worktree record only.** Loses cross-worktree reuse, which is
  what `test-run` facts were added for (#653).
- **Latest-run-wins per test with no flaky guard.** Simplest, and exactly the race-masking the issue
  names: a load-induced pass would erase a real failure.
- **Persisting `flaky`.** Derived data stored beside its inputs; see schema.

## Open questions for the owner

1. **What is "the same tree" for a supersede?** Strict `evidence_tree` equality is the issue's
   wording, but `_store_run_vouching`'s docstring says two runs on the same code rarely share a
   byte-identical tree. A narrow run is normally taken after an edit to the test file or the
   code under test. Recommendation: judgeable-identity (`_tree_met`) against the **base's** tree,
   so a narrow run after fixing a test is allowed only when the fix is outside the judgeable
   set. If the fix is a judgeable change, a new full base is required — which is the rule the
   issue states ("a tree change needs a new base"). Confirm this reading before slice 3.
2. **Default `flaky_policy`.** Recommendation `warn`. `accept` hides flakes from the Critic;
   `block` reproduces today's "any flake costs a full run" unless the narrow rerun path is used.
3. **Is `host_class`/`runner` too coarse to call different environments?** Two pool runners are
   treated as different environments. This is conservative (more flakes named, fewer silent
   greens). Alternative: treat pool runners as one class. Recommendation: keep it strict and
   revisit with data from the first month of `env_differs`.
4. **Does `outcomes` need compression in the store?** Below ~1 MB per full fact it is fine
   uncompressed; prawduct's suite is near that. Decide at slice 1 from a measured fact size, not
   here.

## Not verified in this pass

- That `capture_tree` excludes `.test-evidence.json` (the #1094 design says it does; a comment
  in `_store_run_vouching` says the record is in the tree). Question 1 depends on the answer;
  slice 2 starts by testing it.
- Per-test ids from testament's report shape; slice 1 reads a real report before the schema is
  frozen.
