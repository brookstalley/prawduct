---
artifact: build-plan
version: 2
scope: session-authored-span
branch: fix/1071-session-authored-span
base: develop
working-branches: []
last_validated: 2026-10-27
depends_on:
  - brookstalley/prawduct#1071
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: serial — Chunk 02 is the change record for Chunk 01's one-function fix
---

# Build Plan — Commits this session did not author are not its work (#1071)

## Goals

**Response taken:** Proceed, citing #1071 and the owner's go-ahead on 2026-10-27 ("yes to all")
after the 3.8.0-dev health survey. The survey comment on #1071 carries the evidence.

**Problem:** `gates.session_work_span` diffs the session's base tree against the working tree, so
anything a `git pull`, `git merge`, branch switch or reset brings in reads as this session's work.
Reflection blocks per session rose from 9.7% to 17% under 3.8.0-dev, and 6–7 of the 12 new ones
were sessions that wrote no code. The span also arms the Critic Stop gate (#304), where the same
false fire costs a review round. `TestTheKnownFalseFire` records the false fire as an assumption,
priced at "asking git who wrote each hunk on every turn".

**Success:**
- A session whose only HEAD movement since its start is a pull, fast-forward, automatic merge,
  checkout/switch or reset, and which leaves no uncommitted work, has an empty span: the reflection
  and Critic Stop gates stay silent.
- A session that commits judgeable code still fires, including when it also pulled.
- A merge commit the session concluded by hand (`commit (merge)`) counts only the paths it
  resolved.
- Uncommitted and untracked session work counts exactly as today.
- The span never grows: the new span is a subset of today's.
- The Stop path's added cost is nothing when the span is empty, one `rev-parse` when HEAD's tree
  has not moved since session start, and four or five more git calls when it has.

**Out of scope:** #1071's own repro, which is another session's *commits* in a shared checkout.
Those are `commit:` entries in the same HEAD reflog, so authorship by reflog cannot separate them.
#282 (session lock) owns that seam. #1095 (block-message shape) is separate.

**Inferences (flagged for the boundary review):**
- *The authorship source is HEAD's reflog.* It records how HEAD moved and why, per worktree. One
  `git reflog` read classifies every move since the session started, which is far cheaper than the
  hunk-level authorship the old test priced.
- *The session start time is the `.session-base-tree` marker's mtime.* It is written once, at
  session start, by `cmd_clear`. A new marker field would need the session to be started by this
  plugin build. The mtime works with markers older builds wrote, and the unreadable case degrades.
- *Classification.* Authored: `commit`, `commit (amend)`, `commit (initial)`, `commit (merge)`
  (resolved paths only, via `--cc`), `cherry-pick`, `revert` and `rebase (…)` pick-type entries,
  which replay commits onto a new base. Imported: `checkout:`, `pull` (non-rebase), `merge …`,
  `reset:`, and the `rebase (start)`/`(finish)`/`pull --rebase (start|finish)` moves. **Any
  subject the classifier does not recognise makes it answer today's span**, so a git version with
  new wording loses the narrowing and never the gate.
- *Degradation.* Missing marker, unreadable mtime, failed reflog or failed diff-tree all return
  today's span. Authority only ever narrows on positive evidence.

**Decisions made mid-build:**
- Chunk 01: metadata paths are dropped before the authorship walk rather than after it, so a
  session whose only changes are `.prawduct/` files pays no extra git call. Settled by the cost
  goal.
- Chunk 01: the plan's first cost line ("zero added when HEAD's tree is unmoved") was wrong: the
  check that it is unmoved is itself one `rev-parse`. Corrected above; the cost test
  (`test_its_git_calls_are_bounded_by_what_the_session_did`) pins each tier. Settled by "do it
  right".
- Chunk 01: only the gates' FIRING span narrows. The Critic gate's composition verdict still
  composes coverage over base tree → working tree, so a session that authored code AND switched
  branches is judged on that wider interval, as before. Out of scope here; the boundary review
  should say whether it needs an item.
- Boundary review (R-1/R-10, blocking): treating every merge and fast-forward as imported dropped
  a worktree delegate's merged-back work, whose commits live in the delegate worktree's reflog.
  The rule is now by AGE: a move keeps every commit HEAD reaches that was made since the session
  started; only older history is excluded. A concurrent session's commits pulled in mid-session
  therefore still count, which is #1071's own class. The walk now reads `.session-start` (not the
  base-tree marker's mtime) and must reach an entry older than it, or the whole span stands.
- Live check (gates rule: run a changed detection against this repo first): in this session,
  which switched from the #1087 branch to this one, the old span read 18 non-metadata paths
  (mostly #1087's work, reversed by the switch); the new span reads the 2 files this session
  edited.

## Norm reconciliation (`governed_by`)

- `architecture.md` "Authority fails closed; advice fails soft" — **conforms**. Every failure
  returns today's wider span. The narrowing needs a fully classified reflog.
- `architecture.md` "Every fact has one home" — **conforms**. Authorship lives in
  `session_work_span`, which the reflection gate, the Critic Stop guard, the learnings emitter and
  the briefing already share.
- `architecture.md`, other norms (reviewer never mutates, local-first, writes only `.prawduct/`,
  language-agnostic, guides-not-implements, goals bind) — **inapplicable**: no write path,
  network call, language dispatch or product code.
- `api-contract.md` "Exit codes are the contract" and "Additive-first evolution" — **conforms**.
  The span's dict shape and `source` values are unchanged.
- `data-model.md` — **inapplicable**: no fact kind or schema changes.
- `nonfunctional-requirements.md` "Review wall-clock is P0" — **conforms**. The Stop path adds no
  git call on an empty span, one when HEAD's tree is unmoved, and five or six when it moved.

## Build Chunks

### Chunk 01: The span counts only moves this session authored

- **Description:** `session_work_span` intersects today's base-tree span with the paths this
  session authored: committed entries from HEAD's reflog since session start, plus the working
  tree's diff against HEAD and the session's untracked files.
- **Depends on:** none
- **Deliverables:**
  - `plugin/lib/gates.py`: the reflog classifier and the intersection inside
    `session_work_span`; its docstring, including the cost bound.
  - `tests/test_reflection_gate.py`: `TestTheKnownFalseFire` becomes the silenced case, and new
    cases pin each success line.
  - Every surface describing the span or the merge false fire agrees (sweep: "merge-only",
    "base tree → working tree", "committed work included", "nobody authored").
- **Tests:** `tests/test_reflection_gate.py`, real git repos:
  - pull/fast-forward, `--no-ff` automatic merge, checkout to another branch, and `reset --hard`
    to an upstream commit → empty span, gate silent (red against the pre-fix code);
  - a session commit plus a pull → the commit's paths fire, the pulled paths are absent;
  - a hand-concluded merge → only the resolved path;
  - an unrecognised reflog subject, a missing marker and a failing reflog → today's span;
  - the Critic Stop guard is silent on a pull-only session with an active plan;
  - no reflog read happens when HEAD's tree equals the base tree.
- **Acceptance criteria:** the six success lines above.
- **Done when:**
  1. Tests pass.
  2. The sweep finds no surface contradicting the new span.
  3. Committed.

### Chunk 02: Change record

- **Description:** The fragment for this unit.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `.prawduct/changes/session-authored-span.md`
- **Tests:** none: prose.
- **Acceptance criteria:** the fragment validates; the boundary review names 01 and 02.
- **Type:** cumulative-final
- **Done when:**
  1. Declared suite recorded green.
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
