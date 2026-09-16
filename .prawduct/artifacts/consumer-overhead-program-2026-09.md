---
artifact: program
scope: consumer-overhead-2026-09
status: proposed
drawn: 2026-09-16
parent_evidence: .prawduct/artifacts/consumer-overhead-triage-2026-09-16.md
---

# Program — cut consumer governance overhead (2026-09)

## Problem

Governed product repos spend their governance time re-reviewing and re-testing work that is
already known good. Since 2026-08-01, seven active consumer repos recorded **~205 Critic hours**
(discodon 651 reviews / 96h alone). `verify-resolutions` is **55–66% of runs and 35–50% of
hours**, with 0.14–0.65 findings/review in five of seven repos. Recurring causes, each seen in 3–6
of the 7 repos: post-review commits (often acting on NOTE-class findings) that reopen coverage;
fix commits that introduce the next round's defect; coverage discarded on a merge-conflict
resolution; full-suite re-runs of trees that already passed; advisories that fire every session with
nothing to do. Full evidence: the triage artifact above.

## Success

Measured from consumer governance ledgers (`prawduct-hook review-stats` plus
`.governance-ledger.jsonl` filtered by date), comparing a 4-week window after each workstream ships
against the baseline below. Same repos, same query as the triage (`scratchpad ls.py` shape: group
review facts by scope, count by mode, sum wall clock).

| Metric | Baseline (2026-08-01 → 09-16) | Target |
|---|---|---|
| verify-resolutions share of Critic runs | 55–66% | ≤ 45% |
| verify-resolutions share of Critic hours | 35–50% | ≤ 30% |
| Rounds per build-plan scope, p90 | not yet computed — first deliverable of WS1 Chunk 00 | −30% |
| Full-suite re-runs on an already-recorded green tree | not instrumented | 0 on branch switch / `/clear` (WS6 acceptance) |
| Advisories firing ≥ 5 consecutive sessions with no state change | not instrumented | 0 for the WS7 set |

Framework-internal reference (this repo, 2026-09-16 re-measure in
`build-plan-review-loop-termination.md`): mean reviews/chain 2.7, VR share 55%, 19.2 min/chain.

**Measurement caveat, stated up front:** most of the baseline predates v3.5.0 (2026-09-12, review
round budget) and all of it predates #814 (accept observations on the record). Some of the target
may already be met by those; the WS1 Chunk 00 baseline is re-taken on v3.5.1 consumers before any
refusal ships, so a later improvement is not credited to the wrong change.

## Out of scope

- **#292** (defer per-chunk reviews on short plans) — largest per-plan saving but an owner trade-off
  on early detection; revisit with #291 data.
- **#771 / #816** — whether governance records are review subjects. Decision before build.
- **#181 / #342 / #191** — structural deletion passes; indirect and L.
- Any change that grants coverage without a review fact (the `review-loop-termination` Chunk 03
  cut stands: no miss-rate increase is accepted in exchange for round count).

## Workstreams

