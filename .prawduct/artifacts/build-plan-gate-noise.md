---
artifact: build-plan
version: 2
scope: gate-noise
depends_on:
  - artifact: framework-efficiency-review-2026-07-02
last_validated: 2026-07-02
---

# Build Plan — gate-noise (Wave 1 Plan A, GOV-7T2M)

Parent requirement: `.prawduct/artifacts/framework-efficiency-review-2026-07-02.md`
(Wave 1 Plan A). Backlog: GOV-7T2M (supersedes WMK-4Q9T; related WMK-7D3R).

## Requirements Confidence

**Level:** High

**Why:** Owner-accepted parent artifact specifies both deliverables with file:line
evidence; the code paths are small, pure, and fully test-covered.

**Open assumptions / unknowns:**
- [ASSUMPTION: Deliverable (1) of GOV-7T2M — the freshness-is-the-exit-code line in
  both review protocols — is **already shipped** (PR #104, 2026-06-22, TST-4K2P:
  `skills/critic/review-protocol.md:41`, `skills/pr/review-protocol.md:56`, both
  stating "that exit code is the *only* freshness signal"). The efficiency review's
  "residual gap" claim predates verifying those lines. This plan therefore descopes
  deliverable (1) as already-delivered rather than adding a duplicate line to a
  protocol at its token ceiling. | HIGH impact | user can correct]
- [ASSUMPTION: The artifact's literal instruction "drop refactor/rename/redesign/
  rework/remove/replace from REQUIREMENT_VERBS" is refined to a two-set split,
  because `rename`/`redesign`/`rework` are not absorbed by the common-word floor —
  a bare deletion would make "rename the FooBar module" report *rename* itself as
  an orphan (a new false-positive class, contradicting the item's purpose). The six
  verbs stop making prompts requirement-shaped but stay exempt from orphan
  reporting. | MED impact | user can override]
- [ASSUMPTION: "Include doc subdirectories in the corpus" means recursive globs for
  `docs/` and `methodology/`; `.prawduct/artifacts/` stays top-level (flat by
  convention). Safe direction: extra corpus vocabulary can only suppress orphans,
  never create them. | LOW impact | user can override]

**What would raise confidence:** N/A.

## Status

- [ ] Chunk 01: Work-model tripwire — maintenance-verb split + recursive doc corpus
Context: Plan authored 2026-07-02 from the pick of GOV-7T2M. Deliverable (1)
(protocol freshness lines) verified already shipped in PR #104 — descoped. Chunk 01
is the entire plan.

## Scaffolding

Existing repo — no scaffold. Tests: `pytest tests/test_work_model_index.py
tests/test_work_model_hooks.py` (full suite before commit).

### Verification Strategy

Beyond tests: run the real hook against this repo — pipe the owner's own review
prompt ("Please review the framework for efficiency, quality, performance, and
token management improvements" plus refactor/rework phrasing) through
`prawduct-hook user-prompt-submit` and confirm silence; confirm a genuine
requirement prompt ("add OAuth login to the settings page") still nudges.
Self-hosting caution (learnings): this edits a detector governing the current
session — check the new signal against the repo root before relying on it.

## Build Chunks

### Chunk 01: Work-model tripwire — maintenance-verb split + recursive doc corpus

- **Description:** Stop the undocumented-requirement tripwire firing on
  maintenance-verb prompts (it fired on the owner's own review prompt twice), and
  widen the vocabulary corpus so governing docs in subdirectories stop reading as
  orphan sources. Two edits:
  1. `lib/work_model_index.py` — split the verb set: `REQUIREMENT_VERBS` keeps only
     genuinely requirement-carrying verbs (drop refactor, rename, redesign, rework,
     remove, replace); a new `MAINTENANCE_VERBS` frozenset holds the six.
     `is_requirement_shaped` keeps matching `REQUIREMENT_VERBS` only (so a
     maintenance verb no longer lowers the firing threshold to one orphan);
     `find_orphan_terms` exempts the union (directive vocabulary is still never
     itself the orphan). Update the comments to state the two roles explicitly.
  2. `bin/prawduct-hook` `_work_model_corpus_paths` — recursive (`rglob`) markdown
     globs for `docs/` and `methodology/`; rewrite the comment that currently
     declares top-level-only deliberate (the reversal rationale: governing
     vocabulary does live in subdirectories in product repos, and wider corpus can
     only quiet the nudge, never make it noisier). SessionStart force-rebuilds the
     index, so no staleness edge case from newly-included old files.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/framework-efficiency-review-2026-07-02.md`
- **Deliverables:** edits to `lib/work_model_index.py`, `bin/prawduct-hook`,
  `tests/test_work_model_index.py`, `tests/test_work_model_hooks.py`
- **Tests:**
  - Maintenance-verb prompts are not requirement-shaped: "refactor the retrieval
    pipeline", "rename FooBar to BazQux", "rework the session digest" — silent with
    a single orphan; the owner's review-prompt class joins CONVERSATIONAL_PROMPTS.
  - Maintenance verbs never reported as the orphan (rename/redesign/rework are off
    the common-word floor — regression guard for the two-set split).
  - Requirement prompts still fire (existing REQUIREMENT_PROMPTS corpus unchanged);
    two-orphan threshold still fires on maintenance prompts introducing two genuine
    domain terms.
  - Corpus: a markdown file in a `docs/` subdirectory contributes vocabulary
    (extend `test_index_covers_claude_md_docs_and_methodology`) and its mtime
    staleness triggers rebuild (extend `test_index_rebuilds_when_a_docs_file_is_newer`).
- **Acceptance criteria:**
  - Full pytest suite passes.
  - Live-hook check per Verification Strategy: owner's review prompt silent,
    genuine requirement prompt still nudges.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status
  3. `/prawduct:critic cumulative` run against `merge-base...HEAD`, blocking
     findings resolved — this IS the chunk's review and the `/prawduct:pr create` gate
  4. Backlog: GOV-7T2M updated via `/prawduct:backlog` (and WMK-4Q9T merged/closed
     at archive time per the pick's dedup note)

## Early Feedback Milestone

**Milestone chunk:** 01 (single-chunk plan)
**What the user can do:** Prompt with maintenance verbs without the tripwire firing;
governing docs in subdirectories recognized as vocabulary.

## Governance Checkpoints

**Commit & PR cadence:** Commit the chunk, then one `/prawduct:critic cumulative`
(the chunk review AND the PR gate), then `/prawduct:pr` per the wave rules (own
feature branch off develop, ships at next version bump).
