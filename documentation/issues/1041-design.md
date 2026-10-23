# Issue #1041 — git hygiene: Design

`status: draft · stage: design · area: governance · added: 2026-10-22 · issue:
https://github.com/brookstalley/prawduct/issues/1041`

Requirements: `documentation/issues/1041-requirements.md` (R1–R10, owner-confirmed 2026-10-22).
Build plan: `.prawduct/artifacts/build-plan-git-hygiene.md`.

## Research (verified 2026-10-22, not recalled)

- **`gh pr merge --delete-branch` is unusable for R4.** Source of gh v2.86.0, the installed
  version:
  - `git/client.go` `DeleteLocalBranch` runs `git branch -D`. That discards the `-d` refusal R2
    keeps as the unpushed-commit signal.
  - `pkg/cmd/pr/merge/merge.go` `deleteLocalBranch` runs `git checkout <base>` when the head
    branch is checked out, with no worktree handling. In a linked worktree whose base is held by
    the main clone it returns an error after the merge has already happened.
  - gh's development branch has added worktree handling, but the installed gh doesn't have it, and
    neither does whatever gh an onboarded product's machine runs. R4 performs the steps itself and
    uses `gh` only for PR queries and edits.
- **Harness worktrees** (Claude Code docs: worktrees, hooks, tools-reference; via the
  claude-code-guide agent):
  - The harness holds a `git worktree lock` while an agent runs and releases it when the agent
    finishes. A locked worktree is therefore always skipped (R8), and that is the whole race
    guard.
  - The harness removes a subagent worktree automatically when it has no changes. It does not
    document deleting the branch. Measured here: `worktree-agent-ab9b5942445524ace` survives with
    no worktree.
  - The periodic sweep removes harness-created worktrees after `cleanupPeriodDays` (default 30)
    and keeps any with work.
  - `ExitWorktree remove` deletes the worktree and its branch, and it requires `discard_changes`
    when there is unmerged work.
  - No hook reports a worktree's branch, and nothing announces a lock. The classifier must read
    lock state itself every time.
- **Ownership needs no record.** The only places ownership changes behaviour are the merge flow
  (its own head branch and worktree) and reaping (the delegate it just reaped). In both, the
  caller names the object explicitly. So "owned" is defined as *targeted by the caller*: the
  7-day idle wait is waived, and every proof still applies. Everything the sweep finds by itself
  is a sibling. This avoids a new persisted format and never reads a sibling's files.

## Decisions

1. **One module, `plugin/lib/git_hygiene.py`, owns classification and action.**
   - The "held" computation moves out of `stranded_work.stranded_branches` into
     `gitstate.held_branches(records)`, which both modules read (R1: one classifier).
   - Integration is computed in one call per long-lived ref: `git for-each-ref --merged=<ref>
     refs/heads refs/remotes/<remote>`. `--apply`'s re-proof and `--reap` use
     `merge-base --is-ancestor` against the proving ref.
   - The classifier reads git directly. Tests drive it against real repositories built per
     test, with a fake `gh` on `PATH` for the network legs. (Amended in build: the design first
     said the classifier would be pure over a git snapshot, and the real-repo fixtures made that
     indirection unnecessary.)
2. **The long-lived set** is the union of:
   - `origin/HEAD`'s target;
   - the resolved base (`coverage._resolve_base_branch`, the resolver `resolve-base` already uses);
   - `main`, `master`, `develop` and `trunk`;
   - `release/*`;
   - the names listed in a `project-preferences.md` row `Long-lived branches`.

   That last row is a separate row because `read_preference_row` cuts a value at the first `(`, so
   a list can't share the `Branch cleanup` row. R9 said "may", and this is how. Without the row,
   an environment branch kept equal to `main`, such as `staging`, would read as integrated. The
   dry run and the owner's yes protect it, but the row is the durable answer, and the dry run says
   so when such a branch appears.
