# Planning: Designing the Solution

Planning bridges understanding and building: design the solution in enough detail to build it well, but not so much that planning becomes the project. Planning isn't a one-time phase — new features, refactors, and subsystems each need their own planning scaled to their size.

A `/prawduct:backlog` item at `stage: design` is a planning task: requirements are clear, design is what's pending. The plan you produce advances the item — update it `stage=ready` once buildable. (Earlier stages — `idea`/`research`/`requirements` — route to discovery, not here.)

## Learnings as Design Constraints

Before generating artifacts, run `/prawduct:learnings [your planned work]` to surface relevant project rules and preferences without loading the full files. Active learnings encode architecture decisions, technology constraints, and patterns the project has been burned by — context that prevents repeating known mistakes, not a checklist.

## Artifact Generation

Artifacts are specification files that guide building — catching issues at the spec level is cheaper than in implementation. Each is a file in `.prawduct/artifacts/` (see "Where Artifacts Live").

**Universal artifacts** (every product, scaled to risk):
- **Product Brief** — Vision, personas, flows, scope, success criteria. The foundation everything references.
- **Project Preferences** — Developer conventions: language, code style, testing approach, tooling, architecture patterns. Captured during discovery, read before writing any code (see `templates/project-preferences.md`).
- **Data Model** — Entities, relationships, constraints, state machines.
- **Security Model** — Authentication, authorization, data privacy, abuse prevention.
- **Test Specifications** — Concrete test scenarios at unit, integration, and e2e levels, risk-proportionate.
- **Non-Functional Requirements** — Performance, scalability, uptime, cost constraints.
- **Operational Specification** — Deployment, monitoring, alerting, failure recovery.
- **Observability Strategy** — Signal types, correlation context, sensitive data filtering, instrumentation. Scales from "error logging" to full three-signal architecture.
- **Dependency Manifest** — Every external library with justification and alternatives considered.

**Structurally-triggered artifacts** (from characteristics detected in discovery):
- *Human interface*: Interaction design, information architecture, accessibility specification, onboarding flow
- *Runs unattended*: Pipeline architecture, scheduling, monitoring and alerting, failure recovery, configuration management
- *Programmatic interface* (any surface others call — network service, library/SDK, on-device/platform, or CLI): API contract — operations, inputs/outputs, error model, **versioning scheme**, **deprecation/compatibility policy**, conventions & evolution rules (template: `templates/api-contract.md`). Versioning, deprecation, and error-model choices are *recorded decisions* (`design_decisions.api_versioning_approach` / `api_error_model_approach`), not silent defaults — a deferral must be dated with a revisit trigger.
- *Multiple party types*: Per-party experience specifications, trust boundary analysis, data isolation rules
- *Sensitive data*: Deepens existing artifacts (data lifecycle, security model, audit trails) rather than creating new ones
- *Multi-process or distributed*: System architecture — process topology, communication channels, concurrency model, persistence boundaries

### Artifact Dependencies

Generate in dependency order and validate at boundaries — the cost of fixing a spec error scales with how many downstream artifacts have incorporated it:

**Phase A**: Product Brief (everything depends on this)
**Phase B**: Data Model + Non-Functional Requirements
**Phase C**: Everything else (security, testing, operations, structural artifacts)
**Phase D**: Build Plan (depends on all artifacts)

Between phases, review what you've produced through the review perspectives (Product, Design, Architecture, Skeptic, Testing).

### Where Artifacts Live

Write all generated artifacts to `.prawduct/artifacts/` — the Critic reads from it and the build cycle references it. The stop hook triggers the Critic gate when it detects the active build plan — resolved as described below, not from any one pointer. Name files by artifact type (`product-brief.md`, `data-model.md`, …). Existing specifications elsewhere can stay; Prawduct-generated artifacts go here.

### Proportionality

Artifact depth scales to risk: a personal utility gets a 1-page brief and minimal data model; a financial platform gets deep specs with edge-case coverage. The framework doesn't skip artifacts for low-risk products — it scales them. If an artifact is genuinely not applicable, note that briefly and move on; don't generate content to fill a template.

