# PR Reviewer Agent & `/pr` Skill — Design

## Purpose

Every PR created in a prawduct project should be approved and merged with zero changes. The PR reviewer agent provides an independent, fresh-perspective review at the PR boundary — complementing the Critic (which reviews work quality per-chunk) with release-readiness assessment of the whole changeset.

## Architecture

Two components:

1. **PR Reviewer Agent** — separate agent invoked via Task tool. Reviews the full diff from base branch. Independent context (hasn't seen the builder's reasoning). Writes findings to evidence file.

2. **`/pr` Skill** — single entry point for the full PR lifecycle. Context-aware: detects current state and does the right thing. Invokes the reviewer agent during creation. Enforces branch hygiene throughout.

## `/pr` Skill Behavior

### Context Detection

The skill reads git state to determine the action:

| State | Default Action |
|---|---|
| No PR for current branch, branch has commits ahead of base | **Create** |
| PR exists, new local commits not pushed | **Update** |
| PR exists, CI green, approved (or no required reviewers) | **Merge** |
| PR exists, other state | **Status** |

Explicit override: `/pr create`, `/pr merge`, `/pr status`, `/pr update`.

### Create Flow

1. **Branch hygiene checks**
   - Verify on a feature branch (not main/master/develop or configured base)
   - Verify branch has commits ahead of base
   - Warn if uncommitted changes exist (offer to commit or stash)
   - Run test suite (or verify recent passing run)

2. **Spawn PR reviewer agent** (via Task tool, separate context)
   - Agent reads full diff: `git diff <base>...HEAD`
   - Agent reads commit log: `git log <base>..HEAD`
   - Agent reads project-state.yaml for work context
   - Agent reads PR review instructions (SKILL.md or pr-review.md)
   - Agent writes findings to `.prawduct/.pr-reviews/<branch-name>.json`

3. **Handle findings**
   - BLOCKING findings: present to user, do not create PR until resolved
   - WARNING findings: present to user, proceed unless user wants to fix
   - NOTE findings: include in output, proceed

4. **Create PR**
   - Push branch with `-u` if not already pushed
   - Draft title from work description + commit summary
   - Draft description: summary, key decisions, test evidence, review findings
   - Create via `gh pr create`
   - Update evidence file with PR number

### Update Flow

1. Push new commits to remote
2. Re-run reviewer on the delta (new commits only) if substantive changes
3. Update PR description if scope changed
4. Update evidence file

### Merge Flow

1. **Pre-merge checks**
   - Verify CI checks pass (`gh pr checks`)
   - Verify approval status (if required reviewers configured)
   - Verify no merge conflicts
   - Verify PR review evidence exists for this branch

2. **Merge**
   - Use project-preferred merge strategy (squash by default, configurable)
   - Delete remote branch
   - Switch to base branch and pull
   - Delete local branch
   - Clean up evidence file

### Status Flow

Show: PR URL, CI status, review status, approval status, merge readiness.

## PR Reviewer Agent

### Role

Independent release-readiness reviewer. The Critic ensures work quality during building. The PR reviewer ensures the changeset is ready to merge — right scope, no bugs, well-tested, clearly explained, proportional.

The reviewer has NOT seen the builder's reasoning. This independence is structural — it enables genuinely fresh-eyes review.

### Review Goals (Priority Order)

#### 1. No Bugs Shipped
**Severity: BLOCKING**

Review the full diff for:
- Logic errors (off-by-one, null handling, type confusion)
- Race conditions or concurrency issues
- Security vulnerabilities (injection, auth bypass, data exposure)
- Error handling gaps (unhandled exceptions, silent failures)
- Edge cases (empty inputs, boundary values, overflow)

The Critic may have caught these per-chunk. The reviewer catches what slipped through or emerged from cross-chunk interactions.

#### 2. Tests Cover the Change
**Severity: BLOCKING**

- New code paths have corresponding tests
- Edge cases and error paths are tested
- Integration tests exist for cross-component changes
- Test assertions are meaningful (not just "doesn't throw")
- No test coverage regressions

#### 3. Right Scope and Granularity
**Severity: WARNING**

- PR represents a single coherent change (one logical unit)
- Scope matches the stated work description
- No unrelated changes bundled in
- If oversized: is it practically splittable? (only flag if splitting is cheap — respect that the work is done)

#### 4. Clear Narrative
**Severity: WARNING**

- PR title clearly describes what changed (under 70 chars)
- Description explains WHY, not just WHAT
- Key design decisions are documented
- An unfamiliar reviewer could understand this PR from the description + diff

#### 5. Simplification Opportunities
**Severity: NOTE**

- Unnecessary complexity (could this be simpler?)
- Dead code introduced
- Overly defensive patterns where trust is warranted
- Duplicated logic that could be extracted (only if clearly beneficial)

Scope boundary: flag **simplifications** (cheap to act on), not **alternatives** (architectural rethinks). "This function could be 3 lines" is valid. "You should have used a different pattern" is not — that was the Critic's job during building.

