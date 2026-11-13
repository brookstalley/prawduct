# Issue #1147 — critic: a seeded-defect check for review-protocol changes: Requirements

`status: draft · stage: requirements · area: critic · added: 2026-11-13 · source: owner rulings
2026-11-11 · issue: https://github.com/brookstalley/prawduct/issues/1147`

Related: #1130 (native review beside the boundary Critic) and #458 (shadow Critic A/B) compare
reviewers on real diffs with no ground truth; this item has ground truth. Sequencing: the owner
set the build aside on 2026-11-11 until 3tears-evals is ready (`.prawduct/owner-rulings.md`);
these requirements are the step that ruling left open ("requirements before any build").

## Problem

A change to the Critic's protocol prose is checked two ways: tests pin that the words are present
and inside the payload budget, and a review reads the prose. Neither observes what the prose does
to a reviewer. The one time it was measured (2026-11-11, `.prawduct/changes/read-cost-review.md`),
a new Goal 7 check raised every planted mistake and a real unplanted defect fell from 4 of 5 runs
to 1 of 18, in the one file the new check judged clean. That measurement was improvised: a
fixture kept outside git on one machine, scored by hand, with no rule for what difference counts.

## Goals

- G1. Two refs of this repository can be compared on known defects, and the result says, per
  defect, how often each ref raised it and at what severity.
- G2. A protocol change that lowers the catch rate of a reliably caught defect is reported as such
  before it merges.
- G3. No session that edits review prose can read the answer key, and the key does not leak into
  this (public) repository through the back door of results, examples or this document.
- G4. The instrument is itself checked: it has been seen to report a loss it should report
  (core.md: a check never seen to return non-zero proves nothing).

## Non-goals

- Running on ordinary work cycles or in CI. It runs by hand when the trigger paths (R1) change.
- Comparing reviewers on real diffs without ground truth (#1130, #458).
- Measuring the builder, the PR flow or any gate. Only what reviewers raise is scored.
- An absolute quality score for the Critic. Catch rates are read only as a paired difference.
- Listing the seeded defects here. This document names classes only (G3).

## Requirements

**Trigger and reach**

- R1. The trigger set is the reviewer payload, by the routes `tests/test_reviewer_payload_budget.py`
  already enumerates: `plugin/skills/critic/review-protocol.md`, `goals-1-3.md`, `cross-checks.md`,
  `framework-checks.md`, `coordinator.md`, and `plugin/agents/critic-reviewer.md`. One owner for the
  list: the benchmark reads it from that test's route table, not from a second copy.
- R2. Each run exercises the route the change touches: a change reaching `review-protocol.md` or
  the checks files runs a `cumulative` review on the three-reviewer roster; a change reaching only
  `goals-1-3.md` runs a `chunk` review. A change reaching both runs both.
- R3. A change inside the trigger set carries the benchmark's summary in its change record, or a
  stated reason it was not run. Something mechanical notices the absence (design picks the surface;
  a rule the author must recall is not enough).

**Separation**

- R4. The fixture, the key, the harness, the scorer and every raw result live in one private
  repository. This repository holds only these requirements, the design, and result summaries.
- R5. A summary returned to this repository names a defect by opaque id and class, with counts per
  arm. It carries no file path, no description and no reviewer text for held-out defects (R12).
- R6. Reviewers never run inside the benchmark repository. Per run, the harness builds a throwaway
  copy holding only what an ordinary governed product would: the application, its artifacts, a
  neutral git history (a base and the change set under review), and nothing that marks it as a
  benchmark (no key, no seeding commit messages, no fixture names, no prior results).
- R7. The copy's governance state is produced per run by the plugin at the ref under test, not
  stored. Where a deterministic `prawduct-hook` path produces it, that path is used in preference
  to a model session, so the two arms differ only in the plugin.

**The fixture**

- R8. One realistic expense-tracking application, grown from the 2026-11-11 fixture so its
  baseline runs carry over. It has a clean base and several change sets, each shaped like a
  plausible feature build with its own build plan, so a boundary review has a real bundle.
- R9. Seeded classes cover every Critic goal the route judges, at least two defects per class, so
  a class's result does not rest on one instance. Each class also has at least one clean
  look-alike that should not be raised, so a false-alarm rate is scored beside the catch rate.
- R10. Placement is a seeded variable, because the measured loss was positional: for each class,
  at least one defect sits in a file that holds a different class's clean look-alike (a file some
  other check would judge clean), and at least one sits in a file no check has an opinion on.
- R11. Every key entry records: id, class, goal, change set, location, the severity a correct
  review gives it, and its provenance (seeded, or found by a reviewer and adjudicated in).
- R12. The key is split into a development set and a held-out set. A protocol author may be shown
  development-set detail to diagnose a loss; held-out defects are reported under R5 only. A defect
  described anywhere public is development-set from then on. The unplanted defect of 2026-11-11 is
  already described in this repository's change record and starts there.

**The run**

- R13. Every run is a paired comparison of two refs (default: the integration branch against the
  branch under review). The real pipeline runs at each ref: `critic-begin`, the manifest's roster,
  the reviewers on the manifest's `reviewer_model`, `critic-consolidate`. No hand-rolled
  approximation of dispatch, and the scorer reads the consolidated review fact, not partials.
