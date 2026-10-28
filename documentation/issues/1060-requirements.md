# Issue #1060 — critic: a blocking finding a spanning review cleared has no record: Requirements

`status: draft · stage: requirements · area: critic · added: 2026-10-27 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/1060`

Related: #1057 (verify-resolutions in a second clone finds no prior review — shares the anchor
question), #672 (coverage composes by tree, gates key on identity), #1050 (the evidence-transport
build whose Wave 3 review found this).

## Problem

A BLOCKING finding has exactly one way to become "resolved" in the record: a `resolution` fact,
written by a `verify-resolutions` pass that anchors on the finding's own review. The gate side has a
second, independent way: `coverage_algebra` accepts a later *spanning* review (a `cumulative`) as a
clean evidence path around the superseded fact. When a blocker is fixed and then cleared by a
spanning review, the gate is satisfied but the record is not: no resolution fact exists, the
disposition writer refuses to supply one, and `render-dispositions` reports the finding
`undispositioned` forever. The census contradicts the gate, and the only remaining levers are
wrong: an owner-ruled `--accept` (says "won't fix" about a fixed defect) or a ceremonial extra
verify round.

## Grounding facts

Checked against `develop`/`main` at `eea2be2` (2026-10-27).

- `dispositions.record` refuses `--fixed` on a BLOCKING finding outright, on the reasoning that a
  blocker "clears only through a resolution fact" (`plugin/lib/dispositions.py`, the
  `severity == "blocking" and action == FIXED` branch). It permits `--accept` only with
  `--owner-ruling`.
- `finding_state` (`dispositions.py`) lets a resolution outrank any disposition; with neither, the
  state is `undispositioned`. There is no state for "cleared by a later review".
- Resolution facts are written against the single anchor a verify pass reviews. The dispatcher
  finds the anchor through the per-worktree `.critic-findings.json` pointer
  (`critic_consolidate.py` ~L790–800: the newest review fact); `coverage_algebra._verify_anchor_id`
  documents the same anchor as a "faithful proxy, not the same value" and says a blocker on any
  other fact on the path "is superseded, and only a review spanning the whole interval can supply a
  clean path around it."
- `coverage_algebra.compose` finds a path over clean edges first, then over all edges, and settles
  by checking only the nodes *on the chosen path* (`_settle`). A spanning review that jumps over
  the fact carrying R-1 therefore yields `covered`; R-1's fact is simply off the path.
- So the two sides use different identities for the same fact: the gate reasons by tree/path, the
  record by `(review_id, fid)`. This is the #672 split showing up in the census.

## Requirements

1. **A spanning-cleared blocker is recordable.** There is a supported command that records, for a
   BLOCKING finding `(review_id, fid)`, that a named later review cleared it. The record is a fact
   in the evidence store (append-only, like every disposition), not an edit.
2. **The claim is checked, not asserted.** The command refuses unless: (a) the later review exists
   and is a review fact in the store; (b) that review's span *covers* the finding's review — the
   finding's review fact lies on a composed evidence path that the later review is the clean edge
   of (the same predicate the coverage algebra uses, not a reimplementation); (c) the later review
   itself carries no unresolved BLOCKING finding on that span. Each refusal names which test failed.
   This is the property that stops it laundering a fix no reviewer saw: a free-text "verified by"
   would be an accept by another name.
3. **The census reads it as a resolution, distinctly labelled.** `finding_state` reports the
   finding as cleared (a state distinct from `fixed`, which says an anchored verify pass looked, and
   from `fixed-unreviewed`, which says no reviewer looked), naming the clearing review id.
   `render-dispositions` prints no `undispositioned` for such a finding; the summary tally counts it
   in its own bucket, so a census total cannot claim a verify pass that did not run.
4. **No gate moves.** Recording this fact changes no verdict: the coverage algebra already decides
   the span is covered, and the new fact's kind is outside the verdict's input kinds (the
   `VERDICT_INPUT_KINDS` filter), pinned by a regression test in the style of the existing
   "disposition can never weaken a gate" test.
5. **Discoverable at the point of need.** When `render-dispositions` or the disposition writer meets
   a BLOCKING `undispositioned` finding whose review is spanned by a later clean review, the message
   names the command and the candidate review id, so the operator does not reach for `--accept`.
   Because requirement 3 depends on the same predicate, this can be an automatic candidate lookup,
   not a second implementation.
6. **Consistent with the anchor question (#1057).** Whichever mechanism #1057 settles for naming a
   prior review as a verify anchor, this feature's span check uses the same lookup, so the two
   cannot disagree about which review is "the" prior one in a second clone.
7. **The instance gets its record.** Review `rev-20261025T182810Z-3266301c` finding R-1 (fixed in
   `d4cd1321`, cleared by cumulative `rev-20261025T190407Z-e86edd5b` on
   `feature/1052-evidence-transport`) is dispositioned through the new path. If that branch's store
   is not reachable from the building clone, a fixture reproducing its shape (blocker fixed, then
   cleared by a cumulative that skips the fact) stands in and the gap is stated.

## Acceptance criteria

- On a fixture store with R-1 blocking in review A, a fix, and a clean cumulative B spanning A,
  `render-dispositions` shows R-1 `undispositioned` before the command and not after; both halves
  are asserted.
- The command refuses (non-zero, reason names the failed test) when: B does not exist; B does not
  span A; B has its own unresolved blocker; the finding is not BLOCKING (the existing `--fixed`/
  `--accept` paths are the right ones there).
- `check-cumulative-critic` and the coverage verdict are byte-identical before and after recording.
- A re-run with the same arguments is reported `unchanged`, not appended again.
- The census summary has a separate count for spanning-cleared findings; `fixed` is unchanged for
  anchored verify passes.

## Non-goals

- Not changing how the coverage algebra composes paths (that is #672).
- Not making a spanning review write resolution facts for every finding it clears automatically.
  That is the alternative design (see Open questions) and is larger.
- Not touching non-blocking findings, whose `--fixed`/`--accept` routes already work.

## Open questions for design

1. **Explicit command vs. automatic derivation.** The issue proposes `disposition <rev> <fid>
   --verified-by <later-review-id>`. An alternative is to derive the state at render time:
   "a blocking finding is cleared when compose says its span is covered by a clean path that
   excludes its fact", with no new fact at all. That follows the learnings rule *observable beats
   stored*, and removes the write path that can be forgotten. Cost: the census becomes a function
   of the tree/branch it is rendered on, where today it is a function of the store alone. Design
   should choose; this document is written so either satisfies requirements 1–5 (1 reads "supported
   way", 2 becomes the derivation's predicate).
2. **Anchoring on a named prior review** (the issue's second option,
   `critic-begin --mode verify-resolutions --anchor <review-id>`) fixes the *cause* for the case
   where a verify pass is still possible, but not the case here: the cumulative has already run
   and was accepted by the gate. It belongs with #1057; whether to ship it in the same change is a
   design call.
3. **Which resolution disposition string.** A `resolution` fact with a new disposition value would
   be read by `coverage_algebra._RESOLVING_DISPOSITIONS`, so reusing that kind risks moving a gate
   (requirement 4). A new fact kind or a `disposition` action avoids it; design should confirm
   with the algebra's filter before choosing.
