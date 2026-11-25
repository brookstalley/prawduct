# Issue #1193 — learnings gate: re-blocks every turn on growth from a pull: Design

`status: draft · stage: design · area: stop-hook · added: 2026-11-23 · source: user report
(v3.8.1) · issue: https://github.com/brookstalley/prawduct/issues/1193`

No requirements document precedes this one: the issue's own Expected section is the requirement
set, and it is restated below as R1–R4 so the design has something to be checked against.

## Problem, as the code has it

Two independent defects produce the eight-turn loop.

**D1. The measurement has no authorship filter.** Gate 1c in `cmd_stop`
(`plugin/bin/prawduct-hook`, "Gate 1c: the learnings BUDGET floor") reads the raw
`.session-base-tree` marker (`gates._read_session_base_tree`) and hands it to
`record_lint._check_learnings_budget`. That function compares every rules file's size and shape
against its text at that one tree:

- `grew = now > base` (frozen regime) and `grew = grew or over` (compliant regime);
- the frozen regime's `held` multiset — lines that are "already held" and so are not graded —
  is built from `learnings_files.corpus_texts_at(project_dir, base_tree)` only;
- the regime itself (`compliant_at_base`) is chosen from the base tree only.

A fast-forward pull that lengthens two body lines in an over-cap `core.md` therefore produces
`learnings-over-budget` (the file grew) and `learnings-rule-body` (two body lines not in `held`),
both blocking, though the session never touched the file.

**Correction to the issue's inferred root cause.** The issue infers that the `_rules_changed`
trigger "shares the same unfiltered base". It does not: `_rules_changed` reads
`reflection_span["changed"]`, which is `gates.session_work_span`, which already filters by
`_session_authored_paths`. In the reproduction the gate is reached through the *other* trigger,
`_judgeable_work` (step 4: "makes any judgeable change"). So the trigger is right and the
measurement is wrong: the gate runs because the session did judgeable work, and then charges
it for a file it did not write. The fix belongs in the measurement, not the trigger.

**D2. The remedy cannot reach a clearing state.** The blocker's closing sentence is "pay in this
session, or ask the owner. core.md's cap moves only with an `owner_approved:` date." But
`budget_in_force` takes the *lower* of the ceiling now and the ceiling at the base, so an
`owner_approved:` raise the owner grants mid-session does not count until the next session. No
answer the owner can give clears the block in the session that asked; the only exits are paying
or ending the session against a block. The hook re-blocks at every Stop with the same text
(`.claude/rules/learnings/gates.md`: "a documented 'clears when X' arm is NOT evidence X is
implemented"; "a message naming the caller's NEXT step must ask the gate that will judge that
step").

D1 is the reported trigger and the larger share of real occurrences (any repo whose `core.md` is
over cap and frozen, pulled by any session). D2 survives D1's fix: a session that *did* grow an
over-cap file and whose owner rules "leave it" still loops.

## Requirements (restated from the issue)

- R1. Growth and added lines in a rules file that a pull, merge, reset, branch switch or another
  session's commit brought in are not charged to this session, by the same authorship reading
  the session-span gates use (`_session_authored_paths`).
- R2. Growth this session authored is still charged, including growth it authored *before* a
  pull and growth it authored on top of pulled lines. A fix that stops charging pulled bytes must
  not stop charging the session's own.
- R3. When authorship cannot be told, the gate measures as it does today (against the raw base).
  It may lose a false fire; it may not lose a real one (`_session_authored_paths`'s own
  contract).
- R4. A session whose block the owner has answered can end without the hook repeating the same
  block every turn — and the corpus debt it leaves is still visible afterwards.

## Design

### Part A — an attributed base for the budget check (fixes D1; R1–R3)

**Idea.** Keep one base tree, but widen what counts as "already there before this session's
work" to include every rules-file state the session *received* rather than wrote. Concretely,
alongside the base tree the check takes a list of **imported trees**: the trees of HEAD positions
the session arrived at by importing.

**A1. Where the imported trees come from.** `_session_authored_paths` already walks the HEAD
reflog since `.session-start` and classifies each entry with `_classify_reflog_subject` into
`authored`, `merge-commit` or `imported`. It currently discards the `imported` entries' SHAs.
Extract the walk into one function that returns the classification, and have both readers ask it:

```
gates.session_head_history(project_dir, prawduct_dir, transcript_path=None)
    -> SessionHistory | None
SessionHistory:
    imported: list[str]      # commit SHAs HEAD moved TO by an `imported` entry
                             # (pull/ff-merge/checkout/reset/rebase start|finish)
    merge_theirs: list[str]  # non-first parents of `merge-commit` entries
    dropped: list[str]       # commits _drop_other_sessions_commits dropped as another session's
    why: list[str]           # filled when None is returned
```

`_session_authored_paths` becomes a consumer of the same walk rather than a second walker
(hook-surface.md: "export the ANSWER, not the walker"). `None` has the same meaning it has
today — the reflog could not be read fully back to the session start, or carried a subject the
classifier does not know — and the budget check then runs exactly as now (R3), adding one
`unchecked` line saying authorship could not be told and why.

For a **merge the session concluded** (`commit (merge):`), the imported side is the merge's
non-first parents, not the merge commit: the merge commit's tree contains the session's own
earlier commits, and treating it as imported would launder them (R2).

**A2. How the check uses them.** `_check_learnings_budget` gains one keyword,
`imported_trees: list[str] = ()`. For each rules file:

- *Size floor.* `base` becomes `max(size at base tree, size at each imported tree)`. A file is
  charged for growth only when it is larger now than the largest state it was ever handed.
- *Held lines.* The frozen regime's `held` multiset is the per-line **maximum** count across the
  base corpus and each imported tree's corpus (max, not sum: the same line in the base and in a
  pulled tree is one held line, not two).