3. **Every local delete is compare-and-delete, never `-D`, and squash/rebase merges get a PR proof.**
   (Amended in build: `git branch -d` checks merge into HEAD, not into the proving branch, so it
   is not used at all; see the plan's Chunk 03 decision.)
   - For a branch with no ancestry proof, the network leg asks
     `gh pr list --state merged --head <b> --json number,headRefOid`.
   - On a match with the local tip, it deletes with `git update-ref -d refs/heads/<b> <sha>`, then
     `git config --remove-section branch.<b>`.
   - `update-ref` with an old value deletes only if the ref still names the proven commit, so a
     commit added after the check makes it fail. That keeps R2's purpose (nothing unproven is
     dropped) without git's `-D` override.
   - The check is capped at 8 branches per run, oldest first. The overflow is reported (the #843
     design's cap and posture).
4. **`prawduct-hook git-tidy`** (new subcommand; additive under the api-contract norm):
   - With no flags it is a dry run: online, it first refreshes remote-tracking refs with `git
     fetch --prune`, and it changes no branch, worktree or remote. Each action prints its kind,
     object, proof and exact command,
     and the run ends with a fingerprint: 12 hex characters of SHA-256 over the sorted
     `(kind, object, sha)` list.
   - `--apply <fp>` recomputes the set, refuses on a mismatch (printing the new dry run), and then
     runs each action after re-checking its proof. Failures are per action; the exit code is 1 if
     any action failed.
   - `--offline` skips the network legs and marks what they would have decided as `unchecked`.
     The network legs are `fetch --prune`, the open-PR check on remote candidates, and squash
     proof.
   - `--json` gives the machine envelope.
   - Exit codes: 0 when the run completes (nothing to do counts), 1 when actions failed or the
     fingerprint is stale, 3 when git could not be read. The dry run says "nothing to tidy" only
     when every leg was checked (R10).
5. **`git-tidy --after-merge <branch> [--pr <n>]`** is step 7 of the PR merge flow (R4). Steps in
   order:
   1. retarget each open PR whose base is `<branch>` to the merged PR's base (`gh pr edit --base`);
   2. delete the remote branch with `git push <remote> --delete`, unless it is long-lived, the PR
      is cross-repository, or the branch is already gone (GitHub auto-delete);
   3. `git fetch <remote> <base>`;
   4. if this worktree is on `<branch>`: switch to `<base>` and fast-forward when no other
      worktree holds `<base>`, otherwise `git switch --detach <remote>/<base>`;
   5. decision 3's compare-and-delete, once the merged PR's head is confirmed equal to the local
      tip. A local tip ahead of the merged head is the unpushed-commit signal, and the branch is
      kept.

   With `Branch cleanup: off` it keeps the branches, except when the configured `PR merge
   strategy` is squash or rebase, where the single-use rule makes deletion mandatory. The merge
   the owner approved is the operation-level approval (security-model norm).
6. **`git-tidy --reap <worktree>`** (R5): the caller names the delegate worktree. The command
   removes it without `--force` once it is clean, unlocked and integrated, then deletes its
   branch. No idle wait applies.
7. **Advisory `git-hygiene:tidy-available`** (R6), in a new `plugin/lib/git_hygiene_probes.py`:
   - It runs `git_hygiene.plan(offline=True)`.
   - Sibling worktrees' cleanliness and idleness come from `stranded_work.scan`, whose budgeted,
     `GIT_OPTIONAL_LOCKS=0` scan already computes both. This adds no second worktree walk.
   - Evidence is the sorted candidate lines, so the id is stable for an unchanged set.
   - It is silent under `Branch cleanup: off`.
   - Its text names no prawduct-internal identifier (observability norm). It never names a
     worktree that is dirty, locked, unintegrated or active within 7 days, which keeps #410's
     ruling: it proposes removing something with nothing to lose, never work to pick up.
8. **Egress.** git-tidy's network calls go to the product's own remote and carry none of the
   product's content. They are egress *sites*, not a new *surface* (architecture § Local-first,
   clarified 2026-09-07). They are added to the site lists in `security-model.md` and
   `project-state.yaml` `egress_boundary`, and reached only when a person or the agent runs the
   command. The advisory makes no network call, and a test asserts that by running the probe with
   `PATH` stripped of `gh` and a remote that would fail on contact.

## What changes, by surface

| Surface | Change |
|---|---|
| `plugin/lib/git_hygiene.py` (new) | classifier, plan, fingerprint, apply, after-merge, reap |
| `plugin/lib/gitstate.py` | `held_branches` (moved from `stranded_work`) |
| `plugin/lib/stranded_work.py` | reads `held_branches` |
| `plugin/lib/git_hygiene_probes.py` (new), `probe_families.py` | the advisory |
| `plugin/bin/prawduct-hook` | `git-tidy` dispatch and help |
| `plugin/skills/pr/SKILL.md` step 7 | one `git-tidy --after-merge` call |
| `plugin/methodology/delegation.md` "Reaping ends with the worktree" | `git-tidy --reap` |
| `plugin/methodology/session-digest.md` | unchanged: the advisory and step 7 carry the default, and the digest's reserve is for defaults nothing else carries |
| `plugin/skills/janitor/themes.md` Version Control Hygiene | routes to `git-tidy` |
| `plugin/templates/project-preferences.md` | `Branch cleanup`, `Long-lived branches` rows |
| `.prawduct/artifacts/security-model.md`, `.prawduct/project-state.yaml` | egress sites |
