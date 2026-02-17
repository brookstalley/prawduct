---
artifact: security-model
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
depended_on_by:
  - artifact: test-specifications
  - artifact: operational-spec
last_validated: 2026-02-16
---

# Security Model

<!-- MINIMAL: Framework handles no user data, no authentication, no authorization. -->
<!-- sourced: docs/principles.md § HR9, 2026-02-16 -->

## Applicability

Prawduct is an instruction framework running within the user's local LLM session. It processes no user data, requires no authentication, and has no network surface. Traditional security concerns (auth, authorization, data privacy) do not apply.

## Residual Security Concerns

### Hook Bypass Risk

Mechanical governance hooks (governance-gate.sh, critic-gate.sh, governance-stop.sh) enforce quality process. These hooks can be bypassed by:
- Modifying `.claude/settings.json` to remove hook registrations
- Running git commands outside Claude Code (bypasses critic-gate)
- Deleting `.orchestrator-activated` marker and re-creating it without following the Orchestrator process

**Mitigation:** Hooks are defense-in-depth, not the only governance layer. The Critic review is LLM-judgment-based and runs independently of hooks. The SessionStart hook re-injects governance instructions after compaction.

### Framework-Path Trust

Product repos contain `.prawduct/framework-path` pointing to the prawduct framework directory. If this path is manipulated to point to a malicious framework, all hook paths and skill file reads would load attacker-controlled content.

**Mitigation:** `prawduct-init.py` writes this file mechanically during setup. The path is an absolute filesystem path — it can't be redirected via symlinks without filesystem access. Users who can modify this file already have full filesystem access.

### Governance Marker Spoofing

The `.orchestrator-activated` marker is a simple timestamp file. Any process that can write to `.prawduct/` can create this marker, bypassing the requirement to actually read and follow the Orchestrator.

**Mitigation:** The marker is a convenience check, not a security boundary. The real governance comes from skill instructions and Critic reviews, which operate at the LLM judgment level.

## Abuse Prevention

Not applicable — Prawduct has no multi-user interaction, no user-generated content, and no network-accessible surface.
