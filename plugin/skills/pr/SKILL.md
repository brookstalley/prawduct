---
description: PR lifecycle management — create, update, merge, or check status with independent reviewer
argument-hint: "[create|update|merge|status]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(gh pr *), Bash(gh repo view *), Bash(gh issue view *), Bash(git *), Bash(prawduct-hook test-status), Bash(prawduct-hook check-cumulative-critic), Bash(prawduct-hook cost-of-commit *), Bash(prawduct-hook check-operator-verification), Bash(prawduct-hook accept-operator-verification *), Bash(prawduct-hook verify-operator-verification *), Bash(prawduct-hook check-pr-doc-only), Bash(prawduct-hook check-change-log-entry), Bash(prawduct-hook resolve-base), Bash(prawduct-hook archive-plan *), Bash(prawduct-hook ledger-append *), Bash(python3 plugin/bin/prawduct-hook ledger-append *), Read, Write, Agent
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
Verify on a feature branch (not main/master/develop). Verify commits ahead of base. If uncommitted changes, offer to commit or stash.

**Sync the base BEFORE the review gates, not after.** Run `prawduct-hook resolve-base`, then `git merge-base <base> HEAD` — if that is not `<base>`'s tip, the base has moved. Merge (or rebase onto) it and resolve conflicts **now**, at Step 1: a sync landed after Step 2 or Step 3 moves the span those gates just answered about, which is how one branch paid for two of its three cumulative rounds. Sync first even though the gate can transfer coverage across a base advance — the transfer needs your diff byte-identical AND a suite run that has met the merged tree, so a conflict resolution (which edits your files) denies it outright and an unsynced suite run denies it until you re-run.

**Then the suite: run `prawduct-hook test-status` first** — if it exits 0 (`current`), the saved `.prawduct/.test-evidence.json` already covers the current tree (HEAD + uncommitted edits) and re-running is wasteful. Only run the suite if `test-status` reports `stale` or evidence is missing. When you do run, write fresh evidence so the next caller can skip it. Running it *after* the sync is what leaves the transfer available later.

### Step 1b: Doc-only fast-path
**Run `prawduct-hook check-pr-doc-only`.** This mirrors the stop hook's session-end behavior at the PR boundary: when every file in `merge-base...HEAD` ends in `.md` and none is governance-protected (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md` — skill prose is behavioral logic, not docs; same bound list as the `Type: trivial` gate), the cumulative-Critic and PR-reviewer gates add no value and are skipped.

- **Exit 0 (`doc-only`)**: the **review gates** are what a doc-only diff skips — Steps 2, 2b, 3, and 4 — and nothing else. **Continue through Steps 1c and 1d, then resume at Step 5 (Create PR).** Step 1c costs nothing here (a doc-only diff has no judgeable file, so the probe exits 0 by its own exemption) and running it keeps one path through this skill instead of two; Step 1d is load-bearing on any PR — a doc-only branch still archives the backlog items it closes and still carries its change-log release tag, and a protected base takes those only by PR. Note the skip in the PR description (e.g. "Doc-only PR — review gates skipped per check-pr-doc-only"). Tell the user which gates were skipped and why.
- **Exit 1 (anything else — `not-doc-only`, `empty-diff`, `no-base`, `git-failed`)**: Proceed to Step 2.

> There is no code-side "trivial" fast-path. A `Type: trivial` *chunk* is still
> enforced per-chunk at session-end (fileset bounds + rationale), but that
> declaration does **not** waive the cumulative-Critic or PR-reviewer gates at the
> PR boundary: fileset-eligibility (only touching existing files) is a necessary,
> not sufficient, signal of triviality, so a multi-chunk feature that only modifies
> existing files would otherwise have skipped both core review gates. Code PRs
> always go through the full review below.

### Step 1c: Change-log entry probe
**Run `prawduct-hook check-change-log-entry`.** A branch carrying **judgeable** work in `merge-base...HEAD` must ADD a change-log entry — a branch merged with no entry is invisible to the release flow and surfaces only at release reconstruction (REL-6C3W). Empty diffs and diffs with no judgeable file are exempt (exit 0).

