# Building: Turning Plans Into Working Software

Building is where plans meet reality. Every unit of work — whether it's the first feature of a new project or chunk 80 of a mature one — follows the same cycle: **understand → plan → build → verify.** What changes is the depth, determined by the work's size and type.

## Work-Scaled Governance

There are no phases. The depth of governance scales with two dimensions:

**Size** (determines governance depth):
- **Trivial** (typo, config change): Build + verify.
- **Small** (bug fix, minor feature): Understand context + build + verify + update affected artifacts.
- **Medium** (new feature, significant refactor): Requirements + build plan + build + Critic review + artifact updates.
- **Large** (new subsystem, architectural change): Full discovery + planning + chunked build + Critic per chunk.

**Type** (determines governance emphasis):
- **Feature**: Spec compliance, test coverage, artifact freshness.
- **Bugfix**: Root cause analysis, regression test, learning capture.
- **Refactor**: Behavior preservation (tests don't change), architecture coherence.
- **Optimization**: Baseline measurement before changes, performance regression testing.
- **Debt paydown**: Scope discipline, architecture freshness.
- **Emergency hotfix**: Minimal path — fix + test + verify. Artifacts can follow.

Classification heuristic: 1-2 files = trivial/small; 5+ files or new dependency = medium; new directory structure or API surface = large.

## The Build Cycle

**Establish a green baseline.** Before starting the first chunk of a session, run the full test suite. Every test must pass. If any test fails — for any reason — fix it before proceeding. There is no "pre-existing failure" exception. A failing test means something is wrong: the code, the environment, a dependency, or the test itself. Diagnose and fix it. This is your clean baseline; without it, you can't distinguish new breakage from old.

**Read the spec.** Read the chunk's entry in `.prawduct/artifacts/build-plan.md` and any referenced artifacts. Understand what this chunk delivers, what its acceptance criteria are, and what it depends on. If anything is ambiguous, flag it before building — don't guess silently.

**Write tests.** Tests come first or alongside implementation, not after. Tests are your specification made executable. If you can't write the test, you don't understand the requirement well enough to implement it.

Test at the right level:
- **Unit tests** for individual functions and logic
- **Integration tests** for component interactions, data flow, state transitions
- **End-to-end tests** for critical user flows and acceptance criteria

Depth is proportionate to risk.

**Implement.** Write the code that makes the tests pass. Follow the project's coding conventions (see `project-preferences.md`). Prefer simplicity — the right amount of abstraction is the minimum needed for the current chunk.

Add observability alongside features, not after. If the observability strategy calls for structured logging, log from chunk 1. Use instrumentation in layers: start with what the framework gives for free, add declarative markers, add contextual attributes, and reserve manual instrumentation for critical paths.

**Verify.** Two layers:

- *Code verification:* Run all tests — the full suite, not just what you wrote.
- *Product verification:* Confirm the product works as its users or consumers would experience it. Launch it, call it, run it, inspect its output. If infrastructure dependencies are declared in project-state.yaml, verify against real instances — not just mocks. A system that passes all tests against a mocked database but never touches real persistence is not verified.

Scale verification to chunk significance. When you can't verify directly, say what you can't verify and why (Principle 5).

**Request Critic review.** Mandatory for medium+ work. Invoke the Critic as a separate agent (via the Task tool). Tell it to read `.prawduct/critic-review.md` (product repos) or `agents/critic/SKILL.md` (framework). The stop hook enforces this.

**Resolve findings.** Fix blocking findings before proceeding. Address warnings. Document disagreements with rationale.

**Reflect.** The Critic just gave you independent feedback — the highest-signal moment for learning. What did the Critic catch that you missed? Does it match a pattern in `learnings.md`? Capture learnings immediately if the finding reveals a blind spot.

**Update state and artifacts.** Record what was built. If the chunk changed behavior that artifacts describe — test counts, model fields, architecture components, API surfaces — update those artifacts now. The Critic checks bidirectional freshness: code matches artifacts AND artifacts describe code.

**Compact completed state.** When `project-state.yaml` grows large (the hook warns at ~40KB), compact completed sections: reduce finished chunks to `{id, name, status: complete}`, trim test history, keep the last ~10 change log entries.

## Investigated Changes

Two categories of action require investigation before commitment:

### Boundary Investigation (when changes cross contract surfaces)

Contract surfaces are boundaries where components interact: API endpoints, database schemas, IPC, frontend/backend type contracts, configuration interfaces. See `.prawduct/artifacts/boundary-patterns.md` for this project's documented contract surfaces.

When you modify files that affect a contract surface:
1. **Recognize** the boundary crossing. Any change to a producer that has known consumers.
2. **Investigate** by spawning a focused subagent. It reads the changes, identifies affected contracts, greps for consumers across layer boundaries, and reports: which boundaries were crossed, which consumers may be affected, and whether tests cover the change.
3. **Incorporate** findings into your implementation. Update consumers if needed. Add integration tests.
4. **Record** what was investigated and what was found. The Critic verifies investigation occurred.

### Decision Research (when choices constrain future options)

A decision is "major" when it has: **lock-in** (hard to reverse), **pervasiveness** (used across many files), **structural impact** (shapes architecture), or **external dependency** (long-term reliance on a library/service).

Research scales to impact:
- **Medium-impact** (pervasive pattern, non-core dependency): Quick research in the main context. A few web searches, check library health.
- **High-impact** (lock-in, structural, core dependency): Spawn a research subagent. It investigates thoroughly — best practices, established patterns, library health signals — and returns a concise recommendation. Your context stays clean.

Presentation scales to user engagement:
- **Low engagement**: Decide and state briefly.
- **Medium engagement** (default): Recommend with context, invite feedback.
- **High engagement**: Present options with trade-offs, let user choose.

Record major decisions in the most affected artifact with: what was decided, alternatives considered, rationale, trade-offs accepted.

## Delegating Work to Subagents

**When the user asks you to do work in a subagent, do it.** This is a direct instruction from the user (Principle 22).

Subagent delegation is especially valuable when:
- The user explicitly requests it
- Multiple chunks are independent and can be built in parallel
- A chunk involves focused, well-scoped work that benefits from a clean context
- The main context is getting large

**How to delegate:** Spawn a subagent and give it:
- The chunk spec and referenced artifacts
- The project directory path
- **"Read `.prawduct/.subagent-briefing.md` for project conventions and governance rules."** This file is generated at session start with governance rules, project preferences, and active learnings.
- Instructions to run the full test suite before and after implementation

**Parallel chunks:** When multiple chunks have no dependency between them, build them in parallel using separate subagents. Each subagent gets its own chunk spec. The main agent coordinates: launch all independent chunks, wait for results, run the combined test suite, then proceed with Critic review. Merge conflicts between parallel chunks are the main agent's responsibility.

**What stays in the main agent:** Critic review, reflection, and state updates. The subagent does implementation; the main agent maintains governance.

## Working With Specs

Specs are guides, not scripture. When implementation reveals problems:

**If the spec is wrong**, flag it. Propose the fix. Update the spec to match reality.

**If the spec is ambiguous**, pick the most likely interpretation, implement it, and note the ambiguity.

**If the spec is incomplete**, surface it. Make reasonable choices for minor gaps; escalate significant ones.

**If you can't implement something**, say so explicitly. Never silently drop a requirement (Principle 2).

## Test Discipline

Tests are the most important artifact you produce during building. They're contracts that define correct behavior, and they protect against regression as the codebase grows.

**Tests are behavioral.** Test what the code does, not how it does it.

**Tests are independent.** No shared mutable state, no ordering dependency.

**Tests never weaken.** Test count doesn't decrease. Assertion depth doesn't decrease. Fix the code, never the test. This is Principle 1, and it's a bright line.

**All tests pass, always.** There is no "pre-existing failure" exception. Diagnose and fix every failure.

**Test coverage is proportionate.** Match coverage to risk. Every product needs at least: happy path, error handling for likely failures, and edge cases for anything involving money, data, or safety.

## The Critic

After medium+ work, invoke the Critic as a separate agent. The Critic receives signals (files changed, work type, work size) and reasons about what to check. It has six prioritized goals:

1. **Nothing Is Broken** — Tests pass, count hasn't decreased.
2. **Nothing Is Missing** — Every requirement implemented or explicitly descoped.
3. **Nothing Is Unintended** — No unlisted dependencies, no undocumented decisions.
4. **Everything Is Coherent** — Artifacts consistent with each other and with code. Infrastructure assumptions match declared dependencies.
5. **Decisions Were Deliberate** — Major decisions have rationale, boundary changes triggered investigation.
6. **The System Can Be Understood** — Error handling present, logging appropriate.

See `agents/critic/SKILL.md` (framework) or `.prawduct/critic-review.md` (products) for full instructions.

**Blocking findings** must be resolved before proceeding. **Warnings** should be addressed. **Notes** are informational. If you disagree with a finding, think carefully before dismissing — the Critic catches blind spots the builder can't see.

## Common Traps

**Test corruption**: Weakening tests to make them pass. Fix the code, never the test.

**Silent requirement dropping**: Implementing 9 of 10 requirements and hoping nobody notices.

**Gold plating**: Adding features the spec didn't ask for. Scope Discipline (Principle 11).

**Test-last**: Writing tests that pass against existing implementation documents behavior including bugs.

**Ignoring the Critic**: Dismissing findings without reflection.

**Verification theater**: Claiming verification without exercising the product. Honest confidence (Principle 5). A common variant: all tests pass against mocked infrastructure, but the product has never been tested against real dependencies. If project-state.yaml declares infrastructure dependencies, verify against them.

**Mock-as-implementation**: Using mocks during development and never replacing them with real integrations. Mocks are for test isolation, not for avoiding infrastructure work. If the data model says "persisted to Postgres" and the code uses an in-memory dictionary, that's an unfinished implementation — not a passing test suite.

**"Pre-existing" dismissal**: Labeling a failing test as pre-existing to justify moving on.

**Uninvestigated decisions**: Making a major technology or architectural choice without research. Lock-in, pervasiveness, structural impact, and external dependencies all warrant investigation before commitment.

**Boundary blindness**: Modifying a contract surface without checking consumers. The compliance canary catches this at session end, but checking proactively is cheaper.

**Pacing blindness**: Asking implementation questions when the user is waiting for progress. Decide autonomously on minor details unless genuinely blocked.
