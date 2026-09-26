# Issue #895 — Coverage: Base-Advance Transfer Denies Stacked Branch After Parent Merge: Design

`status: draft · stage: design · area: gates · added: 2026-09-26 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/895`

Builds on `documentation/issues/895-requirements.md` (BAT-1–BAT-11, Decisions 1–7). Requirements
already resolved both of the issue's open questions and made every soundness call (superset
relation, byte-check primitive, prune widening, no call-site change); nothing here reopens them.
This document turns those decisions into the concrete edit: where each change lands, what the
returned data shape gains, how the grant message stays true, and how the acceptance criteria map to
test fixtures.

Related: #672 (sibling, `stage:design`, touches the same function for the unrelated condition-2
conflict-resolution root cause; its Decision 5 states "do not touch #895's scope" and this document
keeps that boundary — nothing below touches `transfer_remedy`, `carried_blocking`, subject matching,
or the `Superseded:` clause). #654 (closed — the Stop-gate fallback this item reaches with no
call-site change, per requirements Decision 5 / BAT-6).

## Grounding facts

Beyond what requirements already grounded, re-verified against `develop` (2026-09-26):

- **The three lines this item touches inside `diagnose_base_advance_transfer`
  (`plugin/lib/coverage.py`) are `:602` (the prune), `:653` (condition 1), and the docstring passages
  at `:500-506` (the numbered conditions list) and `:577-579` (the prune's own guarantee claim).**
  Everything else in the function — guard clauses (`:557-568`), the `_survivors` closure and
  condition 2 (`:611-638`), the covered-verdict check and return shape (`:655-678`) — is unchanged
  code that the new logic calls into, not code this item edits.
- **The surplus byte check (BAT-2) is the same primitive `_survivors` already uses for condition 2,
  not a new one.** `_survivors` (`:619-636`) calls `evidence.tree_diff(project_dir, candidate,
  anchor, paths=paths)` and reads its three-way result the same way every check in this function
  does: `None` → set `degraded` and treat as unresolved, non-empty list → the paths differ (deny),
  empty list → byte-identical (pass). The surplus check is one more call in that same shape, over a
  different (per-candidate, not per-anchor) path list — `evidence.tree_diff(project_dir, prior_head,
  base_tree, paths=surplus)` — so it reuses the existing `degraded` nonlocal rather than adding a
  second failure channel.
- **The surplus check cannot be hoisted into `_survivors` itself.** `_survivors` is keyed by one
  `anchor` (either `head_tree` or `base_tree`) and answers "does this candidate agree with the
  required-span endpoint on the `required` files" — the same question for every candidate in its
  list. The surplus set is `judgeable(prior_diff) − required`, which differs per `(prior_base,
  prior_head)` pair and only exists once a specific candidate has already passed the relaxed
  condition 1. It has to run inside the per-candidate loop (`:640-678`), after condition 1, before
  the covered-verdict check.
- **`required` is already computed once and reused as `paths` for condition 2 (`:563-568`); the
  surplus path list is a second, disjoint `sorted()` computed once per candidate that reaches it** —
  cheap, because by that point the candidate has already survived the (widened) prune and the
  relaxed condition 1, so this is not evaluated for candidates that would have been denied anyway.
- **The returned `transfer` dict (`:666-678`) has no field distinguishing a stacked grant from a
  plain one today.** `files` is `paths` (`sorted(required)`, the branch's own diff — unaffected by
  this item) and `advance_files` is the parent-base-advance diff, computed post-grant purely for
  message detail (`:665`). Neither tells a caller whether the grant relied on a non-empty surplus,
  which is exactly what BAT-7's message-accuracy requirement needs at the `gates.py` render site
  (`:2648-2666`). Adding the surplus set to the return value is therefore not purely a BAT-10
  (SHOULD) convenience — it is the input BAT-7 (MUST) needs, so this design ships it as one field
  serving both.
- **`gates.py`'s grant printer (`:2648-2657`) is the only rendering site with a claim to correct.**
  The Stop gate's fallback (`_merge_base_verdict`, `:1584-1692`) returns a `transferred` dict but
  renders no prose of its own (requirements Grounding facts, confirmed unchanged) — BAT-7 is scoped
  to `gates.py`'s PR/cumulative-gate output only.

## Decisions

**1. Condition 1 (`coverage.py:653`) changes from `!=` to a subset test:**
`if not required <= set(coverage_algebra.judgeable_files(prior_diff)): continue`
(BAT-1). The exact-equality case is the special case where the two sides are equal under `<=`, so
every fixture the current code grants keeps granting with no fixture change.

**2. The surplus byte check runs immediately after condition 1 passes, inside the same per-candidate
loop, before the covered-verdict check (BAT-2):**

```python
prior_judgeable = set(coverage_algebra.judgeable_files(prior_diff))
if not required <= prior_judgeable:
    continue
surplus = sorted(prior_judgeable - required)
if surplus:
    differing = evidence.tree_diff(project_dir, prior_head, base_tree, paths=surplus)
    if differing is None:
        degraded = degraded or "a candidate's surplus files could not be diffed"
        continue
    if differing:
        continue  # a surplus file changed between the prior review and the new base — deny
```

When `surplus` is empty (the existing F1 shape), no new git call runs at all — the function's
current-case cost is unchanged. This settles BAT-2 using the primitive Grounding facts identifies,
not a second `judgeable(diff(prior_base, base_tree))` computation (requirements Decision 2, already
ruled out as redundant).

**3. The prune (`coverage.py:602`) widens from subset-only to subset-or-superset (BAT-3):**

```python
changed_judgeable = set(coverage_algebra.judgeable_files(changed))
if not (changed_judgeable <= required or required <= changed_judgeable):
    continue
```

This is the minimal widening that admits the stacked shape's single wide-spanning fact (`changed_judgeable`
⊇ `required`) while keeping every existing admission reason (`changed_judgeable ⊆ required`, e.g. a
composed narrower fact) unchanged.

