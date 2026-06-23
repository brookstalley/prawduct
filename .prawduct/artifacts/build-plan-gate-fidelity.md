<!-- Build Plan — gate-fidelity
     Tier: 1 (Source of Truth)
     Framework-internal hardening plan. For HOW to build (governance, test
     discipline, Critic review), read /prawduct:building before starting.
-->
---
artifact: build-plan
version: 2
scope: gate-fidelity
depends_on:
  - artifact: critic-review-protocol   # skills/critic/review-cycle.md, review-protocol.md
  - artifact: building-methodology      # methodology/building.md
last_validated: null
---

## Requirements Confidence

**Level:** Medium

**Why:** All 7 backlog items are user/critic-filed with detailed fix-shapes, and the
Explore pass pinned every landing site (file:line) and its existing test coverage — so
*where* and *how* are clear. Confidence is Medium, not High, because two chunks (04
verify-coverage, 06 work-model) carry a genuine policy fork that changes gate behavior
for every downstream consumer, and the user owns that policy (Principle 23).

**Open assumptions / unknowns:**

- `[CONFIRMED 2026-06-22: Chunk 04 — exempt non-executable files by FILE TYPE (prose .md + non-code config: .yaml/.yml/.json/.toml/.ini/.cfg/.txt), DOWNGRADED to an informational NOTE (not silently skipped), with an optional project-preferences allowlist override. User chose this over a configurable docs-path glob allowlist and over scoping the floor to runner-executable languages only.]`
- `[CONFIRMED 2026-06-22: Chunk 06 — reduce the work-model tripwire's NOISE (drop path-like fragments + broaden the common-prose floor) while keeping it firing on every prompt. User chose this over scoping firing to build-intent prompts only and over requiring term recurrence.]`
- `[ASSUMPTION: Chunk 01 — CRT-8H3R and CRT-6J4P are built as ONE chunk because both add the same git merge-base --is-ancestor guard to the gates.py↔critic_mode.py mirror pair (pinned by TestChainAnchorParity); splitting them would force two reviews of one coherent change. | MED impact | user can correct / override / defer]`
- `[ASSUMPTION: Chunk 03 — LOOSEN the verify-chunk-refs header parser to also accept `## Chunk NN —` (h2/em-dash), rather than keep it strict and only improve the error message. prawduct's OWN template/convention stays `### Chunk N:`; this is Postel-style robustness to consumer house styles, and it retires the known "em-dash fails parsers silently" gotcha. | MED impact | user can correct / override / defer]`
- `[ASSUMPTION: Chunk 05 — exclude UNTRACKED non-code files outside source/test/governance roots from the chunk-diff scope (keeping the non-empty files_reviewed invariant), rather than introducing a schema-valid scope:empty findings record. The exclusion is the narrower, lower-blast-radius fix. | MED impact | user can correct / override / defer]`
- `[ASSUMPTION: Ship as ONE feature branch with ONE cumulative-final PR (Chunk 06 carries Type: cumulative-final). If the 6-chunk cumulative review proves too heavy, Stage A (ch 01–02) and Stage B (ch 03–06) can split into two sequential PRs off the branch. | LOW impact | user can correct / override / defer]`

**What would raise confidence:** User confirmation (or override) of the two HIGH-impact
assumptions above (Chunk 04 coverage-exemption policy; Chunk 06 tripwire approach). Either
a one-line confirm or a redirect closes the gap — no spike needed.

## Status

<!-- Two stages. Stage A (ch 01–02) hardens record/chain SELECTION soundness; Stage B
     (ch 03–06) stops gates from firing false BLOCKINGs. Update after each chunk. -->

**Stage A — record-selection soundness**
- [ ] Chunk 01: Ancestry-bound the verify-resolutions chain (CRT-8H3R + CRT-6J4P)
- [ ] Chunk 02: PR-gate ledger fallback selects the newest record covering HEAD (CRT-2K9F)

**Stage B — stop false-BLOCKING gates**
- [ ] Chunk 03: verify-chunk-refs accepts the `## Chunk NN —` header style (BLD-5J8N)
- [ ] Chunk 04: verify-coverage floor is file-type aware (COV-8R2K)
- [ ] Chunk 05: Stop critic-review gate excludes untracked non-code files (STH-6T9W)
- [ ] Chunk 06: work-model tripwire suppresses prose/path-fragment noise (WMK-4Q9T)

