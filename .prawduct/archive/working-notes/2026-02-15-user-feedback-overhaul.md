# User Feedback Overhaul Plan

Created: 2026-02-15
Classification: directional
Trigger: User feedback from real-world usage

## Motivation

Real users report four categories of friction:
1. Framework stops too often asking for confirmation at every stage gate
2. Project names get chosen before the user is asked
3. UI products require human-in-the-loop testing (agent asks user to verify visuals)
4. No path to onboard existing repos into prawduct

Plus three additional items from user during planning:
5. Lenses should apply at Stage 2 for ALL products, not just medium/high risk
6. Remove "should we even build this" from Stage 0.5 — trust the user's intent
7. Governance hooks should gate skill/template reads (not just writes) behind Orchestrator activation

## Affected Files

### Phase 1: Orchestrator Flow & Governance Hooks
- `skills/orchestrator/SKILL.md` — Stage 0.5, Stage 2, Stage 3, Stage 4, Stage 5 confirmation behavior
- `.claude/hooks/governance-gate.sh` — extend to gate reads of skills/templates
- `.claude/hooks/governance-prompt.sh` — more assertive when Orchestrator not activated
- `.claude/settings.json` — add Read to governance-gate matcher
- `CLAUDE.md` — update descriptions to match new behavior

### Phase 2: Closed-Loop Testing (Design)
- `working-notes/` — MCP server design doc
- `docs/high-level-design.md` — architectural addition
- `docs/principles.md` — new principle: dev tooling never ships to production

### Phase 3: Closed-Loop Testing (Implementation)
- `skills/builder/SKILL.md` — MCP server launch and use during chunk execution
- `skills/artifact-generator/SKILL.md` — dev-tools artifact generation for has_human_interface
- `skills/critic/SKILL.md` — new check: dev MCP server excluded from production
- `templates/human-interface/dev-tools-spec.md` — new template for debugging MCP server
- Test scenario updates for visual verification

### Phase 4: Existing Project Onboarding
- `skills/orchestrator/SKILL.md` — new onboarding flow (Stage 0 variant)
- New skill or Orchestrator mode for reverse-engineering codebase into artifacts
- `project-state.yaml` template — version field for migration detection

## Phase 1 Detail: Orchestrator Flow & Governance Hooks

### 1a. Remove excessive confirmation pauses

**Current behavior:** Orchestrator pauses for explicit user confirmation at:
- Stage 0: Classification confirmation ("This sounds like X — is that right?")
- Stage 0.5→1: Validation completion
- Stage 2: Product definition confirmation ("Does this capture it?")
- Stage 3→4: Artifact review confirmation
- Stage 4→5: Build plan confirmation ("Want me to go ahead?")
- Stage 5 chunks: Between chunks for high-risk products

**New behavior:** Orchestrator only stops when it cannot proceed without user input.

| Point | Current | New |
|-------|---------|-----|
| Classification | Ask user to confirm | State the classification, keep moving. "I see this as [X]. Moving into discovery..." |
| Validation | Pause after validation | Remove validation pause entirely (see 1d below) |
| Definition | Ask "Does this capture it?" | Present definition, continue into artifacts. "Here's what I'm building — interrupt me if this is wrong." |
| Artifact review | Wait for user confirmation | Present artifact summary, continue into build planning. "Here are the artifacts. Moving to build planning..." |
| Build plan | Ask "Want me to go ahead?" | Present build plan, start building. "Here's the plan. Starting the build..." |
| Between chunks | Pause for high-risk at checkpoints | Only pause if a flag is raised (artifact_insufficiency, spec_ambiguity) or a governance checkpoint has blocking findings |

**Principle:** The user confirmed their intent when they described the product. Every subsequent pause should be because the framework is genuinely blocked, not because it wants permission to continue doing what the user already asked for.

**User can always interrupt.** This is a conversation — if the user sees something wrong in the definition summary or build plan, they say so. We don't need to ask.

### 1b. Fix project naming sequence

**Current behavior:** Orchestrator picks a directory name during project setup (Step 1 of "When You Are Activated"), which implies a project name before discovery has happened.

**New behavior:**
- During project setup, ask the user what to call the project OR use a temporary name
- The product name emerges from discovery, but the directory name needs to exist before files are created
- Simplest fix: ask "What would you like to call this project?" as part of initial intake, before classification begins. This is a genuine blocking question — we need a directory name.
- If user says "I don't know yet" or similar, use a slug derived from their first sentence (e.g., "family-scorekeeper") and note it can be changed.

### 1c. Apply lenses at Stage 2 for ALL products

**Current behavior (Stage 2, line 167-169):**
> "For low-risk products: Skip formal lens review at this stage."

