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
- [x] Chunk 02: Eighteen scattered rules become three sharp ones
- [ ] Chunk 03: Uplevel the repeated shapes in review-protocol.md (unblocks Chunk 01)
Context: Plan written 2026-08-17 after the `fleet-feedback-661` branch produced three
instances of the defect it describes. **Order reversed by operator decision 2026-08-17**
(the "Open decision" below, option C): Chunk 01 is blocked on a token-budget ruling, and
Chunk 02 has no such constraint. The stated dependency runs fine in reverse — the vocabulary
for *class*, *premise* and *construction* gets settled in the consolidated learnings rule,
and Chunk 01 then CITES it rather than restating it. Chunk 02 is DONE (17 rules to 3,
reviewed, one blocking fix). Next: Chunk 03 (the uplevel), which unblocks Chunk 01.

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
- **Design improvement found during build — a required SLOT, not a paragraph.** The
  original design was prose in `## Severity Levels`. Better: the finding output template
  (`## Output Format`) gains `**Scope:** instance | class — <the premise>`. A slot in a
  template the reviewer fills for every finding is much closer to un-skippable than a
  paragraph it may not re-read, it costs fewer tokens than the prose form, and it
  substantially resolves this plan's prose-vs-schema tension without touching the JSON
  contract in `critic-reviewer.md` / `critic_consolidate.py`. Precedent for treating
  placement as substance: `tests/test_v5_methodology.py::assert_inert_count_cap` already
  asserts *where* a rule sits, not just that it exists.
- **BLOCKED ON A FUNDING DECISION — see "Open decision" below.** `review-protocol.md` is at
  3799 against a `< 3800` ceiling: **zero headroom**, under a standing rule that reads "THE
  NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP." Every sibling is also at its ceiling
  (`review-cycle.md` 9599/<9600, `goals-1-3.md` 2247/<2250, `building.md` 4806/<4810); only
  `framework-checks.md` has slack (33) and it is the wrong home — framework-only, while this
  defect bit a code change. I read the file looking for slack: its budget comment claims it
  is audited lean and I agree — every goal bullet is a specific, severity-mapped check.
- **Deliverables:** the `**Scope:**` slot + its rule in
  `plugin/skills/critic/review-protocol.md`; the resolution-grading half in
  `plugin/skills/critic/review-cycle.md` where `verify-resolutions` is defined; updated
  readings in `tests/test_v5_methodology.py::LAST_MEASURED_TOKENS`
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
- **Depends on:** none. (Was "Chunk 01", reversed by operator decision — this chunk now
  ESTABLISHES the vocabulary for *class*, *premise* and *construction*, and Chunk 01 cites
  it. Same coupling, opposite direction, and it unblocks the budget-constrained chunk.)
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

## Open decision — how Chunk 01 is funded

`learnings.md` L397 states the raise rule: *a token budget is raised only when the framework
is provably better FOR THE RAISE and upleveling has no headroom left — cut the class, not the
words.* Both halves have to be answered, and the second is answered: I looked, and the file
is lean. So the question is only which of these pays.

**A — collapse the declaration→obligation class in Goal 2.** `Foreign API`, `Exposed API`
(two decisions), `Operator verification` and `Requirements Confidence` are five bullets of
one shape: *chunk declares X ⇒ owes Y in Done-when → WARNING if absent.* Stating it once at
the property level frees an estimated 80–120 tokens and would be an instance of the very rule
being added. **Against it:** it is a real behaviour change to five live checks, the specific
trigger tokens are what make them fire, and funding a new rule by refactoring load-bearing
checks produces two half-reviewed changes in one commit. If this is taken it deserves its own
chunk and its own review, not the status of a funding source.

**B — raise the ceiling by ~60, with the justification recorded.** This is the case the raise
rule contemplates: the addition *removes* review work rather than adding it. One defect on
`fleet-feedback-661` cost three review rounds (~15 min of Opus review each) because the class
was re-found twice; a rule that ends that pays for its own tokens on first use. **Against it:**
the ceiling has been raised exactly once before, by owner ruling, and the standing posture is
explicitly "trims or relocates."

**C — build Chunk 02 first.** The learnings consolidation has no budget constraint and real
standalone value; Chunk 01 then cites the consolidated rule rather than restating it, which
may itself be cheaper. Reverses this plan's stated dependency (Chunk 01 was ordered first so
Chunk 02 could inherit its vocabulary) — workable in reverse, since the vocabulary can be
settled in the learnings rule and cited by the protocol.

**Recommendation: B, then C, leaving A as its own scoped chunk if wanted.** The raise rule's
two conditions are met and the arithmetic is favourable; A is worth doing on its merits but
not as a side effect of paying for something else.

**This is the operator's call by construction**, not a preference: the budget comment records
that the ceiling moves by owner ruling.


### Chunk 03: Uplevel the repeated shapes in review-protocol.md

- **Description:** Added 2026-08-17 after the operator asked whether classes could be
  upleveled rather than a ceiling raised. A measured scan says yes, and by more than Chunk 01
  needs: **~634 of 3799 tokens sit in six repeated shapes.** Goal 4 drift family 252; Goal 2
  declaration→obligation 163; Signals 96; `infrastructure_dependencies` checked in BOTH Goal 2
  and Goal 4, 50; Goal 5 missing-rationale 45; a Goal 4 norms bullet restating the Normative
  authority block, 28.

  **The discriminator, which is the whole substance of this chunk.** A class uplevels when
  the general form is *actionable without the enumeration*, and must stay enumerated when the
  enumeration IS the trigger.
  - **Uplevels:** Goal 4's five bullets are one property — *a description whose subject
    moved*; artifact, comment, README, docstring and renamed term are containers, not
    distinct checks. Goal 5's three are *a decision recorded without its why*. The
    `infrastructure_dependencies` pair is one check written twice. The Goal 4 norms bullet is
    already stated above it.
  - **Must NOT uplevel:** Goal 2's declaration→obligation bullets are literal string matches
    (`Foreign API:` ⇒ a `verify-api` step; `Exposed API:` ⇒ two named `design_decisions`
    keys; `Visual change: yes` ⇒ an operator-verification entry). "A declaration creates an
    obligation" names neither the string to find nor the thing owed, so collapsing them
    silently stops three checks firing — the vacuous-guard failure, shipped into the
    reviewer. `framework-checks.md` Check 7 already governs this: *when only the enumerated
    form is workable, say why the general form fails here* — so the chunk RECORDS that
    reason rather than leaving the non-merge unexplained.
- **Depends on:** none. Unblocks Chunk 01 by leaving headroom, but stands on its own merits —
  it is deliberately NOT folded into Chunk 01's commit, because funding a new rule by
  refactoring load-bearing checks ships two half-reviewed changes as one.
- **Artifacts consumed:** `plugin/skills/critic/review-protocol.md`; `framework-checks.md`
  Check 7 (the governing rule for the non-merge)
- **Deliverables:** upleveled Goal 4 and Goal 5 sections, the duplicate
  `infrastructure_dependencies` check resolved to one home, the restated norms bullet removed,
  in `plugin/skills/critic/review-protocol.md`; updated reading in
  `tests/test_v5_methodology.py::LAST_MEASURED_TOKENS`
- **Tests:** the file's own budget guardrail passes with a LOWER reading and an unchanged
  ceiling; `assert_inert_count_cap` still passes (it asserts placement inside the NOTE legend
  entry — do not disturb it)
- **Acceptance criteria:** every check that fired before still fires — verified by walking
  each removed bullet and naming which surviving sentence now carries it, not by reading the
  new prose and finding it plausible; ≥150 tokens recovered; no ceiling raised
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
