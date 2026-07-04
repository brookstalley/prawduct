<!-- Build Plan — prose-diet (MET-3Q8V)
     For HOW to build (governance, test discipline, Critic review), read
     /prawduct:building before starting.
-->
---
artifact: build-plan
version: 1
scope: prose-diet
depends_on: [framework-efficiency-review-2026-07-02.md]
last_validated: 2026-07-02
---

# Build Plan — prose-diet (MET-3Q8V, Wave 1 Plan C)

## Requirements Confidence

**Level:** High

**Why:** Parent requirement is the owner-accepted efficiency review
(`framework-efficiency-review-2026-07-02.md`, Overbuilt #3 + Wave 1 Plan C). Every cited
site was re-verified against HEAD on 2026-07-02 (scout report; all claims held, line
numbers refined). The judgment-heavy decisions — which side wins each contradiction, what
"single-source" means per copy — are recorded below, in this plan, so execution (possibly
on a smaller model) applies decisions rather than making them.

**The problem:** the governance cycle loads ~28k words (~36k est. tokens) of prose that
triplicates content (mode×type matrix ×3, stance ×3, fallback rule ×5), ships
implementation narration (bug IDs, hook internals, a parser-bug story inside the starter
template), contradicts itself in 5 documented places, and compresses load-bearing rules
into identifier-dense sentences weaker models can't parse (building.md:284).

**Success (measured, achieved):** the **cycle-load set** — `methodology/*.md` (all 7),
`templates/build-plan.md`, `skills/critic/{SKILL,review-protocol,review-cycle,framework-checks}.md`,
`skills/{building,discovery,planning,reflection}/SKILL.md` — dropped from its measured
baseline (28,455 words / 36,991 est tokens at b3b641f) to 19,838 words / 25,789 est tokens,
**−30.3%**, using the test suite's estimator (`words × 1.3`). Hard constraint (held): **no
rule, gate semantics, or checkable bar was dropped** — every behavior the prose specifies
survives in exactly one place (Complete Delivery outranks the number). The original floor was
**≥45%, targeting 50%**; that intuition mispriced the corpus — it assumed triplication was the
bulk of the mass, but single-sourcing recovered only ~3–4k est tokens, ~2.6k of in-set chain
machinery was carved out to review Overbuilt #4, and the review program had already certified
review-protocol lean. Honest preservation over a rule-dense, no-drop corpus reaches ~30%; the
residue is enumerated in the change-log (`scope=prose-diet`) and is a measurement of rule
density, not remaining waste. The 5 contradictions read one way everywhere. Lowered
token-budget tests lock the diet in.

**Out of scope:** the two-reviewer overlap machinery (review Overbuilt #4 — ~2k words of
chain/scope prose in the critic/pr protocols: separate item); STN-4W7R part (b)
(checkpoint-attached advisory obligations — Wave 2); `docs/principles.md` structure (23
numbered principles are test-pinned; only stance-overlap trimming inside bodies);
`CLAUDE.md` beyond reference repoints and the two reflection-cadence sentences;
`session-digest-slim.md` beyond mechanical sync with the full digest; any hook/gate
*behavior* change (string/message edits only).

**Recorded decisions (the reconciliations — each is vetoable):**

- **D1 (contradiction a — per-chunk Critic vs 1–3-chunk session cap):** both rules stand;
  they compose. Add one bridging sentence in `methodology/building.md` ("a multi-chunk
  plan spans multiple sessions; per-chunk reviews accumulate and the final/cumulative
  lands with the last chunk — session boundaries don't reset the plan") and delete any
  phrasing implying plan == session.
- **D2 (contradiction b — PR default vs template cadence):** "don't create PRs unless
  asked" wins (owner preference, enforced in digest). The template's cadence example is
  reworded to describe *readiness*, not action: the last chunk's cumulative review is the
  PR gate *when the user asks*.
- **D3 (contradiction c — final-mode fallback stated 5 ways):** canonical statement lives
  in `skills/critic/review-cycle.md` (the enforcement site), worded: "If the mode is
  missing, unrecognized, or inference cannot make a confident call, run `final`." All
  other sites (building.md:227, planning.md:112, review-protocol.md:24,
  template) compress to at most one short sentence + pointer.
- **D4 (contradiction d — reflection cadence):** prescribed cadence is work-boundary
  reflection; the stop hook enforces only a session-end floor (existence + content).
  `methodology/reflection.md`'s "the hook enforces the habit, not the cadence" becomes
  the single explanation; CLAUDE.md and building.md each keep one sentence consistent
  with it (floor ≠ cadence), duplicated explanations deleted.
- **D5 (contradiction e — discovery question counts vs "not a state machine"):** keep the
  numeric shapes but reframe once as "typical shape, not a quota," explicitly governed by
  the existing judgment sentence (discovery.md:103). Weaker models need the concrete
  anchors (Wave 3 thesis); the numbers stop being thresholds.
- **D6 (what "single-source the matrix" means):** `methodology/planning.md` is the
  canonical *definitional/decision* source (modes, Types, when to override).
  `skills/critic/review-cycle.md` keeps only its *behavior tables* (per-mode goals/scope
  columns, per-Type protocol selector) minus re-definitions — it is the Critic's
  selector, not a duplicate. `templates/build-plan.md`'s 673-word comment copy becomes a
  ~5-line pointer + bare field syntax. `review-protocol.md`'s partial copy compresses to
  the minimum the forked Critic needs inline.

**Open assumptions / unknowns:**
- [ASSUMPTION: delegator fold = full deletion of `skills/{building,discovery,planning,reflection}/`
  with every reference rewritten to `/prawduct:methodology <topic>` (the routing already
  exists), including 5 `bin/prawduct-hook` message strings and 2 `lib/` strings; a user
  typing `/prawduct:building` from habit gets "skill not found" and adapts | MED impact |
  user can override → keep the 4 skills as thin aliases instead]
- [ASSUMPTION: `methodology/agent-stance.md` is deleted; the session-digest stance block
  becomes the sole operational stance surface, rewritten advisor-first — this delivers
  STN-4W7R part (a) inside this plan; the checkable-bar elaborations worth keeping move
  into the digest block (budget ~250 words), the rest (register framing, honesty-taxonomy
  mapping) is dropped as rationale that lives in principles | MED impact | user can
  override → keep agent-stance.md as the long-form and diet it instead]
- [ASSUMPTION: updating prose-pinning tests alongside the prose they pin is
  spec-following, not test-weakening — the requirement (this plan) changed; token-budget
  ratchets are *lowered* to post-diet size +10% headroom as the diet's enforcement
  mechanism | LOW impact]

**What would raise confidence:** N/A (owner veto window on the assumptions above).

## Status

- [ ] Chunk 01: Structural moves — reconcile, single-source, filled-example template
- [ ] Chunk 02: Editorial compression pass over the cycle-load prose
- [ ] Chunk 03: Fold the redundant surfaces (delegators, agent-stance) + advisor-first digest
Context: Chunks 01+02 done 2026-07-03 (45c152a, 259e5d2; Critic-clean). Chunk 03 COMPLETE
and cumulative-reviewed (b4d569e + close-out commits). The cumulative Critic's 1 BLOCKING —
measured reduction 36,991 → 25,789 est tokens (−30.3%) vs the ≥45% acceptance floor — was
resolved 2026-07-04 by owner decision (a): the Success floor is amended to the honest
achieved figure (−30.3%). Rationale: the floor cannot be met without dropping rules or the
weaker-model anchors; the 45–50% intuition mispriced a rule-dense, no-drop corpus (chain
machinery ~2.6k = out-of-scope Overbuilt #4; review-protocol audited lean; irreducible
behavior tables; single-statement rules). Residue enumerated in the change-log entry
(`scope=prose-diet`) — a measurement of rule density, not remaining waste. All other
cumulative findings resolved on-branch: change-log entry written (statusless), 4 backlog
items reconciled (STN-4W7R(a) delivered/refs repointed, MET-2X6F noted, MET-7R4J trimmed,
CRT-5Q8W checked — none absorbed), duration-drift + READER_SKILLS + frontmatter-quoting
notes fixed. MET-3Q8V archived shipped 2026-07-04. Chunk-02 Goal-2 NOTE confirmed by the
cumulative: the two trimmed building.md lines were elaboration, not rule loss.

## Scaffolding

Existing repo. Tests: `python -m pytest tests/test_v5_methodology.py tests/test_v5_templates.py tests/test_plugin_methodology_digest.py tests/test_plugin_manifest.py -q`
while iterating; full suite (1533 at branch point) before each commit. Measurement
harness: a scratchpad script computing `wc -w`-based estimator tokens per cycle-load file
(baseline captured in chunk 01, re-run at each chunk close; final numbers go in the
change-log entry). Verify skill routing via repo-local plugin files; `claude plugin
validate` after any `skills/*/SKILL.md` frontmatter change (YAML-quoting learning).

### Verification Strategy

1. **Measurement:** baseline vs post-chunk token estimate per file and total; the ≥45%
   floor is an acceptance criterion of chunk 03, not a per-chunk gate.
2. **No-dropped-rule audit:** for each deleted/compressed passage, the rule it stated is
   findable at its single surviving site — chunk-close self-check, then the cumulative
   Critic's Goal 2 (Nothing Is Missing) is the independent pass; the plan's decision list
   D1–D6 is the checklist.
3. **Form-family grep sweeps** (learnings: enumerate the whole family): after chunk 03,
   `agent-stance`, `/prawduct:building|discovery|planning|reflection`,
   `prawduct:(building|discovery|planning|reflection)`, `skills/(building|discovery|planning|reflection)/`
   return zero hits in active surfaces (methodology/, skills/, templates/, CLAUDE.md,
   bin/, lib/, docs/) — historical files (CHANGELOG, learnings, .prawduct state) exempt.
4. **Live routing:** `/prawduct:methodology building` opens the guide; digest
   `additionalContext` stays < 10,000 chars; slim ≤ half of full (existing tests).
5. **Weaker-model readability spot-check:** the rewritten building.md:284-class sentences
   contain no nested appositives, no set-theory glyphs, no bug-ID citations.

## Build Chunks

### Chunk 01: Structural moves — reconcile, single-source, filled-example template

- **Description:** Apply D1–D6. Scope by pattern: *every site stating a reconciled rule
  or a matrix definition*, not line addresses.
- **Depends on:** none
- **Deliverables:**
  - Contradiction reconciliations D1–D5 applied at every site the scout enumerated
    (building.md, planning.md, discovery.md, reflection.md, review-cycle.md,
    review-protocol.md, templates/build-plan.md, CLAUDE.md reflection sentences).
  - D6 single-sourcing: template comment block (lines ~221–296) → pointer + field syntax;
    review-cycle.md drops re-definitions, keeps behavior tables; planning.md canonical.
  - `templates/build-plan.md` rewritten as a **filled example** (a realistic small
    product, every field populated) + brief comments; parser-bug narrative (lines 20–29)
    deleted; field labels stay string-identical `**Title Case:**` (Critic substring-match
    learning). This also pre-delivers MET-2X6F's "filled example chunk" — note it there
    at close-out.
  - Measurement harness + committed baseline numbers (in the chunk's close-out notes and
    `.session-reflected`, not a new tracked file).
  - Pinned-string tests updated where reconciliation changes pinned text
    (tests/test_v5_methodology.py, tests/test_v5_templates.py, tests/preferences/*).
- **Tests:** existing suites updated in-place; new assertion: template contains a filled
  `### Chunk 01:` with non-bracket content and does NOT contain `_detect_active_scope`.
- **Acceptance criteria:** full suite green; each of D1–D5 reads one way at every site
  (grep evidence per decision); template word count ≤ ~1,100 (from 2,774).
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic` (inference: chunk) run and blocking findings resolved
  3. Chunk marked `[x]` in Status

### Chunk 02: Editorial compression pass over the cycle-load prose

- **Description:** The diet itself: rewrite `methodology/{building,discovery,planning,reflection}.md`
  and `skills/critic/{SKILL,review-protocol,review-cycle,framework-checks}.md` for
  concision — delete implementation narration (bug-ID citations, hook internals,
  withdrawn-model history like the test_v5_methodology bump-history comment), de-Fable-ese
  the compressed sentences (building.md:284, planning.md:105/126, review-cycle.md:71/83
  and their pattern-mates), collapse restatements. Behavior-preserving by construction:
  every rule keeps exactly one clear statement.
- **Depends on:** Chunk 01 (compress the deduplicated text, not text 01 will delete)
- **Deliverables:** the 8 files rewritten; token-budget ratchets lowered
  (test_v5_methodology.py building.md and review-protocol.md budgets → post-diet +10%);
  pinned-string tests updated only where wording legitimately changed (section names and
  goal names preserved where tests pin them — check before renaming any heading).
- **Tests:** suite green with lowered budgets; no set-theory glyphs / `CRT-\d` bug-ID
  citations remain in methodology files (new small assertion, methodology files only —
  skills/critic may keep operational IDs where a gate message names them).
- **Acceptance criteria:** methodology dir + critic files each show their measured
  reduction; running total vs baseline reported; no rule dropped (self-audit against
  D1–D6 list + section inventory taken before editing).
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic` (inference: chunk) run and blocking findings resolved
  3. Chunk marked `[x]` in Status

### Chunk 03: Fold the redundant surfaces + advisor-first digest

- **Description:** Delete `skills/{building,discovery,planning,reflection}/` and
  `methodology/agent-stance.md`; rewrite every live reference (scout inventory: CLAUDE.md,
  digest + slim, skills/{methodology,backlog,doctor,onboard}, templates/build-plan.md:5,
  `bin/prawduct-hook` ×5, `lib/api_versioning_probes.py`, `lib/migrate_plugin.py`,
  README.md, documentation/MIGRATION.md) to `/prawduct:methodology <topic>` form; rewrite
  the digest stance block advisor-first (STN-4W7R(a)): lead with "first duty on any
  substantive ask is the expert take — risks, stronger/simpler alternative,
  recommendation — compliance second," keep the checkable bars, ≤ ~250 words.
- **Depends on:** Chunk 02 (digest rewrite inherits the edited voice)
- **Deliverables:** deletions + reference cascade; roster/digest tests updated
  (test_plugin_manifest ALL_SKILLS/names assertion, test_plugin_methodology_digest
  PHASES/READER_SKILLS parametrization, TestAgentStance repointed at the digest block,
  test_plugin_init/migrate string checks); `/prawduct:methodology` SKILL absorbs anything
  load-bearing from the four delegator bodies (e.g. building's "STOP before code" line —
  which also stays in CLAUDE.md).
- **Tests:** suite green; `claude plugin validate` clean; form-family grep sweep
  (Verification Strategy #3) zero hits on active surfaces.
- **Type:** cumulative-final
- **Acceptance criteria:** total reduction vs baseline **−30.3%** (amended 2026-07-04 from
  ≥45% — see Success; the Complete-Delivery honest-residue clause governs); live checks 4–5
  hold; digest < 10k chars, slim ≤ half of full.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run against merge-base...HEAD and
     blocking findings resolved (this chunk's review IS the cumulative)
  3. Chunk marked `[x]` in Status (flips at release via regen-views; entry statusless on branch)
  4. Backlog hygiene via `/prawduct:backlog`: MET-3Q8V shipped→Archive; STN-4W7R
     updated (part (a) delivered here, part (b) remains); MET-2X6F updated (filled
     example delivered); MET-7R4J superseded-check; change-log entry
     (`type=improvement | chunks=01,02,03 | scope=prose-diet`, statusless on branch)

## Early Feedback Milestone

**Milestone chunk:** 01. **What the user can do:** open `templates/build-plan.md` and see
a filled example instead of 200 placeholders; read any reconciled rule and find it says
one thing everywhere.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic passes; chunk 03's one
`/prawduct:critic cumulative` is both its review and the `/prawduct:pr create` gate. PR
to develop via `/prawduct:pr` when the user asks. Risk tier: `skills/` + `bin/prawduct-hook`
edits in the bundle → expect `escalate` at PR review.

- After chunk 01: check the reconciliations read cleanly before compressing around them.
- After chunk 03 (cumulative): the no-dropped-rule audit is the review's Goal 2 focus —
  hand the Critic the D1–D6 list and the deletion inventory.

**Note on chunk count:** 3 chunks exceeds the wave banner's 1–2 guidance; deliberate —
editorial compression (02) reviewed separately from structural deletion (03) keeps each
Critic pass scoped to one kind of change, and 01's decisions must land before either.
