---
artifact: build-plan
version: 2
scope: note-remedy-contract
branch: fix/note-remedy-contract
partition: serial — both chunks are read by one reviewer and Chunk 02's acceptance is measured by the instrument Chunk 01 builds; a delegate on 02 could not verify its own change
depends_on:
  - artifact: review-loop-nontermination-diagnosis
  - artifact: review-proportionality-assessment-2026-09-17
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint; cost = unit-cost × run-count, both levers → this plan IS that norm being acted on, on the unit-cost side: it does not remove a round, it removes the payload that makes a non-gating finding read as work. Baseline measured 2026-09-18 (1,141 of 1,141 post-2026-08-04 notes carry a remedy, median 122 words)"
      - "proportionality ratchets both ways; adding a control names the yield it expects AND EMITS THAT YIELD OBSERVABLY → ENGAGED, and it is why Chunk 01 exists at all. This change's yield is a rate over the ledger, and a rate nothing computes can only ever be defended on principle. Chunk 01 ships the emission before Chunk 02 makes the change it grades"
      - "review rigor is stage-keyed; the inner stage reports everything below the inner BLOCKING set as an observation → ENGAGED and it BOUNDS this plan: at inner stage a note is already an observation and already outside `findings`, so this plan's subject is the BOUNDARY stage only, where a note is a finding. Chunk 02 must not touch the inner-stage carrier or it re-litigates a norm this plan is not about"
      - "state-file growth past its threshold is an advisory, never a hard block → inapplicable; no chunk changes a size gate"
  - artifact: architecture
    dispositions:
      - "every fact has one home; a fact is the whole predicate, not a token inside it → ENGAGED and it is Chunk 02's central risk. The NOTE contract is ONE fact with four carriers (`review-protocol.md` § Severity Levels, `goals-1-3.md`'s report contract, the `critic_consolidate` directives, `agents/critic-reviewer.md`). The home is `review-protocol.md`; the others cite rather than restate. Four full-length copies is the shape the norm names"
      - "goals and verification bind; prescribed method is advice → the carrier list below is this plan's best guess, made after reading all four but before editing any. A builder who finds a fifth carrier adds it and records why; what binds is the acceptance rate in Chunk 02"
      - "an independent reviewer never mutates the session it reviews → conforms; nothing here gives a reviewer a write path"
      - "authority fails closed; advice fails soft → ENGAGED: a note is ADVICE, and this plan makes it fail softer still. Nothing that gates stops gating, because no gate reads a note (`coverage_algebra.unresolved_blocking` reads blocking only)"
      - "local-first; no network, no third-party runtime dependency → conforms; Chunk 01 is stdlib-only over a local file"
      - "prawduct is Python but never Python-specific → conforms; Chunk 01 reads the ledger, not product code"
      - "prawduct guides and reviews; it never implements → conforms"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use a stable severity-prefix vocabulary → ENGAGED by Chunk 01: the tool's output is operator-facing and must not invent a new prefix"
      - "text emitted into a governed product names no prawduct-internal identifier → ENGAGED by Chunk 02: the NOTE contract sentence is read by a reviewer and SPOKEN into a findings report, so it may not carry a chunk id, a review id or a backlog number"
      - "the governance ledger has a single writer → conforms and is load-bearing for Chunk 01, which only ever READS it"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; `--json` keys are never repurposed → ENGAGED and it is what keeps Chunk 02 small: `recommendation` is NOT schema-required (no validator in `critic_consolidate.py` requires it), so a note omitting it is already valid today. This plan changes a PROSE contract, not a schema, and repurposes no key"
      - "exit codes are the contract → ENGAGED by Chunk 01 (a new tool needs a documented exit meaning); Chunk 02 changes no exit code"
      - "whole-surface semver; the internal CLI surface carries no per-subcommand version → conforms"
last_validated: 2026-09-18
---

## Requirements Confidence

**Level:** High for Chunk 01, Medium for Chunk 02.

**Why High for 01:** the instrument's question is fully stated and its inputs are a local
append-only file whose schema I read rather than recalled (`ts`, and a prose `mode` string — an
earlier scan keyed on `timestamp`/exact `mode` and returned a clean zero for every bucket while
measuring nothing, which is why the tool carries its own positive control).

**Why Medium for 02:** the carrier list is enumerated but the *effect* is a behavioural claim about
a model reading prose, and this plan cannot prove in advance that removing the remedy changes what
reviewers rate. That is what Chunk 01 exists to answer after the fact.