**4. The returned dict gains one field, `surplus_files` — the same list computed in Decision 2,
carried through to the return (empty list when the grant needed no surplus, i.e. the existing F1
shape):**

```python
return {
    "status": TRANSFER_MATCH,
    "prior_fact_id": reviews[-1].get("id") if reviews else None,
    "prior_reviews": len(reviews),
    "prior_base": prior_base,
    "prior_head": prior_head,
    "files": paths,
    "surplus_files": surplus,
    "advance_files": (...),  # unchanged
}
```

This one field discharges BAT-10 (SHOULD) as a byproduct of computing what BAT-7 (MUST) needs — no
separate "is this a stacked grant" derivation is added anywhere else.

**5. `gates.py`'s grant-path message (`:2648-2657`) branches on `transfer.get("surplus_files")`
rather than rendering "none of them yours" unconditionally (BAT-7):**

```python
surplus = transfer.get("surplus_files") or []
advanced = (
    "the advance's own diff was unreadable, so its size is unknown"
    if advance is None
    else (
        f"the advance touched {len(advance)} judgeable file(s), none of them yours"
        if not surplus
        else (
            f"the advance touched {len(advance)} judgeable file(s); "
            f"{len(surplus)} of them are surplus this transfer's own prior "
            f"review already spans, byte-identical between that review and "
            f"the new base"
        )
    )
)
```

Per requirements Decision 6 the exact wording is a build-time choice — what this design fixes is the
*condition* (branch on `surplus_files`, not always render the same sentence) and that the alternate
sentence states only what was actually checked (byte identity of the surplus, established by
Decision 2), never that the advance "touched none of" anything, which would be false when surplus is
non-empty.

