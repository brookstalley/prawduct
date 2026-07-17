---
artifact: nonfunctional-requirements
version: 1
depends_on:
  - artifact: product-brief   # vision lives in README.md + CLAUDE.md
last_validated: null
---

# Non-Functional Requirements

<!-- Written toward the targets we want to hold, not a transcript of current measurements.
     Where a target is aspirational or where reality currently lags, the text says so. -->

## Direction

<!-- Ratified norms (2026-07-17). See docs/norms.md. -->

- **Review wall-clock is a P0 constraint: cost = unit-cost × run-count, so run-count is the lever — fewer, well-scoped reviews — and the two independent reviews at the PR boundary run in parallel, never sequentially.**
  Why: review latency is what determines whether governance feels like a partner or a tax; per-review cost is treated as fixed (reviewers inherit the session model — reviewer-model tiering was removed, the manifest's `tier` is telemetry only), so the only lever is how *often* we review, set by gate and chunk structure.
  Status: steady-state.
- **State-file growth past its size threshold is surfaced as an advisory warning that prompts compaction — it is never a hard block or mechanical enforcement.**
  Why: oversized governance state is a real context-weight cost, but blocking a session on file size would be disproportionate for a local tool — this is advice (fail-soft), not authority; an over-threshold file is the nag's designed target, not a violation, so no ratification retroactivity applies.
  Status: steady-state.

## Performance

Prawduct's performance budget is dominated by one thing: **the wall-clock cost of independent
review.** This is treated as a **P0 constraint**, because review latency is what determines whether
governance feels like a partner or a tax.

The governing model is **cost = unit-cost × run-count**. Per-review cost is treated as fixed —
reviewers inherit the session model (reviewer-model tiering was removed; the manifest's `tier` is
telemetry only) — while **run-count is a design variable set by gate and chunk structure.** We
therefore optimize run-count first (fewer, well-scoped reviews).

Targets we want to hold:

- **Per-chunk Critic review: ≤ 120s median.** A chunk review scopes to the local change and should
  feel like a quick gate, not a context re-establishment.
- **PR boundary (cumulative Critic + PR review): ≤ 7 minutes wall clock.** The two independent
  reviews at the PR boundary **run in parallel, never sequentially** — wall clock is the slowest
  run, not the sum. Any sequencing that exists is for narrative framing, not a data dependency, and
  is a target for removal.
- **A review's cost is fixed context-establishment, not diff size.** A 2-file review and a 20-file
  review cost about the same. The lever is *how often* we review, not making each review cheaper —
  so gate design that avoids a full re-review after a trivial post-review fix is the primary
  optimization.

Hot-path budget (the interactive surface):

- **SessionStart must be fast.** The session-reset/briefing hook runs on every session start and
  must not add perceptible latency. Concretely: minimize git subprocess fan-out (batch
  `git ls-files`/status queries into single invocations), keep the hook import-light (the
  `bin/`↔`lib/` split exists to keep the hot path from importing heavy modules), and prune
  full-tree walks. Regressions here are felt on every single session.
- **No probe or gate on the hot path may block or noticeably delay session start** (see the
  Availability section and `observability-strategy.md`).

## Scalability

Prawduct is **single-actor per repo** — one product owner plus the AI runtime; there are no
concurrent human users, no multi-tenant load, no request throughput to scale. "Scale" here means
the growth of governance state within a repo, and the number of parallel worktrees a session fans
across.

- **Concurrency** is bounded and local: a handful of git worktrees per clone, a small fixed reviewer
  roster (single-pass, or three parallel reviewers for larger changes). The evidence store is shared
  per-clone and appended with single-syscall writes; there is no contention model beyond that.
- **State-file growth is the real scaling axis, and it is governed by mechanical thresholds, not
  vibes.** Files with a size target carry a mechanical check: `project-state.yaml` and
  `learnings.md` each warn past **40 KB**, prompting compaction before context weight compounds
  (the warning is intentionally mechanical because guidance alone erodes). The backlog is the file
  most prone to unbounded growth and needs the same discipline.
  - *Current state (honest):* `project-state.yaml` (~46 KB), `learnings.md` (~71 KB), and
    `backlog.md` (large) are all over their comfortable thresholds and are flagged for compaction.
    The target is that these stay under threshold; reality is currently past it, which is why the
    briefing nags.
- **Architectural change trigger:** if a repo ever needed multiple concurrent human actors,
  per-actor isolation, or a shared server-side store, that is a **structural characteristic flip**
  (`multi_party`), not a tuning exercise — it re-derives the security and data models.

## Availability

Best-effort, local, **degraded-not-down**. Prawduct has no server, no uptime SLA, and nothing to
page. Its availability posture is expressed entirely through **fail-soft design**: every probe,
briefing, and informational path degrades to "skip with a note" rather than crashing, so a broken
probe or malformed state file never takes down a session.

- **"Healthy"** = the plugin loads, governance gates arm, and core state is present and parseable.
- **"Degraded"** = governance still works but something is off (a stale artifact, a size warning, a
  missing optional file). This is a first-class, named state surfaced by `/prawduct:doctor`, not a
  failure.
- The one thing that is *allowed* to stop you is a **governance gate blocking session end** — that
  is availability working as intended (authority fails closed), not an outage.

## Cost Constraints

- **The only meaningful operating cost is reviewer tokens.** Independent reviewers inherit the
  session model (reviewer-model tiering was removed — the manifest's `tier` is telemetry only and
  selects no model). The lever for cost is therefore **run-count**, controlled by gate and chunk
  design, not the reviewer model.
- **No infrastructure cost.** No hosting, no external services, no databases — prawduct is a plugin
  distributed via a git-backed marketplace and runs entirely on the user's machine.
- **Context weight is a cost.** Oversized governance state (backlog, learnings, project-state)
  inflates the context every session and every review must carry — which is why the compaction
  thresholds above are a cost control, not just tidiness.
- **Versioning practice (intended):** releases are versioned **conservatively** — small features are
  patch bumps rather than minor-per-feature — to keep the version number meaningful. *(This is an
  intended practice reflected in the release history; it is not yet codified as a written rule in
  the repo. Codifying it is a candidate norm — see the ratification note in the change record.)*
