# Building: Turning Plans Into Working Software

How deep the governance goes is determined by the work's size and type.

## Sessions and Work Cycles

A **session** is one Claude Code invocation. Only `startup` and `/clear` **begin** one; `resume`, `compact` and `fork` are continuations — the transcript survives, so they brief but reset nothing. The git baseline, reflection gate, and Critic gate all scope to the session.

A **work cycle** is one unit of work with its own governance: understand → plan → build → verify → Critic → reflect. Multiple work cycles can happen within a single session.

**Context compaction** passes no governance checkpoint, so anything that must survive — plans, decisions, rationale, chunk definitions — must be written to a file first.

**`/clear` between work cycles is recommended** (not required): it resets the git baseline so the next cycle's canary only sees its own changes, archives the previous reflection, and starts fresh context.

**Working in a git worktree.** Run the work cycle (including `/prawduct:critic` and `/prawduct:pr`) *from the worktree*, where the gates resolve `.prawduct/` state to it. One edge: entering a worktree *mid*-cycle leaves the SessionStart markers in the primary checkout (gate readers fail safe) — launch, or `/clear`, in the worktree.

The stop hook is a **final safety net**: reflection captured, Critic invoked if code was built against a plan, advisory **compliance canary** checks run. Per-work-cycle governance is the methodology's responsibility, not the hook's.

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

Classification heuristic: 1-2 files = trivial/small; 5+ files or new dependency = medium; new directory structure or API surface = large. **3-4 files is the dead zone: medium if the change crosses a contract surface, adds a dependency, or touches state outliving the process; small otherwise.**

## Before You Build: Confidence Check

Before any non-trivial work cycle, answer three questions in one sentence each:

1. **What problem are we solving?** (Observable, not abstract.)
2. **What does success look like?** "User can do X and see Y," not "it works."
3. **What's out of scope?** What you're deliberately not doing.

If any can't be answered, requirements aren't clear enough (Principle 6 — Requirements Precede Code). Three options: **close the gap** with one targeted question or an inference to confirm; **sketch and confirm** by writing the answers and presenting them; or **proceed knowingly** by declaring the unknowns in the plan's Requirements Confidence as Medium or Low. Surface unknowns early — never silently build on guesses. Apply for any chunk that touches behavior; skip for trivial (typo, config). For unclear or multi-file work, Plan Mode is the native clarify-before-build vehicle. Same model as `discovery.md` "Calibrate Rigor".

**Re-check the plan's `[ASSUMPTION: …]` entries as code reveals new facts.** They are recorded at plan time and, unchecked, stay recorded: an assumption nobody revisited is a decision taken on the user's behalf that nobody confirmed.

### A Requirement Surfaced Mid-Build

The Confidence Check runs at a chunk's *start*; requirements also arrive *during* a build, and the #1 way they enter undocumented is designing them fluently **in chat** and flowing them into code with no artifact between. **Triggered, not always-on:** when a tripwire fires — a noun the artifacts don't contain, design you can't trace to a parent one rung up, a taxonomy invented in chat, the same thing revised 2-3×, or an "are we sure / is this solved" signal — *stop, name it, write or locate the parent requirement, then resume.*

### A Norm Surfaced Mid-Build

The requirement tripwire has a sibling: "we should always X" is **norm birth** — stop and capture
before code proceeds (a `project-preferences.md` row or a `## Direction` entry: statement + why +
retroactivity). Departing from a norm that already governs your change is a recorded `[DECISION: …]`
— never a norm edited to bless your own code (`/prawduct:methodology norms`;
`methodology/planning.md` "Governing Artifacts").

## The Build Cycle

**Establish a clean baseline.** Before the first work cycle of a session:

- *Tests*: Run the full suite. Every test must pass. **A delegate skips this**, inheriting the main agent's baseline.
- *A red baseline is diagnosed before it is fixed*: re-run the failure on a clean checkout of the base commit. Red there too → not yours; record it (`test-evidence record --degraded`) and name it in the handoff rather than folding a fix into your diff. Green there → yours, and you fix it first.
- *Git state*: Commit or stash unrelated work. Medium+ work gets a feature branch (`feature/...`, `fix/...`) unless `project-preferences.md` allows direct commits.
- *Canary findings*: Address or explicitly acknowledge each compliance finding in the session briefing.

