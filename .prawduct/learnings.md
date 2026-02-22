# Learnings

Accumulated wisdom from this project's development. Read this at session start — it directly informs how you work. Entries are ordered by relevance; most important patterns first.

When this file grows past ~3,000 tokens, prune: consolidate related entries, archive learnings that have been incorporated into principles or methodology, remove stale entries.

---

## Judgment alone won't interrupt momentum

**Pattern**: The v2 experiment replaced structural Critic gates with principles saying "invoke the Critic after each chunk." In the first real product build (Hum, chunk 1), Claude didn't read `methodology/building.md`, never invoked the Critic, and self-declared the chunk complete with 15 findings that any independent review would have caught. Discovery and planning methodology guides were read correctly — building was skipped because "start coding" doesn't naturally trigger "read the process guide first."

**Lesson**: There's an asymmetry between behaviors Claude will self-regulate and behaviors it won't. Claude follows principles about *how* to do work (test quality, scope discipline, spec fidelity). It does *not* self-impose process interruptions that halt momentum (invoke a reviewer, pause to read methodology). The first category can be governed by principles. The second needs structural gates. The minimum structural enforcement is: force independent review before declaring work complete.

**Principle**: Relates to Governance Is Structural (#21) and Independent Review (#13).

## Products must be self-contained for parallel agent work

**Pattern**: The v1 system required `framework-path` pointing to a local clone, runtime hook resolution, and shared session state files (`.session-governance.json`, `.active-products/`). This made it impossible for multiple agents to work on different products simultaneously — shared mutable state created race conditions and clobbering.

**Lesson**: Product repos must carry everything they need: their own CLAUDE.md with principles, their own hooks, their own Critic instructions. No runtime dependency on a framework clone. No shared state between agents. The framework is a *generator* that produces self-contained product repos, not a *runtime* that products depend on. This is also the distribution story — if products are self-contained, they work anywhere Claude Code runs.

**Principle**: Relates to Clean Deployment (#9) and structural independence.

## Reactive systems can't detect missing things

**Pattern**: The learning pipeline (observations, Critic, reviews) validates quality of what exists but cannot identify what should exist and doesn't. Critical gaps (missing cross-cutting concerns, missing artifact categories) went undetected across 13+ evaluations and 6+ sessions until an external audit surfaced them.

**Lesson**: Correctness validation ("does this work?") and completeness auditing ("is this everything?") are fundamentally different capabilities. You need both. Periodically step back and ask "what should exist here that doesn't?" — not just "is what exists correct?"

**Principle**: Relates to Automatic Reflection (#16) — reflection must include completeness, not just correctness.

## Governance complexity breeds governance complexity

**Pattern**: Each failure spawned a separate fix. After 11 independent additions, hooks alone were 1,079 lines — exceeding the skill files they protected. Triple-redundant debt detection, uniform 11-step processes regardless of impact. Root cause: reactive additions without coverage auditing.

**Lesson**: Before adding any new enforcement mechanism, ask: "Is this failure already covered by something that exists? Am I adding defense-in-depth where defense-in-one suffices?" Impact-scaled processes (lightweight for small changes, heavy for structural ones) reduce the temptation to make everything heavyweight.

**Principle**: Relates to Proportional Effort (#10) — governance itself must be proportional.

## Independent review catches what self-review misses

**Pattern**: Moving the Critic from in-context (same LLM reviews its own work) to a separate agent improved review quality measurably. The independent agent caught 2 surviving reference errors that in-context review missed, on its very first invocation.

**Lesson**: Independence is a feature for review functions. The reviewer should NOT see the builder's conversation context — that's what creates blind spots. Invoke the Critic as a separate agent via the Task tool. This likely applies to any review function.

**Principle**: Relates to Independent Review (#13).

## Principles need runtime enforcement, not just change-time checks

**Pattern**: "Generality Over Enumeration" was checked when modifying framework files but not when evaluating incoming user guidance. Result: the framework accepted a 285-line technology-specific design that violated the principle, because the principle wasn't applied at runtime.

**Lesson**: Principles apply to decisions as they happen, not just during retrospective review. When receiving guidance or making decisions, actively check: does this violate a principle? Especially watch for: technology specificity, structural assumptions, scope creep, and instance-specific solutions where general ones exist.

**Principle**: Relates to Governance Is Structural (#21) — governance applies continuously, not at checkpoints.

## Filed-away observations don't change behavior

**Pattern**: The YAML observation system captured detailed findings with severity, RCA categories, and status tracking. But observations accumulated without systematically influencing future decisions. The learning loop was write-only — observations were filed but nothing read them before making new decisions.

**Lesson**: Learnings must live where they're read, not where they're filed. This file exists because YAML archives don't change behavior. Keep learnings here, in natural language, where they're loaded at session start and directly influence decisions. When a learning has been incorporated into a principle or methodology update, it can be condensed here.

**Principle**: Relates to Close the Learning Loop (#17).

## Phase-based implementation enables independent testing and rollback

**Pattern**: Large changes (17+ files) that follow phased plans (infrastructure → validation → consumption → documentation) succeed more reliably than monolithic changes. Each phase preserves system functionality and enables confidence to build incrementally.

**Lesson**: For significant changes, plan phases so each one is independently testable and the system remains functional at every boundary. The opposite pattern — monolithic changes with deferred integration — creates fragility and makes rollback difficult.

**Principle**: Relates to Validate Before Propagating (#14).

## Denormalized state drifts without mechanical validation

**Pattern**: Parallel artifact generation by 5 agents produced 12 inconsistencies in denormalized inverse-dependency fields. Each agent independently estimated the field without cross-agent validation.

**Lesson**: Either compute derived data on demand from the source of truth, or mechanically validate it after writes. Never trust denormalized caches maintained by independent actors. This applies to any computed or derived field in any artifact.

**Principle**: Relates to Coherent Artifacts (#12).

## Escape hatches in classification create silent failures

**Pattern**: Gate classified files as framework/product/ungoverned with ungoverned defaulting to auto-allow. An entire product was built without governance because unregistered repos fell into the "ungoverned" escape hatch.

**Lesson**: When classifying inputs, the "unknown" category should default to "suspicious/blocked", not "allowed." Fail-closed is almost always safer than fail-open. This applies broadly: any classification with an "other" bucket that auto-allows is a potential escape hatch.

**Principle**: Relates to Governance Is Structural (#21).