**New behavior:**
Apply Product, Design, Architecture, and Skeptic lenses to the product definition for ALL products. Even small projects benefit from clarity. The lenses are lightweight for simple products (they'll find less to flag), so the overhead is minimal.

Remove the risk-conditional branching. One review path for all products.

### 1d. Remove "should we even build this" from Stage 0.5

**Current behavior (Stage 0.5):** Evaluates "whether this product warrants building." For high-risk products, applies Product and Skeptic lenses asking "does this warrant building?"

**New behavior:** Remove Stage 0.5 entirely. The user asked to build something — help them build it.

- Classification (Stage 0) transitions directly to Discovery (Stage 1)
- The lens applications that were in Stage 0.5 for high-risk products are now covered by Stage 2 (which applies lenses for all products per 1c above)
- If prior art search is added later, it becomes an informational input during discovery, not a gate

**Impact on Stage Transition Protocol:**
- Remove the → Stage 0.5 and → Stage 1 prerequisites sections
- Stage 0 transitions directly to Stage 1 (Discovery)
- Stage numbering stays as-is (skip 0.5) to avoid renumbering everything
- Update all references to "validation" stage throughout the skill

### 1e. Gate skill/template reads behind Orchestrator activation

**Changes to governance-gate.sh:**
- Current PreToolUse matcher: `Edit|Write`
- New PreToolUse matcher: `Edit|Write|Read`
- Add logic: when tool is Read (not Edit/Write), only check files in `skills/` and `templates/`
- Whitelist for pre-activation reads:
  - `skills/orchestrator/SKILL.md` — entry point
  - `project-state.yaml` — needed during activation
  - Everything outside `skills/` and `templates/`
- Block pre-activation reads of:
  - `skills/*/SKILL.md` (except orchestrator)
  - `templates/*`

**Changes to settings.json:**
- Update PreToolUse matcher from `Edit|Write` to `Edit|Write|Read`

**Changes to governance-prompt.sh:**
- Already injects activation instruction when Orchestrator not activated
- Make it more explicit: mention that skill/template reads are also blocked

### 1f. Make governance-prompt.sh more assertive

**Current behavior when Orchestrator not activated:** Injects instruction to activate.

**New behavior:** Same instruction but louder and more specific about what's blocked:
"ORCHESTRATOR NOT ACTIVATED. Reads of skill files (except orchestrator/SKILL.md) and template files are BLOCKED. Edits to all governed files are BLOCKED. Before doing anything else, read skills/orchestrator/SKILL.md and follow its activation process."

## Phase 2 Detail: Closed-Loop Testing Design

Design-only phase. No implementation. Produces a design doc in working-notes/.

Key design questions:
1. **MCP server interface:** What tools does the debugging server expose?
   - `screenshot` — capture current viewport
   - `navigate` — go to URL/route
   - `interact` — click, type, scroll on element
   - `inspect_element` — get computed styles, accessibility tree for element
   - `get_logs` — retrieve structured app logs
   - `get_state` — inspect app state (React DevTools-style)
   - `accessibility_audit` — run axe-core or similar
   - `set_config` — modify env vars, feature flags
   - `seed_data` — populate test data

2. **Technology:** Playwright for browser automation, custom MCP server wrapping it

3. **Security model:**
   - Dev-dependency only — excluded from production builds
   - Localhost-only binding
   - Test/seed data only, never real credentials
   - New hard rule: "HR10: No Dev Tooling in Production" (or similar)
   - Critic check: verify dev MCP server is not in production bundle

4. **Integration with Builder:**
   - Builder launches MCP server before first UI chunk
   - Uses it to verify visual output after each UI-touching chunk
   - Test specifications gain "visual verification" tier
   - Critic checks visual verification evidence exists for UI chunks

5. **Stack coverage:** Start with React + Playwright. Generalize later.

## Phase 3 Detail: Closed-Loop Testing Implementation

Depends on Phase 2 design being approved.

- Implement MCP server for React + Playwright stack
- Modify Builder to launch and use MCP server during chunk execution
- Modify Artifact Generator to include dev-tools setup in has_human_interface builds
- Add Critic check for production exclusion
- Update test scenarios with visual verification criteria

## Phase 4 Detail: Existing Project Onboarding

Two sub-problems:

### 4a. Fresh codebase onboarding
New Orchestrator mode or skill that:
1. Analyzes codebase structure, deps, tech stack → infers structural characteristics
2. Reads existing docs/README → extracts product brief, personas, requirements
3. Analyzes data models → generates data-model artifact
4. Analyzes test coverage → generates test-specifications artifact
5. Infers current stage (most existing repos are effectively Stage 6)
6. Generates project-state.yaml reflecting reality

### 4b. Old prawduct version detection
- Add version field to project-state.yaml template
- During Session Resumption, check schema version
- If old/unrecognized, enter migration mode:
  - Detect which version based on artifact structure and field names
  - Map old artifacts to current structure
  - Present migration summary to user
  - Generate new project-state.yaml

## Implementation Sequence

| Order | Phase | Scope | Dependencies |
|-------|-------|-------|-------------|
| 1 | Phase 1 (Orchestrator + hooks) | ~5 files | None |
| 2 | Phase 2 (MCP design) | Design doc only | None (can parallel with Phase 1) |
| 3 | Phase 3 (MCP implementation) | ~5 new/modified files | Phase 2 approved |
| 4 | Phase 4 (Onboarding) | New skill + Orchestrator changes | Benefits from Phase 3 |

Phase 1 is the immediate deliverable. Phases 2-4 are future sessions.