> **Judgeable is the same predicate Step 1b uses** (`coverage_algebra.is_judgeable_path`), not "is it `.md`" — so `.prawduct/` session metadata is exempt even though it is not `.md`, and governance-protected prose (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md`) needs an entry even though it *is* `.md`. The two gates at this boundary once classified with different rules and returned opposite verdicts on the same file; they now ask one predicate, and the tests assert that they **agree** rather than pinning each verdict separately.

- **Exit 0**: proceed.
- **Exit 1 with `no-entry` or `entry-edited-not-added`**: **STOP** — write the change-log entry for this branch's work (tag line with `scope=` and no `release=` — that absence IS the release-pending state), commit it, then re-run the probe.
- **Exit 1 with `no-base` or `git-failed`**: the probe couldn't evaluate — check the change-log by hand and note the manual check in the PR description.

### Step 1d: The PR carries its own bookkeeping
**Nothing about this branch's work may require a post-merge commit on the integration branch.** Protected bases take commits only by PR, and a dedicated bookkeeping-only PR is ceremony, not governance — so every release tag, archive, and Status tick rides IN this branch, atomic with the merge (an abandoned PR then abandons its bookkeeping too — state can't drift). **That atomicity is a property of riding in a commit, so it holds only for bookkeeping that IS a commit** — the backlog bullet below is the one item that on some backends isn't, and it says what it does instead. Before the review gates, confirm:

- **Backlog — and this one splits by backend, so run `/prawduct:backlog` rather than assuming:** the call is the same either way, `/prawduct:backlog update <id> status=shipped closed-by=<scope>`, but *when* it runs is not.
  - **Markdown backend:** the archive is a file edit, so it rides the branch and is genuinely atomic with the merge. Make the call **now**, at this step.
  - **Issues backend** (`backlog_service_repo` is set): closing an issue is an **API call with no branch to ride**, so it is the single item deliberately deferred to the Merge Flow's **"Close the backlog items this PR resolves"** step, which fires seconds after the merge succeeds. This is not the "post-merge commit" the rule above forbids: no commit is involved, and the integration branch is never touched. Note in the PR description that the close is owed at merge, so an operator who inherits the PR knows it is outstanding. Do **not** rely on `Closes #N` in the PR body to do it for you: GitHub fires closing keywords only for PRs merged into the repository's **default** branch, so on a gitflow base the keyword is inert. Also expect `closed-by=<scope>` to land as a **comment** rather than a queryable field — the adapter's close op has no such argument.

  **The timing rule is not restated here — it is owned by `/prawduct:backlog`'s "When to mark shipped".** That is where the reason lives (the atomicity is a property of being a commit, so it holds for a file edit and not for an API call), and this bullet routes to it rather than re-deriving it, so the two cannot drift apart the way they already did once.
- **Change-log release tag:** run `prawduct-hook resolve-base`. When the base is an integration branch (`develop`), the Step 1c entry stays **untagged by `release=`** — that absence IS the release-pending state, and the `develop→main` release adds the tag. When the base is the **release surface** (trunk — `resolve-base` prints the `main` family), this merge ships the work: add `release=vX.Y.Z` to the entry when the product tracks versions. That tag is the whole release-time edit; nothing is regenerated from it. Get the value right — `check-releasability` reads the ABSENCE of `release=` to enumerate what is still pending, so any value at all (a placeholder like `release=unreleased` included) drops the entry's whole scope out of the pending set and unships the work silently.
- **Build-plan Status:** confirm every chunk whose review has already passed is ticked — nothing derives the boxes, and the briefing, the handoff and the Stop gates all believe them. **The LAST chunk's box is the exception and is NOT ticked here:** on a `cumulative-final` plan its review *is* Step 2 below, and ticking the last box disarms the Stop hook's Critic and reflection gates. Tick it after Step 2 passes. A checkbox lives under `.prawduct/`, which is non-judgeable, so it needs no new review coverage either way — the "land it before Step 2" rule below is about judgeable changes, not this one.
- **Build plan (trunk only):** if this PR completes the active plan, retire it on the branch — **archive it, never delete it**: `prawduct-hook archive-plan <path> --state completed --release vX.Y.Z` (resolve `<path>` via the plan declaring `branch: <this branch>` or, failing that, the `active_build_plan` pointer — never a hardcoded path), then clear the pointer if the pointer is what named it. A plan that declares `branch:` has no pointer to clear: archiving alone ends its claim. The command stamps the plan with its terminal state and moves it into `archive/`, where it stays findable by name and stops reading as live work. On gitflow, **RETAIN** the plan live and keep the pointer until the release — the work is not shipped yet, and the release checklist's *Archive the plans this release shipped* step is where that retention ends (`documentation/release-process.md`; it runs `prawduct-hook plan-backfill`, which archives every plan whose scope the release just tagged).

Land all of this **before** Step 2's cumulative review (the same sequencing rule that step already states: every **judgeable** change lands before the one cumulative run, so its fact spans the whole bundle).

### Step 2: Cumulative-Critic gate — MANDATORY
**Run `prawduct-hook check-cumulative-critic`.** This gate composes review coverage over the shared evidence store: review facts (any mode — labels don't matter) must span merge-base tree → HEAD tree with zero unresolved BLOCKING findings on the path. If it exits non-zero, **STOP** and follow the stderr remedy: `uncovered` → run `/prawduct:critic cumulative` (or `verify-resolutions` when a pre-commit review was followed by a selective commit — the delta review closes the gap); `blocking` → fix the named findings, then `/prawduct:critic verify-resolutions` records the resolution facts and the same evidence passes — **except** any the message marks `Superseded:`, which sit on a review round no verify pass anchors to again and clear only through a spanning `/prawduct:critic cumulative`. Re-check, and do NOT proceed to Step 3 until this gate passes.

**Sequencing (run the full review ONCE):** land every **judgeable** fix — code, evidence, pointers, configs, and governance-protected prose (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md`, which are judgeable despite being `.md`) — BEFORE the one cumulative run, then commit verbatim (the reviewed tree becomes the commit's tree, so the fact vouches for HEAD). For any fix AFTER the cumulative (its own findings included): **fix, then `/prawduct:critic verify-resolutions`** — its fact extends coverage over the delta at delta-review cost (1-2 min), and committing the verified state verbatim keeps HEAD covered. **You do not have to work out whether that pass is needed — asking is free.** When the delta holds no judgeable file and no finding the pass could resolve, dispatch refuses it in under a second (exit 3, "no review needed") instead of spending a reviewer, so a fix that landed only in `.prawduct/` state or non-governance prose costs nothing. Run it and read the exit code; do not skip it on your own judgement, and do not re-run it in another mode after a refusal. Never re-run a full cumulative for in-scope fixes; re-run it only when the verify pass itself refuses (widened delta, lost anchor). A rebase or amend rewrites the tree — coverage gaps there always need a fresh review.

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
- It carries a `commit_reviewed` SHA. If the reviewer omitted it, **do not fill it in from the current HEAD** — you cannot know a commit did not land mid-review. Dispatch again.
- `commit_reviewed` resolves in this repo and is an ancestor of (or equal to) HEAD — `git merge-base --is-ancestor <commit_reviewed> HEAD`. If it is not, the branch was rebased or amended out from under the review and the evidence is void. **Know what this check cannot see:** every commit on the branch is an ancestor of HEAD, so a `commit_reviewed` quietly advanced to a newer commit passes it exactly as the real SHA does. The check catches a rewritten tree, not a laundered field; the prohibition against advancing it is prose, and the cross-check below is what gives it teeth.
- There are no unresolved BLOCKING findings

If any check fails, STOP. Do not create the PR.

Then append the review to the governance ledger (role-vs-role telemetry needs both review roles): `prawduct-hook ledger-append --event review.pr --findings .prawduct/.pr-reviews/[computed-filename] --scope [the build-plan scope this PR ships] --model [the model Step 3 dispatched]`.

### Step 5: Create PR
Push branch with `-u`. Draft title and description from work context + review findings summary. Create via `gh pr create`. Update `pr_number` in the evidence file.

## Update Flow

1. Push new commits to remote
2. Re-run the reviewer **only on a substantive delta**. Substantive = the delta since the reviewed commit contains at least one **judgeable path authored on this branch**. **The reviewed commit is the evidence file's `commit_reviewed` field — read it, never infer it.** **Cross-check it against the ledger before trusting it:** Create Step 4 appended a `review.pr` event whose `review` payload is the evidence record verbatim, so the newest such event in `.prawduct/.governance-ledger.jsonl` carries an independent copy at `.review.commit_reviewed`. If the two disagree, the file was edited after the review — treat the delta as **substantive** and re-run, because the only edit that produces a mismatch is the one the protocol forbids. If the ledger copy is *absent* (an event appended before the field existed), you have no second witness: that is the absent-field case below, so re-run rather than trust the file alone. If the field is absent (evidence written by an older reviewer), the delta is **substantive by default**: `timestamp` plus `commits_reviewed` cannot distinguish "nothing landed since" from "a commit landed mid-review", and that is precisely the case the field exists to catch, so re-run rather than reconstruct. Two deltas are not substantive, and **neither is judged by eye** — a re-review of records and a base sync is minutes of opus for nothing to assess:
   - **Only non-judgeable paths.** Get the delta's paths with `git diff --name-only <commit_reviewed>..HEAD` and pass them to `prawduct-hook cost-of-commit` as **explicit file arguments**. Not substantive requires `paths` non-empty **and** `judgeable` empty. The empty-`judgeable` half alone is not the test: a bare or directory-only invocation prices the *working* tree, which by this step is clean, so it returns the same empty list having examined none of your delta — and skipping the reviewer on that reading is a governance bypass, not a saving. Empty `paths`, or a `reason` (git unreadable), is **substantive**; unknown is never free. `.prawduct/` records and non-governance-protected `.md` move no coverage; source and config classify by *path*, so a comment-only edit to a `.py` or a CI workflow **is** judgeable and does re-run the reviewer (content equivalence was built as an exception and reverted — `coverage_algebra.is_judgeable_path`).
   - **A base-sync merge that introduces no judgeable authored content** — it adds no work for a release-readiness reviewer to assess. Re-run `prawduct-hook check-cumulative-critic`, and if it exits 0 *by transfer* (the message says `transferred across base advance`), the gate has just proved the branch's own diff is byte-identical to the reviewed one, so there is nothing new for the reviewer to read.
3. Update PR description if scope changed
4. Update evidence file; if the reviewer re-ran, append a fresh `review.pr` ledger event (as in Create Step 4)

## Merge Flow

**Check `project-preferences.md` for `PR merge` setting.** If set to `wait_for_user` (default), present the PR URL and findings summary to the user and wait for them to say "merge" before proceeding. If set to `automatic`, merge after CI passes and review is clean.

1. Verify CI checks pass (`gh pr checks`)
2. Verify no merge conflicts
3. Verify PR review evidence exists for this branch — if missing, run the reviewer first
4. Merge using **merge-commit** strategy (`gh pr merge --merge`). Only two things select a different strategy: an explicit `PR merge strategy` setting in `project-preferences.md`, or the user asking in the moment. An absent preference means merge commit — a harness default, a GitHub UI default, or your own inclination is not a preference. If `gh pr merge --merge` fails because the repo's settings disallow merge commits, **STOP and surface it** (the user enables merge commits in repo settings, or deliberately sets the preference) — never silently retry with `--squash`. Merge-commit preserves each commit's identity, so after the merge the branch's commits stay reachable from the base and its merge-base stays correct; squash collapses them to one new SHA, stranding a reused worktree branch with a pre-squash merge-base that makes every "what's new" computation over-count already-merged work. When the configured strategy rewrites history (squash or rebase), the branch is single-use: delete it immediately after merge (the branch-deletion step is mandatory, not hygiene) and never reuse it.
5. **Close the backlog items this PR resolves** — on an Issues backend this is the deferred call from Step 1d, and it is numbered here, ahead of the deletions below, because those destroy the local artifacts that record the debt. `/prawduct:backlog update <id> status=shipped closed-by=<scope>` for each item (the adapter has no `closed-by` field, so the scope lands as a comment — expect that, don't re-run). **A `Closes #N` / `Fixes #N` / `Resolves #N` keyword in the PR body does not do it for you** — GitHub fires closing keywords only for PRs merged into the repository's **default** branch, so on gitflow (feature→`develop`, default `main`) the keyword is inert and the item silently stays open; check with `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` rather than assuming. Write the keyword anyway — it links the PR to the issue and does fire on a trunk repo whose base IS the default branch. Verify each close landed (`gh issue view <n> --json state`). On a markdown backend the archive already merged with the PR and there is nothing to do here.

   **Honest limit — this step is its own only detector.** If you merge through the GitHub UI, or the session ends at the merge, nothing downstream notices the close never fired: the branch and evidence file are gone and no local artifact records that it was owed. The reconciliation sweep that would catch it is prescribed but unbuilt — `documentation/backlog-service-requirements.md` **GV3** ("merged work whose item is still open… this is the price of leaving git; pay it explicitly"). Until it exists, this step running is the whole guarantee.
6. Delete remote branch, switch to base branch, pull, delete local branch
7. Clean up evidence file (gitignored, local — no commit involved). **Deletion is intended, not an
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
8. **Confirm the bookkeeping merged WITH the PR — there is nothing to commit here.** Create-flow Step 1d put the change-log `release=` tag, the Status ticks, (trunk) the plan retirement, and — on a markdown backend — the backlog archives in the branch, so the merge just landed them atomically. (The Issues-backend close is not bookkeeping that *rides* anywhere; it fired at step 5.) If something else was missed, fold it into the next PR that touches the repo — **never** push a bookkeeping commit to the integration branch and **never** open a housekeeping-only PR. On gitflow, release tags additionally self-converge at the release (it tags every unreleased entry regardless) and the backlog skill's reconcile step is a catch-net for unarchived items — a sweep somebody has to run, not convergence, which is why the close is a named step above rather than something left to it; on trunk there is no later release step, so the fold-into-the-next-PR rule IS the convergence — treat a missed `release=` tag as named debt for the next PR, not something that self-heals. Run `prawduct-hook resolve-base` to know which case applies:
   - **Base is `develop`** (gitflow, ahead of a batched `develop→main` release): the work is release-pending — its change-log entry carries **no `release=`** (older logs may also carry a legacy `status=` stamp; it is inert). **RETAIN** the plan live and keep the `active_build_plan` pointer: archiving is what the plan gets at the release, not at this merge. A non-blocking "archive the plan" advisory may surface in the briefing during this window — ignore it until the release ships. A plan that declares `branch:` needs no retention decision: its branch is merged and deleted, so it resolves for nobody and simply reads live-but-inactive until the release archives it. (Archiving early is not the deletion it used to be — `check-releasability` searches archived plans too — but it moves a plan that is still the live description of unshipped work, and the pointer would then name a moved file.)
   - **Base is the release surface** (the `main` family — `resolve-base` prints `main`, `origin/main`, or the `HEAD~1` fallback; i.e. a trunk repo, or any repo whose base is the deployed branch): this merge shipped the work, and the closing PR already carried the `release=`-tagged entry and archived the active build plan / cleared the `active_build_plan` pointer (Step 1d). If it didn't, treat it as missed bookkeeping per the rule above.

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
