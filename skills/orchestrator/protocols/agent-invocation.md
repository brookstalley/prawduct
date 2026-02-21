# Orchestrator: Agent Invocation Protocols

Protocols for spawning subagents via Claude Code's Task tool (`subagent_type: "general-purpose"`). Each agent reads its own SKILL.md in a separate context window, providing independent review/generation.

---

## Shared Agent Conventions

These conventions apply to all agent invocations below unless explicitly overridden.

**Model:** Always use the best available model. Do not specify a downgraded model (e.g., `model: "haiku"`). Omit the `model` parameter to inherit the parent's model.

**Role boundary:** Every agent has a defined scope. Read-only agents (Critic, Review Lenses, Observation Triage) must NOT edit files, create commits, push to remote, or make changes — they report findings for the Orchestrator to act on. Include the tool whitelist in the prompt: "You must ONLY use Read, Glob, Grep, and Bash (for recording tools)."

**Prompt structure:** Every agent prompt must include:
1. Role statement with scope constraints
2. Instructions source (which SKILL.md to read)
3. Project context (paths, stage, files changed, product characteristics)
4. Specific task with output expectations

**Output verification:** After every agent returns, verify:
1. Evidence file exists on disk (findings JSON, artifacts, etc.)
2. Coverage is complete (all requested files/lenses/checks appear)
3. Findings are substantive (not rubber-stamp "pass" without analysis)

