# Skill Authoring Guide

This document codifies structural and health standards for writing LLM skill instructions. Every standard includes a concrete test and provenance linking it to external best practices. Skills are the framework's primary interface — their clarity directly determines output quality.

**Last external review:** 2026-02-12

---

## Structural Standards

These standards govern how instructions are written within skills. Violations reduce LLM instruction-following accuracy.

### S1: Decision Trees as Numbered Steps, Not Prose

When a skill requires choosing between 3+ conditions, present them as a numbered decision tree with one condition per step. Stop at the first match.

**Test:** 3+ conditions in one paragraph = violation.

**Why:** LLMs follow numbered steps more reliably than parsing branching logic from prose. Prose conditionals create ambiguity about evaluation order and mutual exclusivity.

**Derived from:** [Anthropic: Be clear and direct](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/be-clear-and-direct) — "Provide instructions as sequential steps"

**Example violation:**
> If the file exists and the user wants X, do A, but if the file exists and they want Y, do B, unless no file exists in which case check whether Z applies and if so do C, otherwise ask.

**Example fix:**
> 1. Does the file exist?
>    a. YES + user wants X → Do A.
>    b. YES + user wants Y → Do B.
> 2. No file + Z applies → Do C.
> 3. None of the above → Ask the user.

### S2: Define All Thresholds Concretely

Every threshold, boundary, or size classification must have a concrete definition. No subjective adjectives without measurable criteria.

**Test:** Subjective adjective (e.g., "small," "large," "clearly," "significant") used as a decision criterion without a concrete definition = violation.

**Why:** Two LLMs interpreting "small change" differently will produce different behavior. Concrete thresholds produce consistent decisions.

