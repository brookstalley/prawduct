---
artifact: build-plan
version: 1
scope: opus-55-w3-review-machinery
branch: feature/opus-55-w3-review-machinery
partition: 01's PR-side half (`skills/pr/*`, `agents/pr-reviewer.md`, and the tests only they read) goes to one isolated-worktree delegate, run in parallel with the main agent's Critic-side half. The two halves touch disjoint prose files. The tests both halves read (`test_v5_methodology.py`, `test_reviewer_payload_budget.py`, `test_cutover_prose_coherence.py`, `test_control_yield_tokens.py`, `test_prose_severity_ceiling.py`, `preferences/test_free_interval_prose.py`) belong to the integrator, and the delegate reports the edits it needs there instead of making them. W1 set the precedent for delegation.
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: C-10 cuts the provenance of the tool boundary and keeps the boundary itself in both agent definitions (read-only tools, no test/build/product execution, no mutation of the reviewed session, the write allowlist)"
      - "every fact has one home → conforms, and it is the point of C-4, C-9 and C-11: the reviewer's copy of a protocol fact becomes a pointer to the protocol, which is the home"
      - "goals and verification bind; prescribed method is advice → conforms: C-23 removes review-strategy coaching and keeps the goals and severities. Where a slice's replacement would drop content a reader acts on, the content stays in plain words and the departure is recorded"
      - "prawduct guides and reviews, it never implements → inapplicable, because only framework prose changes"
      - "authority fails closed; advice fails soft → inapplicable, because no gate verdict, exit code or advisory changes; only prose and its test pins move"
      - "the plugin writes nothing into a governed repo except… → inapplicable, because nothing new is written"
      - "local-first governance coordination → inapplicable, because no coordination mechanism changes"
      - "written in Python, never specific to Python → inapplicable, because no gate's language dispatch changes"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: one chunk, one boundary review. F6's rounds-per-PR baseline was recorded before this wave, in the audit artifact's § F6, and the comparison reruns the same script"
      - "review rigor is stage-keyed → conforms: no severity rule moves. C-1 changes what the PR reviewer reports, and disposition stays the builder's call, with ACCEPT as the default"
      - "proportionality ratchets both ways → conforms: this wave deletes text and adds no control"
      - "state-file growth is an advisory, never a block → inapplicable"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms with one recorded exception class: a test pinning a sentence this wave rewrites is retired as a descoped requirement, or re-anchored on structure or the interface token it protects (C-23 deletes `test_signals_and_work_scaling` with its text). The exception class is absence guards on deleted text, named in the [DECISION] under Requirements Confidence"
      - "model plan (Fable coherence before the cycle lands) → conforms: owed once, before W6 lands"
lifecycle: completed
archived: 2026-10-02
released_in: v3.7.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan: Opus 5.5 prompt audit — W3, review machinery

## Problem

The review machinery is the prose the Critic and the PR reviewer read, plus what the builder reads
to drive them. On Opus 5.5 it misfires in four ways:

- **Filters ahead of reporting.** The PR reviewer is told to file only what a maintainer "would
  genuinely want" and to flag oversize or a simplification only when it is cheap (C-1). The Critic
  reviewer is told not to "invent findings" (C-22) and is coached on review depth by work size
  (C-23). A literal-following model reads each of these as a reason to stay quiet, and recall
  drops.
- **Copies inside one context.** Each reviewer reads its agent definition and its protocol, and
  both carry the same rules in different wordings (C-4, C-9, C-11). There is also a report format
  that no reader of that file uses (C-3).
- **History where an instruction should be.** Issue numbers, dates, "an earlier draft",
  migration-relative phrasing, harness-version provenance and defences of past design choices sit
  inside the steps (C-6, C-7, C-10, C-12, C-15, C-16, C-19, C-21, C-24). The builder carries
  `pr/SKILL.md`'s share of it on every `/prawduct:pr` (C-13, C-14).
