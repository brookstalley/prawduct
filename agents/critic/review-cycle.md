# Critic: Review Cycle (Product Builds)

Per-chunk review lifecycle during the build phase.

---

## Per-Chunk Cycle

1. Builder completes a chunk's implementation and tests.
2. Critic runs all applicable checks: Spec Compliance → Test Integrity → Scope Discipline → (others as applicable).
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

### Spec Compliance
[Checklist table]

### Test Integrity
- Test count: [before] → [after] [PASS/FAIL]
- Test files deleted: [none / list] [PASS/FAIL]
- New tests added: [count] [PASS/WARNING]
- Behavior vs. implementation testing: [assessment]
- Error case coverage: [assessment]

### Scope Discipline
- Unlisted dependencies: [none / list]
- Unspecified patterns: [none / list]
- Extra functionality: [none / list]

### Findings

#### [Finding Name]
**Check:** [Check Name]
**Severity:** blocking | warning | note
**Recommendation:** [What the Builder should do]

### Summary
[Total findings by severity. Whether the chunk passes review.]
```

## Recording Reviews

Every review cycle must produce a findings record — governance without an audit trail is documentation fiction.

After each review cycle, write `.prawduct/.critic-findings.json` with the findings (see main SKILL.md for format). When no findings exist, record an empty findings array.