**What would raise it:** nothing cheap, and that is the honest answer. The change has to ship to be
measured. This is why Chunk 01 leads.

## Open assumptions

- `[ASSUMPTION: #832's subject is NOTE-severity FINDINGS, not the observations array | HIGH impact |
  user can veto]` — #832 says "a NOTE-severity finding carries an observation and no remedy."
  Observations are already severity-less and their stated value is that the builder can act on them
  (`review-cycle.md`: *"The builder still reads your observations and can act on them"*). Stripping
  `recommendation` from `observations` would break the mechanism that makes a demotion acceptable
  instead of a silent drop. **This plan therefore leaves `observations[].recommendation` alone.**
- `[ASSUMPTION: the four carriers below are the whole set | MED impact | user can correct]` — found
  by grep over `plugin/skills/critic/`, `plugin/lib/critic_consolidate.py` and `plugin/agents/`.
  A fifth carrier is a Chunk 02 finding, not a re-plan.

## Advisory position — what I would do differently

**The risk this plan does not price, and the reason to watch the ratio rather than the rate.**
A reviewer that may no longer write a remedy under a NOTE has a second way to comply: rate the
thing WARNING instead, where remedies are still welcome. That displaces work up a severity rather
than removing it, and it would look like success on every metric #832 names — note remedy rate
would go to zero exactly as asked. **The acceptance below therefore measures the note:warning
*ratio* alongside the remedy rate**, and a warning share that rises materially is this change
failing, not succeeding.

**What I would cut if this had to be smaller:** nothing. Two chunks is already the floor — the
instrument cannot be dropped without making the change unfalsifiable, which is the exact defect
`nonfunctional-requirements.md` names.

**What I would add if this had more room:** a follow-on that asks whether notes earn their keep at
all. Over 1,020 reviews there is no evidence any note ever prevented a blocker. That is not
"notes are worthless" — it is that notes have never been asked to prove their keep, and #830 is
where that question belongs. Out of scope here, deliberately.

## Status

- [x] Chunk 01: The instrument — an era split and a remedy dimension on `review-stats`
- [ ] Chunk 02: The NOTE contract — one home, three references, and the ratio that grades it

---

## Chunk 01: The instrument — an era split and a remedy dimension on `review-stats`

**Type:** code
**Description:** Extend `review-stats` with `--since` / `--until` window bounds and a per-severity
**remedy dimension** (how many findings carry a non-empty `recommendation`, and the median word
count). This is the emission `nonfunctional-requirements.md` requires of any added control, and it
is the only thing that can grade Chunk 02.

**Route changed from the plan as first written, and why.** This chunk was drafted as a new
`tools/review-era-split.py`, modelled on `tools/pr-review-yield.py`. Reading the surfaces first
showed that wrong on the plan's own `governed_by` terms: `review-stats` already aggregates B/W/N,
actionable share, observations and durations by role × model × mode × scope × stage, over the same
ledger. A second tool would have been a second home for every one of those facts — the exact norm
this plan disposes of under `architecture.md`. What `review-stats` genuinely lacks is a **date
window** and **any notion of a remedy**; those two gaps are what this chunk fills. Recorded here
rather than silently taken, per `architecture.md` *goals and verification bind; prescribed method is
advice*.

**Why it leads.** Chunk 02 changes prose whose effect is a rate. A rate measured only after the
change has no before, and a claim with no before is unfalsifiable.

**Deliverables:**
- `plugin/lib/telemetry.py` — window filtering and the remedy dimension; `REPORT_SCHEMA_VERSION`
  bumped (6 → 7).
- `plugin/bin/prawduct-hook` — the `review-stats` usage string and arg handling.
- `tests/test_review_stats.py` — the module's existing test home, extended.

  **Corrected mid-build.** This line first read *"new `tests/test_telemetry.py` — the module has no
  test file today"*. False: `tests/test_review_stats.py` is 685 lines covering exactly this module,
  including a `TestJsonSchemaStability` class that pins the `--json` key set and version. The claim
  came from a `grep -rln ... | head`, and the file sorted below the cut — the sliced-sample rule,
  where the slice is invisible in the output you read back. A second test file was written and then
  folded into the existing one; the pins there are renegotiated in the open rather than worked
  around.

