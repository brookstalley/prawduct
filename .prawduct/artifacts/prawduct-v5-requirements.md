# Prawduct v5 Requirements — Scaling Governance for Maturing Projects

## Problem Statement

Prawduct successfully guides projects from discovery through initial build. However, as projects mature (Discodon: 24K LOC, 42K test LOC, 60+ build chunks, 4,400+ tests), governance effectiveness degrades in predictable ways:

1. **LLM adherence decays with context scale.** The larger the codebase and conversation history, the more likely the LLM skips methodology — building without specs, shipping without tests, swallowing exceptions. Users must manually remind Claude to follow the process it was given.

2. **Phase boundaries are artificial.** Prawduct treats discovery → planning → building → reflection as a lifecycle, but real projects are continuously doing all four. A bug fix needs micro-discovery. A new feature mid-iteration needs planning. The phase model creates a mental gap where "we're past planning" becomes an excuse to skip it.

3. **Cross-boundary coherence breaks silently.** Backend API changes break frontend consumers. Integration tests either don't exist or aren't run. The Critic catches individual chunk quality but not system-wide coherence.

4. **Documentation drift is inevitable without automation.** Specifications written during planning become fiction after 20+ chunks. Manual scrubs work but only when someone remembers to ask for them.

5. **Learnings accumulate without changing behavior.** The learning loop captures insights but doesn't reliably prevent recurrence. Known patterns repeat because the context window doesn't always include the relevant learning at decision time.

## Evidence Base

These requirements are grounded in observations from Discodon (15+ build sessions, 60+ chunks) and Prawduct's own iteration history. Key evidence:

- Discodon commit 732be18: dedicated documentation scrub fixing stale Radix UI claims, wrong token tool names, outdated status fields — artifacts had drifted for weeks
- Discodon learnings explicitly capture "Always verify frontend types match actual backend response" — a coherence failure that tests caught late
- Prawduct learning: "Judgment alone won't interrupt momentum" — LLM doesn't self-impose process interruptions
- Prawduct learning: "Filed-away observations don't change behavior" — write-only learning loops
- Prawduct learning: "Reactive systems can't detect missing things" — validation catches what's wrong but not what's absent
- Critic gate never fired for 40+ sessions because it was watching `artifacts/build-plan.md` while the plan lived in `project-state.yaml`
- Discodon learnings.md grew to 42KB despite guidance saying "keep under 3,000 tokens"

## Design Constraints

1. **Prawduct remains LLM-executable.** No external services, no CI/CD dependencies. Everything runs in Claude Code sessions.
2. **Products remain self-contained.** No runtime dependency on framework repo. Sync mechanism propagates improvements.
3. **Proportional effort.** Small projects shouldn't feel heavier. Governance scales with risk and codebase size.
4. **Hook complexity is acceptable when justified.** We can take more complexity than v4 has today. If it becomes a problem we'll reduce again. But prefer principles + structural nudges where they work.
5. **Automated migration.** Existing v4 products transition via automated big-bang migration on next session start. Users should not need to run init or migrate manually.
6. **Prawduct-managed content in CLAUDE.md must be clearly block-marked.** Developers must know what not to edit, and the framework must preserve edits outside its blocks. CLAUDE.md can be partially generated.
7. **The Critic is the strongest part of Prawduct — protect it.** The separate-agent Critic review model works exceptionally well. All changes must preserve or strengthen Critic capabilities, never degrade them.
8. **Subagents must follow Prawduct principles.** When the builder delegates to subagents, governance context (principles, project-specific rules, active learnings) must be passed along.
9. **Design for current model capabilities.** Do not assume future model improvements. We'll adapt Prawduct in response to model changes, not in anticipation of them.

---

## R1: Continuous Governance (replaces phase-based model)

### Problem
The discovery → planning → building → reflection sequence implies each happens once. Real projects cycle through all four continuously. A developer fixing a bug doesn't think "I'm in building phase" — they investigate (discovery), plan a fix (planning), implement (building), and verify (reflection). The phase model makes this feel like it doesn't apply.

### Requirements

**R1.1** Replace the phase lifecycle with a continuous governance model. Every unit of work (feature, bugfix, refactor, optimization) follows a scaled version of the same cycle: understand → plan → build → verify. The methodology should describe this as the natural rhythm, not as phases to graduate through.

