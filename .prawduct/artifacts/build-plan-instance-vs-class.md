---
artifact: build-plan
version: 2
scope: instance-vs-class
branch: fix/instance-vs-class
depends_on: []
governed_by:
  - artifact: api-contract
    dispositions:
      - "error model (a boundary returns a diagnostic, never a traceback) → conforms — the
        `--chunk` label normalisation removes a case that reached record-lint as an unrunnable
        check rather than a diagnostic"
      - "versioning/deprecation → inapplicable because no published surface changes shape;
        `--chunk` gains an accepted input form and refuses none"
      - "published surfaces are read-only and allowlistable → conforms — no exit code on
        `version` or `print-install-reference` moves"
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

- [x] Chunk 01: A finding says whether it is an instance or a class, and the remedy is graded
- [x] Chunk 02: Eighteen scattered rules become three sharp ones
- [x] Chunk 03: Uplevel the repeated shapes in review-protocol.md (unblocks Chunk 01)
Context: Plan written 2026-08-17 after the `fleet-feedback-661` branch produced three
instances of the defect it describes. **Order reversed by operator decision 2026-08-17**
(the "Open decision" below, option C): Chunk 01 was blocked on a token-budget ruling, and
Chunk 02 had no such constraint. The stated dependency ran fine in reverse — the vocabulary
for *class*, *premise* and *construction* got settled in the consolidated learnings rule,
and Chunk 01 now CITES it rather than restating it. Chunk 02 DONE (17 rules to 3, reviewed,
one blocking fix). Chunk 03 DONE (`review-protocol.md` 3799 → 3671, ceiling untouched at
3800; reviewed, one blocking fix plus four demoted, all fixed rather than accepted).
**ALL THREE CHUNKS DONE (2026-08-18).** Chunk 01 shipped the rule to `review-protocol.md`
(3671 → 3794, ceiling untouched at 3800) and to
`critic_consolidate.RESOLUTION_IS_A_CLAIM_DIRECTIVE`, with `chunk` mode explicitly descoped —
see the two DECISION blocks on Chunk 01. Reviewed by `cumulative`
`rev-20260818T175424Z-bd5c4bf5` (0 blocking, 2 warning, 10 note; **every finding carried the
`Scope:` slot this chunk added, and both warnings graded themselves `class`**) and closed by
`verify-resolutions` `rev-20260818T181936Z-d7ef1f87` (0 findings, both warnings verified
`fixed` by construction). PR gate satisfied. **Plan is complete; the branch is PR-ready.**

**Owner decision still open, carried past plan close:** fund `goals-1-3.md` so `chunk` mode
gets the rule (a ~70-token ceiling raise or its own uplevel chunk), or leave `chunk` mode on
the escalation trigger. The same decision covers `review-cycle.md`'s `## Per-Chunk Output
Format` and `goals-1-3.md`'s report contract, the two sibling templates that did not get the
`**Scope:**` slot.

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
- **[DECISION 2026-08-18: the second deliverable moves from `review-cycle.md` to the
  verify-dispatch directive, and the deliverable list was itself instance-shaped.]** The list
  above names two files. The class is *every surface a reviewer reads while writing or grading a
  site-naming finding*, and its members are fixed and enumerable: `review-protocol.md`
  (`final`/`cumulative` — the single-pass fork and all three coordinator reviewers),
  `goals-1-3.md` (`chunk` and `verify-resolutions`, which it orders to open nothing else), and
  `critic_consolidate.RESOLUTION_IS_A_CLAIM_DIRECTIVE` (printed at `verify-resolutions`
  dispatch). `review-cycle.md` is on none of those paths — the file says so itself where it
  records that fix-by-fudging's workaround leg "was rated only here, in a file this mode's
  reviewer is forbidden to open." Shipping the grading half there puts it where its actor
  cannot read it. It goes into the claim directive instead, which already carried the rule in
  instance form — *"a finding whose second site is in a file this delta does not touch"* — a
  list of two where the property was meant; sharpening that clause is the change, and the
  reader is the reviewer at the moment it writes `resolutions`. Licensed by `architecture.md`
  § Direction GOV-4T9P: a plan's named call sites are the author's guess made before the code
  was read; goals and verification bind, prescribed method is advice.
- **[DECISION 2026-08-18: `chunk` mode is explicitly descoped, not silently dropped.]**
  `goals-1-3.md` is at 2247 against a `< 2250` ceiling — 2 tokens, under its own standing
  "THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP". The compressed rule costs ~65.
  Funding it means either an owner ruling on the ceiling or a scoped uplevel pass in a second
  budgeted file, which this plan already refuses to bundle into a chunk that adds a rule. What
  ships covers `final`, `cumulative` and `verify-resolutions`; **all three observed instances
  came from those modes** (`cd033794` was `cumulative`, `f4a0f50e` was `verify-resolutions`),
  and a `chunk`-mode finding still meets the rule one round later at the verify pass that
  grades its fix. Open for the owner: fund `goals-1-3.md` (a ~70-token raise, or its own
  uplevel chunk), or leave `chunk` mode on the escalation trigger above.
  - **The gap is three surfaces in two files, found by applying this chunk's own rule to this
    chunk's own diff.** `review-protocol.md`'s `## Output Format` was the template the plan
    named; the reason it needed a slot — *a template is filled every time and a paragraph is
    re-read never* — names no file, so it is a class. Its other two members are
    `review-cycle.md`'s `## Per-Chunk Output Format` (line 453, the same
    `**Goal:**`/`**Severity:**`/`**Recommendation:**` shape, no `**Scope:**`) and
    `goals-1-3.md`'s prose report contract, which enumerates the fields to report back. Both
    sit in the two files with 1 and 2 tokens of headroom, so the single funding decision above
    covers the whole remaining class rather than leaving a second item to rediscover.
  - **Checked and clean, so it is not an open risk:** `critic_consolidate.validate_partial`
    tolerates an unrecognized key on a finding, so a reviewer that mirrors the new markdown
    slot into its JSON partial as `"scope"` does not fail the consolidation closed. Verified by
    calling the validator, not by reading it.
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
  - **[DECISION 2026-08-18: the yield criterion lands at 128, not ≥150, and the first check
    is why.]** The 634-token scan measured what the six shapes *cost*, not what they could
    give back. A first draft hit 153 and the Critic found 31 of them were deletions, not
    merges: Signals' work-type mapping had been redirected to the chunk `Type:` selector — a
    different axis, whose real home is a builder-side file no reviewer opens — and the flat
    stale-artifact `WARNING` had been folded under the prose ceiling, quietly letting a stale
    `architecture.md` grade NOTE. Both restored, and the criterion above is the one that
    caught it. Closing the remaining 22 means shaving load-bearing prose, which is the trade
    this file's budget comment has refused for five consecutive edits. 128 tokens of headroom
    against an untouched 3800 ceiling is what Chunk 01 has to work with.
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