There is no "pre-existing" exception: every session starts clean.

**Read the spec.** Read the chunk's entry in `.prawduct/artifacts/build-plan.md` and any referenced artifacts — what this chunk delivers, its acceptance criteria, its dependencies. Flag ambiguity before building; don't guess silently. Validate that referenced files and components still exist — plans go stale. Run `/prawduct:learnings [chunk focus]` for relevant rules before coding.

**Persist plans immediately.** When scope evolves — new chunks, discovered gaps — update `build-plan.md` at once. *Writing* it is not enough before you delegate: a worktree-isolated subagent reads HEAD, so an uncommitted amendment is invisible to it (see "Delegating Work to Subagents").

**Write tests.** Tests come first or alongside implementation, not after. If you can't write the test, you don't understand the requirement well enough to implement it.

Test at the right level — **unit** (functions, logic), **integration** (component interactions, data flow, state), **end-to-end** (critical user flows, acceptance criteria). Depth proportionate to risk.

**Implement.** Write the code that makes the tests pass, following `project-preferences.md` conventions. Prefer simplicity — the minimum abstraction the current chunk needs. Add observability alongside features, not after.

**Update artifacts as you go.** When implementation changes something an artifact describes — API surface, data model, architecture — update that artifact as part of implementation, not at the end. Artifact drift is the #1 recurring quality issue at scale.

**CLAUDE.md is instructions, not documentation** — dev commands, test workflows, conventions. Architecture descriptions and component inventories belong in `docs/` or `.prawduct/artifacts/`. Target: project-specific content under ~150 lines (the Critic warns above it).

**Comments and durable specs are self-contained — explain *why*, never ride meaning on an id that changes under you, and never narrate history.** Review and finding ids never ship — history's one home is commits and the change-log, so a comment recounting it (`// Critic caught Y`) is a deletion, not a rewrite. Carry the present-tense reason instead: not `// per chunk 03` but `// OpenFoodFacts rate-limits burst lookups`.

**Same decay: a count nothing reads is not worth writing.** Ask what gets decided differently if it is wrong by two; if nothing, omit it, make it relational ("the table's rows"), or cite the command that regenerates it. Numbers something *relies* on stay exact. **Suite totals keep coming back** — the evidence store holds pass/fail per tree, so say "suite green" and cite `test-status`; never copy a total into a record or add a field for one.

**Verify.** Two layers:

- *Code:* Record **once**, at Verify — **not** after committing (a commit doesn't stale session-scoped evidence). Check `test-status` first (exit 0 = already passed; don't re-run). Record via `prawduct-hook test-evidence record`, or ingest an existing run — `--from-junit`, `--from-counts` (any toolchain), `--no-rerun` (restamp) — no re-run even when `test_command:` is declared. Non-default suites: `test_command:`/`test_commands:`/`tests_dirs:`.
- *Product:* Launch it, call it, inspect output. If infrastructure dependencies are declared, verify against real instances — mocks are not verification.

Scale to chunk significance. When you can't verify, say so (Principle 5).

**Gate waivers.** When a gate is genuinely N/A, write `.prawduct/.gates-waived` as `{"critic": "reason", "pr": "...", "reflection": "..."}`. String reasons required. Auto-cleared next session. Doc-only edits are skipped automatically.

**In-flight background work auto-defers — don't waive.** When the gate would block only because harness-tracked background work (`Workflow`/`Task`) is still producing the diff, the Stop hook defers and re-arms when it lands. An *untrackable* wait (CI, a remote queue) still blocks.

**Critic review.** Run `/prawduct:critic` (no args) — the SKILL infers mode from git + build-plan state via `prawduct-hook infer-critic-mode` and records `mode_chosen_by`. Pass an explicit mode (e.g. `/prawduct:critic cumulative`) only to override; report override cases so inference can improve.

