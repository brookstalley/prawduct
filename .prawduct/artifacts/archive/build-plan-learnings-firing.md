---
artifact: build-plan
version: 2
scope: learnings-firing
depends_on:
  - artifact: architecture              # the advice-fails-soft / authority-fails-closed split every new print site sits under
  - artifact: observability-strategy    # channel split and severity-prefix vocabulary for the new builder-facing output
  - artifact: api-contract              # additive-first evolution for the new `superseded-by=` metadata key
governed_by:
  - artifact: architecture
    dispositions:
      - "reviewer never mutates the session it reviews → conforms, and 01(b) is the one place it bit. The directive is emitted at `critic-begin`, which the reviewing fork runs — it prints to that fork's context and writes nothing. The reason 01(b) moved off its specced site is downstream of this norm: because a reviewer's output is confined to its partial, consolidate's stdout cannot reach the builder, so advice printed there is advice nobody acts on."
      - "authority fails closed, advice fails soft → conforms — every surface this plan adds is ADVICE printed to the builder. No gate reads it, no exit code changes, and a delivery line that cannot be computed is omitted rather than blocking the record it rides on. Chunk 02's supersession path is the exception that proves it: it feeds a *retirement*, which is authority, so it fails CLOSED on every ambiguity rather than degrading to a note."
      - "local-first: no network, no daemon, stdlib-only runtime → inapplicable, because nothing in this plan opens a socket, spawns a daemon, or adds a dependency. Chunk 02's only subprocess is the pre-existing `run_sentinel`, which supersession deliberately does not invoke."
      - "plugin writes only its own .prawduct/ state → conforms — the supersession path writes learnings.md and learnings-detail.md, both already owned by `audit-learnings --apply`."
      - "Python-implemented, never Python-specific → conforms, with one thing to watch. Nothing here inspects product code, so no per-file language dispatch is owed. The one Python-shaped surface is `sentinel=`, which names a pytest id — pre-existing, untouched by this plan, and the reason supersession is worth having: a rule retired because a broader rule replaced it needs no test runner at all, so `superseded-by=` is the language-agnostic retirement route the corpus previously lacked."
      - "prawduct guides and reviews, never implements → conforms — the delivery lines pose a question to the builder; none of them inspect or edit product code."
      - "goals and verification bind, prescribed method is advice → conforms, and this plan is the norm's own evidence base. Chunk 01(b) departed from its specced call site and Chunk 02 from two of its stated deliverables; each departure is recorded at the chunk with the reason, and every acceptance criterion was met unchanged. Born 2026-07-31 from this session, so the plan predates the norm — the departures were recorded before it existed, which is what suggested it."
      - "one home per fact; every other mention is a reference (born 2026-07-31) → conforms, and this plan is where the norm's evidence came from — 9 of 23 findings in its own cumulative review were one fact copied and drifting. Two duplications it introduced are now collapsed: the restamp claim (four copies, all corrected instead of reduced to one — recorded as the wrong repair) and the descent clause's binding status, whose home is the Problem section and whose change-log mention now references it. The `superseded-by=` forwarding pointer is a deliberate second copy of a heading and is the norm's edge case: it is a reference by intent, and Chunk 03(b) records the sequencing constraint that keeps it resolvable"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary, stdout/stderr channel split → conforms — delivery lines ride stdout beside the confirmation they annotate, exactly as `_BATCH_FIX_DIRECTIVE` already does. `RESOLUTION_IS_A_CLAIM_DIRECTIVE` carries the `PRAWDUCT:` prefix; `_GREEN_IS_EVIDENCE_DIRECTIVE` does not, because it is appended to a `recorded:` line that already identifies itself."
      - "the governance ledger has a single writer; agents never hand-author it → inapplicable, because nothing in this plan writes a ledger line. Chunk 02 mutates learnings.md and learnings-detail.md only, and the directives write nothing at all."
      - "no prawduct-internal identifiers in product-emitted text → conforms — the lines name the builder's own tests and claims, never a prawduct finding id. Checked against the drafted text, not assumed: the only backticked tokens are `fixed`, `waived`, `unresolved_blocking`, `git show` and `resolutions`, all of which are the reader's own vocabulary at that moment."
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the internal CLI carries no per-subcommand version → conforms — `superseded-by=` ships at the plugin version like every other CLI change, and adds no version handle. The persisted surface it touches (`learnings.md` metadata) is not the schema-versioned evidence store."
      - "exit codes are the contract; severity prefixes stable; errors attributed, never stack traces → conforms — every new failure path (unresolvable, ambiguous, self-referential, empty, both-keys) lands as an attributed `errors` entry naming the entry and the fix, and none of them changes an exit code or escapes as a traceback. `audit-learnings` still exits 0 on a clean audit and 1 only on a structural problem."
      - "additive-first evolution → conforms — `superseded-by=` is a new optional key in an existing optional comment; absent metadata keeps meaning 'active, no lifecycle metadata', and no existing flag or exit code is repurposed. `retirements` gains `reason`/`superseded_by`/`resolved_to` as new keys and keeps its meaning; supersessions ride that existing list rather than a new one precisely so a reader who iterates it is not silently under-reported to."
