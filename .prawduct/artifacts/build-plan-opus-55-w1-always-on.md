---
artifact: build-plan
version: 1
scope: opus-55-w1-always-on
branch: feature/opus-55-w1-always-on
partition: 01 serial (main agent); 02-03 delegated to one isolated-worktree delegate, run in parallel with 01 — disjoint files (digest/CLAUDE.md/principles vs the learnings corpus and learnings_files.py) and disjoint test files, so it shortens wall clock without the tracks colliding
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
governed_by:
  - artifact: digest-behavior-inventory
    dispositions:
      - "the inventory is the digest scrub's acceptance list → conforms: every A- and B-row clause the rewritten bullets touch survives. A8/A9/A10 (standing block, in-flight is RUNNING, persist before handing over) stay in A-17's rewrite; A13 stays in A-18; B1/B2/B3 stay in A-19; B7/B8/B9 stay in A-20. Chunk 01 re-checks the rows against the written digest, not against the slice text"
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms: this wave deletes second homes (A-2, A-3, A-4, A-12, A-26, A-37); none is added. A-22's stance bar keeps its home in principles.md and the digest keeps only the trigger"
      - "prawduct guides and reviews, it never implements → inapplicable, because only framework prose and one header constant change"
      - "goals and verification bind; prescribed method is advice → conforms: the ruled decisions and Success bind; where a slice's replacement text dropped content a test pins (the standing-block distinctions), the content was restored in plain words rather than the text applied verbatim"
      - "the plugin writes nothing into a governed repo except its own state, the evidence store and the files it must reconcile → conforms, and it is why A-16 stops at new scaffolds: rewriting an onboarded repo's `core.md` header would be a new write into product files, so it is recorded for the owner rather than built"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "authority fails closed; advice fails soft → inapplicable, because no verdict or advisory path changes"
      - "local-first governance coordination → inapplicable, because no coordination mechanism changes"
      - "written in Python, never specific to Python → conforms: the header exclusion is by markdown grammar, which is language-neutral"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms: a test pinning a sentence this wave rewrites is retired as a descoped requirement or re-pointed at the interface token it protects; no new sentence pin is added"
      - "model plan (Fable coherence before the cycle lands) → conforms: owed once, before W6 lands, per the audit's § Binding norms; not per wave"
---

# Build Plan: Opus 5.5 prompt audit — W1, the always-on surface

## Problem

The text every session loads is tuned for older models, and on Opus 5.5 it misfires in three ways.
It never says not to stop early (A-1). It tells the builder to re-check work that Opus 5+ already
checks (A-22, and the nine falsify-first rules in `core.md`). It makes delegation the first answer
(A-21). The learnings corpus is also patch accretion: 38 core rules restate about 17 ideas, and the
area files copy core again. The evidence and replacement text for every decision is in
`opus-55-prompt-audit-2026-09/slice-A.md`. The owner ruled on 2026-09-28 (the artifact's
§ Rulings).

## Success

- The digest carries A-1's early-stop paragraph as the first paragraph under `## Closing the turn`.
  A-17 to A-21, A-39 and A-22's digest half are applied, and the stripped character count sits
  below its pre-wave reading with the ceilings lowered to match.
- `principles.md` carries A-22's renamed bar, and A-23 and A-24 are applied. Root `CLAUDE.md`
  carries A-25 and A-26.
- `core.md` holds the 17 rules A-15's disposition index yields, under A-16's header. The area files
  apply A-2, A-3 and A-31 to A-37. A-38's specimen strip is applied corpus-wide.
- The suite passes. Every sentence-pinning test that a rewrite breaks is retired or re-pointed at
  its interface token, per the prose-test taxonomy.
- One fresh-agent probe on the new digest and `core.md`, run on the session model (F1 ruling: these
  surfaces reach only the main agent). It checks A-1 (the agent takes the next step instead of
  announcing it) and A8/A9 (the standing block is correct).

## Out of scope

- W2 to W6, including the hook-text decisions A-5, A-6, A-7, A-27 to A-30, which are W2's.
- The flags A-40, A-41 and A-42. They are records and are not applied.
- Any new learnings rule. Consolidation only merges, rewrites and deletes.

## Requirements Confidence: High

Every change has replacement text, and the owner has ruled on it.

- [ASSUMPTION: A-38 "applied corpus-wide" means stripping issue ids, dates, version archaeology and specimen parentheticals from every area-file rule, and dropping any Tell that restates its rule. It does not re-judge whether a rule should exist | MED impact | owner can narrow it to the rules A-38 names]
- [ASSUMPTION: this branch stacks on `feature/opus-55-prompt-audit` because the slice files it applies live there. The two land together or in that order | LOW impact | owner can reorder]

## Status

- [x] Chunk 01: digest, root CLAUDE.md, principles.md
- [x] Chunk 02: core.md consolidation, area-file dedup, CORE_HEADER
- [x] Chunk 03: A-38 specimen strip across the learnings corpus

## Chunk 01: digest, root CLAUDE.md, principles.md

**Type:** doc-only
**Decisions:** A-1, A-17, A-18, A-19, A-20, A-21 (with the F4 owner amendment), A-22, A-23, A-24,
A-25, A-26, A-39.
**Files:** `plugin/methodology/session-digest.md`, `plugin/docs/principles.md`, `CLAUDE.md`,
`plugin/methodology/reflection.md` (one sentence that A-16 made false; the delegate found it),
`tests/test_plugin_methodology_digest.py` (the ceilings, the `DIGEST_SECTION_PLACEMENT` key rename
for A-39, and `DIGEST_HEADROOM_RESERVE`), and any other test the suite shows pinning a rewritten
sentence.
**Done when:** the digest-behavior-inventory rows listed under `governed_by` are each found in the
written digest. The character wall and the token ceilings are re-measured and lowered. The suite
passes. The probe has run.

## Chunk 02: core.md consolidation, area-file dedup, CORE_HEADER

**Type:** code (A-16 changes `plugin/lib/learnings_files.py`'s `CORE_HEADER`. It reaches new scaffolds
and relayouts only: `core.md` is scaffold-once, so already-onboarded repos keep the old header, which
still lints clean because the header is excluded by grammar, not text)
**Decisions:** A-2, A-3, A-4, A-8 to A-16, A-31 to A-37.
**Files:** `.claude/rules/learnings/*.md`, `plugin/lib/learnings_files.py`,
`tests/test_learnings_files.py`, `tests/test_plugin_init.py`, and any learnings budget or lint pin
the suite shows.
**Done when:** `core.md` matches A-15's index at 17 rules. Each area file drops the rules its
decision names. The header obligation is gone from `CORE_HEADER` and from the four area-file
headers. The suite passes.

## Chunk 03: A-38 specimen strip across the learnings corpus

**Type:** doc-only
**Decisions:** A-38.
**Files:** `.claude/rules/learnings/*.md`.
**Done when:** no rule carries an issue id (`#NNN`, `ABC-1X2Y`), a date, or a specimen
parenthetical that does not change what it prescribes. A grep for `#[0-9]` and
`[A-Z]{3}-[0-9][A-Z0-9]{3}` in the corpus returns only ids that ARE the rule's subject. The suite
passes. Critic: this is the plan's last chunk, so its review is the branch's cumulative.
