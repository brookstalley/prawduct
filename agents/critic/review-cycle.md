# Critic: Review Cycle

Work-scaled review lifecycle. Review depth matches the size of the work.

---

## When Review Is Required

- **Trivial** (typo, config): No Critic review needed.
- **Small** (bug fix, minor feature): Optional Critic review.
- **Medium** (new feature, refactor): Critic review mandatory after completion.
- **Large** (subsystem, architecture): Critic review per chunk.

The stop hook enforces review for code changes when a build plan exists.

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
- **Regression check:** Do pre-existing tests still pass? → **BLOCKING** if violated.
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