last_validated: 2026-07-31
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.3
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan: Rules That Fire

## Problem

`.prawduct/learnings.md` held 159 rules when this plan was authored (2026-07-29); Chunk 03's
collapse brought it to 149 on 2026-08-01. Recompute rather than cite either:
`grep -c '^## ' .prawduct/learnings.md`. A product repo (discodon) running the latest
prawduct spent one cycle whose retrospective — `documentation/LEARNINGS_VERIFYING_TEST_
INFRASTRUCTURE.md` in that repo — records four false claims and twelve Critic rounds. Every
one of those failures was already covered by a rule in this file.

The decisive evidence is the rule *Anything in a durable artifact that one command could check
is a CLAIM*, which read as follows when this plan was authored (Chunk 03 amended it in place on
2026-08-01 to absorb two retiring members; grep the heading rather than a line number):

> Anything in a durable artifact that one command could check is a CLAIM — including an
> identifier, a count, or a facet value, not just a rationale.

That is the general, upleveled, well-worded rule the corpus supposedly lacks. It exists, it
covers all four failures, and it did not fire. **The corpus does not have an authoring
problem. It has a delivery problem.** A rule stored in a file that is read at session start
and never again competes with the entire rest of the context by the time the claim gets
written.

The design precedent is `_BATCH_FIX_DIRECTIVE` — not stored, but *printed by code at the exact
moment the builder holds a set of findings*, built because the file-stored version of the same
rule was not firing.

**It is a precedent, not evidence.** It lives on the unmerged `feature/clear-signal-and-batch-fix`
branch and has never shipped, so nothing has been observed firing in the field and this plan may
not cite it as proof that delivery works. That branch is also where "warnings and notes gate
nothing" replaces develop's "**Warnings** should be addressed — the Critic only uses WARNING when
confident." Both halves of the round-multiplication fix are in flight there; neither reached
discodon.

Which sharpens the diagnosis rather than softening it. On *shipped* prawduct the round-count
pressure is real and partly instruction-driven: the guidance a builder actually reads pushes
toward addressing warnings, and no code-delivered directive counters it at the moment findings
land. That two independent lines of work — discodon's retrospective and that branch — converged
on the same defect is the strongest signal here that it is structural rather than one builder's
bad day.

### The second failure: delivery is not descent (owner-raised, 2026-07-31)

Delivery gets the rule in front of the reader at the right moment. It does **not** make the
reader spend it. A general rule can arrive exactly on time, be read, be agreed with, and change
nothing — because nothing made the reader recognize the case in hand as an instance of it. That
is a distinct failure from the one above and it survives the fix for it.

It also inverts part of this plan's own remedy. Upleveling buys durability by removing the
particulars, and the particulars are what a reader pattern-matches against. So **a rule's
generality is what makes it storable and what makes it inert, and those are the same property.**
The corpus bears this out: `learnings.md` headings run to a median of 188 characters and 396 at
the 90th percentile (`awk '/^## /{print length($0)}' .prawduct/learnings.md`), because the rules
that work already carry their instances inline. `learnings-detail.md` is documented as
"consulted when debugging in a known area" (`methodology/reflection.md`), i.e. read on demand —
so an instance relocated there is, for firing purposes, deleted.

