# Issue #1058 — governance: stats and contribute double-count ingested reviews: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-11-08 · source: Wave 3 build
2026-10-25 · issue: https://github.com/brookstalley/prawduct/issues/1058`

Related: #1115 (roll review stats up across clones; this item is its precondition and the two must
agree on one provenance rule), #1050 / #1052 (evidence transport), #1061 (transport polish).

## Problem

Since evidence transport, `review` facts ingested from `refs/notes/prawduct` sit in every syncing
clone's store beside the facts that clone wrote itself. `stats` (`stats.aggregate` over
`evidence.read_facts`) and `contribute` (`contribution.weekly_reports`, which calls the same
`stats.aggregate`) count every `review` fact in the store with no regard to where it was written.
Two clones of one product that both opt into the stats upload therefore send the same review twice,
and a clone that has only ever ingested reports reviews it never ran. `plugin/docs/governance-telemetry.md`
documents the double count as known.

## Findings that change the issue's premise

1. **The issue says the ingested envelope "keeps its original `actor.worktree`/`actor.session`".
   It does not.** `evidence_notes.sent_envelope` cuts `actor.worktree` to its basename (or
   `.claude/worktrees/<name>`) and drops `actor.session` before a fact travels, deliberately, so a
   reviewing machine's path is not published. So "count only facts whose `actor.worktree` is under
   this clone" has no usable signal on the very facts it must exclude: an ingested worktree is a
   bare name that is under no clone path. It also fails the other way if a native fact ever carries
   a relative worktree.
2. **The collector cannot dedupe by fact id.** The `contribute` bundle is one aggregate report per
   (week, version bucket) built by `contribution.build_report` from counts and shares; it carries no
   fact ids, by design (small-count suppression and banding exist because a count near a
   cardinality of one is an identifier). Dedupe at the collector would require adding ids to the
   payload, which the anonymity design argues against. So the fix must be local, before the
   aggregate is built.
3. **`stats` is also a local-decision tool, not only an upload feed.** Whether an ingested review
   belongs in a clone's own `stats` is a product question (#1115 wants it to, as a deliberate
   rollup), so the exclusion must be a reader-side choice on one shared derivation, not a
   write-side deletion.

## Goals

