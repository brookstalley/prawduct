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
- **Chunk 02 — ~~contraction and verb-plural normalization~~ → DELETE the work-model tripwire.**

  **Replaced 2026-08-11, owner direction.** The original chunk was a precision fix on
  `work_model_index._normalize`. The 2026-07-12 owner ruling recorded on #257 says the resolution for
  this tripwire is **deletion, not a precision fix**, and declares the remaining fix legs moot. The
  ruling's precondition is **verified live**: its named replacement, CRT-5M9J (#293, closed), ships the
  `scope-trace:` question in both `skills/critic/review-protocol.md:99` and
  `skills/pr/review-protocol.md:51` — so requirements-precede-code enforcement survives the deletion.

  **Scope — delete:**
  - `cmd_user_prompt_submit` and `cmd_build_index` in `plugin/bin/prawduct-hook`, plus
    `_work_model_ensure_index` and the index cache it writes.
  - Both wirings in `plugin/hooks/hooks.json` (SessionStart `build-index`, `UserPromptSubmit`).
  - Tripwire-only lib surface: `build_index`, `find_orphan_terms`, `is_requirement_shaped`,
    `should_fire`, `format_nudge`, `nudge_for`, `_is_question`, `_is_harness_text`, and the constants
    only they use (`REQUIREMENT_VERBS`, `MAINTENANCE_VERBS`, `_DIRECTIVE_VERBS`, `_NOUN_DETERMINERS`,
    `_SENTENCE_BREAK`, `_HARNESS_MARKERS`).
  - `tests/test_work_model_hooks.py` and the tripwire half of `tests/test_work_model_index.py`.
  - Prose describing the tripwire — it is named as "tripwire #1" in the session digest and is
    referenced from the governance surfaces; a deleted mechanism that documentation still asserts is
    a Living Documentation failure, not a leftover.

  **Scope — KEEP (this is the boundary that makes it a chunk rather than an `rm`):**
  `prawduct-hook jurisdiction` is a separate, healthy consumer built on the same module. It reads the
  corpus directly via `_work_model_corpus_paths` and never touches the cache (confirmed by reading
  `cmd_jurisdiction`), so the cache goes and jurisdiction is unaffected. Everything it shares stays:
  `jurisdiction_candidates`, `salient_terms`, `extract_vocabulary`, `_normalize`, `_tokens`,
  `_salient`, `_in_floor`, `_COMMON`, `STOPWORDS`, `_MIN_LEN`, `_WORD`, and `lib/common_words.py`.

  > ⚠️ **#638's defect SURVIVES this deletion, and that is the finding worth carrying forward.**
  > The mis-stemming lives in `_normalize`, which `jurisdiction_candidates` shares. Deleting the
  > tripwire removes the *visible* symptom (the nudge that reported `i'll` and the non-word
  > `enriche`) while the bug keeps degrading jurisdiction's term matching — silently now, as a weaker
  > match rather than a false claim. **Do not close #638 as resolved by the deletion.** Re-scope it to
  > jurisdiction match quality. Note the inversion this creates: once the tripwire is gone,
  > `_normalize` is no longer code slated for deletion, so the 2026-07-12 ruling stops covering it and
  > a fix becomes legitimate again — at low priority, because a seeding heuristic that ranks slightly
  > worse is not an advisory that cries wolf.

## Status

- [ ] Chunk 01: blockquote/bullet-tolerant field detection
- [ ] Chunk 02: delete the work-model tripwire (keep jurisdiction)

**Context:** Plan written 2026-08-11 immediately after the v3.3.1 cut, from two defects diagnosed
post-release. Both reproduced before planning. Nothing built yet.
