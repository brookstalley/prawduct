# Planning: Designing the Solution

Planning bridges understanding and building. You've understood enough of the problem; now design the solution in enough detail to build it well, but not so much detail that the planning itself becomes the project. Planning isn't a one-time phase — new features, refactors, and subsystems each need their own planning scaled to their size.

A `/prawduct:backlog` item at `stage: design` is a planning task: requirements are clear, architecture/detailed design is what's pending. The plan you produce advances the item — update it `stage=ready` once it's buildable. (Earlier stages — `idea`/`research`/`requirements` — route to discovery first, not here.)

## Learnings as Design Constraints

Before generating artifacts, run `/prawduct:learnings [your planned work]` to surface relevant project rules and preferences. This returns only what's relevant without loading the full files. Active learnings encode architecture decisions, technology constraints, and patterns the project has been burned by. They should inform design — not as a checklist, but as context that prevents repeating known mistakes.

## Artifact Generation

Artifacts are specification files that guide building. They ensure you think through the design before writing code — catching issues at the spec level is cheaper than catching them in implementation. Each artifact is a file written to `.prawduct/artifacts/` (see "Where Artifacts Live" below).

**Universal artifacts** (every product, scaled to risk):
- **Product Brief** — Vision, personas, flows, scope, success criteria. The foundation everything else references.
- **Project Preferences** — Developer conventions: language, code style, testing approach, tooling, architecture patterns. Captured during discovery, read before writing any code. Tells every session *how* code should be written (see `templates/project-preferences.md`).
- **Data Model** — Entities, relationships, constraints, state machines. The structural backbone.
- **Security Model** — Authentication, authorization, data privacy, abuse prevention.
- **Test Specifications** — Concrete test scenarios at unit, integration, and e2e levels, with risk-proportionate depth.
- **Non-Functional Requirements** — Performance targets, scalability, uptime expectations, cost constraints.
- **Operational Specification** — Deployment, monitoring, alerting, failure recovery.
- **Observability Strategy** — Signal types, correlation context, sensitive data filtering, instrumentation approach. Scales from "error logging" to full three-signal architecture.
- **Dependency Manifest** — Every external library with justification and alternatives considered.

