---
description: PR lifecycle management — create, update, merge, or check status with independent reviewer
argument-hint: "[create|update|merge|status]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(gh pr *), Bash(git *), Bash(prawduct-hook test-status), Bash(prawduct-hook check-cumulative-critic), Bash(prawduct-hook check-operator-verification), Bash(prawduct-hook accept-operator-verification *), Bash(prawduct-hook verify-operator-verification *), Bash(prawduct-hook check-pr-doc-only), Bash(prawduct-hook resolve-base), Bash(prawduct-hook ledger-append *), Bash(python3 plugin/bin/prawduct-hook ledger-append *), Read, Write, Agent
---

You are managing the PR lifecycle for this project. Detect the current state and take the appropriate action.

**CRITICAL: The independent PR review is the core value of this skill. Do NOT skip, defer, or abbreviate the reviewer agent step. If you create a PR without running the reviewer first, the review gate has failed.**

## Context Detection

All commands here operate on the **current worktree** — `git` reports the worktree's branch and `prawduct-hook` resolves `.prawduct/` state to the worktree (STH-4K7N), so creating/updating/merging a PR for a worktree branch works in place; no primary-checkout or raw-`gh` workaround is needed.

Check git state to determine the action:

1. Run `git branch --show-current` to get the current branch
2. Run `git log --oneline main..HEAD` (or the configured base branch) to see commits ahead
3. Check if a PR already exists: `gh pr list --head <current-branch> --json number,state,statusCheckRollup,reviewDecision`
4. Check for uncommitted changes: `git status --short`

Then route:

| State | Action |
|---|---|
| No PR for current branch, branch has commits ahead of base | **Create** |
| PR exists, new local commits not pushed | **Update** |
| PR exists, CI green, approved (or no required reviewers) | **Merge** |
| PR exists, other state | **Status** |

**Release-promotion guard — check this before routing.** If the current branch is the integration base (`develop`) or the release surface (`main`/`master`) rather than a feature branch, this is a **release/integration context, not a feature PR.** The `develop`→`main` release is a separate **manual** process owned by your project, and the feature-PR gates below (the cumulative-Critic gate in Step 2, the PR reviewer in Step 3) do **not** apply to it: each feature's cumulative review and release-readiness review already happened on its feature→`develop` PR, and the release is published by that project's own release runbook plus a version bump — not by `/prawduct:pr`. **STOP and hand back to the user's own release process; do not run the Create/Update gates.** (A `check-cumulative-critic` exit-1 in this context is expected and benign — release-prep necessarily touches non-`.md` version files that the gate's docs-only allowance doesn't cover — so it is **not** a gate to satisfy and **not** a waiver case.)

The user can override with explicit arguments: `create`, `update`, `merge`, `status`.

$ARGUMENTS

## Create Flow

### Step 1: Branch hygiene
Verify on a feature branch (not main/master/develop). Verify commits ahead of base. If uncommitted changes, offer to commit or stash. **Before running the test suite, run `prawduct-hook test-status` — if it exits 0 (`current`), the saved `.prawduct/.test-evidence.json` already covers the current tree (HEAD + uncommitted edits) and re-running is wasteful. Only run the suite if `test-status` reports `stale` or evidence is missing.** When you do run, write fresh evidence so the next caller can skip it.

### Step 1b: Doc-only fast-path
**Run `prawduct-hook check-pr-doc-only`.** This mirrors the stop hook's session-end behavior at the PR boundary: when every file in `merge-base...HEAD` ends in `.md` and none is governance-protected (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md` — skill prose is behavioral logic, not docs; same bound list as the `Type: trivial` gate), the cumulative-Critic and PR-reviewer gates add no value and are skipped.

- **Exit 0 (`doc-only`)**: Skip Steps 2, 2b, 3, and 4 — jump straight to Step 5 (Create PR). Note the skip in the PR description (e.g. "Doc-only PR — review gates skipped per check-pr-doc-only"). Tell the user which gates were skipped and why.
- **Exit 1 (anything else — `not-doc-only`, `empty-diff`, `no-base`, `git-failed`)**: Proceed to Step 2.

