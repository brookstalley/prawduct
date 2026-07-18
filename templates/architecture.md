<!-- Architecture Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator

     Usage: Copy to your project's artifacts/ as architecture.md. Generate this
     when classification.structural.multi_process_distributed is set.

     "Architecture" here means the PROCESS AND COMPONENT TOPOLOGY of a product
     whose behavior spans more than one runtime — not a diagram for its own
     sake. It covers a client + server, a mobile app + backend, services +
     workers + queues, a browser extension + native host, a game client +
     authoritative server, a CLI + daemon, host + plugins over IPC — any product
     where two runtimes must agree and can fail independently. The sections
     below apply to all of them; pick the examples that fit your topology and
     ignore the rest.

     Proportionate to risk: a two-process family app gets a half-page; a
     multi-service platform with independent deploys gets the full treatment.
     Skip sections that don't apply — say so and move on.

     This artifact NAMES the topology and the rules that keep it coherent;
     the per-boundary contract details live in api-contract.md and
     boundary-patterns.md, trust decisions in security-model.md, and scale/
     latency targets in nonfunctional-requirements.md — reference them, don't
     restate them. Coverage is satisfied by this file existing: a product whose
     recorded characteristics genuinely don't warrant a topology spec records
     a one-line "(Not relevant — <reason>.)" instead — though note that
     multi_process_distributed being recorded is usually the reason this file
     is expected at all, so a stub here invites the Critic to weigh the
     contradiction.
-->
---
artifact: architecture
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: security-model
  - artifact: nonfunctional-requirements
last_validated: null
---

# Architecture

<!-- OPTIONAL norm home ("Direction"). To record a norm, add a `## Direction` heading here with
     entries — each: a bold **Statement.**, then `Why:` (required), `Status:` (steady-state |
     in-transition + its tracking item), and optional `Retroactivity:` / `Rulings:` lines.
     Normative statements BIND future work — not descriptions of current behavior. Norms bind;
     descriptions track — see /prawduct:methodology norms for the anatomy, the
     normative-vs-descriptive test, and the lifecycle rules. Add the heading ONLY with a real
     entry: a bare `## Direction` heading reads as ratified norms to the advisory probes. A
     product with no norms to declare leaves this comment as-is — "none to ratify" is recorded
     owner-confirmed through the doctor's Norm Ratification Flow (/prawduct:doctor), never as a
     side effect of authoring this artifact. Don't restate the rules here. -->

## Overview & Topology

<!-- The whole system on one screen: every runtime, where it runs, and why the
     product is split at all.
     - Inventory the runtimes: process/service/app name, platform (server,
       iOS/Android, browser, desktop, embedded, worker pool), and lifecycle
       (always-on, per-request, user-launched, scheduled).
     - A text/ASCII topology sketch is enough — components and the channels
       between them. Keep it honest over pretty.
     - WHY this shape: the constraint that forces the split (untrusted clients,
       platform boundaries, scale, isolation, offline). "It grew this way" is
       an honest answer that invites simplification. -->

## Components & Responsibilities

<!-- One entry per runtime. For each:
     - Purpose: the one job this component does.
     - Owned state: what data/resources it is authoritative for (reference the
       Data Model entities — don't restate fields).
     - What it must NEVER do — the responsibility line that keeps siblings from
       blurring (e.g., "workers never touch the user DB directly").
     Two components with the same answer to "purpose" is a smell worth
     recording. -->

## Communication & Boundaries

<!-- Every channel two runtimes share. For each: transport (HTTP/gRPC, queue,
     shared DB/table, file drop, IPC/pipe, push notification, WebSocket),
     direction, and sync vs. async.
     - The CONTRACT for each channel lives elsewhere — point at api-contract.md
       (programmatic surfaces) and boundary-patterns.md (this project's
       documented crossings); this section is the map, not the schemas.
     - Mark the TRUST boundaries: which channels cross from untrusted territory
       (user devices, browsers, third parties) into trusted — and point at
       security-model.md for what that crossing requires.
     - A shared database used by two writers IS a communication channel — name
       it as one, with its coordination rule. -->

## Data Ownership & Consistency

<!-- Who may write what, and what "agree" means between runtimes.
     - Single-writer rule per entity: exactly one component owns each Data
       Model entity's writes. Name the owner; exceptions are recorded
       decisions, not accidents.
     - Consistency model per channel: what staleness consumers tolerate
       (read-after-write? eventual? offline-first with sync?). The mobile/game
       case: what does the client trust locally vs. reconcile?
     - Message semantics where queues/events exist: at-least-once vs.
       at-most-once delivery, ordering guarantees, and therefore which
       consumers must be idempotent / dedup. -->

## Failure Modes & Resilience

<!-- Partial failure is the default state of a multi-runtime product. Per
     component and per channel:
     - What happens to the rest of the system when THIS is down or slow —
       degraded mode, queued-and-retried, or hard failure? Say which is
       intended.
     - Timeout / retry / backoff policy per channel (a retry storm is a design
       decision made by omission).
     - Recovery: restart order, crash-restart state (what's rebuilt vs.
       persisted), and how backlogged work drains (backpressure vs. unbounded
       queues).
     - The user-visible truth: what does the person see during each failure
       (spinner, stale data, offline banner, silent catch-up)? -->

## Deployment & Version Skew

<!-- What ships independently, and how mixed versions coexist.
     - Deploy units: which components version and release together vs.
       independently. App-store clients and browser extensions make skew
       MANDATORY: last month's client will talk to today's backend — say how
       long that must keep working.
     - Compatibility policy across each channel during skew (additive-only
       changes, capability negotiation, minimum-version enforcement) — align
       with api-contract.md's versioning decisions.
     - Rollout/rollback: order of operations when a change spans components
       (migrate-then-deploy? expand/contract?), and what rollback means for
       already-written data. -->

## Scaling Model

<!-- Where load goes when it grows — scaled to the targets in
     nonfunctional-requirements.md (don't restate the numbers).
     - Which components scale horizontally (stateless replicas) vs. are
       singletons or hold pinned state (sessions, locks, in-memory caches,
       matchmaking).
     - The known bottleneck: every topology has a first thing that falls over —
       name it and the signal that says it's approaching (ties to the
       Observability Strategy).
     - What you are deliberately NOT scaling for yet — a recorded decision
       beats an implicit one. -->

## Cross-Cutting Runtime Concerns

<!-- The concerns that only exist BECAUSE there are multiple runtimes. Address
     the ones that apply:
     - Correlation: how one user action is traced across components (request
       IDs propagated over every channel — ties to observability-strategy.md).
     - Time: whose clock wins; timezone/UTC discipline; tolerance for client
       clock drift (games and sync engines live or die here).
     - Configuration & secrets distribution: how each runtime gets its config,
       and how a config change propagates (restart? poll? push?).
     - Environment parity: how the multi-runtime topology runs on a dev
       machine (all-local? docker-compose? stubs for the mobile client?) —
       divergence here is where "works on my machine" is born. -->

## Decision Log

<!-- Major topology decisions with their rationale (Principle 4 — Reasoned
     Decisions): what was chosen, the alternatives considered, why, and the
     trade-off accepted. New entries append; reversals reference the entry
     they reverse. Keep it to decisions that shaped the topology — this is
     not a diary. -->
