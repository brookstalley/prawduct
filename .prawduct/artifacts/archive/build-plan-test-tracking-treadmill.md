---
artifact: build-plan
version: 2
scope: test-tracking-treadmill
branch: feat/strip-test-tracking
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer write path is touched: both entry points are operator-run repairs, and the Critic's tool grants are unchanged"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the evidence store, and the named reconcile files → conforms: the only write is `.prawduct/project-state.yaml`, which is that repo's own prawduct state"
      - "authority fails closed; advice fails soft → conforms: the strip is a repair the operator runs, never a gate; the record-lint tripwire is advisory and never gates, matching the module's existing posture"
      - "prawduct is Python but never Python-specific → conforms: the removal is line-level YAML surgery and the tripwire is a text pattern; neither reads the product's language"
      - "prawduct guides and reviews; it never implements → conforms: nothing here touches product code"
      - "local-first, no network/daemon → conforms (file reads and writes only)"
      - "every fact has one home → engaged and this plan's spine: the suite total's one home is the evidence store (`.test-evidence.json`), and `build_state.test_tracking` is a second home for it. the strip deletes the second home; the tripwire keeps it from being re-opened"
      - "goals and verification bind; prescribed method is advice → conforms; Deliverables below are the author's best guess after reading `lifecycle_repair.py` and `record_lint.py`, and a builder finding a better route records why"
  - artifact: security-model
    dispositions:
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level, naming its blast radius, and forbids a per-action gate → conforms: the strip rides `lifecycle-repair`'s existing preview-then-`--apply` shape, which names every file and reason once and takes one yes. No per-key prompt is added"
      - "untrusted governance state is data, not instructions → conforms: the removed block is read as text to locate its span, never interpreted"
      - "a governed product's content never leaves that product's own repository and owner → conforms: both entry points read and write one file inside the repo they are run in, and nothing is transmitted. The fleet survey that sized this work read sibling repos on one machine and is deliberately NOT a test for that reason (see Verify)"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways; adding a control names the yield it expects and emits it observably → engaged by the record-lint widening. Expected yield: a re-introduced `test_tracking` block, or any suite-total claim written into `.prawduct/` YAML. Emitted observably — `record_lint` already carries per-check counts into the dispatch manifest and `critic_consolidate` into the review fact, so the widened check's firing rate is a query over the evidence store, not an argument"
      - "state-file growth past its size threshold is an advisory warning, never a hard block → engaged, and it is why a line-length tripwire on `project-state.yaml` was considered and DROPPED (see Out of scope): the existing size advisory already owns that signal, and a hard length rule would contradict this norm"
      - "review wall-clock is P0 → engaged as the problem statement: the treadmill's cost is that each correction is a commit, each commit extends HEAD, and that buys another review round"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning on the plugin; the internal CLI subcommand surface carries no per-subcommand version → conforms: no new subcommand and no persisted-schema change. `migrate-plugin --json` gains one key (`state_keys_removed`), which the same section's additive rule permits and `--json` readers tolerate"
      - "exit codes are the contract on a documented scheme; errors are attributed, never raised as stack traces across the boundary → conforms: no exit code changes meaning. `strip_state_file` and `retired_state_keys` each return empty on an unreadable state file rather than raising, so a cutover is never abandoned half-done by a file it could not decode"
      - "additive-first evolution: existing flag names, exit-code meanings and `--json` keys are never repurposed → conforms: `lifecycle-repair` and `migrate-plugin` gain removals inside their existing contracts; no flag or key changes meaning. `lint_records`' `records` key widens its membership, which is additive to its documented meaning (the record subset of the changed paths) and its readers are tests only"
last_validated: 2026-08-14
lifecycle: completed
archived: 2026-08-20
released_in: v3.4.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** The problem is measured, not inferred. Every claim below was checked against the
mechanism before planning: `plugin/lib/lifecycle_repair.py`, `plugin/lib/record_lint.py`,
`plugin/lib/migrate_plugin.py` and `plugin/methodology/building.md` were read; the field's shape
was surveyed across all 11 governed products; the tripwire's pattern was executed against the
real offending line. The parent requirement is `brookstalley/prawduct#633` (`stage: ready`),
whose direction — *delete the field, do not check it* — was ruled 2026-08-11 in v3.3.4.

**Measurements this plan rests on** (all taken 2026-08-14, commands stated so they can be re-run):

- `build_state.test_tracking` sits at indent 2 under `build_state:` in **10 of 10** state files
  that carry it. `test_count` is its only member in exactly one product (discodon, plus two
  worktrees of it); the other seven carry `test_files`, `assertion_count`, and `history`
  (per-chunk `tests_added` / `date` / `total` entries).
