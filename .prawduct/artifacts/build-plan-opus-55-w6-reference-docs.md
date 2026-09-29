---
artifact: build-plan
version: 1
scope: opus-55-w6-reference-docs
branch: feature/opus-55-w6-reference-docs
partition: "One chunk built by the main agent. The wave is six prose files, most of the diff in one of them, and splitting it would buy little wall clock for an integration cost. The regression probe runs in a background agent that writes only to the scratchpad, as in W3 to W5."
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms, and it is the point of E-4, E-17 and E-19: a restated severity, a restated producer obligation and a restated reflection sentence become pointers to their homes, or go"
      - "the plugin writes nothing into a governed repo except… → conforms: only plugin-shipped reference docs and the runbook skill's prose change"
      - "goals and verification bind; prescribed method is advice → conforms: E-5 turns three self-review passes into the bar a finished runbook meets"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer surface changes"
      - "authority fails closed; advice fails soft → inapplicable, because no gate verdict, exit code or advisory changes"
      - "prawduct guides and reviews, it never implements → conforms: E-16 keeps the statement that the test-report contract installs nothing, and drops only its justification to a maintainer"
      - "local-first governance coordination → inapplicable"
      - "written in Python, never specific to Python → inapplicable"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: one chunk, one boundary review"
      - "proportionality ratchets both ways → conforms: the wave only deletes and rewrites text; it adds no control"
      - "review rigor is stage-keyed → inapplicable, because no severity rule changes. E-4 re-points a restated severity at its home and does not change it"
      - "state-file growth is an advisory, never a block → inapplicable"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms: no test pinned a sentence this wave rewrites. The one docstring that quoted a rewritten sentence (`test_registry_completeness.py`) quotes the new one. The three machine-read tables (`discipline.md`, `test-report-contract.md`, `waivers.md`) keep their parsed shape"
      - "model plan (Fable coherence before the cycle lands) → the pass is owed before this wave lands, and this plan's Done-when carries it"
---

# Build Plan: Opus 5.5 prompt audit — W6, reference docs

## Problem

