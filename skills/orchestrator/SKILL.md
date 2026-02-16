# Orchestrator

The Orchestrator manages the overall Prawduct process — from first user input through artifact generation and review. It is the default active skill, the conductor of all other skills, and the user's primary conversational interface. It decides what to do next, when to invoke specialized skills, and when to move between stages.

## When You Are Activated

This is the default skill. When using Prawduct to build a user's product:

1. **Establish the project directory.** Check these conditions in order; stop at the first match:

   1. Does `.prawduct/project-state.yaml` exist in the current directory?
      a. YES + user describes a NEW product → Create a separate directory for the new product with `.prawduct/` inside it.
      b. YES + not a new product → This is a returning product session. The **product root** is `.prawduct/` within this directory. Proceed.
   2. Does `project-state.yaml` exist at the repo root (no `.prawduct/`)?
      a. YES + this is the prawduct framework repo → Self-hosted. The **product root** is the repo root. Proceed.
      b. YES + user describes a NEW product → Create a separate directory for the new product with `.prawduct/` inside it.
      c. YES + not a new product → Check `schema_version`. Current version: product root is the repo root (legacy layout). Old/missing version: enter Migration Mode (see Existing Project Onboarding section in working-notes). Legacy-layout products continue to work — migration to `.prawduct/` is offered in a future phase.
   3. No `project-state.yaml` anywhere + CWD contains project signals (source code, package.json, Cargo.toml, go.mod, requirements.txt, etc.) and is NOT the prawduct repo → **Onboarding Mode**: activate governance (write current ISO-8601 timestamp to `.claude/.orchestrator-activated`), initialize governance tracking (Step 4), then read `skills/orchestrator/onboarding.md` and follow its process. Onboarding handles Steps 2 and 5-6 internally — skip them.
   4. No `project-state.yaml` + user specified a directory → Create `.prawduct/` within it.
   5. None of the above → Ask the user where project files should go, then create `.prawduct/` there.

   **Project naming:** When creating a new project directory (conditions 1a, 2b, 4, or 5), ask the user what to call the project before creating any files. This is a genuine blocking question — the framework needs a directory name. Example: "What would you like to call this project?" If the user has no preference, derive a short slug from their description (e.g., "family-scorekeeper") and tell them: "I'll call it [slug] — you can rename it anytime."

   **Bootstrap files:** When creating a new product directory (conditions 1a, 2b, 4, or 5), generate three bootstrap files so the product repo works as a standalone Claude Code project:
   1. **`.prawduct/framework-path`** — Write the absolute path to the prawduct framework directory (where this skill file lives). Plain text, single line, no trailing newline.
   2. **`CLAUDE.md`** — Minimal bootstrap that tells Claude to read the framework-path file, then read the Orchestrator skill from the framework. Content:
      ```
      # [Project Name]

      ## Setup
      This project uses the Prawduct framework.
      Framework location: read `.prawduct/framework-path` for the absolute path.

      ## Instructions
      Before taking any action, read the framework path from `.prawduct/framework-path`,
      then read `<framework-path>/skills/orchestrator/SKILL.md` and follow its activation process.
      ```
   3. **`.claude/settings.json`** — Hook configuration with absolute paths to framework hooks. Generate from the framework's own `.claude/settings.json`, replacing relative hook paths with absolute paths using the framework directory.

   **Path resolution:** When skills reference `project-state.yaml`, `artifacts/`, `working-notes/`, or `framework-observations/`, those paths are in the **product root**. For product repos, the product root is `.prawduct/` within the project directory. For the framework repo (self-hosted), the product root is the repo root. When skills reference other skills (`skills/...`), templates (`templates/...`), tools (`tools/...`), or scripts (`scripts/...`), those are read from the prawduct framework directory. In product repos, the framework directory is stored in `.prawduct/framework-path`. When skills reference source code (`build_state.source_root`), that path is relative to the project directory (not `.prawduct/`).
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
   `product_dir` is the project root (where `.claude/` lives, where source code is written). `product_output_dir` is where prawduct outputs live (`.prawduct/` for product repos, same as `product_dir` for the framework repo). This file is read by unified mechanical hooks (governance-gate, governance-tracker, governance-stop, governance-prompt) that block file edits when chunks lack review, track framework edits for Critic coverage, inject governance reminders, and block session completion when critical debt exists. The SessionStart hook clears it on `/clear` or new startup.
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
1. **Locate product root and load state.** Check `.prawduct/project-state.yaml` first (product root = `.prawduct/`), then root `project-state.yaml` (framework repo: product root = repo root; legacy product: product root = repo root). Read `project-state.yaml` to recover stage, decisions, artifacts, and pending work. Refresh the governance marker (write timestamp to `.claude/.orchestrator-activated`).
2. **Run `tools/session-health-check.sh`** for infrastructure health, actionable patterns, and backlog status.
3. **Orient the user.** Summarize where we left off, surface anything needing attention (actionable patterns, state warnings, documentation staleness, infrastructure health), and continue from the current stage.

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
