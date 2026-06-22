# Building: Turning Plans Into Working Software

Building is where plans meet reality. Every unit of work — whether it's the first feature of a new project or chunk 80 of a mature one — follows the same cycle: **understand → plan → build → verify.** What changes is the depth, determined by the work's size and type.

## Sessions and Work Cycles

A **session** is one Claude Code invocation — the period between the `clear` hook firing (at startup or `/clear`) and the `stop` hook firing (at exit). The git baseline, reflection gate, and Critic gate all scope to the session.

A **work cycle** is one unit of work with its own governance: understand → plan → build → verify → Critic → reflect. Multiple work cycles can happen within a single session.

**Context compaction** is a context-management event, not a session boundary: no hooks, no baseline reset, no governance checkpoint. Anything that must survive — plans, decisions, rationale, chunk definitions — must be written to a file first.

**`/clear` between work cycles is recommended** for cleaner governance. It resets the git baseline (so the next cycle's canary only sees its own changes), archives the previous reflection, and starts fresh context. Not required — multiple work cycles within a single session work correctly.

**Working in a git worktree.** A work cycle composes in a worktree — run it (including `/prawduct:critic` and `/prawduct:pr`) *from the worktree*, where the gates resolve `.prawduct/` state to the worktree (STH-4K7N); no review-in-primary or raw-`gh` workaround is needed. One edge: starting in the primary checkout and entering a worktree *mid*-cycle leaves the SessionStart markers in primary (gate readers fail safe) — launch, or `/clear`, in the worktree to avoid it.

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

## Before You Build: Confidence Check

Before any non-trivial work cycle, answer three questions in one sentence each:

1. **What problem are we solving?** (Observable, not abstract.)
2. **What does success look like?** "User can do X and see Y," not "it works."
3. **What's out of scope?** What you're deliberately not doing.

If any can't be answered, requirements aren't clear enough (Principle 6 — Requirements Precede Code). Three options: **close the gap** with one targeted question or an inference to confirm; **sketch and confirm** by writing the answers and presenting them; or **proceed knowingly** by declaring the unknowns in the plan's Requirements Confidence as Medium or Low. Fill what you can infer yourself and record each as a vetoable assumption; surface only consequential, unverifiable unknowns, and early. Don't silently build on guesses — that's how unclear requirements become debt. Apply for any chunk that touches behavior; skip for trivial (typo, config). For unclear or multi-file work, Plan Mode (read-only explore + interview before execution) is the native clarify-before-build vehicle. Mirrors the discovery-side self-assessment, the `[ASSUMPTION: …]` recording format, and research triggers (see `methodology/discovery.md` "Calibrate Rigor").

### A Requirement Surfaced Mid-Build

The Confidence Check runs at a chunk's *start*; requirements also arrive *during* a build, and the #1 way they enter undocumented is designing them fluently **in chat** and flowing them into code with no artifact between. **Triggered, not always-on:** when a tripwire fires — a noun the artifacts don't contain, design you can't trace to a parent one rung up, a taxonomy invented in chat, the same thing revised 2–3×, or an "are we sure / is this solved" signal — *stop, name it, write or locate the parent requirement, then resume.* Never silently *invent* a requirement any more than you'd *drop* one (Principle 6, mirror of #2).

## The Build Cycle

**Establish a clean baseline.** Before starting the first work cycle of a session, establish a clean state:

- *Tests*: Run the full test suite. Every test must pass. Fix any failures — there is no "pre-existing" exception.
- *Git state*: Check for uncommitted changes. Commit or stash unrelated work. A dirty working tree blurs the boundary between what you built and what was already there. For medium+ work, create a feature branch (`feature/...`, `fix/...`) unless `project-preferences.md` allows direct commits.
- *Canary findings*: Review any compliance findings from the session briefing. Address or explicitly acknowledge each one.

There is no "pre-existing" exception (tests, broad exceptions, stale artifacts, anything). If you encounter a problem, fix it or flag it with a reason it can't be fixed now. "Pre-existing" is an escape hatch that permanently degrades quality. Every session starts clean.

**Read the spec.** Read the chunk's entry in `.prawduct/artifacts/build-plan.md` and any referenced artifacts. Understand what this chunk delivers, what its acceptance criteria are, and what it depends on. If anything is ambiguous, flag it before building — don't guess silently. Validate that files, modules, and components referenced in the chunk plan still exist — plans go stale when the codebase evolves (module renames, component deletions, API changes). A quick check before starting saves significant rework. Also run `/prawduct:learnings [this chunk's focus]` to check for relevant project rules and preferences before coding.

**Persist plans immediately.** When scope evolves during a work cycle — new chunks emerge, the plan changes, gaps are discovered — write the updated plan to `build-plan.md` immediately. Conversation context is ephemeral; artifacts persist. A plan that exists only in conversation will be lost on compaction or session end. This is the most common way knowledge is lost across sessions.

**Write tests.** Tests come first or alongside implementation, not after. Tests are your specification made executable. If you can't write the test, you don't understand the requirement well enough to implement it.

Test at the right level:
- **Unit tests** for individual functions and logic
- **Integration tests** for component interactions, data flow, state transitions
- **End-to-end tests** for critical user flows and acceptance criteria

Depth is proportionate to risk.

**Implement.** Write the code that makes the tests pass. Follow the project's coding conventions (see `.prawduct/artifacts/project-preferences.md`). Prefer simplicity — the right amount of abstraction is the minimum needed for the current chunk.

Add observability alongside features, not after. If the observability strategy calls for structured logging, log from chunk 1.

**Update artifacts as you go.** When your implementation changes something an artifact describes — API surface, data model fields, architecture components — update that artifact now, as part of implementation. Don't defer artifact updates to a separate step at the end. Artifact drift is the #1 recurring quality issue at scale; updating inline prevents it.

**CLAUDE.md is instructions, not documentation.** It tells Claude how to work here — dev commands, test workflows, key conventions. Architecture descriptions, config tables, and component inventories belong in `docs/` or `.prawduct/artifacts/`. When a build plan says "update CLAUDE.md," add only what a new session needs to work effectively. Target: project-specific content under ~150 lines.

**Verify.** Two layers:

- *Code:* Run the full suite once. Check `prawduct-hook test-status` first — exit 0 means this session's evidence passed, so re-running is wasteful. Record via `prawduct-hook test-evidence record` — or `--from-junit <f>` to ingest an existing run instead of re-running (TST-7M3K). Non-default suites: `test_command:`/`tests_dirs:`.
- *Product:* Launch it, call it, inspect output. If infrastructure dependencies are declared, verify against real instances — mocks are not verification.

Scale to chunk significance. When you can't verify, say so (Principle 5).

**Gate waivers.** When a gate is genuinely N/A, write `.prawduct/.gates-waived` as `{"critic": "reason", "pr": "...", "reflection": "..."}`. String reasons required. Auto-cleared next session. Doc-only edits are skipped automatically.

**In-flight background work is not a waiver case.** If the Critic/reflection gate blocks only because a tracked background `Workflow`/`Task` is still producing the diff, **wait — don't waive**: the gate *will* be satisfied this session once the job lands, and waiving would skip the Critic the completed work still needs. The repeated block is an expected reminder, not an error to escape. (Rough edge `STH-3W7F`: `.gates-deferred` to quiet the wait without skipping the Critic is pending.)

**Critic review.** Run `/prawduct:critic` (no args) — the SKILL infers mode from git + build-plan state via `prawduct-hook infer-critic-mode` and records `mode_chosen_by`. Pass an explicit mode (e.g. `/prawduct:critic cumulative`) only to override; report override cases so inference can improve. The Critic runs as a separate agent with restricted tools. See Modes below for per-mode behavior.

**Resolve findings.** Fix blocking findings before proceeding. Address warnings. Document disagreements with rationale.

**Reflect — now, not at session end.** Append to `.prawduct/.session-reflected`: what the chunk delivered, what the Critic caught, what surprised you. A paragraph is enough. Add a rule to `learnings.md` only if this cycle produced one. Chunk-boundary reflection makes `/clear` instant later.

**Operator verification (F10).** Visual / live-integration chunks: enqueue in `.prawduct/operator-verification.md` and mark `Visual change: yes`. `/prawduct:pr create` blocks on pending entries when `operator_verification_required: true`.

**Verify artifacts are current.** Confirm artifacts reflect the code. The Critic checks bidirectional freshness. CLAUDE.md is an instruction file, not an artifact — the Critic warns when its project content exceeds ~150 lines.

**Update build plan Status.** Mark the chunk `[x]` in `build-plan.md`'s Status section. Update the Context line with what's done and what's next — this is the cross-session handoff. (When `views_enabled`, Status/release-notes/scope_rollups are derived views — add a tagged change-log entry and run regen-views instead.)

## Session Scope Discipline

Limit work cycles to 1-3 chunks for medium+ work. Critic review quality degrades when reviewing many chunks at once — the reviewer loses focus across a large diff. Context compaction within a long session can lose governance context (plans, rationale, decisions that existed only in conversation).

**Complete required governance at chunk boundaries, then affirmatively signal when `/clear` is safe.** Critic review, reflection capture, plan persistence, and backlog updates must be done before the chunk is complete — and the user should not have to guess.

When you've completed 2-3 chunks, or the user switches tasks, it's time for `/clear`. Before signaling, complete in order:

1. **Commit** (tests passing). 2. **Critic** (if medium+ and not run yet) — resolve blocking findings. 3. **Persist** pending decisions/plans to artifact files. 4. **Backlog** — file/close affected items via `/prawduct:backlog`. 5. **Update build plan Status** in `build-plan.md` (mark chunks, update Context). 6. **Reflection** — confirm `.prawduct/.session-reflected` has an entry for this chunk; add a one-paragraph synthesis only if a cross-cutting pattern emerged.

End your chunk-complete message with a line like *"Chunk N complete — Critic passed, reflection captured, build plan updated. Safe to `/clear` when you're ready."* Do NOT signal completion until steps 1–6 are done — "ready for next session" and "safe to /clear" both imply handoff is finished. If a required step genuinely cannot be completed (e.g., Critic agent failed), say so explicitly and flag the gap for the user.

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

A decision is "major" when it has: **lock-in** (hard to reverse — a persisted format/schema is ALWAYS lock-in, reversal cost not LOC: enumerate the questions the data must answer — its consumers' future queries — before designing fields), **pervasiveness** (used across many files), **structural impact** (shapes architecture), **external dependency** (long-term reliance on a library/service), or **volatility** (correctness depends on timely / fast-moving / post-cutoff data — knowledge gaps want reasoning, volatility gaps want web research; see `methodology/discovery.md` "Calibrate Rigor").

Research scales to impact:
- **Medium-impact** (pervasive pattern, non-core dependency): Quick research in the main context. A few web searches, check library health.
- **High-impact** (lock-in, structural, core dependency): Spawn a research subagent. It investigates thoroughly — best practices, established patterns, library health signals — and returns a concise recommendation. Your context stays clean.

Presentation scales to user engagement:
- **Low engagement**: Decide and state briefly.
- **Medium engagement** (default): Recommend with context, invite feedback.
- **High engagement**: Present options with trade-offs, let user choose.

Record major decisions in the most affected artifact with: what was decided, alternatives considered, rationale, trade-offs accepted.

## Delegating Work to Subagents

**When the user asks you to do work in a subagent, do it.** This is a direct instruction from the user (Principle 23).

Subagent delegation is especially valuable when:
- The user explicitly requests it
- Multiple chunks are independent and can be built in parallel
- A chunk involves focused, well-scoped work that benefits from a clean context
- The main context is getting large

**How to delegate:** Spawn a subagent and give it:
- The chunk spec and referenced artifacts
- The project directory path
- **"Read the build cycle via `/prawduct:building`, then `.prawduct/.subagent-briefing.md` for project conventions and learnings."**
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

**Tests never weaken.** Don't delete tests or relax assertions to make code pass. Test consolidation is fine — name the reason in the change-log. Fix the code, never the test. This is Principle 1, and it's a bright line.

**All tests pass, always.** There is no "pre-existing" exception. Diagnose and fix every failure.

**Test coverage is proportionate.** Match coverage to risk. Every product needs at least: happy path, error handling for likely failures, and edge cases for anything involving money, data, or safety.

**Multi-hop behavior needs multi-hop tests.** When tested behavior depends on a subsequent invocation (accumulators, coordinators, cursors, stateful retries — next cycle, next call, next prune), exercise at least one step beyond the immediate post-state. Post-state-only tests miss multi-hop bugs.

**Test strategies match the domain.** When test-specifications call for property-based tests, use the project's configured PBT library. Don't add them speculatively — proportionality applies to strategies too.

**Idiomatic tooling, honest coverage.** Use language-native incremental/cached runners to skip re-runs when nothing changed. The framework asserts the *contract* (judged changes appear in `.test-evidence.json`'s `changes_referenced`; the rest in `changes_unjudged`, ungated), not a specific verifier. `bin/test-reference-verify` is a **floor**: symbol-grep catches untested new code but cannot prove execution. For real coverage, plug in a language-native tool and emit `coverage_level: executed`; the Critic's `verify-coverage` scales finding language accordingly.

## The Critic

After medium+ work, invoke the Critic as a separate agent. The Critic receives signals (files changed, work type, work size) and reasons about what to check. It has seven prioritized goals:

1. **Nothing Is Broken** — Test coverage adequate, no security vulnerabilities.
2. **Nothing Is Missing** — Every requirement implemented or explicitly descoped.
3. **Nothing Is Unintended** — No unlisted dependencies, no undocumented decisions.
4. **Everything Is Coherent** — Artifacts consistent with code, documentation doesn't drift.
5. **Decisions Were Deliberate** — Major decisions have rationale, boundary changes investigated.
6. **The System Can Be Understood** — Error handling present, logging appropriate.
7. **The Design Is Sound** — Good encapsulation, appropriate coupling, no unnecessary complexity or duplication.

In `final` mode the Critic also cross-checks learnings and reconciles the backlog. Medium/large `final` reviews use a coordinator pattern — parallel subagents for correctness (1-3), design (4, 7), and sustainability (5-6).

### Modes

`/prawduct:critic` (no args) infers from git + build-plan state; `Critic mode:` in the plan and an explicit slash arg are successive overrides. Four modes:

- **`chunk`** — Goals 1-3 against the chunk's uncommitted diff.
- **`final`** — all 7 goals + cross-checks + Framework-Specific Checks.
- **`cumulative`** — all 7 goals against `merge-base...HEAD`. Gates `/prawduct:pr create`.
- **`verify-resolutions`** — Goals 1-3 against the prior review's scope; re-review after fixing prior findings.

Inference failure or unrecognized mode → `final`. See `skills/critic/review-cycle.md` (per-mode table) and `skills/critic/review-protocol.md` (goals).

**The Critic takes time.** Reviews take 1-5 minutes; don't check on it. While it reviews, deep-scrub your own changes — self-review often pre-resolves findings.

**Never write Critic findings yourself.** If the agent is slow, wait. Writing `.critic-findings.json` "based on" expected output is governance fraud. If the agent fails, tell the user and re-invoke.

**Blocking findings** must be resolved before proceeding. **Warnings** should be addressed — the Critic only uses WARNING when confident. **Notes** are genuinely ambiguous — the builder decides. If you disagree with a finding, think carefully before dismissing — the Critic catches blind spots the builder can't see.

## Creating Pull Requests

**Default: wait for the user to ask.** Do not create PRs proactively. Only use `/prawduct:pr` when the user explicitly requests it ("PR this", "create a PR", "push this up", "open a PR"). If `project-preferences.md` sets `PR creation: automatic`, you may create PRs after Critic review passes without being asked.

Use `/prawduct:pr` for the full PR lifecycle. It invokes the PR reviewer agent for independent release-readiness assessment — a fresh-eyes review of the full changeset, complementing the Critic's per-chunk reviews. The `/prawduct:pr` command is context-aware: it detects git state and routes to create, update, merge, or status automatically.

**Cumulative-Critic gate.** `/prawduct:pr create` calls `prawduct-hook check-cumulative-critic` — required: a blocking-free record vouching for HEAD — a `cumulative` record or a `verify-resolutions` chain record extending one (CRT-4J8W; details in `skills/critic/review-cycle.md`). Sequence: land every non-`.md` fix, run `/prawduct:critic cumulative` once; post-cumulative fixes ride the chain (fix → commit → `verify-resolutions`). While it runs (~4-10 min), do findings-independent prep.

See the plugin's bundled `skills/pr/review-protocol.md` for review criteria. After merge, `/prawduct:pr` cleans up the build plan. Without `/prawduct:pr`, do it manually.

## Exception Handling

Catch specific exceptions. Broad catches (`except Exception`, empty `catch {}`) hide bugs and make debugging difficult.

When a broad catch is genuinely necessary (system boundaries, event loops, top-level supervisors), mark it with an intentional-waiver pragma:

- Python: `except Exception as e:  # prawduct:allow prawduct/broad-except -- reason`
- JS/TS: `catch (e) { // prawduct:allow prawduct/broad-except -- reason`

`prawduct:allow <scope>/<rule-id> -- reason` is the general waiver mechanism (`docs/waivers.md`), generalizing the legacy `prawduct:ok-broad-except`. The canary skips waived lines; the Critic verifies each is legitimate — "reviewed and intentional," not "exempt."

Broad catches that swallow errors without logging (`except Exception: pass`, empty `catch {}`) are always findings — no waiver can justify silencing errors.

## Common Traps

**Test corruption**: Weakening tests to make them pass. Fix the code, never the test.

**Silent requirement dropping**: Implementing 9 of 10 requirements and hoping nobody notices.

**Gold plating**: Adding features the spec didn't ask for. Scope Discipline (Principle 12).

**Test-last**: Writing tests that pass against existing implementation documents behavior including bugs.

**Ignoring the Critic**: Dismissing findings without reflection.

**Verification theater / mock-as-implementation**: Claiming verification without exercising the product, or shipping mocks where the data model declares a real integration. If `project-state.yaml` declares infrastructure dependencies, verify against them — green tests against in-memory stand-ins are not "done."

**"Pre-existing" dismissal**: Labeling a quality issue as "pre-existing" to justify ignoring it. There is no pre-existing exception. If you found it, it's yours to fix or flag.

**Uninvestigated decisions**: Major technology or architectural choices without research. Lock-in, pervasiveness, structural impact, and external dependencies warrant investigation.

**Boundary blindness**: Modifying a contract surface without checking consumers. The canary catches this at session end; checking proactively is cheaper.

**Pacing blindness**: Asking implementation questions when the user is waiting for progress. Decide autonomously on minor details unless genuinely blocked.

**Unnecessary backwards compatibility**: Adding migration paths or fallbacks when there's no existing deployment to migrate. Backwards compatibility is a requirement to be elicited, not an assumption.

**Opinionated defaults without configuration**: Shipping a workflow-affecting feature with one hardcoded behavior. If it could reasonably work two ways, make it a `project-preferences.md` preference with a safe default.

**Skipping `final` mode**: chunk-mode skips Coherence, Design, Learnings Cross-Check, and Backlog Reconciliation. After all chunks are `[x]`, run `final` — or the `cumulative` that IS a `cumulative-final` plan's last-chunk review — the stop hook WARNs otherwise.