#### 6. Merge Hygiene
**Severity: WARNING**

- No debug code, console.logs, commented-out experiments
- No unintended file changes (lock files, IDE configs, unrelated formatting)
- No TODOs or placeholders left in shipped code
- No secrets or credentials

#### 7. Proportionality
**Severity: NOTE**

- Effort matches the task size and risk
- Over-engineered? (abstractions for one-time operations, premature generalization)
- Under-engineered? (shortcuts that will cause near-term rework)

### Evidence Format

Written to `.prawduct/.pr-reviews/<branch-name>.json`:

```json
{
  "timestamp": "2026-03-17T14:30:00Z",
  "branch": "feature/add-auth",
  "base": "main",
  "pr_number": null,
  "commits_reviewed": 3,
  "files_reviewed": ["src/auth.py", "tests/test_auth.py"],
  "findings": [
    {
      "goal": "No Bugs Shipped",
      "severity": "blocking",
      "file": "src/auth.py",
      "line": 42,
      "summary": "Token comparison uses == instead of constant-time compare"
    }
  ],
  "summary": "1 blocking, 0 warnings, 0 notes. Fix timing-safe comparison before creating PR."
}
```

After PR creation, `pr_number` is updated. After merge, the evidence file is deleted with the branch.

### Output Format

```markdown
## PR Review

### Context
[Branch, base, commits, files changed, work description from project-state]

### Findings

#### [Finding Title]
**Goal:** [Goal Name]
**Severity:** blocking | warning | note
**File:** [path:line] (if applicable)
**Recommendation:** [What to do]

### PR Draft
**Title:** [Suggested title]
**Description:**
[Draft PR description — summary, key decisions, test evidence]

### Summary
[Findings count by severity. Whether PR is ready to create.]
```

## File Layout

### Framework (this repo)

```
agents/pr-reviewer/
├── SKILL.md              # Full reviewer instructions
└── review-criteria.md    # Detailed criteria with examples (optional, if SKILL.md gets long)
```

### Product repos (via templates)

```
.prawduct/
├── pr-review.md                    # Condensed reviewer instructions (like critic-review.md)
└── .pr-reviews/                    # Evidence directory (gitignored)
    └── <branch-name>.json
```

### Skill definition

The `/pr` skill is defined as a Claude Code command file in the product repo, placed by `prawduct-init.py` and kept in sync by `prawduct-sync.py`. Location follows Claude Code conventions for custom slash commands.

## Integration with Existing Governance

### Stop hook enhancement

The stop hook gains a third check: if a PR was created this session (detectable via `gh pr list --author @me --state open` or git reflog), warn if no PR review evidence exists for that branch. This is advisory (WARNING), not blocking — the Critic gate remains the hard block.

### Build methodology reference

`methodology/building.md` gains a brief section: "Before creating a PR, use `/pr` to review and create. This invokes the PR reviewer agent for independent assessment. See `agents/pr-reviewer/SKILL.md` for review criteria."

### Cross-cutting concerns

Add "PR Review" row to `.prawduct/cross-cutting-concerns.md`:
- Discovery: N/A (PR review is a framework capability, not a per-product discovery concern)
- Artifact: `agents/pr-reviewer/SKILL.md`, `templates/pr-review.md`
- Builder: `methodology/building.md` PR section
- Critic: N/A (PR reviewer is a peer of the Critic, not reviewed by it)

## Relationship to Critic

| Dimension | Critic | PR Reviewer |
|---|---|---|
| **When** | After each build chunk | Before PR creation |
| **Scope** | One chunk's changes | Full PR diff (all chunks) |
| **Perspective** | Is the work good? | Is this ready to merge? |
| **Key concerns** | Spec compliance, tests, coherence | Bugs, scope, narrative, simplification |
| **Enforcement** | BLOCKING (stop hook) | WARNING (stop hook advisory) |
| **Independence** | Separate agent (Task tool) | Separate agent (Task tool) |

## Configuration

Products can configure PR behavior in `project-preferences.md` or `project-state.yaml`:

```yaml
pr_preferences:
  merge_strategy: squash          # squash | merge | rebase
  base_branch: main               # default base for PRs
  protected_branches: [main, develop]  # branches that can't be PR source
  require_review_before_create: true   # enforce reviewer before PR creation
```

## Open Questions

1. **Skill registration mechanism**: How exactly are custom slash commands registered in Claude Code? Need to verify during build phase. May be `.claude/commands/pr.md` or similar.
2. **Delta review for updates**: When pushing new commits to an existing PR, should the reviewer re-review the full diff or just the new commits? Full diff catches emergent issues; delta is faster. Lean toward delta with periodic full re-review.
3. **Non-GitHub remotes**: The design assumes GitHub (`gh` CLI). Should we abstract for GitLab/Bitbucket support later, or keep it GitHub-only for v1? Lean toward GitHub-only, clean abstraction boundary for future extension.
