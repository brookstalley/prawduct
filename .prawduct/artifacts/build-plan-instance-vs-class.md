---
artifact: build-plan
version: 2
scope: instance-vs-class
branch: fix/instance-vs-class
depends_on: []
governed_by:
  - artifact: api-contract
    dispositions:
      - "inapplicable because this plan changes review prose and the learnings corpus, no CLI surface"
last_validated: 2026-08-17
---

## Requirements Confidence

**Level:** High

**Why:** The problem is observed, not inferred — three instances in one session
(`fleet-feedback-661`), each caught by a reviewer rather than by me, plus a corpus survey
that found ~18 existing rules across three families all circling it. Success is statable:
a reviewer must answer instance-or-class on any site-naming finding, using a tell that is
mechanical rather than evocative.

**Open assumptions / unknowns:**

- [ASSUMPTION: the rule ships as review prose, not as a required finding-schema field |
  HIGH impact | user can override] Findings are JSON (`name`, `severity`, `files`), so a
  required field cascades into `critic-reviewer.md`, `critic_consolidate.py` and the lint —
  four budgeted surfaces. **This assumption is in genuine tension with the session's own
  lesson** that a check which can be silently skipped is skipped, and prose is skippable.
  It is taken because every one of the Critic's seven goals is already prose: the observed
  defect is that *this* prose was absent, not that prose does not work. The escalation
  trigger is named in Chunk 01 rather than left to judgment.
- [ASSUMPTION: this branches off `fix/661-fleet-feedback` rather than `develop` | MED
  impact | user can override] That branch is complete and unmerged, and both touch
  `learnings.md`; branching off `develop` guarantees a conflict there. The cost is that
  this branch carries 661's commits until 661 lands. **Cleaner alternative: PR and merge
  661 first** — it is finished, all gates satisfied — then branch this off `develop`.

**What would raise confidence:** Nothing blocking.

## Status

- [ ] Chunk 01: A finding says whether it is an instance or a class, and the remedy is graded
- [ ] Chunk 02: Eighteen scattered rules become three sharp ones
Context: Plan written 2026-08-17 after the `fleet-feedback-661` branch produced three
instances of the defect it describes. Chunk 01 first: Chunk 02's consolidated wording must
match the vocabulary Chunk 01 establishes, or the corpus and the protocol disagree about
what a class is. Next: Chunk 01.

## Verification Strategy

