---
artifact: architecture
version: 1
depends_on:
  - artifact: product-brief   # vision lives in README.md + CLAUDE.md
  - artifact: data-model
last_validated: null
---

# System Architecture

<!-- Triggered by classification.structural.multi_process_distributed (monolith-with-workers).
     Describes the intended process topology, communication channels, concurrency model, and
     persistence boundaries. Written toward the design we want to hold — where the current code
     has not fully arrived, the text says so. -->

## Design Intent

Prawduct's architecture serves one goal: **govern an AI coding session without ever trusting the
governed party to certify itself.** Everything below follows from that. Five invariants express
what we want to be true.

1. **Code owns the data plane; the model supplies judgment as content.** Every file a gate trusts
   is written by deterministic code. A reviewer's judgment enters only as *content inside a
   validated partial*, which code checks against a code-written manifest before it becomes a fact.
   The line between "what a reviewer claimed" and "what the ledger attests" is code, always.

2. **An independent reviewer never mutates the session it reviews.** This is the load-bearing
   governance invariant. It is enforced at the *mutation site* (the session-reset command refuses to
   run while a review is active), not merely by restricting a reviewer's tools — because a
   dispatched subagent does not inherit the coordinator's tool restrictions.

3. **Local-first, no network, no daemon.** Coordination is process-spawn + atomically-written files
   + the git object database. There is no socket, port, or long-running server. This is a
   deliberate constraint: a governance layer that required infrastructure would not survive contact
   with "I just want to code." Any future need for a network surface is a characteristic flip, not
   a quiet addition.

4. **Coordination is decoupled, idempotent, and fail-closed.** The processes that produce a review
   (coordinator, reviewers, consolidator) are never all alive at once; they communicate through
   files and reconverge through idempotent operations keyed by identity fixed at dispatch. When
   state is incomplete or ambiguous, the system blocks (fail-closed on *authority*), while probes
   that merely inform never block (fail-soft on *advice* — see the Failure Model).

5. **The plugin writes nothing into a repo it governs, except its own version marker and the
   guidance it injects.** All mutable state lives under the product's `.prawduct/` (per-worktree) or
   the clone's shared evidence store (inside `.git`). Governance code and methodology ship in the
   plugin and stay there. This is what lets a repo commit only a tiny install reference.

## Direction

<!-- Ratified norms (2026-07-17). The descriptive Design Intent above motivates these; the entries
     below are their binding form. See docs/norms.md. -->

- **An independent reviewer never mutates the session it reviews — enforced at the mutation site, not by tool-restriction alone.**
  Why: a dispatched subagent does not inherit the coordinator's tool limits, so the invariant must be enforced where mutation happens; this is the load-bearing governance guarantee — without it the reviewed party could quietly rewrite what it is being judged on.
  Status: steady-state. Mechanism: `prawduct-hook clear` refuses while a review is active (`critic-begin` … `critic-consolidate`/`critic-end`).
- **Authority fails closed; advice fails soft.**
  Why: anything that produces or consumes a governance *verdict* blocks on incomplete, malformed, or ambiguous state (so governance means something), while anything that merely *informs* degrades to a note (so governance stays bearable) — the split is also an abuse-resistance property: you cannot make a gate pass by feeding it garbage, garbage makes it block.
  Status: steady-state.
- **Local-first: coordination is process-spawn + atomically-written files + the git object database — no network, no daemon, and the runtime carries no third-party dependencies (dev/test tooling excepted).**
  Why: a governance layer that required infrastructure would not survive contact with "I just want to code," and a zero-dependency stdlib runtime shrinks the supply-chain surface to prawduct's own code plus git; any future network surface is a characteristic flip, not a quiet addition.
  Status: steady-state.
- **The plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the `.gitignore` / `.claude/settings*.json` it must reconcile — never framework files.**
  Why: least authority over the machine is what makes running the plugin a safe trust decision and what lets a governed repo commit only a tiny install reference; framework code stays in the plugin, read-only from the repo's perspective.
  Status: steady-state.

