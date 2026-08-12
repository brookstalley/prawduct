---
artifact: build-plan
version: 2
scope: durable-agent-worktrees
depends_on:
  - artifact: architecture
last_validated: 2026-08-12
---

## Requirements Confidence

**Level:** Medium

**Problem.** `gitstate.is_ephemeral_worktree` classifies a worktree as disposable from its
*directory name* alone (`.claude/worktrees/agent-<hex>`) and returns before ever consulting the
branch. An agent worktree holding a **real named branch** — `fix/gate-integrity`, not the
harness's `worktree-agent-<hex>` scratch branch — is therefore governed as disposable, and the
ephemeral guard refuses every `.prawduct/` write in it, `critic-begin` included. The Critic gate
becomes unsatisfiable for that branch with no workaround short of evicting the worktree.

**Success.** In an agent-path worktree whose branch is a real named branch: `critic-begin`
dispatches, `test-evidence record` writes to *that worktree's* `.prawduct/`, and the marker is
that worktree's own — so N concurrent agent worktrees need no arbitration. In an agent-path
worktree on a `worktree-agent-<hex>` scratch branch: refused exactly as today.

**Out of scope.** `critic-begin --base/--head` (withdrawn — symptom of this defect).
Per-actor keying of `.test-evidence.json` (#649 — measured non-existent for durable worktrees;
this plan's Chunk 01 test is what closes it). Queueing concurrent reviews (#602, still open, and
per-worktree markers make it far less reachable). Anything in the reporter's §C/§D.

**[ASSUMPTION — the one that carries risk]** A named branch created inside an agent worktree
travels with its tree: the branch is what lands, so a `.prawduct/` write on it is carried, not
discarded. #594's guard exists because an `isolation: "worktree"` agent's *code commit* returns
while its `.prawduct/` write does not — the two are separated. On a real named branch they are
not separable: if the branch is discarded the code is discarded too, so there is nothing left to
govern and nothing silently ungoverned. **Not verified against the harness's actual disposal
policy** — verifying it means dispatching a probe agent, which this session was asked not to do.
If the harness ever merges a code commit *off* a named branch while discarding that branch, this
assumption breaks and #594's defect returns for exactly that case.

## Governing Norms

- `data-model.md` — "derived views are disposable and never authoritative" → conforms
  (Chunk 02 changes what a reader *derives*; the one thing it does store, `actor.branch`, is
  provenance the reader needs, not a derived verdict cached into the store).

## Chunks

### Chunk 01 — Classify by branch identity, not by path alone

**Deliverables**
- `plugin/lib/gitstate.py` — `is_ephemeral_worktree` becomes a true conjunction: an
  `.claude/worktrees/agent-*`/`wf_*` path is disposable **only when** its branch also matches
  the harness's scratch shape (or the branch is unreadable/detached — fail closed, the
  restrictive side, since a tree with no branch has nothing that carries a write out).
- `plugin/bin/prawduct-hook` — two changes, not one. (a) The Ephemeral-worktree guard header's
  rationale: replace the path-based reasoning with the branch-identity one. The note currently
  asserts the write "dies at that merge", which is what makes the refusal message false on a real
  branch. (b) `_check_ephemeral_worktree`'s `kind is None` arm gains a behavior path: it must
  still emit the HEAD-snapshot NOTICE for a durable agent worktree. The notice answers "how old is
  what I am reading" and the refusal answers "may I write here" — only the second stops applying
  on a named branch, and the early return would have dropped the first for exactly the population
  this chunk creates.
- `tests/test_ephemeral_worktree.py` — the missing coverage. Every existing case builds its
  fixture on branch `worktree-agent-<wid>`, so no test today distinguishes the two.

**Acceptance criteria**
- [x] An agent-path worktree on branch `fix/real-thing` is NOT ephemeral; `critic-begin`,
      `test-evidence record`, `disposition` and `advisory dismiss` all proceed.
- [x] An agent-path worktree on `worktree-agent-<hex>` is still ephemeral and still refuses all
      four, with the existing message.