- **Register.** Capitals, and bold on most sentences in a paragraph (C-17, C-18). There is also a
  fixed progress-note cadence (C-2).

The Critic goal files say BLOCKING applies "where ratified norms exist". `norms.md` § Severity
scopes BLOCKING to *adopted* norms (slice E's note on E-4).

The evidence and replacement text are in `opus-55-prompt-audit-2026-09/slice-C.md`. The owner ruled
on 2026-09-28 (the artifact's § Rulings).

## Success

- Every decision in the Decisions line below carries its slice-C replacement, or a recorded
  departure. The replacement is located by its `evidence:` string, not its line number, because
  W1 and W2 moved lines.
- C-7's sibling sweep has run over the Critic files (`#[0-9]{3}`, `20[0-9][0-9]-`, `earlier draft`,
  `used to`, `now do`). Each hit is either cut or kept with a one-line reason in the chunk's
  Found-while-applying, and the pinned measurements ("23%", "13.5", "18.4") are kept.
- `review-protocol.md` and `goals-1-3.md` say BLOCKING applies where the product has *adopted*
  norms. `review-protocol.md` names `norms.md`'s "Severity, stated once" paragraph. `goals-1-3.md`
  states the scope inline, so its reader never has to open another file.
- Every token ceiling a trimmed file sits under is lowered in the same commit. Those are the
  per-file ceilings in `test_v5_methodology.py` and the route sums in
  `test_reviewer_payload_budget.py`.
- The suite passes. Every sentence pin a rewrite breaks is retired or re-pointed, per the prose-test
  taxonomy. For each `"<lit>" not in` assertion in `tests/`, `<lit>` is checked against the edited
  files at `origin/develop`. A negative pin on a phrase this wave deletes would go vacuously green.
- **Probe, on Sonnet 5.5** (F1: the reviewer surfaces are read by subagents), with the old text as
  control:
  - **C-1:** a PR reviewer gets a bundle that carries one real, cheap-to-accept release-readiness
    defect. The case to use is a changeset that is oversized and not cheaply splittable, plus a
    change-log entry that describes the branch's history rather than the delta against base. The
    failure targeted is that the defect goes unreported.
  - **C-22/C-23:** a dispatched Critic reviewer gets a small ("trivial"-sized) diff that carries
    one borderline WARNING. The failure targeted is a clean pass.
  - The control must show the failure for the probe to show that the decision helps. If it does
    not, the result is recorded as "no regression", as W1 and W2 recorded theirs.
- The comparison against F6's rounds-per-PR baseline is owed once W3 has shipped enough PRs to
  measure. It is recorded as due, not run here.

## Out of scope

- **C-8 and C-20, the two `move` decisions.** C-8 splits `review-cycle.md` and C-20 moves the
  Coordinator Pattern. They go to their own plan, W3b, which follows this one before W4.
- The flags C-26 to C-29. C-25, an `add` the owner did not take.
- W4 to W6. That includes `norms.md`'s own enforcement-table wording (E-4, W6) and `building.md:107`
  (W4).
- Any change to what a gate decides, to a severity rule, or to the evidence schemas.

## Requirements Confidence: High

Every decision has replacement text, and the owner has ruled on it. The one inference is the
split below.

- [DECISION: C-8 and C-20 move to their own plan, W3b, which runs right after this one | the audit
  says they "could be their own plan", and planning.md says to split when the change types
  differ. These two are structural moves with test re-pointing, while everything else is in-place
  prose. C-7 and C-21 rewrite sentences that C-8 then moves, so rewriting first and moving second
  never moves text that is about to change | owner can veto and fold them in]
- [DECISION: one chunk, with the PR-side half delegated inside it | `plugin/skills/` is a
  `risk_surface`, so a multi-chunk plan infers a per-chunk review for each chunk. One chunk gives
  one boundary review, and the review run count is the P0 lever | owner can veto]
- [DECISION: two tests pin the ABSENCE of deleted text, which the prose-test taxonomy's "never a
  sentence" does not allow:
  - `test_pr_reviewer.py::test_the_value_filters_stay_out_of_the_review_protocol` pins C-1's four
    value-filter phrases.
  - `test_critic_consolidate.py::test_review_cycle_prose_states_no_cadence_of_its_own` pins the
    pattern `every N minutes`.
  
  Each guards a ruled removal whose regrowth no interface token can show. C-1's filters depress
  recall, and the probes can't catch a regression. A restated cadence would drift from its one home
  in code. Every other sentence pin the wave touched is retired, or re-anchored on structure or an
  interface token (`base_branch:`, `review.pr`, the numbered steps of "## What to do") | owner can
  veto and retire either test]
- [DECISION: C-10's replacement text said "Your tools are read-only" and dropped the clause asking
  the reviewer to stay inside its `tools:` list. `Bash(...)` patterns are declared, not enforced,
  and the W3 cumulative's own reviewer ran commands outside the list. So the clause is restored:
  "its `Bash(...)` patterns are a contract you keep, not a fence the harness enforces" | the ruling
  applies replacement text unless that makes a sentence false, and this one did (R-6) | owner can
  veto]
- [DECISION: Chunk 01 is ticked although its done-when's Sonnet 5.5 probe ran on Sonnet 5 | the
  Agent tool's alias could not reach 5.5 from this session. The owed rerun of both reviewer-surface
  probes is scheduled in the audit's § Rulings (F5 note) to ride W4's probe session, rather than
  holding a reviewed wave open for a model this session cannot select | owner can veto and hold the
  tick]
- [ASSUMPTION: the Agent tool's `sonnet` alias resolves to Sonnet 5.5, which the owner reports
  shipped 2026-09-28. The probe records the model id that actually ran | LOW impact | owner can
  correct]

## Found while applying

- **C-2's `machine_read: no` was wrong.** `test_critic_consolidate` bound the prose's "every 4
  minutes" to `critic_consolidate._CACHE_WARM_INTERVAL_MINUTES`, which the wait message
  interpolates. The cadence stays in code: its reason (prompt-cache warmth) holds, #368 is dropped,
  and C-2 ruled on the prose only. The binding test now pins that the prose states no interval.
- **C-19's rewrite dropped the `prawduct-hook` prefix** from `critic-discard` and `critic-restore`.
  That left their `_NOT_GRANTED` exemption rows stale. The rows are removed, as that test
  instructs.
- **The delegate found four slice notes that were wrong.** C-4's wording does not keep "If either
  disagrees". That pin was re-pointed, and later deleted as a sentence pin by the review. C-16(a) had no new home for the Step 3 assertions,
  because the agent definition was already pinned. Two pins were missed entirely: `#254` and "Clean
  up evidence file".
- **`documentation/issues/712-design.md` quoted a sentence C-16(d) rewrote.** It is corrected.
- **The sibling sweep also cut four history phrases C-7 didn't list:** "the number nothing measured
  before", "the review that prompted this rule", "used to infer", and "can no longer disagree". It
  kept the pinned measurements and "Measured at ten rounds", which is the reason for the
  verify-mode rule.
- **The negative-pin scan came back clean.** No `"<lit>" not in` pin reads a literal this wave
  deleted from these files.
- **The delegate's recorded departures,** all vetoable:
  - [DECISION: C-5 also drops "(table at the end)", because the table is deleted]
  - [DECISION: C-5 deletes `SKILL.md`'s `:190` whole, because the dispatch prompt already says to
    use the path as given]
  - [DECISION: C-12 cuts "rather than from the shares below", because the shares are deleted]
  - [DECISION: C-18 keeps bold on bullet lead labels as structure, plus at most one command or
    stop condition, and keeps every bold span a test quotes. Bold spans went from 144 to 82]

## Status

- [x] Chunk 01: review machinery prose (C-1 to C-7, C-9 to C-19, C-21 to C-24, E-4 alignment)

## Chunk 01: review machinery prose

**Type:** cumulative-final
**Decisions:**
- **Critic side (main agent):** C-2, C-3, C-7, C-9, C-10 (the `critic-reviewer.md` half), C-19,
  C-21 (both Critic files), C-22, C-23, C-24, and the E-4 alignment in `review-protocol.md` and
  `goals-1-3.md`.
- **PR side (delegate):** C-1, C-4, C-5, C-6, C-10 (the `pr-reviewer.md` half), C-11, C-12, C-13,
  C-14, C-15, C-16, C-17, C-18, and C-21's `plugin/skills/pr/review-protocol.md` half.

**Files:**
- Critic side: `plugin/skills/critic/SKILL.md`, `plugin/skills/critic/review-cycle.md`,
  `plugin/skills/critic/review-protocol.md`, `plugin/skills/critic/goals-1-3.md`,
  `plugin/skills/critic/framework-checks.md`, `plugin/agents/critic-reviewer.md`.
- PR side: `plugin/skills/pr/SKILL.md`, `plugin/skills/pr/review-protocol.md`, `plugin/agents/pr-reviewer.md`.

**Tests:** find them by grepping `tests/` for each edited file's path and for each rewritten
phrase. Don't trust a slice's `machine_read: no`. So far the grep finds these:
- Delegate-owned: `test_pr_reviewer.py`, `test_pr_reviewer_agent.py`, `test_pr_review_payload.py`,
  `test_pr_evidence_contract.py`.
- Integrator-owned: `test_v5_methodology.py`, `test_reviewer_payload_budget.py`,
  `test_critic_reviewer_agent.py`, `test_critic_skill_metadata.py`,
  `tests/preferences/test_critic_skill_structure.py`, `tests/preferences/test_free_interval_prose.py`,
  `test_cutover_prose_coherence.py`, `test_control_yield_tokens.py`,
  `test_prose_severity_ceiling.py`, `test_finding_scope_rule.py`.

**Also check:** every other site that states the same rule. By the state, not the words:
- C-2's wait guidance also appears in `building.md` and the digest.
- C-17's never-skip-the-reviewer appears in the stop gate's text.
- C-21's freshness signal appears wherever `test-status` exit codes are explained.

A sentence another wave owns is fixed now only if this wave made it false.

**Probe outcome (2026-09-28):** four fresh agents, each answering from the prompt files alone,
with the old text as control.
- **The `sonnet` alias resolved to `claude-sonnet-5`, not Sonnet 5.5,** in all four runs, so the
  plan's assumption was false. F1's floor probe on Sonnet 5.5 is still owed. The Agent tool's alias
  offers no way to pick 5.5 from here.
- **C-1 (PR reviewer).** Both texts reported both defects at WARNING: the change-log entry that
  narrates branch history, and the oversized bundle. The control did not suppress the oversize
  finding: it judged the split cheap and flagged it. So this probe shows no regression, not that
  C-1 helps. The new-text run left the split to the builder, as C-1 intends.
- **C-22/C-23 (Critic reviewer).** Neither text gave a clean pass, so the control did not show the
  targeted failure either. The new text rated the untested "unset keeps 3" requirement BLOCKING,
  which is the protocol's rating for untested required behaviour. The old text folded it into a
  WARNING. That is one sample, not evidence of a shift.
- W1, W2 and W3 have now all probed without a control that fails. A small single-diff scenario
  does not make a Sonnet reviewer under-report here. The recall question F6 raises is answered by
  the rounds-per-PR comparison, not by these probes.

**Done when:** each Success bullet holds, the suite passes, and the probe has run. The review is
one `/prawduct:critic cumulative` over the branch. Commit first, then run it once.
