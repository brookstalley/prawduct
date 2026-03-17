# Build Plan: PR Reviewer Agent & `/pr` Skill

## Classification
- **Size**: medium (new agent + skill + init/sync/hook integration)
- **Type**: feature
- **Governance**: full (Critic per chunk)

## Design Reference
`.prawduct/artifacts/pr-reviewer-design.md`

## Chunks

### Chunk 1: PR Reviewer Agent + Condensed Template
**Files:**
- `agents/pr-reviewer/SKILL.md` — full reviewer instructions (modeled on Critic pattern)
- `templates/pr-review.md` — condensed version for product repos

**Acceptance:** Agent has complete review instructions covering all 7 goals. Template is a faithful condensation.

### Chunk 2: `/pr` Slash Command + Discoverability
**Files:**
- `.claude/commands/pr.md` — framework's own `/pr` command
- `templates/commands-pr.md` — template deployed to product repos as `.claude/commands/pr.md`
- `templates/product-claude.md` — discoverability: route PR-related requests to `/pr`
- `methodology/building.md` — add PR section

**Acceptance:** `/pr` command works in framework repo. Template ready for deployment. Any PR-related user request ("PR this", "create a PR", "push this up") routes to `/pr`.

### Chunk 3: Init/Sync/Hook Integration + Tests
**Files:**
- `tools/prawduct-init.py` — deploy pr-review.md, commands/pr.md, .pr-reviews/ gitignore
- `tools/prawduct-sync.py` — add manifest entries for new files
- `tools/product-hook` — stop hook advisory for PR review evidence
- `tests/test_pr_reviewer.py` — tests for init/sync/hook integration
- `.prawduct/cross-cutting-concerns.md` — add PR Review row
- `.prawduct/project-state.yaml` — update WIP, test count, change log

**Acceptance:** `prawduct-init.py` creates all PR reviewer files in new products. Sync updates them. Stop hook warns if PR created without review evidence. All tests pass.

## Post-Build
- Critic review after chunk 3
- Session reflection
