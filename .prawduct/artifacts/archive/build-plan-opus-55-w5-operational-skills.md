---
artifact: build-plan
version: 1
scope: opus-55-w5-operational-skills
branch: feature/opus-55-w5-operational-skills
partition: "01's backlog half (`plugin/skills/backlog/**`) goes to one delegate in a worktree the coordinator creates, in parallel with the main agent's half (every other skill in the wave). The halves touch disjoint prose files and are about the same size, so running them side by side roughly halves the wall clock. D-34 spans both halves, and each half applies its own site. Every test either half breaks belongs to the integrator. The delegate reports the edits it needs there instead of making them. The regression probe runs in a background agent that writes only to the scratchpad. W3 and W4 set the precedent."
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms, and it is the point of D-1, D-10, D-24, D-25, D-34, D-45, D-51, D-52, D-57 and D-59: a second copy of a fact becomes a pointer to its home, or goes"
      - "the plugin writes nothing into a governed repo except… → conforms: only plugin-shipped skill prose changes"
      - "goals and verification bind; prescribed method is advice → conforms: D-28 and D-46 turn a scoring script and a five-step choreography into the goal they served"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer surface changes. D-23 and D-45 trim `cache-reads.md`, which reviewers read, without changing its contract"
      - "authority fails closed; advice fails soft → inapplicable, because no gate verdict, exit code or advisory changes. Beyond prose and its test pins, the janitor's check 5 runs on the Issues backend again (an advisory survey, its blocker #729 shipped), and one test now checks every cache reader's grant"
      - "prawduct guides and reviews, it never implements → inapplicable"
      - "local-first governance coordination → inapplicable"
      - "written in Python, never specific to Python → inapplicable"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: one chunk, one boundary review"
      - "proportionality ratchets both ways → conforms: the wave deletes text; its one added control is a test of grants the cache readers already hold, and check 5 on Issues restores a survey that was off only while its blocker was open"
      - "review rigor is stage-keyed → inapplicable, because no severity rule changes"
      - "state-file growth is an advisory, never a block → inapplicable"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms: a pin on a sentence this wave rewrites is retired, or re-anchored on structure or on the interface token it protects. D-2, D-29 and D-30 are the slice's machine-read decisions, and each says what it keeps"
      - "model plan (Fable coherence before the cycle lands) → conforms: owed once, before W6 lands"
lifecycle: completed
archived: 2026-10-02
released_in: v3.7.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan: Opus 5.5 prompt audit — W5, operational skills

## Problem

