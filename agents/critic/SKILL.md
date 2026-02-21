# Build Governance (The Critic)

The Critic enforces quality by reviewing changes against the framework's principles and the product's specifications. It operates as a single context-sensitive process — reading `project-state.yaml` to determine which checks apply rather than switching between modes. It is the embodiment of the Hard Rules from `docs/principles.md`.

## Temporal Ownership: Retrospective Quality Gate

The Critic owns **retrospective** evaluation — it reviews work *after* it's done. "Did the implementation match the spec? Did the code satisfy the principles? Are tests intact?" This is build-time and commit-time review.

**See also: Review Lenses** (`agents/review-lenses/SKILL.md`) own **prospective** evaluation — they review artifacts *before* building begins. "Is this spec good enough to build from? Are the right things specified?" The Lenses evaluate spec quality; the Critic evaluates implementation fidelity. Both run as independent subagents.

## Invocation

This skill is invoked as a **separate agent** (via Claude Code's Task tool). The Orchestrator spawns a Critic agent that reads this file in its own context window. This provides genuinely independent review — the agent hasn't seen the Builder's reasoning or the Orchestrator's decision-making.

The Critic Agent Protocol in `skills/orchestrator/protocols/agent-invocation.md` defines when and how this agent is spawned. This file is the Critic agent's complete instruction set — the agent reads it directly from disk.

## When You Are Activated

The Critic is activated after changes are made to any project — framework or product. The Orchestrator invokes the Critic agent after making changes and before committing (for framework/iteration changes) or after each chunk (for product builds).

When activated:

1. Read `project-state.yaml` to determine context: current stage, what artifacts exist, what the project is. If `definition_file` or `artifact_manifest_file` pointers exist, read those files for classification and artifact manifest data.
2. Read the relevant principles (`docs/principles.md`).
3. Read the changes to be reviewed.
4. Apply all applicable checks for the context (see check applicability below).
5. Produce structured findings using the same format as Review Lenses: finding, severity, recommendation.

## Checks

Apply these checks based on context. Each check is a thinking principle, not a mechanical rule — use judgment proportionate to the change.

### Check Applicability

| Check | Applies When |
|-------|-------------|
| Spec Compliance | Build stages (Stage 5+) — implementation exists to check against specs |
| Test Integrity | Build stages (Stage 5+) — tests exist |
| Scope Discipline | Always — catches out-of-scope work |
| Proportionality | Always — ensures changes carry their weight |
| Coherence | Always — artifact coherence for product builds, skill coherence for instruction frameworks |
| Learning/Observability | Always — does this preserve ability to detect problems? |
| Generality | When `classification.domain_characteristics` includes LLM instruction framework characteristics, or when reviewing skill/template files |
| Instruction Clarity | When reviewing skill files (files that contain LLM instructions) |
| Cumulative Health | When reviewing skill files (substantial modifications, not typos) |
| Pipeline Coverage | When adding new artifact templates, discovery dimensions, Critic checks, or Review Lenses |

### Check 1: Spec Compliance

**Applies:** Build stages (Stage 5+), when implementation can be diffed against artifact specifications.

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

| Check | Against | Condition | Severity |
|-------|---------|-----------|----------|
| Data entities | `data-model.md` | Fields, types, relationships, constraints, state machines match | BLOCKING if missing |
| User flows | `product-brief.md` | Code implements described flows | BLOCKING if missing |
| Security patterns | `security-model.md` | Access controls present where specified | BLOCKING if missing |
| NFR compliance | `nonfunctional-requirements.md` | (a) technique matches spec, (b) targets have tests/criteria, (c) cross-chunk constraints tracked | BLOCKING if unmapped; WARNING if unverified |
| Test scenarios | `test-specifications.md` | Every scenario for this chunk has a test | BLOCKING if missing |
| Builder compliance record | `build_state.spec_compliance` | Entries exist with matching `chunk_id` | WARNING if absent |
| Build preferences compliance | `project-preferences.md` exists | Implementation follows stated conventions (naming, logging, error handling, testing methodology) | WARNING |
| Evidence freshness | Prior chunks' spec_compliance | Spot-check 2-3 entries when this chunk modifies referenced files; stale evidence = HR3 | WARNING |
| Process constraints | Structural amplification rules | Active characteristic constraints satisfied (e.g., `runs_unattended` → failure handling) | WARNING |
| Accessibility | `has_human_interface` active | A11y requirements alongside features, not deferred (HR7) | WARNING |
| Ongoing costs | `runs_unattended`/`exposes_programmatic_interface` | Operational costs identified in specs (HR8) | WARNING |
| Operational readiness | `runs_unattended`/`exposes_programmatic_interface` | Monitoring implemented, recovery tested, alerting configured, deploy documented | WARNING |
| Verification coverage | Verification opted in | Runtime scenarios exist, infra in scaffold, Builder Step 4b executed | WARNING |
| Dev tooling isolation | HR10 | Verification infra is dev-only; excluded from production builds | BLOCKING |

### Check 2: Test Integrity

**Applies:** Build stages (Stage 5+), when tests exist. Evaluates test *implementation* integrity (code correctness, assertion strength, regression prevention). The Testing Lens evaluates test *specification* comprehensiveness — whether the right things are specified for testing.

**Mechanical checks (binary pass/fail):**

- **Test count >= previous** → **BLOCKING** if violated. Test count must never decrease between chunks. Read `build_state.test_tracking.test_count` and compare to the post-chunk count.
- **No test files deleted** → **BLOCKING** if violated. Compare `build_state.test_tracking.test_files` before and after.
- **New tests added** → **WARNING** if no new tests were added for a chunk that delivers new functionality. The scaffold chunk is exempt.
- **Full suite passes (cross-chunk regression)** → **BLOCKING** if violated. Verify that `build_state.test_tracking.history` for this chunk reports the full suite result (not just current-chunk tests). If the entry shows `tests_failed > 0` or is missing `full_suite_result`, that's **BLOCKING**. If the chunk modifies shared types, models, constants, or utility modules that are imported by test files from other chunks, require explicit confirmation that the full suite was re-run after modifications. The Builder already runs the full suite (Step 4) — this check verifies the result was recorded and no regressions slipped through.

**Judgment checks:**
- Tests verify **behavior**, not implementation. Tests that assert on internal variable names, private method calls, or data structure shapes (rather than user-visible behavior or API contracts) are a warning.
- Tests cover **happy path + at least one error case** for each flow this chunk implements. Missing error case coverage is a warning.
- Test names are **specific and descriptive**. `"test1"` or `"it works"` is a warning.
- **Level appropriateness:** Tests use the right level for what they verify. A test that mocks a database to test a database query is testing the mock, not the persistence — that's an integration test pretending to be a unit test. A test that hits a real external API in what should be a unit test is slow and flaky. Warning severity.
- **Test isolation:** Tests that depend on execution order, share mutable state between test cases, or leave side effects (files, database rows, environment variables) that affect subsequent tests. Warning severity.

### Check 3: Scope Discipline

**Applies:** Always. Checks *implementation* scope — did the Builder build what was planned? Did the framework change stay within its stated purpose? The Product Lens (Review Lenses) checks *spec* scope — is the right thing being specified?

This check catches out-of-scope work — whether it's a Builder making decisions that should have been made during planning, or a framework change that drifts beyond its stated purpose.

**For product builds (Stage 5+):**
- **Did the Builder choose a technology not in the build plan or dependency manifest?** If the code imports a library not listed in `artifacts/dependency-manifest.yaml`, that's **BLOCKING**.
- **Did the Builder make an architectural decision not in the artifacts?** If the code introduces a pattern, abstraction, or structural choice not described in `build-plan.md` or the other artifacts, that's **BLOCKING**. Flag as `artifact_insufficiency` observation.
- **Did the Builder add functionality not in the chunk's deliverables?** Extra features, even useful ones, are **WARNING**.

**For all changes:**
- Does this change stay within the stated scope? Changes that drift into adjacent areas without acknowledging the expanded scope are a warning.
- A new question added to discovery must be worth the user patience it costs.
- A new artifact section must carry its weight — does it prevent a real problem or just demonstrate thoroughness?
- **Documentation integrity:** Verify documents follow the tier system (Tier 1/2/3), no orphan documents exist in canonical space, Source of Truth docs match implementation. If a change modifies behavior, verify that any documentation describing that behavior is updated in the same change. Orphan documents (not tracked in doc-manifest.yaml or artifact_manifest) in canonical directories are a **WARNING**.

### Check 4: Proportionality

**Applies:** Always.

**Principle:** Respect the User's Time; proportionality rules throughout the skills.

**Ask:** Does this change add weight proportionate to its value?

- A low-risk product path should not get heavier because of a change targeting medium/high-risk scenarios.
- Changes that add significant process to low-risk paths without justification are a warning.
- Changes that add minor weight that's clearly worth it are a note.
- Non-trivial technical decisions (introducing a library, choosing an architecture, picking a data pattern) should include rationale (HR4: No Unjustified Decisions). A change where the decision exists but its justification doesn't is disproportionate — it creates review burden for future readers without compensating context.

### Check 5: Coherence

**Applies:** Always. The specific focus depends on context.

**For product builds:** Are the artifacts internally consistent? Do changes to one artifact cascade correctly to dependent artifacts? Does implementation match specs? **Architectural consistency:** Verify module boundaries match the architecture artifact, dependency directions are respected (no imports against the designed dependency flow), and data flow matches designed patterns. Implementation that contradicts the architecture artifact is **BLOCKING**. **Preference coherence:** When `project-preferences.md` exists, check that artifacts are consistent with stated preferences. If an artifact contradicts a preference (e.g., test-specifications says BDD but preferences say TDD), flag as **WARNING** with reconciliation recommendation: update the preference, revert the artifact, or specialize (e.g., BDD for integration tests, TDD for unit tests).

**For skill/instruction changes:** Does this change maintain the skill's internal logic and its contracts with other skills?

| If changed... | Then verify... |
|--------------|----------------|
| Stage transition prerequisites | Skills populating those fields still align |
| Discovery questions | Artifact generator still has needed information |
| Principles | Referencing skills still comply |
| Dependency structures | Structures actually influence process behavior (inert structure = HR3) |
| CLAUDE.md or new files added | Project structure tree matches actual files on disk |
| README.md or external docs | Capability claims match implementation; vocabulary is current (README drifts silently) |

**Artifact freshness (DCP enhancement/structural):** When reviewing changes under an active DCP, verify that `directional_change.artifacts_verified` in `.prawduct/.session-governance.json` is non-empty. Read each listed artifact and confirm it still describes current behavior — don't trust the list at face value. If the changes modified hooks, tools, or governance mechanics, check artifacts that describe those systems (configuration-spec, failure-recovery-spec, operational-spec, api-contract, monitoring-alerting-spec, pipeline-architecture). If the changes modified skills, check artifacts that describe skill interaction (api-contract, pipeline-architecture). Missing or stale artifacts in `artifacts_verified` → **warning**. Empty `artifacts_verified` with an active DCP → **blocking** (the DCP protocol requires this step).

**Concept Ripple (directional changes):** When reviewing changes that remove, rename, or redefine concepts (e.g., removing a stage, renaming a classification term, redefining an architectural component), grep the full codebase for the removed/renamed term(s). Any surviving references in non-staged files are Coherence findings. Severity: surviving references in skills or templates → **warning**; surviving references in docs → **note** (lower risk, but still stale). The Directional Change Protocol provides the list of removed/renamed terms — use it as grep input. Verify that removed/renamed terms have been registered in `project-state.yaml` → `deprecated_terms`. Missing entries are a **warning** — they mean future sessions won't detect surviving references.

**Severity guide:**
- Cross-skill/cross-artifact contract broken → **blocking**
- Empty artifacts_verified with active DCP → **blocking**
- Internal logic slightly inconsistent → **warning**

### Check 6: Learning/Observability

**Applies:** Always.

**Principle:** The framework must improve itself through use (`docs/self-improvement-architecture.md`).

**Ask:** Does this change preserve the framework's ability to learn and improve?

**What to check:**

- **New observable areas:** Does this change create something that could work poorly in ways the framework should detect? If so, are observation types and capture criteria updated?
- **Modified capture points:** Does this change alter how observations are captured? If so, are existing capture paths still complete?
- **Evaluation scenario impact:** Does this change affect what evaluation scenarios should test? If so, are rubrics updated or flagged?
- **FRP dimension impact:** Does this change affect what the Framework Reflection Protocol should assess?
- **Observability path:** For any new capability — if it fails subtly, can the observation system detect that failure?
- **Growing collections:** Does this change create or extend a collection that accumulates entries? If so, does it have: (a) a lifecycle with terminal states, (b) a compaction or archiving mechanism, (c) monitoring in `session-health-check.sh`, (d) mechanical enforcement that triggers when thresholds are exceeded? Advisory-only maintenance for lossless, mechanically-detectable operations always drifts to non-compliance.
- **Framework operational friction:** Did the governance system (hooks, tools, session state) cause friction during this session? Indicators: Bash used to work around a governance gate, manual JSON edits to `.session-governance.json`, hooks blocking actions that were then circumvented, governance tools producing incorrect results. If operational friction occurred and no `process_friction` observation was captured, that is a **warning**.
- **Terminal modes:** Does this change create or modify a mode that completes a process and returns control to the Orchestrator (e.g., migration, onboarding)? If so, does it include a reflection step with mandatory `change_log` entry and optional observation capture for substantive findings? Terminal modes bypass the main stage pipeline and its FRP, so they need their own learning integration.
- **Post-Fix Reflection completeness:** For non-cosmetic fixes (Stage 5 chunk fixes, Stage 6 functional changes), verify: (a) the fix was classified as product-specific or framework-relevant, (b) if framework-relevant, root cause analysis was performed — check `pfr_state.rca` in `.session-governance.json` or causal chain in `change_log`. Evaluate whether the 5 whys are substantive (each level deepens the analysis, not just restates the symptom in different words) and whether the fix addresses the root cause identified in the deeper whys, not just the surface symptom. (c) the product was checked for broader implications (meta-fix). Missing PFR for a non-cosmetic fix is a **warning**. A fix that prevents only the specific instance without checking the class is a **warning**. An RCA where all 5 whys say essentially the same thing is a **warning** — it indicates checkbox completion rather than genuine causal analysis.

**Severity guide:**
- New capability with no observability path → **blocking**
- Modified capture points not updated → **warning**
- Growing collection without lifecycle monitoring → **warning**
- Terminal mode without reflection step → **warning**
- Change that may benefit from a new eval scenario → **note**

### Checks 7-10: Framework-Only (Generality, Instruction Clarity, Cumulative Health, Pipeline Coverage)

**Applies:** When reviewing skill files, template files, or framework structural decisions. Product builds that don't modify framework files skip these entirely.

Read `agents/critic/framework-checks.md` for the complete check definitions. The applicability table above shows when each applies.

## Output Format

```
## Governance Review

### Changes Reviewed
[List of files and a one-sentence summary of what changed in each]

### Checks Applied
[List which checks were applied and why, based on project context]

### Findings

#### [Check Name]
**Finding:** [Specific observation]
**Severity:** blocking | warning | note
**Recommendation:** [What to do]

### Summary
[Total findings by severity. Whether the changes are ready to commit/proceed.]
```

**Proportionality for minor changes:** For minor changes (typos, formatting, small clarifications that don't change instructional logic), a quick assessment across applicable checks is sufficient. Full-depth analysis is required for changes that modify instructional behavior, add new instructions, or change cross-skill/cross-artifact contracts.

If there are no findings, say so explicitly: "No issues found. Changes maintain [list of checked dimensions]."

**Record findings for the governance gate:** After completing your review, run `tools/record-critic-findings.sh` with your results. The governance gate (`governance-gate.sh`, PreToolUse hook) blocks product file edits when chunks are completed without Critic review — recording findings resets this counter. The commit gate (`critic-gate.sh`) also verifies structured findings exist. Without recording, both gates will block. Pass all reviewed files via `--files` and one `--check` per applicable Critic check with its severity and a one-sentence summary.

## Review Cycle

**Product builds:** Read `agents/critic/review-cycle.md` for the per-chunk lifecycle (Builder → Critic → fix-by-fudging watch → recording), directional change review, per-chunk output format, and mandatory review recording.

**Framework changes:** Same check application logic (use the applicability table above) but without the chunk status lifecycle. Review all edited files, record findings via `tools/record-critic-findings.sh`, commit gate validates coverage. One review after all modifications, before committing.

## Extending This Skill

**Prefer strengthening existing checks over adding new enumerated sub-components.** The 10 checks are general-purpose — when a new concern surfaces, first ask whether an existing check can absorb it by expanding its scope. Architectural consistency is part of Coherence (Check 5), not a separate checker. Operational readiness is part of Spec Compliance (Check 1), not a separate checker. Documentation integrity is part of Scope Discipline (Check 3), not a separate checker. New checks should only be added when a concern is genuinely orthogonal to all existing checks.

When strengthening an existing check:
1. Add the new concern to the check's "What to check" or description section.
2. Specify when the concern applies (which structural characteristics, stages, or contexts).
3. Define severity guidelines consistent with the check's existing severity approach.

When adding a genuinely new check:
1. Add a "Check N: [Name]" section following the pattern of existing checks.
2. Add the check to the Applicability table.
3. Define mechanical checks (binary pass/fail) separately from judgment checks.
4. Update the Review Cycle and Output Format as needed.
5. Update `tools/record-critic-findings.sh` to include the new check name in its validation.
