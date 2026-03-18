# Prawduct v5 Requirements — Scaling Governance for Maturing Projects

## Problem Statement

Prawduct successfully guides projects from discovery through initial build. As projects mature (Discodon: 24K LOC, 42K test LOC, 60+ chunks, 4,400+ tests), governance effectiveness degrades in five predictable ways:

1. **LLM adherence decays with context scale.** The LLM skips methodology — building without specs, shipping without tests, swallowing exceptions — and users must manually remind it.
2. **Phase boundaries are artificial.** Real projects continuously do discovery, planning, building, and reflection. The phase model creates a "we're past that" excuse.
3. **Cross-boundary coherence breaks silently.** API changes break frontend consumers; integration tests are missing or unrun.
4. **Documentation drifts without automation.** Artifacts become fiction after 20+ chunks.
5. **Learnings accumulate without effect.** Known patterns repeat because the relevant learning isn't in context at decision time.

## Evidence Base

- Discodon commit 732be18: documentation scrub fixing weeks of artifact drift
- Discodon: "Always verify frontend types match actual backend response" — coherence failure caught late
- Prawduct: "Judgment alone won't interrupt momentum" — LLM doesn't self-impose process interruptions
- Prawduct: "Filed-away observations don't change behavior" — write-only learning loop
- Critic gate never fired for 40+ sessions (watching wrong file)
- Discodon learnings.md grew to 42KB despite 3,000-token guidance

## Design Constraints

1. **LLM-executable.** No external services, no CI/CD. Runs in Claude Code sessions.
2. **Self-contained products.** No runtime framework dependency. Sync propagates improvements.
3. **Proportional effort.** Governance scales with risk and codebase size.
4. **Hook complexity acceptable when justified.** We'll reduce if it becomes a problem.
5. **Automated v4 migration.** Hook/sync detects v4 and migrates automatically.
6. **Block-marked CLAUDE.md.** Prawduct content in PRAWDUCT:BEGIN/END blocks. Project edits outside blocks always preserved.
7. **Protect the Critic.** Separate-agent review is the strongest part. Never degrade it.
8. **Subagents follow governance.** Context must be passed to delegated agents.
9. **Design for current model capabilities.** Adapt to improvements, don't anticipate them.

---

## C1: Work-Scaled Governance

*Consolidates: R1 (Continuous Governance) + R6 (Mature Project Patterns)*

### Core Idea
There are no phases. Every unit of work — whether it's the first feature of a new project or chunk 80 of a mature one — follows the same cycle: **understand → plan → build → verify.** What changes is the depth, determined by two dimensions: **size** and **type**.

### Work Size (determines governance depth)
- **Trivial** (typo, config change): Build + verify.
- **Small** (bug fix, minor feature): Understand context + build + verify + update affected artifacts.
- **Medium** (new feature, significant refactor): Requirements + build plan + build + Critic review + artifact updates.
- **Large** (new subsystem, architectural change): Full discovery + planning + chunked build + Critic per chunk.

Classification heuristic is based on blast radius: 1-2 files = trivial/small; 5+ files or new dependency = medium; new directory structure or API surface = large.