Context: Plan authored and approved; both HIGH-impact policy forks confirmed by the user
(Chunk 04 file-type-exempt→NOTE; Chunk 06 filter-noise-stay-always-on). Remaining
assumptions (ch 05 exclude, one-PR) stand as vetoable. Stage A (ch 01–02) plus Chunk 03
shipped to the branch — each with a clean chunk-mode Critic pass; full suite green (1419).
(Status checkboxes stay `[ ]` until release — views_enabled flips them from the change-log
at ship time.) Next: Chunk 04 (verify-coverage file-type floor) — touches `lib/coverage.py`,
`lib/gates.py`, and `skills/critic/review-cycle.md` (NOT trivial-eligible; watch the
review-cycle.md token budget when softening F4b).

## Scaffolding

N/A — existing framework repo; no project initialization, dependencies, or new structure.

### Verification Strategy

Per-chunk: run the affected test files **with the repo-local interpreter**
(`python3 -m pytest tests/<file>.py`) and exercise the changed hook command via
`python3 bin/prawduct-hook <cmd>` (NOT a PATH-installed `prawduct-hook` — learning:
verify lib/bin changes against the working tree, not the installed plugin). Each
false-positive fix gets a regression test reproducing the reported false fire AND a
test proving the *true-positive* path still blocks (a relaxed gate needs the most
adversarial coverage — the retired PR trivial-fast-path lesson). Full suite green
(`python3 -m pytest`) before the cumulative review.

## Module Boundaries

- `lib/gates.py` — gate evaluation (ch 01, 02, 04, 05). The gates↔`lib/critic_mode.py`
  mirror parity (`TestChainAnchorParity`, `TestConsolidationPins`) must hold across ch 01.
- `lib/critic_mode.py` — mode inference (ch 01).
- `lib/buildplan_refs.py` — the single canonical chunk-section walker (ch 03); changes
  here propagate to all four chunk-field parsers + the critic_mode reader.
- `lib/coverage.py` — coverage diff/classification helpers (ch 04).
- `lib/work_model_index.py` — work-model term extraction (ch 06).
- `skills/critic/review-cycle.md` — Critic Goal-1 F4b prose (ch 04, coherence with the gate).

## Build Chunks

### Chunk 01: Ancestry-bound the verify-resolutions chain

- **Description:** A prior-review anchor SHA that still *resolves* but is **not an
  ancestor of HEAD** (session switched to a divergent/sibling branch) must not anchor a
  verify-resolutions delta — today the scope helper and rule-1b only demote when the
  anchor fails to resolve at all, yielding cross-branch phantom-finding diffs (CRT-8H3R)
  and cross-bundle chain vouching (CRT-6J4P). Add a `git merge-base --is-ancestor
  <anchor> HEAD` guard at every point an anchor is accepted, demoting to
  cumulative/final when the anchor is non-ancestral.
- **Depends on:** none
- **Artifacts consumed:** `methodology/building.md` (mode semantics), `skills/critic/review-cycle.md` (per-mode behavior)
- **Deliverables:**
  - `lib/gates.py` — in `_compute_verify_resolutions_scope`, after the existing
    `git rev-parse --verify <commit_reviewed>^{commit}` success block, add an
    `--is-ancestor` check; on failure return an empty scope with a new categorized
    reason (e.g. `non-ancestor-commit:`) sibling to the existing `unresolved-commit:` /
    `scope-widened:` reasons in the docstring.
  - `lib/critic_mode.py` — mirror the guard in `_rule_postfix_chain_fires` (rule-1b,
    between the anchor-resolve check and the `_committed_files_since` delta) and on the
    rule-1 `_commit_resolves` path (`_rule_verify_resolutions_fires`). Preserve the
    `gates`↔`critic_mode` mirror parity.
