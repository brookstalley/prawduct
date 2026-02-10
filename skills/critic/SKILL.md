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

**Severity guide:**
- Cross-skill contract broken → **blocking**
- Skill's internal logic slightly inconsistent → **warning**

#### Check 5: Instruction Clarity

**Principle:** Skills are LLM instructions, not descriptions

**Ask:** Would an LLM following these instructions produce the intended behavior?

- Instructions should be imperative ("do X") not descriptive ("the system does X").
- Instructions should be unambiguous — if two reasonable LLMs might interpret the instruction differently and produce meaningfully different outputs, it's unclear.
- Instructions should not contradict each other within or across skills.

**Severity guide:**
- Ambiguous instruction that could produce wrong behavior → **warning**
- Slightly unclear wording, unlikely to cause problems → **note**

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

If there are no findings, say so explicitly: "No issues found. Changes maintain generality, completeness, proportionality, coherence, and clarity."

## Mode 2: Product Governance

*Phase 2 — not yet implemented.* This mode reviews implementation of user products against their specifications during the Build + Governance Loop (Stage 5).

When implemented, it will include the sub-components defined in `docs/high-level-design.md`:

- [ ] Spec Compliance Auditor — diff implementation against specification
- [ ] Test Integrity Checker — monitor for corruption patterns (HR1)
- [ ] Architectural Consistency Checker — validate against architecture artifact
- [ ] Documentation Controller — enforce tier system, prevent orphans
- [ ] Operational Readiness Checker — verify monitoring, recovery, alerting

The review cycle (defined in the HLD) watches specifically for "fix-by-fudging":
- "Fixing" by weakening the check instead of fixing the code
- "Fixing" by changing the spec to match the (wrong) implementation
- "Fixing" by adding a workaround rather than addressing root cause

## Extending This Skill

- [x] Framework Governance: generality, read-write chains, proportionality, coherence, clarity (Phase 2 start)
- [ ] Product Governance: spec compliance + test integrity (Phase 2)
- [ ] Product Governance: architectural consistency (Phase 2)
- [ ] Product Governance: documentation controller (Phase 2)
- [ ] Product Governance: operational readiness (Phase 2)
- [ ] Integration with Review Lenses: Critic findings feed back to Lenses for pattern detection (Phase 2)
- [ ] Mechanical enforcement via tools/ scripts for checks that can be automated (Phase 2)
