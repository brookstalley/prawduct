---
artifact: build-plan
version: 2
scope: gate-clarity
branch: feature/gate-clarity
base: develop
working-branches: []
partition: "01 (Opus-class, high), 02+03 (one Opus-class builder, high; they share session_review_verdict and the Stop hook's critic blocker) and 04 (Sonnet-class, high) delegated to three builders in isolated worktrees. Seams: coverage.diagnose_base_advance_transfer belongs to 01 alone, whose return shape stays as it is; gates.session_review_verdict and the Stop-gate critic blocker in prawduct-hook belong to 02+03; the test-evidence changes_unjudged producers and renderers belong to 04. The coordinator integrates, runs the suite once, writes Chunk 05 and governs"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; 01 takes a cost off every Stop that grows with the review-fact count, and 02 lets an operator skip a cumulative round they would otherwise run blind"
      - "proportionality ratchets both ways → conforms; 03 removes a demand for coverage of history this session did not write, and the PR gate keeps the whole branch"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file's growth rule changes. If 01 adds a persisted memo, its eviction is bounded, and the chunk says how"
      - "review rigor is stage-keyed → conforms; the boundary gate (PR) is unchanged, and only the session gate's span narrows"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer changes"
      - "authority fails closed; advice fails soft → conforms; 01 denies on any diff that cannot be computed, a mode-only change still blocks, 02's explanation degrades to `CAUSE: unavailable (<reason>)` and never prints nothing, and 03 narrows only on an authorship read it fully completed"
      - "local-first → conforms; nothing reaches the network"
      - "every fact has one home → conforms; 02 has one function explain the uncovered verdict for both gates, and 04 gives the out-of-remit reason one producer"
      - "written in Python, never specific to Python → conforms; 04 makes visible that non-Python paths are out of the symbol grep's remit rather than unjudged"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms"
      - "facts immutable and append-only → conforms; no fact is rewritten"
      - "derived views never authoritative → conforms; 01's memo is a derived view whose miss costs time, never a verdict"
      - "a newer-schema fact is surfaced, never dropped → inapplicable because no fact schema changes"
depends_on:
  - plugin/lib/coverage.py
  - plugin/lib/gates.py
  - plugin/lib/evidence.py
  - plugin/bin/prawduct-hook
  - plugin/bin/test-reference-verify
last_validated: 2026-11-11
---

## Goals

