---
artifact: build-plan
version: 2
scope: per-tree-test-evidence
branch: feature/653-per-tree-test-evidence
depends_on:
  - artifact: data-model
  - artifact: kernel-v3-evidence-design
  - artifact: boundary-patterns
governed_by:
  - artifact: data-model
    dispositions:
      - "governance verdicts come from the append-only fact ledger, never mutable model-written state; no model sits in a fact's write path → conforms: `test-run` facts are appended by `test-evidence record` (deterministic code) from the same variables it writes to `.test-evidence.json`; the model supplies at most a junit report, exactly as it does today"
      - "facts are immutable and append-only → conforms: a later run on the same tree is a new fact, and the NEWEST fact for a tree decides it, so a red re-run supersedes an earlier green without editing it"
      - "derived views are disposable and never authoritative → conforms: nothing becomes a view; `.test-evidence.json` stays a primary per-worktree record"
      - "a fact written by a newer schema is a loud block → conforms: the new kind rides schema 1, which already keeps unknown kinds and lets gates filter by kind; `SCHEMA_VERSION` does not move"
      - "two stores, two lifetimes → conforms: the store is per-clone and gitignored by construction (inside `.git`), the right lifetime for a cache of runs"
  - artifact: architecture
    dispositions:
      - "every fact has one home → engaged, see the DECISION below on the file and the fact recording one run"
      - "authority fails closed; advice fails soft → conforms: a store that cannot be read or appended leaves clause 2 answering from `.test-evidence.json` alone, which is today's behaviour, never a looser one; a failed append is attributed on stderr and does not change `record`'s exit"
      - "local-first: no network, no daemon, no third-party dependency → conforms"
  - artifact: api-contract
    dispositions:
      - "persisted data independently schema-versioned → conforms: new kind under schema 1"
      - "exit codes are the contract → conforms: no exit code changes; `test-status` gains reason wording only"
      - "additive-first evolution → conforms: one fact kind, no flag or key changes meaning"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: the lookup adds one store read (0.1s on this clone's 12MB store) and at most two tree diffs to `test-status`"
      - "state-file growth is advisory, never a block → conforms: one small line per recorded run"
      - "review rigor is stage-keyed → inapplicable, because no severity or stage changes"
partition: serial — both chunks edit `cmd_test_evidence` and `gates.tests_are_current`
last_validated: 2026-09-23
---

# Build plan — remember green runs per tree, across branches and worktrees (#653)

## Requirements Confidence

**Level:** High on the problem, Medium on the lookup's candidate set (see assumptions).

**Problem:** `.test-evidence.json` holds one record per worktree. Switching branch replaces it, so
switching back to a branch whose tree already has a green run re-runs the suite. In discodon one
`/clear` invalidated evidence for four branches, each paying a ~7.3-minute run plus the review round
its stale-evidence finding rides in.

**Success:** switching between two branches whose judgeable trees each have a recorded green run
re-runs nothing — `test-status` exits 0 labelled tree-valid on each, in either worktree of the clone.

**Out of scope:** changing when the suite runs (#820, next plan); moving the session-fresh clause
or the coverage half off `.test-evidence.json`; retention or compaction of the store.

**Owner decision, 2026-09-23 (recorded on #653):** runs are `test-run` facts on the shared evidence
store, the kind `evidence.py` already reserves.

### Consumer queries (planning.md: enumerate before designing fields)

| # | Consumer | Question | Needs |
|---|---|---|---|
| Q1 | `tests_are_current` clause 2 (`test-status`, Critic, PR payload) | Does any recorded green, whole-suite run vouch for this working tree? | tree, failed, degraded, ts |
| Q2 | `suite_vouches_for_tree(target)` (PR gate, Stop gate transfer) | Same, for a named tree | same |
| Q3 | a reader saying WHICH run vouched | Where and when did it run, and was it measured or reused? | ts, actor.branch/worktree, source |
| Q4 | consumer-overhead measurement (`tools/measure-consumer-overhead.py`) | How many suite runs, how long, per branch? | duration_seconds, actor.branch, ts |
| Q5 | #820 | Was it the whole declared suite? | nothing: a narrowed report is refused before recording (`docs/test-report-contract.md`), so every fact is a whole-suite run by construction |

Failing names (#792) stay on `.test-evidence.json`: no query above needs them cross-worktree.

**Fact body:** `tree`, `passed`, `failed`, `skipped`, `duration_seconds`, `source`
(`run` | `from-junit` | `restamp`), `degraded` when present. No fact when no tree was captured
(`--from-counts`, a capture failure).

`[DECISION: the file and the fact both record one run, written by one command from one set of
variables | the norm's why is that N copies drift because N places must be edited; here one writer
emits both in the same call, so a change to what a run records is one edit. The file answers "this
worktree's latest run" (session clause, coverage half, failing names); the fact answers "which trees
have green runs". Making the fact the only home would move ten readers and give every existing
worktree one false stale on upgrade | user can veto/override]`

`[DECISION: the newest fact for a tree decides it | a flaky red re-run on a tree must supersede the
earlier green, as the single record does today; "any green fact" would let one lucky run vouch
forever | user can veto/override]`

`[ASSUMPTION: candidates are (a) facts whose tree equals the target exactly and (b) the newest fact
recorded on the current branch, each judged by the existing judgeable tree-diff | MED impact — a
branch switch returns to a tree that differs from its run only in docs/metadata, so exact match
alone rarely hits, while diffing every fact is O(store); two diffs bound the cost | user can correct]`

**Boundary investigation (2026-09-23, every `read_facts` consumer, `tools/` included):** every gate,
verdict, count and census filters by kind before reading a body, so no verdict changes. Three
surfaces do change: `evidence list` (a `test-run` row renders with no columns, and rows crowd the
default newest-20 view), `evidence status` (a `test-run=N` tally, harmless), and **`verdict_cache`**,
whose key is a SHA-256 of the whole store text — so every append of any kind makes every cached
coverage verdict unreachable across the clone, and the next gate recomputes cold (17.4s measured
at 2,715 facts; 29–120s observed in a consumer). A suite run usually sits right before a gate.

`[DECISION: the verdict-cache fingerprint hashes every store line EXCEPT well-formed schema-1 lines
of an observational kind (`test-run`, `guard-refusal`) | the memo's contract is that its key covers
every input the verdict is a function of; `coverage_verdict` reads review and resolution facts only,
so those two kinds are not inputs and excluding them keeps the contract exact. Unparseable lines,
unknown kinds and schema-ahead lines stay in the hash, so nothing the verdict might read can escape
it. Alternatives: accept a cold gate after every recorded run (a real cost in large consumers), or
a sibling `test-runs.jsonl` (departs from the owner's one-store decision) | user can veto/override]`

## Chunk 1: record every run as a `test-run` fact

**Delivers:** `test-run` in `KNOWN_KINDS`; `test-evidence record` appends one fact per record that
captured a tree (run, `--from-junit`, `--no-rerun`), soft-failing with stderr attribution;
`evidence list` renders a `test-run` row's tree, counts, source and degraded marker; the
verdict-cache fingerprint excludes observational kinds (DECISION above).

**Done when:** tests for each source, for no fact on `--from-counts`, for a degraded and a failing
run producing facts, for an append failure leaving `record`'s exit unchanged; a `test-run` or
`guard-refusal` append leaves the fingerprint unchanged while a review append, an unknown kind and a
malformed line each change it; targeted tests green.

## Chunk 2: freshness consults the store

**Delivers:** clause 2 of `tests_are_current` and `suite_vouches_for_tree` ask the file's run first
(unchanged), then the store's candidates; the reason names the branch and time of the vouching run.
`data-model.md`'s status line, `boundary-patterns.md`, and the kernel-v3 deferral updated.

**Done when:** the acceptance scenario as a multi-hop test (branch A green, branch B green, back to A:
current, tree-valid, no run); a second worktree at A's tree is current; a red re-run on A's tree makes
A stale; a degraded fact never vouches; an unreadable store falls back to today's answer; targeted
tests green; one `/prawduct:critic`.

## Status

- [ ] Chunk 1: record every run as a `test-run` fact
- [ ] Chunk 2: freshness consults the store
