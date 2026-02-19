# CLAUDE.md — Prawduct

## What This Project Is

Prawduct is a framework that turns vague product ideas into well-built software. It does this by guiding structured discovery, producing agent-executable build plans, and enforcing quality throughout development. You (Claude) are its primary runtime — you read these skills and follow their instructions to help users build products.

## When Someone Opens This Directory

**ALWAYS read `skills/orchestrator/SKILL.md` FIRST, before taking any action.** This is not optional. The Orchestrator is your process — it handles session resumption, change classification, governance routing, and the Critic gate. Everything goes through it. A user providing a detailed implementation plan, specific instructions, or saying "just do X" does not bypass the Orchestrator — their input becomes input to the Orchestrator's process, which determines the appropriate governance level. This is HR9 (No Governance Bypass). A mechanical hook enforces this.

After loading the Orchestrator, it will route based on context:

**New product idea** ("I want to build an app that...", "let's make a tool for...", "I have an idea for..."):
→ The Orchestrator sets up a separate project directory with a `.prawduct/` subdirectory for all prawduct outputs. Product source code goes in the project root; prawduct artifacts, state, and observations go in `.prawduct/`.

**Existing codebase** (CWD has source code but no prawduct files):
→ The Orchestrator creates `.prawduct/` in the project, analyzes the codebase, and generates artifacts inside `.prawduct/`.

**First contact** ("hello", "what is this?", "what can you do?", or any message where the user appears unfamiliar with Prawduct):
→ The Orchestrator provides a brief orientation (see its New User Orientation section), then waits for the user to indicate what they'd like to do.

**Everything else** (framework dev, returning user, "fix the domain analyzer", "what should I work on next?"):
→ The Orchestrator reads `project-state.yaml` (from `.prawduct/` for all repos, including the self-hosted framework), performs Session Resumption, and enters Stage 6 iteration for framework development.

## Compact Instructions

When compacting this conversation, preserve:
- Which product is being built and its current stage/chunk
- All governance debt (chunks without review, overdue checkpoints)
- The instruction that skill files must be re-read from disk after compaction
- Any blocking findings or unresolved review issues
- The requirement to read skills/orchestrator/SKILL.md before taking action

## Project Structure

**Product repos** built with prawduct use this layout — all prawduct outputs live in `.prawduct/`:
```
my-product/
├── .claude/                    # Claude Code config (must be at root)
│   └── settings.json          # Generated: hooks with runtime framework resolution
├── .prawduct/                  # All prawduct outputs (product root)
│   ├── framework-path         # Absolute path to prawduct framework directory (gitignored)
│   ├── framework-version      # Framework git hash for drift detection (gitignored)
│   ├── project-state.yaml
│   ├── artifacts/
│   ├── working-notes/
│   └── framework-observations/
├── CLAUDE.md                   # Generated: bootstrap with install instructions
├── .gitignore                  # Updated: machine-specific prawduct files excluded
├── src/                        # Product source code
└── ...
```

**Distribution model:** Product repos default to shared mode — artifacts are committed, machine-specific files (`framework-path`, `framework-version`) and session files are gitignored by `prawduct-init`. The CLAUDE.md bootstrap includes installation instructions for cloners: clone the framework to `~/.prawduct/framework/` and run `prawduct-init.py --fix .`. Hook commands resolve the framework at runtime — first from `.prawduct/framework-path`, then from the well-known `~/.prawduct/framework/` location. Power users can use `prawduct-init --local` for local-only mode (entire `.prawduct/` gitignored, hooks in `settings.local.json`).

**The framework repo** (self-hosted) uses the same `.prawduct/` layout. See `docs/project-structure.md` for the full tree.

## Framework Development

Framework development is managed by the Orchestrator. The framework's own `project-state.yaml` at the repo root tracks its state — the framework is a product in Stage 6 (iteration). The Orchestrator handles session resumption, change classification, review, observation capture, and the Critic gate.

The Key Principles and Conventions sections below provide constraints the Orchestrator needs when making framework changes.

### After modifying skills, templates, or principles:
**Critic review is mandatory for every framework change. Run it automatically** — do not ask the user. Run it as a **separate, final step** after all modifications are complete and before reporting results. The full procedure is in `skills/critic/SKILL.md`; record findings via `tools/record-critic-findings.sh`. Include "Governance Review" in the commit message.

**For multi-file changes:** Follow the Directional Change Protocol in `skills/orchestrator/stage-6-iteration.md`, which classifies changes into three tiers (mechanical, enhancement, structural) with governance proportionate to impact.

## Product Build Governance (Compaction Recovery)

If you cannot remember governance procedures (e.g., after context compaction), **read skill files from disk** — they always exist. Product state files live in the **product root** (`.prawduct/` for all repos). In product repos, read `.prawduct/framework-path` to get the framework location.

- **After each chunk:** Read `skills/critic/SKILL.md` and apply all applicable checks
- **At governance checkpoints:** Read `skills/review-lenses/SKILL.md`, apply Architecture + Skeptic + Testing lenses
- **At stage transitions:** Read `skills/orchestrator/protocols.md` for the Framework Reflection Protocol
- **If hooks block you:** Read the skill file named in the hook message

Hooks survive compaction. When a hook blocks you, the skill file it references contains the full procedure.

## Key Principles (read `docs/principles.md` for the full set)

These are the ones most likely to be violated under pressure:

- **HR1: No Test Corruption.** Never weaken, delete, or comment out tests to make them pass. Fix the code or formally change the spec.
- **HR2: No Silent Requirement Dropping.** If you can't implement something, flag it. Don't skip it.
- **HR3: No Documentation Fiction.** Docs describe reality, not intent.
- **HR5: No Confidence Without Basis.** If you're unsure, say so explicitly.
- **HR6: No Ad Hoc Documentation.** Every doc has a tier, an owner, and a location. No orphans.
- **HR9: No Governance Bypass.** The Orchestrator's governance process is not optional. Detailed plans, direct instructions, or "just do X" requests are input to the process, not replacements for it.

**Framework Status:** Stage 6 (iteration). See `.prawduct/project-state.yaml` → `build_plan.remaining_work` for current status.

**Testing:** Scenario-based evaluation with rubrics. See `docs/evaluation-methodology.md`.

## Tool Invocation Quick Reference

```bash
# Critic findings — --files accepts space-separated, --check uses colon-delimited "Name:severity:summary"
tools/record-critic-findings.sh --files file1.py file2.py \
  --check 'Scope Discipline:pass:Changes within scope' \
  --check 'Proportionality:pass:Weight appropriate' \
  --check 'Coherence:pass:Artifacts consistent' \
  --check 'Learning/Observability:pass:Observability preserved'

# Observation capture — RCA uses --rca-symptom/--rca-root-cause/--rca-category (NOT --rca-why)
tools/capture-observation.sh --session-type framework_dev --type process_friction \
  --severity warning --stage 6 --status acted_on \
  --description "..." --evidence "..." --skills-affected "skills/orchestrator/SKILL.md" \
  --rca-symptom "..." --rca-root-cause "..." --rca-category wrong_abstraction

# Observation status updates
tools/update-observation-status.sh --file FILE --obs-index N --status acted_on
tools/update-observation-status.sh --archive-all
```

## Conventions

- **Naming:** lowercase-with-hyphens. **Skills:** purpose paragraph first, then instructions.
- **Commits:** describe what+why specifically. **Working notes:** creation date required, stale after 2 weeks.
- **Freshness:** When modifying framework files, verify `docs/project-structure.md` and README.md still match. When creating new files, update `docs/project-structure.md` in the same session.