- G1. A store holding one native and one ingested review reports one review in `stats` and sends
  one in `contribute` (the issue's acceptance, kept).
- G2. "Native to this clone" is decided by one predicate with one owner, used by every aggregate
  that counts store facts (`stats`, `contribute`, `aggregate-stats`, and any later rollup).
- G3. The predicate rests on a signal that survives the reductions `sent_envelope` applies and that
  cannot be forged by a path coincidence.

## Non-goals

- Deduplicating at the collector, or adding fact ids to the contribute bundle (finding 2).
- Rolling stats up across clones on purpose (#1115). The predicate here must make that a one-flag
  change, not be designed around it.
- Dispositions, resolutions and other kinds: see R4 for which kinds the count rule covers.

## Requirements

**Provenance**

- R1. A fact written by `evidence.append_envelope` on behalf of a live session in this clone is
  *native*. A fact appended by `evidence_notes.ingest` is *ingested*. The distinction is recorded
  where ingest writes it, not inferred later from path shape.
- R2. The marker is outside `(kind, id)`, `ts` and `body` (the fields dedupe and every verdict
  read), so that adding it changes no dedupe, no coverage verdict and no existing fact's meaning.
  Candidate home: an `actor` flag set only by `ingest` (`actor.ingested: true`), which `sent_envelope`
  must also never forward as native (a re-sent ingested fact stays ingested at the next reader).
- R3. Facts already in stores before the marker exists carry none. They are classified by the one
  fallback that is true of them: a fact whose `actor.worktree` is not an absolute path (the shape
  `sent_envelope` produces) is treated as ingested; anything else as native. The fallback is
  stated once, in the predicate, and named as a migration aid with a removal condition (a release
  after which no store holds un-marked ingested facts).

**Counting**

- R4. Over-counting is a property of kinds that describe an activity: `review` (the issue's
  subject) is excluded when ingested. `resolution` and `test-run` facts are also in
  `evidence.TRANSPORTED_KINDS` or in `stats.aggregate` and are affected the same way; the
  predicate is applied to every kind the aggregate counts from, not to `review` alone, and a
  falsifying query (R9) proves that no counted kind was missed. `session-start` and
  `guard-refusal` are never transported, so they are native by construction.
- R5. `stats.aggregate` takes an explicit provenance selector with default `native`. `all` exists
  for #1115's rollup and for diagnosis; no caller passes it in this change.
- R6. Finding outcomes (`stats.finding_outcome`) join dispositions and resolutions to reviews by
  review id. A native review's outcome must still resolve when its resolution was ingested from
  another clone (the join reads the whole store; only the *count* is native-scoped). A test pins
  this, since scoping the join by mistake would silently lower every actionable rate.
- R7. Human and JSON `stats` output states the scope in one line (`counting this clone's own
  facts; N ingested excluded`) so a reader who expects the rollup is not misled by a smaller
  number. The count of excluded facts is a number, not a boolean.

**Documentation and cascade**

- R8. `plugin/docs/governance-telemetry.md` loses the "documented double count" statement and
  instead defines native vs ingested once; `evidence_notes.py`'s module docstring and
  `sent_envelope` docstring, and the `stats` and `contribute` skill/CLI usage text, agree with it.
  Search for the *claim* (double count, count twice, ingested reviews), not the edited tokens.

## Verification (stated now so design cannot soften it)

- R9. Falsifying checks, each seen to fail before the fix:
  - one native + one ingested review: `stats` total is 1, `contribute` preview reports 1;
  - an un-marked legacy ingested fact (basename worktree) is excluded by the R3 fallback;
  - a store of only ingested reviews reports 0 reviews and no weekly report is generated for a
    window holding no native activity (`weekly_reports` skips a window with no reviews or sessions);
  - two clones of one fixture repo, both syncing, both previewing: the two previews' review counts
    sum to the number of reviews actually run;
  - a query over `stats.aggregate` for every `kind` it branches on, asserting each is passed
    through the native predicate (the coverage claim in R4).

## Open questions

1. **Marker vs fallback only.** Is a write-side marker (R1/R2) worth a schema touch, or is the R3
   shape fallback enough on its own? The fallback is one line but rests on `sent_envelope`'s
   current spelling, so a change there would silently reclassify every fact. Recommendation: marker
   as the truth, fallback only for legacy; confirm.
2. **A clone that has only ingested.** It now contributes nothing. Is that right, or should a
   reviewer's first clone count facts that predate the notes (a clone made after the reviewer's
   machine was lost)? Recommendation: nothing; the original clone's upload is the record.
3. **Facts a clone wrote natively that a later fetch would re-ingest** (store deleted, notes
   remain): they return as ingested and stop counting. Acceptable loss, or a reason to key
   provenance on `actor.build`/machine instead? Recommendation: accept; name it in the docs.
4. **Sizing.** Likely effort S for R1 to R3 and R5 to R7, rising to M with the R8 cascade and the
   two-clone test; the issue is labelled S.

## Acceptance (for this stage)

- [ ] Owner answers or defers Q1 to Q3.
- [ ] Issue relabelled with the corrected premise (finding 1) and, if Q4 holds, effort M.
- [ ] On go: `documentation/issues/1058-design.md` written, issue advanced to `stage:design`.

## Grounding

Read: the issue body and #1115; `plugin/lib/evidence_notes.py` (`sent_envelope`, `ingest`);
`plugin/lib/stats.py` (module docstring, `aggregate`, the `stats` CLI read);
`plugin/lib/contribution.py` (`weekly_reports`); `plugin/lib/evidence.py` (`is_ephemeral_fact`);
`plugin/docs/governance-telemetry.md` (idempotence and window sections). Not opened: the full
`build_report` payload schema (confirmed only that it is counts/shares), `finding_outcome`'s
internals (R6 is stated from its docstring contract), and the test files; design must open them.
No prior art for this item on any unmerged branch (only `origin/claude/*` and `origin/main` exist).
