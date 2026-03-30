# Learnings

Active rules from this project's development. Read at session start. Entries use "When X, do Y because Z" format. Full context in `learnings-detail.md`.

When this file grows past ~3,000 tokens, prune: consolidate related entries, move incorporated learnings to learnings-detail.md.

---

## Session-end signals must come AFTER handoff

When signaling session completion ("Ready for next session", "Session is complete"), do the handoff FIRST — commit, update build plan Status, write reflection, capture backlog. Because users interpret completion signals as "handoff is done" and act on them immediately.

## Artifacts drift silently during sustained building

When building multiple chunks, update artifacts (test specs, architecture, data model) as code changes what they describe — not at the end. Because the Critic checks bidirectional freshness, and stale specs become planning fiction. Relates to Living Documentation (#3).

## Structural gates must match natural workflow

When adding structural enforcement (hooks, gates), check BOTH reasonable locations for the thing being enforced. Because the Critic gate only checked `artifacts/build-plan.md` but the natural location was `project-state.yaml`, so the gate never fired for 40+ sessions. Relates to Governance Is Structural (#21).

## Growing files need structural nudges to prune

When a file has a size target, add a mechanical check (not just guidance). Because guidance alone never triggers pruning — the clear hook now warns when learnings.md exceeds 8KB. Relates to Close the Learning Loop (#17).

## Reactive systems can't detect missing things

When validating work, also ask "what should exist here that doesn't?" — not just "is what exists correct?" Because the learning pipeline, Critic, and reviews all validate quality of existing work but cannot identify missing cross-cutting concerns or artifact categories. Relates to Automatic Reflection (#16).

## Governance complexity breeds governance complexity

When adding enforcement, first ask "is this failure already covered by something that exists?" Because after 11 independent additions, hooks alone exceeded the skill files they protected. Impact-scaled processes (lightweight for small, heavy for structural) reduce the temptation to make everything heavyweight. Relates to Proportional Effort (#10).

## Principles need runtime enforcement, not just change-time checks

When receiving guidance or making decisions, actively check against principles — not just during retrospective review. Because the framework accepted a 285-line technology-specific design that violated "Generality Over Enumeration" since the principle wasn't applied at decision time. Relates to Governance Is Structural (#21).

## Denormalized state drifts without mechanical validation

When data appears in multiple places, compute derived values on demand or mechanically validate after writes. Because 5 parallel agents produced 12 inconsistencies in denormalized inverse-dependency fields. Relates to Coherent Artifacts (#12).

## Coherence cascades require checking summaries, not just primary locations

When adding a concept to a system, grep for every place that *summarizes* or *enumerates* what the system contains. Because summaries are denormalized state — they drift when the source changes. Also check scope declarations (section comments saying "only for X") and test scenarios (sibling concepts need rubric criteria too). Reinforced 2026-02-22 with identical miss. Relates to Coherent Artifacts (#12).

## Escape hatches in classification create silent failures

When classifying inputs with an "unknown" or "other" bucket, default to blocked, not allowed. Because an entire product was built without governance when unregistered repos fell into the "ungoverned" auto-allow escape hatch. Relates to Governance Is Structural (#21).
