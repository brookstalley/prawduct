# Critic: Review Cycle

Work-scaled review lifecycle. Review depth matches the size of the work.

---

## When Review Is Required

| Work size | Mode and frequency |
|---|---|
| **Trivial** (typo, config) | None — waive via `.gates-waived` if the stop hook prompts. |
| **Small** (bug fix, minor feature) | One `final` review, optional. |
| **Medium** (new feature, refactor) — non-chunked | One `final` review, mandatory after completion. |
| **Medium / Large** (chunked build plan) | `chunk` review per non-final chunk + `final` review on the last chunk. |
| **Any work merging a multi-cycle branch** | `cumulative` review before opening the PR (in addition to the per-chunk reviews above). |

The stop hook enforces review for code changes when a build plan exists. It also surfaces an advisory WARNING when all chunks are marked `[x]` but the most recent review was `chunk` mode — run `/critic final` before pushing.

`/pr create` is gated by `python3 tools/product-hook check-cumulative-critic` — opening a PR without a fresh, blocking-free `cumulative` record fails the gate.

## Mode Selection

The build plan is authoritative. Each chunk declares `Critic mode: chunk | final` (see `templates/build-plan.md`). The build cycle reads the field and invokes `/critic chunk` or `/critic final` accordingly.

**Heuristic when authoring a build plan:**
- Single-chunk plan → `final`.
- Multi-chunk plan → first N-1 chunks `chunk`, last chunk `final`.
- Trivial chunks (typo-level edits buried inside a larger plan) → waive entirely.

**Fail-safe default:** if the field is absent, the build cycle treats the chunk as `final`. Do not omit the field expecting the default — declare it. If the Critic itself is invoked without `$ARGUMENTS` or with an unrecognized mode, it runs `final`.

## Per-Mode Behavior

| Aspect | `chunk` | `final` | `cumulative` |
|---|---|---|---|
| **Goals run** | 1, 2, 3 | All 7 goals | All 7 goals |
| **Goals skipped** | 4-7; Learnings Cross-Check; Backlog Reconciliation; Framework-Specific Checks (7-10); README/top-level docs scan | None | None |
| **Scope** | Chunk's uncommitted diff (`git diff` + `git status` for new files) | Full session diff at end-of-cycle, OR uncommitted diff for non-chunked work | `git diff <base-branch>...HEAD` — the entire PR bundle, all commits on the branch since it diverged |
| **Execution** | Always single-pass | Single pass for trivial/small; coordinator pattern for medium/large | Single pass for trivial/small; coordinator pattern for medium/large |
| **Target wall-clock** | 1-2 min | 4-10 min | 4-10 min |
| **When invoked** | Between chunks of a multi-chunk plan, before committing | End of work cycle (last chunk), non-chunked medium+ work, or any time the right answer is unclear | Before opening a PR (gated by `/pr create`). Catches cross-chunk integration cracks. |

**Two-form rule for the `mode` value:**
- **Caller-side** (in `$ARGUMENTS`, build plan field `Critic mode:`, slash-command argument): the short token — `chunk`, `final`, or `cumulative`.
- **Persisted-side** (in `.prawduct/.critic-findings.json`'s `mode` field, session briefings, gate WARNINGs): the verbose string — exactly `"chunk (lighter pass, not ready for push)"`, `"final (full review, ready for push)"`, or `"cumulative (bundle review, ready for merge)"`.

Read short, write verbose. Verbose makes the JSON self-documenting in briefings — anyone reading the file sees what mode was used without consulting docs. The hook validator in `tools/product-hook` rejects bare short tokens in the persisted `mode` field.

### Cumulative-mode diff scope and PR gate

`cumulative` is the only mode whose scope is *not* derived from working-tree state. Compute the base via `git merge-base <base-branch> HEAD` (typically `main` or `develop` — read `project-preferences.md` if a different default is set). Then diff `<merge-base>...HEAD`. This deliberately spans every commit on the branch, not just the end-of-cycle diff `final` would see, so cross-chunk integration cracks surface here even if every per-chunk review was clean.

`/pr create` calls `python3 tools/product-hook check-cumulative-critic` and refuses to open the PR if the gate fails. The gate requires: cumulative-mode findings file present, schema-valid, recorded in the current session (mtime later than `.session-start`), and free of unresolved BLOCKING findings. WARNING and NOTE are advisory at the PR gate — they do not block, matching the PR reviewer's own severity contract.

**Prep work before invoking cumulative.** A cumulative review takes ~4-10 minutes synchronously. Before invoking it, complete any prep work that doesn't depend on its findings: `/learnings` for next-chunk topics, draft the PR description, audit the backlog for items this branch resolves, capture deferred chunk-boundary reflections. This does NOT shorten the wait — it reorganizes work so the agent can integrate findings the moment Critic returns rather than spinning up fresh post-wait. See `methodology/building.md` for the full guidance.

## Per-Chunk Cycle

1. Builder completes a chunk's implementation and tests.
2. Critic reviews using the goal-based approach (see SKILL.md).
3. **If BLOCKING findings exist:**
   - Builder fixes the issues.
   - Critic re-reviews — specifically watching for **fix-by-fudging**:
     - Weakening a test to make it pass instead of fixing the code → **BLOCKING**
     - Changing a spec to match wrong implementation instead of fixing the code → **BLOCKING**
     - Adding a workaround instead of addressing root cause → **WARNING**
   - Repeat until no blocking findings remain.
4. **Record findings** to `.prawduct/.critic-findings.json` (see main SKILL.md for format).
5. **If no BLOCKING findings:** chunk is complete, proceed to next chunk.

## Final-Mode Cross-Checks

After completing the goal-based review in `final` mode, run two additional passes that `chunk` mode skips:

### Learnings Cross-Check

Scan your findings against active learnings. If a change reintroduces a pattern that `.prawduct/learnings.md` explicitly warns against, escalate severity — the project already learned this lesson once and tolerating regression undoes the learning. Conversely, if learnings reference patterns relevant to the changed code and the code handles them correctly, no finding is needed: the learning is working as intended.

### Backlog Reconciliation

Read `.prawduct/backlog.md`. For each open item, check whether this session's changes resolve it — directly (the item was the work) or incidentally (other work addressed the underlying issue). For each resolved item, emit a **NOTE** finding: "Backlog item appears resolved: [item text]. Verify and remove from backlog." This keeps the backlog reflecting reality. Do not remove items yourself — the builder verifies and removes.

## Directional Change Review

When a significant architectural or design change spans multiple chunks, review the change holistically after all chunks are complete:

- **Artifact consistency:** Were all affected artifacts updated? Implementation referencing stale artifact content → **BLOCKING**.
- **Regression check:** Were pre-existing tests modified or removed? Review the diff for weakened or deleted tests → **BLOCKING** if tests were weakened to pass.
- **Retrospective:** Was the change reflected on? If missing → **WARNING**.

## Per-Chunk Output Format

```
## Critic Review — Chunk [ID]: [Name]

### Signals
[Work size, work type, files changed, boundaries crossed]

### Changes Reviewed
[List of files and what changed]

### Findings

#### [Finding Name]
**Goal:** [Goal Name]
**Severity:** blocking | warning | note
**Recommendation:** [What the Builder should do]

### Summary
[Total findings by severity. Whether the chunk passes review.]
```

## Recording Reviews

Every review cycle must produce a findings record — governance without an audit trail is documentation fiction.

After each review cycle, write `.prawduct/.critic-findings.json` with the findings (see main SKILL.md for format). When no findings exist, record an empty findings array.
