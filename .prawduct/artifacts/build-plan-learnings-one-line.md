---
artifact: build-plan
version: 2
scope: learnings-one-line
branch: feature/learnings-one-line
depends_on:
  - artifact: learning-system-v2-discovery
  - artifact: learning-system-audit-2026-09-01
  - artifact: nonfunctional-requirements
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "state-file growth is an advisory warning, never a hard block → amendment proposed: learnings rules files leave this norm's scope. They are an always-loaded corpus with an owner-set cap, not state files. Owner direction 2026-09-24, in the session that commissioned this plan: 'We can't have giant learnings like that', with a hard cap that only the owner can raise. The v2 budget gate already blocked without a recorded decision; this plan records the departure rather than widening it silently"
      - "context weight is a cost → conforms: this plan exists to cut always-loaded context (core.md is 107KB here and 139KB in discodon)"
      - "proportionality ratchets both ways → conforms: the controls added name their yield (the compliance state is printed in every session briefing), and the one control that never held, agent self-raise on core.md, is removed"
      - "review wall-clock is P0 → inapplicable, because no review path changes"
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms: the line limit and core cap are constants in one module, and every prose carrier cites them"
      - "authority fails closed, advice fails soft → conforms: an unreadable corpus or base reports 'unchecked' and never passes as compliant"
      - "the plugin writes nothing into a governed repo except its own state and reconciled files → conforms: compaction writes the repo's own learnings files, the same surface learnings-migrate already writes"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "local-first, no network, no third-party dependencies → conforms: git, the ledger and files only"
      - "written in Python, never specific to Python → conforms: learnings files are markdown in every product, and the checks are line and byte measures"
      - "prawduct guides and reviews, it never implements → conforms: compaction edits prawduct's own governance corpus in the repo, not product code, and the rewriting judgment is the agent's, validated by code"
      - "goals and verification bind, prescribed method is advice → conforms: the chunk Deliverables are best guesses and the Success list binds"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution → conforms: learnings-compact is a new verb; learnings_budgets keeps its shape and core.md gains a required owner_approved field, recorded as a contract change in the change-log"
      - "whole-surface semantic versioning; persisted data independently schema-versioned → conforms: the compaction-map ledger event carries the ledger's schema_version, and the core-cap change ships in a minor release, recorded in the change-log"
      - "exit codes are the contract → conforms: learnings-compact uses 0/1/2 on the learnings-migrate scheme"
  - artifact: learning-system-v2-discovery
    dispositions:
      - "R2 (16KB default, raise with reason, no count cap, over-and-grew only) → superseded in part by the owner's 2026-09-24 direction: core.md becomes a hard cap only the owner can raise, and a compliant corpus blocks when over even if it did not grow. Area files keep raise-with-reason (owner, same day)"
      - "R3 (unmapped rules and bodies land in core.md under ## Unsorted) → superseded: this is the defect. The compaction command corrects the output, and the migration stops emitting bodies"
      - "§8.7(3), 'an over-cap core.md on day one costs nothing until the next rule is written' → falsified in discodon (growth measured against the legacy file's 176KB) and corrected by removing that credit"
partition: serial — 02's validator reuses 01's lint, and 04 runs 02's command on this repo's own corpus; 03 is prose that could run beside 02 but shares the change-log and the token-budget tests with it
last_validated: 2026-09-24
---

# Build plan — learnings are one line each, and core.md stays small

## Requirements Confidence

**Level:** Medium. The owner confirmed the shape on 2026-09-24. The numbers are assumptions.