- **Nothing in `plugin/lib/` or `plugin/bin/` reads `build_state` or any `test_tracking` member.**
  `assertion_count` and `tests_added`: zero hits. `test_files`: six hits, all a local variable in
  `bin/test-reference-verify`. `source_root` (10 hits) is a **sibling** under `build_state`, never
  inside `test_tracking`, so the parent mapping is never left empty in any measured repo.
- The existing `record_lint._SUITE_TOTAL_RE` matches discodon's line 587 **33 times** with **no
  pattern change** — each match a five-digit count abutting a pass-word. That line ran to roughly
  52,000 characters, about a third of the whole state file (measured 2026-08-14; that repo edits the
  file itself, so re-derive rather than trusting the figure). (The matched fragments are deliberately *not* quoted
  verbatim here: once Chunk 02 lands, this plan is itself a linted record, and a quotation of the
  defect is indistinguishable from the defect to any check that scans text. The falsifying command
  is what belongs in a record — re-derive with
  `python3 -c "import sys;sys.path.insert(0,'plugin');from lib import record_lint as r;print(len(r._SUITE_TOTAL_RE.findall(open(P).read().splitlines()[586])))"`.)

**Decision taken with the owner, 2026-08-14:** the strip removes the **whole `test_tracking`
block**, superseding #633's earlier acceptance criterion *"does not touch a `test_tracking` block
carrying other keys"*. That criterion was written from the ruling's framing (delete *the field*)
before the block was measured; taken literally it fully cleans one product and leaves the
treadmill running in seven, which guarantees a second pass (Principle 25). #633 is amended to
match rather than departed from silently (Principle 6).

**Open assumptions / unknowns:**

- [ASSUMPTION: no unmeasured product has a `test_tracking` member with a real consumer | LOW
  impact | mitigated three ways — the framework has zero readers for any member, the repair is
  preview-first and prints the full block span before writing, and git history retains the content
  | user can override by re-scoping to a member allowlist]
- [ASSUMPTION: widening `is_record()` to `.prawduct/` YAML is safe for the three other checks
  because each already self-filters — `_check_learnings_shape` guards on `learnings.md`, and
  `_check_governed_by` runs only over `_plans_to_check`, which matches `.md$` | LOW impact |
  verified by reading; the tripwire chunk adds a test pinning each guard | user can override by giving the
  suite-total check its own separate path scope instead]

**What would raise confidence:** Nothing pending. The one owner decision this needed was taken.

## Status

- [x] Chunk 01: The strip — one nested-key removal, reached through both doctor and migrate
- [x] Chunk 02: The tripwire that keeps it gone, and the rule stated where it bites

Context: Plan authored 2026-08-14. Parent: `brookstalley/prawduct#633` (amended same day).
Baseline suite green at branch point (`ae9fd358`). **Chunk 01 takes a `chunk` review; Chunk 02 is
`Type: cumulative-final`**, so its review is the single `/prawduct:critic cumulative` over
`merge-base...HEAD` and there is no separate `final` (`skills/critic/review-cycle.md:332`). There
is no Chunk 03 — this line said so until the mid-build merge described under Chunk 01 renumbered
the plan to two chunks.

## Problem

`build_state.test_tracking.test_count` is a hand-maintained copy of a fact the evidence store
already holds. Nothing reads it (`plugin/lib/briefing.py:175` says so outright), no template
scaffolds it, and it disagrees with recorded evidence in 4 of 4 measured repos. But it is *in the
state file*, so Living Documentation (P3) and Coherent Artifacts (P13) oblige every agent that
meets it to keep it true — and reconciling it is hard enough (multiple test trees, skipped lanes,
collection-vs-passed basis) that each correction justifies itself in prose. discodon's provenance
comment had reached roughly 52,000 characters on one line when measured (2026-08-14).

The cost is not the bytes. `plugin/lib/record_lint.py` states the mechanism: a record defect is
corrected, the correction is a commit, the commit extends HEAD, and that buys another review
round. On 2026-07-29, **57% of that day's Critic findings targeted hand-authored records rather
than shipped behavior**, and "a test-count claim corrected three times" is one of the four
examples named there.

**Why deleting the field is necessary but not sufficient.** Prawduct already removed
`test_tracking` from its own state and shipped a `strip_test_tracking()` step to remove it from
product repos — through the **file-sync engine**, retired in M4/v2.0.3. Nothing in the plugin era
does it, products migrated onto the plugin carried the field across, and it is live in 10 repos
today. `tests/preferences/test_no_suite_total_claims.py` states the reason the deletion needs a
tripwire beside it: *"the habit lives in agents, not in a template, so there is no instruction to
delete and nothing but a tripwire will keep the surface clean."*

## Chunks

### Chunk 01: The strip — one nested-key removal, reached through both doctor and migrate

