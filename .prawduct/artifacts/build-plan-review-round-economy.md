---
artifact: build-plan
version: 2
scope: review-round-economy
# branch: feature/review-round-economy   <- uncomment when the branch is created; a claim on a
#                                           missing branch trips the session briefing's staleness check
partition: serial — every chunk edits `begin_review` / `cmd_critic_begin` or the critic skill's exit table; parallel chunks would conflict on each
program: consumer-overhead-program-2026-09.md (WS1 + WS4)
related_issues:
  - "brookstalley/prawduct#776 — budget inert on trunk-based repos (Chunk 01)"
  - "brookstalley/prawduct#724 — stale-evidence precondition for verify-resolutions (Chunk 02; design: documentation/issues/724-design.md)"
  - "brookstalley/prawduct#815 — round tally at dispatch (Chunk 03)"
  - "brookstalley/prawduct#731 — blast-radius prompt before the fix commit (Chunk 04)"
  - "brookstalley/prawduct#167 — NOT built here; decision-gated on Chunk 00's measurement (program Owner decision 3)"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → ENGAGED; this plan exists for it"
      - "a control names its expected yield and emits it observably → conforms; each new refusal appends a guard-refusal fact under its own guard name"
      - "proportionality ratchets both ways → conforms; Chunk 02's refusal applies to verify-resolutions only and has --force"
  - artifact: data-model
    dispositions:
      - "guard-refusal facts are observational, never authoritative, single sink `evidence.append_guard_refusal` → conforms; no refusal grants or removes coverage"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, on a documented scheme → ENGAGED: Chunk 02 takes exit 5 (see DECISION); the skill's exit table is the one home"
      - "additive-first evolution → conforms; no existing exit code changes meaning"
last_validated: 2026-09-16
---

# Build plan — review round economy

## Requirements Confidence

**Level:** Medium

**Why:** Chunks 01, 02 and 04 have written designs or triage answers. Chunk 03's threshold and
Chunk 00's metric definition are proposed here, not yet confirmed.

**Open assumptions / unknowns:**
- `[ASSUMPTION: #815's note fires from the 3rd round in a scope onward, counts verify rounds, and is suppressed when a refusal fires | MED impact | user can override the threshold]`
- `[ASSUMPTION: "rounds per scope" counts every review fact (all modes) whose manifest scope matches; wall clock is manifest dispatch → consolidate | MED impact | user can correct the definition]`
- `[DECISION: #724's refusal takes exit 5, not the exit 4 its design names | exit 4 shipped in v3.5.0 as budget-exhausted, and an exit code is contract; #167, if built later, takes 6 | user can veto]`
- `[DECISION: #776 is fixed, not retracted — when merge_base..HEAD is empty (trunk shape), the budget counts the scope's round facts directly | three surfaces name trunk repos as the reason the budget is scope-keyed; retracting would remove the only hard stop those repos have | user can veto]`

**What would raise confidence:** owner answers on program decisions 3–5.

## Status