- **Tests:**
  - `tests/test_cumulative_gate.py` (`TestScope*`): a resolvable-but-non-ancestor anchor
    → empty scope / demotion with the new reason; an ancestor anchor → unchanged behavior.
  - `tests/test_critic_mode_inference.py` (`TestRule1VerifyResolutions`,
    `TestRule1bPostfixChain`): a sibling-branch anchor does NOT fire rule-1/rule-1b;
    an ancestor anchor still does.
  - `TestChainAnchorParity` / `tests/test_buildplan_walkers.py::TestConsolidationPins`
    stay green (mirror parity).
- **Acceptance criteria:** New non-ancestor cases demote as specified; all existing
  mode-inference and cumulative-gate tests pass; mirror-parity pins green.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` (inferred mode) run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status; reconcile CRT-8H3R + CRT-6J4P in backlog

### Chunk 02: PR-gate ledger fallback selects the newest record covering HEAD

- **Description:** When interleaved Critic→PR cycles overwrite the single-slot
  `.critic-findings.json` with a record that is the right KIND but covers a *sibling
  branch's* HEAD, the PR gate evaluates that stale record, fails the coverage check, and
  exits 1 — never consulting the governance ledger where this branch's own
  still-valid covering record was appended (CRT-2K9F). Make the gate fall back to the
  ledger when the slot record qualifies-by-kind but does NOT cover HEAD, and have the
  fallback select the newest qualifying record whose `commit_reviewed` covers the current
  HEAD. Must NOT loosen the gate — a covers-HEAD clean record is exactly as strong as the
  slot record; this only stops a sibling branch's clean record from masking this branch's.
- **Depends on:** none (independent of ch 01; same file)
- **Artifacts consumed:** `skills/critic/review-protocol.md` (PR gate contract)
- **Deliverables:**
  - `lib/gates.py` — at the `check_cumulative_critic` decision point (currently: if
    `_pr_gate_record_qualifies(data)` → `_evaluate_pr_gate_record` unconditionally), also
    reach the ledger fallback when the slot record qualifies-by-kind but
    `_record_covers_head(...)` reports `"stale"`. Extend `_ledger_fallback_record`'s
    acceptance loop to require `_record_covers_head` covers HEAD (reuse the existing
    primitive), selecting the newest such record. Retain the CRT-8W3F session-freshness
    bound.
- **Tests:**
  - `tests/test_governance_ledger.py` (`TestGateLedgerFallbackAccepts`,
    `TestGateLedgerFallbackStaysHonest`): interleaved-branch case — slot covers Y's HEAD,
    ledger holds X's covering-HEAD clean record, PR on X passes via fallback; a ledger
    with NO covering record still fails (honesty preserved).
  - `tests/test_cumulative_gate.py`: a fresh slot record that covers HEAD still passes
    directly (no behavior change on the happy path).
- **Acceptance criteria:** Interleaved-branch re-run no longer forces a needless Critic
  re-run; no covering record anywhere → still blocks; happy path unchanged.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` (inferred mode) run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status; reconcile CRT-2K9F in backlog

### Chunk 03: verify-chunk-refs accepts the `## Chunk NN —` header style

- **Description:** The chunk-section walker recognizes only `### Chunk NN:` (h3 + colon),
  so plans using the `## Chunk NN —` house style (h2, em-dash) exit 1 "chunk not found"
  even though the chunk exists — training reviewers to hand-wave a real-BLOCKING-shaped
  signal (BLD-5J8N). Widen the single canonical walker to accept both forms. prawduct's
  own template/convention stays `### Chunk N:`; this is robustness to consumer house
  styles, not a convention change.
- **Depends on:** none
- **Artifacts consumed:** `templates/build-plan.md` (the canonical convention — unchanged)
- **Deliverables:**
  - `lib/buildplan_refs.py` — in `_chunk_section_lines`, recognize a heading that starts
    with either `### Chunk ` or `## Chunk `, parse the chunk id from a non-colon delimiter
    (em-dash `—`, en-dash `–`, hyphen `-`, or colon `:`), and resolve the sibling-stop
    conflict (an h2 chunk header must not trip the `## ` section-terminator for its own
    section). The fix flows through `_parse_build_plan_chunk_refs`,
    `_parse_build_plan_chunk_type`, `_parse_build_plan_chunk_trivial_rationale`, and
    `critic_mode._critic_mode_for_chunk` (all fold onto this walker).