**R1.2** Scale governance to work size, not project phase:
- **Trivial** (typo fix, config change): Build + verify. No planning artifact needed.
- **Small** (bug fix, minor feature): Understand context + build + verify + update affected artifacts.
- **Medium** (new feature, significant refactor): Explicit requirements + build plan + build + Critic review + artifact updates.
- **Large** (new subsystem, architectural change): Full discovery + planning + chunked build + Critic review per chunk.

**R1.3** Provide a work-size classification heuristic based on blast radius, not developer intuition. Examples: touching 1-2 files = trivial/small; touching 5+ files or adding a new dependency = medium; new directory structure or API surface = large.

**R1.4** Retire `current_phase` from project-state.yaml. Replace with a work-in-progress tracker that describes what's being done now and at what governance level.

### Success Criteria
- A developer starting a bug fix in a mature project gets appropriately-scaled governance without being told "you're in iteration phase, read iteration.md."
- The same framework instructions work for a greenfield project's first feature and for chunk 80 of a mature product.

---

## R2: Active Compliance (LLM stays on-method without reminders)

### Problem
As codebases grow, CLAUDE.md competes with more context for the LLM's attention. Methodology instructions get diluted. The LLM defaults to its training behavior (just start coding) rather than the prescribed process (understand first, then plan, then build with tests).

### Requirements

**R2.1** Identify the specific behaviors that degrade at scale and classify them:
- **Self-regulatable** (LLM does these naturally with principles): Code quality, naming conventions, error handling patterns, following established architecture.
- **Momentum-vulnerable** (LLM skips these under pressure): Reading methodology before building, running full test suite, invoking Critic, updating artifacts after changes, writing tests alongside code.

**R2.2** For momentum-vulnerable behaviors, add structural reinforcement beyond CLAUDE.md prose:
- Hook-based reminders at session start that surface the specific rules most likely to be skipped (not all rules — the ones that degrade at scale).
- Pre-commit or pre-chunk verification that tests were actually run (not just "tests pass" in prose — evidence of test execution).

**R2.3** The session-start hook should perform a "governance health check" that surfaces:
- Whether tests pass right now (before any changes).
- Which artifacts are potentially stale (modified files vs. artifact last-update dates).
- Any learnings relevant to the current state (e.g., known fragile areas).