**Derived from:** [Anthropic: Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — "Be specific about what you want"

**Example violation:**
> If the scope change is small, update and proceed. If it's large, discuss with the user.

**Example fix:**
> Small scope change (affects 1-2 artifacts and ≤1 chunk): update and proceed. Large scope change (affects 3+ artifacts or requires new chunks): discuss with the user.

### S3: Separate Concerns with Structural Markers

Each section header should describe one coherent concern. If a section header could be split into 2+ independent headers without losing meaning, the section mixes concerns.

**Test:** Section header splittable into 2+ independent headers = violation.

**Why:** Mixed-concern sections bury instructions. LLMs scan section headers to locate relevant context; instructions in the wrong section are effectively invisible.

**Derived from:** [Anthropic: Chain complex prompts](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/chain-prompts) — "Break complex tasks into subtasks"

**Example violation:**
> ## Build Loop
> [per-chunk cycle, governance checkpoints, pacing rules, and completion sequence all in one section]

**Example fix:**
> ## Per-Chunk Execution
> [the 7-step cycle]
> ## Governance Checkpoints
> [when and what to check]
> ## Build Pacing
> [risk-proportionate interaction rules]
> ## Build Completion
> [post-all-chunks sequence]

### S4: Structural Demarcation for Critical Rules

Non-negotiable rules, invariants, and hard constraints must be visually distinct from surrounding instructions. Use bold markers, dedicated subsections, or equivalent structural emphasis.

**Test:** A rule described as "MUST," "NEVER," "CRITICAL," or "non-negotiable" that appears inline within a regular paragraph without structural emphasis = violation.

**Why:** Critical rules buried in prose are easily overlooked during instruction-following. Structural separation signals importance and aids scanning.

**Derived from:** [Anthropic: Use XML tags](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags) — structural separation for clarity

### S5: Context Alongside Instructions

Every non-obvious instruction should include a brief explanation of why it exists. "Do X because Y" is more reliably followed than "Do X."

**Test:** An instruction that a reasonable reader would ask "why?" about, without an accompanying rationale = violation. Instructions that are self-evidently necessary (e.g., "save the file") are exempt.

**Why:** LLMs with context about the purpose of an instruction apply it more accurately to edge cases. Without "why," the instruction becomes a memorized rule that breaks when conditions vary.

**Derived from:** [Anthropic: Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — "Providing context helps Claude understand the deeper intent"

### S6: No Internal Contradictions

When different sections of a skill prescribe different behavior for what appears to be the same situation, the skill must include an explicit resolution at the boundary explaining why the difference exists.

**Test:** Two sections that could be read as contradicting each other, without an explicit note explaining the difference = violation.

**Why:** LLMs resolve contradictions unpredictably. Explicit resolution ensures consistent behavior.

**Derived from:** [Anthropic: Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — "Be explicit, define all terms, no contradictions"; also the framework's own Critic Check 8 (Instruction Clarity)

**Example violation:**
> Stage 2: "Skip formal lens review for low-risk products."
> Stage 3: "Review Lenses MUST run in all cases."

**Example fix:**
> Stage 2: "Skip formal lens review for low-risk products at this stage — the definition is lightweight and the full artifact review in Stage 3 will catch issues."
> Stage 3: "Review Lenses MUST run in all cases. (Stage 2 skips lenses for low-risk because the *definition* is lightweight. Stage 3 always runs lenses because *generated artifacts* feed downstream build — errors here propagate to code. Different stages, different quality gates.)"

---

## Health Standards

These standards govern the overall condition of a skill file. They are evaluated holistically, not per-instruction.

### H1: Length Proportionality

A skill's length should be proportionate to its responsibility scope.

| Scope | Guideline |
|-------|-----------|
| Focused (single concern, e.g., Review Lenses) | 100-200 lines |
| Moderate (multi-step process, e.g., Artifact Generator) | 200-400 lines |
| Complex (full lifecycle management, e.g., Orchestrator) | 300-600 lines |

**Test:** A skill exceeding its scope guideline by >25% should be reviewed for redundancy, buried instructions, or mixed concerns (S3). A skill under its guideline is not a problem — brevity is a feature.

**Why:** Overly long skills dilute instruction density. Critical instructions compete for attention with less important ones.

**Derived from:** [Lakera Prompt Engineering Guide](https://www.lakera.ai/blog/prompt-engineering-guide) — prompt length vs. instruction-following accuracy tradeoff; [Palantir LLM Best Practices](https://www.palantir.com/docs/foundry/aip/best-practices-prompt-engineering) — conciseness principle

### H2: Voice Consistency

Instructions should be consistently imperative ("Do X," "Check Y," "If Z, then W"). Descriptive voice ("The system does X," "This skill handles Y") should appear only in context/purpose sections, not in procedural instructions.

**Test:** Descriptive statements in procedural sections (steps, checklists, decision trees) = violation. Imperative statements in context sections are acceptable.

**Why:** Voice shifts signal ambiguity about whether something is an instruction to follow or a description of what happens. LLMs may treat descriptive statements as context rather than directives.

### H3: Cross-Section Consistency Audit

When modifying a skill, search for contradictions, redundancy, and orphaned references across all sections — not just the section being changed.

**Test:** After any modification, can you find two sections that now say different things about the same topic without explicit resolution? = violation (S6). Can you find the same instruction stated in two places? = redundancy warning. Can you find a reference to a section, field, or concept that no longer exists? = orphan.

**Why:** Skills accumulate changes over time. Each individual change may be sound, but their aggregate can create contradictions and redundancy that individual reviews miss.

---

## Using This Guide

**During skill creation:** Apply all standards. New skills should start clean.

**During skill modification:** Apply S1-S6 to the modified section. Apply H3 (cross-section audit) to the full skill. Check H1 if the modification adds significant content.

**During Critic Check 8 (Instruction Clarity):** Reference S1, S2, and S6 specifically — these are the most commonly violated standards.

**During evaluation (step 2b):** Use S1-S6 as a checklist for skill instruction quality assessment.

**During external practice review:** Compare standards against current external research. Update provenance links. Add new standards if research identifies patterns not covered.
