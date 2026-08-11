# Build Plan — advisory false positives

**Scope:** `advisory-false-positives`
**Type:** bugfix
**Size:** medium (two modules + tests; every installed repo runs these probes)
**Critic mode:** cumulative-final
**Target release:** v3.3.2
**Branch:** `fix/advisory-false-positives`
**Baseline:** 4336 passed, 0 failed, 11 skipped (evidence tree-valid at branch point)

## Requirements Confidence

**High.** Both defects were reproduced against real inputs before any code was written — the
norm-registry one against `../samsung-frame-art-loader`'s actual artifacts, the tripwire one by
calling `_normalize` directly. Neither rests on inference about what the code probably does.

Parent requirement for both: `docs/norms.md` § Anatomy defines what a Direction entry is, and the
advisory surface's contract is that it reports facts about the repo. **An advisory that makes a
claim the reader can disprove by opening a file is a defect in the advisory**, not a formatting
requirement on the product — this is the ruling these chunks are built against, and it is what makes
"accept blockquoted fields" a fix rather than a feature.

## The problem

Two surfaces report things that are not true.

1. **`probe_norm_registry_unratified` falsely accuses blockquoted Direction entries.**
   `_FIELD_MARKER_RE` (`plugin/lib/norm_probes.py`) anchors `^\s*` + optional emphasis + field name,
   so a leading `>` or `- ` defeats it. Measured: `'**Why:** x'` and `'Why: x'` match; `'> **Why:** x'`
   and `'- **Why:** x'` do not. A product writing `> **Why:** …` gets
   *"no `## Direction` section is ratified in any artifact"* while carrying five ratified sections.
   The same blind spot sits in `_direction_lines`' soft-wrap joiner, which folds blockquoted
   continuations mid-sentence (observed: `"says the > display plane never requires…"`), degrading the
   citation scans `dead-why` and `stalled-transition` read off those lines.

2. **`work_model_index._normalize` mints non-words.** It reduces only `'s` and `n't`, so `'d`/`'ll`/
   `'re`/`'ve`/`'m` survive whole and are reported as undocumented domain vocabulary; and the bare
   plural rule strips the `s` off verbs (`'enriches'` → `'enriche'`). Same class as the `let'` bug the
   function's own comment says was already fixed.

## Success criteria

- Samsung's five Direction artifacts register as entries; arm (a) of the advisory goes silent there.
- **No repo that passes today changes verdict** — this is the regression risk that matters, since the
  fix loosens a predicate. Verified by re-running the cross-repo sweep, not by assertion.
- `you'd` / `i'll` / `they've` / `enriches` stop surfacing as orphan terms.
- Both pinned by tests that fail against the current code.

## Out of scope — deliberately, with reasons

- **The frequency-floor misses** (`timing`, `promptly`, `declined`, `follow-up`). These are a finite
  word list under-covering, not a normalization bug. The module's own comment rules that noise is
  handled by a populated index, never by widening the stoplist, and widening it swallows the
  content-bearing nouns the tripwire exists to catch.
- **Norm anatomy redesign.** `docs/norms.md` keeps its documented form; this widens what the detector
  accepts, it does not change what is canonical.
- **Advisory store / dismissal semantics.** Untouched. Note the consequence and do not "fix" it:
  samsung's stored advisory is keyed on its evidence string, so the existing one resolves through the
  normal resolution path once the probe stops firing — nothing here should mint a new id.
- **`_norms_exist` widening.** Already correct via the Enforcement-index arm; it is why samsung still
  got a correct sweep verdict while being falsely accused of having no norms.

## Chunks

- **Chunk 01 — blockquote-tolerant field detection.** Strip leading blockquote markers in
  `_direction_lines`, which is the single point every downstream matcher (`_FIELD_MARKER_RE`,
  `_WHY_RE`, `_STATUS_RE`, `_FIELD_OR_ITEM_RE`) reads through — so one change fixes entry detection
  AND the soft-wrap fold. Tests: every emphasis form of `Why`/`Status` in blockquote form; samsung's
  real shape (bold statement paragraph + blockquoted Why); nested `>>`; a continuation that no longer
  folds `>` into prose; the probes (`dead-why`, `stalled-transition`) driven end-to-end rather than
  their regexes asserted; and guards that a heading-only section and a blockquoted roadmap still do
  NOT count (loosening must not reopen the false-pass this detector exists to prevent).

  **Amended mid-build (2026-08-11), scope narrowed:** the original plan also widened
  `_FIELD_MARKER_RE` to accept a `- **Why:**` sub-bullet. **Dropped.** Reading the sibling
  `record_lint.direction_norm_count` showed a bullet-prefixed field line is consumed as a *new bullet*
  there and never counted, so the two modules would diverge further for a shape no repo writes. The
  blockquote half needs no such widening — stripping at `_direction_lines` leaves the shared marker
  regex untouched, which is what keeps `record_lint`'s imported copy in step.
- **Chunk 02 — contraction and verb-plural normalization.** Reduce the remaining contraction suffixes
  to their base word, and stop the bare-plural rule minting non-words from `-es` verbs. Tests: each
  contraction form; `enriches`; a guard that genuine plural normalization (`settings` → `setting`)
  still works and that distinct terms are not collapsed (the `series` → `seri` case the docstring
  warns about).

## Status

- [ ] Chunk 01: blockquote/bullet-tolerant field detection
- [ ] Chunk 02: contraction and verb-plural normalization

**Context:** Plan written 2026-08-11 immediately after the v3.3.1 cut, from two defects diagnosed
post-release. Both reproduced before planning. Nothing built yet.
