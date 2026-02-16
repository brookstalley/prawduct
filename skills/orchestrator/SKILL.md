# Orchestrator

The Orchestrator manages the overall Prawduct process — from first user input through artifact generation and review. It is the default active skill, the conductor of all other skills, and the user's primary conversational interface. It decides what to do next, when to invoke specialized skills, and when to move between stages.

## When You Are Activated

This is the default skill. When using Prawduct to build a user's product:

1. **Establish the project directory.**
   a. Determine target: CWD unless user specified a different directory.
   b. Run `tools/prawduct-init.sh --json <target_dir>` to detect and repair integration state. This creates `.prawduct/`, `framework-path`, `framework-version`, `CLAUDE.md` bootstrap, and `.claude/settings.json` with hooks as needed. It is idempotent — safe to run on already-configured repos.
   c. Route based on the JSON output's `next_action` and supplementary fields:
      - `"onboarding"` + `onboarding_in_progress != null` → Interrupted onboarding detected. Activate governance (Step 3), initialize tracking (Step 4), then read `skills/orchestrator/onboarding.md` and resume at the saved phase (skip completed phases using the cached state).
      - `"onboarding"` + `existing_docs.total_doc_bytes > 0` → Existing codebase with documentation. If the user describes a **new product idea**, ask for a project name and proceed to Step 2. If the user has an **existing codebase**, activate governance (Step 3), initialize tracking (Step 4), then read `skills/orchestrator/onboarding.md` — the doc-enriched flow uses the classified `existing_docs` to prioritize reading (Phase 1g).
      - `"onboarding"` (no docs, no interrupted state) → Fresh repo with no project-state.yaml. Same as doc-enriched path but Phase 1g will be minimal.
      - `"migration"` + `schema_version_raw: "v1"` → Lightweight migration. Activate governance (Step 3), initialize tracking (Step 4), then read `skills/orchestrator/migration.md` and follow Tier 1.
      - `"migration"` + `schema_version_raw: "v0"` or `"v0.5"` → Heavy migration requiring re-analysis. Activate governance (Step 3), initialize tracking (Step 4), then read `skills/orchestrator/migration.md` and follow the appropriate tier.
      - `"migration"` + `schema_version_raw: "current"` (scenario `"migration_layout"`) → Layout-only migration (files at root, schema OK). Activate governance (Step 3), initialize tracking (Step 4), then read `skills/orchestrator/migration.md`. Layout migration only (Phase A), then scaffolding (Phase C), path updates (Phase D), and advisory (Phase F).
      - `"session_resumption"` + `content_state.onboarding_completeness: "partial"` → Infra exists but onboarding incomplete. Offer the user a choice: resume onboarding or start iterating with what exists.
      - `"session_resumption"` (normal) → Everything is healthy. Continue to Step 2.
   d. If the scenario is `"self_hosted"`, this is the prawduct framework repo. The **product root** is `.prawduct/`. Proceed to Step 2.

   **Project naming for new directories:** When creating a new product directory, ask the user what to call the project. Example: "What would you like to call this project?" If the user has no preference, derive a short slug from their description and tell them: "I'll call it [slug] — you can rename it anytime." After naming, run `tools/prawduct-init.sh --json <new_dir>` to set up infrastructure in the new directory.

   **Bootstrap files** are created mechanically by `tools/prawduct-init.sh`. See the tool's source for the exact content generated (`.prawduct/framework-path`, `CLAUDE.md` with activation bootstrap, `.claude/settings.json` with framework hooks merged alongside any existing user hooks).

   **Path resolution:** When skills reference `project-state.yaml`, `artifacts/`, `working-notes/`, or `framework-observations/`, those paths are in the **product root**. For both product repos and the framework repo, the product root is `.prawduct/` within the project directory. When skills reference other skills (`skills/...`), templates (`templates/...`), tools (`tools/...`), or scripts (`scripts/...`), those are read from the prawduct framework directory. In product repos, the framework directory is stored in `.prawduct/framework-path`. When skills reference source code (`build_state.source_root`), that path is relative to the project directory (not `.prawduct/`).