**Response taken:** Proceed, citing it. The owner chose these four items on 2026-11-11 ("Yes
please for 937, 890, 961, 900, 1000, 682, and 1098 using subagents, opus or sonnet, each with
appropriate effort level and following our delegation protocol"), after a survey that put
consumer QOL and performance first. #937, #1000 and #682 are `stage:ready` and carry their own
problem, proposed change and acceptance. These sections quote them. #1098 is `stage:idea` and
asks for a decision, which this plan makes in Decisions below, marked as an inference.

**Product:** a governed product's builder waits less at every turn and is told why a gate refused.
Four frictions consumers report or measurably pay for:
- #937: the warm Stop hook spends about 2.9 s of 6.3 s here in one pathspec-limited `git diff`
  per prior review endpoint. The count grows with the store, so long-lived repos get slower.
- #1000 (reported by TangleClaw): an `uncovered` verdict doesn't say whether the base advanced,
  the branch's own head changed, or an uncommitted file defeated the suite match. Builders then
  run another cumulative round blind, or follow a remedy that cannot reach the state.
- #1098: a session that wrote code and also synced or switched branches is asked for review
  coverage of history it did not write.
- #682 (from a discodon report): `changes_unjudged` reads as missing evidence. Two separate Critic
  passes mistook it for exactly that.

**Architecture:** what covers what does not change. Composition, the transfer conditions, suite
vouching and the PR gate's span stay as they are. 01 is a pure optimisation. 02 and 04 change
only what a gate says. 03 narrows only the session gate's demand, and only toward the PR gate's
own bar.

**Constraints:**
- Each item's scope-outs, quoted in its chunk, bind.
- `.claude/rules/learnings/gates.md` binds: "A persisted memo key must cover every input for the
  VALUE's lifetime", and "a message naming the caller's NEXT step must ask the gate that will
  judge that step".
- This repo's hooks govern this session. The changed detection runs against this repo before the
  merge (gates.md).

**Decisions:**
- [DECISION: #1098. The Stop gate's verdict also passes when every judgeable file left uncovered
  on the session span is one this session did not author, using the same authorship read the
  firing span uses (`gates._session_authored_paths`). When that read returns `None`, the verdict
  is as today | The two options #1098 names each misjudge one case. The authored span alone is not
  a tree interval, so the composition algebra cannot ask it. The merge-base span alone would ask
  for coverage of earlier sessions' unreviewed branch work, which belongs to the PR gate, not to
  this session. A relax-only third arm keeps the algebra and both existing arms. It loses only
  false fires, and anything it lets through still meets the PR gate | user can veto/override]
  Inferred, not ruled: the owner has not seen this choice. It is flagged here for the boundary
  review.

**Decisions made mid-build:** (appended while building)

- [DECISION: Chunk 04. `changes_unjudged` narrows to symbol-less Python files and deleted files.
  Non-Python paths move to the new `changes_out_of_remit`, with a record-level
  `changes_out_of_remit_reason`. `changes_unchecked`, the same set under its pre-#682 name, stays
  emitted as a deprecated alias until a major release | api-contract.md's additive-first norm says
  a published key is never repurposed. Its reason is protecting a caller across versions. Every
  reader of this record ships in the same plugin at the same version, and each one now reads both
  buckets: the gate in `verify_coverage` and the directive trigger in `_evidence_changed_judged_code`.
  A record written before the split still reads correctly. This is the precedent the owner ruled
  for #303. The removal the builder first made is undone, so the only departure from the norm is
  the narrowing | user can veto/override] Inferred, not ruled. The builder chose the shape, and the
  coordinator restored the alias.

**Level:** High for 01, 02 and 04, whose items carry their own acceptance. Medium for 03. Whether
the coverage algebra can report which files are left uncovered cheaply, without a second
composition, is unknown until the builder reads `coverage_algebra`. The cheapest step that would
raise it is that read, which is the chunk's first step.

## Verification Strategy

Each chunk's tests are red first at the behaviour it adds, and each names the input that must trip
it. 01 records a before and after timing of the warm Stop on this repo and on one consumer clone
(the same command both times). A mode-only change still blocks the transfer, and a test pins
that. 02 and 04 change what an operator reads, so each pins every rendered branch with an
assertion on the text. After the merge, the coordinator runs the changed Stop detection against
this repo before any commit that could disable it. The full suite runs once, on the integrated
branch.

## Build Chunks

### Chunk 01: The Stop hook's base-advance diagnosis stops scaling with the review-fact count (#937)

- **Description:** `coverage.diagnose_base_advance_transfer` → `_survivors` runs one
  pathspec-limited `tree_diff` per distinct prior base/head endpoint. Make its cost independent of
  the number of review facts. The issue names two routes: memoise per (candidate, anchor, paths)
  across turns, where the base anchor is stable, or memoise `git ls-tree <tree> -- <paths>`
  (mode, oid) per tree and path set, then compare in Python. The builder picks a route and records
  why. Whatever memo it adds has a key covering every input for the value's lifetime and a bounded
  size. It must not use `git cat-file --batch-check <tree>:<path>`, which ignores modes (fail-open).
  The function's return shape and its verdicts do not change.
- **Type:** code (optimisation: baseline before change)
- **Depends on:** none
- **Deliverables:** `plugin/lib/coverage.py` (`diagnose_base_advance_transfer` internals only),
  and `plugin/lib/evidence.py` if the memo lives beside `tree_diff`. Tests in the existing
  coverage/transfer test files, or a new `tests/test_base_advance_diagnosis_cost.py`.
- **Tests:** Red first. With N prior review facts, the number of git subprocesses the diagnosis
  spawns does not grow with N (counted through a patched `run_git`). A mode-only change on a
  required path still denies the transfer. An unreadable tree still degrades and denies. Existing
  transfer tests stay green, unmodified.
- **Acceptance criteria:** a warm-Stop timing before and after, on this repo and on one consumer
  clone, the same command both times, recorded in the chunk's report. No verdict changes.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: Both gates say why a span is uncovered (#1000)

- **Description:** #1000's proposed change, in full:
  - `coverage.explain_uncovered(...)` returns `last_review`, `base_moved`, `head_changed`,
    `uncommitted`, `status` and `reason`. It never raises, and it degrades to `unavailable`.
  - One `CAUSE:` line goes right after the `uncovered:` line in
    `gates._cumulative_critic_verdict`, and in the Stop gate's critic blocker in `prawduct-hook`.
    It names each cause that holds, in a fixed order, with up to three paths each.
  - `transfer_remedy` takes an optional `uncommitted` list. When the denying suite-coupled paths
    are uncommitted, it names `git stash push -- <paths>`, the suite, `test-evidence record`, a
    re-run of the gate, then `git stash pop`.

  Explanation only: no verdict changes. It does not edit `diagnose_base_advance_transfer`, which
  belongs to 01.
- **Depends on:** none
- **Deliverables:** `plugin/lib/coverage.py` (new `explain_uncovered`), `plugin/lib/gates.py`
  (`_cumulative_critic_verdict`, `transfer_remedy`), `plugin/bin/prawduct-hook` (the Stop critic
  blocker), new `tests/test_cumulative_gate_explain.py`.
- **Tests:** #1000's acceptance (a), (b) and (c), the `unavailable` render, and the existing
  coverage, transfer and Stop-gate tests green except assertions on the exact uncovered text.
- **Acceptance criteria:** #1000's checklist.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: The Stop gate does not demand review of history this session did not write (#1098)

- **Description:** In `gates.session_review_verdict`, after the primary verdict and the
  merge-base fallback leave the span uncovered or blocked, add a third arm. Compute the session
  span's judgeable files that composed coverage leaves unreviewed. When
  `_session_authored_paths` returns a set and none of those files is in it, the verdict is
  `covered` with an `imported` key naming the files it excused. The Stop blocker's render says
  so in one line. A blocking finding on an authored file still blocks. When authorship is `None`,
  the verdict is as today. The PR gate is untouched.
- **Depends on:** 02 (same function and render; the same builder does both, in order)
- **Deliverables:** `plugin/lib/gates.py` (`session_review_verdict`), and `coverage_algebra`
  only if it needs a function that reports which files are left uncovered. Tests in the
  session-verdict test file.
- **Tests:** Red first. A session that commits file A, then merges a base carrying an unreviewed
  file B, with A covered by a review: today's verdict blocks, the new one passes and names B as
  imported. The same with A unreviewed blocks, naming A. The same with the reflog unreadable
  blocks, as today. A blocking finding on A blocks.
- **Acceptance criteria:** the four cases above, and every existing session-verdict test green,
  unmodified.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 04: `changes_unjudged` separates out-of-remit paths from unjudged ones (#682)

- **Description:** Present the list so a reader can tell out-of-remit from genuinely unjudged. A
  non-Python path, which the static symbol grep excludes by construction, is reported as out of
  remit with its reason, not as unjudged. Read #556's shipped `changes_unreferenced` first, the
  other half of the same record, so that the two buckets read as one scheme. Scope-out: changing
  what the field measures.
- **Depends on:** none
- **Deliverables:** the producer (`plugin/bin/test-reference-verify`) and every reader and
  renderer of `changes_unjudged` in `plugin/bin/prawduct-hook` and `plugin/lib/gates.py`, the key's
  documentation in `plugin/docs/project-state-keys.md` and the doctor skill, and the tests that
  name it (`tests/test_reference_verifier.py`, `tests/test_verify_coverage_gate.py`,
  `tests/test_test_report_scope.py`). Enumerate readers by grep, not from this list.
- **Tests:** Red first. A changed `.md` or `.ts` path lands in the out-of-remit bucket with its
  reason. A changed Python file with no grep signal stays unjudged. Every rendered branch has an
  assertion on its text.
- **Acceptance criteria:** #682's checklist. A grep for `changes_unjudged` over `plugin/`,
  `tests/` and `documentation/` shows every reader updated, with the output in the report.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 05: The record, the seams, and the boundary review

- **Description:** The coordinator merges the three builder branches, resolves the seams, runs the
  changed Stop detection against this repo, runs the suite once, writes the change record
  (`.prawduct/changes/gate-clarity.md`), and runs one cumulative Critic naming 01 to 05.
- **Type:** cumulative-final
- **Depends on:** 01, 02, 03, 04
- **Done when:**
  1. Suite green on the integrated head, recorded
  2. Cumulative review with no unresolved blocking finding