**Fallback:** If verification fails, re-invoke once with explicit note about what was incomplete. If it fails again, conduct an in-context review as fallback (read the agent's SKILL.md and apply checks manually).

---

## Critic Agent Protocol

### When to invoke

- **Stage 5 per-chunk:** After each chunk (step 5 of the per-chunk cycle)
- **Stage 6 iteration:** After every file change before committing
- **DCP Enhancement:** Step 4 (after implementation)
- **DCP Structural:** Step 4 (plan-stage review — Generality + Coherence + Learning/Observability only) and Step 8 (final full review)
- **Build completion:** Full product governance review (Stage 5 completion step 1)

### Agent prompt

**Role boundary: The Critic agent is read-only.** (See Shared Agent Conventions above.)

Include these elements in the Task tool prompt:

1. **Role and constraints:** "You are the Critic for a Prawduct governance review. Your role is strictly read-only: review, analyze, and record findings. Do NOT edit files, fix issues, create commits, push to remote, or make any changes to the codebase. If you find issues, report them in your findings — the Orchestrator decides what to fix. You must ONLY use Read, Glob, Grep, and Bash (for `tools/record-critic-findings.sh`) tools."
2. **Instructions source:** "Read `agents/critic/SKILL.md` for your complete check definitions, applicability table, and output format."
3. **Project context:**
   - Project directory path
   - Product root (`.prawduct/`) path
   - Current stage
   - Files changed in this review (list relative paths)
   - One-sentence summary of what was changed and why
4. **Accepted context** (prevents false positives): Any user-approved tradeoffs, design decisions explicitly discussed, or scope decisions from this session. Keep brief — 2-3 sentences max. If none, say "No special tradeoffs."
5. **Task:** "Apply all applicable checks per the applicability table. Run `tools/record-critic-findings.sh` with your findings (--files for all reviewed files, --check for each applicable check). Return a structured summary in the Critic output format."

**Canonical example invocation:**

```
Task(subagent_type="general-purpose", prompt="""
You are the Critic for a Prawduct governance review.
Your role is strictly read-only: review, analyze, and record findings.
Do NOT edit files, fix issues, create commits, push to remote, or make
any changes. Only use Read, Glob, Grep, and Bash (for record-critic-findings.sh).

Read agents/critic/SKILL.md for your complete check definitions, applicability table,
and output format. Read docs/principles.md for the Hard Rules.

Project: /path/to/project
Product root: /path/to/project/.prawduct
Stage: iteration
Files changed:
- skills/orchestrator/protocols/agent-invocation.md
- skills/orchestrator/stage-5-build.md
- CLAUDE.md

Change summary: Moved Critic invocation from in-context skill loading to subagent model.
Accepted tradeoffs: None — this is a straightforward architectural change.

Apply all applicable checks per the applicability table. Run
tools/record-critic-findings.sh with your findings. Return your full review.
""")
```

### Output verification

After the agent returns, verify these four conditions:

1. **Evidence exists:** `.prawduct/.critic-findings.json` was created or updated.
2. **File coverage:** `reviewed_files` in the findings includes all files listed as changed.
3. **Substantiveness:** At least one check has a summary longer than 5 words.
4. **Check count:** `total_checks >= 4` (the minimum always-applicable checks).

### Acting on findings

- **Blocking:** Must be resolved before proceeding. Fix the issues, then re-invoke the Critic agent for the changed files.
- **Warning:** Note them. Fix quick ones, track others in `build_state.reviews`.
- **Note:** Informational. No action required unless they accumulate.
- **No findings:** Proceed. Record the clean review.

### Governance tracking

After the Critic agent completes successfully:
- Update `.prawduct/.session-governance.json` → `governance_state.chunks_completed_without_review` to 0
- Set `last_critic_review_chunk` to current chunk name (Stage 5) or change description (Stage 6)
- The `record-critic-findings.sh` tool also resets the chunk counter automatically

---

## Review Lenses Agent Protocol

### When to invoke

- **Stage 2 (Definition):** Product, Design, Architecture, Skeptic lenses on crystallized decisions
- **Stage 3 Phase A:** Product and Design lenses on the Product Brief
- **Stage 3 Phase B:** Architecture lens on Data Model and NFRs
- **Stage 3 Phase C:** All five lenses on the complete artifact set
- **Stage 4:** Architecture and Skeptic lenses on the build plan
- **Stage 5 checkpoints:** Architecture, Skeptic, and Testing lenses on implementation
- **Stage 5 completion:** All five lenses on the complete implementation
- **Stage 6:** Product and Architecture lenses on change requests (as needed)

### Agent prompt

**Role boundary: The Lenses agent is read-only.** (See Shared Agent Conventions above.)

Include in the Task tool prompt:

1. **Role:** "You are the Review Lenses evaluator for a Prawduct quality review. Your role is strictly read-only: evaluate, analyze, and record findings. Do NOT edit files, fix issues, run git commands, or make any changes. Report findings — the Orchestrator handles fixes."
2. **Instructions source:** "Read `agents/review-lenses/SKILL.md` for your complete lens definitions, severity guide, and output format."
3. **Review context:** Project/product root paths, current stage and phase, which lenses to apply, artifact files to review, product characteristics summary.
4. **Task:** "Apply the specified lenses per the skill instructions. Run `tools/record-lens-findings.sh` with your findings. Return a structured summary."

Follow the canonical example pattern (Critic above), substituting: role → Lenses evaluator, SKILL.md → `agents/review-lenses/SKILL.md`, recording tool → `tools/record-lens-findings.sh`, context → artifacts to review + which lenses.

### Output verification

1. **Evidence exists:** `.prawduct/.lens-findings.json` was created or updated.
2. **Lens coverage:** All requested lenses appear in the findings.
3. **Substantiveness:** At least one lens has findings beyond "no issues."

### Acting on findings

- **Blocking:** Must resolve before proceeding to the next stage/phase.
- **Warning:** Address before delivery; doesn't block forward progress.
- **Note:** Informational. Consider but no required action.

---

## Observation Triage Agent Protocol

### When to invoke

- **Session resumption:** After the health check reports active observations (> 0 observation files in `.prawduct/framework-observations/`)
- **After Pattern Extractor:** When new pattern clusters are available
- **On user request:** When the user asks about observation status or priorities

### Agent prompt

Include in the Task tool prompt:

1. **Role:** "You are the Observation Triage agent. Your role is strictly read-only: read observation files, assess priorities, and return structured JSON recommendations. Do NOT write files, move observations, or update project-state.yaml."
2. **Instructions source:** "Read `agents/observation-triage/SKILL.md` for your complete triage rules, priority scoring, and output format."
3. **Paths:** Framework root, observation directory (`.prawduct/framework-observations/`), project state (`.prawduct/project-state.yaml`), pattern report (`.prawduct/.pattern-report.json` if exists), deferred backlog (`.prawduct/observation-backlog-deferred.yaml` if exists).
4. **Task:** "Read all active observation files, apply triage rules, and return a JSON object with archive_recommendations, priority_items, stale_backlog_entries, and summary."

### Output verification

1. **Valid JSON:** Output parses as JSON.
2. **Archive safety:** Every file in `archive_recommendations` exists on disk and all its entries have terminal status (`acted_on`, `wont_fix`, `duplicate`).
3. **Priority limit:** `priority_items` has at most 5 entries.
4. **File existence:** Every file referenced in `priority_items` exists on disk.

### Applying recommendations

- **Archive candidates:** Run `tools/update-observation-status.sh --archive-all` for each recommended file, or archive selectively.
- **Priority items:** Present the top items during session orientation as actionable work.
- **Stale backlog:** Mention stale entries and offer to re-evaluate or archive.

---

## Artifact Generator Agent Protocol

The Orchestrator spawns one AG agent per phase (A, B, C, D) rather than a single monolithic call. Between phases, the Orchestrator applies Review Lenses as a separate agent — agents do not invoke each other.

### When to invoke

- **Stage 3 (Artifact Generation):** One call per phase — Phase A (Foundation), Phase B (Structure), Phase C (Integration)
- **Stage 4 (Build Planning):** Phase D (Build Planning)
- **Stage 6 (Iteration):** Scoped artifact updates when functional changes affect artifacts

### Role boundary

The AG agent writes artifacts to `.prawduct/artifacts/` and updates the artifact manifest. It does NOT make product decisions, skip phases, invoke other agents, or modify project-state.yaml beyond the artifact manifest.

### Agent prompt (per-phase)

Include in the Task tool prompt:

1. **Role:** "You are the Artifact Generator for a Prawduct product build. Generate artifacts for [Phase X] per your skill instructions. Write artifacts to the product's `.prawduct/artifacts/` directory and update the artifact manifest."
2. **Instructions source:** "Read `agents/artifact-generator/SKILL.md` for your complete artifact selection, phasing, and consistency rules."
3. **Project context:** Project/product root paths, framework directory path (for template resolution at `{framework_root}/templates/`), structural characteristics, risk level, domain, current phase.
4. **Phase-specific task:**
   - **Phase A:** "Generate the Product Brief. Read `{framework_root}/templates/product-brief.md` for the template. Run the Phase A incremental check."
   - **Phase B:** "Generate Data Model and NFRs. Read existing Product Brief at `.prawduct/artifacts/product-brief.md`. Read templates from `{framework_root}/templates/`. Run the Phase B incremental check."
   - **Phase C:** "Generate remaining artifacts (Security Model, Test Specs, Operational Spec, Dependency Manifest, and structural artifacts). Read all prior artifacts. Run the full cross-artifact consistency check."
   - **Phase D:** "Generate the build plan. Read all artifacts and `{framework_root}/templates/build-plan.md`. Populate `build_plan` in project-state.yaml."
5. **Re-invocation variant** (when Review Lenses found blocking findings): Include the blocking findings and instruction to address them.

Follow the canonical example pattern (Critic above), substituting: role → Artifact Generator, SKILL.md → `agents/artifact-generator/SKILL.md`, context → framework root for templates + phase + product characteristics.

### Output verification

1. **Artifact files exist:** Expected artifacts for this phase are written to `.prawduct/artifacts/`.
2. **YAML frontmatter present:** Each artifact has standard frontmatter (artifact name, version, depends_on, depended_on_by).
3. **Manifest updated:** `artifact_manifest` includes entries for the new artifacts.
4. **Incremental check passed:** The phase-specific consistency check was executed.

### Cross-phase state

Each phase writes artifacts to disk. The next phase reads them from disk — no conversation context carries between phases. Phase B's prompt says "Read `.prawduct/artifacts/product-brief.md` (generated in Phase A)."

### Template resolution

Product repos store the framework path in `.prawduct/framework-path`. The Orchestrator includes the framework directory in the agent prompt so the agent can find templates at `{framework_root}/templates/`.