The operational skills (`plugin/skills/*` except `critic` and `pr`) misfire on Opus 5.5 in four
ways. The evidence and the replacement text are in `opus-55-prompt-audit-2026-09/slice-D.md`, and
the owner ruled on 2026-09-28 (the audit's § Rulings):

- **Maintainer archaeology in runtime prompts.** Health checks, runbooks and adapter docs explain
  why they were built, what an earlier version got wrong, and which incident proved it. Examples are
  doctor's checks (D-2 to D-7, D-30 to D-32), the migration scrub (D-9, D-11 to D-14, D-35 to D-39),
  and issue ids, chunk ids and version pins throughout (D-17, D-19 to D-22, D-53). The model runs
  these on every invocation and reads each history as an instruction.
- **Duplicated facts that drift.** "Degraded because ungraded" is stated seven times in doctor
  (D-1). The label-provisioning map is in three skills (D-34). Upstream-filing mechanics, the
  Issues-backend field list, the write-through list and the `closed-by` handle rule each have a
  second copy (D-24, D-25, D-45, D-51). A `duplicate_alias` remedy sits under the wrong bullet
  (D-10).
- **Phantoms and fossils.** An envelope no code emits (D-15), retired ops and flags named in
  prohibitions (D-8, D-41, D-43), file-sync negations (D-49, D-55), and pointers to guidance a
  product's `CLAUDE.md` no longer carries (D-18).
- **Register, delegation and self-checks.** Shouted headings (D-54, D-58, D-61), `add` leading with
  delegation (D-26, F4), a methodology route that restates `delegation.md` (D-59, F4), an arithmetic
  ranking rubric (D-28), a scripted template diff (D-46), and a migration eyeball-check that the
  `verify-migration` gate supersedes (D-40, F3).

## Success

- **Every decision carries its slice-D replacement, or a recorded departure.** The Decisions line
  below lists them. Each replacement is located by its `evidence:` string, not by line number,
  because the files have moved since the audit.
- **The runbook skill's copies of slice-E findings are corrected** (the audit's W5 row):
  - The "best-evidenced finding in the whole literature" claim (E-1's `dup_of`) takes E-1's
    corrected wording or a pointer to `runbook-authoring.md`, whose own E-1 fix is W6's.
  - The "4.6–6.1%" hallucination rate (E-8's `dup_of`) takes E-8's undated wording.
- **The suite passes.**
  - Every sentence pin a rewrite breaks is retired or re-pointed, per the prose-test taxonomy.
  - D-23 and D-29 move rationale into test docstrings, and D-29 drops its two asserts
    (`"blanket"`, `"rejected"`), as ruled.
  - Each `"<lit>" not in` assertion in `tests/` is checked against the edited files at
    `origin/develop`. A negative pin on a phrase this wave deletes goes vacuously green.
  - After each deletion, `plugin/` and `documentation/` are grepped for the deleted passage's lead
    phrases, and for any other surface stating the same rule (by the state, not the words). A
    sentence another wave owns is fixed now only if this wave made it false.
- **One regression probe** (the audit's W4 recommendation: one per wave, aimed at a decision whose
  failure shows in its output). It runs on the session model, because `/prawduct:backlog` is a
  main-agent surface, and it confirms the model id from `modelUsage`.
  - **P1, D-28 (`pick` ranking).** A scratch markdown backlog holds items with `impact:`/`effort:`
    and two items missing both. One of those is high-value. The old and the new `SKILL.md` ride the
    system prompt, with the prawduct plugin disabled. The failure targeted is a top-3 ranking that
    contradicts value per effort, or an unassessed item ranked without being flagged as
    unassessed. The grading criteria are fixed before the runs. Two samples per arm.
- **No token ceiling moves.** No file in this wave has one (slice D § Budgets, re-checked
  2026-09-29).

## Out of scope

- `critic/` and `pr/` (W3, W3b), `plugin/docs/*` (W6), the methodology guides (W4).
- The slice-E outside-slice notes the audit's W5 row does not name: the runbook skill's restated
  budgets, its "Non-negotiables" list, and its Step 2 derivation-source list. They were not ruled.
- #915 (`migrate` reports success without checking the plugin loads). That is mechanism work; D-20
  only removes chunk ids from the same file.
- The thin product anchor's copy of A-18's shout (`anchor_repair.ANCHOR_V4`). The audit recorded it
  and did not propose it.
- Any change to what a gate decides, to a severity rule, or to a parsed field's format.

## Requirements Confidence: High

Every decision has replacement text and a ruling. These are the inferences:

- [DECISION: one chunk, with the backlog half delegated inside it | the wave is prose-only and not a
  risk surface, so one boundary review covers it, and review run count is the P0 lever | owner can
  veto]
- [DECISION: one regression probe, on D-28 | the audit's W4 recommendation, which the owner did not
  veto. D-28 is the one decision in this wave whose failure shows in an output that can be graded. D-40,
  the wave's one `model_dependent` decision, needs a live GitHub migration to exercise | owner can
  veto]
- [DECISION: D-58 applies A-18's wording pattern to `methodology/SKILL.md`, as the audit's W1 notes
  ask | the two decisions agree, so no departure | owner can veto]

## Found while applying

- **The template carries a third copy of E-1's overstated claim** (`plugin/templates/runbook.md`,
  "Length is the best-evidenced defect in the whole literature"). E-1 names it as a `dup_of`, but W4
  did not take it and W6 owns only `plugin/docs/`, so nobody else would.
  [DECISION: corrected here to the same hedged direction the skill now states | a correction is not
  deferred to a wave that doesn't own the file | owner can veto]
- **D-57's replacement named `prawduct-hook print-install-reference` in onboard**, which grants
  nothing by that name, so `test_every_instructed_command_is_granted[onboard]` went red. The mention
  is a cross-reference to doctor's check, not an instruction to run it.
  [DECISION: onboard says "grades it against the plugin's published contract" instead of naming the
  command | granting a command onboard never runs would widen its tool list for a pointer | owner
  can veto]
- **D-18's ruled "Run `/prawduct:critic` after each chunk" is false on a short plan**, which defers
  per-chunk reviews to one boundary run.
  [DECISION: janitor says "as each chunk's "Done when" directs", the wording `methodology/SKILL.md`
  already uses | the ruled text was as wrong as the text it replaced | owner can veto]
- **D-25 moved a guarded sentence.** `test_skill_prose_field_list_matches_the_derived_writable_set`
  pinned SKILL.md's closed-world list of writable block fields, which D-25 replaced with a pointer to
  `adapter-mode.md`. That file's list was split across a clause ("With `--affected`, … above, these
  are the only writable block fields") that no single-sentence regex can read.
  [DECISION: `adapter-mode.md` states the list in one sentence, and the guard now reads it there.
  Red-verified by dropping `--closed-by` from the sentence | the guard protects a closed-world claim
  against the CLI, and it has to sit on the claim's one home | owner can veto]
- **D-23 and D-29's rationale moved into test docstrings as ruled**
  (`test_skill_command_grants.py`, `test_cutover_prose_coherence.py`). D-29's two asserts
  (`"blanket"`, `"rejected"`) are dropped.
- **The delegate's recorded departures,** all vetoable. Its diff was read in full after the merge,
  not taken from the summary.
  - [DECISION: D-24 — adapter-mode's write-operations intro points `file-upstream`'s preview at
    `/prawduct:report-bug` | the block below no longer describes preview]
  - [DECISION: D-40 — step 7's "the check *Spot-check* could not yet make" names "the step 5 rollup"
    | D-40 renamed step 5 and removed its checks]
  - [DECISION: D-35 — also drops "(#728)" and names "the Step 1 export backup" for "the MG2 export
    backup" | the audit's line list missed both]
  - [DECISION: D-25 — the Claims paragraph's "`--working-branch` (see above)" points at
    `adapter-mode.md` § update | "above" pointed at the list D-25 removed]
- **Four stale sentences the delegate found and no decision covers,** fixed here because they are
  in this wave's files:
  - `migration-scrub.md` step 2 said "`search --like` is a post-cache accelerator, not available in
    the cacheless service". No `--like` exists in `plugin/`, and the service has a cache. The
    instruction now just says to read the source or the `list` output.
  - "no longer yields" and "all learned the hard way" (D-38's class) and SKILL.md's "MG4/G1"
    (D-35's class).
  - SKILL.md's `lib/backlog_probes.py` citation resolves, so it stays.
- **No other surface restates what this wave deleted.** A sweep of `plugin/` and `documentation/`
  for the queued envelope, the retired flags, the incident names and the dated rates found only
  `documentation/backlog-service-api-contract.md` and its test spec. They describe the queue as an
  optional layer, which is still true.
- **The negative-pin scan came back clean.** Of the `"<lit>" not in` literals this wave removed from
  its files, every one asserts against runtime output (stderr, probe evidence), not these files.

**P1 outcome (2026-09-29, D-28, Opus 5.5).** Each subject ran `claude -p --model claude-opus-5-5
--setting-sources project --strict-mcp-config --settings
'{"enabledPlugins":{"prawduct@prawduct":false}}'`, with the arm's `SKILL.md` appended to the
system prompt. The new arm differed from the old only in the Score step (the diff was checked). The
fixture was a nine-item markdown backlog: two items with no `impact:`/`effort:`, one of them a
data-loss bug with a one-line fix, and one low-value/high-effort item. The criteria were fixed
before the runs. All four runs have `modelUsage` = `claude-opus-5-5` (re-derived from the raw
JSON), and none quotes the digest.
- **Both arms, 2 of 2:** the same top 3, with the data-loss bug first, the low-value/high-effort
  item never in the top 3, and every unassessed item flagged as missing its fields.
- **Differences:** the old arm printed numeric scores (3.0, 2.0, 0.33), and one old run said the
  formula put the data-loss bug "only around fifth" before overriding it. The new arm computed no
  score. Mean output was about 2,470 characters new, 2,900 old.
- **Result: no regression.** The control did not fail either, so this is not evidence that D-28
  helps.

## Status

- [x] Chunk 01: operational skills (D-1 to D-61, the runbook skill's E-1 and E-8 copies, P1)

## Chunk 01: operational skills

**Type:** cumulative-final
**Decisions:**
- **Main agent:** D-1 to D-8, D-18 to D-22, D-30 to D-34 (its doctor and onboard sites), D-46 to
  D-49, D-54 to D-61, and the runbook skill's E-1 and E-8 copies.
- **Delegate (`plugin/skills/backlog/**`):** D-9 to D-17, D-23 to D-29, D-34 (its migration-scrub
  site), D-35 to D-45, D-50 to D-53.

**Files:**
- Main: `plugin/skills/doctor/SKILL.md`, `plugin/skills/janitor/SKILL.md`,
  `plugin/skills/onboard/SKILL.md`, `plugin/skills/migrate/SKILL.md`,
  `plugin/skills/methodology/SKILL.md`, `plugin/skills/ping/SKILL.md`,
  `plugin/skills/repo-disable/SKILL.md`, `plugin/skills/runbook/SKILL.md`.
- Delegate: `plugin/skills/backlog/SKILL.md`, `plugin/skills/backlog/adapter-mode.md`,
  `plugin/skills/backlog/cache-reads.md`, `plugin/skills/backlog/migration-scrub.md`.
- Integrator: `tests/test_skill_command_grants.py` (D-23's docstring),
  `tests/test_cutover_prose_coherence.py` (D-29), and every test the run turns red.

**Tests:** find them by running, not by reading notes. Grep `tests/` for each edited file's name
and each rewritten phrase, then run what the grep finds **without `-x`**. A pin can be built from a
constant, and a literal grep can't see it. `opus-55-prompt-audit-2026-09/pins_D.txt` is the audit's
cross-check of test literals against these files.

**Cumulative review (`rev-20260929T151553Z-d97c0bcb`): 0 blocking, 3 warnings (2 distinct), 10
notes.** Fixed in one pass, then one `verify-resolutions` (`rev-20260929T152314Z-f0e0aaa0`: 0
blocking, all three warnings resolved):
- **R-1/R-9:** the moved D-23 docstring claimed a test enforced the cache-query grant for four
  readers, and only the PR reviewer's was tested.
  `test_every_cache_reader_admits_both_cache_query_spellings` now covers all four. It was
  red-verified by dropping the janitor's and the critic-reviewer's grants.
- **R-6:** janitor check 5 said the Issues backend has no `promoted` state. Its `in-progress`
  status is that state, and `cache-query open` returns it, so the check now runs on both backends.
- **Notes fixed:** doctor's could-not-run rule names #12 and #17's exceptions (R-2). #14's reason
  is true now (R-3). The D-29 test's name matches what it checks (R-4/R-8). The guard's comment
  says it is bounded at the clause (R-5).
- **Accepted:** R-7 (the pinned "not being a third" still states the rule), R-10 (D-32's ruled
  deletion; nothing renumbers the checks), R-11 to R-13 (informational).

**Done when:**
1. Each Success bullet holds, and the suite passes.
2. P1 has run, and its result is recorded in this plan and in the audit's § Found while applying.
3. Committed, then one `/prawduct:critic cumulative` over the branch, with blocking findings
   resolved.
4. Chunk marked `[x]`.