**Structurally-triggered artifacts** (based on characteristics detected in discovery):
- *Human interface*: Interaction design, information architecture, accessibility specification, onboarding flow
- *Runs unattended*: Pipeline architecture, scheduling, monitoring and alerting, failure recovery, configuration management
- *Programmatic interface*: API contract (operations, request/response formats, error codes, authentication, rate limits)
- *Multiple party types*: Per-party experience specifications, trust boundary analysis, data isolation rules
- *Sensitive data*: Deepens existing artifacts (data lifecycle, security model, audit trails) rather than creating new ones
- *Multi-process or distributed*: System architecture — process topology, communication channels (patterns, endpoints, protocols), concurrency model, persistence boundaries (what's durable vs. ephemeral, what lives where)

### Artifact Dependencies

Artifacts depend on each other. The Product Brief is the foundation — everything references it. The Data Model and NFRs depend on the brief. Security, testing, and operational specs depend on the data model. Generate them in dependency order and validate at boundaries.

**Phase A**: Product Brief (everything depends on this)
**Phase B**: Data Model + Non-Functional Requirements
**Phase C**: Everything else (security, testing, operations, structural artifacts)
**Phase D**: Build Plan (depends on all artifacts)

Between phases, review what you've produced. Apply the review perspectives (Product, Design, Architecture, Skeptic, Testing) to catch issues before they propagate downstream. The cost of fixing a spec error scales with how many downstream artifacts have already incorporated it.

### Where Artifacts Live

Write all generated artifacts to `.prawduct/artifacts/`. This is the canonical location — the Critic reads from it and the build cycle references it. The stop hook triggers the Critic review gate when it detects the active build plan (the `active_build_plan` pointer; default `artifacts/build-plan.md`).

Name files by artifact type: `product-brief.md`, `data-model.md`, `build-plan.md`, etc. For onboarded projects that already have specifications elsewhere, those can stay — but Prawduct-generated artifacts go in `.prawduct/artifacts/`.

### Proportionality

Artifact depth scales to risk. A low-risk personal utility might have a 1-page product brief and a minimal data model. A high-risk financial platform needs deep specs with edge case coverage. The same artifacts exist at different depths — the framework doesn't skip artifacts for low-risk products, it scales them.

If an artifact is genuinely not applicable (e.g., API contract for a product with no programmatic interface), note that briefly and move on. Don't generate content just to fill a template.

## Build Planning

The build plan decomposes artifacts into buildable chunks — coherent units of work with clear deliverables and acceptance criteria.

**Plan lifecycle on gitflow.** When authoring a new plan while the prior plan's work is merged-but-unreleased (gitflow: feature merged to `develop`, the `develop→main` release pending), leave `active_build_plan` pointing at the pending plan until the release ships — the release flips its change-log entries to `shipped` and regenerates its Status. Write the new plan under a scope-named file (`build-plan-<scope>.md`) and repoint only after the release (see `/prawduct:pr` step 7). Build plans are tracked artifacts — commit them.

### Requirements Confidence

Every build plan opens with a **Requirements Confidence** level — High, Medium, or Low — that's an honest self-assessment of whether you understand what to build well enough to build it well (Principle 6 — Requirements Precede Code).

- **High** means the problem, success criteria, and scope are each statable in one sentence with no significant unknowns. Proceed.
- **Medium** means most is clear but specific assumptions are unconfirmed. List them. Expect to revisit during early chunks.
- **Low** means significant unknowns remain. List them and what would resolve them. Either the first chunk closes the gap, or you proceed knowingly — silent low-confidence work is the failure mode the field exists to prevent.

The field is required, but it's not a gate. No review blocks Medium or Low plans — the value is that committing to a Confidence level forces honesty. A plan that says "High" is making a claim. Chunk-level Critic reviews surface acceptance criteria that aren't observable behavior, which is the most common downstream symptom of overstated confidence; the Confidence field gives the builder a chance to catch this earlier.

When confidence is Medium or Low, the plan also lists *what would raise it*. Don't leave that field as "more thinking." Specify the missing information and the cheapest path to get it: a single clarifying question, a 30-minute spike, a 5-line scope sketch to confirm. The cure isn't more process — it's the cheapest concrete step that closes the gap.

**Record inferred answers as vetoable assumptions.** When you fill a requirement yourself rather than confirming it with the user (intentional inference — see `methodology/discovery.md` "Calibrate Rigor"), capture it in the plan's **Open assumptions** field in a form the user can scan and veto:

`[ASSUMPTION: <what you assumed> | HIGH/MED/LOW impact | user can correct / override / defer]`

This is what makes filling-in *intentional* rather than silent: a High-impact assumption the user disagrees with is caught before it becomes built code, and the impact tag tells the reader which ones to check first. An assumption is not a confirmed requirement — it's a decision you made on the user's behalf, surfaced for correction. The same convention carries into the build plan's `Open assumptions / unknowns` field (see `templates/build-plan.md`).

**Good chunks are:**
- **Vertically sliced** — each chunk delivers working, testable functionality from data model through UI (if applicable)
- **Dependency-ordered** — later chunks build on earlier ones; the first chunk validates the architecture
- **Independently testable** — each chunk can be verified without waiting for later chunks
- **Small enough to review** — a chunk should be reviewable in one Critic pass

**The first chunk is special.** It should be a thin vertical slice through the entire architecture — proving that the layers connect, the data flows, and the build approach works. Don't build one layer completely before touching the next. Validate the path before widening it.

**Verification strategy.** The build plan should include how the builder will confirm each chunk's output works beyond tests — exercising the product as its users or consumers would experience it. What this looks like depends on structural characteristics and available tools. Don't over-specify — describe the approach, not a checklist. For many products, the simplest effective method is best. Complex products (e.g., those with human interfaces or multi-party interactions) may need dedicated tooling planned into the scaffold.

**Governance checkpoints** are points during the build where you pause to review the whole — not just the current chunk but the trajectory. Place them at natural boundaries: after the first chunk (architecture validation), at the midpoint, and before completion. The number scales with risk (1-2 for low-risk, 3-5 for high-risk).

**Enumerate the surfaces when a chunk introduces a project-wide concept.** Some chunks add a structural concept that has to be threaded through many files at once — a new build-plan field, a governance flag, a convention every reviewer must honor. These cascade: a single concept can touch the product CLAUDE.md, the Critic skill and its review protocol, the PR protocol, the methodology guides, the build-plan template, and the tests that guard them — eight or more surfaces is common. The plan should list those surfaces up front, in the chunk description, rather than discovering them mid-build. Two reasons. First, an enumerated surface count makes the chunk's true size visible, so it can be split if it's too large to review in one Critic pass. Second, several of those surfaces (methodology files, the Critic protocol) carry token-budget guardrail tests; a cascade that adds prose to each will pressure those budgets and force an aggressive trim of surrounding text before any budget can be raised. Anticipating the cascade means the trim is planned, not a surprise at chunk-close. This pattern has recurred enough (the Requirements-Precede-Code threading, the source-of-truth guardrail, the waiver-pragma work) to be a planning default, not a lesson re-learned per chunk.

### Critic Mode Per Chunk

`Critic mode:` is the proportionality knob — it controls how heavy each per-chunk review is so the cycle doesn't re-pay full-review cost on every chunk. Four modes are available: `chunk`, `final`, `cumulative`, `verify-resolutions`. The field is **optional**: at runtime `/prawduct:critic` (no args) infers the mode from git + build-plan state (see `methodology/building.md` and `skills/critic/review-protocol.md`). Declare `Critic mode:` explicitly only when the plan needs to override what inference would pick — e.g., forcing `final` on an early chunk that lands an architectural keystone (see the override examples below).

**Heuristic — what inference will pick, and when to override:**
- **Single-chunk plan** → inference picks `final` (no prior committed chunks). No declaration needed.
- **Multi-chunk plan** → inference picks `chunk` for non-final chunks (prior chunks committed, more chunks pending) and `final` for the last chunk. No declaration needed for the common case.
- **Override forward to `final`** on an early chunk that lands an architectural keystone whose coherence matters before later chunks build on it — Goals 4-7 + cross-checks pay off here even mid-plan.
- **Override forward to `cumulative`** on the last chunk of a multi-chunk plan that ships as a single PR — typically by declaring `Type: cumulative-final` (the Type triggers a cumulative pass on top of the chunk's `final` review; the explicit `Critic mode:` field is not required for this case).
- **Trivial chunks** (typo-level edits buried inside a larger plan) → waive Critic entirely via `.gates-waived`. For bounded mechanical code changes, prefer `Type: trivial` over the waiver (see Choosing a Chunk Type below).

**Why this layering:** the per-chunk goals (Nothing Is Broken, Missing, Unintended) catch the high-frequency failures — fix-by-fudging, dropped requirements, broad exceptions — and they're cheap to run because they scope to local changes. The final-chunk goals (Coherence, Decisions, Understood, Design, plus the cross-checks) need the full diff to do their job — coherence is across files, design is a system-wide property — so they belong at the end of the cycle, not on every chunk.

**Per-chunk commit is the contract.** `chunk`-mode reviews assume the previous chunk has been committed, so the working-tree diff is just the current chunk's changes. Plans that batch-commit at the end break the assumption — if you need that, override every chunk to `final` (squash-at-end with full-review-per-chunk is heavy but safe; squash-at-end with `chunk`-mode is wrong because the diff scope is unbounded).

**Fail-safe defaults.** If `Critic mode:` is absent and inference cannot make a confident call, both the build cycle and the Critic itself default to `final`. Both layers fail safe to thoroughness — but rely on inference rather than omitting the field as a shortcut to `final`. If you want `final`, let inference pick it for the last chunk or declare it explicitly when overriding earlier.

See `methodology/building.md` for the runtime behavior (how `/prawduct:critic` infers mode and accepts overrides) and `skills/critic/review-cycle.md` for the per-mode behavior table.

### Choosing a Chunk Type

Chunks also declare `Type:` — a separate axis from `Critic mode:`. Mode controls *how deep* the review is; Type controls *what kind of work* is under review. The Critic reads both and selects protocol per the matrix in `skills/critic/review-cycle.md`.

Allowed values: `code` | `doc-only` | `cleanup` | `designer-handoff` | `cumulative-final` | `trivial`. Default is `code` — the fully-armed protocol — so a missing field is the safe option, not a carveout. Declare a non-default Type only when the chunk actually deviates.

- **`code`** — code or behavior changes. The default; you rarely need to write it explicitly.
- **`doc-only`** — methodology, template, or prose-only edits. Critic skips test-evidence checks but still reviews prose deliverables for coverage. Use when the chunk truly doesn't touch executable code.
- **`cleanup`** — branch hygiene, file moves, dead-code removal. Critic tolerates a zero diff; structural-only review. Use when the chunk's value is the removal, not the new code.
- **`designer-handoff`** — handing off visual / token / design-asset work to a human designer. The Critic returns "Review skipped — Type: designer-handoff" and the stop-hook Critic gate also skips. **This is the only Type that bypasses Critic enforcement entirely — use deliberately.** Replaces the prior user-memory carveout with a framework-level rule.
- **`cumulative-final`** — marker on the last chunk of a multi-chunk plan. Signals that a `/prawduct:critic cumulative` review against `merge-base...HEAD` is required in addition to the chunk's own `final` review. The cumulative review is the `/prawduct:pr create` gate (Principle 14 — Independent Review at the bundle level).
- **`trivial`** — semantically simple change whose risk is low *because the author can name why* — not because LOC is small. Two enforcement layers run at chunk close:
  1. **File-set bounds (machine-enforced, hard):** chunk diff has no edits under `skills/`, `methodology/`, or `templates/`; no edits to `CLAUDE.md`; no test-file deletions; no new files. These are the catastrophic-blast-radius classes regardless of size — file-set is necessary but not sufficient.
  2. **Required `**Trivial because:**` rationale (machine-enforced, hard):** the chunk must include a non-empty rationale field. Empty or absent → BLOCKING at the stop-hook. The rationale is the semantic claim; **Critic Goal 3** validates rationale-vs-diff fit (Chunk 05) — a strong rationale points at the structural property bounding risk, not at the author's feeling about the change.

  **Size is not a bound.** An 80-LOC project-wide rename can be trivial; a 5-line state-machine change cannot. Trivial is a judgment, not a LOC metric — the rationale captures the judgment.

  **Over-declaration is unsafe and BLOCKING.** A chunk declared `Type: trivial` that violates either bound is treated as `code` AND the stop-hook emits a named blocker pointing at the specific violation (e.g., `skill-file-edited: skills/critic/SKILL.md`, `missing-rationale: ...`). The framework refuses silent carveouts — fix the violation or change the Type, never both quietly.

  **Strong rationale examples:** `"project-wide rename of FooBar to BazQux; no behavior change"`; `"add type annotations to public API; no logic change"`; `"appends two learning entries to .prawduct/learnings.md; no code, no tests, no behavior"`. **Weak rationale to avoid:** `"small change"`, `"easy fix"`, `"quick update"` — these describe feeling, not structure, so the Critic can't validate fit against the diff.

**Type vs. mode orthogonality.** A `Type: doc-only` chunk can still be `Critic mode: final` (full review of prose deliverables); a `Type: code` chunk can be `Critic mode: chunk` (lightweight Goals 1-3 review). The two fields answer different questions — declare each on its own merits. Under-declaring Type is safe (worst case: redundant Critic work); over-declaring is unsafe (`designer-handoff` on a code chunk silently skips review; `trivial` on a non-eligible chunk produces a named blocker).

### Forward-References to Not-Yet-Created Files

The Critic's ref-drift check (Goal 2) verifies that backticked file paths in the current chunk's section exist on disk — a guard against plans that reference files a rename or refactor has since moved. But a chunk that *creates* a file legitimately names a path that doesn't exist yet. To distinguish the two, prefix the path with the word **`new`** on the same line — e.g. "new `skills/foo/bar.md`". The verifier treats a path immediately preceded by `new` as a forward reference and skips the existence check for it; everything else in the current chunk must already exist. (Paths in future-chunk sections — Chunk N+1, N+2, … — are never checked, so forward references there need no marker.)

This convention is also documented in the build-plan template's inline comment, but authors who write plans without copying the template won't see it there — so it lives here too. Omit the `new` prefix on a file your chunk creates and you'll get a spurious BLOCKING ref-drift finding; the fix is the one-word prefix, not weakening the check.

### Foreign API Verification

When a chunk wraps a foreign API or SDK — anything whose surface the agent doesn't own and can't change — **the first step is reading source or running discovery probes, not drafting handlers from documentation.** Vendor docs lag behind code; LLM training data lags further. Tests written against an assumed signature pass against fakes that mirror the same assumption, then fail at integration time when the real surface diverges. This pattern recurs every time the framework or a product touches a foreign SDK (hallucinote's Ableton Live MCP integration is the canonical case — handlers shipped against signatures that didn't match the real API, found at integration time).

**The rule.** A chunk that wraps a foreign API declares `**Foreign API:** <name>` in the build plan (between `**Type:**` and `**Done when:**`) and includes a `verify-api` step prepended as step 0 in its Done-when (so existing step numbering is preserved across chunks with and without a foreign API). `verify-api` means one of, in preference order:
- Read the foreign code directly (vendor SDK source, MCP server source, library `.pyi` stubs).
- Run a discovery probe against a live instance (curl, REPL session, smoke script) and capture the actual response shape.
- If neither is possible, document the docs source consulted and flag the chunk as `Requirements Confidence: Medium` with "API surface assumed from docs" listed as an open assumption.

Fakes and mocks are built *after* `verify-api` confirms the real shape, not before. The cost is one-time per API surface (~5-30 min depending on surface size); the cost it replaces is one or more chunk-reworks when the assumed shape turns out wrong.

The Critic's Goal 2 looks for `Foreign API:` in the chunk and emits a **WARNING** if no `verify-api` step appears in Done-when. Missing `Foreign API:` field is safe (no foreign API to verify); the field is declared only when relevant.

**Worked example (the pattern the Critic matches).** Prepend `verify-api` as Done-when step 0 so the existing step numbering is preserved across chunks with and without a foreign API:

```
### Chunk 3: Ableton transport handlers

- **Foreign API:** ableton-live-mcp                    # ← field declared
- **Done when:**
  0. verify-api — read MCP server source for the     # ← step present → no finding
     transport resource handlers; capture actual
     response shapes in api-notes-ableton.md
  1. Acceptance criteria met and tests pass
  2. /prawduct:critic chunk run and blocking findings resolved
  3. Committed and chunk marked [x] in Status
```

vs. the WARNING form (same chunk with step 0 omitted):

```
### Chunk 3: Ableton transport handlers

- **Foreign API:** ableton-live-mcp                    # ← field declared
- **Done when:**
  1. Acceptance criteria met and tests pass            # ← no verify-api → WARNING
  2. /prawduct:critic chunk run and blocking findings resolved
  3. Committed and chunk marked [x] in Status
```

The Critic finds the `verify-api` step by case-insensitive substring match anywhere in the chunk's Done-when items — exact phrasing doesn't matter, but the literal token `verify-api` should appear.

**Discovery surfaces foreign APIs early.** When discovery flags an external SDK or service in `infrastructure_dependencies` (see `methodology/discovery.md` "Surface Infrastructure Dependencies"), carry that forward into the build plan as `**Foreign API:** <name>` on whichever chunk first touches the wrapper. Annotation in the plan is what triggers the Critic check.

### Visual Change Verification

Tests confirm logic; they don't confirm that a human-facing surface *looks and reads* right. When a chunk produces a user-visible change — a UI screen, a CLI output format, the appearance of a generated artifact, a live external integration — a passing test suite is necessary but not sufficient. Someone has to look at it before merge.

**The rule.** A chunk that produces a user-visible change declares `**Visual change:** yes` in the build plan (alongside the other chunk fields). At chunk-close the builder appends an entry to `.prawduct/operator-verification.md` describing what to verify and where (see `methodology/building.md` chunk-close step). When `operator_verification_required: true` in `project-state.yaml`, `/prawduct:pr create` blocks on pending entries — drain each via `prawduct-hook verify-operator-verification <VRF-id>`, or override per-PR with `--accept-pending-verification "rationale"`. The Critic emits a NOTE if a chunk declares `Visual change: yes` but no queue entry references it.

The field is declared only when relevant — omitting it is safe (no user-visible surface to verify). Reserve `yes` for changes a test can't speak to: pixel layout, copy and tone, output legibility, the shape of a real third-party response. Pure logic and internal-API chunks don't need it.

## Common Traps

**Over-specification**: Writing specs so detailed they're harder to maintain than the code. Specs should be precise enough to build from but not so rigid they can't adapt to implementation discoveries.

**Under-specification**: Leaving ambiguities that the builder will have to resolve with guesses. Every ambiguity is a risk of building the wrong thing. Be specific about behavior, flexible about implementation.

**Monolithic chunks**: Chunks so large they can't be reviewed meaningfully. If a chunk touches every layer and takes days, it's too big. Split it.

**Dependency ignorance**: Planning chunks that can't be built in order because they depend on things that don't exist yet. Map dependencies explicitly.

**Line-number scoping**: Identifying change sites by line number rather than by structural pattern. "Change lines 42, 87, and 134" is brittle — those lines shift as the file evolves. "All methods that swallow exceptions and return failure replies" is robust — it identifies the pattern, so you find all instances even if new ones were added since the plan was written. Scope changes by the pattern they share, not by their current addresses.

**Template worship**: Generating every section of every template regardless of relevance. If a section doesn't apply, say so briefly. Don't fill space with "not applicable" paragraphs.
