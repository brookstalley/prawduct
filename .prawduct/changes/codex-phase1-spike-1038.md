---
schema: 1
type: feature
scope: codex-phase1-spike-1038
date: 2026-10-28
title: Add an experimental Codex Phase 1 adapter
closes: [brookstalley/prawduct#1038]
---
Add an experimental Codex adapter over the canonical Prawduct host seam, with
SessionStart briefing and core learnings injection, reflection-only Stop handling,
skill entry points, and doctor diagnostics for configuration and observed hooks.
The adapter keeps governance in the canonical plugin instead of copying its rules.

Stop blocks with an experimental diagnostic even when the canonical host import
raises RuntimeError or SyntaxError. SessionStart resolves the active worktree root
when invoked from a subdirectory, initializes boundary state at that root, and
preserves it for resume and compact events. Regression coverage includes these
failure paths, recorded hook shapes, packaging, host behavior, and the Python floor.

## Consumer note
Adds a Codex SessionStart briefing with core learnings, a reflection-only Stop
gate, the `methodology building` skill, and observed-only doctor diagnostics.
This is an experimental Phase 1 spike, not supported Codex parity. A canonical
Prawduct plugin root and explicit host hook setup are required; observed receipts
do not prove current hook trust. Stop covers reflection only and explicitly reports
Critic, PR, learnings migration, learnings budget, clear verdict, and clear reason
as uncovered. No Gemini/Antigravity or Phase 2/3 support is included.
