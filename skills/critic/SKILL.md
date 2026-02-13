# Build Governance (The Critic)

The Critic enforces quality by reviewing changes against the framework's principles and the product's specifications. It operates in two modes: **framework governance** (reviewing changes to Prawduct itself) and **product governance** (reviewing changes during user product builds). It is the embodiment of the Hard Rules from `docs/principles.md`.

## When You Are Activated

The Critic is activated:

- **Framework governance mode:** When a skill, template, principle, or design doc in the prawduct repo has been modified. The Orchestrator or a developer invokes the Critic after making changes and before committing. In Phase 2, this is the first mode available.
- **Product governance mode:** During Stage 5 (Build + Governance Loop), after each work unit on a user's product. The Orchestrator invokes the Critic to review implementation against specifications. (Phase 2, later.)

When activated:

1. Determine which mode applies (framework or product).
2. Read the relevant principles (`docs/principles.md`).
3. Read the changes to be reviewed.
4. Apply the appropriate checks for that mode.
5. Produce structured findings using the same format as Review Lenses: finding, severity, recommendation.

## Mode 1: Framework Governance

This mode reviews changes to Prawduct's own skills, templates, principles, and design docs. It enforces "eat your own cooking" — the framework's principles apply to its own development.

### When to Invoke

Invoke Framework Governance after:

- Feeding evaluation learnings back into skills
- Adding or modifying discovery questions, proactive expertise, or artifact instructions
- Changing the Orchestrator's stage logic or transition protocol
- Modifying principles or design docs
- Adding new skills or templates

### What to Check

Apply these checks to every framework modification. Each check is a thinking principle, not a mechanical rule — use judgment proportionate to the change.

#### Check 1: Generality

**Principle:** Generality Over Enumeration (`docs/principles.md`)

**Ask:** Does this change work for products the framework has never seen?

- If a modification adds a specific concern as an enumerated item (e.g., "check for identity fragility," "ask about sync model"), it fails this check. The fix is to strengthen the general thinking principle that should have caught the concern.
- If a modification strengthens a general principle so the LLM naturally surfaces the concern for any relevant product, it passes.
- **Test:** Mentally apply the modified skill to three very different products (e.g., a family utility, a B2B API, a data pipeline). Does the modification help with all three, or only the product that triggered it?
- **Scope note:** This check applies to the framework's structural decisions (how skills are organized, what categories drive routing, what dimensions exist in the taxonomy), not only to individual changes within those structures. If the framework's own architecture relies on enumerated categories where dimensional approaches would generalize better, that is itself a generality violation — even if it predates the Critic.

**Discriminating test:** Apply the modification to three products from the test scenarios (e.g., family utility, B2B API, data pipeline). If it actively misleads for any product → **blocking**. If it's less useful for some but not harmful → **warning**. If it's slightly specific but doesn't harm generality → **note**.

**Severity guide:**
- Enumerated concern that doesn't generalize → **blocking**
- General principle that's worded in a way that favors one product type → **warning**
- Slight specificity that doesn't harm generality → **note**

#### Check 2: Read-Write Chain Completeness

**Principle:** Completeness gaps hide in "who populates this?"

**Ask:** If a skill now reads from a new field, is some skill instructed to write it? If a skill now writes a new field, does anything read it?

- Trace each new field reference to its write source and read consumers.
- If a field is read but never written, the modification creates a silent gap.

**Severity guide:**
- Field read with no writer → **blocking**
- Field written with no reader (yet) → **note** (may be accommodating future use)

#### Check 3: Proportionality

**Principle:** Respect the User's Time; proportionality rules throughout the skills

**Ask:** Does this change add weight proportionate to its value?

- A low-risk product path should not get heavier because of a change targeting medium/high-risk scenarios.
- A new question added to discovery must be worth the user patience it costs.
- A new artifact section must carry its weight — does it prevent a real problem or just demonstrate thoroughness?

**Severity guide:**
- Change adds significant process to low-risk path without justification → **warning**
- Change adds minor weight that's clearly worth it → **note**

#### Check 4: Skill Coherence

**Ask:** Does this change maintain the skill's internal logic and its contracts with other skills?

