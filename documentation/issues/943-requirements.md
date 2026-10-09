# Issue #943 — program: refresh the consumer-overhead program against current backlog: Requirements

`status: draft · stage: requirements · area: critic · added: 2026-10-09 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/943`

Related: #724, #815, #731, #672, #895, #679, #680, #811, #762, #301 (the still-open remainder, see
the status table). Out of scope: building any of the five plans (issue scope-out).

## Problem

On 2026-09-16 a session drew a consumer-overhead program: a program doc
(`consumer-overhead-program-2026-09.md`), a triage artifact
(`consumer-overhead-triage-2026-09-16.md`) and five build plans. It never landed. It sits on
`origin/docs/consumer-overhead-program` (3 commits over merge-base `94ea57a0`; the branch is now
~390 files behind `develop`, so a merge would revert most of the tree and cannot be landed as-is).
Since then the work it describes was mostly done as individual backlog items, v3.6.0 → v3.7.0 shipped,
and the program's `status: proposed` table no longer describes the backlog. The decision this item
owns: does the program still stand, as a document, or is it retired?

## Grounding facts

Re-derivable. Measured 2026-10-09 against `develop` @ `317de616` (v3.7.0 + 3.7.1 patch) and the
GitHub-Issues backlog.

- **Branch content is nine files only.** `git diff --name-status 94ea57a0 origin/docs/consumer-overhead-program`
  shows seven added artifacts under `.prawduct/artifacts/` (program, triage, five build plans), plus
  edits to `.prawduct/project-state.yaml` and `plugin/CHANGELOG.md`. Only the seven artifacts are
  worth preserving; the two edits are stale against `develop`.
- **Status of each plan's issues** (closed-set from `list_issues state=CLOSED since=2026-09-16`;
  open-set from the open list):

  | Plan (workstream) | Issues | Now | Verdict |
  |---|---|---|---|
  | review-round-economy (WS1, WS4) | #776 closed; #167 closed; #724 open (`stage:ready`, design exists); #815 open (`stage:design`); #731 open (`stage:design`) | 1 of 4 chunks' issues shipped; adjacent round-cost work also shipped (#829, #831, #832, #851, #866, #882, #845; v3.6.1 "fix after a clean review waits for next review") | **partly shipped; three chunks still open** |
  | test-failure-ids (WS3) | #792 closed; #680 open (`stage:design`) | the named fix shipped | **shipped; #680 residue open** |
  | transfer-denial-voice (WS5) | #672 open (`stage:ready`, design exists); #956 closed; #895 open (`stage:ready`) | the stacked-base case split out as #895/#956; the prose-conflict tolerance (Chunks 02–03) never started | **still open** |
  | test-evidence-slots (WS6) | #653 closed; #767 closed; #679 open (`stage:design`) | v3.6.1: runs are "recorded against the exact code they tested", switching back to a passed branch runs nothing | **shipped; #679 residue open** |
  | false-positive-sweep (WS7) | #809, #813, #765, #818 closed; #811, #762, #301 open | 4 of 7 shipped | **mostly shipped; three open** |

- **Program metrics were never baselined for the targets that matter.** The program's own table
  says "not yet computed" for rounds-per-scope p90 and "not instrumented" for suite re-runs and
  advisory repeats. Its baseline window (2026-08-01 → 09-16) predates v3.5.0, v3.6.0, v3.6.1 and
  v3.7.0 — all of which changed review cost.
- **Measuring tool exists.** `tools/measure-consumer-overhead.py <consumer-repo> [--since --until --prs --json]`
  groups a consumer's ledger by plugin version window. It needs a consumer clone with a populated
  governance ledger; a fresh session has none (this repo's clone-shared store is empty in a new
  container).
- **Prior decisions still bind.** The program's owner decisions 3 (do not build the #167 refusal;
  #167 is since closed) and 9 (file the "13–18 true findings regardless of round" diagnosis; whether
  it was ever filed was not checked) were never confirmed by the owner — they were the author's
  recommendations.

## Requirements

- **R-1 Per-plan verdict.** Each of the five plans is marked `shipped`, `partly shipped`,
  `still open` or `dropped`, with the issue numbers and the evidence for the verdict (issue state,
  release, or commit). The table above is the draft; it is re-derived from the backlog at the time
  the verdict is recorded, not copied.
- **R-2 Open work lives in the backlog, not in a plan.** Every chunk still open maps to exactly one
  open backlog item (the table gives the mapping). A chunk with no backlog item gets one filed, in
  the same change that records the verdict (rule: file the item the moment it should exist). A
  chunk whose item is closed is marked shipped, never left to read as pending.
- **R-3 Baseline re-measured, or its absence stated.** The baseline is re-taken by running
  `tools/measure-consumer-overhead.py` against the consumer repos, over windows keyed to the
  v3.5.0 / v3.6.0 / v3.6.1 / v3.7.0 tags. If a consumer clone is not reachable from the session
  doing this, the verdict says so and records the command and the repos to run it on; it must not
  carry the 2026-09-16 numbers forward as if current.
- **R-4 Land or retire, with the reason.** The outcome is one of:
  - **Retire** (recommended): the program's open remainder is a list of ordinary backlog items, no
    lane or sequencing constraint beyond what those items already carry (see R-5). Preserve the
    seven artifacts by committing them under `.prawduct/artifacts/archive/` (or a single archived
    program record), marked `status: retired`, with the reason and date; then delete
    `docs/consumer-overhead-program` from origin.
  - **Land a rewritten program**: only if R-5 finds a sequencing constraint the individual items
    do not carry.
  Never merge the branch itself: it would revert ~85k lines of `develop`.
- **R-5 Sequencing constraints survive retirement.** Two constraints from the program are real and
  must be carried onto the items before the program is retired, or they are lost:
  (a) WS1 Chunk 02 (#724) and #679 interact — refusing a stale-evidence verify pushes a suite run
  ahead of the round, and its cost falls with multi-slot evidence (now shipped; re-check whether the
  concern is moot); (b) all lane-A items (#724, #815, #731) edit `critic_consolidate.py` and the
  critic skill's exit table, so they should not run in parallel worktrees. Each is stated on the
  affected items, or ruled moot with a reason.
- **R-6 Stale owner decisions are re-asked, not inherited.** The program's nine Owner decisions
  are recorded as recommendations only. For each that still has an open item, its status
  (answered / still open) is recorded; decisions 1–2 (cut 3.5.1; merge `fix/coverage-honesty`) are
  moot and say so.

## Out of scope

- Building or re-planning any of the five plans or the open items in the table.
- Re-litigating #292 (closed) or #771/#816 (records as review subjects).
- Changing the issue's labels: the next stage is the owner's to set.

## Open questions for the owner

1. **Retire vs land.** The draft recommends retire (R-4): the remainder is ten ordinary backlog
   items, and the branch cannot merge. Confirm, or name the sequencing constraint that justifies a
   rewritten program.
2. **Where do archived artifacts go?** `.prawduct/artifacts/archive/` holds shipped build plans
   today; the program and triage are not build plans. Confirm that archive is the right home for
   them, or whether they should be deleted outright with the branch (the issue body would then be
   their only record).
3. **Baseline repos.** Which consumer clones should the re-measure run against (the program used
   seven; discodon alone was 96 of ~205 hours)?