The reference docs in `plugin/docs/` (all but `principles.md`, which W1 took) misfire on Opus 5.5
in the ways slice E records, ruled by the owner on 2026-09-28 (the audit's § Rulings):

- **An overstated claim the guide contradicts.** `runbook-authoring.md` calls length "the single
  most strongly evidenced finding in the entire literature", then concedes no experiment
  manipulated length and names a different rule the most strongly evidenced (E-1). Six competing
  superlatives follow it (E-6).
- **A restated threshold that drifted.** `norms.md`'s enforcement table says BLOCKING "where
  ratified norms exist"; § Severity scopes it to *adopted* norms (E-4).
- **Builder self-verification.** Three self-review passes over a runbook draft (E-5, fork F3).
- **History inside instructions.** Research history, incident replays, ticket ids, "used to",
  "today", and a named-but-unimplemented region form (E-3, E-7 to E-15, E-18, E-19).
- **Clauses for the wrong reader.** Prawduct-internal norms and test names addressed to a
  producer author in another ecosystem, and reviewer-talk comments in code consumers paste
  (E-2, E-16, E-17).

## Success

- **Every decision carries its slice-E replacement, or a recorded departure** (E-1 to E-19). Each
  site is located by its `evidence:` string, not its line number.
- **The suite passes.** Every test naming an edited file runs, without `-x`. A `"<lit>" not in`
  literal this wave deleted from its files would go vacuously green, so each is checked against
  the files at `origin/develop`.
- **No other surface restates what this wave deleted or corrected.** `plugin/` and
  `documentation/` are swept for each rewritten fact, by the state as well as the words.
- **One regression probe** (the audit's W4 recommendation), on E-5, the wave's one
  `model_dependent` decision. `/prawduct:runbook` runs in the main agent, so the probe runs on the
  session model and confirms the model id from `modelUsage`. **P1:** the old and the new guide, each
  appended to the system prompt beside the same skill, write a runbook for a scratch repo's alert.
  The failure targeted is a new-arm runbook that fails one of the guide's four non-negotiables the
  old arm meets. Criteria are fixed before the runs. Two samples per arm.
- **No token ceiling moves.** No file in `plugin/docs/` has one (slice E § Inventory).

## Out of scope

- `plugin/docs/principles.md` (W1), and every file another wave owns, except where this wave's
  edit would leave a copy disagreeing with its home (§ Found while applying).
- The slice-E outside-slice notes not ruled: the runbook skill's restated budgets, its
  "Non-negotiables while drafting" list and its Step 2 derivation list; `review-cycle.md`'s ledger
  restatement; `planning.md`'s `governed_by:` restatement.
- Ticket ids and history in code docstrings (`lib/ledger.py`, `lib/telemetry.py`,
  `lib/norm_probes.py`). They are code, which is #181's mechanism half.
- Any change to what a gate decides, to a severity rule, or to a parsed table's shape.

## Requirements Confidence: High

Every decision has replacement text and a ruling. These are the inferences:

- [DECISION: one chunk, built by the main agent | six prose files with most of the diff in one; a
  delegate would add an integration step for little wall clock | owner can veto]
- [DECISION: the probe targets E-5 | it is the wave's one `model_dependent` decision, and a worse
  runbook shows in output that can be graded | owner can veto]

## Found while applying

- **E-19 cut the intro's "(learning-system audit 2026-09-01 §3.5)"**, which left rows 7 to 9's
  "fleet-wide (audit §3.5)" citing an audit the table no longer names.
  [DECISION: those cells read "fleet-wide" | a chunk corrects a reference its own edit orphaned;
  the Learned-by column is not machine-read | owner can veto]
- **E-5's class had three more copies.** `runbook-authoring.md`'s example runbook "would pass the
  self-review". The runbook skill's Step 5 ("Subtract, then self-review … Then run the guide's
  rejection criteria"), its Read-this-first summary ("a self-review of six restraint checks") and
  its Step 2 ("You will need it for the self-review") all still told the author to re-run the
  criteria. E-5's own `why:` names Step 5, and no remaining wave owns the skill.
  [DECISION: the example "meets the rejection criteria"; Step 5 keeps the subtraction pass and
  states the criteria as the bar the finished runbook meets, Restraint block first; the summary
  names "the rejection criteria"; Step 2's record feeds Step 6's report | leaving them would make
  the skill and its guide disagree on the one thing E-5 changed | owner can veto]
- **`test_registry_completeness.py`'s docstring quoted E-14's old sentence** ("that is the only
  change needed"). It now quotes the new one. No assert read it.
- **E-7's replacement cites the critical-step test in Branching** by its existing anchor, which
  the table of contents already uses.

**P1 outcome (2026-09-29, E-5, Opus 5.5).** Each subject ran `claude -p --model claude-opus-5-5
--setting-sources project --strict-mcp-config --settings
'{"enabledPlugins":{"prawduct@prawduct":false}}'` from a scratch repo for a `ledger-worker` service,
with the skill and the arm's guide appended to the system prompt. The skill was the pre-W6 copy in
both arms, so the new arm was still told to self-review by the skill's Step 5. The probe measures the
guide change alone. The diff between arms was checked, and the criteria (the guide's four
non-negotiables) were fixed before the runs. All four runs have `modelUsage` = `claude-opus-5-5`,
and none quotes the digest.
- **Both arms, 2 of 2:** every non-negotiable met. The weakest run was in the control (old-2: a
  verification step expecting only "an `Active:` line").
- **Differences:** runbooks were 8 to 11 steps, 3,960 to 4,919 characters, the new arm slightly
  shorter. No run narrated a self-review. Only one old run revised its draft after writing it.
- **Result: no regression.** The control did not fail, so this is not evidence E-5 helps. C3
  (irreversible steps) was barely exercised: every subject correctly kept the destructive
  dead-letter purge out of the procedure.

**Cumulative review (`rev-20260929T171037Z-407e81b6`): 0 blocking, 2 warnings, 8 notes.** Fixed in
the working tree with the coherence-pass fixes below, then one `verify-resolutions`:
- **R-2:** two copies of rewritten facts outside the edited docs: the runbook template's "most
  commonly omitted section" superlative (E-6's class) and `lib/norm_probes.py`'s comment calling
  the stall window "configurable" (E-12's class).
- **R-4, R-5/R-7, R-8:** Step 5's "Fix, don't annotate." restored; the evidence appendix no longer
  confirms the ITBench-AA ceiling the body stopped citing; E-8's ✓ sentence says packages and API
  calls, which is what was measured, not "flags, and endpoints".
- **R-1:** the declared suite is recorded again over the fixed tree.
- **Accepted:** R-3 (P1 is recorded; the review ran beside the probe to save wall clock), R-6 (the
  `#self-review--rejection-criteria` anchor is linked from the shipped template), R-9 (#181 and
  #342 get a "prose half shipped" comment at merge, not before), R-10 (#818 is probe behaviour
  this wave does not touch).

**Fable final-coherence pass (2026-09-29).** `claude -p --model claude-fable-5-1`, from a scratch
directory with the prawduct plugin disabled, over the whole cycle's result (`git diff 0bbc5a61
HEAD -- plugin/ CLAUDE.md .claude/rules/`, final files read). `modelUsage` = `claude-fable-5-1`.
The model was set at spawn, which `project-preferences.md` § Model floor admits alongside `/model`.
Result: 0 blocking, 8 warnings, 9 notes, all seams between waves; verdict "one coherent whole on
its four aims". Every quote was re-checked against the files before fixing.
- **Fixed (all eight warnings):** W-1, the chunk-boundary review exception, false on a short plan
  (`session-hygiene.md`, root `CLAUDE.md`); W-2 and W-3, `review-cycle.md` claiming the close
  directive prints its paragraph verbatim and quoting a `building.md` sentence that no longer
  exists; W-4, the backlog skill naming the inert change-log `status=shipped` as a release step (it
  is the `release=` tag); W-5, the runbook skill's copy of E-8's overclaim; W-6, a `reviews.md` rule
  telling the builder to scrub the whole diff before review (B-1's class; the grep-a-ban half
  stays); W-7, two pointers to a `building.md` "Coverage Evidence" section that does not exist;
  W-8, the preferences template routing norms to Goal 4 (it is Goal 3).
- **Fixed (notes):** N-1, three reviewer directives in `critic_consolidate.py` lose their capitals;
  N-2 and N-3, issue and spec ids (STH-4K7N, REL-6C3W, D4, D14, § refs) leave runtime prose;
  N-5, a `core.md` Tell that assumed file-list deliverables; N-6, the methodology index's
  between-phase validation (B-19's class); N-8, a mode-inference pointer; N-9, this bookkeeping.
- **Accepted:** N-4 (`building.md`'s "research subagent" for high-impact decisions; unruled, and
  a test pins it as behaviour, so changing it is a decision for the owner, not a coherence fix);
  N-7 (the chunk reviewer's "ACCEPT is the default" coaching; unruled reviewer behaviour,
  and nothing is filtered).
- **Verify pass (`rev-20260929T173826Z-ea3cccf8`, run as `final` over the batch): 0 blocking,
  0 warnings, 3 notes, 7 observations.** O-1 (the change-log overstated which ids left the skills)
  and O-2 (this repo's own `project-preferences.md` still routed norms to Goal 4) are fixed in the
  records. The rest are accepted on the record.
- **Budgets:** `review-cycle.md` 7469 → 7460 and the framework injected footprint 3145 → 3142, each
  ceiling ratcheted to one over its reading. `session-hygiene.md` holds at 3040.

## Status

- [x] Chunk 01: reference docs (E-1 to E-19, P1)

## Chunk 01: reference docs

**Type:** cumulative-final
**Decisions:** E-1 to E-19.

**Files:** `plugin/docs/runbook-authoring.md` (E-1, E-5 to E-9), `plugin/docs/norms.md` (E-3, E-4,
E-10 to E-13), `plugin/docs/waivers.md` (E-14, E-15), `plugin/docs/test-report-contract.md` (E-2,
E-16, E-17), `plugin/docs/governance-telemetry.md` (E-18), `plugin/docs/discipline.md` (E-19);
`plugin/skills/runbook/SKILL.md` and `tests/preferences/test_registry_completeness.py`
(§ Found while applying).

**Tests:** find them by running, not by reading notes. Every test module that names a doc under
`plugin/docs/` or the runbook skill runs, without `-x`.

**Done when:**
1. Each Success bullet holds, and the suite passes.
2. P1 has run, and its result is recorded in this plan and in the audit's § Found while applying.
3. Committed, then one `/prawduct:critic cumulative` over the branch, with blocking findings
   resolved.
4. The Fable final-coherence pass has run over the whole audit cycle (W1 to W6) and its findings
   are dispositioned, before the PR merges.
5. Chunk marked `[x]`.