- [ ] Chunk 00: Baseline — rounds-per-scope and verify-on-verify share on v3.5.1
- [ ] Chunk 01: The round budget counts on trunk-based repos (#776)
- [ ] Chunk 02: verify-resolutions refuses on stale test evidence (#724)
- [ ] Chunk 03: The round tally reaches the author at dispatch (#815)
- [ ] Chunk 04: The fix commit gets a blast-radius check (#731)
Context: Drawn 2026-09-16 from the consumer-overhead triage. Nothing built. Chunk 00 waits until
v3.5.1 has been installed in consumers for about a week; Chunks 01–02 need no baseline and may start
first.

## Chunk 00: Baseline — rounds-per-scope and verify-on-verify share on v3.5.1

- **Type:** doc-only
- **Description:** Re-take the triage's ledger measurement on consumers running v3.5.1, and add
  two numbers the triage lacked: p90 rounds per build-plan scope, and the share of verify-resolutions
  rounds whose anchor was itself a verify-resolutions fact with zero unresolved blocking (the #167
  class). The output answers program decision 3: is #167 still material after #814?
- **Deliverables:** new `.prawduct/artifacts/round-economy-baseline-2026-09.md` with per-repo
  numbers, the query used, and a one-line #167 verdict (build / don't build / re-measure date).
  A comment on #167 pointing at it.
- **Acceptance criteria:** every number states its window, repo set, and plugin version. The query
  is reproducible from the artifact alone.
- **Done when:** artifact committed; #167 comment posted; `/prawduct:critic`.

## Chunk 01: The round budget counts on trunk-based repos (#776)

- **Description:** `critic_consolidate.py`'s spent-round count intersects scope facts with
  `coverage.count_branch_rounds`, which admits only commits in `merge_base..HEAD`. After every push
  on a trunk-based repo that set is empty, so the budget never trips. When the branch span is empty
  (or the branch is the default branch), count the scope's full-round facts directly. Gitflow
  behaviour must stay byte-identical.
- **Deliverables:** the count fix in the budget helper; a corrected docstring. The change-log entry
  names the trunk shape.
- **Tests:** trunk repo, 6 full rounds on one scope, pushed → next full-round dispatch exits 4.
  Gitflow repo, same facts on a merged prior branch → not counted (regression). Verify rounds are
  never counted (regression).
- **Acceptance criteria:** the three tests pass; `python3 -m pytest tests/test_critic_dispatch_refusal.py` green.
- **Done when:** acceptance passes; `/prawduct:critic`; tick.

## Chunk 02: verify-resolutions refuses on stale test evidence (#724)

- **Description:** Build `documentation/issues/724-design.md` as written, with one amendment: the
  CLI exit is **5**, not 4 (DECISION above). The precondition runs right after the in-flight guard
  and calls `gates.tests_are_current` unchanged.
  **Known bound, stated rather than fixed:** within a session, `tests_are_current`'s session-fresh
  clause reports current on a moved tree (#767), so this refusal catches cross-session and
  failed/degraded evidence, not an in-session stale tree. WS6 owns that.
- **Deliverables:** as the design's Files touched table, with exit 5. `plugin/skills/critic/SKILL.md`
  exit table gains the row. The design doc gets a one-line amendment note about the exit number.
- **Tests:** the design's nine cases, with 5 in place of 4. Also: the budget refusal still exits 4
  (collision regression).
- **Acceptance criteria:** as the design's Acceptance list.
- **Done when:** acceptance passes; `/prawduct:critic`; tick.

## Chunk 03: The round tally reaches the author at dispatch (#815)

- **Description:** When `begin_review` dispatches in a scope that already holds ≥ 2 review facts
  (all modes), print the tally and challenge `coverage.py` already renders for the gate, as a NOTE.
  One computation, two carriers: call the gate's renderer, never re-word it. On a verify dispatch
  the note says verify rounds are how blocking findings clear, not an optional round. No note when
  Chunk 01's or Chunk 02's refusal fires.
- **Deliverables:** the note in `begin_review`'s ok path, via the existing tally renderer. The skill's
  step 4 names it in one line.
- **Tests:** round 2 → no note; round 3 → note carries the same text as the gate's; verify dispatch →
  the verify wording; refused dispatch → no note.
- **Acceptance criteria:** tests pass; the tally string has exactly one construction site
  (grep-checkable).
- **Done when:** acceptance passes; `/prawduct:critic`; tick.

## Chunk 04: The fix commit gets a blast-radius check (#731)

- **Type:** cumulative-final
- **Description:** Put #731's three enumerate-the-dependents questions (changed signature, return or
  error → callers; added output or field → governing contracts, including ones this changeset
  introduced; guard reordered, tightened or removed → what is now unreachable) into
  `next_action_line`. That is the carrier that reaches the builder on single-pass paths; the
  triage comment of 2026-09-02 shows `_BATCH_FIX_DIRECTIVE` does not. Print it only when the
  consolidated review has findings the builder will fix. `review-cycle.md` points to it and does
  not restate it.
- **Deliverables:** `next_action_line` text; one pointer sentence in `plugin/skills/critic/review-cycle.md`.
- **Tests:** a consolidation with blocking findings → the line carries the three questions; a clean
  consolidation → it doesn't; the questions have one construction site.
- **Acceptance criteria:** tests pass; the critic skill token-budget tests pass (declare any raise).
- **Done when:** commit; one `/prawduct:critic cumulative`; tick.

## Verification strategy

After Chunk 02, in a scratch governed repo: commit a change, run a review, make a fix commit without
recording tests, run `/prawduct:critic verify-resolutions` → expect exit 5 naming the reason; record
tests; re-run → dispatches. After Chunk 03, run three rounds in one scope and read the note on the
third.