- *Regime.* `compliant_at_base` holds only if the base **and** every imported tree are compliant.
  A pull that delivers a non-compliant corpus puts the session in the frozen regime, so it is
  asked not to make the corpus worse, which is what the frozen regime means.
- *Raises.* `budget_in_force` is unchanged. A raise that arrived in a pull is in an imported
  tree, not in the base, and still waits for the next session; that is the existing "growth and
  the raise that would excuse it cannot land together" rule, and the pull does not get to be the
  exception.

Why per-tree floors instead of subtracting pulled bytes from a diff: subtraction needs a
three-way content model of every file, and the floors need two `git cat-file` reads per imported
tree that the check already performs for the base. The cost of the floor is a mild leniency — a
session that deletes 100 bytes and pulls 200 can then add up to 100 without a charge — and that
leniency is in the direction of a session that paid, which the gate does not exist to stop.

**A3. Worked cases (each becomes a test, red first).**

| Case | Today | After |
|---|---|---|
| ff pull lengthens two body lines of over-cap `core.md`; session never edits it (the report) | 2 blocks | none |
| as above, then the session adds one rule to `core.md` | blocks | blocks: `over-budget` (now > pulled size); the new line is not held |
| session adds a rule, commits, then `git pull` merges upstream growth | blocks | blocks on the session's rule only; the merge's second-parent tree supplies the pulled lines |
| pull delivers a raise of `learnings_budgets.core.md` with `owner_approved` | blocks if grown | unchanged: raise counts next session |
| reflog does not reach `.session-start` (fresh worktree, expired reflog) | measures raw | measures raw, plus `unchecked` naming why (R3) |
| another session in the checkout commits growth to `core.md` while this one is idle | blocks | none: its commit is in `dropped` and its tree is an imported tree |
| no `.session-base-tree` marker (the HEAD fallback) | measures vs HEAD | unchanged: nothing to attribute against |