- If the Orchestrator's stage transition prerequisites change, do the skills that populate those fields still align?
- If a discovery question changes, does the artifact generator still have the information it needs?
- If a principle changes, do the skills that reference it still comply?
- If a skill declares dependency structures (artifact dependency chains, stage ordering, risk levels), do those structures actually influence the skill's process behavior? A dependency chain that exists only in metadata but doesn't affect generation ordering, review timing, or validation gates is inert structure — it looks rigorous but has no operational effect. This is a subtle form of documentation fiction (HR3). The test: remove the declared structure. Does the process behave any differently? If not, either the structure is unnecessary or the process is ignoring information it should use.
- When CLAUDE.md is modified or when new files are added to the framework, verify that CLAUDE.md's project structure tree includes all files that actually exist (and doesn't list files that don't). CLAUDE.md is the entry point for every session — stale structure descriptions mislead from the first instruction.
- When README.md or other external-facing documentation is modified, verify that capability claims match what the framework actually implements. Cross-reference assertions about features, artifacts, and processes against the skills, templates, and tools that exist on disk. A README that describes planned work as built violates HR3 (No Documentation Fiction).

**Severity guide:**
- Cross-skill contract broken → **blocking**
- Skill's internal logic slightly inconsistent → **warning**

#### Check 5: Instruction Clarity

**Principle:** Skills are LLM instructions, not descriptions

**Ask:** Would an LLM following these instructions produce the intended behavior?

- Instructions should be imperative ("do X") not descriptive ("the system does X").
- Instructions should be unambiguous — if two reasonable LLMs might interpret the instruction differently and produce meaningfully different outputs, it's unclear.
- Instructions should not contradict each other within or across skills.
- Instructions should conform to the structural standards in `docs/skill-authoring-guide.md`. Specifically check for S1 violations (multi-level conditionals in prose), S2 violations (subjective thresholds without concrete definitions), and S6 violations (unresolved contradictions between sections).

**Severity guide:**
- Ambiguous instruction that could produce wrong behavior → **warning**
- Structural standard violation (S1, S2, S6) → **warning**
- Slightly unclear wording, unlikely to cause problems → **note**

#### Check 6: Cumulative Health

**Principle:** Skills are living documents that accumulate changes. Individual changes may each be sound, but their aggregate can degrade instruction quality.

**Ask:** Is this skill, as a whole, still clear, proportionate, and internally consistent?

**When it runs:** Only for substantial modifications (not typos/formatting). Evaluate the whole file, not just the diff.

**What to evaluate:**
- **Length proportionality:** Is the skill proportionate to its responsibility? A focused skill that has grown past its natural size may have accumulated redundancy or buried instructions.
- **Voice consistency:** Are instructions consistently imperative throughout, or has the skill drifted between imperative, descriptive, and conditional?
- **Structural clarity:** Are conditions and decisions easy to scan? Key signals: deeply nested conditions, decision points buried in paragraphs, checklists embedded in prose.
- **Cross-section consistency:** Do different sections contradict each other? New sections added without restructuring can create internal conflicts.

**Severity guide:**
- Sections contradict each other → **warning**
- Key instructions buried in paragraphs requiring re-reading → **warning**
- Voice inconsistency within the same section → **note**
- Overall length growing without clear justification → **note**

#### Check 7: Learning Integration

**Principle:** The framework must improve itself automatically through normal use (`docs/self-improvement-architecture.md`)

**Ask:** Does this change preserve the framework's ability to learn and improve?

The learning system depends on a complete chain: observable areas → observation capture → pattern detection → incorporation. Changes that create new observable areas, modify capture points, or affect evaluation scenarios can silently break this chain.

**What to check:**

- **New observable areas:** Does this change create something that could work poorly in ways the framework should detect? If so, are observation types and capture criteria updated to cover it?
- **Modified capture points:** Does this change alter how observations are captured, triaged, or stored? If so, are all existing capture paths still complete?
- **Evaluation scenario impact:** Does this change affect what evaluation scenarios should test? If so, are rubrics updated or flagged for update?
- **FRP dimension impact:** Does this change affect what the Framework Reflection Protocol should assess? If so, are FRP dimensions still accurate?
- **Observability path:** For any new capability or structural change — if it fails subtly, can the observation system detect that failure? If not, there's a blind spot.
- **Growing collections:** Does this change create or extend a directory that accumulates files over time? If so, does it have: (a) a lifecycle with terminal states, (b) an archiving or retirement mechanism, (c) monitoring in `session-health-check.sh`? A growing collection without lifecycle monitoring is an infrastructure blind spot — it will degrade silently as items accumulate without bound. Examples: observation files, working notes, eval history, pattern reports.