Two consequences, both ratified by the owner on 2026-07-31 and binding on the chunks below:

1. **Every rule this plan delivers carries its descent** — the general statement, then the act to
   perform, then instances concrete enough to pattern-match against, then (for code-delivered
   directives only) an explicit instruction to apply it to the case in hand.

   What *binds* is that structure, and it is what the guard asserts: an imperative present, and
   the text pointing at the reader's current decision. Aiming the last clause at the case the
   reader feels **surest** about — on the reasoning that it is the one a general rule never
   reaches — is authorial intent, deliberately left unpinned. A test that froze the wording would
   fail every improvement to the sentence and pass any defect that kept the words, which is
   `learnings.md`'s "assert the PROPERTY, not one spelling of it". The change-log entry states it
   the same way; if these two ever diverge again, this line is the home.
2. **The collapse merges statements and unions instances** — see Chunk 03(b). Rule *count* is
   what competes for attention at read time; discriminating detail is not, and is not what the
   corpus needs less of.

## Success

1. At least two rules move from stored to **delivered**: emitted by code at the moment of the
   action they govern, on a trigger narrow enough that they are never noise.
2. Retiring a rule **by supersession** becomes a first-class, auditable operation — the
   historical entry names the rule that replaced it, so a reader who remembers the old rule
   finds a forwarding address rather than a hole.
3. The corpus shrinks **in rule count, not in discriminating detail**. Two near-duplicate
   families (counted by the commands in Scaffolding, never transcribed here — learning 322)
   collapse into their existing general rules, each of which absorbs the distinguishing
   instances of the members it retires. A collapse that reduced the count by dropping instances
   would fail this criterion, not meet it.
4. Six mechanisms from the discodon retrospective land as **two** rules, not six — each stated
   generally and each carrying the mechanisms it absorbed as named instances.
5. Every rule delivered or rewritten here descends: statement → act → instances, plus an
   apply-it-here clause on the code-delivered directives.

## Out of Scope

- Rewriting the ~140 rules outside the two identified families.
- Any change to what the Critic reviews or how gates compose. This plan adds advice, not authority.
- The change-log ledger, and everything on the `record-mechanization` plan.
- Automatic detection of unfalsified claims. The delivery lines *ask*; nothing here judges the answer.

## Requirements Confidence

**High** on the problem and on Chunks 01–02. The delivery thesis is backed by a natural
experiment inside this repo: the one rule that was moved from storage to code-delivery is the
one rule whose sibling failure mode (round multiplication) still recurred only in the half the
directive does not address (*entering* a round versus batching *within* one).

**Medium** on Chunk 03's collapse ratio.

- [ASSUMPTION: the ~14-rule assertion family collapses into line 292 without losing a distinction
  worth keeping | HIGH impact | user can override] — **superseded 2026-07-31, and it was the
  wrong shape of worry.** It named three members as exceptions: 298 (the falsifying query can
  itself carry the defect it hunts), 27 (a completeness claim must never be a count of sites
  fixed), and 286 (a rationale you *reached for* is the one to verify). The owner-raised descent
  problem generalizes those three to the whole family — the second-order point *is* each rule's
  value, and the general statement is the index, not the content. So the assumption is not
  "does the merge lose something for three of them" but "the merge loses something for all of
  them unless instances are unioned rather than dropped", which Chunk 03(b) now requires and
  the acceptance criteria pin. What still needs the owner's per-rule call is which instances are
  genuinely redundant — that remains the approved map's job.
- [ASSUMPTION: printing a delivery line on a narrow trigger reads as help rather than nagging
  | MED impact | user can override] — mitigated by conditioning each line on state the builder
  just changed, never on every invocation.

## Status

- [x] Chunk 01: Deliver the two rules at their moment
- [x] Chunk 02: Supersession as a lifecycle event
- [x] Chunk 03: Collapse the two families, add the two new rules

## Scaffolding

**Family membership is derived, never transcribed.** Both counts in this plan come from
`tests/spikes/learning_families.py` (added in Chunk 03), which classifies by heading text and prints
the roster. Cite the command, never the digits.

## Verification Strategy

