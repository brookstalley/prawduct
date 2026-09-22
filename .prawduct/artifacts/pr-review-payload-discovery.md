---
artifact: discovery
scope: pr-review-payload
depends_on:
  - artifact: nonfunctional-requirements
last_validated: null
---

# Discovery — the PR reviewer's payload, not its goals

**Date of every measurement below: 2026-09-18.** Re-derive rather than trusting the digits:
`tools/pr-review-yield.py` for this repo's ledger, `tools/measure-consumer-overhead.py ../discodon`
for a consumer's. Both grow as the corpus does.

**Owner's framing this answers:** the PR reviewer takes ~13 minutes per run in the largest
consumer, up from ~5, while producing steadily less per minute. Target: ~2 minutes, without
materially impacting quality. The owner's suspicion — that much of the reviewer's work is wasted
time and tokens — is what the measurements below test.

---

## 1. The finding: the goals are cheap, the payload is not

`tools/pr-review-yield.py` over this repo's 122 `review.pr` events:

| | |
|---|---|
| Median duration | 420s (300s in June → 480s in September) |
| Findings | 279 — 1 blocking, 96 warning, 182 note |
| Median files reviewed | 14.5 |
| Cost vs. size | ≤5 files → 260s median; ≥20 files → 480s. Fixed cost dominates. |

`tools/measure-consumer-overhead.py ../discodon --prs` puts the same reviewer at 13.1 min/review
in the v3.5 window against 4.9 in v2.1, across 178 reviews with **zero blocking findings ever**.

> **Correction, 2026-09-22.** Every duration in this section, both 13.1 and the 420s median above,
> is the reviewing model's own estimate. Where a PR review has since been clocked (dispatch mark to
> evidence write), it takes about a minute: 77s median over 19 reviews in this repo, against 240s
> estimated on the same rows. discodon's PR reviews are not clocked yet. Re-derive with
> `prawduct-hook review-stats --json` (`by_role_model_mode`, `duration_measured`); the reasoning is
> `documentation/consumer-build-metrics.md` hazard 2.

The reviewer's goals are four, and answering them is not what costs. What costs is establishing
context. Priced against a representative branch — `feat/pr-review-payload`'s parent, 18 files,
2,428 diff lines — at ~4 bytes per token:

| Mandated input | bytes | ~tokens | consumer |
|---|---|---|---|
| `.claude/rules/learnings/core.md`, **auto-injected** | 100,336 | 25.1k | none in this role |
| root `CLAUDE.md`, auto-injected | 7,499 | 1.9k | none — the protocol governs |
| `core.md` **again**, protocol step 6 | 100,336 | 25.1k | 1 finding in 122 reviews |
| `project-state.yaml`, protocol step 1 | 55,392 | 13.8k | two fields |
| `review-protocol.md` | 18,050 | 4.5k | the instructions |
| the active build plan, protocol step 5 | 21,517 | 5.4k | ~25% of findings |
| `.critic-findings.json`, protocol step 4 | 7,162 | 1.8k | no goal reads it |
| `git diff <base>...HEAD` | 148,151 | 37.0k | everything |
| **total** | **458,443** | **~115k** | |

Roughly **57% of the reviewer's context has no consumer in its own protocol.** Worse for wall
clock, the protocol's six numbered steps plus the backlog reconciliation, the test-status read
and the default-branch check are **13–18 sequential tool round-trips before the first judgment**.
Each is a full model call against a context growing toward 115k tokens. Turn count, not prefill,
is what converts a payload into minutes.

## 2. The duplicate is verified, not inferred

Claude Code's subagent documentation states that a non-fork subagent's initial context contains
"every level of the CLAUDE.md hierarchy the main conversation loads, **including project rules**",
and that `omitClaudeMd: true` in the agent's frontmatter is the documented opt-out. `.claude/rules/`
files are project rules. So `core.md` arrives in the PR reviewer's context before it acts, and
`review-protocol.md` step 6 then instructs it to read the same file again.

`briefing.py`'s `generate_subagent_briefing` already knows this — a comment there records it as the
reason the subagent briefing carries no learnings section. That reasoning was never carried to
`review-protocol.md`, which predates it. One mechanism, two carriers, one updated.

The duplicate is not merely redundant, it is **unusable**: the protocol's own Learnings Cross-Check
section forbids this reviewer from scanning the diff against those rules, because the `final` /
`cumulative` Critic owns that walk. Measured yield of the one goal that consumes them: **1 finding
across 122 reviews.**

## 3. The reviewer that runs is not the reviewer the protocol describes

All four goals are written as though the subject were product code — scope creep, narrative,
debug statements, bundle-level simplification. Classifying all 279 findings by subject matter:

| subject | share |
|---|---|
| change-log coherence | 47.7% |
| build-plan status / dangling pointers | 25.4% |
| backlog reconciliation (R-1 / R-2) | 15.4% |
| retired or collided tag keys (`scope=`, `chunks=`, `release=`) | 9.7% |
| test-evidence staleness | 2.9% |
| **debug code, stray files, secrets — the stated Merge Hygiene bullets** | **0.7%** |

That classification is a **keyword** pass over finding summaries, not a hand classification —
it reports what a finding is *about*, and deliberately not whether a deterministic check could
replace it. Hand-reading the 60 most recent Merge Hygiene findings says roughly a fifth could be
mechanized (a scope-key collision `check-releasability` already detects, a retired `chunks=` tag, a
`test-status` exit code, a backlog status disagreement) and the rest are semantic prose judgments
no gate can make: a change-log paragraph describing the branch's first commit rather than what
ships; a docstring narrating review history; two carriers of one fact disagreeing.

**This is the reviewer's real value and nothing else in the pipeline provides it.** The `.prawduct/`
bookkeeping surface is non-judgeable by the coverage algebra, so the Critic never reviews it. The PR
reviewer is the only layer that reads it — by accident of being the only layer that reads everything.

## 4. What this repo has already decided

- **`nonfunctional-requirements.md` § Direction** makes reviewer **payload** a declared lever:
  *"cost = unit-cost × run-count, and both factors are levers — … unit-cost via the reviewer's
  payload (what a given mode must load to answer its goals)"* (amended 2026-07-29). This work is an
  application of that norm, not a new argument.
- **§ Performance** sets the PR boundary at **≤ 7 minutes wall clock** and states that the
  cumulative Critic and the PR review *"run in parallel, never sequentially — any sequencing that
  exists is for narrative framing, not a data dependency, and is a target for removal."*
  `skills/pr/SKILL.md` runs them sequentially (Step 2 → Step 3). Filed as **#678**.
- **Stage-keyed rigor** (ratified 2026-09-17) puts the PR review at the **boundary** stage, which
  *"is never skipped or inferred away."* Cutting the review is off the table; cutting its payload
  is the only lever the norm leaves.
- **#652** — *role-scope the ~51k-token subagent briefing* — is this problem filed from the
  briefing side, before the auto-injection path was understood.

## 5. A defect found on the way, not fixed here

`nonfunctional-requirements.md` records a **2026-09-16 owner ruling keeping the `pr-scoped` review
mode** — the first evidence-based run of the proportionality norm's removal-by-default arm.
`grep -rn "pr-scoped" plugin/` returns nothing. The mode's 30 ledger events run
2026-06-10 → 2026-07-10, and `artifacts/archive/build-plan-kernel-evidence-store.md` records the
collapse `pr-scoped`/`pr-full` → `pr`.

So the removal arm's first real run **graded a control that had already been removed two months
earlier**, from historical ledger rows, and ruled to keep it. Nothing was harmed — keeping a
retired thing is inert — but the ruling's clause (c), which asks whether `pr` and `pr-scoped` have
converged in yield, cannot be answered and does not protect the reviewer this plan changes.

**This needs an owner ruling, not a silent edit** — amending a norm to match the code is the
laundering tell. Carried into the build plan's last chunk as a decision to surface, not to make.

## 6. Recommendation, and the honest limit

Five changes, in dependency order. The first four remove waste: **no goal is dropped and no finding
class stops being checked.**

1. **Measure before optimizing.** `duration_seconds` is self-reported by the reviewing model
   (`tools/pr-review-yield.py` reports `0 measured, 122 self-reported`). A 2-minute target stated
   against an estimate is not a target. Record a code-written dispatch timestamp.
2. **One payload command instead of twelve reads** — deterministic, so it passes *facts* and never
   the caller's reasoning, which is what the reviewer's independence actually protects.
3. **Delete the learnings read** (§2) and the output the caller never consumes: the protocol asks
   for a markdown `## PR Review` block *and* a JSON file, plus a PR draft that `SKILL.md` Step 5
   re-drafts anyway.
4. **Dispatch as a named agent with `omitClaudeMd: true`**, removing the auto-injected 27k tokens.
5. **Run it concurrently with the cumulative Critic** (#678, and the norm already requires it).

**Items 1–4 project to roughly 4–6 minutes, not 2.** Payload falls ~115k → ~49k tokens and turns
~15 → ~4, but the floor is the 37k-token diff plus the semantic read that produces the findings.
Reaching 2 minutes means shrinking what the reviewer reads *of the diff* — the first change with a
real quality cost, and one that should be argued against measured post-change numbers rather than
bundled in on a projection.

**Re-pointing the goals (§3) is a scope decision, not waste removal.** It is the change most likely
to move yield in either direction, and it is why chunk 05 re-runs the measurement before the work
is called done.
