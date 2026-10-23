# Issue #1041 — git hygiene: prawduct deletes merged branches and dead worktrees on proof of integration: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-10-22 · source: owner
session · issue: https://github.com/brookstalley/prawduct/issues/1041`

Related: #843 (the landing side: a finished branch that never merged; its pushed-branch arm will
read the classifier R1 defines, and is not built here). The `branch-landing:stranded-branch`
advisory (`plugin/lib/stranded_branch_probes.py`) and `delegation:unintegrated-delegate-worktree`
(`plugin/lib/adhoc_delegate_probes.py`) stay as they are: they ask about work that is NOT carried
elsewhere, and this item never deletes that.

## Problem

Prawduct detects untidy git state and cleans none of it up. The one deletion it performs is
`/prawduct:pr` merge step 7, a single line of prose: "Delete remote branch, switch to base branch,
pull, delete local branch". That line fails in a linked worktree, because the base branch is
already checked out in the main clone. Delegate reaping (`delegation.md`, "Reaping ends with the
worktree") removes the worktree but says nothing about its `worktree-agent-<id>` branch. Nothing
prunes worktree entries whose directory is gone, tracking refs for deleted remote branches, or
remote branches merged outside the PR flow.

Measured on this clone, 2026-10-22: five local branches already reachable from `origin/develop` or
`origin/main` (`pr-944`, `fix/backlog-triage-intake`, `feature/870-version-bump-free-edge`, two
`worktree-agent-*`); one worktree entry whose directory is gone; seven remote `claude/*` branches
merged into develop; one stale remote-tracking ref. GitHub's delete-head-branch-on-merge setting is
off for this repo.

## The protocol (owner-confirmed 2026-10-22)

1. **Proof, never inference.** Prawduct deletes a ref or worktree only when what it holds is
   provably carried by something that stays. Age, inactivity and "looks abandoned" are never proof.
   This is the line the 11,000-line loss in `.claude/rules/learnings/backlog.md` crossed.
2. **Ownership.** A session cleans what it created and *proposes* what others created. Liveness is
   inferred from timestamps, so a paused session looks idle, and removing its directory breaks it
   (core learning: another session's worktree is its territory).
3. **Four moments:** the merge flow, delegate reaping, a session-start advisory, and an on-demand
   command.
4. **Owner rulings on the three forks:** the session-start sweep *proposes* and the agent applies on
   the owner's single yes per sweep; the sweep includes merged remote branches, on that same yes;
   a sibling worktree that is clean, integrated and idle for 7 days is proposed by name, never
   removed automatically.

## Grounding facts

Checked against `develop` at `0b0ddffc`.

- `gitstate.worktree_records` is the one `git worktree list --porcelain` parser, shared by
  `stranded_work`, `adhoc_delegate_probes` and the briefing. It returns `None` on a git failure.
- `stranded_work.stranded_branches` already computes "held" (checked out in a worktree whose
  directory exists) and "carried by a remote", from one `rev-list --branches --not --remotes`
  walk. It does not compute "integrated into a long-lived branch", which is the property deletion
  needs. Being pushed is not proof: a pushed, unmerged branch is not integrated.
- `stranded_work.IDLE_AFTER_SECONDS` is 7 days, the owner's sibling-worktree threshold.
- Advisory ids hash the full evidence list (`advisory_store.compute_id`), so an advisory whose
  evidence is the sorted candidate list keeps its id until the set changes. A dismissal then holds
  until a new candidate appears.
- Advisory probes are local-only by invariant ("cheap read-only scans only … probes run on every
  sync", `advisory_store.py`). `project-state.yaml` `egress_boundary` lists three network egress
  sites; a command that runs `git fetch`, `git push --delete` or `gh` from `plugin/lib` is a new one
  unless it reuses an existing site.
- `gitstate.ephemeral_kind_of` recognises harness agent worktrees (`.claude/worktrees/agent-*` on
  `worktree-agent-<hex>`). The harness locks such a worktree while its agent runs.
- `project-state.yaml` `base_branch` is optional; `prawduct-hook resolve-base` resolves the base
  (`origin/develop` here). The default branch is `origin/HEAD` (`main` here).

## Definitions

- **Long-lived branch:** the remote's default branch, the resolved base, `main`, `master`,
  `develop` and `trunk` where they exist, `release/*`, and any names the preference in R9 adds.
  *Inferred:* `release/*` is long-lived and `hotfix/*` is not.
- **Integrated:** the branch tip (or a detached worktree's HEAD) is an ancestor of a long-lived
  branch's local or remote-tracking ref. On a repo whose merge strategy is squash or rebase, a
  merged PR whose recorded head SHA equals the local tip is also proof. That proof needs the
  network, so only the on-demand command (R7) can use it.
- **Held:** checked out in a worktree whose directory exists (the `stranded_work` definition).
- **Owned by this session:** a worktree the session recorded creating: its launch worktree, or a
  delegate worktree it dispatched. Anything else is a **sibling**. How the session records this is
  a design question; it must not read a sibling's files to decide (`adhoc_delegate_probes`: "stats,
  never reads").

## Requirements

1. **One classifier.** A single function classifies every local branch as long-lived, held,
   integrated, or unintegrated, and every worktree as current, locked, missing, dirty, integrated,
   or unintegrated, with an owned/sibling flag. The stranded-branch scan and #843's later arm read
   it; nothing else computes integration on its own.
2. **Delete only what is integrated, with git's own safety.** Local branches go with `git branch
   -d` and worktrees with `git worktree remove` without `--force`. A refusal is reported with the
   branch kept, never escalated to `-D` or `--force`. A `-d` refusal after a merge is the
   unpushed-commit signal (`.claude/rules/learnings/pr.md`), and it must stay visible.
3. **Remote branches.** A remote branch is a candidate only if it is on the repo's own remote (not
   a fork), not long-lived, and integrated, and no open PR uses it as its head or base. Deleting a
   stacked PR's base closes the child PR on GitHub, so the merge flow retargets such PRs first
   (R4), and the sweep skips the branch.
4. **Merge-flow cleanup is one command, not prose.** `/prawduct:pr` merge step 7 becomes a single
   `prawduct-hook` call. It works in the main worktree and in a linked one, and it:
   1. retargets open PRs whose base is the merged branch;
   2. deletes the remote branch;
   3. leaves the session on the updated base, switching to it where possible and detaching at
      `origin/<base>` where the base is held by another worktree;
   4. deletes the local branch with `-d`.

   A long-lived head branch is never deleted. On a squash or rebase repo the deletion remains
   mandatory (the single-use rule), even when R9 turns cleanup off.
5. **Delegate reaping deletes the branch too.** Reaping an integrated delegate removes its worktree
   and its `worktree-agent-<id>` branch through the same command. `delegation.md` says so.
6. **Session-start advisory.** One advisory, `git-hygiene:tidy-available`, fires when the
   classifier finds candidates: integrated local branches that are not held; worktree entries whose
   directory is gone; integrated remote branches, read from local remote-tracking refs; and sibling
   worktrees that are clean, integrated and idle for 7 days or more, listed by name. It makes no
   network call. Its evidence is the sorted candidate list, so a dismissal holds until the set
   changes. Its recommended action is the R7 dry run. The agent shows the owner what would be
   removed and applies it on a yes. It does not raise the advisory as a question mid-chunk;
   cleanup waits for a work boundary.
7. **On-demand command.** `prawduct-hook git-tidy` lists every action with its object, its proof
   and the exact git command, and changes nothing by default. `--apply` executes the set the dry
   run printed: the dry run emits a fingerprint, and `--apply <fingerprint>` refuses when the set
   has changed. Each action re-checks its proof just before it runs, and one failure does not stop
   the others. Network steps (`fetch --prune`, the open-PR check, squash-merge proof, remote
   deletes) run only here and in R4. They are declared in `egress_boundary`, reached only when a
   person acts. The janitor's version-control theme routes to this command.
8. **Never deleted:** long-lived branches; held branches; unintegrated branches of any age; the
   current or main worktree; locked worktrees; worktrees with tracked changes or untracked
   non-ignored files; branches on forks. Prawduct never changes repository settings on GitHub.
9. **Policy belongs to the product.** *Inferred, owner may veto:* a `project-preferences.md` row
   `Branch cleanup`, either `propose` (the default) or `off`. `off` silences the R6 advisory and
   makes R4 keep the branch, except where the single-use rule in R4 applies. The same row may
   name extra long-lived branches.
10. **Fail visibly.** A probe that cannot read git reports what it could not check. "Nothing to
    tidy" is said only when everything was checked (#917 posture).

## Acceptance

- [ ] On a fixture reproducing this clone's state, the dry run lists exactly the five local
      branches, the missing worktree entry and the seven remote branches, and nothing else. A
      held branch, a locked agent worktree on an unintegrated branch, and an unintegrated pushed
      branch are all absent.
- [ ] Red-verified: replacing the integration proof with an age check makes a test fail. A
      branch with one commit beyond its merged tip is kept, and `-d`'s refusal is reported.
- [ ] Merge-flow cleanup run from a linked worktree whose base is held by the main clone ends
      detached at the updated base, with the local and remote branch gone.
- [ ] A stacked PR's base is retargeted before the remote delete (fake `gh`), and the sweep skips
      a branch that is an open PR's base.
- [ ] `--apply` with a stale fingerprint changes nothing and says why.
- [ ] A dirty or locked worktree is never removed, and a sibling is listed only after 7 idle days.
- [ ] The advisory makes no network call (asserted, not assumed), and its id is stable for an
      unchanged candidate set.
- [ ] `egress_boundary`, `delegation.md`, the PR skill's step 7, the janitor theme and the
      digest's single-use sentence all describe the shipped mechanism; no sentence still says
      step 7 "switch[es] to base branch" unconditionally.

## Research for design (volatile; verify, don't recall)

- How `gh pr merge --delete-branch` (gh 2.86) behaves in a linked worktree, and whether R4 should
  use it or do the steps itself.
- The harness's worktree lifecycle: which worktrees and branches `isolation: "worktree"` and
  `EnterWorktree`/`ExitWorktree` already remove, and when they release the lock. R5 must not race
  the harness.
- How a session records that it owns a worktree without reading a sibling's files.

## Scope-out

- #843's pushed-but-never-PR'd arm, and any deletion of unintegrated work.
- Rewriting history, and archiving branches as tags.
- Changing GitHub repository settings such as delete-head-branch-on-merge. The dry run may
  mention it.
- Cleaning up other clones of the same repo.
