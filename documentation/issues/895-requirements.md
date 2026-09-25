# Issue #895 — Coverage: Base-Advance Transfer Denies Stacked Branch After Parent Merge: Requirements

`status: draft · stage: requirements · area: gates · added: 2026-09-25 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/895`

Related: #654 (closed — gave the Stop gate's merge-base fallback the same base-advance-transfer
attempt the PR/cumulative gate already had, by routing both through the one shared
`coverage.diagnose_base_advance_transfer` function; grounds this document's answer to the issue's
own second open question). #672 (sibling, `stage:design` as of 2026-09-24, touches the *same*
function for a *different* root cause — Half 2's conflict-resolution tolerance in condition 2 — and
its design doc explicitly states Decision 5, "Do not touch #895's scope," and claims only the
"denial-message wording" sub-item this issue's own Scope-out bounced to it. This document keeps
that boundary: it does not touch `transfer_remedy`'s denial branches, `carried_blocking`, subject
matching, or `review-cycle.md`'s `Superseded:` clause). #334, #536, #669 (672's own siblings; not
directly relevant here).

## Problem

`coverage.diagnose_base_advance_transfer` lets a review taken before a base sync still vouch for the
span the sync creates, when the branch's own diff did not move a byte. On a stacked branch (child
branched from a parent branch, not yet merged), every prior review of the child spans from the *old*
base — the parent's then-current tip — so the prior span's judgeable file set is the parent's files
**plus** the child's own files. Once the parent merges and the child syncs its base, the merge-base
becomes the parent's final tree and the *required* span shrinks to the child's own files alone: every
prior span is now a strict superset of what condition 1 asks it to equal, so the transfer denies and
the operator pays a full cumulative re-review of work already reviewed — the exact cost the transfer
exists to remove, and the common case for the stacked-PR workflow this repo's own `/prawduct:pr`
convention encourages.

## Grounding facts

Re-verified against the current tree (`develop`, 2026-09-25):

- **The three-condition contract is exactly as the issue describes.** `diagnose_base_advance_transfer`
  (`plugin/lib/coverage.py:484-680`): condition 1 is `set(coverage_algebra.judgeable_files(prior_diff))
  != required` → deny (`:653-654`); condition 2 is the pathspec-limited blob equality the `_survivors`
  closure computes for `required` files only, on both the head side and the base side (`:619-638`);
  condition 3 (suite currency) is the caller's, not this function's (docstring `:500-502`,
  `gates.suite_vouches_for_tree`).

- **A second, earlier site excludes every stacked candidate before condition 1 is ever reached, and
  the issue's own body does not name it.** The candidate-selection loop that builds `prior_bases`/
  `prior_heads` (`:592-609`) prunes any fact whose own `files_changed` is not a subset of `required`
  (`:602-603`: `if not set(coverage_algebra.judgeable_files(changed)) <= required: continue`). In the
  stacked shape, a single review fact recording the whole parent-tip→child-head span has
  `files_changed` equal to *parent's files ∪ child's files* — a superset of `required`, not a subset —
  so this prune discards the candidate outright. **Relaxing condition 1 (`:653-654`) alone is a no-op
  for this issue's own repro**: the candidate never survives long enough to reach that line. Any fix
  must touch both sites, or the acceptance fixture will still deny.