Each case is seeded so that the instrument is seen to fire as well as to stay quiet (core.md: "a
check never seen to return non-zero proves nothing"): rows 2 and 3 are the must-still-block
cases and guard R2.

**A4. The telemetry emitter rides the same base.** The `learning.written` emitter immediately
below Gate 1c builds its "new since base" set from `corpus_texts_at(_budget_base)` alone, so the
same pull records every pulled rule as *written by this session* — persisted and counted, which
is worse than a false block. It takes the same imported trees: a unit hash present in any
imported tree's corpus is not written. One `SessionHistory` read is shared by both, as the
existing comment there requires ("ONE state answers both questions").

**A5. Out of scope for Part A.** The Critic's `critic-begin` record lint calls
`_check_learnings_budget` with the *review's* base tree, which is a branch base, not a session
base; a feature branch that merged its integration branch carries the same class of
misattribution there. It is a different base with a different authorship question (which
commits are the branch's), so it is noted on the issue as a follow-up rather than folded in.
The new keyword defaults to `()`, so that caller is unchanged.

### Part B — a block the owner has answered stops repeating (fixes D2; R4)

**This part amends a binding norm and needs the owner's ruling before it is built** (core.md:
"a governance change cannot supply its own authority"). The gate's code says "No waiver. A
waiver the agent writes for itself is how a cap stops being a cap." Part B is designed so that
nothing the agent writes clears it — but whether a repeated block may ever become a record is
the owner's call. Two options, recommendation first.

**B1 (recommended): block once per finding set, then record.** The first Stop that produces a
given set of learnings-budget findings blocks, as today. The hook stores a fingerprint of that
set — sorted `(check, path, detail-without-byte-counts)` tuples hashed — in a new gitignored,
per-clone marker `.prawduct/.learnings-block-shown` together with the session-start stamp. At a
later Stop of the **same session** whose findings fingerprint identically, and whose turn closes
handed over (`standing_block.disposition` = `YOUR TURN`), the findings are:

- not added to `blockers`;
- printed as one `NOTE:` line ("learnings budget still unpaid — blocked once this session at
  <time>; the debt carries to the next session's briefing");
- recorded with `_record_stop_observation(project_dir, "learnings-budget-standing", ...)`, so
  `stats` counts how often a session ends unpaid.

Any change to the finding set — the file grew again, a new body line, a new file over — is a new
fingerprint and blocks again. The marker is keyed to the `.session-start` stamp, so a
new session ignores a stale one and its first matching Stop blocks again. The debt is also
re-asserted at every session start already: the briefing (`lib/briefing.py`, via
`record_lint.corpus_status`) reports an over-cap `core.md`. Nothing the agent writes
moves the outcome; the only input is whether the hook has already shown this exact block.

Why this does not reopen the hole the "no waiver" comment guards: the debt that ends a session
unpaid is growth the next session inherits in its base, and today that growth is never charged
again either (`now == base` next session). B1 does not create that escape; it stops charging the
same unpayable debt eight times in one session, and adds a record where today there is none.

**B2 (alternative): let an owner-approved raise dated today count in-session for `core.md`.**
This makes the existing remedy text true: the owner answers by writing `owner_approved: <today>`
and the block clears. Rejected as the default because `owner_approved:` is text an agent can
write (the briefing's own comment: "being seen every session is the only check on it"), so this
turns the cap's one owner-only lever into an in-session agent lever — the exact pattern the
`budget_in_force` "lower of now and base" rule was added to stop.

**B3. The remedy text, whichever option is chosen.** The blocker's closing sentence is derived
from what will actually clear it (hook-surface.md: "derive a two-state message from the state").
Under B1: "pay in this session; if the owner rules it stays unpaid, close the turn handed over
and this block is shown once — the cap moves only with `owner_approved:`, from the next session."
The sentence "or ask the owner" alone is removed, because asking does not change the verdict.

## Changes

| File | Change |
|---|---|
| `plugin/lib/gates.py` | Extract `session_head_history` from `_session_authored_paths`; the latter consumes it. |
| `plugin/lib/record_lint.py` | `_check_learnings_budget(..., imported_trees=())`: size floor, held max-union, regime over base+imported. |
| `plugin/bin/prawduct-hook` | Gate 1c reads `session_head_history` once, passes imported trees to the check and the `learning.written` emitter; B1 fingerprint marker and recorded observation; derived remedy sentence. |
| `plugin/lib/core.py` | Add `.prawduct/.learnings-block-shown` to the gitignored per-clone list (B1 only). |
| `tests/test_learnings_cutover_gate.py`, `tests/test_record_lint.py` | The A3 table as tests; B1: blocks once, records twice, re-blocks on a changed set, re-blocks in a new session. |
| gate registry / `docs/governance-telemetry.md` | Register the `learnings-budget-standing` observation id where stop observations are enumerated (B1 only). |

## Verification

- Each A3 row as a test, written to fail on the current code before the change.
- Run the changed Stop hook from the repo (`python3 plugin/bin/prawduct-hook`, hook-surface.md)
  against this repository after a real `git pull --ff-only` that moves `core.md`, before merging
  (gates.md: "editing a runtime that governs the current session: run the changed detection
  against this repo first").
- Grep every caller of `_check_learnings_budget` and `corpus_texts_at` and state, in the change
  record, which pass imported trees and why the others do not.

## Open questions for the owner

1. **Part B: B1, B2, or neither?** B1 is recommended. "Neither" ships Part A alone and keeps the
   loop for session-authored growth the owner declines to have paid.
2. **B1's handed-over condition.** Should the downgrade require a `YOUR TURN` close, or apply to
   any repeat of an identical set? Requiring the close ties it to "has asked"; it also means a
   turn that forgets the close re-blocks, which is the safer failure.
3. **A5 follow-up.** File the Critic-path misattribution as its own item now, or fold it into this
   one once Part A lands?

## Grounding

Read: the issue; `plugin/bin/prawduct-hook` `cmd_stop` Gate 1b/1c and the `learning.written`
emitter; `plugin/lib/record_lint.py` `_check_learnings_budget`, `budget_in_force`,
`_effective_kb`, `corpus_status`; `plugin/lib/gates.py` `session_work_span`,
`_session_authored_paths`, `_classify_reflog_subject`, `_IMPORTED_SUBJECTS`;
`plugin/lib/standing_block.py` (dispositions); `_record_stop_observation`. Not reproduced: the
observed eight-turn session itself; the reproduction is stated from the issue and checked against
the code path above, not re-run.