- R14. Arms are interleaved in time and pinned alike: same model id, same host version, same
  change sets. Each result records both plugin commits, model id, host version, route and date.
- R15. Initial sizing, tunable once variance is measured: 6 runs per arm, matching the baseline
  already held. Design states the wall clock and token cost of that (a three-reviewer review pays
  the protocol four times; 6 per arm is 12 pipeline runs and 36 reviewers), measured on the first
  real comparison, not estimated.

**Scoring and the refusal rule**

- R16. A finding is matched to a key entry by a judge that does not know which arm produced it
  (the blind sheet and key split in `.prawduct/research/native-review-paired/compare.py` is the
  local prior art). Per defect and arm the score records raised or not, the goal it was filed
  under, and whether it was a finding or only an observation.
- R17. A defect is *gating* when the baseline record catches it reliably: initial bar, raised as a
  finding in at least 9 of its last 10 baseline runs. Everything else is informational. Only
  gating defects can produce a refusal.
- R18. Refusal is two-step, so that one noisy batch cannot refuse a change. Screen: a gating
  defect whose candidate arm trails its baseline arm by 3 or more catches of 6. Confirm: 6 more
  runs per arm; the change is reported as lowering the catch rate when the pooled candidate arm
  has raised the defect in at most half the runs the baseline did. (For scale: 6 of 6 against 3 of
  6 is about 1 in 11 by chance under a one-sided exact test; 12 of 12 against 6 of 12 is under 1
  in 100. The thresholds are proposals for the owner, Q2.)
- R19. A severity demotion counts: a gating defect that the candidate raises only as an
  observation is scored as not caught for R18, and reported as demoted, not missed.
- R20. The report also states, per class, the candidate's gains (defects it raised more often) and
  both arms' false-alarm rates on look-alikes, so a refusal is read against what the change bought.
  The owner may accept a reported loss, as on 2026-11-11; the acceptance is recorded with the
  result.
- R21. A real defect a reviewer raises that is not in the key is adjudicated by a person and added
  with provenance, development-set by default. Until adjudicated it is neither a catch nor a
  false alarm.

**Proving the instrument**

- R22. Before it gates anything, the benchmark reproduces the 2026-11-11 result: the pre-read-cost
  protocol against the shipped one, same fixture, must report the known loss. A benchmark that
  shows no difference there is not ready.
- R23. A same-ref comparison (a ref against itself) is run once per fixture revision; it must
  produce no refusal, and its spread is the noise floor R15 and R18 are tuned against.

## Open questions (each needs an answer before design)

1. **Can a headless session drive the real pipeline end to end?** The CLI flags exist
   (`claude -p`, `--plugin-dir`), the path is untested, and two local facts cut against assuming
   it: a forked skill's `allowed-tools` was not a hard cap under `-p` in an earlier probe, and
   #1130's host facts found launch mode varying run to run. This is a spike, and R13 depends on
   it. If the forked `/prawduct:critic` cannot be driven headless, what is the nearest faithful
   route, and who rules that it is faithful enough?
2. **The refusal thresholds** (R17, R18). Proposed above from the one measurement there is. The
   owner sets them; R23's noise floor should be in hand first.
3. **How much may a protocol author see?** R12 assumes a held-out set reported only by id and
   class. That protects against prose tuned to the fixture and makes a held-out loss hard to
   diagnose. Alternative: no held-out set, and rotate fresh defects in on a schedule. Owner's call.
4. **Who may trigger a run, and with what budget?** Proposed: the owner, or a session the owner
   directs, with the measured cost of R15 stated before the run starts.
5. **Is governance state reproducible without a model?** R7 prefers a deterministic path. If
   onboarding a copy needs a model session, that session's variance lands in both arms; design
   must say how it is held equal (for example, one generated state shared by the pair is *not*
   available, since each arm's plugin must generate its own).
6. **Does the harness build on 3tears-evals or stand alone?** The build is sequenced behind it;
   whether it is a dependency or only a scheduling constraint is not recorded.
7. **Trigger reach beyond prose.** `critic_consolidate._derive_roster` and
   `model_tier.reviewer_model_for` change reviewer behaviour without touching R1's files. In the
   trigger set, or out?

## Acceptance (for this stage)

- [ ] Requirements reviewed by the owner; Q1 to Q7 each answered or explicitly deferred.
- [ ] Q1 spiked, with the result recorded on the issue.
- [ ] `documentation/issues/1147-design.md` written and the issue advanced to `stage:design`.

## Grounding

Read: the issue body; `.prawduct/owner-rulings.md` (2026-11-11 entries);
`.prawduct/changes/read-cost-review.md` (the measurement and its run counts);
`plugin/skills/critic/SKILL.md` and `coordinator.md` (pipeline, roster, `reviewer_model`);
`tests/test_reviewer_payload_budget.py` (payload routes);
`.prawduct/research/native-review-paired/` (blind-sheet scoring, host facts). Not read: the
2026-11-11 fixture and its result files, which are outside git on the owner's machine, so R8's
"grown from" and R22 are stated from the change record, not from the fixture. The chance figures
in R18 are hypergeometric tail values computed while writing, not taken from any run.
