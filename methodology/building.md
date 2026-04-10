# Building: Turning Plans Into Working Software

Building is where plans meet reality. Every unit of work — whether it's the first feature of a new project or chunk 80 of a mature one — follows the same cycle: **understand → plan → build → verify.** What changes is the depth, determined by the work's size and type.

## Sessions and Work Cycles

A **session** is one Claude Code invocation — the period between the `clear` hook firing (at startup or `/clear`) and the `stop` hook firing (at exit). The git baseline, reflection gate, and Critic gate all scope to the session.

A **work cycle** is one unit of work with its own governance: understand → plan → build → verify → Critic → reflect. Multiple work cycles can happen within a single session.

**Context compaction** is a context-management event within a session — it is NOT a session boundary. Compaction does not trigger hooks, does not reset the git baseline, and does not create a governance checkpoint. Anything that must survive compaction — plans, decisions, rationale, chunk definitions — must be written to a file before compaction occurs. Conversation context is ephemeral; artifacts persist.

**`/clear` between work cycles is recommended** for cleaner governance. It resets the git baseline (so the next work cycle's canary only sees its own changes), archives the previous reflection, and starts fresh context. But it is not required — multiple work cycles within a single session work correctly.

The stop hook is a **final safety net**: reflection captured, Critic invoked if code was built against a plan, and advisory **compliance canary** checks run. Per-work-cycle governance (Critic after each chunk, reflection after each significant action) is the methodology's responsibility, not the hook's.

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

**Establish a clean baseline.** Before starting the first work cycle of a session, establish a clean state:

- *Tests*: Run the full test suite. Every test must pass. Fix any failures — there is no "pre-existing" exception.
- *Git state*: Check for uncommitted changes. Commit or stash unrelated work. A dirty working tree blurs the boundary between what you built and what was already there. For medium+ work, create a feature branch (`feature/...`, `fix/...`) unless `project-preferences.md` allows direct commits.
- *Canary findings*: Review any compliance findings from the session briefing. Address or explicitly acknowledge each one.

There is no "pre-existing" exception — for tests, for broad exceptions, for stale artifacts, for anything. If you encounter a problem during your session, it is your responsibility to fix it or explicitly flag it with a reason it can't be fixed now. The concept of "pre-existing" is an escape hatch that allows quality to degrade permanently. Every session starts clean.

**Read the spec.** Read the chunk's entry in `.prawduct/artifacts/build-plan.md` and any referenced artifacts. Understand what this chunk delivers, what its acceptance criteria are, and what it depends on. If anything is ambiguous, flag it before building — don't guess silently. Validate that files, modules, and components referenced in the chunk plan still exist — plans go stale when the codebase evolves (module renames, component deletions, API changes). A quick check before starting saves significant rework. Also run `/learnings [this chunk's focus]` to check for relevant project rules and preferences before coding.

**Persist plans immediately.** When scope evolves — new chunks, plan changes, gaps discovered — write the updated plan to `build-plan.md` now. A plan that exists only in conversation will be lost on compaction or session end.

**Write tests.** Tests come first or alongside implementation, not after. Tests are your specification made executable. If you can't write the test, you don't understand the requirement well enough to implement it.

Test at the right level:
- **Unit tests** for individual functions and logic
- **Integration tests** for component interactions, data flow, state transitions
- **End-to-end tests** for critical user flows and acceptance criteria
- **Property-based tests** for invariants stated in the chunk. See `build-governance.md` for tool-per-language guidance.

Depth is proportionate to risk.

**Implement.** Write the code that makes the tests pass. Follow the project's coding conventions (see `.prawduct/artifacts/project-preferences.md`). Prefer simplicity — the right amount of abstraction is the minimum needed for the current chunk.

Add observability alongside features, not after. If the observability strategy calls for structured logging, log from chunk 1.

**Update artifacts as you go.** When your implementation changes something an artifact describes — API surface, data model fields, architecture components — update that artifact now, as part of implementation. Don't defer artifact updates to a separate step at the end. Artifact drift is the #1 recurring quality issue at scale; updating inline prevents it.

**CLAUDE.md is instructions, not documentation.** It tells Claude how to work here — dev commands, test workflows, key conventions. Architecture descriptions, config tables, and component inventories belong in `docs/` or `.prawduct/artifacts/`. When a build plan says "update CLAUDE.md," add only what a new session needs to work effectively. Target: project-specific content under ~150 lines.

**Verify.** Two layers:

- *Code:* Run the full suite. First check `python3 tools/product-hook test-status` — exit 0 means saved evidence still covers the tree; re-running is wasteful. After, write `.prawduct/.test-evidence.json` with the `fingerprint=` line.
- *Product:* Launch it, call it, inspect output. If infrastructure dependencies are declared, verify against real instances — mocks are not verification.

Scale to chunk significance. When you can't verify, say so (Principle 5).

**Gate waivers.** When a gate is genuinely N/A, write `.prawduct/.gates-waived` as `{"critic": "reason", "pr": "...", "reflection": "..."}`. String reasons required. Auto-cleared next session. Doc-only edits are skipped automatically.

**Critic review.** Run `/critic` — it's in the build plan's "Done when" steps. The Critic runs as a separate agent with its own context and restricted tools.

**Resolve findings.** Fix blocking findings before proceeding. Address warnings. Document disagreements with rationale.

**Reflect.** The Critic just gave you independent feedback — the highest-signal moment for learning. What did the Critic catch that you missed? Does it match a pattern in `learnings.md`? Capture learnings immediately if the finding reveals a blind spot.

**Verify artifacts are current.** Confirm artifacts reflect the code. The Critic checks bidirectional freshness. CLAUDE.md is an instruction file, not an artifact — the Critic warns when its project content exceeds ~150 lines.

**Update build plan Status.** Mark the chunk `[x]` in `build-plan.md`'s Status section. Update the Context line with what's done and what's next — this is the cross-session handoff.

## Session Scope Discipline

Limit work cycles to 1-3 chunks for medium+ work. Critic review quality degrades when reviewing many chunks at once — the reviewer loses focus across a large diff. Context compaction within a long session can lose governance context (plans, rationale, decisions that existed only in conversation).

When you've completed 2-3 chunks, or the user switches tasks, it's time for `/clear`. **Do NOT recommend `/clear` until handoff is complete** — the next session starts cold. Complete first:

1. **Commit** (tests passing). 2. **Critic** (if medium+ and not run yet). 3. **Persist** pending decisions/plans to artifact files. 4. **Backlog** deferred work to `.prawduct/backlog.md`. 5. **Update build plan Status** in `build-plan.md` (mark chunks, update Context). 6. **Reflect** to `.prawduct/.session-reflected`. 7. **Then say** `/clear` with what was persisted.

Never signal completion before handoff is done — "Ready for next session" implies steps 1-6 are finished. Do the work, then signal.

The `/clear` hook auto-generates `.prawduct/.session-handoff.md` from the build plan Status, reflection, Critic findings, and changed files. The next session's briefing surfaces the context inline and points to the handoff file for detail.

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
- **"Read `.prawduct/build-governance.md` for the build cycle, then `.prawduct/.subagent-briefing.md` for project conventions and learnings."**
- Instructions to run the full test suite before and after implementation

**Parallel chunks:** When multiple chunks have no dependency between them, build them in parallel using separate subagents. Each subagent gets its own chunk spec. The main agent coordinates: launch all independent chunks, wait for results, run the combined test suite, then proceed with Critic review. Merge conflicts between parallel chunks are the main agent's responsibility.

When running 2+ parallel subagents in a shared worktree, they can see each other's partial changes — this can confuse agents that check git status. Use worktree isolation (`isolation: "worktree"`) for truly independent chunks. The compliance canary may fire O(agents x edits) during parallel work — this noise is expected and can be acknowledged in the session reflection.

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

**All tests pass, always.** There is no "pre-existing" exception. Diagnose and fix every failure.

**Test coverage is proportionate.** Match coverage to risk. Every product needs at least: happy path, error handling for likely failures, and edge cases for anything involving money, data, or safety.

## The Critic

After medium+ work, invoke the Critic as a separate agent. The Critic receives signals (files changed, work type, work size) and reasons about what to check. It has seven prioritized goals:

1. **Nothing Is Broken** — Test coverage adequate, no security vulnerabilities.
2. **Nothing Is Missing** — Every requirement implemented or explicitly descoped.
3. **Nothing Is Unintended** — No unlisted dependencies, no undocumented decisions.
4. **Everything Is Coherent** — Artifacts consistent with code, documentation doesn't drift.
5. **Decisions Were Deliberate** — Major decisions have rationale, boundary changes investigated.
6. **The System Can Be Understood** — Error handling present, logging appropriate.
7. **The Design Is Sound** — Good encapsulation, appropriate coupling, no unnecessary complexity or duplication.

After goals, the Critic cross-checks learnings and reconciles the backlog (flagging resolved items).

For medium/large reviews, the Critic uses a coordinator pattern — spawning parallel subagents for correctness (1-3), design (4, 7), and sustainability (5-6) to improve throughput.

See `agents/critic/SKILL.md` (framework) or `.prawduct/critic-review.md` (products) for full instructions.

**The Critic takes time.** Reviews take 1-5 minutes. Do not check on it or hurry it along. **While it reviews, do your own deep scrub**: re-read changes for completeness, correctness, DRY, encapsulation, test coverage, UX, and documentation. Self-review often pre-resolves Critic findings.

**Never write Critic findings yourself.** If the Critic agent is slow, wait. Do not write `.critic-findings.json` "based on" expected output — self-authored review evidence is governance fraud. If the agent fails, tell the user and re-invoke.

**Blocking findings** must be resolved before proceeding. **Warnings** should be addressed — the Critic only uses WARNING when confident something is a real issue. **Notes** are genuinely ambiguous — the Critic isn't sure and the builder should decide. If you disagree with a finding, think carefully before dismissing — the Critic catches blind spots the builder can't see.

## Creating Pull Requests

**Default: wait for the user to ask.** Do not create PRs proactively. Only use `/pr` when the user explicitly requests it ("PR this", "create a PR", "push this up", "open a PR"). If `project-preferences.md` sets `PR creation: automatic`, you may create PRs after Critic review passes without being asked.

Use `/pr` for the full PR lifecycle. It invokes the PR reviewer agent for independent release-readiness assessment — a fresh-eyes review of the full changeset, complementing the Critic's per-chunk reviews. The `/pr` command is context-aware: it detects git state and routes to create, update, merge, or status automatically.

See `agents/pr-reviewer/SKILL.md` (framework) or `.prawduct/pr-review.md` (products) for review criteria. After merge, `/pr` cleans up the build plan. Without `/pr`, do it manually.

## Exception Handling

Catch specific exceptions. Broad catches (`except Exception`, empty `catch {}`) hide bugs and make debugging difficult.

When a broad catch is genuinely necessary — system boundary error handlers, event loop recovery, top-level process supervisors — mark it explicitly:

- Python: `except Exception as e:  # prawduct:ok-broad-except — reason`
- JS/TS: `catch (e) { // prawduct:ok-broad-except — reason`

The compliance canary skips marked lines. The Critic verifies that marked catches log with context and are at genuine system boundaries. The marker means "reviewed and intentional," not "exempt from review."

Broad catches that swallow errors without logging (`except Exception: pass`, empty `catch {}`) are always findings — no marker can justify silencing errors.

## Common Traps

**Test corruption**: Weakening tests to make them pass. Fix the code, never the test.

**Silent requirement dropping**: Implementing 9 of 10 requirements and hoping nobody notices.

**Gold plating**: Adding features the spec didn't ask for. Scope Discipline (Principle 11).

**Test-last**: Writing tests that pass against existing implementation documents behavior including bugs.

**Ignoring the Critic**: Dismissing findings without reflection.

**Verification theater**: Claiming verification without exercising the product. All tests pass against mocks but the product has never touched real dependencies. If project-state.yaml declares infrastructure dependencies, verify against them.

**Mock-as-implementation**: Using mocks during development and never replacing them with real integrations. If the data model says "Postgres" and the code uses an in-memory dict, that's unfinished — not passing.

**"Pre-existing" dismissal**: Labeling a quality issue as "pre-existing" to justify ignoring it. There is no pre-existing exception. If you found it, it's yours to fix or flag.

**Uninvestigated decisions**: Major technology or architectural choices without research. Lock-in, pervasiveness, structural impact, and external dependencies warrant investigation.

**Boundary blindness**: Modifying a contract surface without checking consumers. The compliance canary catches this at session end, but checking proactively is cheaper.

**Pacing blindness**: Asking implementation questions when the user is waiting for progress. Decide autonomously on minor details unless genuinely blocked.

**Unnecessary backwards compatibility**: Adding migration paths or fallbacks when there's no existing deployment to migrate. Backwards compatibility is a requirement to be elicited, not an assumption.

**Opinionated defaults without configuration**: Shipping a workflow-affecting feature with one hardcoded behavior. If a feature could reasonably work two ways, make it a preference in `project-preferences.md` with a safe default.
