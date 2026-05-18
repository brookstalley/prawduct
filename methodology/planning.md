# Planning: Designing the Solution

Planning bridges understanding and building. You've understood enough of the problem; now design the solution in enough detail to build it well, but not so much detail that the planning itself becomes the project. Planning isn't a one-time phase — new features, refactors, and subsystems each need their own planning scaled to their size.

## Learnings as Design Constraints

Before generating artifacts, run `/learnings [your planned work]` to surface relevant project rules and preferences. This returns only what's relevant without loading the full files. Active learnings encode architecture decisions, technology constraints, and patterns the project has been burned by. They should inform design — not as a checklist, but as context that prevents repeating known mistakes.

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

Write all generated artifacts to `.prawduct/artifacts/`. This is the canonical location — the Critic reads from it and the build cycle references it. The stop hook triggers the Critic review gate when it detects `artifacts/build-plan.md`.

Name files by artifact type: `product-brief.md`, `data-model.md`, `build-plan.md`, etc. For onboarded projects that already have specifications elsewhere, those can stay — but Prawduct-generated artifacts go in `.prawduct/artifacts/`.

### Proportionality

Artifact depth scales to risk. A low-risk personal utility might have a 1-page product brief and a minimal data model. A high-risk financial platform needs deep specs with edge case coverage. The same artifacts exist at different depths — the framework doesn't skip artifacts for low-risk products, it scales them.

If an artifact is genuinely not applicable (e.g., API contract for a product with no programmatic interface), note that briefly and move on. Don't generate content just to fill a template.

## Build Planning

The build plan decomposes artifacts into buildable chunks — coherent units of work with clear deliverables and acceptance criteria.

### Requirements Confidence

Every build plan opens with a **Requirements Confidence** level — High, Medium, or Low — that's an honest self-assessment of whether you understand what to build well enough to build it well (Principle 6 — Requirements Precede Code).

- **High** means the problem, success criteria, and scope are each statable in one sentence with no significant unknowns. Proceed.
- **Medium** means most is clear but specific assumptions are unconfirmed. List them. Expect to revisit during early chunks.
- **Low** means significant unknowns remain. List them and what would resolve them. Either the first chunk closes the gap, or you proceed knowingly — silent low-confidence work is the failure mode the field exists to prevent.

The field is required, but it's not a gate. No review blocks Medium or Low plans — the value is that committing to a Confidence level forces honesty. A plan that says "High" is making a claim. Chunk-level Critic reviews surface acceptance criteria that aren't observable behavior, which is the most common downstream symptom of overstated confidence; the Confidence field gives the builder a chance to catch this earlier.

When confidence is Medium or Low, the plan also lists *what would raise it*. Don't leave that field as "more thinking." Specify the missing information and the cheapest path to get it: a single clarifying question, a 30-minute spike, a 5-line scope sketch to confirm. The cure isn't more process — it's the cheapest concrete step that closes the gap.

**Good chunks are:**
- **Vertically sliced** — each chunk delivers working, testable functionality from data model through UI (if applicable)
- **Dependency-ordered** — later chunks build on earlier ones; the first chunk validates the architecture
- **Independently testable** — each chunk can be verified without waiting for later chunks
- **Small enough to review** — a chunk should be reviewable in one Critic pass

**The first chunk is special.** It should be a thin vertical slice through the entire architecture — proving that the layers connect, the data flows, and the build approach works. Don't build one layer completely before touching the next. Validate the path before widening it.

**Verification strategy.** The build plan should include how the builder will confirm each chunk's output works beyond tests — exercising the product as its users or consumers would experience it. What this looks like depends on structural characteristics and available tools. Don't over-specify — describe the approach, not a checklist. For many products, the simplest effective method is best. Complex products (e.g., those with human interfaces or multi-party interactions) may need dedicated tooling planned into the scaffold.

**Governance checkpoints** are points during the build where you pause to review the whole — not just the current chunk but the trajectory. Place them at natural boundaries: after the first chunk (architecture validation), at the midpoint, and before completion. The number scales with risk (1-2 for low-risk, 3-5 for high-risk).

### Critic Mode Per Chunk

Every chunk in a build plan declares `Critic mode: chunk | final`. The mode controls how heavy the per-chunk review is — this is what makes Critic review proportional rather than re-paying full-review cost on every chunk.

**Heuristic when authoring a build plan:**
- **Single-chunk plan** → `final`. The one Critic run is also the end-of-cycle synthesis.
- **Multi-chunk plan** → first N-1 chunks `chunk`, last chunk `final`. Each per-chunk review covers Goals 1-3 against just that chunk's diff (target 1-2 min); the final chunk's review covers all 7 goals plus Learnings Cross-Check, Backlog Reconciliation, and Framework-Specific Checks against the full session diff (target 4-10 min).
- **Trivial chunks** (typo-level edits buried inside a larger plan) → waive Critic entirely via `.gates-waived`.