- **Tests:**
  - `tests/test_buildplan_walkers.py::TestChunkSectionLines`: add `## Chunk 01 — Name`
    positive cases (section found, refs extracted) alongside the existing `### Chunk 01:`
    cases.
  - `tests/test_build_plan_resolution.py::TestActiveBuildPlanChunkHeadingsParse`: the two
    fixtures that pin the strict contract (`test_fixture_four_hash_heading_fails`,
    `test_fixture_missing_colon_heading_fails`) — update so the h2/em-dash form now PARSES
    (retitle/repoint; keep a genuinely-malformed heading as the negative case).
- **Acceptance criteria:** Both header styles resolve identically; the four downstream
  parsers + the critic_mode reader work on an h2/em-dash plan; genuinely malformed
  headings still fail clearly.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` (inferred mode) run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status; reconcile BLD-5J8N in backlog

### Chunk 04: verify-coverage floor is file-type aware

- **Description:** The symbol-grep coverage floor is applied to non-executable files the
  same as code, so a chunk whose deliverables legitimately include prose `.md` — or a
  branch editing a non-code config file (`.yaml`, etc.) with no test symbols — produces an
  unsoftenable BLOCKING missing-coverage and `verify-coverage` exits 1 on an otherwise
  clean tree, forcing a waiver or a token reference-test (COV-8R2K). Make the floor
  file-type aware: exempt non-executable files (prose docs + non-code config), reporting
  them as an informational NOTE rather than BLOCKING. The gate and the Critic's Goal-1 F4b
  rule must AGREE (coherence), so soften the protocol prose to match.
  **Surfaces (enumerated):** `lib/gates.py`, `lib/coverage.py`,
  `skills/critic/review-cycle.md`, the gate tests. Touching governance protocol prose →
  NOT trivial-eligible; watch the `review-cycle.md` token budget when softening F4b.
- **Depends on:** none
- **Artifacts consumed:** `skills/critic/review-cycle.md` (Goal 1, rule F4b)
- **Deliverables:**
  - `lib/coverage.py` — a helper classifying a changed path as non-executable
    (extension-based: `.md` + config extensions `.yaml/.yml/.json/.toml/.ini/.cfg/.txt`;
    reuse/extend the existing `.md` logic), with an optional `project-preferences`
    allowlist override hook.
  - `lib/gates.py` — in `verify_coverage`, route non-executable files out of the BLOCKING
    `missing` set into an informational NOTE (per the Chunk-04 HIGH-impact assumption).
  - `skills/critic/review-cycle.md` — soften Goal-1 F4b so a missing-coverage line on a
    non-executable file is NOTE, not BLOCKING.
- **Tests:**
  - `tests/test_verify_coverage_gate.py`: a `.md`-only deliverable chunk → no BLOCKING,
    exit 0; a YAML-only branch → no BLOCKING, exit 0; a MIXED chunk → only the executable
    files are gated (a real uncovered `.py` still BLOCKS — true-positive preserved).
  - If the `review-cycle.md` edit pressures its token-budget guard, trim per the
    surrounding-text rule (planning.md "Enumerate the surfaces").
- **Acceptance criteria:** Non-executable-only changes don't trip the coverage gate;
  executable coverage gaps still BLOCK; the gate and F4b prose tell the same story.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` (inferred mode) run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status; reconcile COV-8R2K in backlog

### Chunk 05: Stop critic-review gate excludes untracked non-code files from chunk-diff scope

- **Description:** An untracked, operator-dropped non-code file (e.g. a note placed in
  `incoming-bugs/`) is counted into the chunk-diff scope, growing it beyond what the
  verify-resolutions findings cover; the suggested remedy can't produce a schema-valid
  empty-scope record, so a waiver becomes the only exit on a clean, fully-reviewed tree —
  training waiver-reaching (STH-6T9W). Exclude untracked non-code files outside
  source/test/governance roots from the scope, symmetric with the existing
  `_is_metadata_path` exclusion. Keep the non-empty `files_reviewed` invariant intact.