## Process Topology — "monolith with workers"

The **monolith** is a single long-lived Claude Code session. The **workers** are short-lived: hook
processes the harness spawns on lifecycle events, and reviewer subagents the session dispatches.

```
Claude Code harness (external)
  │  fires lifecycle hooks (python3, one process per event); backgrounds Agent subagents
  ├─ SessionStart  → identity/version banner · guidance digest (injected as context)
  │                → session reset + briefing · build index
  ├─ UserPromptSubmit → prompt-time checks
  ├─ Stop          → governance gates (Critic coverage + reflection) + consolidation backstop
  └─ SubagentStop  → (scoped to critic-reviewer) consolidate when all reviewers reported
  │
  ▼
Main Claude session  (the monolith / coordinator of work)
  │  invokes /prawduct:critic → forked context (own tool allow-list)
  ▼
Critic coordinator  (forked skill context)
  │  small change  → reviews itself, single-pass
  │  5+ changed files → dispatches worker subagents, then STOPS
  ▼
critic-reviewer subagents (parallel workers, read-only + Write-partial only)
  │  each writes exactly one partial findings file
  ▼
critic-consolidate  (deterministic code — not a process of its own)
      runs from whichever trigger fires first: SubagentStop, the single-pass fork inline,
      or the Stop-hook backstop — all idempotent
```

The coordinator and reviewers are separate agent contexts; the hooks are separate OS processes.
`critic-consolidate` is code run inside whichever process invokes it.

## The Critic Data Plane

The flagship multi-process flow, and the clearest expression of invariant 1.