> There is no code-side "trivial" fast-path. A `Type: trivial` *chunk* is still
> enforced per-chunk at session-end (fileset bounds + rationale), but that
> declaration does **not** waive the cumulative-Critic or PR-reviewer gates at the
> PR boundary: fileset-eligibility (only touching existing files) is a necessary,
> not sufficient, signal of triviality, so a multi-chunk feature that only modifies
> existing files would otherwise have skipped both core review gates. Code PRs
> always go through the full review below.

### Step 1c: Change-log entry probe
**Run `prawduct-hook check-change-log-entry`.** A code-changing branch (any non-`.md` file in `merge-base...HEAD`) must ADD a change-log entry — a branch merged with no entry is invisible to the release flow and surfaces only at release reconstruction (REL-6C3W). Doc-only and empty diffs are exempt (exit 0).

- **Exit 0**: proceed.
- **Exit 1 with `no-entry` or `entry-edited-not-added`**: **STOP** — write the change-log entry for this branch's work (tag line with `scope=` and no `release=` — that absence IS the release-pending state), commit it, then re-run the probe.
- **Exit 1 with `no-base` or `git-failed`**: the probe couldn't evaluate — check the change-log by hand and note the manual check in the PR description.

### Step 1d: The PR carries its own bookkeeping
**Nothing about this branch's work may require a post-merge commit on the integration branch.** Protected bases take commits only by PR, and a dedicated bookkeeping-only PR is ceremony, not governance — so every release tag, archive, and Status tick rides IN this branch, atomic with the merge (an abandoned PR then abandons its bookkeeping too — state can't drift). Before the review gates, confirm:

