# Critic: Framework-Only Checks (7-10)

These checks apply only when reviewing skill files, template files, or framework structural decisions. They are loaded on demand — product builds that don't modify framework files skip them entirely.

---

### Check 7: Generality

**Applies:** When reviewing skill files, template files, or framework structural decisions. Also applies when `classification.domain_characteristics` indicates an LLM instruction framework.

**Principle:** Generality Over Enumeration (`docs/principles.md`)

**Ask:** Does this change work for products the framework has never seen?

- If a modification adds a specific concern as an enumerated item rather than strengthening the dynamic generation system, it fails this check.
- If a modification strengthens a general principle or structural amplification rule so the LLM naturally surfaces the concern for any relevant product, it passes.
- **Test:** Mentally apply the modified skill to three very different products. Does the modification help with all three, or only the product that triggered it?
- **Plan-level generality:** When reviewing design plans, working notes, or proposed approaches (not just skill file changes): mentally apply the planned approach to three very different products (e.g., a web app, a CLI tool, and firmware). Does the approach help all three, or does it assume one product type? Plans that name a specific technology as *the* solution where a general principle would serve better fail this check — the technology should be positioned as one implementation of the general principle.

**Severity guide:**
- Enumerated concern that doesn't generalize → **blocking**
- Plan that assumes one product type where a general principle would serve better → **warning**
- General principle worded to favor one product type → **warning**
- Slight specificity that doesn't harm generality → **note**

### Check 8: Instruction Clarity

**Applies:** When reviewing skill files (files that contain LLM instructions).

**Principle:** Skills are LLM instructions, not descriptions.

**Ask:** Would an LLM following these instructions produce the intended behavior?

- Instructions should be imperative ("do X") not descriptive ("the system does X").
- Instructions should be unambiguous — if two reasonable LLMs might interpret differently with meaningfully different outputs, it's unclear.
- Instructions should not contradict each other within or across skills.
- Check for S1 violations (multi-level conditionals in prose), S2 violations (subjective thresholds without concrete definitions), and S6 violations (unresolved contradictions).

**Severity guide:**
- Ambiguous instruction that could produce wrong behavior → **warning**
- Structural standard violation (S1, S2, S6) → **warning**
- Slightly unclear wording, unlikely to cause problems → **note**

### Check 9: Cumulative Health

**Applies:** When reviewing skill files (substantial modifications, not typos/formatting).

**Principle:** Skills accumulate changes. Individual changes may each be sound, but their aggregate can degrade instruction quality.

**Ask:** Is this skill, as a whole, still clear, proportionate, and internally consistent?

**What to evaluate:**
- **Length proportionality:** Is the skill proportionate to its responsibility?
- **Voice consistency:** Are instructions consistently imperative throughout?
- **Structural clarity:** Are conditions and decisions easy to scan?
- **Cross-section consistency:** Do different sections contradict each other?

**Severity guide:**
- Sections contradict each other → **warning**
- Key instructions buried in paragraphs → **warning**
- Voice inconsistency within the same section → **note**
- Overall length growing without clear justification → **note**

### Check 10: Pipeline Coverage

**Applies:** When a new artifact template, discovery dimension, Critic check, or Review Lens is added or substantially modified.

**Principle:** Cross-cutting concerns should have complete pipeline coverage — discovery surfaces them, artifacts specify them, the Builder implements them, the Critic validates them, and Review Lenses evaluate them.

**Ask:** Is the pipeline complete for the concern this change addresses?

- Does the concern have discovery questions that surface it during Stages 0-1?
- Does at least one artifact template specify it?
- Does the Builder have instructions for implementing it?
- Does the Critic have a check that validates it?
- Does at least one Review Lens evaluate it?
- Is the concern registered in `.prawduct/artifacts/cross-cutting-concerns-registry.md`?

If any dimension is missing, flag it as a warning. The registry should be updated to reflect the new coverage.

**Severity guide:**
- New artifact/dimension with no corresponding Critic check or Review Lens → **warning**
- Concern not registered in the cross-cutting concerns registry → **warning**
- Minor coverage gap in a non-critical dimension → **note**
