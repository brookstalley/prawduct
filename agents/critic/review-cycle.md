# Critic: Review Cycle (Product Builds)

Product build chunk lifecycle — how the Critic interacts with the Builder during Stage 5.

---

## Per-Chunk Cycle

1. Builder marks chunk status as "review" in `project-state.yaml`.
2. Critic runs all applicable checks: Spec Compliance → Test Integrity → Scope Discipline → (others as applicable).
3. **If BLOCKING findings exist:**
   - Builder fixes the issues.
   - Critic re-reviews — specifically watching for **fix-by-fudging**:
     - Weakening a test to make it pass instead of fixing the code → **BLOCKING**
     - Changing a spec to match wrong implementation instead of fixing the code → **BLOCKING**
     - Adding a workaround instead of addressing root cause → **WARNING**
   - Repeat until no blocking findings remain.
4. **Record findings in project state.** This step is mandatory for every chunk, regardless of whether findings exist. Update `project-state.yaml` → `build_state.reviews` with findings from this review cycle (see Recording Reviews below).
5. **If no BLOCKING findings:** chunk status → "complete", proceed to next chunk.

## Directional Change Review

This review is invoked by the Orchestrator after all chunks from a directional change are complete — not after each individual chunk (per-chunk checks still apply during the build).

**When to invoke:** The Orchestrator's Directional Change Protocol invokes this after implementation and before the retrospective.

**What to check:**

- **Artifact consistency:** Were all affected artifacts updated before building? If implementation references stale artifact content → **BLOCKING**.
- **Retrospective completeness:** Did the Orchestrator run the post-shift retrospective? If missing → **WARNING**.
- **Observation capture:** Were substantive findings captured as observations? If the retrospective identified gaps but no observations created → **WARNING**.
- **Regression check:** Do pre-existing tests still pass? → **BLOCKING** if violated (HR1: No Test Corruption).

## Per-Chunk Output Format

```
## Governance Review — Chunk [ID]: [Name]

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
**Description:** [Specific observation]
**Recommendation:** [What the Builder should do]

### Summary
[Total findings by severity. Whether the chunk passes review.]
```

## Recording Reviews — MANDATORY

**Every review cycle must produce a `build_state.reviews` entry.** This is not optional — governance without an audit trail violates HR3 (No Documentation Fiction).

After each review cycle, update `project-state.yaml` → `build_state.reviews` with:
```yaml
- chunk_id: "[current chunk]"
  findings:
    - description: "[finding]"
      severity: blocking | warning | note
      status: open | resolved | deferred
```

**When no findings exist**, record an empty-findings entry:
```yaml
- chunk_id: "[current chunk]"
  findings: []
```

**Verification:** After recording, confirm that `build_state.reviews` contains an entry for the current chunk before proceeding.