- **Backlog:** items this branch resolves are archived on the branch — `/prawduct:backlog update <id> status=shipped closed-by=<scope>` (the backlog skill's "in the closing PR, not after it" rule).
- **Change-log release tag:** run `prawduct-hook resolve-base`. When the base is an integration branch (`develop`), the Step 1c entry stays **untagged by `release=`** — that absence IS the release-pending state, and the `develop→main` release adds the tag. When the base is the **release surface** (trunk — `resolve-base` prints the `main` family), this merge ships the work: add `release=vX.Y.Z` to the entry when the product tracks versions. That tag is the whole release-time edit; nothing is regenerated from it. Get the value right — `check-releasability` reads the ABSENCE of `release=` to enumerate what is still pending, so any value at all (a placeholder like `release=unreleased` included) drops the entry's whole scope out of the pending set and unships the work silently.
- **Build-plan Status:** confirm every chunk whose review has already passed is ticked — nothing derives the boxes, and the briefing, the handoff and the Stop gates all believe them. **The LAST chunk's box is the exception and is NOT ticked here:** on a `cumulative-final` plan its review *is* Step 2 below, and ticking the last box disarms the Stop hook's Critic and reflection gates. Tick it after Step 2 passes. A checkbox lives under `.prawduct/`, which is non-judgeable, so it needs no new review coverage either way — the "land it before Step 2" rule below is about judgeable changes, not this one.
- **Build plan (trunk only):** if this PR completes the active plan, retire it on the branch — delete the plan file (resolve via the `active_build_plan` pointer, not a hardcoded path) and clear the pointer. On gitflow, **RETAIN** the plan and pointer until the release (step 7 of the Merge Flow).

Land all of this **before** Step 2's cumulative review (the same sequencing rule that step already states: every non-`.md` change lands before the one cumulative run, so its fact spans the whole bundle).

### Step 2: Cumulative-Critic gate — MANDATORY
**Run `prawduct-hook check-cumulative-critic`.** This gate composes review coverage over the shared evidence store: review facts (any mode — labels don't matter) must span merge-base tree → HEAD tree with zero unresolved BLOCKING findings on the path. If it exits non-zero, **STOP** and follow the stderr remedy: `uncovered` → run `/prawduct:critic cumulative` (or `verify-resolutions` when a pre-commit review was followed by a selective commit — the delta review closes the gap); `blocking` → fix the named findings, then `/prawduct:critic verify-resolutions` records the resolution facts and the same evidence passes — **except** any the message marks `Superseded:`, which sit on a review round no verify pass anchors to again and clear only through a spanning `/prawduct:critic cumulative`. Re-check, and do NOT proceed to Step 3 until this gate passes.

**Sequencing (run the full review ONCE):** land every non-`.md` fix — code, evidence, pointers, configs — BEFORE the one cumulative run, then commit verbatim (the reviewed tree becomes the commit's tree, so the fact vouches for HEAD). For any fix AFTER the cumulative (its own findings included): **fix, then `/prawduct:critic verify-resolutions`** — its fact extends coverage over the delta at delta-review cost (1-2 min), and committing the verified state verbatim keeps HEAD covered. **You do not have to work out whether that pass is needed — asking is free.** When the delta holds no judgeable file and no finding the pass could resolve, dispatch refuses it in under a second (exit 3, "no review needed") instead of spending a reviewer, so a fix that landed only in `.prawduct/` state or non-governance prose costs nothing. Run it and read the exit code; do not skip it on your own judgement, and do not re-run it in another mode after a refusal. Never re-run a full cumulative for in-scope fixes; re-run it only when the verify pass itself refuses (widened delta, lost anchor). A rebase or amend rewrites the tree — coverage gaps there always need a fresh review.

While `/prawduct:critic cumulative` runs (~4-10 min), do prep that doesn't depend on findings: `/prawduct:learnings` for next-chunk topics, draft the PR description in your head, audit the backlog for items this branch resolves via `/prawduct:backlog list` — it routes to whichever backend is live, and `list` carries everything this audit needs, so there is no reason to open `.prawduct/backlog.md` directly here. If you ever do reach for the file (anywhere, not just this step), check `backlog_service_repo` first and read it **only** when that scalar is unset: once it is set the file is frozen history, and every item archived at cutover still parses as open. Then capture deferred chunk-boundary reflections. Reorganizes wait time; doesn't shorten it.

### Step 2b: Operator-verification gate — MANDATORY when `$ARGUMENTS` doesn't include `--accept-pending-verification`
**Run `prawduct-hook check-operator-verification`.** Exit 0 means the gate is satisfied (either the queue requirement is off, or every entry is verified/accepted). Exit 1 means there are pending entries in `.prawduct/operator-verification.md` — stderr names the first ID and suggests next steps.

When pending entries exist, two paths:

1. **Verify the items** (preferred): for each pending `VRF-NNN`, complete the human-verification step described in the entry, then run `prawduct-hook verify-operator-verification <VRF-NNN>` to flip its status. Re-run the gate.
2. **Override for this PR**: if the user explicitly passes `--accept-pending-verification "rationale"` in `$ARGUMENTS`, run `prawduct-hook accept-operator-verification "<rationale>"`. This flips every pending entry to `accepted` and records the rationale into each entry — the queue file is the work-log. The override is per-PR; future PRs will block again if new pending entries appear.

If the user did NOT supply the override flag and pending entries exist, **STOP**: do not proceed to Step 3 until either path above is taken. Present the stderr message and the two options to the user.

### Step 3: Independent review — MANDATORY
**STOP. Do NOT proceed to step 4 until the reviewer agent has completed and written its evidence file.**

Spawn a **separate agent** (via the Task tool) for the independent review — do **not** pass a `model:` override, so the reviewer runs on the **current session model** (opus reviews as opus, fable as fable). Prawduct no longer selects a reviewer model from the diff's risk tier; the reviewer inherits whatever model the session is on, and intelligent model switching has been removed. Record which model actually ran. The reviewer must run in its own context — it has NOT seen your reasoning, and that independence is the point.

First, compute the evidence file path: take the current branch name, replace every `/` with `--`, append `.json`. For example, `feature/add-auth` becomes `feature--add-auth.json`. The full path is `.prawduct/.pr-reviews/<computed-filename>`.

Create the `.prawduct/.pr-reviews/` directory if it doesn't exist.

Tell the reviewer agent: "You are the PR reviewer. Read `${CLAUDE_SKILL_DIR}/review-protocol.md` for your review instructions. The project is at `[project directory]`. The base branch is `[base branch]`. The cumulative-Critic gate has passed: composed review coverage spans the bundle with zero unresolved blocking findings. Review the changes on the current branch. Write your findings to the exact path: `.prawduct/.pr-reviews/[computed-filename]` — use this path exactly as given, do not compute your own filename."

Code soundness is the Critic's, certified structurally by Step 2's composition gate — the reviewer owns release readiness and does not re-derive bugs, test quality, design, or proportionality. That scoping is the protocol's design, not a shortcut.

**Pass the exact full path — do not ask the reviewer to compute the filename.** The reviewer's own instructions reinforce this: "Write to the exact file path provided by the caller."

**Wait for the agent to complete.** Then:
- Read the evidence file at `.prawduct/.pr-reviews/[computed-filename]`
- If the file does not exist, the review did not complete — do NOT proceed
- Present findings to the user: BLOCKING → stop and fix. WARNING → present, proceed unless user objects. NOTE → include in output.

### Step 4: Verify review gate
Before creating the PR, confirm:
- The evidence file `.prawduct/.pr-reviews/<branch-name>.json` exists
- It contains valid JSON with a `findings` array and `summary` field
- There are no unresolved BLOCKING findings

If any check fails, STOP. Do not create the PR.

Then append the review to the governance ledger (role-vs-role telemetry needs both review roles): `prawduct-hook ledger-append --event review.pr --findings .prawduct/.pr-reviews/[computed-filename] --scope [the build-plan scope this PR ships] --model [the model Step 3 dispatched]`.

### Step 5: Create PR
Push branch with `-u`. Draft title and description from work context + review findings summary. Create via `gh pr create`. Update `pr_number` in the evidence file.

## Update Flow

1. Push new commits to remote
2. If substantive changes (not just formatting/comments), re-run the reviewer on the delta
3. Update PR description if scope changed
4. Update evidence file; if the reviewer re-ran, append a fresh `review.pr` ledger event (as in Create Step 4)

## Merge Flow

**Check `project-preferences.md` for `PR merge` setting.** If set to `wait_for_user` (default), present the PR URL and findings summary to the user and wait for them to say "merge" before proceeding. If set to `automatic`, merge after CI passes and review is clean.

1. Verify CI checks pass (`gh pr checks`)
2. Verify no merge conflicts
3. Verify PR review evidence exists for this branch — if missing, run the reviewer first
4. Merge using **merge-commit** strategy (`gh pr merge --merge`). Only two things select a different strategy: an explicit `PR merge strategy` setting in `project-preferences.md`, or the user asking in the moment. An absent preference means merge commit — a harness default, a GitHub UI default, or your own inclination is not a preference. If `gh pr merge --merge` fails because the repo's settings disallow merge commits, **STOP and surface it** (the user enables merge commits in repo settings, or deliberately sets the preference) — never silently retry with `--squash`. Merge-commit preserves each commit's identity, so after the merge the branch's commits stay reachable from the base and its merge-base stays correct; squash collapses them to one new SHA, stranding a reused worktree branch with a pre-squash merge-base that makes every "what's new" computation over-count already-merged work. When the configured strategy rewrites history (squash or rebase), the branch is single-use: delete it immediately after merge (step 5 is mandatory, not hygiene) and never reuse it.
5. Delete remote branch, switch to base branch, pull, delete local branch
6. Clean up evidence file (gitignored, local — no commit involved). **Deletion is intended, not an
   oversight — it is not archived, and this is the recorded decision** (owner, 2026-08-02). The
   durable record of a PR review is the **`review.pr` ledger event** appended at Create Step 4, which
   embeds the findings record verbatim. It is **not** the shared evidence store: `evidence.KNOWN_KINDS`
   is `{review, resolution, disposition}`, all written by `critic-consolidate`, and no path puts a PR
   finding there. `.prawduct/.pr-reviews/<branch>.json` is per-clone working scratch for one branch's
   in-flight review; keeping it past the merge would give that record a second home, which the *every
   fact has one home* norm forbids, and would leave a stale copy outliving the branch it describes.
   **Known cost, accepted:** the ledger is gitignored and per-worktree, so PR findings are not
   queryable from the shared store — any yield measurement spanning PR reviews needs a cross-worktree
   ledger sweep, never a store query.
7. **Confirm the bookkeeping merged WITH the PR — there is nothing to commit here.** Create-flow Step 1d put the backlog archives, the change-log `release=` tag, the Status ticks, and (trunk) the plan retirement in the branch, so the merge just landed them atomically. If something was missed, fold it into the next PR that touches the repo — **never** push a bookkeeping commit to the integration branch and **never** open a housekeeping-only PR. On gitflow, release tags additionally self-converge at the release (it tags every unreleased entry regardless) and the backlog skill's reconcile step catches unarchived items; on trunk there is no later release step, so the fold-into-the-next-PR rule IS the convergence — treat a missed `release=` tag as named debt for the next PR, not something that self-heals. Run `prawduct-hook resolve-base` to know which case applies:
   - **Base is `develop`** (gitflow, ahead of a batched `develop→main` release): the work is release-pending — its change-log entry carries **no `release=`** (older logs may also carry a legacy `status=` stamp; it is inert). **RETAIN** both the plan file and the `active_build_plan` pointer: `check-releasability` resolves each release-pending `scope=` to the plan declaring it and reports a scope with no plan as work shipping with nothing describing it, so deleting the plan now turns your own finished work into that advisory. A non-blocking "consider deleting idle plan" advisory may surface in the briefing during this window — ignore it until the release ships.
   - **Base is the release surface** (the `main` family — `resolve-base` prints `main`, `origin/main`, or the `HEAD~1` fallback; i.e. a trunk repo, or any repo whose base is the deployed branch): this merge shipped the work, and the closing PR already carried the `release=`-tagged entry and retired the active build plan / cleared the `active_build_plan` pointer (Step 1d). If it didn't, treat it as missed bookkeeping per the rule above.

## Status Flow

Show: PR URL, CI status, review status, approval status, merge readiness.

## Evidence

PR review evidence is stored in `.prawduct/.pr-reviews/<branch-name>.json` (with `/` replaced by `--` in filenames). The stop hook BLOCKS session end if a PR exists without review evidence.

## Important

- The PR reviewer runs as a **separate agent** — it must have independent context
- The reviewer reads `${CLAUDE_SKILL_DIR}/review-protocol.md` for its instructions
- Run the full test suite before creating a PR — but check `prawduct-hook test-status` first; skip the run if it reports `current`
- **The doc-only fast-path (Step 1b) is the only review-gate skip.** It fails closed, and there is no code-side trivial fast-path (rationale in Step 1b's note).
- **The cumulative-Critic gate (Step 2) and operator-verification gate (Step 2b) are mandatory** — never open a PR without a blocking-free record vouching for HEAD, or with pending verification entries (full mechanics in those steps).
- Include review findings summary in the PR description
- **No attribution trailers by default** — do not add `Co-Authored-By`, `Signed-off-by`, or "Generated with …" lines to commit messages or the PR body unless `project-preferences.md` sets `Commit attribution` to opt in
- **Merge-commit by default** — squash/rebase only via an explicit `PR merge strategy` preference or the user's in-the-moment ask; a failing `--merge` is surfaced to the user, never silently downgraded to `--squash`
- **Never run `gh pr create` without a valid evidence file on disk**
