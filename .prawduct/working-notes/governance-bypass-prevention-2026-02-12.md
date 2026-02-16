# Plan: Governance Bypass Prevention

**Created:** 2026-02-12
**Motivation:** Framework governance was bypassed when a detailed implementation plan was provided directly. The Orchestrator (which enforces DCP, Critic review, session resumption) was never loaded. Root cause: CLAUDE.md routing is conditional and soft; no hard rule prohibits governance bypass; no mechanical enforcement ensures Orchestrator activation.

## Problem Statement

Three gaps allow governance bypass:

1. **CLAUDE.md routing is conditional.** It says "route based on what the user says" with two branches. A detailed implementation plan doesn't clearly match either branch, so the LLM treats it as a direct execution instruction.

2. **No hard rule prohibits it.** HR1-HR8 cover specific quality failures but none says "the process itself is not optional." There's no principle to violate when skipping governance.

3. **No mechanical enforcement.** The commit gate checks for Critic evidence, the edit tracker reminds about Critic review, but nothing checks whether the Orchestrator was activated before framework files are modified.

## Changes

### 1. CLAUDE.md — Unconditional Orchestrator activation

**Section:** "When Someone Opens This Directory"

Replace the conditional routing with an unconditional directive. The Orchestrator is ALWAYS loaded first, regardless of what the user says. A user-provided plan is input to the Orchestrator's Stage 6 process, not a replacement for it.

Key change: from "route based on what the user says" to "always read the Orchestrator first, then it handles routing."

Also update the "Key Principles" section to include the new HR9.

### 2. docs/principles.md — Add HR9: No Governance Bypass

New hard rule after HR8. The governance process is how changes happen, not an optional layer. Detailed instructions, implementation plans, or "just do X" requests do not exempt changes from the framework's own governance. This applies to framework development specifically — the Orchestrator determines appropriate governance level (DCP for 3+ files, standard Critic for smaller changes).

### 3. .claude/hooks/orchestrator-gate.sh — New PreToolUse hook

PreToolUse hook on Edit and Write that checks whether `skills/orchestrator/SKILL.md` has been read in the current session before allowing framework file modifications.

**Mechanism:** When the Orchestrator is loaded and performs Session Resumption, it creates a marker file `.claude/.orchestrator-activated`. The hook checks for this marker. If absent and the target is a framework file, it blocks with a message directing the LLM to read the Orchestrator first.

**Marker lifecycle:** Created by the Orchestrator check (or could be created by the hook itself when it detects `skills/orchestrator/SKILL.md` was read — simpler). Cleaned up alongside `.session-edits.json` after commit.

Actually, simpler approach: the hook fires on Edit/Write. It reads the tool input to get the file path. If it's a framework file AND `.claude/.orchestrator-activated` doesn't exist, it blocks (exit 2). The Orchestrator skill instructions will include "touch .claude/.orchestrator-activated after Session Resumption."

### 4. .claude/settings.json — Register the new hook

Add the new PreToolUse hook for Edit|Write matcher.

### 5. skills/orchestrator/SKILL.md — Orchestrator activation marker

Add instruction to Session Resumption: after completing session orientation (step 5), create `.claude/.orchestrator-activated` marker. This signals to the hook that the Orchestrator has been properly loaded and governance is active.

Also add for new project sessions (after step 4 of "When You Are Activated"): create the marker.

### 6. CLAUDE.md — Update project structure tree

Add orchestrator-gate.sh to the hooks section.

## Files Modified

| File | Change |
|------|--------|
| CLAUDE.md | Unconditional routing, new HR in key principles, project structure update |
| docs/principles.md | Add HR9: No Governance Bypass |
| .claude/hooks/orchestrator-gate.sh | NEW: PreToolUse hook blocking framework edits without Orchestrator activation |
| .claude/settings.json | Register new PreToolUse hook |
| skills/orchestrator/SKILL.md | Add activation marker creation to Session Resumption |
| .claude/hooks/critic-gate.sh | Clean up .orchestrator-activated alongside other markers on commit |

## Risks

- **False blocks on non-framework files:** Hook must correctly identify framework files (reuse existing FRAMEWORK_PATTERNS from framework-edit-tracker.sh).
- **Marker not created:** If the Orchestrator instructions aren't followed (the very problem we're solving), the marker won't exist. But the hook will then block, which is the correct behavior — it forces the LLM back to the Orchestrator.
- **New sessions with no project-state.yaml:** The Orchestrator handles new projects too. The marker should be created regardless of path.