- **The prune's own docstring states an invariant this item's fix falsifies, and the invariant is
  currently true only because condition 1 is exact-equality.** `:576-591`: "The prune is a COST
  bound, not one of the conditions — it can only deny a transfer the three conditions would have
  granted, never grant one they would not." Once condition 1 accepts supersets, a candidate the prune
  discards *can* be one the relaxed three conditions would have granted (this issue's own case) — the
  comment must be corrected in the same change, not left describing a guarantee the code no longer
  keeps (a stale invariant claim is exactly the failure class `documentation/issues/` requirements
  docs in this repo are written to catch before it ships).

- **The "prior span must itself be covered" check already vouches for the surplus files — no new
  evidence-store query is needed.** `:655-660`: after condition 1 (relaxed or not), the winning
  candidate's own span (`prior_base` → `prior_head`) must independently verdict `"covered"` via the
  same `coverage_verdict` composition every other gate trusts. That composition is tree-keyed, not
  fact-keyed (`documentation/issues/672-design.md` Grounding facts, first bullet, re-confirmed here):
  a `"covered"` verdict over the whole prior span holds whether it comes from one fact that reviewed
  parent's-files-and-child's-files together, or from two composed facts (the parent's own review,
  chained to the child's own narrower review) — either way, every judgeable file in that span,
  including what becomes surplus after the sync, already has zero unresolved blocking findings on its
  path. This directly answers the issue's first open requirements question ("must the surplus also be
  covered by facts in the shared store?") — yes, and the existing check already does it; nothing new
  is needed.

- **The relaxed check the issue's own candidate shape describes reduces to a single per-file byte
  comparison, with no need to independently verify "surplus == advance's files."** The issue's
  proposed shape asks for two things: (a) the surplus is exactly what the base advance brought in,
  and (b) each surplus file is byte-identical between the prior span's head and the new base. (b)
  alone is suffient and is already the safer primitive: for any file `f` in `surplus = judgeable(prior_diff)
  − required`, checking `blob(prior_head, f) == blob(base_tree, f)` (the new base) directly answers
  "does this file still hold the exact content the prior review saw?" regardless of which commit
  touched it or when. Requiring surplus to additionally equal `judgeable(diff(prior_base, base_tree))`
  (the set-membership half of (a)) adds a constraint the byte check does not need and that a second,
  unrelated base-advance touching the same file set could trip for no soundness reason. Framing
  condition 1's relaxed form directly as the byte check, not as "surplus must equal the advance's
  files," is simpler and at least as strict.

- **`advance_files` — the diff the surplus check needs — is already computed today, just only for
  post-grant message detail.** `:665-677`: on a grant, `advance = evidence.tree_diff(project_dir,
  prior_base, base_tree)` is the full tree diff between the winning candidate's base and the new base,
  already restricted to judgeable files for the returned `advance_files` field. This is the same diff
  the relaxed surplus check needs; today it runs *after* the match decision, purely for reporting.

- **Both call sites share this one function, so a fix here reaches both without any call-site
  change — this directly answers the issue's second open requirements question.** The Stop gate's
  fallback, `_merge_base_verdict` (`gates.py:1584-1692`, added by #654), calls
  `coverage.diagnose_base_advance_transfer` at `:1649-1651` and reads its status through
  `coverage.classify_transfer` at `:1655` — the identical function and the identical classification
  the PR/cumulative gate uses at `check_cumulative_critic` → `_branch_coverage` (`gates.py:2532-2539`,
  `:2540`). Relaxing condition 1 (and its upstream prune) inside `coverage.py` changes what both
  callers see; #654's own docstring (`gates.py:1607-1621`) confirms the substitution was designed to
  be sound specifically because the merge-base span becomes "exactly the shape
  `coverage.diagnose_base_advance_transfer` was written for" once a base syncs. No change to
  `gates.py`'s two call sites is required for the transfer itself to reach both gates.

- **One grant-message sentence becomes false the moment a transfer can carry a nonzero surplus.**
  `gates.py:2648-2655` (the PR/cumulative gate's grant rendering): `advanced = f"the advance touched
  {len(advance)} judgeable file(s), none of them yours"`. In the relaxed/stacked case, the advance's
  judgeable files *do* include the surplus this transfer relied on — they are not disjoint from what
  the prior review "owned," even though they remain disjoint from the branch's own *required* diff
  today (condition 2, unchanged, still denies if the advance touched a `required` file). "None of
  them yours" is accurate only when surplus is empty; it must not render unchanged when surplus is
  non-empty, per this repo's own standing rule that operator-facing prose asserting a system property
  must be checked against what the system actually does. The Stop gate's own grant path
  (`_merge_base_verdict`, `:1675-1691`) carries no equivalent claim to fix — it returns a `transferred`
  dict with `advance_files` but renders no prose of its own; only `gates.py`'s PR/cumulative-gate
  printer (`:2648-2666`) needs the wording checked.

- **No existing fixture builds the stacked shape at all.** `tests/test_cumulative_gate.py`'s
  `TestBaseAdvanceTransfer` (`:498-660`+) is built entirely on `_advanced_base_repo` (`:103-131`),
  whose own docstring names it "the F1 shape: a feature branch reviewed at its tip, then the base
  advances into it touching nothing the branch changed" — the advance always lands on a file
  (`upstream.py`) the branch's own prior review never touched, so `judgeable(prior_diff) == required`
  holds in every existing fixture and the superset case this issue is about has no test at all, grant
  or deny. This is the gap that let the defect ship unnoticed until it cost a real round (issue
  Evidence: round 5, ~10 min, on `feature/653-per-tree-test-evidence`).

## Decisions

**1. Condition 1 is relaxed from set equality to `required ⊆ judgeable(prior_diff)`** (superset-or-
equal), never the reverse direction. Plain equality is the special case where surplus is empty, so
every transfer the current exact-match code grants keeps granting.

**2. Soundness of a non-empty surplus rests on a direct per-file byte check —
`blob(prior_head, f) == blob(base_tree, f)` for every `f` in `judgeable(prior_diff) − required` —
not on an independent check that the surplus set equals `judgeable(diff(prior_base, base_tree))`.**
The byte check is the primitive the issue's own soundness argument reduces to (Grounding facts); it
is simpler, strictly sufficient, and does not need the second (redundant) diff computed before the
decision — `advance_files` stays a post-grant, message-only computation exactly as it is today.

**3. No new query against the shared evidence store for "the parent's own reviews" is added.** The
existing `prior_verdict.get("status") == "covered"` check (`:658-660`), unchanged, already vouches for
every judgeable file in the prior span — surplus included — however that coverage was composed. This
settles the issue's first open requirements question without new code.

**4. The candidate-selection prune (`:602-603`) is relaxed in the same change, to admit a candidate
whose `files_changed` is a superset of `required`** (not only a subset, as today). It stays a cost
bound, not a fourth condition: a candidate it now admits still has to pass the (relaxed) condition 1,
condition 2, and the covered-verdict check to grant. Its docstring's "never grant one [the conditions]
would not" sentence is corrected in the same commit to state the new, narrower guarantee once the
subset-only bound is gone.

**5. No change to either gate's call site is needed for the transfer to reach both gates.** Both
`_merge_base_verdict` (Stop gate fallback, shipped by #654) and `_branch_coverage`/
`check_cumulative_critic` (PR/cumulative gate) call `coverage.diagnose_base_advance_transfer` and
`coverage.classify_transfer` directly; the relaxation lives entirely inside `coverage.py`. This
settles the issue's second open requirements question: #654's shape already generalizes, and this
item does not reopen `gates.py:1584-1692`.

**6. The PR/cumulative gate's grant-path sentence "none of them yours" (`gates.py:2654`) must be
made conditionally accurate: it may keep its current wording only when surplus is empty; when
surplus is non-empty, it must say something true instead.** Exact wording is left to the build step
(consistent with how `documentation/issues/797-requirements.md` leaves advisory prose wording to
design/build while fixing its required content) — the requirement is truth, not a specific sentence.

**7. Scope boundary with #672 is preserved exactly as that document's own Decision 5 states it:**
this item changes only `diagnose_base_advance_transfer`'s condition 1, its upstream prune, and the
one grant-path sentence in `gates.py`'s PR/cumulative-gate printer. It does not touch condition 2's
conflict-resolution tolerance, `transfer_remedy`'s denial branches, `carried_blocking`, subject
matching, or `review-cycle.md`'s `Superseded:` clause.

## Requirements

MUST unless marked SHOULD.

- **BAT-1** `diagnose_base_advance_transfer`'s condition 1 grants when
  `required ⊆ judgeable_files(prior_diff)`, not only on exact equality (Decision 1).
- **BAT-2** For every file in the surplus (`judgeable_files(prior_diff) − required`), the transfer
  grants only if that file's blob at `prior_head` equals its blob at the new `base_tree`; any surplus
  file that differs denies the transfer, the same fail-closed direction every other condition here
  takes (Decision 2).
- **BAT-3** The candidate-selection prune admits a fact whose `files_changed` is a superset of
  `required`, not only a subset or exact match, so a single review fact spanning the whole stacked
  prior interval is considered a candidate at all (Decision 4).
- **BAT-4** No new read of the evidence store beyond what `diagnose_base_advance_transfer` already
  performs is added to vouch for the surplus; the existing prior-span `covered` verdict check is the
  sole authority for it (Decision 3).
- **BAT-5** Condition 2's existing per-`required`-file byte checks (`blob(head,f)==blob(prior_head,f)`
  and `blob(base,f)==blob(prior_base,f)` for `f` in `required`) are unchanged — an advance that
  touches a file the branch's own required diff also touches still denies, exactly as today.
- **BAT-6** Neither `_merge_base_verdict` (`gates.py:1584-1692`) nor `_branch_coverage`/
  `check_cumulative_critic` (`gates.py:2464-2572`) requires any code change for the relaxed transfer
  to reach it; both continue to call `coverage.diagnose_base_advance_transfer` and
  `coverage.classify_transfer` exactly as they do today (Decision 5).
- **BAT-7** The PR/cumulative gate's grant message never states or implies that the base advance
  touched none of the branch's own reviewed history when the grant relied on a non-empty surplus; the
  existing "none of them yours" sentence renders only when surplus is empty (Decision 6).
- **BAT-8** The prune's docstring (`coverage.py:576-591`) is corrected to state the guarantee it
  actually holds once the subset-only bound is relaxed (Decision 4) — it must not continue asserting
  it "can only deny a transfer the three conditions would have granted."
- **BAT-9** This change makes no edit to `transfer_remedy`, `carried_blocking`, `finding_subject`, or
  `review-cycle.md`'s `Superseded:` clause (Decision 7; #672's claimed territory).
- **BAT-10 (SHOULD)** The returned `transfer` dict distinguishes the surplus files from `required`
  (e.g., a new key, or deriving it from the existing `files`/`advance_files` pair) so a caller or a
  future audit can tell a plain transfer from a stacked one without re-diffing — useful for
  `record_transfer_grant`'s ledger, not required for soundness.
- **BAT-11 (SHOULD)** The mechanism generalizes to more than one merged ancestor between reviews
  (a stack more than one level deep) under the same per-file byte check, with no special-casing of
  "exactly one parent" — this item does not add a dedicated fixture for the multi-level case, but the
  implementation must not assume a single parent.

## Acceptance

- [ ] **Positive control (the issue's own repro):** a child branch reviewed from the old base (a
      single review fact spanning parent-tip-then→child-head, `files_changed` = parent's files ∪
      child's files), the parent branch merges to develop byte-identically, and the child syncs its
      base back. `check-cumulative-critic` grants by transfer (BAT-1, BAT-2, BAT-3).
- [ ] **Same fixture, via the Stop gate's fallback path**, with no code change at that call site
      (BAT-6).
- [ ] **Regression:** a surplus file that differs between the prior head and the new base — e.g. the
      parent's PR picked up one more commit after the child's last review — still denies (BAT-2).
- [ ] **Regression:** an unreviewed judgeable change in the child's own files still denies, exactly as
      the non-stacked case does today.
- [ ] **Regression:** every existing `TestBaseAdvanceTransfer` case in `tests/test_cumulative_gate.py`
      (the non-stacked F1 shape, the composed-facts case, the rebase case, and every existing denial
      case) still passes unchanged (BAT-1's superset relation is a strict widening, never a
      narrowing).
- [ ] **Message check:** the PR/cumulative gate's grant output for the stacked fixture does not print
      "none of them yours" (BAT-7).
- [ ] A mutation restoring the prune's old subset-only bound turns the positive-control fixture red
      (proves BAT-3 is load-bearing, not redundant with BAT-1).

## Scope-out (this item)

- **Condition 2's conflict-resolution tolerance** (a merge conflict resolved in a non-judgeable file)
  — #672 Half 2, already in that item's design as of 2026-09-24.
- **Denial-message wording** (`transfer_remedy`'s branches, the `absent`/no-degraded-reason case) —
  explicitly claimed by `documentation/issues/672-design.md` Decision 4 / What ships #4, per this
  issue's own original Scope-out line.
- **Any change to `gates.py:1584-1692` (`_merge_base_verdict`) or its call site** — #654 already
  shipped the call; Decision 5 establishes no further change is needed there.
- **`carried_blocking`, `finding_subject`, subject-matching, or `review-cycle.md`'s `Superseded:`
  clause** — #672 Half 1's territory, unrelated root cause.
- **Multi-level stacks as a dedicated, separately-fixtured scenario** — BAT-11 states the
  implementation must not special-case a single parent, but a second fixture for a two-level stack is
  not required to close this item.
- **Weakening the byte-identity bar (COV-3M8Q) for either `required` or surplus files** — this item
  extends *which files* get compared, never *how* they are compared; content-equivalence
  normalization stays banned exactly as `:508-517`'s soundness-boundary paragraph states.

## Evidence / references

- `plugin/lib/coverage.py:455-482` (`TRANSFER_MATCH`, `classify_transfer`) — the one reading every
  gate site shares.
- `plugin/lib/coverage.py:484-680` (`diagnose_base_advance_transfer`) — the function this item
  changes: guard clauses and `required` computation (`:557-568`), the candidate-selection prune
  (`:570-609`), condition 2 / `_survivors` (`:611-638`), the pairwise condition-1 + covered-verdict
  loop (`:640-678`), the docstring's soundness-boundary paragraph (`:508-517`) and its
  `advance_files` note (`:543-547`).
- `plugin/lib/gates.py:1584-1692` (`_merge_base_verdict`) — the Stop gate's fallback, added by #654,
  sharing this function unchanged (BAT-6).
- `plugin/lib/gates.py:2464-2572` (`_branch_coverage`, called from `check_cumulative_critic`) — the
  PR/cumulative gate's call site (`:2532-2539`), unchanged (BAT-6).
- `plugin/lib/gates.py:2648-2666` — the grant-path printer carrying the "none of them yours" sentence
  this item must correct (BAT-7).
- `plugin/lib/gates.py:1245-1265`+ (`record_transfer_grant`) — the yield ledger BAT-10 (SHOULD) would
  extend.
- `plugin/lib/coverage_algebra.py:113-116` (`judgeable_files`), `:79`-ish (`is_judgeable_path`) — the
  predicate every set in this document is built from.
- `tests/test_cumulative_gate.py:103-131` (`_advanced_base_repo`), `:498-660`+
  (`TestBaseAdvanceTransfer`) — the existing fixture family (the F1, non-stacked shape only) this
  item's acceptance criteria add a stacked sibling to, without touching any existing case.
- `documentation/issues/672-design.md` — the sibling design (`stage:design`, 2026-09-24) sharing this
  function; its Decision 5 ("Do not touch #895's scope") and Decision 4 / What-ships-#4 (claiming the
  denial-message wording) are the boundary this document keeps on the other side.
- GitHub issue #654 (closed 2026-08-13, `closed-by` completing the Stop-gate fallback) — confirms
  Decision 5's "no call-site change needed" is current, not stale.
- GitHub issue #895 (2026-09-23) — problem statement, proposed change, both open requirements
  questions (answered in Grounding facts / Decisions 3 and 5), and acceptance criteria this document
  grounds and extends.