**R2.4** CLAUDE.md instructions for mature projects should be restructured for LLM attention:
- Critical rules (test before commit, don't swallow exceptions, run integration tests) at the TOP, not buried in methodology files the LLM may not read.
- Repetition of key rules in the places where they're most likely to be violated (e.g., "run integration tests" appears in both the build cycle AND the commit checklist).

**R2.5** Add a "compliance canary" — a lightweight check the hook runs before session end that detects the most common governance failures:
- Code changed but no tests added or modified.
- API contract changed but integration tests not run.
- New dependency added but dependency manifest not updated.

### Success Criteria
- Over a 10-session sequence, the LLM follows methodology without user reminders in 8+ sessions.
- When the LLM does skip a step, the hook catches it before the session ends.

---

## R3: Cross-Boundary Coherence

### Problem
In systems with multiple layers (API + frontend, service + database, process + subprocess), changes to one layer can break another. Prawduct's current chunk-based review catches issues within a chunk but not across boundaries established in prior chunks.

### Requirements

**R3.1** Define "contract surfaces" — boundaries where components interact:
- API endpoints (request/response schemas)
- Database schemas (migrations, model definitions)
- Inter-process communication (message formats, protocols)
- Frontend/backend type contracts
- Configuration interfaces

**R3.2** Contract surfaces should be **detected, not declared** — and detection should use **LLM/subagent investigation, not static heuristics.** Requiring LLMs to declare boundaries introduces the same adherence problem we're solving. And static grep heuristics are brittle — they break when project structure evolves and can't reason about semantic relationships (e.g., a renamed field that's still the same concept).

Instead, when the builder modifies files that could affect contract surfaces, the governance system should:
- Spawn a focused subagent to investigate cross-boundary impact. The subagent reads the changed files, identifies what contracts they participate in (API schemas, shared types, message formats), and greps for consumers across layer boundaries.
- The subagent reports: which boundaries were crossed, which consumers may be affected, and whether those consumers' tests cover the change.
- The builder must address the subagent's findings before the chunk is complete.
- The Critic verifies that boundary investigation was performed when cross-layer files were modified.

Per-project boundary patterns should be documented in an artifact (e.g., "route handlers are in `src/web/routes/`, frontend consumers are in `src/web/frontend/src/`") to help the investigation subagent focus, but the subagent reasons about what it finds rather than mechanically executing grep patterns.

**R3.3** Integration tests should be a first-class artifact category. The test specification should distinguish:
- Unit tests (single component, mocked dependencies)
- Integration tests (multiple components, real interactions)
- Contract tests (verify that producer and consumer agree on interface shape)
- End-to-end tests (full system flow)

Products should declare which test levels exist and when each should run.

**R3.4** The build cycle should include a "boundary check" step: after implementing changes, explicitly verify that no contract surfaces were modified without updating consumers. The Critic should check for this.

**R3.5** For projects with frontend + backend, require an API contract artifact (OpenAPI spec, TypeScript types, or equivalent) that is the source of truth for both sides. Changes to backend response shapes must update this artifact, and frontend must consume from it.

### Success Criteria
- A backend API change that breaks the frontend is caught before the chunk is declared complete.
- Contract surface changes trigger explicit consumer verification in the build cycle.

---

## R4: Living Artifacts (automated staleness detection)

### Problem
Specifications written during planning become stale as the codebase evolves. The Critic's bidirectional freshness check helps but only runs when invoked. Between Critic reviews, artifacts drift silently.

### Requirements

**R4.1** Each artifact should declare what makes it stale, using **content-based heuristics** (not timestamps). Examples:
- `data-model.md` is stale if model class names or field names in code don't match what the artifact describes.
- `test-specifications.md` is stale if the actual test count diverges significantly from the documented count, or test files exist that aren't referenced.
- `architecture.md` is stale if top-level modules or directories exist that aren't mentioned, or if described modules no longer exist.
- `dependency-manifest.md` is stale if `package.json`, `pyproject.toml`, or equivalent lists dependencies not in the manifest.

Content-based detection is more complex than timestamps but avoids false positives (file touched but content unchanged) and catches true positives that timestamps miss (artifact never updated despite many code changes).

**R4.2** The session-start hook should run a lightweight staleness scan and report which artifacts may need attention. Not blocking — informational, surfaced via the session briefing (stdout). The scan should be fast (<5 seconds) — check high-signal indicators (test count, directory listing, dependency file hashes), not full content analysis.

**R4.3** After each chunk (or at Critic review time), the Critic performs a deeper content-based freshness check. The Critic already does bidirectional checks; extend this to include the content-based staleness indicators from R4.1.

**R4.4** Provide guidance for artifact compaction. After 30+ chunks, some artifacts (build plan, change log) grow unwieldy. Define when and how to archive completed work while preserving relevant context.

**R4.5** Establish a "documentation debt" concept analogous to tech debt. When an artifact is known-stale but fixing it isn't the current priority, record the debt explicitly rather than letting it accumulate silently.

### Success Criteria
- Stale artifacts are surfaced within 1-2 sessions of becoming stale, not after 20+ chunks.
- Users never need to manually request a "documentation scrub" — the system surfaces the need proactively.

---

## R5: Effective Learning at Scale

### Problem
Learnings accumulate but don't reliably prevent recurrence. The Discodon learnings file grew to 42KB. Many learnings are too specific to be useful outside their original context. The learning loop is write-heavy and read-light.

### Requirements

**R5.1** Separate learnings into two tiers:
- **Active rules** (~20-30 items): Concise, actionable, always loaded. Format: "When X, do Y because Z." These are the behaviors that have been validated across multiple sessions.
- **Reference knowledge** (unbounded): Detailed root-cause analysis, edge cases, technology-specific gotchas. Loaded on demand when relevant, not at session start.

**R5.2** Learnings should have a lifecycle:
- **Provisional**: Captured from a single incident. May be wrong or over-specific.
- **Confirmed**: Validated across 2+ incidents or explicitly confirmed by user. Promoted to active rules.
- **Incorporated**: The learning has been encoded into methodology, artifact templates, or hook logic. Can be archived from active rules.

**R5.3** The session-start hook should surface learnings relevant to the current work, not all learnings. If the session involves frontend work, surface frontend-related learnings. If it involves API changes, surface API coherence learnings. Grep-based heuristic on recent git changes is sufficient.

**R5.4** When a learning is violated (the same mistake is made again despite being captured), this is a signal that the learning needs to be promoted to a structural enforcement (hook check, Critic rule, or CLAUDE.md repetition). Track recurrence.

**R5.5** Provide pruning guidance: learnings that haven't been referenced in N sessions and aren't in the "confirmed" tier can be moved to the reference file. Keep the active rules file lean.

### Success Criteria
- Active rules file stays under 3,000 tokens even for large projects.
- When a known pattern recurs, the relevant learning is in-context at decision time.
- Learnings that keep recurring despite being captured get escalated to structural enforcement.

---

## R6: Mature Project Patterns

### Problem
Prawduct has no explicit guidance for patterns that only matter in mature projects: tech debt management, performance optimization, deprecation, emergency hotfixes, and large-scale refactoring.

### Requirements

**R6.1** Document these mature-project work patterns with governance guidance:
- **Emergency hotfix**: Minimal governance path — fix + test + verify. Artifact updates can follow.
- **Tech debt paydown**: Requires explicit scoping (what debt, why now, blast radius). Tests must not decrease. Architecture artifacts must be updated if structure changes.
- **Performance optimization**: Requires baseline measurement before changes. NFR artifact must define target. Regression testing must cover performance, not just correctness.
- **Deprecation/removal**: Requires consumer audit (who uses this?), migration path, and phased removal.
- **Large refactor**: Requires architecture artifact update FIRST (target state), then incremental migration with tests green at every step.

**R6.2** Add a "work type" to the governance model alongside work size. The work type influences which checks are most important:
- Feature: spec compliance, test coverage, artifact freshness
- Bugfix: root cause analysis, regression test, learning capture
- Refactor: behavior preservation (tests don't change), architecture coherence
- Optimization: baseline measurement, performance regression testing
- Debt paydown: scope discipline (don't expand scope), architecture freshness

**R6.3** Provide a health check protocol that assesses:
- Test health: Are tests still meaningful? Any test rot? Coverage gaps?
- Artifact health: Which artifacts are stale? Which are no longer relevant?
- Dependency health: Are dependencies current? Any known vulnerabilities?
- Architecture health: Does the architecture artifact still describe reality?

The health check is **triggered by accumulating staleness signals from R4.2, not by a fixed cadence.** The session-start staleness scan (R4.2) reports individual stale artifacts. When enough signals accumulate (3+ stale artifacts, or any stale architecture artifact, or dependency file changed but manifest not updated), the session briefing escalates from specific staleness findings to a health check recommendation. This avoids arbitrary thresholds that are too frequent for small projects and too rare for large ones — the trigger scales naturally with project complexity and drift rate.

`project-state.yaml` tracks the last health check date and findings:
```yaml
health_check:
  last_full_check: 2026-03-01
  last_check_findings: "3 stale artifacts updated, dependency manifest refreshed"
```

The session briefing includes this context: "Health: last full check 2026-03-01 (14 files changed, 2 chunks completed since)." This is advisory — never blocking. The user or LLM decides when to act. When a health check runs, it updates the tracking fields.

### Success Criteria
- A developer doing a performance optimization gets different governance emphasis than one adding a feature.
- Health checks are suggested when drift is actually detected, not on an arbitrary schedule.
- The suggestion scales naturally — small projects rarely trigger it, large active projects trigger it more often.

---

## R7: Scalable Context Management

### Problem
As projects grow, the amount of context needed for effective governance exceeds what fits in a session. CLAUDE.md, learnings, artifacts, and project state compete for attention. The LLM can't read everything at session start, and not reading everything means missing relevant context.

### Requirements

**R7.1** Define a context hierarchy:
- **Always loaded** (CLAUDE.md, active rules): <4K tokens. Contains the rules most likely to be needed. This content must be ruthlessly concise.
- **Loaded at session start** (project state, governance health check output): <2K tokens. Current state and immediate concerns.
- **Loaded on demand** (methodology guides, full artifacts, reference learnings): Read when entering a specific work type. The hook or CLAUDE.md directs when to read what.

**R7.2** CLAUDE.md for mature projects should be shorter than for new projects, not longer. As methodology is internalized into hooks, templates, and Critic checks, the prose instructions in CLAUDE.md should shrink. Extract rules into enforceable mechanisms, then remove the prose. All Prawduct-managed content must live inside clearly marked blocks (extending the existing PRAWDUCT:BEGIN/END pattern) so that:
- Developers can see at a glance what is framework-managed vs. project-specific.
- The sync mechanism can update framework blocks without touching project content.
- A project can remove Prawduct entirely by deleting the marked blocks.
- Project-specific edits outside blocks are always preserved across syncs.

**R7.3** The session-start hook should produce a concise "session briefing" that tells the LLM:
- What the project is and its current state (1-2 sentences).
- What governance rules are most relevant right now (based on recent work patterns).
- What known risks or stale artifacts need attention.
- What the active learnings are (or a pointer to them).

This briefing replaces the LLM reading 5+ files at session start.

**R7.4** Provide artifact summarization guidance. Large artifacts (500+ lines) should have a summary section at the top that captures the key decisions without requiring reading the full document. The full content remains for Critic review and detailed reference.

### Success Criteria
- Session start takes <30 seconds of hook processing.
- The LLM has governance-relevant context without reading more than 2 files at session start.
- CLAUDE.md for a mature project is <=60% the size of CLAUDE.md for a new project.

---

## R8: Exception and Error Governance

### Problem
As Discodon grew, error handling patterns degraded. Exceptions were swallowed, error recovery was inconsistent, and the LLM's natural tendency to "make things work" led to `except Exception: pass` patterns that hid real bugs.

### Requirements

**R8.1** Establish error handling as a first-class cross-cutting concern with full pipeline coverage:
- **Discovery**: Surface error handling approach (already exists).
- **Planning**: Error handling architecture artifact — defines the project's error taxonomy, handling patterns, and what must never be silently caught.
- **Building**: Explicit rule in build cycle: "Never catch broad exceptions without re-raising or logging. Never add `except Exception: pass`."
- **Critic**: Check for exception swallowing, overly broad catches, and missing error propagation.

**R8.2** Define a "never swallow" list that projects can customize:
- Default: `Exception`, `BaseException`, `RuntimeError` should never be caught without logging + re-raising.
- Project-specific additions (e.g., database connection errors, authentication failures).

**R8.3** The Critic should specifically look for error handling regressions:
- New `except` blocks that are broader than necessary.
- Error paths that don't have test coverage.
- Removed error handling that was previously present.

### Success Criteria
- `except Exception: pass` never appears in code without the Critic flagging it.
- Error handling patterns are consistent across the codebase, governed by a declared approach.

---

## R10: Researched Decisions (recognize, investigate, present)

### Problem
LLMs treat all implementation decisions with equal (low) deliberation. "Use SQLite" and "name this variable `count`" get the same amount of thought. But "use SQLite" might lock the product into a single-process architecture for its entire life, while variable naming is inconsequential. The LLM defaults to whatever's in its training data — often a reasonable choice, but not necessarily the *right* choice for this project's language, scale, goals, and constraints.

Prawduct's existing prior art search (discovery.md) partially addresses this during initial discovery, but:
- It only runs during discovery, not during building when most implementation decisions are actually made.
- It searches for existing *products*, not for implementation patterns, libraries, or architectural approaches.
- It doesn't recognize when a decision is major vs. routine.
- It doesn't scale research depth to decision impact.

Evidence from this session: researching how Claude Code hook output is delivered to the LLM (stdout vs. stderr, system-reminder injection) fundamentally changed the R7 design. If we'd just gone with "print to stderr" without research, the entire session briefing mechanism would have been invisible to the model. That research took minutes and changed the outcome.

Evidence from Discodon: library choices (py-cord, Lavalink, ZMQ) and pattern choices (multi-process architecture, PUB/SUB messaging, entity-per-process model) were made early and never revisited. Some were excellent; others created ongoing friction captured in 6+ learnings about ZMQ gotchas alone. More research upfront would have surfaced alternatives or at least set expectations.

### Requirements

**R10.1 — Decision recognition.** The builder must recognize when it's about to make a decision that constrains future options. A decision is "major" when it has one or more of these properties:
- **Lock-in**: Hard to reverse later (database choice, communication protocol, auth strategy, API style).
- **Pervasive**: Will be imported/used across many files or modules (state management pattern, error handling strategy, logging framework).
- **Structural**: Shapes the architecture (multi-process vs. single-process, monolith vs. services, sync vs. async).
- **External dependency**: Introduces a dependency on a library, service, or standard that the project will rely on long-term.

Routine decisions (variable names, local control flow, file organization within established patterns) are not major and don't need research.

**R10.2 — Proactive research.** When the builder recognizes a major decision, it should research before committing. Research depth scales to decision impact:

- **Medium-impact** (pervasive pattern, non-core dependency): Quick research in the main context — a few web searches, check library health/maintenance status, review common alternatives. Minutes, not hours. Stays in the builder's context because the research is brief and the findings are immediately actionable.

- **High-impact** (lock-in, structural, core dependency): **Spawn a research subagent.** The subagent investigates thoroughly and returns a concise recommendation with alternatives, trade-offs, and cautionary tales. Using a subagent for high-impact research has three benefits:
  - **Context preservation.** Reading 10 web pages of comparison material pollutes the builder's context with information useless after the decision is made. The subagent absorbs it and returns only the synthesis.
  - **Fresh perspective.** The builder may already be leaning toward an approach. A research subagent hasn't committed to anything — it's more likely to genuinely evaluate alternatives. This is the same independence principle that makes the Critic effective.
  - **Depth without delay.** The builder can continue other work while the research subagent investigates, or can pause and wait for a focused recommendation — either way, the research is thorough without fragmenting the build context.

Research should focus on:
- Best practices *in the context of this project* — language, runtime, scale expectations, structural characteristics.
- Established patterns, not just libraries. "How do Python projects at this scale typically handle inter-process communication?" is more useful than "what ZMQ alternatives exist?"
- Cautionary tales. What goes wrong with this choice at scale? What are the known footguns?
- Library health signals: maintenance activity, community size, breaking change history, whether the project is in active development or maintenance mode.

When web search is available, use it — training data may be stale or lack context about library maintenance status, community health, or recent breaking changes. When it's not available, use domain knowledge and flag the limitation (Principle #5: Honest Confidence).

**R10.3 — Contextual presentation.** How the research is surfaced depends on the user's engagement style, following the Prawduct communication spectrum:

- **Low engagement / trusting** ("just build it", short answers, accepting suggestions without pushback): Make the decision, briefly state what was chosen and the key reason. "I'm using `aiohttp` for HTTP calls — it's the standard async choice for Python and avoids adding a sync dependency in our async codebase." Don't ask.

- **Medium engagement / collaborative** (asks questions, provides opinions on some things, defers on others): Present the recommendation with context. "For inter-process communication, I'd recommend ZMQ over raw sockets or gRPC — it handles the PUB/SUB pattern we need without the overhead of gRPC's code generation. The main trade-off is ZMQ's learning curve around socket lifecycle. Sound good, or would you prefer to explore alternatives?"

- **High engagement / opinionated** (has strong preferences, names specific technologies, asks "why not X?"): Present options with trade-offs. "For IPC, the main contenders are ZMQ, gRPC, and Redis Pub/Sub. Here's how they compare for our use case: [comparison]. I'd lean toward ZMQ because [reasons], but gRPC would be better if we expect to add non-Python services later. What's your preference?"

The builder should calibrate based on signals already captured: the user expertise profile in `project-state.yaml`, the engagement patterns observed in the current session, and explicit preferences in `project-preferences.md`. When uncertain, default to medium engagement (recommend with context, invite feedback).

**R10.4 — Record the decision.** Major decisions and their rationale should be captured — not in a separate decisions log (another artifact to maintain), but in the artifact most affected:
- Library choices → dependency manifest.
- Architectural patterns → architecture artifact.
- API design choices → API contract artifact.

Each recorded decision includes: what was decided, what alternatives were considered, why this choice was made, and what trade-offs were accepted. This is Principle #4 (Reasoned Decisions) applied specifically to major implementation choices.

**R10.5 — Revisitation trigger.** Learnings that accumulate around a specific decision are a signal that the decision may need revisiting. If `learnings.md` has 3+ entries about ZMQ gotchas, the session briefing should note: "ZMQ has accumulated 6 learnings — consider whether the IPC choice is still serving the project well." This is advisory, not blocking.

**R10.6 — Critic verification.** The Critic should check for unreasoned major decisions:
- New external dependencies added without rationale in the dependency manifest.
- Architectural patterns introduced without being captured in the architecture artifact.
- Implementation choices that appear to lock in a specific approach (e.g., tight coupling to a specific database or framework) without documented reasoning.

The Critic doesn't second-guess the decisions — it verifies they were made deliberately, not by default.

### Success Criteria
- Major decisions are recognized as such before they're committed to, not after 20+ chunks of building on them.
- Research happens before commitment, with depth proportional to impact.
- The user receives the right level of involvement — not interrogated about every library, not surprised by foundational choices made silently.
- Decision rationale is captured in existing artifacts, making it available for future sessions and Critic review.
- Accumulated friction around a past decision triggers a revisitation suggestion.

---

## Implementation Priorities

Based on the severity and frequency of the problems observed:

### P0 — Address immediately (these cause the most damage)
1. **R2: Active Compliance** — LLM adherence is the #1 problem. If the LLM doesn't follow the process, everything else is moot.
2. **R3: Cross-Boundary Coherence** — Silent integration failures are the most expensive bugs.
3. **R10: Researched Decisions** — Uninvestigated foundational choices compound into permanent constraints. This must be present from the start because early decisions have the highest lock-in.

### P1 — Address next (these prevent scaling)
4. **R1: Continuous Governance** — Phase model causes friction; continuous model enables everything else.
5. **R4: Living Artifacts** — Staleness detection prevents the documentation scrub problem.

### P2 — Address to mature (these improve long-term quality)
6. **R7: Scalable Context Management** — Makes governance sustainable as projects grow.
7. **R5: Effective Learning** — Makes accumulated wisdom actually useful.
8. **R6: Mature Project Patterns** — Fills the gap for post-initial-build work.
9. **R8: Exception Governance** — Specific instance of a broader "best practice enforcement" need.
10. **R9: Subagent Governance** — Ensures delegated work meets the same standards.

---

## R9: Subagent Governance

### Problem
As projects grow, builders delegate work to subagents for parallelism. Subagents operate in separate contexts without access to Prawduct methodology, principles, or project-specific learnings. They produce code that may violate conventions, skip tests, or ignore cross-cutting concerns — and the builder may not catch these gaps in review.

### Requirements

**R9.1** When the builder delegates to a subagent, it must pass governance context:
- Project principles (concise — not full CLAUDE.md, but the critical rules).
- Project-specific conventions (from project-preferences.md or equivalent).
- Active learnings relevant to the delegated work.
- Testing requirements (test alongside code, don't weaken existing tests).
- Error handling rules (never swallow exceptions, project-specific patterns).

**R9.2** The SessionStart hook generates `.prawduct/.subagent-briefing.md` — a single file assembled from project state that the builder includes in delegation prompts. This mirrors the proven Critic pattern: one file, read from disk by the subagent. The builder's delegation prompt includes a single instruction ("Read `.prawduct/.subagent-briefing.md` for project conventions and governance rules") rather than composing context from 5 files each time.

The briefing is assembled from:
- Static governance rules (universal Prawduct: test alongside code, never weaken tests, never swallow exceptions).
- Project conventions (extracted from `project-preferences.md`).
- Active learnings (extracted from `learnings.md`).

The briefing regenerates every session start. Within a session, the source files rarely change, making mid-session staleness a non-issue. The Critic reviews subagent output anyway, catching any convention violations the briefing missed.

**R9.3** The Critic should review subagent-produced code with the same rigor as builder-produced code. Since the Critic already reviews all changes in the chunk, this is primarily about ensuring the Critic instructions call out common subagent failure modes:
- Missing tests for delegated work.
- Convention violations (naming, error handling, logging patterns).
- Ignoring cross-cutting concerns (observability, accessibility).

**R9.4** The builder remains responsible for subagent output. Delegation is not an excuse for governance gaps. The build cycle should explicitly state that delegated work must be verified before the chunk is complete.

### Success Criteria
- Subagent-produced code follows the same conventions as builder-produced code.
- The Critic catches subagent governance gaps at the same rate as builder gaps.

---

## Resolved Design Decisions

These were open questions that have been decided:

1. **Hook complexity**: Acceptable to increase. We can take more complexity; we'll reduce if it becomes a problem. (Constraint 4)

2. **Contract surfaces: detected via LLM investigation, not declared or static heuristics.** A focused subagent investigates cross-boundary impact when contract-adjacent files change. Per-project boundary patterns documented in an artifact help the subagent focus, but it reasons about what it finds rather than mechanically executing greps. (R3.2)

3. **CLAUDE.md: partially generated, block-marked.** Prawduct-managed content in clearly marked blocks. Project-specific content outside blocks always preserved. Hook can generate session-specific preamble within blocks. (Constraint 6, R7.2)

4. **Model improvements: design for current capabilities.** Do not anticipate improvements. We'll adapt Prawduct in response to model changes. (Constraint 9)

5. **Critic model: keep and strengthen.** The separate-agent Critic is the strongest part of Prawduct. Continue this pattern. For continuous governance (R1), scale Critic invocation to work size — not every trivial change needs full Critic review, but medium+ work does. (Constraint 7)

6. **Subagent governance: yes, explicitly.** Governance context must be passed to subagents. Builder remains responsible for subagent output. (R9)

7. **Session briefing format: structured stdout from SessionStart hook.** Hook prints a concise structured briefing to stdout, which Claude Code injects as a `system-reminder` — guaranteed delivery, no behavioral compliance needed, no git noise. CLAUDE.md carries stable methodology; the briefing carries volatile state (current work, stale artifacts, relevant learnings). Format is semi-structured prose with labeled sections (~200-400 tokens). (R2.3, R7.3)

8. **Staleness detection: content-based, not timestamp-based.** Check semantic indicators (test counts, model class names, directory structure, dependency lists) rather than file modification times. Avoids false positives and catches true drift. Lightweight scan at session start; deeper analysis at Critic review time. (R4.1)

9. **Critic scaling: goal-based, not rule-based.** The Critic receives goals (ensure quality, catch regressions, verify coherence) and signals (files changed, quantity, work type, work size) and reasons about what to check. No fixed 10-check list for every review — the Critic decides scope based on what it sees. This preserves the Critic's strength (independent reasoning) while avoiding wasted effort on trivial changes. (R1, Constraint 7)

10. **Learning relevance: all available signals.** The hook uses git changes, file types, directory patterns, AND user-stated intent (if provided) to surface relevant learnings. More signals = better relevance. (R5.3)

11. **v4 → v5 migration: automated big-bang.** Existing products transition via an automated migration tool (like the existing `prawduct-migrate.py` pattern). Users should not need to run init manually. The sync mechanism or hook detects v4 state and runs migration automatically on next session start. (Constraint 5)

12. **Boundary investigation trigger: "appears to modify a contract."** The builder spawns a boundary-investigation subagent when changes appear to modify a contract surface — not on every cross-layer file touch. This needs tuning in practice; start with the quieter threshold and loosen if things are missed. (R3.2)

13. **Subagent briefing: generated at session start as a file on disk.** The SessionStart hook assembles `.prawduct/.subagent-briefing.md` from project-preferences, active learnings, and static governance rules. The builder includes it in delegation prompts with a single file-read instruction — mirroring the Critic's proven pattern. Regenerated every session; source files rarely change within a session. (R9.2)

14. **Health check cadence: emergent from staleness detection, not fixed schedule.** No separate trigger mechanism. R4.2's staleness scan runs at session start; when enough signals accumulate, the session briefing escalates to a health check recommendation. `project-state.yaml` tracks last health check date/findings for context. Advisory only, never blocking. (R6.3)

## Remaining Open Questions

None. All design decisions have been resolved. Implementation questions will emerge during build planning.

---

## Relationship to Existing Principles

These requirements don't replace Prawduct's 22 principles — they strengthen the mechanisms that enforce them. Specifically:

| Principle | Current State | v5 Strengthening |
|-----------|--------------|-----------------|
| #1 Tests Are Contracts | Strong in principle, weakens at scale | R2 (compliance verification), R3 (integration test tiers) |
| #3 Living Documentation | Reactive (Critic catches drift) | R4 (proactive staleness detection) |
| #10 Proportional Effort | Phase-based scaling | R1 (work-size scaling), R6 (work-type scaling) |
| #13 Independent Review | Critic after chunks | R1 (scaled review), R3 (boundary checks) |
| #17 Close the Learning Loop | Write-heavy loop | R5 (learning lifecycle, relevance surfacing) |
| #21 Governance Is Structural | Two hooks | R2 (compliance canary), R4 (staleness scan) |
| #4 Reasoned Decisions | Principle only, no enforcement | R10 (major decision recognition, research, rationale capture) |
| #6 Bring Expertise | Discovery-only prior art search | R10 (continuous research during building, contextual presentation) |
| #5 Honest Confidence | Principle only | R10 (flag when research is limited by available tools) |