**6. Docstring corrections land in the same commit as the code they describe (BAT-8, and the
function's own top-level conditions list, which is not separately numbered in requirements but is
the same class of stale-invariant-claim this repo's own learnings flag):**

- The numbered conditions list (`:504`) — `1. the two spans' judgeable changed-file sets are
  identical` — becomes: `1. the required span's judgeable changed-file set is a SUBSET of the prior
  span's (equal, in the common case; a stacked branch's prior span may additionally cover surplus
  files, admitted only when 1b holds) / 1b. every surplus file (prior span's judgeable files minus
  the required set) is byte-identical between the prior review's head and the new base`. Condition 2
  and condition 3's descriptions are unchanged (BAT-5, BAT-9).
- The prune's guarantee claim (`:577-579`) — *"it can only deny a transfer the three conditions would
  have granted, never grant one they would not"* — becomes: *"it can still deny a transfer the
  (relaxed) conditions would have granted, but no longer only that: once condition 1 accepts a
  superset (Decision 1 above), a prune that kept only subset-admitted facts would discard the exact
  stacked-branch candidate condition 1 was widened to accept, before condition 1 ever sees it — so
  the prune is widened to admit supersets too (Decision 3). It still cannot GRANT a transfer the
  conditions would not: a candidate it admits still has to pass the relaxed condition 1, the surplus
  byte check, condition 2, and the covered-verdict check."* This states the guarantee the code
  actually holds post-change, per BAT-8's requirement not to leave the old sentence standing.

**7. No change to either gate call site, `gates.py:1584-1692` or `gates.py:2464-2572`/`:2532-2539`**
(requirements Decision 5 / BAT-6, reconfirmed — both call `coverage.diagnose_base_advance_transfer`
and `coverage.classify_transfer` unchanged; the new `surplus_files` key is additive to the returned
dict and neither call site inspects unknown keys).

## What ships

1. **`plugin/lib/coverage.py`** — inside `diagnose_base_advance_transfer`: the prune widened
   (`:602`, Decision 3), condition 1 relaxed (`:653`, Decision 1), the surplus byte check added
   (Decision 2), `surplus_files` added to the returned dict (Decision 4), and the two docstring
   passages corrected (`:504`, `:577-579`, Decision 6). No signature change — same parameters, same
   caller contract.
2. **`plugin/lib/gates.py`** — the PR/cumulative-gate grant printer (`:2648-2657`) branches on
   `transfer.get("surplus_files")` per Decision 5. No other line in `gates.py` changes (Decision 7 /
   BAT-6).
3. **Tests** — `tests/test_cumulative_gate.py`:
   - A new fixture helper, `_stacked_base_repo`, alongside the existing `_advanced_base_repo`
     (`:102-129`): builds `main` → `parent` (one commit) → `child` (one commit off `parent`),
     records a single review fact spanning `main`'s tip → `child`'s head (so `files_changed` covers
     both the parent's and the child's files — the shape requirements' Grounding facts describes as
     currently untested), merges `parent` into `main` byte-identically, then syncs `child`'s base
     (merge, matching `_advance_and_merge`'s existing `merge=True` default) so the new merge-base is
     `main`'s post-merge tip.
   - **Positive control**: `check-cumulative-critic` over the synced `child` branch grants by
     transfer (BAT-1, BAT-2, BAT-3) — covers the requirements doc's first acceptance box.
   - **Same fixture via the Stop gate's fallback**, asserting no code change was needed at that call
     site (BAT-6) — second acceptance box.
   - **Regression**: mutate the parent's file after the merge (a second commit on `main` after the
     child's last review, before the child syncs) — the surplus byte check denies (BAT-2) — third
     acceptance box.
   - **Regression**: an unreviewed judgeable change in the child's own file still denies, unchanged
     from the non-stacked case — fourth acceptance box.
   - **Regression**: every existing `TestBaseAdvanceTransfer` case runs unchanged and stays green —
     fifth acceptance box (Decision 1/3 are strict widenings, never narrowings, so no existing
     fixture's expected outcome changes).
   - **Message check**: the stacked-fixture grant's printed output does not contain the literal
     string `"none of them yours"` (BAT-7) — sixth acceptance box.
   - **Mutation-restore check**: with the prune reverted to its old subset-only form (Decision 3 /
     `:602`) but condition 1 and the surplus check left relaxed, the positive-control fixture must go
     red — proving BAT-3 is load-bearing and not redundant with BAT-1 alone (per the requirements
     doc's own final acceptance box, and this repo's mutation-based-evidence rule for a regression
     test).

## Acceptance mapping

| Requirements acceptance box | Discharged by |
|---|---|
| Positive control grants by transfer | `_stacked_base_repo` + `check-cumulative-critic` test |
| Same fixture via Stop-gate fallback, no call-site change | Second `_stacked_base_repo` test, no edit to `gates.py:1584-1692` |
| Surplus file differs → still denies | Mutated-parent-file regression test |
| Unreviewed child change → still denies | Existing-shape regression test, unchanged assertion |
| Every existing `TestBaseAdvanceTransfer` case passes unchanged | Full suite run, no expected-outcome edits |
| Grant message omits "none of them yours" for the stacked case | Message-content assertion on the stacked fixture's printed output |
| Reverting the prune alone turns the positive control red | Mutation-restore test isolating Decision 3 |

## Scope-out (carried from requirements, unchanged)

Condition 2's conflict-resolution tolerance, denial-message wording (`transfer_remedy`), any change
to `gates.py:1584-1692` or its call site, `carried_blocking`/`finding_subject`/subject
matching/`Superseded:`, a dedicated multi-level-stack fixture, and any weakening of the byte-identity
bar (COV-3M8Q) — all #672's territory or explicitly out per requirements BAT-9/BAT-11 and its own
Scope-out section. This design adds nothing to that list and removes nothing from it.

## Evidence / references

- `plugin/lib/coverage.py:484-680` (`diagnose_base_advance_transfer`) — `:500-506` (conditions list),
  `:557-568` (guard clauses, `required`/`paths`), `:570-609` (the prune), `:611-638` (`_survivors`,
  condition 2), `:640-678` (the per-candidate loop, condition 1, covered-verdict check, return
  shape).
- `plugin/lib/evidence.py:1011-1036` (`tree_diff` — the `paths=` pathspec-limited primitive both
  condition 2 and the new surplus check share).
- `plugin/lib/gates.py:2648-2657` (the grant-path printer carrying the message this item corrects).
- `documentation/issues/895-requirements.md` — BAT-1–BAT-11, Decisions 1–7, the Grounding facts this
  document extends rather than repeats, and the acceptance/scope-out lists this document maps
  against.
- `documentation/issues/672-design.md` — the sibling design sharing this function; its Decision 5
  ("do not touch #895's scope") is the boundary this document keeps on the other side.
- `tests/test_cumulative_gate.py:90-129` (`_advance_and_merge`, `_advanced_base_repo`) — the existing
  fixture family this item's `_stacked_base_repo` sits alongside.
- GitHub issue #895 — problem statement and both open requirements questions (already answered in
  the requirements doc this design builds on).