- [x] A `wf_*` workflow worktree is still ephemeral regardless of branch (workflow stages get no
      named branch; the path IS the identity there).
- [x] An agent-path worktree with a detached HEAD is ephemeral (fail closed).
- [x] An `EnterWorktree` session worktree under the same parent is unchanged — still governed.
- [x] **The #649 decider:** two agent-path worktrees of one clone, each on its own real named
      branch, each record test evidence; each reads back its own counts and the clone's
      `.test-evidence.json` is untouched.
- [x] Full suite green, no regressions against the baseline taken before this plan.

**Done when** — acceptance criteria pass · `/prawduct:critic` · blocking findings resolved ·
Status box ticked.

### Chunk 02 — Reconcile the historical reader with the live predicate

**Deliverables**
- `plugin/lib/gitstate.py` — `ephemeral_worktree_kind_of_path` is deliberately path-only,
  because an evidence fact records `actor.worktree` as a string and the tree is usually deleted
  by the time anyone reads it. After Chunk 01 the two predicates disagree about the same path: the
  live one says durable, the historical one says ephemeral. Resolve it — the fact records the
  branch, and both predicates answer from one body. A path with NO recorded branch keeps reading
  as ephemeral (the restrictive side, and the historically accurate one — see AC3), rather than
  becoming a third "unknown" state that no caller of a `str | None` predicate could express.
- `plugin/lib/evidence.py` — `is_ephemeral_fact` consumes the reconciled answer. Its
  consequence is user-visible: `evidence status` prints "these COVER NO BRANCH … the review cost
  was spent, the coverage was not gained" — which becomes a lie about a durable agent worktree's
  review, and lands on exactly the reviews this plan is trying to make possible.
- `tests/test_evidence_ephemeral_provenance.py` — cover both directions.

**Acceptance criteria**
- [x] A fact recorded from an agent-path worktree on a real named branch does NOT read as
      ephemeral in `evidence status`, and is not counted in the wasted-cost sentence.
- [x] A fact from a scratch-branch agent worktree still does.
- [x] A pre-existing fact carrying no branch is not silently reclassified in either direction —
      the store is append-only and no version moves (`data-model.md`).
- [x] Full suite green.

**Done when** — acceptance criteria pass · `/prawduct:critic` · blocking findings resolved ·
Status box ticked.

## Status

- [x] Chunk 01 — Classify by branch identity, not by path alone
- [x] Chunk 02 — Reconcile the historical reader with the live predicate

**Context.** Branch `fix/durable-agent-worktrees` off `develop`. Closes #648; closes #649 via
Chunk 01's decider test. Reported upstream as brookstalley/discodon#2213. The suite was green
before any change here and must stay green; the counts live in `.prawduct/.test-evidence.json`,
which is regenerated by `prawduct-hook test-evidence record` and is the only place they are true.

**BOTH CHUNKS COMPLETE (2026-08-12).** Landed together in `22fbd8dd` rather than one commit per
chunk — Chunk 02's reader could not be reconciled without Chunk 01's predicate existing, and
splitting them would have committed a state where the live and historical answers disagreed.

Review history, all facts in the shared evidence store: `chunk` (3 blocking, 3 warning, 1 note) →
fixes in `22fbd8dd` → `verify-resolutions` clean (7/7) → `cumulative` (0 blocking, 2 warning, 11
note) → fixes in `4ce17414` → `verify-resolutions` clean. All 13 cumulative findings dispositioned
as recorded facts: 6 fixed, 7 accepted (`render-dispositions --review
rev-20260812T222200Z-d5b23a76`).

**Not yet done, and deliberately not:** #648 and #649 are closed on this branch but NOT on GitHub —
that happens at merge. #649's closing note must correct its premise (it conflates the clone-shared
evidence JSONL with the per-worktree `.test-evidence.json`). Carried in
`.prawduct/.handoff-notes.md`.

The risk assumption in Requirements Confidence above is still **unverified** — but it is no longer
recorded only here. Its falsifier now lives in `is_ephemeral_worktree`'s docstring, the hook's
guard header and the change-log, so archiving this plan does not lose it (cumulative R-6).
