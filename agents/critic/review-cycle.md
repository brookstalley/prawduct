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

The stop hook enforces review for code changes when a build plan exists. It also surfaces an advisory WARNING when all chunks are marked `[x]` but the most recent review was `chunk` mode — run `/critic final` before pushing.

## Mode Selection

The build plan is authoritative. Each chunk declares `Critic mode: chunk | final` (see `templates/build-plan.md`). The build cycle reads the field and invokes `/critic chunk` or `/critic final` accordingly.

**Heuristic when authoring a build plan:**
- Single-chunk plan → `final`.
- Multi-chunk plan → first N-1 chunks `chunk`, last chunk `final`.
- Trivial chunks (typo-level edits buried inside a larger plan) → waive entirely.

**Fail-safe default:** if the field is absent, the build cycle treats the chunk as `final`. Do not omit the field expecting the default — declare it. If the Critic itself is invoked without `$ARGUMENTS` or with an unrecognized mode, it runs `final`.

## Per-Mode Behavior

| Aspect | `chunk` | `final` |
|---|---|---|
| **Goals run** | 1 (Nothing Is Broken), 2 (Nothing Is Missing), 3 (Nothing Is Unintended) | All 7 goals |
| **Goals skipped** | 4-7; Learnings Cross-Check; Backlog Reconciliation; Framework-Specific Checks (7-10); README/top-level docs scan | None |
| **Scope** | The chunk's uncommitted diff (`git diff` for tracked files plus `git status` for new files) | Full session diff at end-of-cycle, OR uncommitted diff for non-chunked work |
| **Execution** | Always single-pass; no coordinator pattern | Single pass for trivial/small; coordinator pattern (3 subagents) for medium/large |
| **Target wall-clock** | 1-2 min | 4-10 min |
| **When invoked** | Between chunks of a multi-chunk plan, before committing | End of work cycle (last chunk), non-chunked medium+ work, or any time the right answer is unclear |

**Two-form rule for the `mode` value:**
- **Caller-side** (in `$ARGUMENTS`, build plan field `Critic mode:`, slash-command argument): the short token — `chunk` or `final`.
- **Persisted-side** (in `.prawduct/.critic-findings.json`'s `mode` field, session briefings, gate WARNINGs): the verbose string — exactly `"chunk (lighter pass, not ready for push)"` or `"final (full review, ready for push)"`.

Read short, write verbose. Verbose makes the JSON self-documenting in briefings — anyone reading the file sees what mode was used without consulting docs. The hook validator in `tools/product-hook` rejects bare short tokens in the persisted `mode` field.

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