**Problem:** `.claude/rules/learnings/core.md` loads in every session and has grown to 107KB here,
139KB in discodon, 58KB in bankmachine and 57KB in hallucinote, roughly 15–35k tokens per session.
This is the fourth time the corpus has regrown (#449, the July compaction, #369, v2). Every pass
paired a one-off sweep with a control that could be bypassed: an advisory nudge nobody acted on; a
per-rule 400-character check that v2 deleted; an agent-raisable budget (six raises here in five
days); an agent-writable waiver; and a migration credit that measured discodon's `core.md` against
the 176KB legacy file, so its first 47KB of growth counted as shrinkage. The write-side guidance
(`reflection.md` Step 4: "a heading that carries the rule, its brief why, and the instance that
earned it, inline … never trim a rule to fit") pulls against the budget on every reflection.

**Success:**
1. On a compacted repo, every rule in every learnings file is one line of at most 250 characters.
   A body line anywhere is a finding, and `core.md` is at most 12KB.
2. An agent cannot raise `core.md`'s cap. A raise needs an `owner_approved:` date, is surfaced in
   the session briefing and the PR review payload, and does not count when it lands in the same
   session as the growth it would excuse.
3. A non-compacted repo is frozen: at Stop, neither `core.md` nor the corpus total may grow, with
   no legacy credit and no waiver. Every added or edited rule line must already meet the line limit.
4. The line-length and body checks need no base tree, so a session with no base marker still gets them.
5. `prawduct-hook learnings-compact` takes a repo from non-compliant to compliant in one reviewable,
   revertible commit. Drops happen only with owner approval, and citation history carries across
   the rewrite.
6. Every surface that tells an agent how to write a rule states the one-line format and names the
   route when the rule does not fit.
7. This repo's own corpus is compacted, and its RULING entries live beside the norms they rule on.

**Out of scope:**
- Compacting consumer repos. Each one does that in its own session, driven by the directive this
  plan ships.
- discodon's stale container plugin install (an operator task, noted in the handoff).
- The PR reviewer's learnings exposure (#888).
- An aggregate prose budget across all governance files (#850).

**Open assumptions:**
- `[ASSUMPTION: 250 characters per rule line and a 12KB core cap | HIGH impact — they set how much must move out or be dropped | user can override]`
- `[ASSUMPTION: rules are written as top-level '- ' bullets; '## ' banners may group them and are exempt from the length limit but count toward the cap | MED | user can correct]`
- `[ASSUMPTION: area files keep raise-with-reason at a 16KB default, and the one-line limit and body check apply to them too | MED — the owner chose raise-with-reason for areas on 2026-09-24; the line format was not separately asked | user can correct]`
- `[ASSUMPTION: citation continuity is a compaction map (old unit hash → new) recorded as ledger events that review-stats joins through, not a change to unit hashing | MED | user can defer]`
- `[ASSUMPTION: in an unattended session, compaction applies everything except drops, and core.md stays frozen over its cap until the owner approves drops | MED | user can override]`

**What would raise confidence:** after Chunk 02, a dry run of `learnings-compact --plan` against
discodon's and hallucinote's corpora (read-only) to confirm that 250/12KB is reachable without
mass drops.

## Status

- [x] Chunk 01: The format and the caps are enforced
- [x] Chunk 02: `learnings-compact` — worksheet, validator, one commit
- [ ] Chunk 03: Every write surface teaches the one-line format
- [ ] Chunk 04: Compact this repo's corpus and move its rulings
Context: Plan written 2026-09-24 from the 3.6.x overhead audit (see the owner conversation; the
fleet figures are re-derivable from each repo's `.prawduct/.governance-ledger.jsonl` and
`.git/prawduct/evidence.jsonl`). A sibling plan for the post-cumulative verify-round change lives on
`feature/post-cumulative-pr-coverage` in its own worktree and shares no files with this one.

**Chunk 01 built and reviewed (commit 18b35c4c), with these departures from its text (recorded, not silent):**
- **Success 4 is met by measuring against HEAD when the marker is missing**, not by base-free checks.
  A base-free format check would grade a not-yet-compacted corpus whole and block every such
  session. HEAD still charges uncommitted growth, and the NOTE says committed growth is not charged.
- **The legacy credit is replaced by a migration-session rule.** When the base holds the legacy file
  and no `core.md`, `core.md` is judged against the corpus total and its lines are not graded
  (they moved). Every later session is per-file. discodon's growth happened INSIDE its migration
  session, so the total rule would still have passed it. Its later growth came through sessions with
  no marker, and the HEAD fallback closes that path.
- **`reflection.md`'s budget paragraph and the template's budget block were corrected in this
  chunk.** The gate falsified them (a 16KB core, agent raises, "never trim"), and a later chunk
  defers deletions, not corrections. Chunk 03 still owns Step 4's rule-shape sentence and the
  other carriers.
- **A frozen corpus grades added lines by content, not position**, so reordering or moving a line
  between files is never "added".
- **`learnings-core-raise-unapproved` is a NOTE at Stop, not a blocker.** The check already ignores
  the raise, so the cap holds without charging the session for the declaration.
- **The freeze is per file, not on the corpus total** (Success 3 said both). A total freeze would
  stop an uncompacted repo adding any scoped rule to an area file under its budget, which the owner
  kept as raise-with-reason. The briefing and the template state the per-file rule.
- **The briefing's directive names `learnings-compact` from Chunk 01 on.** The command lands in
  Chunk 02 of the same release, and nothing ships between them.
- **The migration session grades no file's lines**, area files included (review
  rev-20260924T132555Z-d981bb78, blocker R-3): `learnings-migrate` writes area files from the legacy
  corpus, so their lines are moved too.
- **puzzles, the repo with a 4KB core, is non-compliant too** (584 body lines in its area files).
  The owner's "no bodies anywhere" ruling reaches area files.

**Chunk 02 built and reviewed (commit f1cb80c1), with these departures:**
- **An unapproved drop is refused, not applied as pending.** The agent keeps that rule as a one-line
  rewrite and proposes the drop.
- **`--apply` writes an over-cap `core.md` for any reason, not only pending drops,** and reports it
  as a NOTE (exit 0). The Stop gate's freeze is what holds it: an over-cap file may not grow.
  Refusing the whole compaction would leave the corpus in its worse, non-one-line shape.
- **An interrupted `--apply` is a named state** (review rev-20260924T135450Z-58842bdd, R-2). It keeps
  the worksheet, names what reached disk, and says to restore the rules directory and re-apply, never
  `--plan --force`. The stale-corpus refusal names that route first.
- **`learnings-migrate` is unchanged.** Emitting one-line rules needs judgment the migration cannot
  make without the model. Its output is now followed by the OVER LIMIT directive and this command.
- **"Duplicate clusters" became `related` rows** (up to 3 at ≥ 0.2 word overlap). Rules paraphrase
  each other rather than repeat, so a 0.5 threshold found no pair on this repo's 338 rules. A test
  pins a positive control.
- **The confidence dry run** (2026-09-24; re-derive with `prawduct-hook learnings-compact --plan` in
  each repo, then delete the worksheet):
  - hallucinote has 108 rules with a median length of 84 characters, about 9KB, so it fits 12KB with
    no drops;
  - discodon has 455 rules (357 in core) with a median length of 311 characters. Only 24 name a path
    an area file could claim, and 13 have ever been cited. Reaching 12KB there means moving or
    dropping most of its core.

  **Owner question:** does 12KB stand for discodon, or does its owner raise it (`owner_approved:`)
  for a transition?

**Baseline (2026-09-24):** the declared suite had 1 failure on `origin/develop` that is not this
branch's: `tests/test_pr_evidence_contract.py::TestClosingKeywordClaims` over
`documentation/issues/672-design.md` (added by develop's `a0e90e80`). Flagged to the owner, not fixed here.

## Build Chunks

### Chunk 01: The format and the caps are enforced

- **Description:** The gate half, with no content changes. It adds two base-free checks to
  `record_lint`: a rule line over the limit, and a body line (any non-blank, non-frontmatter,
  non-title, non-banner line that is not a rule unit). It makes `core.md`'s cap a constant only an
  `owner_approved:` field can lift, and it adds the compliant/frozen regimes of Success 1–4.
  - Remove the legacy credit in `_base_size`. The freeze measures `core.md` and the corpus total
    against the session base, so a migration or compaction commit (which does not grow the total)
    passes, and nothing else grows.
  - Retire the `learnings-budget` waiver key. A waiver the agent writes for itself is how a cap
    stops being a cap.
  - The briefing line reports `OVER LIMIT` with the figures and an `agent →` directive to compact.
    The directive names the Chunk 02 command, and until that ships it names this plan.
  - The limit, the cap and the check ids live in one module. `learnings_files.py` is the natural
    home; if the builder finds a better one, record why.
- **Depends on:** none
- **Deliverables:** `plugin/lib/record_lint.py` (new checks, freeze regime, `owner_approved` parsing,
  credit removed), `plugin/lib/learnings_files.py` (constants, compliance predicate),
  `plugin/lib/briefing.py` (`_learnings_lines`), `plugin/bin/prawduct-hook` `cmd_stop` Gate 1c (the
  base-free checks run when the base marker is missing; the waiver key is gone),
  `plugin/hooks/gates.json` (new check ids).
- **Tests:**
  - Each regime, each over/under/grew/shrank cell, the migration commit passing without the credit,
    and the discodon shape (a migration session followed by area-to-core moves) blocking.
  - A same-session raise not counting; an `owner_approved`-less core raise ignored and named.
  - No base marker, with a too-long added line: blocks.
  - The existing tests that pin the credit (`test_the_migration_commit_measures_against_the_legacy_file`)
    and over-but-unchanged silence are renegotiated in the open, per the rule on deliberate red tests:
    the credit is the defect.
  - Red-verify each new check against the real discodon shape. Build that fixture from its real
    history rather than from belief.
- **Acceptance criteria:** the four regimes behave as Success 1–4 state; `cmd_stop` blocks on this
  repo's current corpus only if the session grew it; the briefing names the state.
- **Done when:**
  1. Acceptance criteria met and the affected test files pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: `learnings-compact` — worksheet, validator, one commit

- **Description:** A new verb on the `learnings-migrate` pattern: mechanical where it can be,
  model-filled where judgment is needed, and it refuses rather than guesses.
  - `--plan` writes a worksheet with one row per existing unit: file, text, bytes, times cited
    (`learning.fired`), last touched (git), candidate area files by path mention and existing
    globs, and duplicate clusters. The worksheet is gitignored, under the git dir as `--local`'s
    backup is.
  - The agent fills a disposition per row: `rewrite <text> → <file>`, `merge-into <row>`,
    `moved-to <path>` (for rulings; the command verifies the text now exists there), or
    `drop <reason>` with an `approved: <date>` only the owner's word supplies.
  - `--apply` refuses unless every row is dispositioned, every output line passes Chunk 01's lint,
    caps are met (or `core.md` is over only by rows whose drops await approval), and `moved-to`
    text is found. It then writes the files and records one compaction-map ledger event per
    rewritten or merged unit, so `review-stats` joins citation history through the rewrite and the
    Stop hook does not count rewrites as new rules.
  - It honours `--local` (the #889 path) and refuses on dirty or untracked corpora as migrate does.
  - Fix `learnings-migrate` so it stops emitting bodies. A repo still migrating from legacy should
    land one-line rules directly, not bodies that compaction must undo.
  - `/prawduct:doctor` gains the check that runs this flow.
  - A persisted format needs its questions first. The worksheet is transient, but the
    compaction-map event is not. Its consumers are `review-stats`' `learning` block and the Stop
    hook's `learning.written` diff, so list the queries each makes before designing fields.
- **Depends on:** Chunk 01
- **Deliverables:** new `plugin/lib/learnings_compact.py`, `plugin/bin/prawduct-hook`
  (`cmd_learnings_compact`), `plugin/lib/learnings_migrate.py` (no bodies),
  `plugin/lib/ledger.py` (the map event, machine-only) and `plugin/lib/telemetry.py` (join through
  the map), `plugin/skills/doctor/SKILL.md`, `.prawduct/artifacts/api-contract.md` (the verb and
  exit codes).
- **Tests:**
  - Carried from Chunk 01's verify pass (rev-20260924T134116Z-8bc3ba33, O-1): a Stop test for a
    repo with no base marker AND no commits, whose NOTE says HEAD did not resolve.
  - Worksheet round-trip.
  - Each refusal named.
  - A drop without approval refused.
  - A `moved-to` whose text is absent refused.
  - An unattended apply leaving `core.md` frozen over its cap.
  - Citation history surviving a rewrite in `review-stats`.
  - Mirror `tests/test_learnings_migrate.py`'s structure (interrupted apply, refusals, `--local`) —
    copy the precedent's test cases before writing new ones.
  - At least one test reads a real corpus, not only fixtures.
- **Acceptance criteria:** Success 5. A read-only `--plan` against discodon's and hallucinote's
  corpora produces a complete worksheet (this is the confidence check).
- **Done when:**
  1. Acceptance criteria met and the affected test files pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Every write surface teaches the one-line format

- **Description:** Replace the guidance that caused the regrowth, and delete the sentences it
  replaces rather than appending exceptions after them.
  - `reflection.md` Step 4: one line of at most 250 characters, with the instance as a clause if it
    helps. If it does not fit, it is two rules or it is narrative (`.session-reflected`). At the
    cap, merge or retire a rule; never raise `core.md`.
  - Delete "never trim a rule to fit" and the five-part "good rules have" list.
  - The `cmd_stop` reflection blocker's rule sentence.
  - `review-cycle.md`'s rule-pass bullet, which becomes a check against the format.
  - `janitor/SKILL.md`.
  - `CORE_HEADER` (the scaffold states the format, so a new repo starts right).
  - `templates/project-state.yaml`'s `learnings_budgets` block. Correct its stale claim that
    `verify-records` is where the budget blocks.
  - `docs/norms.md`, if the ruling home changes (see Chunk 04).
  - The NFR amendment under its norm, in the norm's own section, with the owner's words, never by
    editing the clause itself.
  - The change-log entry, which is the release note. It covers every chunk and states the contract
    change (the `owner_approved` field) and the directive consumers will see.
  - Enumerate carriers by two vocabularies before editing ("heading that carries", "instance that
    earned it", "trim", "budget", "raise"), and pin each carrier plus the retired wording's absence
    in one test, as `tests/test_suite_at_boundary.py` does.
- **Depends on:** Chunk 01 (the numbers the prose cites)
- **Type:** doc-only
- **Deliverables:** the files named above, `tests/test_v5_methodology.py` (re-measured token
  readings, with ceilings ratcheted in the same commit), and a new carrier test.
- **Carried from Chunk 02's verify pass (rev-20260924T141043Z-7ef33ffc) — code fixes riding this
  chunk's commit:**
  - O-1: the `--local` backup-location refusal is a `raise`, so neither the count test nor any
    test sees it. Pin it.
  - O-2: the "not in the worksheet" refusal must name restore-and-reapply first, as the
    stale-corpus one does. An interrupted apply that created an area file reaches it.
  - O-4: a merge-into case whose target rewrite names an unknown file.
  - O-5: the test module docstring's claim that `TestRefusals` covers every route.
- **Tests:** a carrier pin with an absence assertion per retired phrase, red-verified against a
  rewording rather than the literal; re-measured budgets.
- **Acceptance criteria:** Success 6. No carrier still instructs the multi-part heading form.
- **Done when:**
  1. Acceptance criteria met and the affected test files pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Compact this repo's corpus and move its rulings

- **Description:** Use the tool on this repo (287 `core.md` units at a mean of 370 characters, plus
  four area files of 11–23KB).
  - Run `--plan`, and fill the worksheet with parallel delegates by row range if that finishes
    sooner. The integrator owns the worksheet.
  - Route RULING entries to the governing artifact they rule on, and update `docs/norms.md` links
    and every `[[ruling-name]]` citation.
  - Present drops to the owner triaged: the decision-worthy ones individually, the obvious ones
    grouped for a single yes.
  - Apply, then update the tests that read this repo's corpus (`TestAgainstTheRealCorpus`'s `>100`
    floors, `TestThisReposOwnCorpus`). Each floor says which emptiness it rejects rather than
    pinning today's count.
  - Remove `core.md`'s `learnings_budgets` entry and its roughly 10KB of raise reasons.
- **Depends on:** Chunk 02, Chunk 03
- **Deliverables:** `.claude/rules/learnings/*.md`, the governing artifacts receiving rulings,
  `docs/norms.md`, `.prawduct/project-state.yaml`, `tests/test_learnings_files.py`.
- **Tests:** the corpus tests above; the full suite (this chunk is the boundary).
- **Acceptance criteria:** Success 7. `core.md` ≤ 12KB; `prawduct-hook verify-records` clean; the
  briefing reports compliant.
- **Type:** cumulative-final
- **Done when:**
  0. Owner has approved the drop list (the triaged presentation, not all 287 rows)
  1. Acceptance criteria met and the declared suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review. The branch is PR-ready after Chunk 04's
cumulative; `/prawduct:pr create` when the owner asks.

- After Chunk 01: confirm with the owner that the freeze regime is not blocking ordinary sessions
  on this repo (it should block only growth).
- After Chunk 02: the discodon/hallucinote dry runs decide whether 250/12KB stands.
- Before Chunk 04's apply: the owner's drop sign-off.