- **Depends on:** none
- **Artifacts consumed:** `skills/critic/review-cycle.md` (verify-resolutions scope contract)
- **Deliverables:**
  - `lib/gates.py` — extend the `session_changed` filter in
    `_verify_resolutions_gate_check` (and the matching filter in
    `_compute_verify_resolutions_scope`) to drop untracked files (git status `??`) that
    are not under source/test/governance roots and are non-code by extension. Prefer a
    local gate-level predicate over changing `gitstate._get_session_changed_files`
    (narrower blast radius); document the choice.
- **Tests:**
  - `tests/test_session_critic_gate.py` (`TestSatisfySessionGateVerifyResolutionsScope`):
    an untracked operator note (e.g. `incoming-bugs/foo.md` or a stray `.txt`) does NOT
    inflate `out_of_scope`; a clean fully-reviewed tree carrying such a file → gate
    satisfied. A genuinely-in-scope untracked *code/test* file still counts (true-positive
    preserved).
- **Acceptance criteria:** A reviewed clean tree with a stray untracked non-code file
  ends the session without a waiver; in-scope untracked code still gates.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` (inferred mode) run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status; reconcile STH-6T9W in backlog

### Chunk 06: work-model tripwire suppresses prose/path-fragment noise

- **Description:** The prompt-term extractor treats common adjectives/adverbs/verbs and
  singularized file-path fragments as candidate domain terms, firing the "terms not found
  in any governing artifact" tripwire on most natural-language prompts (it fired on this
  very planning session's prompt) — pure noise today, but it desensitizes the one tripwire
  meant to catch real undocumented requirements (WMK-4Q9T). Reduce the noise while keeping
  the tripwire firing on every prompt (per the Chunk-06 HIGH-impact assumption): drop
  path-like fragments and broaden the common-prose floor — as a SEPARATE filter, since the
  module docstring frames `STOPWORDS` as deliberately narrow. No POS-tagger dependency
  (hot path).
- **Depends on:** none
- **Artifacts consumed:** `lib/work_model_index.py` module docstring (filter-design intent)
- **Deliverables:**
  - `lib/work_model_index.py` — suppress tokens that originate from a path-like string in
    the raw prompt (detect `/`-bearing or known-extension tokens and exclude their
    shredded fragments), and broaden the common-English floor (`_in_floor`) coverage of
    prose words. Land as a new predicate in the `find_orphan_terms` filter comprehension
    and/or `_salient`, NOT by expanding `STOPWORDS`.
- **Tests:**
  - `tests/test_work_model_index.py`: the literal terms from this session's false fire
    (`urgent`, `wrap-up`, `awaiting`, `model-id`, `fold`, `single-owner`, `ceiling`,
    `cross-linked`, `incoming-bug`) are NOT flagged as orphans; a genuine undocumented
    domain term still IS flagged (true-positive preserved).
  - `tests/test_work_model_hooks.py`: the end-to-end nudge still fires on a real orphan
    and stays quiet on an all-prose prompt.
- **Acceptance criteria:** Ordinary-English / path-fragment prompts don't fire the
  tripwire; a real undocumented domain term still does.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status; reconcile WMK-4Q9T in backlog
  3. `/prawduct:critic cumulative` run against `merge-base...HEAD` (the one cumulative
     review AND the `/prawduct:pr create` gate) and blocking findings resolved

## Early Feedback Milestone

N/A — framework-internal governance fixes; no interactive user surface. Each chunk's
"feedback" is its regression test reproducing the reported false fire / unsound selection.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after `/prawduct:critic` (inferred mode) passes;
one cumulative review on Chunk 06 (`Type: cumulative-final`) is both the final review and
the `/prawduct:pr create` gate. Default: one feature branch → one PR. If the 6-chunk
cumulative proves too heavy to review in one pass, split Stage A (ch 01–02) and Stage B
(ch 03–06) into two sequential PRs off the branch.

- After Chunk 01: per-chunk review confirms the ancestry-guard primitive + mirror parity
  before ch 02 and Stage B build on the same gate surfaces.
- After Chunk 06: cumulative review across all 6 chunks — coherence of the `lib/gates.py`
  changes (ch 01, 02, 04, 05 all touch it), and that no relaxed gate lost a true-positive.