- **Chunk 01** — unit tests over the two print sites: the line appears when its trigger holds,
  is absent when it does not, and its absence never changes an exit code. Each assertion is
  mutation-proved: invert the trigger, watch the test go red.
- **Chunk 02** — unit tests over `audit_learnings`: an entry with `superseded-by=` and no
  sentinel retires under `--apply`; the historical entry carries the forwarding pointer; a
  `superseded-by=` naming a heading that does not exist is an error, not a silent retirement.
- **Chunk 03** — the collapse is executed *through* Chunk 02's mechanism, which dogfoods it.
  `tests/spikes/learning_families.py` re-run after the collapse is the completeness check.

## Build Chunks

### Chunk 01: Deliver the two rules at their moment

- **Description:** Move two rules from storage to code-delivery, each on a trigger narrow enough
  to never be noise.

  **(a) Green is evidence only about what could have made it red.** The moment is
  `prawduct-hook test-evidence record` (`plugin/bin/prawduct-hook:2025`) — where the builder
  stamps "the suite is green" into the record the gates read. Trigger: the record's
  `changes_referenced` is non-empty, i.e. the builder just added or changed judged code. The
  line names the check, not the virtue: *for each new test, what change would turn it red? A
  fixture that never reaches the subject, an assertion that cannot tell the two orderings
  apart, and a branch that depends on a file that happens to exist locally all pass
  identically.* Silent when nothing judged changed — a docs-only cycle, or a run that touched no
  source, prints nothing.

  **Two corrections from the cumulative review, both to claims rather than behavior.** (i) *Not*
  "a restamp prints nothing": `--no-rerun` re-runs the F4a overlay, which repopulates
  `changes_referenced` against the current tree, so a restamp with judged changes in the diff
  fires — correctly, since the builder did just change judged code. The claim was wrong here, in
  the constant's docstring, in a test docstring, and in the change-log, all at once. (ii)
  `changes_referenced` is a **proxy** for "judged code changed" and is narrower than the phrase:
  `bin/test-reference-verify` matches Python symbols only, so the directive never fires in a
  Swift/Rust/C#/TypeScript product, and Success criterion 1 currently holds for Python repos
  only. Recorded at the constant where a reader meets it; widening the trigger is a separate
  decision with a noise tradeoff, not a silent fix.

  **(b) A claim needs its falsifier run.** The rule: *a resolution is a claim about the tree. Say
  which evidence you read, not that you are confident.*

  **The moment is `critic-begin --mode verify-resolutions`, NOT `critic-consolidate`** — a
  correction to this spec made when (b) was built (2026-07-31), because the specced site cannot
  fire. `verify-resolutions` is always single-pass (`_derive_roster` returns `SINGLE_PASS_ROSTER`
  for it unconditionally), so the reviewing fork writes its `resolutions` into the partial and
  *then* runs `critic-consolidate` itself: a directive there reaches an agent that has already
  made the claim and is one step from exiting. Nor does it carry to the builder — the Critic
  skill is `context: fork`, and the fork's report-back instruction (`skills/critic/goals-1-3.md`)
  enumerates findings and a summary, not the consolidator's stdout. Dispatch is the same reader
  in the same review, one step earlier, and upstream of the claim. The constant still lives
  beside `_BATCH_FIX_DIRECTIVE` so the data plane's two directives are edited together; only the
  print site moved.

  Trigger: the manifest's mode is `verify-resolutions` — keyed off the manifest rather than the
  `--mode` argument, so a dispatch demoted for scope-widening (exit 2) never delivers advice for
  a review that is not happening.

  **Unblocked 2026-07-31**: `feature/clear-signal-and-batch-fix` merged to `develop` as `0f3e26c`
  (PR #155) and this branch was rebased onto it, so `_BATCH_FIX_DIRECTIVE` is present.

- **Depends on:** (b) only — the clear-signal branch landing (**resolved**)
- **Artifacts consumed:** `observability-strategy.md` (channel split), `architecture.md` (advice fails soft)
- **Deliverables:** two module-level directive constants and their print sites, plus tests.
  **Only one sits beside `_BATCH_FIX_DIRECTIVE`** — `RESOLUTION_IS_A_CLAIM_DIRECTIVE` in
  `lib/critic_consolidate.py`, so the data plane's directives are edited together;
  `_GREEN_IS_EVIDENCE_DIRECTIVE` lives in `bin/prawduct-hook` beside the recorder it annotates.
  Each is adjacent to the code that emits it, which is the placement that matters; the original
  "both beside `_BATCH_FIX_DIRECTIVE`" wording survived the 01(b) correction sweep and was false.
- **Tests:** (a) landed in `tests/test_plugin_runtime.py` and (b) in
  `tests/test_critic_consolidate.py` — **not** the `tests/test_test_evidence.py` this spec named,
  which does not exist. Each half sits beside the code it guards: (a)'s trigger is a helper in
  `bin/prawduct-hook`, and (b)'s constant and its sibling `_BATCH_FIX_DIRECTIVE` are both in
  `lib/critic_consolidate.py`, so the two directives' rules are read and edited together.
  Trigger-on, trigger-off, and exit-code-unchanged for each
- **Acceptance criteria:** each line appears exactly on its trigger; neither changes any exit
  code; both are mutation-proved (invert the trigger → red)
- **Type:** code
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

### Chunk 02: Supersession as a lifecycle event

- **Description:** `audit_learnings_cmd.py` models exactly one retirement reason — a declared
  `sentinel=` test that now passes ("structurally enforced"). It has no concept of a rule
  retired because a *broader rule* replaced it, which is what every consolidation is. Today that
  leaves consolidation as an unauditable hand-edit, which is precisely why a corpus reaches 159
  rules with two near-duplicate families in it: adding is cheap and merging is not.

  Add `superseded-by=<heading-prefix>` to the recognized metadata keys. An entry carrying it
  retires under `--apply` with no sentinel run, and its historical entry records the forwarding
  pointer. A `superseded-by=` whose target heading does not resolve in `learnings.md` is an
  `errors` entry and the retirement does **not** apply — the same fail-closed posture the
  failing-sentinel path already takes, and the direct analogue of learning 31 (an absence-claim
  must cite a path that resolves).

  **Built 2026-07-31. Four things the spec did not anticipate, all recorded at the mechanism:**

  1. **`_KNOWN_METADATA_KEYS` was dead code, so "add the key to it" was a decorative
     deliverable.** The module had exactly one reference to that set — its own definition —
     while its comment claimed "the audit logic only consults this set." Adding `superseded-by`
     to a set nothing reads changes no behavior. It is now pinned to the keys the logic actually
     reads, by a guard that parses this module's own `meta.get(...)` call sites
     (`TestKnownMetadataKeysMatchesTheLogic`); drift fails in both directions.
  2. **The retirement path collided with the repo's own guard test, and would have blocked
     Chunk 03.** `_apply_retirements` copied each retired entry verbatim — lifecycle comment
     included — into `learnings-detail.md`, which
     `test_no_lifecycle_metadata_has_drifted_to_the_detail_file` forbids, because that file is
     never parsed and an inert comment there once disabled the whole mechanism. Verified
     empirically before the fix, not inferred. Retired entries now shed the comment and carry a
     one-line retirement note in its place. **This changes the older sentinel route too**, which
     is a deliberate departure from "no existing audit-learnings behavior changes" below: the
     latent break is identical on both routes, and fixing only the new one leaves the guard
     failing for the old.
  3. **An entry declaring BOTH keys is an error and retires under neither.** Not a precedence
     question: choosing silently would let a *failing* sentinel be bypassed by adding a
     supersession key — a gate weakened by an edit to the thing it guards.
  4. **Supersession targets resolve against the corpus as it stood before the run**, so a chain
     retired in one pass (A→B, B→C) resolves both pointers rather than failing A for naming a
     heading the same run removed. The reader following A lands on B in the historical section,
     which carries its own pointer to C.

- **Depends on:** nothing (parallel with 01)
- **Artifacts consumed:** `api-contract.md` (additive-first evolution)
- **Deliverables:** `superseded-by` in `_KNOWN_METADATA_KEYS` **plus the guard that makes that
  set load-bearing**; retirement path; forwarding pointer in the historical section; `--json`
  shape extended additively; `skills/doctor/SKILL.md` updated (it documents the retirement
  semantics and said sentinel was the only route)
- **Tests:** `tests/test_audit_learnings.py` — retires without a sentinel; forwarding pointer
  present and placed under the title; unresolvable / ambiguous / self-referential / empty
  targets error and do not apply; both-keys errors; chain resolves; sentinel path otherwise
  unchanged; record key sets uniform across both routes
- **Acceptance criteria:** the cases above pass and are mutation-proved (10 mutations, all
  caught); no existing audit-learnings behavior changes **except the comment-shedding in (2),
  which is recorded here as a deliberate departure with its reason**
- **Verified live**, not only through the library: `prawduct-hook audit-learnings` and
  `--apply` run against a synthetic corpus, reporting `ready` for a resolvable pointer and
  `blocked` for an unresolvable one, and writing both files as specified. `--json` shape and
  `--apply`-to-write posture conform to `api-contract.md`'s Operations norms.
- **Type:** code
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

### Chunk 03: Collapse the two families, add the two new rules

- **Description:** Two parts, in order.

  **(a) The two genuinely-new rules from the discodon retrospective.** Six mechanisms, two
  rules — the rest are already-covered instances.

  1. *Green is evidence only about what could have made it red* — absorbs mechanisms 1 (the
     fixture never reaches the subject), 2 (machine state as an undeclared input), 4 (a
     load-dependent race in test setup), 5 (silent-by-construction properties: a stage whose
     value is speed needs a test that fails when it stops being fast), and 6 (mutation testing
     is one-directional — reverting removes the damage alongside the fix, so it is blind to
     what your change broke beside it; pair it with branch coverage of the function you
     touched). Existing line 15 becomes an instance and retires into it via Chunk 02.
  2. *A text-anchored edit changes a neighborhood, not a point* — mechanism 3, plus mechanism
     6's concrete defect. Inserting at a `def` line lands the new function between the next one
     and its decorator; restructuring `try/except` into `try/except/else` strands the fallback
     inside `else`. Both compile, both stay green. This is the defect class the agent's own
     text-anchored Edit tool manufactures, and nothing in the corpus covers it.

  **(b) The collapse — merge the statements, union the instances.** Write
  `tests/spikes/learning_families.py` to classify the corpus, then produce a per-rule keep/merge map
  for both families. The assertion family merges into existing line 292; the
  discriminating-test family merges into the new rule (1) above.

  **The keep/merge test is NOT "is this member covered by the general rule?"** Everything is
  covered by the general rule — that is what makes generality feel like progress while it removes
  the discriminating power a reader needs to recognize their own case. The test is: *does this
  member contribute an instance the general statement cannot generate?* If yes, the member
  retires and **its instance moves into the successor's heading**; the successor gets longer, the
  corpus gets shorter by one rule, and nothing recognizable is lost. Only a member whose instance
  is genuinely redundant retires without leaving anything behind.

  Relocating an instance to `learnings-detail.md` does **not** count as keeping it: that file is
  read on demand when debugging a known area, not at the moment the rule has to fire. Heading
  length is not the constraint people assume — the corpus already runs 188 median / 396 p90 / 907
  max characters, and the long ones are the ones that work.

  **Sequencing constraint, and it binds Chunk 03 specifically.** A forwarding pointer is written
  as *literal resolved heading text* into `learnings-detail.md`, and nothing ever re-resolves it:
  `audit-learnings` parses `learnings.md` and nothing else. So the moment a successor heading is
  reworded, every pointer at it names a heading that does not exist — a hole that reads as a
  forwarding address, which is the exact failure `resolve_supersession_target` rejects
  self-supersession to prevent, reintroduced downstream of the check. **LRN-9K2P is open at
  `stage: ready` to reword ~28 `learnings.md` headings, and this chunk mints a batch of pointers.**
  Run the collapse BEFORE that rewording, or the rewording before the collapse — not interleaved,
  and never the rewording after without re-checking every `superseded by **X**` in the detail file
  against `learnings.md`. (LRN-6C2X already records this hazard for the pairing invariant; neither
  side recorded it for supersession pointers until this review.)

  **The map is presented for approval before any retirement is applied** — three members carry
  second-order points that a merge could silently drop (see Requirements Confidence), and under
  the union rule the map must state, per retired member, which instance survived and where.

  **(c) The standing read-instruction.** One structural statement of the descent obligation —
  that a rule agreed with and not applied to the case in hand has done nothing — added where
  learnings are *read*, not repeated per rule. Owner ruling 2026-07-31: structural once, plus an
  inline apply-it-here clause on the code-delivered directives only (Chunk 01(a) and 01(b) each
  ship one). Repeating an exhortation across every rule reproduces the inertness one level up;
  stored rules carry instances instead, which do the same work at lower cost per rule.

  **Built 2026-08-01. One spec correction, owner-decided, and it changes acceptance criterion 3.**
  The approved map collapsed each family into **one** destination and justified it as *"within
  house style — 188 median / 396 p90 / 907 max characters."* Drafted for real, the two
  destinations measured **1,484 and 1,798 characters** — 1.7× and 2.0× the corpus maximum, not
  within it — and collided with `record_lint`'s `learnings-entry-shape` cap
  (`_LEARNINGS_RULE_MAX = 400`, shipped 2026-07-30), whose remedy *"move the evidence to
  learnings-detail.md"* is exactly what the 2026-07-31 union ruling overruled.

  Owner decision: **split each family thematically under the cap** — family 1 into four
  destinations, family 2 into five, grouped by the *kind* of failure. So criterion 3's *"reduced
  to their general rule plus whatever the map explicitly kept"* now reads **general rule plus its
  thematic siblings plus the keeps**; its intent (count down, instances preserved) is met and the
  union criterion is met in full. Measured trade, recorded because the intuition here is wrong:
  the split saves **−18%** of characters against the mega-heading's **−21%** — nearly identical,
  because the *instances* dominate and both shapes keep them. **The shape buys rule count, not
  tokens** (19 → 10 rather than 19 → 6). Token reduction is not this chunk's goal and criterion 3
  forecloses it deliberately; that work shipped as LRN-4K8T, which is where the 400 cap came from.

  **Two `--apply` side-effects, recorded rather than left in the diff.** It is a whole-corpus
  operation, so it also retired one unrelated `sentinel=`-ready entry (plugin-skill frontmatter
  validation). And it correctly refused *"Framework ownership follows the write strategy"*, whose
  sentinel names `tests/test_prawduct_sync.py` — deleted with the file-sync engine in v2.0.3.
  Filed for repair; out of this chunk's scope.

- **Depends on:** Chunk 02 (the mechanism the collapse executes through)
- **Artifacts consumed:** the discodon retrospective; `learnings.md`; `learnings-detail.md`
- **Deliverables:** two new rules with narratives in `learnings-detail.md`;
  `tests/spikes/learning_families.py`; the approved collapse applied via `audit-learnings --apply`;
  the standing read-instruction from (c)
- **Tests:** the family script re-run post-collapse is the completeness check; the retirement
  path is already tested by Chunk 02
- **Acceptance criteria:** both new rules present with narratives; every retired rule carries a
  resolvable forwarding pointer; the family script reports both families reduced to their
  general rule plus whatever the map explicitly kept; **every retired member's distinguishing
  instance is locatable in its successor's heading, or the map says explicitly why it was
  redundant** — the union half of the collapse is an acceptance criterion, not a style note,
  because dropping instances is the cheap way to hit the count and the whole reason the corpus
  stopped firing
- **Type:** code
- **Done when:**
  1. Acceptance criteria met
  2. Collapse map approved by the user before `--apply` runs
  3. `/prawduct:critic final` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `prawduct-hook test-evidence record` after a chunk that touched
judged code and see the green-is-evidence line fire — then run it on a docs-only change and see
it stay silent.

## Governance Checkpoints

- Chunk 01 and 02 are independent and may be built in either order or in parallel.
- Chunk 03(b) has a **hard stop** before `--apply`: the collapse map is approved by the user
  first. Collapsing a rule the project earned is not a call this plan makes unilaterally.

## Related open backlog items

To be reconciled at Chunk 03 — the "confirmed by mutation names its own falsifier" idea from
the retrospective's structural candidate #1 is folded into Chunk 01(a)'s delivery line rather
than filed separately.