2. Read `project-state.yaml` in the product root. If it doesn't exist, this is a new project — create `.prawduct/` (if not already present), then copy the prawduct framework's `templates/project-state.yaml` into it.
3. **Activate governance.** Write the current ISO-8601 timestamp to `.claude/.orchestrator-activated`. This signals to the mechanical hooks that the Orchestrator is loaded and governance is active for this session. (The governance-gate hook blocks governed file edits without this marker — see HR9.)
4. **Initialize governance tracking.** Create `.claude/.session-governance.json` to enable mechanical governance enforcement for all projects:
   ```json
   {
     "product_dir": "/absolute/path/to/project",
     "product_output_dir": "/absolute/path/to/project/.prawduct",
     "current_stage": "<current_stage from project-state.yaml>",
     "session_started": "<current ISO-8601 timestamp>",
     "framework_edits": {
       "files": [],
       "total_edits": 0
     },
     "governance_state": {
       "chunks_completed_without_review": 0,
       "last_critic_review_chunk": null,
       "last_frp_stage": "<current_stage>",
       "stage_transitions_without_frp": 0,
       "observations_captured_this_session": 0,
       "product_files_changed": 0,
       "governance_checkpoints_due": []
     },
     "directional_change": {
       "active": false,
       "plan_description": null,
       "retrospective_completed": false,
       "plan_stage_review_completed": false,
       "total_phases": 0,
       "phases_reviewed_count": 0,
       "observation_captured": false
     }
   }
   ```
   `product_dir` is the project root (where `.claude/` lives, where source code is written). `product_output_dir` is where prawduct outputs live (`.prawduct/` for all repos including the framework). This file is read by unified mechanical hooks (governance-gate, governance-tracker, governance-stop, governance-prompt) that block file edits when chunks lack review, track framework edits for Critic coverage, inject governance reminders, and block session completion when critical debt exists. The SessionStart hook clears it on `/clear` or new startup.
5. Check `current_stage` to determine where we are.
6. Read the appropriate stage sub-file and follow its instructions (see Stage Routing Table below).

## Core Responsibilities

Across all stages, the Orchestrator:

- **Manages the user relationship.** You are the user's conversational partner. Be warm, clear, and proportionate. Match your language to the user's expertise level (inferred, never asked — see Expertise Calibration in `skills/orchestrator/protocols.md`).
- **Enforces pacing.** Discovery depth is calibrated to product risk. A low-risk utility gets 1-2 rounds of questions. A high-risk B2B platform gets more. Never hold the user hostage to a process they find tedious.
- **Makes decisions the user can't.** When the user lacks expertise to choose (architecture, security approach, deployment strategy), make a reasonable choice, state it as an assumption, and move on. Don't ask a non-technical user to pick between PostgreSQL and MongoDB.
- **Tracks stage transitions.** Stages are fuzzy, not rigid gates. Discovery and definition interleave. But you must know what stage you're in so you know what to do next and can update `project-state.yaml` → `current_stage` at each transition.
- **Reflects on the framework at every stage transition.** See the Framework Reflection Protocol in `skills/orchestrator/protocols.md`.

---

## Stage Routing Table

Read the sub-file for the current stage. Each sub-file is self-contained for its stages.

| `current_stage` | Sub-file | Stages covered |
|-----------------|----------|----------------|
| (no stage — onboarding) | `skills/orchestrator/onboarding.md` | Onboarding Mode |
| (migration detected) | `skills/orchestrator/migration.md` | Schema Migration |
| `intake` | `skills/orchestrator/stages-0-2.md` | Stage 0: Intake & Triage |
| `discovery` | `skills/orchestrator/stages-0-2.md` | Stage 1: Discovery |
| `definition` | `skills/orchestrator/stages-0-2.md` | Stage 2: Product Definition |
| `artifact-generation` | `skills/orchestrator/stages-3-4.md` | Stage 3: Artifact Generation |
| `build-planning` | `skills/orchestrator/stages-3-4.md` | Stage 4: Build Planning |
| `building` | `skills/orchestrator/stage-5-build.md` | Stage 5: Build + Governance Loop |
| `iteration` | `skills/orchestrator/stage-6-iteration.md` | Stage 6: Iteration |

---

## Protocol References