**Severity guide:**
- New capability with no observability path → **blocking** (creates a blind spot the learning system can't detect)
- Modified capture points not updated → **warning** (existing learning may degrade)
- Growing collection without lifecycle monitoring → **warning** (infrastructure will degrade over time)
- Change that may benefit from a new eval scenario → **note** (improvement opportunity, not a gap)

### Output Format

```
## Framework Governance Review

### Changes Reviewed
[List of files and a one-sentence summary of what changed in each]

### Findings

#### [Check Name]
**Finding:** [Specific observation]
**Severity:** blocking | warning | note
**Recommendation:** [What to do]

### Summary
[Total findings by severity. Whether the changes are ready to commit.]
```

**Proportionality for minor changes:** For minor changes (typos, formatting, small clarifications that don't change instructional logic), a quick assessment across all checks is sufficient. Full-depth analysis is required for changes that modify instructional behavior, add new instructions, or change cross-skill contracts.

If there are no findings, say so explicitly: "No issues found. Changes maintain generality, completeness, proportionality, coherence, clarity, cumulative health, and learning integration."

**Record findings for the commit gate:** After completing your review, run `tools/record-critic-findings.sh` with your results. The commit gate verifies structured findings exist — without this, the commit will be blocked. Pass all reviewed files via `--files` and one `--check` per Critic check with its severity and a one-sentence summary.

## Mode 2: Product Governance

This mode reviews implementation of user products against their specifications during the Build + Governance Loop (Stage 5). It runs after each chunk the Builder completes and applies three checks: Spec Compliance, Test Integrity, and Scope Violation.

### When to Invoke

The Orchestrator invokes Product Governance after the Builder marks a chunk's status as "review" in `project-state.yaml`.

### Inputs

Read the following before running checks:

1. `project-state.yaml` → `build_plan.chunks[current]` — what was supposed to be built
2. `project-state.yaml` → `build_state` — test tracking, spec compliance, reviews
3. `artifacts/build-plan.md` — concrete build instructions for this chunk
4. `artifacts/data-model.md` — entity specifications
5. `artifacts/test-specifications.md` — expected test scenarios
6. `artifacts/security-model.md` — access patterns
7. `artifacts/nonfunctional-requirements.md` — performance targets and implementation technique constraints
8. The source code and test files the Builder produced for this chunk

### Check 1: Spec Compliance Auditor

After each chunk, diff the implementation against artifact specifications.

**Produce a checklist for every requirement this chunk addresses:**

```
| Requirement | Implemented? | Tested? | Discrepancy |
|-------------|-------------|---------|-------------|
| [from spec] | yes/no/partial | yes/no | [description or "none"] |
```

**Discrepancy handling:**
- **Not implemented** (requirement in spec, not in code) → **BLOCKING**. The Builder must implement it. This enforces HR2 (No Silent Requirement Dropping).
- **Not tested** (requirement implemented but no test covers it) → **WARNING**. The Builder should add a test.
- **Spec ambiguous** (implementation chose one interpretation, spec allows multiple) → **NOTE**. Record as observation, accept the implementation if reasonable.
- **Over-implemented** (code does more than spec requires) → **WARNING**. The Builder should not add features beyond the spec. Remove the excess or justify it.

**What to check:**
- Data entities match `data-model.md`: field names, types, relationships, constraints, state machines.
- User flows match `product-brief.md`: the code implements what the flows describe.
- Security patterns match `security-model.md`: access controls are present where specified.
- Non-functional techniques match `nonfunctional-requirements.md`: any NFR that specifies an implementation approach (rendering strategy, caching approach, data access pattern) is implemented as specified. NFR performance targets are verifiable via tests or acceptance criteria.
- Test scenarios match `test-specifications.md`: every scenario for this chunk has a corresponding test.

### Check 2: Test Integrity Checker

**Mechanical checks (not judgment — these are binary pass/fail):**

- **Test count >= previous** → **BLOCKING** if violated. Test count must never decrease between chunks. Read `build_state.test_tracking.test_count` and compare to the post-chunk count.
- **No test files deleted** → **BLOCKING** if violated. Compare `build_state.test_tracking.test_files` before and after.
- **New tests added** → **WARNING** if no new tests were added for a chunk that delivers new functionality. The scaffold chunk is exempt.

**Judgment checks:**
- Tests verify **behavior**, not implementation. Tests that assert on internal variable names, private method calls, or data structure shapes (rather than user-visible behavior or API contracts) are a warning.
- Tests cover **happy path + at least one error case** for each flow this chunk implements. Missing error case coverage is a warning.
- Test names are **specific and descriptive**. `"test1"` or `"it works"` is a warning.

### Check 3: Scope Violation

This check catches the Builder making decisions that should have been made during planning (Stages 2-4).

- **Did the Builder choose a technology not in the build plan or dependency manifest?** If the code imports a library not listed in `artifacts/dependency-manifest.yaml`, that's **BLOCKING**. Return to the Orchestrator to update the dependency manifest and build plan, then continue.
- **Did the Builder make an architectural decision not in the artifacts?** If the code introduces a pattern, abstraction, or structural choice not described in `build-plan.md` or the other artifacts, that's **BLOCKING**. The planning phase was insufficient — flag as `artifact_insufficiency` observation.
- **Did the Builder add functionality not in the chunk's deliverables?** Extra features, even useful ones, are **WARNING**. The build plan defines what gets built; additions should go through the Orchestrator.

### Review Cycle

1. Builder marks chunk status as "review" in `project-state.yaml`.
2. Critic runs all three checks: Spec Compliance → Test Integrity → Scope Violation.
3. **If BLOCKING findings exist:**
   - Builder fixes the issues.
   - Critic re-reviews — specifically watching for **fix-by-fudging**:
     - Weakening a test to make it pass instead of fixing the code → **BLOCKING**
     - Changing a spec to match wrong implementation instead of fixing the code → **BLOCKING**
     - Adding a workaround instead of addressing root cause → **WARNING**
   - Repeat until no blocking findings remain.
4. **If no BLOCKING findings:** chunk status → "complete", proceed to next chunk.

### Output Format

```
## Product Governance Review — Chunk [ID]: [Name]

### Spec Compliance
[Checklist table]

### Test Integrity
- Test count: [before] → [after] [PASS/FAIL]
- Test files deleted: [none / list] [PASS/FAIL]
- New tests added: [count] [PASS/WARNING]
- Behavior vs. implementation testing: [assessment]
- Error case coverage: [assessment]

### Scope Violation
- Unlisted dependencies: [none / list]
- Unspecified patterns: [none / list]
- Extra functionality: [none / list]

### Findings

#### [Finding Name]
**Check:** [Spec Compliance | Test Integrity | Scope Violation]
**Severity:** blocking | warning | note
**Description:** [Specific observation]
**Recommendation:** [What the Builder should do]

### Summary
[Total findings by severity. Whether the chunk passes review.]
```

### Recording Reviews

After each review cycle, update `project-state.yaml` → `build_state.reviews` with:
```yaml
- chunk_id: "[current chunk]"
  findings:
    - description: "[finding]"
      severity: blocking | warning | note
      status: open | resolved | deferred
```

## Extending This Skill

Remaining governance sub-components and enhancements are tracked in `project-state.yaml` → `build_plan.remaining_work`.

When adding new product governance checks:
1. Add a "Check N: [Name]" section under Mode 2, following the pattern of Checks 1-3.
2. Define mechanical checks (binary pass/fail) separately from judgment checks.
3. Add the check to the Review Cycle (step 2).
4. Update the Output Format template to include the new check's section.

When adding new framework governance checks:
1. Add a "Check N: [Name]" section under Mode 1, following the pattern of Checks 1-7.
2. Update `tools/record-critic-findings.sh` REQUIRED_CHECKS array to include the new check name.
3. Update the commit gate expectations if the check changes what should block commits.