- **`critic-begin` (code).** Captures the working tree into the shared git object DB via a
  *temporary* index (never touching the session's real index or working tree), derives the review
  interval and reviewer roster from git + mode in code, and writes the dispatch manifest and the
  active-review marker. The manifest is the contract: it names the exact tree interval and roster a
  review will attest.
- **Reviewers write partials (model judgment as content).** Single-pass: the fork writes one
  partial. Coordinator: each worker writes exactly its own `<role>.json` and nothing else. Every
  partial is schema-validated.
- **`critic-consolidate` (code).** Reads the manifest, collects the partials, and **fails closed**
  on any gap (missing role, wrong reviewed-commit, malformed partial → no fact). On success it
  appends the review fact (and any resolution facts) to the evidence store, regenerates the derived
  findings view, anchors a telemetry event, clears the marker, and removes the partials.

**Why consolidation is decoupled from dispatch.** The harness backgrounds dispatched subagents, so
the coordinator cannot reliably resume to aggregate. Instead, consolidation runs from three
independent, idempotent triggers — the per-reviewer `SubagentStop` hook, the single-pass fork
inline, and the Stop-hook backstop — so the review lands exactly once regardless of which fires.

## Worktree & Distribution Model

"**Tree-keyed**" carries two distinct meanings; both are intentional.

- **Facts are keyed by git *tree SHA*, not by branch or commit.** A verbatim commit preserves its
  tree, so a review recorded before commit still vouches for the eventual commit from any checkout.
  Gates answer coverage by *composition over trees*: a squash-merge (same tree) stays covered, a
  rebase or amend (new tree) correctly opens a coverage gap. This is what makes governance survive
  normal git workflows instead of fighting them.
- **The evidence store is shared across all worktrees of a clone**, because it lives inside the
  shared `.git` common dir. Every worktree appends to and reads the same log, so review coverage
  composes across worktrees — while unrelated clones are isolated by construction.

**Session/gate state is per-worktree**, deliberately, so parallel worktree agents don't clobber each
other's session markers. The resolver pins governance reads and writes to the session's active
worktree. The split is the design: *shared* where coverage must compose (the evidence store),
*local* where sessions must stay isolated (session markers). Readers fail safe toward more gating
when the two disagree.

**Distribution.** Prawduct ships as a Claude Code plugin (skills, hooks, methodology, the
`prawduct-hook` CLI). A governed repo commits only an install *reference*; framework code lives in
the plugin root and is read-only from the repo's perspective. The one legacy exception — the 1.x
file-sync file registry — exists now only so migration can *remove* committed framework copies;
the plugin no longer places them.

## Concurrency Model

- **Races are avoided by construction, not locks.** Parallel reviewers each write a distinct partial
  file; a deterministic merge unions them. There is no shared mutable file two writers contend on.
- **Idempotency absorbs the multi-trigger race.** The review's identity is fixed at dispatch, and
  every append is existence-guarded, so the three consolidation triggers collapse to exactly one
  fact — every repeat is a clean no-op.
- **Atomic writes everywhere.** All `.prawduct/` state files are written tmp-sibling-then-rename, so
  a reader sees old-or-new, never a torn prefix. Append-only stores use a single append-mode write
  syscall so concurrent whole-line appends from multiple worktrees interleave cleanly. Read paths
  self-heal a torn tail line rather than trusting it.
- **In-flight vs. abandoned.** When the Stop gate sees an active-review marker, it distinguishes
  "reviewers still running" (defer) from "review abandoned" (self-heal or block) by consulting the
  harness's background-task state — and fails closed on any ambiguity.

## Persistence Boundaries

| Tier | Where | Holds | Sharing |
|------|-------|-------|---------|
| Ledger (source of truth) | `<git-common-dir>/prawduct/` (inside `.git`) | evidence facts | shared by all worktrees of a clone; never committed |
| Session/gate state | `.prawduct/.*` (gitignored) | markers, partials, caches, session baselines, advisories | per-worktree |
| Committed product state | `.prawduct/` (tracked) | project-state, backlog, learnings, artifacts, change log, build plan | shared via git, owned by the product |
| Plugin (distributed) | plugin root | skills, hooks, methodology, CLI, templates | read-only; never placed into a repo |
| Framework docs (this repo) | `documentation/` (tracked) | long-form requirements, PRDs, research, and the migration guide — human-facing working docs, framework-repo only (distinct from the plugin-bundled `docs/` reference) | committed to the framework repo |
| Upstream bug intake (this repo) | `incoming-bugs/` (tracked) | bug reports products file upstream about prawduct itself, via `/prawduct:report-bug`; triaged into the backlog, then archived under `incoming-bugs/archive/` | committed to the framework repo |

## Communication Channels

All local. There are four, and only four:

1. **CLI invocation + JSON on stdin/stdout** — the harness passes event payloads to `prawduct-hook`
   on stdin; skills and the Critic fork reach the data plane by invoking `prawduct-hook`
   subcommands.
2. **Files as the shared bus** — the dispatch manifest, per-role partials, evidence store, findings
   view, and session markers let the decoupled coordinator, reviewers, and consolidator communicate
   without ever being alive simultaneously.
3. **Hook stdout injected as session context** — SessionStart hooks print the briefing and inject
   guidance; this is the harness→model channel.
4. **The git object database as a side channel** — tree objects written to the shared ODB, then
   referenced by SHA, are the substrate that makes tree-keying work across worktrees.

## Failure Model

The architecture holds two failure postures on purpose, and keeps them apart:

- **Authority fails closed.** Anything that produces or consumes a governance *verdict* blocks when
  state is incomplete, malformed, or ambiguous — a missing reviewer partial, an unreadable marker, a
  newer-than-known schema. A gate that cannot be sure prefers to block.
- **Advice fails soft.** Anything that merely *informs* — the SessionStart briefing, advisory
  probes, version banner — must never block session start or interrupt work. A probe that errors is
  swallowed with attribution, not raised. (See `observability-strategy.md` for how failures surface,
  and `nonfunctional-requirements.md` for the wall-clock budget this posture protects.)

The distinction is the whole ballgame: gates are strict so governance means something; probes are
gentle so governance is bearable.