The **strategy-class** artifacts (data model, security model, non-functional requirements, operational spec, observability strategy, plus the characteristic-triggered API contract and architecture) are coverage-tracked once discovery records the product's structural characteristics: the framework detects one that was *never created* — the gap reactive review can't see — and nudges via the `strategy-artifact-missing` advisory and the `/prawduct:doctor` coverage check. "Note that briefly and move on" is that record: a one-line `(not relevant — <reason>)` stub in `.prawduct/artifacts/<name>` **is** coverage (the file existing is the whole check; whether the decision holds is the Critic's call). `prawduct-hook coverage-scaffold` drops those stubs in one act. See `methodology/discovery.md` for the characteristic → artifact map.

## Build Planning

The build plan decomposes artifacts into buildable chunks — coherent units of work with clear deliverables and acceptance criteria.

**Which plan is active is branch state — let the plan say so.** A plan's frontmatter may declare `branch: <name>`; while that branch is checked out, every governance surface resolves that plan, ahead of the `active_build_plan:` scalar. Prefer it: the scalar is one product-level line that two concurrent branches conflict on every time, and after a merge one of the two plans is invisible to every surface that reads it. Opt in per plan — a plan declaring no `branch:` resolves by the scalar exactly as before.

**Several plans may declare one branch, and that is ordinary** — a `release/2-0` carrying a telemetry plan and a documentation plan, or a fix branch that grew three. Governance resolves one of them and says which, in the session briefing. **This is the one place the precedence is written; every other surface points here.** In order: the sole claimant if there is one (ahead of everything, so a lone plan keeps governing after its last box is ticked — which happens during its own closing PR); else the one claimant still holding open chunks; else the plan `active_build_plan` names, *if* it is one of the candidates still in contention — its remaining job is breaking a tie within a branch, and it does not resurrect a finished plan over open ones; else path order, which is arbitrary and says so. Nothing is silent, because governing by the wrong plan looks exactly like governing correctly unless the surface names its choice. When several plans on a branch are all live work, point the scalar at whichever one you are building now.

**Plan lifecycle: a plan ends by being archived, never deleted.** When its work is done — or has stopped, been descoped, or been absorbed elsewhere — `prawduct-hook archive-plan <path> --state completed|superseded` stamps it with what became of it and moves it into `archive/`, where it stays findable by name. Both terminal states archive; a half-finished dead plan left live is the one that reads as active forever. Archiving also ends a `branch:` claim, so for a branch-declaring plan the move is the whole retirement — nothing has to be un-pointed for the claim to stop resolving. **On gitflow**, when authoring a new plan while the prior plan's work is merged-but-unreleased, leave the prior plan live until the release ships. A branch-declaring plan gets its pointer **cleared** at that merge; a scalar-only plan keeps `active_build_plan` aimed at it and is repointed after the release. `/prawduct:pr`’s Merge Flow *"Confirm the bookkeeping merged WITH the PR"* step owns that split and says why each way. Build plans are tracked artifacts — commit them, archived ones included.

### Requirements Confidence

Every build plan opens with a **Requirements Confidence** level — an honest self-assessment of whether you understand what to build well enough to build it well (Principle 6):

- **High**: problem, success criteria, and scope each statable in one sentence, no significant unknowns.
- **Medium**: most is clear but specific assumptions are unconfirmed. List them; expect to revisit in early chunks.
- **Low**: significant unknowns remain. List them and what would resolve them. Either the first chunk closes the gap, or you proceed knowingly — silent low-confidence work is the failure mode the field exists to prevent.

The field is required but not a gate — committing to a level forces honesty. When Medium or Low, also list *what would raise it*: not "more thinking" but the cheapest concrete step — a clarifying question, a 30-minute spike, a 5-line scope sketch.

**Record inferred answers as vetoable assumptions.** When you fill a requirement yourself rather than confirming it (intentional inference — `methodology/discovery.md` "Calibrate Rigor"), capture it in the plan's **Open assumptions** field:

`[ASSUMPTION: <what you assumed> | HIGH/MED/LOW impact | user can correct / override / defer]`

An assumption is a decision made on the user's behalf, surfaced for correction — the impact tag tells the reader which to check first.

**Good chunks are:**
- **Vertically sliced** — each delivers working, testable functionality across layers
- **Dependency-ordered** — later chunks build on earlier ones
- **Independently testable** — verifiable without waiting for later chunks
- **Small enough to review** — one Critic pass

**The first chunk is special**: a thin vertical slice through the entire architecture, proving the layers connect and the build approach works. Validate the path before widening it.

**Verification strategy.** Include how the builder confirms each chunk works beyond tests — exercising the product as its users would. Describe the approach, not a checklist; complex products (human interfaces, multi-party) may need dedicated tooling planned into the scaffold.

**Governance checkpoints** are points where you review the whole trajectory, not just the current chunk. Place them at natural boundaries — after the first chunk (architecture validation), midpoint, before completion. The count scales with risk (1-2 low, 3-5 high).

**A persisted format is always a lock-in decision, regardless of implementation size.** Lock-in is measured by reversal cost, not LOC — a 30-line ledger writer locks a schema every future consumer depends on. A chunk introducing a persisted format must enumerate, in the plan and before designing fields, the questions the data must answer: its consumers' future queries are its requirements, elicited from those consumers, not inferred from the mechanism (see `methodology/building.md` "Decision Research").

**Enumerate the surfaces when a chunk introduces a project-wide concept.** A new build-plan field, governance flag, or convention cascades across many files — product CLAUDE.md, the Critic and PR protocols, methodology guides, the template, their guarding tests. List the surfaces up front in the chunk description: the count makes the chunk's true size visible (split it if too large for one Critic pass), and several of those surfaces carry token-budget guardrail tests — anticipate the trim rather than discovering it at chunk-close.

### Partition: Serial or Delegated

Chunk boundaries are where the delegation decision is drawn: the last moment before any brief exists at which the whole partition is visible at once. Ask it of each chunk: **what would prove this chunk on its own?** A chunk you cannot answer that for is not scoped tightly enough to hand to anyone, which is a finding about the chunk rather than about delegation. Then apply the default (`/prawduct:methodology delegation`): delegate when the same work finishes in less wall clock and the delegates will not fight each other.

**Record the decision either way**, in the plan's `partition:` frontmatter field, on one line. `serial — 02 and 03 both edit the store module` is an answer; `02-04 delegated, isolated worktrees` is an answer. Serial is very often right — *unexamined* is what the field catches, and a plan with independent chunks and no partition line is the guide's **serial by default** anti-pattern in its plan-time form.

**Disclose it when the plan is presented.** A plan that will delegate says how many delegates, isolated worktrees or the shared one, what each touches, and what they will *not* do. Carry what varies between plans: a disclosure that could be copy-pasted from the last one is boilerplate, and boilerplate stops being read.

**Ask for approval only on one of these four reasons.** The list is closed, because an agent resolving vagueness asks defensively every time — which is the round-trip this exists to avoid.

1. This project has never delegated before, so the user has no precedent for what it looks like.
2. The fan-out is materially wider than anything this project has done.
3. Delegates will write in the shared worktree, so the user's own tree changes under them.
4. Something irreversible or outward-facing sits inside a delegated chunk.

Reasons 1 and 2 turn on history, so **read it rather than asserting it** — the `partition:` lines
on this repo's plans, live and archived, and whether `project-preferences.md` carries a Delegation
row. A precedent you did not look up is the defensive ask wearing a justification.

Three standing negatives override all four — **do not ask** when the user has already approved this plan's delegation, when `project-preferences.md` records delegation as pre-approved, or when the user asked for the plan and its execution without further interruption. Absent a listed reason, disclose and proceed.

**On a yes, offer to make it durable** — a `project-preferences.md` row — or the same question returns with every plan, which is the unnecessary asking wearing a seatbelt.

### Governing Artifacts

Some artifacts don't just describe the product — they **bind** future work: a `## Direction`
section in a strategy-class artifact (observability, security, architecture, API contract, NFRs,
operational spec, data model) or a norm row in `project-preferences.md`. Norms bind; descriptions track
(`/prawduct:methodology norms`). A plan states which norms govern it and reconciles against them *before* code.

**Declare `governed_by:` in the plan frontmatter**, alongside `depends_on:` — the governing
artifacts whose Direction norms (and preferences norms) bind this plan's work. Seed the list
mechanically, then curate: `prawduct-hook jurisdiction --file <plan-or-notes>` (or pipe the plan
text on stdin) ranks candidate governing artifacts by term overlap with each artifact's
vocabulary; `--artifacts-only` restricts to the `governed_by:` target set. The command proposes
candidates — you decide which actually govern.

**Reconcile each governing artifact against its `## Direction` section** and record a one-line
disposition per norm — `conforms` | `ruling needed` | `exception` | `amendment proposed` |
`inapplicable because X`. Applicability is recorded, not assumed: "this norm doesn't apply here"
is itself an interpretation, and it belongs on paper where a reviewer can disagree, not in your
head. A departure from a norm is never silent — you conform, or you record the decision:

`[DECISION: <what was decided> | <why, engaging the norm's why> | user can veto/override]`

— the decision sibling of the `[ASSUMPTION: …]` form above. Amending a norm to bless your own code
is the laundering tell (`/prawduct:methodology norms`); the Critic routes an unrecorded departure to a
**BLOCKING** finding.

**New structural context prompt.** When a chunk introduces a new execution context (a process, a
scheduler, a worker), a new storage surface, or a new external surface (an API you expose or
consume), state how each cross-cutting concern (`.prawduct/cross-cutting-concerns.md`) lands there
— or why it doesn't. A new surface that silently inherits nothing is how observability, auth, and
error handling go missing one context at a time.

### Critic Mode Per Chunk

`Critic mode:` is the proportionality knob — it controls how heavy each per-chunk review is. Four modes: `chunk`, `final`, `cumulative`, `verify-resolutions`. The field is **optional**: at runtime `/prawduct:critic` (no args) infers the mode from git + build-plan state (see `methodology/building.md` and `skills/critic/review-protocol.md`). Declare it only to override inference.

**Heuristic — what inference will pick, and when to override:**
- **Single-chunk plan** → inference picks `final`. No declaration needed.
- **Multi-chunk plan** → `chunk` for non-final chunks, `final` for the last. No declaration needed.
- **Override forward to `final`** on an early chunk that lands an architectural keystone whose coherence matters before later chunks build on it.
- **Override forward to `cumulative`** on the last chunk of a plan that ships as a single PR — typically by declaring `Type: cumulative-final` (the chunk's review IS the one cumulative pass: commit the chunk, then run `/prawduct:critic cumulative` once — no separate `final` and no explicit `Critic mode:` needed).
- **Trivial chunks** (typo-level edits inside a larger plan) → waive Critic via `.gates-waived`; for bounded mechanical code changes, prefer `Type: trivial` (below).

**Why this layering:** the per-chunk goals catch the high-frequency failures cheaply because they scope to local changes; the final-chunk goals need the full diff — coherence is across files — so they belong at the end of the cycle.

**Per-chunk commit is the contract.** `chunk`-mode reviews assume the previous chunk was committed, so the working-tree diff is just the current chunk. Batch-commit-at-end plans break this — if you need that, override every chunk to `final` (heavy but safe; squash-at-end with `chunk`-mode has unbounded diff scope and is wrong).

**Fail-safe default.** If the mode is missing, unrecognized, or inference cannot make a confident call, the review runs `final` (canonical rule: `skills/critic/review-cycle.md`) — but rely on inference rather than omitting the field as a shortcut to `final`.

See `methodology/building.md` for runtime behavior and `skills/critic/review-cycle.md` for the per-mode behavior table.

### Choosing a Chunk Type

Chunks also declare `Type:` — a separate axis from `Critic mode:`. Mode controls *how deep* the review is; Type controls *what kind of work* is under review. The Critic reads both and selects protocol per the matrix in `skills/critic/review-cycle.md`.

Allowed values: `code` | `doc-only` | `cleanup` | `designer-handoff` | `cumulative-final` | `trivial`. Default is `code` — the fully-armed protocol — so a missing field is the safe option, not a carveout. Declare a non-default Type only when the chunk actually deviates:

- **`code`** — code or behavior changes. The default; rarely written explicitly.
- **`doc-only`** — methodology, template, or prose-only edits. Critic skips test-evidence checks but still reviews prose deliverables for coverage.
- **`cleanup`** — branch hygiene, file moves, dead-code removal. Critic tolerates a zero diff; structural-only review.
- **`designer-handoff`** — handing off visual / token / design-asset work to a human designer. The Critic returns "Review skipped" and the stop-hook gate also skips. **The only Type that bypasses Critic enforcement entirely — use deliberately.**
- **`cumulative-final`** — marker on the last chunk of a multi-chunk plan: the chunk's own review IS the one `/prawduct:critic cumulative` against `merge-base...HEAD` (commit first, run once — cumulative is a strict superset of `final`, so no separate `final`). That review is also the `/prawduct:pr create` gate (Principle 14 at the bundle level).
- **`trivial`** — semantically simple change whose risk is low *because the author can name why* — not because LOC is small (an 80-LOC project-wide rename can be trivial; a 5-line state-machine change cannot). Two machine-enforced layers at chunk close:
  1. **File-set bounds (hard):** no edits under `skills/`, `methodology/`, or `templates/`; no edits to `CLAUDE.md`; no test-file deletions; no new files — the catastrophic-blast-radius classes regardless of size.
  2. **Required `**Trivial because:**` rationale (hard):** non-empty, or BLOCKING at the stop-hook. The rationale is the semantic claim Critic Goal 3 validates against the diff — **strong** rationale names the structural property bounding risk (`"project-wide rename of FooBar to BazQux; no behavior change"`); **weak** rationale describes feeling (`"small change"`) and can't be validated.

  **Over-declaration is unsafe and BLOCKING**: a `Type: trivial` chunk violating either bound is treated as `code` AND the stop-hook emits a named blocker (e.g., `skill-file-edited: …`) — fix the violation or change the Type, never both quietly.

**Type vs. mode orthogonality.** A `doc-only` chunk can be `Critic mode: final`; a `code` chunk can be `chunk`. Declare each on its own merits. Under-declaring Type is safe (worst case: redundant Critic work); over-declaring is unsafe (`designer-handoff` on a code chunk silently skips review; `trivial` on a non-eligible chunk produces a named blocker).

### Forward-References to Not-Yet-Created Files

The Critic's ref-drift check (Goal 2) verifies backticked file paths in the current chunk's section exist on disk. A chunk that *creates* a file legitimately names a nonexistent path — prefix it with the word **`new`** on the same line ("new `skills/foo/bar.md`") and the verifier skips the existence check for it. Paths in future-chunk sections are never checked. Omit the prefix on a created file and you'll get a spurious BLOCKING ref-drift finding; the fix is the one-word prefix, not weakening the check.

### Foreign API Verification

When a chunk wraps a foreign API or SDK — anything whose surface the agent doesn't own — **the first step is reading source or running discovery probes, not drafting handlers from documentation.** Vendor docs lag code; training data lags further; tests written against an assumed signature pass against fakes mirroring the same assumption, then fail at integration time.

**The rule.** The chunk declares `**Foreign API:** <name>` and prepends a `verify-api` step as Done-when step 0 (existing numbering preserved). `verify-api` means, in preference order: read the foreign code directly (SDK/MCP source, `.pyi` stubs); probe a live instance and capture the actual response shape; or, if neither is possible, document the docs consulted and flag the chunk `Requirements Confidence: Medium` with the assumed surface as an open assumption. Fakes are built *after* `verify-api` confirms the real shape. The Critic's Goal 2 emits a **WARNING** when a chunk declares `Foreign API:` but no `verify-api` step appears in Done-when (case-insensitive substring — the literal token `verify-api` should appear; the filled example in `templates/build-plan.md` shows the shape). When discovery flags an external SDK in `infrastructure_dependencies` (see `methodology/discovery.md` "Surface Infrastructure Dependencies"), carry it into the plan on the chunk that first touches the wrapper — the annotation is what triggers the check.

### Exposed API: Versioning, Deprecation & Error Model

The mirror for the interface a product *produces* — any programmatic surface others call (network service, library/SDK, on-device/platform, or CLI). Two design decisions must be *recorded*, not left to silence: the **versioning + deprecation/compatibility** scheme and the **error model** — introducing either later is a breaking change for every consumer. The framework forces the decision, not versioning itself: "none — internal-only" is valid; a deferral must be dated with a revisit trigger.

**The rule.** The chunk declares `**Exposed API:** <name>`. The decisions live in `design_decisions.api_versioning_approach` and `api_error_model_approach`, detailed in the API contract artifact (`templates/api-contract.md`). The Critic's Goal 2 emits a **WARNING** for each missing decision. Discovery's `exposes_programmatic_interface` flag carries into the plan on the chunk that first builds the surface; the `api-versioning` advisory independently nudges already-built products.

### Visual Change Verification

Tests confirm logic; they don't confirm a human-facing surface *looks and reads* right. A chunk producing a user-visible change — UI screen, CLI output format, generated-artifact appearance, live external integration — declares `**Visual change:** yes` and, at chunk-close, appends an entry to `.prawduct/operator-verification.md` describing what to verify and where. When `operator_verification_required: true`, `/prawduct:pr create` blocks on pending entries — drain via `prawduct-hook verify-operator-verification <VRF-id>`, or override per-PR with `--accept-pending-verification "rationale"`. The Critic emits a NOTE if the field is declared but no queue entry references it. Reserve `yes` for what a test can't speak to: pixel layout, copy and tone, output legibility, the shape of a real third-party response.

## Common Traps

**Over-specification**: Specs so detailed they're harder to maintain than the code. Precise about behavior, flexible about implementation.

**Under-specification**: Ambiguities the builder resolves with guesses — every one is a risk of building the wrong thing.

**Monolithic chunks**: Too large to review meaningfully. If a chunk touches every layer and takes days, split it.

**Dependency ignorance**: Chunks that can't be built in order. Map dependencies explicitly.

**Line-number scoping**: Identifying change sites by line number rather than structural pattern. "Change lines 42, 87, and 134" is brittle — lines shift. "All methods that swallow exceptions and return failure replies" is robust: it finds all instances even ones added since the plan was written. Scope changes by the pattern they share, not their current addresses.

**Template worship**: Generating every section regardless of relevance. If a section doesn't apply, say so briefly.