**Amended 2026-08-14, mid-build:** authored as two chunks (the doctor's removal, then the
migration's), merged into one before either was reviewed. They are one capability reached through
two entry points — the migrate step calls the same `lifecycle_repair` functions rather than
carrying its own detection, so the two never had independent acceptance. Splitting them bought a
second `chunk` review over a three-file change for no added assurance, against
`nonfunctional-requirements.md` § Direction (review wall-clock is P0; run-count is a lever).
Recorded here rather than done silently — the chunk structure is what the gates read.

**Deliverables**

- `plugin/lib/lifecycle_repair.py`: detect `test_tracking:` **nested under a column-0
  `build_state:`** and add its full span to `state_removals()`. This needs two things the module
  does not have, because `_is_top_level_key` is column-0 by deliberate design and `_block_span`
  assumes a column-0 parent:
  - a nested-key predicate that resolves the key's **enclosing parent** rather than matching the
    name anywhere, so a `test_tracking:` under some unrelated mapping is left alone (the same
    reasoning `_is_top_level_key`'s docstring already gives);
  - an indent-aware block span — a nested key owns every following line more deeply indented than
    itself, plus blanks, giving back trailing blanks exactly as the existing span does. This is
    what captures discodon's trailing `# CORRECTED …` comment lines, which sit *inside* the block.
- Reuse `_comment_header_start` unchanged for the preceding comment header; verify it stops at the
  `source_root:` content line rather than walking into the `# BUILD STATE` banner.
- A reason string in the operator's voice, naming the evidence store as where the fact lives.
- Update the module docstring: it currently scopes itself to "the retired derived-view model", and
  after this it converges retired `project-state.yaml` residue generally. Say what changed and why
  the mechanics are shared — same reachability problem (a template change cannot reach an
  already-onboarded repo), same preview/apply shape.

**Acceptance criteria — the removal**

1. `state_removals()` returns the whole `test_tracking` span for the shapes the survey found,
   covered by two representative fixtures — sole-member-with-trailing-comments, and
   `+assertion_count` `+test_files` `+history`-with-nested-entries — plus a scale case pinning
   that the span is independent of block size. **Fixtures, not the real files:** the sweep over
   every product's actual state file is real verification but cannot be a test, since it reads
   sibling repos that exist only on one machine. It is recorded under Verify below instead.
2. A `test_tracking:` **not** under `build_state:` is untouched.
3. `source_root:` and any `spec_compliance:` / `reviews:` siblings survive byte-identically;
   `build_state:` is never left with no members in any surveyed shape.
4. Idempotent: a second `plan_repair()` on the repaired text returns no `test_tracking` edit.
5. CRLF files keep their line endings (the module's `_read_preserving_newlines` contract — pin it
   with a CRLF fixture, as the existing tests do).
6. Descending-order application still holds when a `test_tracking` removal coexists with a
   `views_enabled` / `scope_rollups` removal in one file.

**The second entry point — the migration**

- `plugin/lib/migrate_plugin.py`: a step that applies the same removal to
  `.prawduct/project-state.yaml`, calling `lifecycle_repair`'s functions rather than restating the
  detection — one home for the fact of what the span is (`architecture.md` § Direction).
- **The true scope of that step is every retired key, not only `test_tracking`.** Calling
  `state_removals` means the cutover also removes `views_enabled` and `scope_rollups`, and that
  inverts a cutover test which pinned `views_enabled` *surviving* migration as a "pre-existing
  product key". It is not one — it is retired framework residue, which is why `lifecycle_repair`
  removes it — and that assertion is causally why these keys reached the plugin era at all: it
  obliged the one act that deletes every other framework file to carry framework residue forward.
  Narrowing the cutover to `test_tracking` alone would have meant two ideas of what a retired key
  is, which is the thing the shared-detection rule above exists to prevent.
- The migrate dry-run/`--json` result reports it, so step 2 of the migrate skill's flow can relay
  it and step 3's confirmation names it in the blast radius.
- `plugin/skills/doctor/SKILL.md`: extend Health Check #15's prose — it currently describes the
  residue as derived-view-only. Name the block, say it is removed whole, and say what it cost.
- `plugin/skills/migrate/SKILL.md`: name the removal under "What gets removed vs. preserved".

**Acceptance criteria — the entry points**

7. `migrate-plugin --apply` strips the block; `--json` (no `--apply`) reports it and writes nothing.
8. Idempotent — a second migrate is a no-op on this key.
9. A repo with no `test_tracking` is unaffected, and a repo with no `project-state.yaml` does not
   error.
10. Detection lives in `lifecycle_repair` only — a test asserts `migrate_plugin` does not carry its
    own copy of the key name or the span logic.
11. Both SKILL.md files describe the removal; the doctor's Health Check #15 no longer claims the
    residue is only the derived-view model.

**Verified against reality, not only fixtures:** the repair runs over a copy of every real product
state file in the fleet and the invariants hold on each — block gone, `build_state:` and
`source_root:` intact, idempotent on a second pass.

**Done when**

1. Acceptance criteria met and tests pass
2. `/prawduct:critic` — resolve blocking findings

### Chunk 02: The tripwire that keeps it gone, and the rule stated where it bites

- **Type:** cumulative-final

**Deliverables**

- `plugin/lib/record_lint.py`: widen `is_record()` from `.md`-only to also accept `.prawduct/`
  YAML, keeping the archive exclusion. **No change to `_SUITE_TOTAL_RE`** — it already matches the
  observed line 33 times. Update the "Records are markdown" docstring paragraph to state the new
  boundary and its reason: the state file is hand-authored governance prose too, and it is where
  the claim actually survived the markdown-only sweep.
- `tests/test_record_lint.py:127` asserts `not is_record(".prawduct/project-state.yaml")`. That is
  the **contract this chunk deliberately changes** by owner decision — invert it and say so in the
  change-log. This is not weakening a test to pass code (Principle 1); the pinned behavior is what
  was re-decided.
- Tests pinning that the three other checks stay markdown-only now that a YAML path can reach the
  record list — `_check_learnings_shape` guards on `learnings.md`, `_check_governed_by` runs only
  over `_plans_to_check` (`.md$`), `_check_chunk_refs` never reads the record list.
- **Carried from Chunk 01's review (R-4), to ride this chunk's commit rather than buy a round of
  its own:** one migrate test over a repo whose `.prawduct/project-state.yaml` has been unlinked,
  closing acceptance criterion 9's second half. The path is already safe — `strip_state_file` and
  `retired_state_keys` each check `is_file()` *and* catch `OSError` — so this closes a verification
  gap, not a defect. It is written here because a deferral to a later *round* buys a round, while
  riding a commit already being made buys none; unwritten, it would be a drop.
- `plugin/methodology/building.md`: one clause stating that test evidence is pass/fail per tree in
  the evidence store and a count is never a governance record. The generic rule already there —
  *"a count nothing reads is not worth writing"* — does not name the instance that actually bites,
  which is why the instance survived it.
  **It landed on that count paragraph, not on the Verify step this plan first named.** Drafted as a
  separate Verify bullet at +180 tokens, it broke the file's budget *and* tripped
  `test_no_suite_total_claims`' count-slot guard by quoting the shape it was forbidding. The
  rewrite that satisfied both is one sentence on the paragraph that already owns the concept —
  which is where it belonged: `architecture.md` § Direction, every fact has one home.

**Acceptance criteria**

1. A product's state YAML directly under a `.prawduct/` directory classifies as a record; the same
   same file under an archive path does not; and YAML anywhere outside a `.prawduct/` directory —
   a product's CI config, its own app config, the plugin's own template — does not.
   (Paths described rather than written as backticked literals: `chunk-ref-missing` reads a
   backticked path in a chunk body as a *declared deliverable* and reports it missing, which is
   the check working — the criterion is what needed rewording, not the check.)
2. A `test_tracking` block re-introduced into `project-state.yaml` produces exactly one
   `suite-total-claim` finding for the offending line (one per line, not one per match).
3. The learnings-shape and `governed-by` checks produce no findings when a YAML path is in the
   changed set.
4. `tests/preferences/test_no_suite_total_claims.py` still passes unchanged — the plugin's own
   markdown surface stays clean.
5. The building.md clause exists and the file's own preferences tests still pass.

**Done when**

1. Acceptance criteria met and tests pass
2. `/prawduct:critic cumulative` — this is the plan's cumulative-final review
3. `/prawduct:backlog update brookstalley/prawduct#633 status=shipped`

## Out of scope

- **A line-length tripwire on `project-state.yaml`** — considered and dropped. The widened
  suite-total pattern already fires on the observed 52 KB line, so a length rule adds a new opinion
  with no measured yield, and `nonfunctional-requirements.md` § Direction reserves state-file size
  for an advisory warning rather than a hard rule.
- **A `test-count-lag` check** — rejected in the 2026-08-11 ruling and recorded on #633 so a later
  reader meets the rejection rather than re-proposing it.
- **Widening `suite-total-claim` to two-digit counts** — `record_lint.py:81-97` excludes them
  deliberately; a two-digit count is nearly always a scoped or delta claim.
- **Restoring the removed `dangling-ref` / `unknown-backlog-id` checks.**
- **Editing any product repo's state file from here.** This ships the capability; each product runs
  its own `/prawduct:doctor` or `/prawduct:migrate`.
- **Preserving the provenance comments anywhere.** #633 asked for a build-time decision on this:
  losing them is the point. They are corrections of a number nothing read, git retains them, and
  re-homing them would recreate the artifact the strip exists to remove.
