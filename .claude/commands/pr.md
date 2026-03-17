You are managing the PR lifecycle for this project. Detect the current state and take the appropriate action.

## Context Detection

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

The user can override with explicit arguments: `create`, `update`, `merge`, `status`.

$ARGUMENTS

## Create Flow

1. **Branch hygiene**: Verify on a feature branch (not main/master/develop). Verify commits ahead of base. If uncommitted changes, offer to commit or stash. Run the test suite.
2. **Spawn PR reviewer agent**: Use the Task tool to spawn a separate agent. Tell it: "You are the PR reviewer. Read `agents/pr-reviewer/SKILL.md` for your review instructions. The project is at `$CLAUDE_PROJECT_DIR`. The base branch is `main`. Review the changes on the current branch."
3. **Handle findings**: BLOCKING → present and stop. WARNING → present, proceed unless user objects. NOTE → include in output.
4. **Create PR**: Push branch with `-u`. Draft title and description from work context + review findings. Create via `gh pr create`. Update evidence file with PR number.

## Update Flow

1. Push new commits to remote
2. If substantive changes (not just formatting/comments), re-run the reviewer on the delta
3. Update PR description if scope changed
4. Update evidence file

## Merge Flow

1. Verify CI checks pass (`gh pr checks`)
2. Verify no merge conflicts
3. Verify PR review evidence exists for this branch
4. Merge using squash strategy (or project-configured strategy from project-preferences.md)
5. Delete remote branch, switch to base branch, pull, delete local branch
6. Clean up evidence file

## Status Flow

Show: PR URL, CI status, review status, approval status, merge readiness.

## Evidence

PR review evidence is stored in `.prawduct/.pr-reviews/<branch-name>.json` (with `/` replaced by `--` in filenames). This is checked by the stop hook.

## Important

- The PR reviewer runs as a **separate agent** via the Task tool — it must have independent context
- For the framework repo itself, the reviewer reads `agents/pr-reviewer/SKILL.md`
- For product repos, the reviewer reads `.prawduct/pr-review.md`
- Always run the full test suite before creating a PR
- Include review findings summary in the PR description