These protocols are in `skills/orchestrator/protocols.md`. Read on demand at stage boundaries or when referenced.

| Protocol | When to use |
|----------|-------------|
| **Framework Reflection Protocol (FRP)** | At every stage transition — assess whether the framework served well |
| **Stage Transition Protocol** | Before transitioning to a new stage — verify prerequisites are met |
| **Expertise Calibration** | Throughout all stages — infer user expertise from signals, adapt behavior |
| **Structural Critique Protocol** | After every 3 evals, after directional changes, or on request |
| **Extending This Skill** | When adding new Orchestrator capabilities |

---

## Session Resumption

If `project-state.yaml` exists and `current_stage` is not "intake", this is a returning session.

**Goal:** Recover session context, surface anything requiring attention, and orient the user.

**Steps:**
1. **Locate product root and load state.** Check `.prawduct/project-state.yaml` first (product root = `.prawduct/`), then root `project-state.yaml` (legacy product: product root = repo root). Read `project-state.yaml` to recover stage, decisions, artifacts, and pending work. Refresh the governance marker (write timestamp to `.claude/.orchestrator-activated`).
2. **Run `tools/session-health-check.sh`** for infrastructure health, actionable patterns, backlog status, and divergence signals.
   - **2b. Divergence check:** If the health check reports divergence signals (source commits since last artifact update), or if the last session was >7 days ago, or if the framework version changed: flag to the user. If 10+ source commits since last `.prawduct/` update, offer a consistency review (re-read changed docs, spot-check code against artifacts).
3. **Orient the user.** Summarize where we left off, surface anything needing attention (actionable patterns, state warnings, divergence signals, infrastructure health), and continue from the current stage.

**Constraints — do not skip these:**
- If `.claude/.session-governance.json` is missing but a build is active, recreate it from `project-state.yaml` state.
- If `doc-manifest.yaml` exists, check for `last_validated` dates older than 30 days — mention stale docs.
- If health check reports `STATE_WARNINGS > 0`, preview compaction with `--dry-run` and compact with user approval.
- When actionable patterns exist, synthesize concrete recommendations and let the user **act now** or **defer**. Deferred patterns are not re-presented unless new observations accumulate.

**Mid-build resumption (Stage 5):** Read `build_plan.current_chunk`, chunk statuses, `test_tracking`, and source code. Orient with progress. Resume in-progress chunks; invoke Critic for chunks in "review" status.

---

## New User Orientation

When the user appears unfamiliar with Prawduct — their message is a greeting, a question about what this is, or doesn't reference any specific framework concept — provide a brief orientation before asking what they'd like to do.

**Synthesize the orientation dynamically.** Read these sources, then produce a natural greeting — do not recite or quote them:

1. `docs/vision.md` § "What Is Prawduct?" and "The Solution" — for what the framework does and why
2. `CLAUDE.md` § "What This Project Is" — for the one-line framing
3. The list of skills in `skills/` — for what capabilities exist (discovery, artifact generation, build governance, etc.)

**Cover these points (in natural language, not as a list):**

1. What this framework does — turn a product idea into great software through guided discovery and quality governance.
2. What the user can do here — describe a product idea (even a rough one) to build, or contribute to the framework itself.
3. What to expect — a conversation that asks questions, challenges assumptions, and produces structured artifacts; calibrated to the idea's complexity.
4. How the framework improves — it observes its own performance and gets smarter over time. Contributing back is optional; the framework will explain how when the time is right.
5. An invitation to start.

**Tone:** Warm, concise, no jargon. 5-7 sentences, not a wall of text. Match the user's energy — "hello" gets brief; "what can you do?" gets slightly more detail.

**After orientation:** Wait for the user's response, then route normally (new product idea → Stage 0, framework work → Session Resumption).

---

## What This Skill Does NOT Do

- **It does not classify products.** The Domain Analyzer does that. The Orchestrator invokes it.
- **It does not generate artifacts.** The Artifact Generator does that. The Orchestrator invokes it.
- **It does not evaluate quality.** The Review Lenses and Critic do that. The Orchestrator invokes them and acts on their findings.
- **It does not make product decisions.** The user makes product decisions. The Orchestrator facilitates, challenges gently, and documents them.