**Why this layering:** the per-chunk goals (Nothing Is Broken, Missing, Unintended) catch the high-frequency failures — fix-by-fudging, dropped requirements, broad exceptions — and they're cheap to run because they scope to local changes. The final-chunk goals (Coherence, Decisions, Understood, Design, plus the cross-checks) need the full diff to do their job — coherence is across files, design is a system-wide property — so they belong at the end of the cycle, not on every chunk.

**Per-chunk commit is the contract.** `chunk`-mode reviews assume the previous chunk has been committed, so the working-tree diff is just the current chunk's changes. Plans that batch-commit at the end break the assumption — if you need that, declare every chunk `final` (squash-at-end with full-review-per-chunk is heavy but safe; squash-at-end with `chunk`-mode is wrong because the diff scope is unbounded).

**Fail-safe default:** if `Critic mode:` is absent from a chunk, the build cycle treats it as `final`. Don't omit the field expecting the default — declare it. The Critic itself, if invoked without a recognized mode token in `$ARGUMENTS`, also defaults to `final`. Both layers fail safe to thoroughness.

See `methodology/building.md` for the runtime behavior (how the build cycle reads the mode and invokes `/critic`) and `agents/critic/review-cycle.md` for the per-mode behavior table.

### Choosing a Chunk Type

Chunks also declare `Type:` — a separate axis from `Critic mode:`. Mode controls *how deep* the review is; Type controls *what kind of work* is under review. The Critic reads both and selects protocol per the matrix in `agents/critic/review-cycle.md`.

Allowed values: `code` | `doc-only` | `cleanup` | `designer-handoff` | `cumulative-final`. Default is `code` — the fully-armed protocol — so a missing field is the safe option, not a carveout. Declare a non-default Type only when the chunk actually deviates.

- **`code`** — code or behavior changes. The default; you rarely need to write it explicitly.
- **`doc-only`** — methodology, template, or prose-only edits. Critic skips test-evidence checks but still reviews prose deliverables for coverage. Use when the chunk truly doesn't touch executable code.
- **`cleanup`** — branch hygiene, file moves, dead-code removal. Critic tolerates a zero diff; structural-only review. Use when the chunk's value is the removal, not the new code.
- **`designer-handoff`** — handing off visual / token / design-asset work to a human designer. The Critic returns "Review skipped — Type: designer-handoff" and the stop-hook Critic gate also skips. **This is the only Type that bypasses Critic enforcement entirely — use deliberately.** Replaces the prior user-memory carveout with a framework-level rule.
- **`cumulative-final`** — marker on the last chunk of a multi-chunk plan. Signals that a `/critic cumulative` review against `merge-base...HEAD` is required in addition to the chunk's own `final` review. The cumulative review is the `/pr create` gate (Principle 14 — Independent Review at the bundle level).

**Type vs. mode orthogonality.** A `Type: doc-only` chunk can still be `Critic mode: final` (full review of prose deliverables); a `Type: code` chunk can be `Critic mode: chunk` (lightweight Goals 1-3 review). The two fields answer different questions — declare each on its own merits. Under-declaring Type is safe (worst case: redundant Critic work); over-declaring is unsafe (`designer-handoff` on a code chunk silently skips review).

## Common Traps

**Over-specification**: Writing specs so detailed they're harder to maintain than the code. Specs should be precise enough to build from but not so rigid they can't adapt to implementation discoveries.

**Under-specification**: Leaving ambiguities that the builder will have to resolve with guesses. Every ambiguity is a risk of building the wrong thing. Be specific about behavior, flexible about implementation.

**Monolithic chunks**: Chunks so large they can't be reviewed meaningfully. If a chunk touches every layer and takes days, it's too big. Split it.

**Dependency ignorance**: Planning chunks that can't be built in order because they depend on things that don't exist yet. Map dependencies explicitly.

**Line-number scoping**: Identifying change sites by line number rather than by structural pattern. "Change lines 42, 87, and 134" is brittle — those lines shift as the file evolves. "All methods that swallow exceptions and return failure replies" is robust — it identifies the pattern, so you find all instances even if new ones were added since the plan was written. Scope changes by the pattern they share, not by their current addresses.

**Template worship**: Generating every section of every template regardless of relevance. If a section doesn't apply, say so briefly. Don't fill space with "not applicable" paragraphs.