**Resolve findings.** Consolidate before reading `.critic-findings.json` where the digest says to; single-pass reviews consolidate themselves. **Disposition them ALL in ONE pass — fix everything in the working tree, then ONE `/prawduct:critic verify-resolutions`, then ONE commit** (in that order — committing first re-anchors the pass; `review-cycle.md`) — fix-commit-verify per finding multiplies rounds. **Once zero blocking remain the review is over — then fix, accept, or file** (`skills/critic/review-cycle.md`). Accept (won't-fix, reasoned) is the default. **Record it as a fact (`prawduct-hook disposition`), then `render-dispositions` into the entry — never hand-count.** Re-run the gate, don't infer a round from stale output. Document disagreements with rationale.

**Reflect — now, not at session end.** Append to `.prawduct/.session-reflected`: what the chunk delivered, what the Critic caught, what surprised you. A paragraph is enough. Add a rule to `learnings.md` only if this cycle produced one.

**Operator verification (F10).** Visual / live-integration chunks: enqueue in `.prawduct/operator-verification.md` and mark `Visual change: yes`. `/prawduct:pr create` blocks on pending entries when `operator_verification_required: true`.

**Verify artifacts are current.** Confirm artifacts reflect the code — the Critic checks bidirectional freshness.

**Update build plan Status.** Mark the chunk `[x]` and update the Context block — the cross-session handoff.

## Session Scope Discipline

**Size a work cycle by the diff its review must cover, not by a chunk count.** Critic quality degrades across a large diff, and the constraint is the reviewer's *attention* rather than its window. The roster rule names the honest unit: a risk surface, or 12+ judgeable files. A multi-chunk plan spans sessions: per-chunk reviews accumulate, and the final/cumulative lands with the last chunk.

**Complete required governance at chunk boundaries, then signal — never *ask* whether to prepare a handoff; prepare it and say so.** At a chunk boundary, or when the user switches tasks, complete in order:

1. **Commit** (tests passing). 2. **Critic** (if medium+ and not run yet) — resolve blocking findings. 3. **Persist** pending decisions/plans to artifact files. 4. **Backlog** — file/close affected items via `/prawduct:backlog`. 5. **Update build plan Status** (mark chunks, update Context). 6. **Reflection** — confirm `.prawduct/.session-reflected` has an entry for this chunk; add a synthesis only if a cross-cutting pattern emerged. 7. **Handoff notes** — **read `.prawduct/.handoff-notes.md` before rewriting it**, then reconcile to what the *next* session needs: where you stopped, what you'd do next, what would bite them. Never blind-append.

**Then close the turn with the standing block — last, after every other word.** Say `SAFE TO CLEAR` only when steps 1-7 above are done **and nothing is outstanding, in flight included** — that binding is what this file owes the block. Its shape, trigger and failure modes are `methodology/reflection.md` "Work cycle boundary", and the session digest injects them into every session, so they reach you whether or not you opened this guide.

The `/clear` hook regenerates `.prawduct/.session-handoff.md` — never hand-edit it — from your notes (first), build plan Status, reflection, Critic findings and changed files. `prawduct-hook handoff preview` shows what the next session would get.

## Investigated Changes

Two categories of action require investigation before commitment:

### Boundary Investigation (when changes cross contract surfaces)

Contract surfaces — API endpoints, DB schemas, IPC, frontend/backend type contracts, config interfaces — are where components interact; see `.prawduct/artifacts/boundary-patterns.md` for this project's documented ones.

When you modify files that affect a contract surface:
1. **Recognize** the boundary crossing — any change to a producer with known consumers.
2. **Investigate** with a focused subagent: read the changes, grep for consumers across layers, report crossed boundaries, affected consumers, and test coverage.
3. **Incorporate** findings — update consumers, add integration tests.
4. **Record** what was investigated and found. The Critic verifies investigation occurred.

**Both directions.** Steps 1-4 ask *did my change break downstream consumers?* When you write or change a **consumer**, ask the mirror: read the producer's actual emitted signal sequence — every event, terminal marker and error path, and in what order — not just the type or shape both sides agree on. A consumer that type-checks and still awaits a signal the producer never sends, or drops a terminal/error one it does, is a Critic Goal 1 **BLOCKING** finding.

### Decision Research (when choices constrain future options)

A decision is "major" when it has: **lock-in** (hard to reverse — a persisted format is always lock-in, measured by reversal cost not LOC; enumerate the data's future consumer queries before designing fields), **pervasiveness** (many files), **structural impact** (shapes architecture), **external dependency** (long-term library/service reliance), or **volatility** (correctness rests on fast-moving / post-cutoff data — web-research it, don't recall; see `methodology/discovery.md` "Calibrate Rigor").

Research scales to impact: **medium** (pervasive pattern, non-core dep) → quick in-context research; **high** (lock-in, structural, core dep) → a research subagent returns a concise recommendation on patterns and library health. Presentation scales to engagement: **low** → decide and state briefly; **medium** (default) → recommend and invite feedback; **high** → options with trade-offs for the user to choose. Record major decisions in the most affected artifact: what, alternatives, rationale, trade-offs.

**The cheap-check gate** (Principle 24 — Retrieval Over Generation). Before any expensive or hard-to-reverse step — experiment spend, a deploy, a tuning campaign — ask: *what is the cheapest verification that could change this decision, and did I do it?* A free read or short search comes first. Tells you're generating, not retrieving: a confidence word with no citation; tuning a mechanism you haven't read; contradicting an artifact in hand; revising the same decision with no new fact (full detectors: `docs/principles.md` #24).

## Delegating Work to Subagents

**When the user asks you to work in a subagent, do it** (Principle 23). Otherwise the default is **delegate when the same work finishes in less wall clock and the delegates will not fight each other** — recorded as the plan's `partition:`, re-checked at each chunk close, and asked again of a tangent or anything you were about to backlog. **Read `/prawduct:methodology delegation` before fanning out** — it is the judgment; this section is the mechanics.

**How:** give it the chunk spec and referenced artifacts, the project directory path, the instruction **"Read the build cycle via `/prawduct:methodology building`"**, and **a verification ceiling** — the project's `Delegate verification` row where it has one, else the narrowest run covering its own change; never the full suite. A cost bound, not a rigor discount, and what it prevents fails *silently*: a contended run reports a green that skipped a part nobody can name. Add **"then `.prawduct/.subagent-briefing.md`"** only for a *shared*-worktree agent — it is gitignored, so an isolated one never sees it; inline what that agent needs.

**Parallel chunks:** launch independent chunks as separate subagents and await results. **Worktree-isolated (`isolation: "worktree"`) subagents read HEAD** — uncommitted artifacts, the plan you just amended included, are invisible; commit first or inline it in the prompt, say the prompt outranks any file, then tell it not to write `.prawduct/` (`prawduct-hook` refuses only on the harness's scratch branch, not one the agent creates). **Shared-worktree subagents share your git *index*** — `git rm` stages into *yours*, and `git add <paths>` does not scope a later `git commit`; use `git commit -- <paths>`. Prefer isolation for truly independent chunks. The canary may fire O(agents × edits) — expected; note it in the reflection.

**What stays in the main agent:** the combined suite and all end-to-end verification, merge conflicts, Critic, reflection, state updates. The subagent implements; the main agent governs.

**A delegate's "Done" on a removal or a sweep is a claim — verify it by re-deriving it.** Removals and sweeps fail silently and in the direction of looking finished: a symbol left behind, an allowlist wider than the brief, an inventory count several percent short. Before accepting, run the derivation yourself — grep the removed symbol, recount from the source the brief named, diff the files it touched against the ones it owned.

## Working With Specs

Specs are guides, not scripture. **If the spec is wrong**, flag it, propose the fix, update the spec to match reality. **If the spec is ambiguous**, pick the most likely interpretation, implement it, note the ambiguity. **If the spec is incomplete**, surface it — reasonable choices for minor gaps, escalate significant ones.

## Test Discipline

Tests are the most important artifact you produce: contracts that define correct behavior and protect against regression.

**Tests are behavioral.** Test what the code does, not how it does it.

**Tests are independent.** No shared mutable state, no ordering dependency.

**Tests never weaken.** Consolidation is fine — name the reason in the change-log (Principle 1 — a bright line).

**Test coverage is proportionate.** Every product needs at least: happy path, error handling for likely failures, and edge cases for anything involving money, data, or safety.

**Multi-hop behavior needs multi-hop tests.** When tested behavior depends on a subsequent invocation (accumulators, coordinators, cursors, stateful retries), exercise at least one step beyond the immediate post-state.

**Test strategies match the domain.** When test-specifications call for property-based tests, use the project's configured PBT library. Don't add them speculatively.

**Idiomatic tooling, honest coverage.** Use language-native incremental runners to skip re-runs when nothing changed. The framework asserts the *contract* (judged changes land in `.test-evidence.json`'s `changes_referenced`; the rest in `changes_unjudged`, ungated), not a specific verifier. `bin/test-reference-verify` is a **floor**: symbol-grep catches untested new code but can't prove execution. For real coverage, plug in a language-native tool and emit `coverage_level: executed`.

## The Critic

After medium+ work, invoke the Critic as a separate agent. It reasons from signals through seven prioritized goals, from **Nothing Is Broken** to **The Design Is Sound** (definitions: `skills/critic/review-protocol.md`).

In `final` mode the Critic also cross-checks learnings and reconciles the backlog. `final`/`cumulative` reviews may use a coordinator pattern — parallel subagents for correctness, design and sustainability. The roster rule, which depends on whether the repo declares `risk_surfaces:`, is in `skills/critic/review-cycle.md`.

### The evidence model

Every consolidated review appends a **fact** to a store shared by all worktrees of the clone (`<git-common-dir>/prawduct/evidence.jsonl`; inspect with `prawduct-hook evidence status|list`). Facts record *trees*, so nothing expires by time or session and the gates answer by **composing** them — mode labels don't matter, a pre-commit review vouches for the verbatim commit, a rebase/amend opens a gap, and blocking findings block until cleared (`verify-resolutions`, or a spanning review). `.critic-findings.json` is a derived view of the newest fact (no gate reads it), written by the lifecycle commands, never you. Full model: `skills/critic/review-cycle.md`.

### Modes

`Critic mode:` in the plan and an explicit slash arg are successive overrides on the inference described above. Four modes: `chunk`, `final`, `cumulative`, `verify-resolutions`. What each covers — and the fail-safe that a missing, unrecognized or unconfidently-inferred mode runs `final` — is `skills/critic/review-cycle.md`, not restated here. Two facts are worth having before you open it: `cumulative` feeds `/prawduct:pr create`'s gate, and `verify-resolutions` alone records resolution facts.

**The Critic takes minutes, not seconds** (per-mode targets: `review-cycle.md`). Don't poll; deep-scrub your own changes while it runs, which often pre-resolves findings. If it fails, tell the user and re-invoke — never write `.critic-findings.json` yourself.

**Warnings and notes gate nothing** — every fix commit extends HEAD, which is how a passing review buys another round. Think before dismissing one anyway: the Critic catches blind spots the builder can't see.

## Creating Pull Requests

**Default: wait for the user to ask** — unless `project-preferences.md` sets `PR creation: automatic`.

`/prawduct:pr` handles the full lifecycle (it detects git state and routes to create, update, merge, or status) and invokes the PR reviewer agent for independent release-readiness assessment of the full changeset. Review criteria: the plugin's `skills/pr/review-protocol.md`. After merge, `/prawduct:pr` cleans up the build plan.

**Cumulative-Critic gate.** `/prawduct:pr create` calls `prawduct-hook check-cumulative-critic` — composed coverage must span merge-base → HEAD with zero unresolved blocking findings. Land every judgeable fix first, run `/prawduct:critic cumulative` once, commit verbatim. While it runs, do findings-independent prep.

## Exception Handling

A broad catch is legitimate at system boundaries, event loops and top-level supervisors — mark it with `prawduct:allow prawduct/broad-except -- reason` in a comment on the `except`/`catch` line *itself*. The Critic verifies each is legitimate — "reviewed and intentional," not "exempt."

## Common Traps

**Test-last**: Tests written to pass against existing implementation document behavior, including bugs.

**Uninvestigated decisions**: a major choice made without the research above.

**Tuning a mechanism you haven't read**: read it first — a ten-minute read routinely collapses a multi-day tuning campaign (Principle 24).

**Boundary blindness**: Modifying a contract surface without checking consumers. The canary catches this at session end; checking proactively is cheaper.

**Pacing blindness**: Asking implementation questions when the user is waiting for progress. Decide autonomously on minor details unless genuinely blocked.

**Unnecessary backwards compatibility**: Adding migration paths or fallbacks when there's no existing deployment to migrate. Backwards compatibility is a requirement to be elicited, not an assumption.

**Opinionated defaults without configuration**: If a workflow-affecting feature could reasonably work two ways, make it a `project-preferences.md` preference with a safe default.

**Skipping `final` mode**: `chunk` mode covers Goals 1-3 only. After all chunks are `[x]`, run `final` — or on a `cumulative-final` plan, the single `cumulative` that serves as the last chunk's review. The stop hook WARNs otherwise.