### Work Type (determines governance emphasis)
- **Feature**: Spec compliance, test coverage, artifact freshness.
- **Bugfix**: Root cause analysis, regression test, learning capture.
- **Refactor**: Behavior preservation (tests don't change), architecture coherence.
- **Optimization**: Baseline measurement before changes, performance regression testing.
- **Debt paydown**: Scope discipline, architecture freshness.
- **Emergency hotfix**: Minimal path — fix + test + verify. Artifacts can follow.

### Health Check
No fixed cadence. Emerges from staleness signals (see C4). When enough drift accumulates, the session briefing escalates to a health check recommendation. `project-state.yaml` tracks last check date/findings. Advisory only.

### Changes from v4
- Retire `current_phase` from project-state.yaml.
- Replace with work-in-progress tracker (what's being done, at what governance level).
- Critic receives goals and signals, reasons about scope — no fixed checklist per review.

---

## C2: Structural Compliance

*Consolidates: R2 (Active Compliance) + R8 (Exception Governance) + R9 (Subagent Governance)*

### Core Idea
Some behaviors the LLM self-regulates from principles alone (code quality, naming, following established patterns). Others it skips under momentum (running tests, invoking the Critic, updating artifacts, not swallowing exceptions). The first category needs principles. The second needs **structural reinforcement** — mechanisms that don't rely on the LLM remembering.

### Three Structural Mechanisms

**1. Session Briefing (SessionStart hook → stdout → system-reminder)**

The hook produces a concise (~200-400 token) structured briefing injected automatically as a system-reminder. Guaranteed delivery — no behavioral compliance needed. Contains:
- Project identity and current state (1-2 sentences).
- Stale artifact warnings (from C4 staleness scan).
- Relevant active learnings (filtered by recent git changes and file types).
- Key reminders for momentum-vulnerable behaviors.
- Health check recommendation if warranted.

CLAUDE.md carries stable methodology. The briefing carries volatile state. Clean separation.

**2. Compliance Canary (stop hook)**

Lightweight check before session end that detects common governance failures:
- Code changed but no tests added or modified.
- Contract surface changed but consumers not verified (see C3).
- New dependency added without rationale in dependency manifest.
- Broad exception handling introduced without logging/re-raising.

Not a complete audit — just the highest-signal canaries for the most common failures.

**3. Subagent Briefing (.prawduct/.subagent-briefing.md)**

Generated at session start by the hook. Assembled from static governance rules + project-preferences + active learnings. The builder includes it in delegation prompts with one line: "Read `.prawduct/.subagent-briefing.md`." Mirrors the Critic pattern — one file, read from disk. Builder remains responsible for subagent output; Critic reviews all changes regardless of who produced them.

### What Gets Reinforced

The specific behaviors that degrade at scale, including but not limited to:
- Write tests alongside code, not after.
- Never weaken a test to make it pass.
- Never silently drop a requirement.
- Never catch broad exceptions without logging + re-raising. Projects define a "never swallow" list.
- Run integration tests when changes cross boundaries.
- Invoke Critic after medium+ work.
- Update artifacts when code changes what they describe.

These appear in CLAUDE.md (top, concise), in the session briefing (reminders), and in the compliance canary (detection). Repetition across delivery mechanisms is intentional — it compensates for attention dilution.

### CLAUDE.md Structure

Critical rules at the TOP of CLAUDE.md, not buried in methodology files. CLAUDE.md for mature projects should be **shorter** than for new projects — as rules are internalized into hooks and Critic checks, remove the prose. Target: <4K tokens for the Prawduct-managed block.

---

## C3: Investigated Changes

*Consolidates: R3 (Cross-Boundary Coherence) + R10 (Researched Decisions)*

### Core Idea
Two categories of action require investigation before commitment: **changes that cross boundaries** and **decisions that constrain future options.** Both follow the same pattern: recognize the trigger → investigate (depth scaled to impact) → incorporate findings → record rationale. Both benefit from subagent investigation for the same reasons: context preservation, fresh perspective, and depth without delay.

### Boundary Investigation (when changes cross contract surfaces)

Contract surfaces are boundaries where components interact: API endpoints, database schemas, inter-process communication, frontend/backend type contracts, configuration interfaces.

**Detection, not declaration.** When the builder modifies files that appear to affect a contract surface, it spawns a focused investigation subagent. The subagent reads the changes, identifies affected contracts, greps for consumers across layer boundaries, and reports: which boundaries were crossed, which consumers may be affected, and whether tests cover the change.

Per-project boundary patterns are documented in an artifact to help the subagent focus, but it reasons about what it finds rather than mechanically following patterns.

**Test tiers.** Products declare which test levels exist (unit, integration, contract, end-to-end) and when each should run. The build cycle includes a boundary check step; the Critic verifies it occurred.

### Decision Research (when choices constrain future options)

A decision is "major" when it has: **lock-in** (hard to reverse), **pervasiveness** (used across many files), **structural impact** (shapes architecture), or **external dependency** (long-term reliance on a library/service).

**Research scales to impact:**
- **Medium-impact** (pervasive pattern, non-core dependency): Quick research in the main context. A few web searches, check library health, review alternatives.
- **High-impact** (lock-in, structural, core dependency): Spawn a research subagent. It investigates thoroughly — best practices in this project's context, established patterns, cautionary tales, library health signals — and returns a concise recommendation. The builder's context stays clean.

**Presentation scales to user engagement:**
- **Low engagement**: Decide and state briefly. Don't ask.
- **Medium engagement**: Recommend with context, invite feedback.
- **High engagement**: Present options with trade-offs, let user choose.
Calibrate from user expertise profile, session engagement signals, and project-preferences. Default to medium.

### Recording and Revisitation

Major decisions are recorded in the most affected artifact (library choices → dependency manifest, patterns → architecture, API design → contract artifact). Each includes: what was decided, alternatives considered, rationale, trade-offs accepted.

When learnings accumulate around a decision (3+ entries), the session briefing suggests revisitation. Advisory only.

The Critic verifies that major decisions were made deliberately: new dependencies have rationale, architectural patterns are documented, contract surface changes triggered investigation.

---

## C4: Active Context

*Consolidates: R4 (Living Artifacts) + R5 (Effective Learning) + R7 (Scalable Context Management)*

### Core Idea
Context — artifacts, learnings, CLAUDE.md, project state — must be actively managed, not passively accumulated. Everything in the context window has a cost. If it's stale, it's worse than absent (wrong guidance). If it's bloated, it dilutes the important parts. Active context management means: detect staleness, surface relevance, enforce budgets, and compact aggressively.

### Context Hierarchy (token budgets)

| Tier | What | Budget | Delivery |
|------|------|--------|----------|
| Always loaded | CLAUDE.md (Prawduct block) | <4K tokens | System prompt |
| Session start | Session briefing | <400 tokens | Hook stdout → system-reminder |
| Session start | Active learnings | <3K tokens | Read at session start |
| On demand | Methodology guides, full artifacts, reference learnings | Unbounded | Read when entering specific work |

CLAUDE.md for mature projects is **shorter** than for new projects. Extract rules into enforceable mechanisms, then remove the prose.

### Artifact Staleness (content-based detection)

Each artifact type has content-based staleness indicators:
- `data-model.md`: model class/field names in code don't match artifact.
- `test-specifications.md`: actual test count diverges from documented count.
- `architecture.md`: top-level modules/directories exist that aren't mentioned.
- `dependency-manifest.md`: dependency files list items not in manifest.

**Session-start scan** (lightweight, <5 seconds): Checks high-signal indicators. Surfaces findings in session briefing.

**Critic deep check** (at review time): Full content-based freshness analysis. Bidirectional — code matches artifacts AND artifacts describe code.

When staleness signals accumulate (3+ stale artifacts, stale architecture, dependency drift), the session briefing escalates to a health check recommendation.

**Documentation debt**: When an artifact is known-stale but not the current priority, record it explicitly in project-state.yaml rather than letting it accumulate silently.

### Learning Lifecycle

**Two tiers:**
- **Active rules** (~20-30 items, <3K tokens): Concise, actionable, always loaded. Format: "When X, do Y because Z."
- **Reference knowledge** (unbounded): Detailed root-cause analysis, edge cases, technology-specific gotchas. Loaded on demand.

**Lifecycle stages:**
- **Provisional**: Single incident. May be wrong or over-specific.
- **Confirmed**: Validated across 2+ incidents or explicitly confirmed by user. Promoted to active rules.
- **Incorporated**: Encoded into methodology, templates, or hooks. Archived from active rules.

**Relevance surfacing**: Session-start hook filters learnings by recent git changes, file types, directory patterns, and user-stated intent. The session briefing includes only relevant learnings, not all learnings.

**Recurrence escalation**: When a learning is violated again despite being captured, it's promoted to structural enforcement (hook check, Critic rule, or CLAUDE.md repetition).

### Artifact Compaction

After 30+ chunks, artifacts grow unwieldy. Guidance for compaction:
- Build plan: Reduce completed chunks to `{id, name, status: complete}`.
- Change log: Keep last ~10 entries; git has the full history.
- Large artifacts (500+ lines): Summary section at top with key decisions.

---

## Implementation Priorities

### P0 — Address first (these cause the most damage)
1. **C2: Structural Compliance** — If the LLM doesn't follow the process, nothing else matters. Session briefing, compliance canary, and subagent briefing are the delivery mechanisms for everything else.
2. **C3: Investigated Changes** — Uninvestigated decisions compound into permanent constraints. Silent cross-boundary breaks are the most expensive bugs.

### P1 — Address next (these prevent scaling)
3. **C1: Work-Scaled Governance** — Phase model causes friction; continuous model enables everything else.
4. **C4: Active Context** — Staleness detection, learning lifecycle, and context budgets keep governance sustainable as projects grow.

---

## Context Window Impact Analysis

The consolidation from 10 requirements to 4 isn't just aesthetic — it directly reduces the context window footprint:

**v4 CLAUDE.md Prawduct block**: ~3,200 tokens (current)

**Projected v5 CLAUDE.md Prawduct block**: ~2,800 tokens (target)

How this is possible despite adding capabilities:
- **C1** replaces verbose phase descriptions with a single size×type matrix. Fewer words, same information.
- **C2** moves enforcement from CLAUDE.md prose ("remember to run tests") to hooks (compliance canary catches it). Less CLAUDE.md text needed because the hook does the remembering.
- **C3** is methodology guidance (loaded on demand when entering a build chunk), not CLAUDE.md content. CLAUDE.md needs only: "Investigate before committing to major decisions or changes that cross boundaries."
- **C4** is primarily hook logic (staleness scan) and file structure (learning tiers). CLAUDE.md needs only: "Active rules in learnings.md. Reference knowledge in learnings-detail.md. Session briefing surfaces what's relevant."

**Session briefing** adds ~200-400 tokens per session but replaces the LLM reading 3-5 files (~4,000-8,000 tokens) at session start. Net savings: ~4,000+ tokens.

**Subagent briefing** adds 0 tokens to the builder's context (it's a file on disk that subagents read).

**Critic instructions** are in a separate agent context — 0 tokens in the builder's window regardless of how comprehensive they are.

**Net effect**: v5 should consume **fewer** total context tokens than v4 for the same or better governance, by shifting work from CLAUDE.md prose to hooks, session briefings, and Critic instructions.

---

## Migration: v4 → v5 (Zero User Action Required)

Existing v4 products (like Discodon) must upgrade automatically. The infrastructure for this already exists — v5 extends it.

### Existing Chain (already working in v4)
1. User opens product directory in Claude Code.
2. `.claude/settings.json` fires `product-hook clear` as SessionStart hook.
3. `product-hook` calls `try_sync()`, which locates the framework repo (sibling `../prawduct` or `PRAWDUCT_FRAMEWORK_DIR`).
4. `prawduct-sync.py` **auto-pulls the framework repo** (`git pull --ff-only`, best-effort, silent on failure). This means pushing v5 to the prawduct remote is sufficient — product repos pull it automatically on next session start.
5. `prawduct-sync.py` reads `sync-manifest.json`, compares template hashes, updates changed files.
6. CLAUDE.md block content is updated; user content outside blocks preserved.
7. Hook prints sync actions to stdout (model sees them as system-reminder).

### What v5 Adds to This Chain
The sync script gains a **version-aware migration step** that runs before normal sync when it detects a v4 manifest:

**Files updated via existing sync mechanisms:**
- `CLAUDE.md` Prawduct block — replaced with v5 template (shorter, restructured for LLM attention). User content outside blocks untouched.
- `tools/product-hook` — gains session briefing generation, compliance canary, staleness scan, subagent briefing assembly.
- `.prawduct/critic-review.md` — updated for goal-based Critic scope.
- `.claude/settings.json` — hooks updated if new hook events needed.

**Files restructured by migration:**
- `learnings.md` → split into active rules (stays as `learnings.md`, pruned to confirmed rules <3K tokens) + reference knowledge (new `learnings-detail.md`, full history preserved).
- `project-state.yaml` → `current_phase` retired, `health_check` tracking section added.
- `sync-manifest.json` → version bumped, new file entries added.

**New files placed (if missing):**
- `.prawduct/.subagent-briefing.md` — generated by hook on first session start.
- `.prawduct/artifacts/boundary-patterns.md` — template for project-specific contract surface documentation (placed once, like project-preferences).

**What migration does NOT touch:**
- Any file outside `.prawduct/`, `tools/`, and `.claude/` — product source code is never modified.
- User content outside PRAWDUCT:BEGIN/END blocks in CLAUDE.md.
- Artifact files in `.prawduct/artifacts/` (except templates being placed for the first time).
- Git history — migration creates new files and modifies tracked files; the user commits when ready.

### Migration Safety
- Migration runs as part of `try_sync()` — wrapped in try/except, best-effort, never blocks session start.
- If migration fails partway, normal sync still works on next session (idempotent — checks current state, not "has migration run").
- If the framework repo hasn't been updated to v5 yet, sync runs normally with v4 templates. Migration only triggers when v5 templates are detected in the framework.
- The session briefing reports what migration did: "v5 migration: updated CLAUDE.md block, split learnings, added staleness scan."

### What the User Sees
First session after prawduct framework is updated to v5:
```
Framework sync: updated CLAUDE.md, product-hook, critic-review.md, settings.json
v5 migration: split learnings (42 active rules → 18 active + 24 reference), added health tracking
IMPORTANT: CLAUDE.md was updated by framework sync. Re-read CLAUDE.md now.

== SESSION BRIEFING ==
Project: Discodon | Work: none active
Stale artifacts: test-specifications.md (documented: 4157 tests, found: 4444)
Active learnings (3 most relevant): [...]
```

Subsequent sessions: normal v5 behavior. No migration needed.

---

## Resolved Design Decisions

1. **Hook complexity**: Acceptable to increase; we'll reduce if needed.
2. **Contract surfaces**: Detected via LLM investigation, not declared or static heuristics.
3. **CLAUDE.md**: Partially generated, block-marked. Project edits outside blocks preserved.
4. **Model capabilities**: Design for current; adapt to improvements later.
5. **Critic**: Keep and strengthen. Goal-based scope, not fixed checklist.
6. **Subagent governance**: Yes. Briefing file on disk, Critic pattern.
7. **Session briefing**: Structured stdout → system-reminder. ~200-400 tokens.
8. **Staleness detection**: Content-based, not timestamps.
9. **Learning relevance**: All available signals (git, file types, user intent).
10. **Migration**: Automated big-bang on next session start.
11. **Boundary investigation trigger**: "Appears to modify a contract" threshold; tune in practice.
12. **Health check cadence**: Emergent from staleness signals, not fixed schedule.

## Remaining Open Questions

None. Implementation questions will emerge during build planning.

---

## Relationship to Existing Principles

| Principle | Current State | v5 Strengthening |
|-----------|--------------|-----------------|
| #1 Tests Are Contracts | Weakens at scale | C2 (compliance canary), C3 (test tiers) |
| #3 Living Documentation | Reactive (Critic catches drift) | C4 (proactive staleness detection) |
| #4 Reasoned Decisions | Principle only | C3 (decision research, rationale capture) |
| #5 Honest Confidence | Principle only | C3 (flag when research is limited) |
| #6 Bring Expertise | Discovery-only prior art | C3 (continuous research during building) |
| #10 Proportional Effort | Phase-based scaling | C1 (size × type scaling) |
| #13 Independent Review | Critic after chunks | C1 (scaled review), C3 (boundary checks) |
| #17 Close the Learning Loop | Write-heavy loop | C4 (lifecycle, relevance surfacing, recurrence escalation) |
| #21 Governance Is Structural | Two hooks | C2 (session briefing, compliance canary, subagent briefing) |

---

## Traceability: Original → Consolidated

| Original | Consolidated Into | What Happened |
|----------|------------------|---------------|
| R1: Continuous Governance | C1 | Core of C1 — size scaling |
| R2: Active Compliance | C2 | Core of C2 — structural mechanisms |
| R3: Cross-Boundary Coherence | C3 | Boundary investigation half of C3 |
| R4: Living Artifacts | C4 | Staleness detection in C4 |
| R5: Effective Learning | C4 | Learning lifecycle in C4 |
| R6: Mature Project Patterns | C1 | Work types + health check in C1 |
| R7: Scalable Context Management | C4 | Context hierarchy + budgets in C4 |
| R8: Exception Governance | C2 | Specific momentum-vulnerable behavior in C2 |
| R9: Subagent Governance | C2 | Subagent briefing mechanism in C2 |
| R10: Researched Decisions | C3 | Decision research half of C3 |