Prose changes, so verification is adversarial reading plus the guardrail tests: the six
Critic skill files carry hard token ceilings with a "what paid for it" narration discipline
(`tests/test_v5_methodology.py::LAST_MEASURED_TOKENS`), and `learnings.md` carries a
400-char-per-rule lint (`record_lint`'s `learnings-entry-shape`).

The real test is retrospective and is Chunk 01's acceptance criterion: apply the drafted
rule to the three findings this session actually produced and confirm it fires on each. A
rule that cannot catch the defects that motivated it is the vacuous-guard class again.

## Build Chunks

### Chunk 01: A finding says whether it is an instance or a class, and the remedy is graded

- **Description:** A finding that names a site gets fixed at that site, and the class
  survives. Observed three times in one session: `update-gitignore` fixed and
  `coverage-scaffold` missed; those two fixed and `migrate-plugin` + `init-product` missed
  (the cutover and the scaffolder, both mutating on `--dry-run`). Each time a reviewer
  caught it, so the review is where the knowledge already is — the builder-side rules did
  not fire because at write time you believe you are fixing a bug, not a class.

  Two halves, and the second is what makes it more than a longer list. **The tell must be
  mechanical:** state the defect's reason in one sentence; if that sentence does not name
  the site you found, the finding is an instance and the reason defines the class. (Mine
  was *"the `"--flag" in argv` idiom reads an unknown token as absent"* — names an idiom,
  not a command, so grepping the idiom bounds the class.) **And the remedy is graded:**
  fixing the enumerated members does not resolve a class finding when the class is
  unbounded — only a construction does (one owner every member passes through, or a check
  derived from the source of truth). Family B below is the evidence for this: six existing
  rules independently record that the naive search under-reports, so an enumeration is not
  a reliable resolution even when attempted in good faith.

  **Escalation trigger, stated now rather than left to judgment** (the prose-vs-schema
  assumption): if a review after this ships produces a site-naming finding that does not
  answer instance-or-class, prose has failed and the answer becomes machine-checkable —
  cheapest form is a lint on findings whose `files` array has ≥2 entries, asking whether
  the text answers it.
- **Depends on:** none
- **Artifacts consumed:** this session's `.prawduct/.session-reflected`; the three findings
  in `rev-20260817T211246Z-cd033794` and `rev-20260817T213600Z-f4a0f50e`
- **Deliverables:** the rule in `plugin/skills/critic/review-protocol.md` (currently 3799
  tokens, budgeted — the addition must be **funded from within the file** and the narration
  must say what paid); the resolution-grading half in
  `plugin/skills/critic/review-cycle.md` (9599, budgeted) where `verify-resolutions` is
  defined; updated readings in `tests/test_v5_methodology.py::LAST_MEASURED_TOKENS`
- **Tests:** the existing budget guardrails must pass with updated readings — no ceiling
  raised (a raise needs the separate justification `learnings.md` already demands)
- **Acceptance criteria:** applied to the three findings this session produced, the drafted
  tell fires on each and names the right class; no Critic file's ceiling is raised; every
  budget narration says what paid for the addition
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Eighteen scattered rules become three sharp ones

- **Description:** The corpus has the same disease it describes. A survey of
  `learnings.md` found roughly eighteen rules across three families, each written at the
  altitude of the incident that produced it, so the general statement is buried among its
  own paraphrases and none of them fired this session:

  - **Family A — the fix has relatives** (~8: L345, L497, L551, L273, L423, L281, L285,
    L453). L345 already states it well and generally; L551 states it as "a rule discovered
    on one branch of a dispatch table governs its siblings," which is one incident's shape
    wearing general clothes — it names a data structure that need not exist, a relation
    (siblings) that is only one of several, and a tell ("your fix is a table row") that does
    not fire for a fix inside a handler.
  - **Family B — the search under-reports** (~6: L283, L375, L473, L481, L411, L433).
    Distinct and load-bearing: even knowing it is a class, grepping the identifier misses
    the prose, the paraphrase, and the silent drop.
  - **Family C — define the class by property, not container** (~4: L405, L383, L539, plus
    `methodology/planning.md`'s "Line-number scoping" trap).

  **B and C are kept and sharpened, not deleted.** An earlier read of this corpus called
  the whole set "~12 restatements of one rule"; the careful read is three rules, and acting
  on the first read would have destroyed real content. That correction is itself an instance
  of Family C — the class was defined by a keyword match rather than by the property.
- **Depends on:** Chunk 01 (the consolidated Family A rule must use Chunk 01's vocabulary
  for "class", "premise" and "construction", or the corpus and the protocol disagree)
- **Artifacts consumed:** `.prawduct/learnings.md`, `.prawduct/learnings-detail.md`
- **Deliverables:** three rules in `.prawduct/learnings.md` replacing the ~18; the retired
  rules' evidence preserved in `.prawduct/learnings-detail.md` under the surviving headings
  — **narrative moves, it is never deleted**
- **Tests:** `record_lint`'s `learnings-entry-shape` clean (each surviving rule ≤400 chars);
  `prawduct-hook learnings-obligation` ok; no `[[wikilink]]` left pointing at a deleted rule
- **Acceptance criteria:** the three survivors each state a mechanical tell; every retired
  rule's distinguishing evidence is findable in `learnings-detail.md`; total rule count
  drops by ~15 with no loss a reader could name
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