| WS | Work | Issues | Plan | Stage |
|---|---|---|---|---|
| 0 | Cut v3.5.1 (ships #814, #817) | — | release runbook (parent session) | in progress |
| 1 | Pre-dispatch round economy | #776, #724, #815 (+ #167 gated) | `build-plan-review-round-economy.md` | ready (Chunks 00–03); #167 decision-gated |
| 2 | Finish and release learnings-v2 | #744 (closes #652, #685) | existing `build-plan-learnings-v2-docs.md` Chunk 05 on `feature/learning-system-v2` | awaiting owner merge of PR #759 |
| 3 | Failing test ids in evidence | #792 (+ #680 residue) | `build-plan-test-failure-ids.md` | ready |
| 4 | Blast-radius prompt before the fix commit | #731 | folded into WS1 plan as Chunk 04 | ready (carrier answered by triage: `next_action_line`) |
| 5 | Coverage survives non-judgeable conflict resolution | #672 half 2 + denial voice | `build-plan-transfer-denial-voice.md` | Chunk 01 ready (spec exists); Chunks 02–03 design-first |
| 6 | Multi-slot test evidence | #653, #679, #767(b) | `build-plan-test-evidence-slots.md` | design-first |
| 7 | False-positive sweep | #809, #813, #765, #818, #811, #762 slice, #301 | `build-plan-false-positive-sweep.md` | mixed: 3 ready, 4 design-first |

WS4 is folded into WS1's plan because both edit `plugin/lib/critic_consolidate.py` and the critic
skill's exit/next-action prose; two plans there would conflict on every chunk. It stays a separate
row so its metric (fix-caused rounds) is reported separately.

## Ordering and parallelism

| Lane | Workstreams, in order | Owns (files no other lane edits) | Shared — coordinate |
|---|---|---|---|
| A — critic | WS1 (Chunks 00–04) | `critic_consolidate.py`, `skills/critic/SKILL.md`, `skills/critic/review-cycle.md`, `cmd_critic_begin` in `prawduct-hook` | `prawduct-hook` (single file, different subcommands) |
| B — evidence | WS3 → WS6 | `test-evidence` / `test-status` in `prawduct-hook`, `gates.tests_are_current` / `test_status`, `.test-evidence.json` shape | `gates.py` with lane C |
| C — coverage | WS5 | `coverage.diagnose_base_advance_transfer`, `gates.transfer_remedy` / `record_transfer_grant` | `gates.py` with lane B |
| D — sweep | WS7 | `plan_archive.py`, `api_versioning_probes.py`, `norm_probes.py`, `operator_verification.py`, `templates/change-log.md`, `change_log.py` docstring, `core._contract_diff` | none |
| E — release | WS0 now; WS2 after owner merges #759 | version files, `plugin/CHANGELOG.md` | every lane appends to `plugin/CHANGELOG.md` `-dev` section — rebase, don't hand-merge |

Lanes A–D can run in parallel worktrees. `prawduct-hook` and `gates.py` are single large files
shared across lanes; the edits are in disjoint functions, so expect textual rebases, not semantic
conflicts. **Hard sequencing:**

1. **WS3 before WS6.** WS6 redesigns the evidence record; WS3 adds a field to it. Building WS6 first
   would design the slot schema without the failing-ids field and migrate twice.
2. **#767 option (a) never ships before WS6.** Strict tree-keying `test-status` before multi-slot
   evidence forces a suite re-run after every commit. WS6 ships #767 option (b) (disclosure only).
3. **WS1 Chunk 02 (#724) interacts with WS6.** Refusing a stale-evidence verify pushes a suite run
   ahead of the round. That trade is right (a suite run is cheaper than a wasted round and it was
   owed anyway), but its cost falls fastest once WS6 lands; measure WS1 before and after.
4. **WS2 and WS0 share a version number** — see Owner decisions.
5. **WS5 Chunk 01 depends on the unmerged `fix/coverage-honesty` branch** — see Owner decisions.

## Owner decisions

1. **v3.5.1 vs learnings-v2.** `build-plan-learnings-v2-docs.md` Chunk 05 records the owner's call
   (2026-09-15) that learnings-v2 ships as **3.5.1**, and its `gates.json` rows carry
   `since: 3.5.1`. Cutting develop as 3.5.1 now makes those wrong. *Recommendation:* cut now as
   3.5.1 (the round-economy fixes are already late for consumers), and re-pin learnings-v2 to
   3.5.2 in its merge commit.
2. **`fix/coverage-honesty` is complete and unmerged** (12 commits, Chunks 01–02 closed
   2026-09-10, no PR). *Recommendation:* PR it to develop before WS5 starts; WS5 Chunk 01 is its
   split-out Chunk 03.
3. **#167 — does a refused verify leave the PR gate uncovered?** Yes, as designed: the refusal
   records a guard-refusal fact, which `data-model.md` § Direction forbids from becoming
   authoritative, so the delta stays uncovered. And the cumulative gate's own fix-churn NOTE
   (`gates.py`) tells the builder that "ONE verify-resolutions closes it", which the #167
   refusal would then block: the gate and the dispatcher would contradict each other.
   *Recommendation:* do not build the #167 refusal now. #814 attacks the same churn at the
   cheaper point, before the commit. Re-measure the verify-on-verify share on v3.5.1 consumers
   (WS1 Chunk 00); build #167 only if it is still material, and then with a coverage answer
   designed first.
4. **#776 — fix or retract.** *Recommendation:* fix it. When the branch span is empty (trunk shape),
   count the scope's round facts directly. Recorded as a vetoable [DECISION] in WS1.
5. **#815 threshold.** *Recommendation:* show the note from the 3rd round in a scope onward (two
   already spent), counting verify rounds and saying they are not optional. Suppress it when a
   refusal fires, because the refusal already prints the tally.
6. **#301 — patch or retire the trivial gate.** *Recommendation:* retire it. Its sibling fast-path
   was retired on the same unsoundness (fileset-as-detector). WS7 Chunk 03 is written for
   retirement.
7. **#811 — which fix.** *Recommendation:* (c) name the rejected heading and say what the caller can
   do, plus (b) surface an unparseable queue as a NOTE when the requirement is off. Don't widen the
   parser (a); one heading grammar is the contract.
8. **#762 — scope.** *Recommendation:* ship detection only (`git check-ignore` in `_contract_diff`,
   report "wholesale ignore subsumes N entries"). Never rewrite a user-authored `.gitignore` rule.
9. **Diagnosis fix #6** (tell the agent a full review returns 13–18 true findings regardless of
   round) is still unfiled (`build-plan-review-loop-termination.md` advisory note 3).
   *Recommendation:* file it, and land it after WS1 with a re-measurement.

## What I'd do differently

The largest lever is not in this program. It is WS0 and WS2, which ship work that is already
built. Everything else is sized small on purpose. If only one lane can run, run A (WS1 Chunks
00–02): verify rounds are the dominant cost, and those chunks are mechanical with written designs.