**Done when:**
1. `--since` / `--until` accept the same forms `tools/pr-review-yield.py` already accepts, and the
   five window cases its `TestReport` pins are **ported before new ones are written**: a date-only
   `--until` covers that whole day, a month-only one covers that whole month, a zoneless bound
   matches the same instant in UTC, a full timestamp is used as given, and the bounds actually
   filter. Citing that tool as precedent obliges copying its test file, not just its design.
2. The remedy dimension counts a finding whose `recommendation` is absent, empty, or whitespace as
   **without** a remedy, and this is pinned. That distinction is the whole measurement.
3. **A control that must fail:** two fixtures identical but for remedy presence report *different*
   rates. Assert the difference, not that a number is present — a rate assertion that passes on
   both measured nothing.
4. Absence stays distinguishable from zero, matching how `observations` is already handled in
   `_extract_row`: a corpus with no remedy data reports null, never 0%, or the change reads as a
   narrowing that never fired.
5. `--json` gains keys and repurposes none; existing keys keep their meanings (`api-contract.md`,
   additive-first). A test pins that an existing key survives the bump.
6. **Real-corpus reconciliation:** run against `.prawduct/.governance-ledger.jsonl` with
   `--since 2026-08-04` and reproduce the verify-resolutions totals recorded on issue #829
   (99 blocking / 470 non-blocking across both eras; 26 non-blocking post-cut). A tool that cannot
   reproduce a number already written down is wrong about something.
7. `/prawduct:critic` per inference (short plan — the boundary cumulative covers it).

**Verification beyond tests:** run `review-stats --since 2026-08-04` and `--until 2026-08-04` and
confirm the two partitions sum to the unwindowed totals. A window that drops or double-counts events
is invisible in any single run.

## Chunk 02: The NOTE contract — one home, three references, and the ratio that grades it

**Type:** cumulative-final
**Description:** State once, in `review-protocol.md` § Severity Levels, that a NOTE-severity
**finding** carries an observation and no remedy; make the other three carriers cite that sentence
rather than restate it; and pin the rule where it is read.

**The four carriers** (home first):
- `plugin/skills/critic/review-protocol.md` § Severity Levels — **the home.** The NOTE bullet
  states the rule. The adjacent `Scope grades the remedy` and `Prose remedies` bullets currently
  instruct a remedy for the class NOTE covers and must be bounded to WARNING and above.
- `plugin/skills/critic/goals-1-3.md` — the report contract's `findings` JSON example and the
  "report to the user … each finding with goal, severity and recommendation" sentence. Reference,
  not a second statement.
- `plugin/lib/critic_consolidate.py` — the reviewer directives. Reference.
- `plugin/agents/critic-reviewer.md` — reference if it states a severity contract at all; if it
  does not, say so in the chunk close rather than adding one.

**Deliverables:**
- `plugin/skills/critic/review-protocol.md`, `plugin/skills/critic/goals-1-3.md`,
  `plugin/lib/critic_consolidate.py`, `plugin/agents/critic-reviewer.md`.
- Pins in the existing critic prose-coherence test module.
- A change-log entry tagged `scope=note-remedy-contract` with **no `release=`**.

**Done when:**
1. The rule is stated in exactly one carrier and the other three cite it. Verify by grep for the
   rule's own wording across `plugin/`, in two vocabularies sharing no word — a clean sweep usually
   indicts the query, not the tree.
2. `observations[].recommendation` is **unchanged**, and a test asserts it survives. This is the
   negative half of the open assumption above; without it the next editor reads "notes carry no
   remedy" and takes the observation channel with it.
3. The inner-stage carrier is untouched — at inner stage a note is already an observation. A test
   asserts the stage-keyed split still reads as it did.
4. A pin fails RED against the pre-change wording, verified by mutation, and red-verified against a
   **different** phrasing than the one that prompted it.
5. Change-log entry written, `check-change-log-entry` exit 0.
6. `/prawduct:critic cumulative` — the chunk's review IS the one cumulative pass.

**Verification beyond tests:** re-run Chunk 01's tool after the next review cycle and compare
**both** the note remedy rate and the note:warning share against the 2026-09-18 baseline
(1,141/1,141 notes with a remedy; 1,141 notes to 884 warnings post-2026-08-04). A remedy rate that
falls while the warning share rises is this change displacing work, not removing it — record that
reading honestly rather than reporting the rate alone.
