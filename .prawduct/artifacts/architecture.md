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

3. **Local-first, no network, no daemon — in governance.** Coordination is process-spawn +
   atomically-written files + the git object database. There is no socket, port, or long-running
   server. This is a deliberate constraint: a governance layer that required infrastructure would
   not survive contact with "I just want to code." The one network surface is the **opt-in** backlog
   backend (`backlog_service_repo`), which reaches GitHub Issues through the `gh` CLI; it is off by
   default, degrades to the markdown backend, and no gate or review verdict depends on it.

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
- **Local-first: *governance* coordination is process-spawn + atomically-written files + the git object database — no network, no daemon, and the governance runtime carries no third-party dependencies (dev/test tooling excepted). An opt-in backlog backend may take a network surface, provided it stays off by default, degrades to the markdown backend, and carries no governance verdict.**
  Why: a governance layer that *required* infrastructure would not survive contact with "I just want to code," and a zero-dependency stdlib runtime shrinks the supply-chain surface to prawduct's own code plus git. Both rationales survive this amendment intact, because the network surface is opt-in per product (`backlog_service_repo` unset ⇒ the markdown backend) and confined to backlog storage: a product that never opts in runs exactly the substrate this norm has always described, and no gate, evidence fact, or review verdict crosses the network.
  Status: steady-state.
  Amended: 2026-07-21, owner decision at the backlog-service cutover. The original entry declared that any future network surface would be "a characteristic flip, not a quiet addition" — this is that decision, taken deliberately rather than by accretion. Scope narrows from "no network anywhere" to "no network in governance; opt-in network for backlog storage." The dependency is the `gh` CLI, recorded in `project-state.yaml` `design_decisions.infrastructure_dependencies`. No structural characteristic flips: `gh` owns the credential (`~/.config/gh`) and the adapter never manages a token, so `handles_sensitive_data` stays absent.
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
  │                → briefing (every source) · session reset (boundary sources only) · build index
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
independent triggers — the per-reviewer `SubagentStop` hook, the single-pass fork
inline, and the Stop-hook backstop — so the review lands regardless of which fires. **"Exactly once"
holds for the review *fact*, not for every output:** the fact is idempotent by `(kind, id)`, while the
governance-ledger anchor is replay-closed by `ledger.review_event_exists` and merely overlap-narrowed
(read-then-write, no lock). A concurrent overlap can still anchor twice — observed live 2026-07-29 —
and mandating concurrent coordinator dispatch made that path more reachable, not less. Residual:
CRT-8L3Q.

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
| Plugin (distributed) | `plugin/` in the prawduct repo; the plugin root once installed | skills, hooks, methodology, CLI, templates | read-only; never placed into a repo |
| Framework docs (this repo) | `documentation/` (tracked) | long-form requirements, PRDs, research, and the migration guide — human-facing working docs, framework-repo only (distinct from the plugin-bundled `docs/` reference) | committed to the framework repo |
| Upstream bug intake (this repo) | `incoming-bugs/` (tracked) | bug reports products file upstream about prawduct itself, via `/prawduct:report-bug`; triaged into the backlog, then archived under `incoming-bugs/archive/` | committed to the framework repo |

### What counts as a session boundary

Session/gate state is scoped to a *session*, so the definition of where one ends is load-bearing for
every gate that reads it. Claude Code fires `SessionStart` with five sources, and they divide on one
question — **was the transcript restored?**

| | Sources | What the hook does |
|---|---|---|
| **Boundary** | `startup`, `clear` | orientation **+** the reset (generate the handoff, consume the forward notes, archive the reflection, delete `.gates-waived`, re-capture the three session anchors) **+** the two boundary-dependent readers below |
| **Continuation** | `resume`, `compact`, `fork` | orientation **only**: briefing, advisories, session-file untracking, the state-size and preferences checks, the subagent briefing |

Statements sort into **three** categories, not two — the middle one is the easy mistake:

1. **Destructive boundary acts** — they delete or overwrite session-scoped evidence.
2. **Boundary-dependent readers** — they destroy nothing, but *interpret* session state as belonging
   to a session that has **finished**. Two qualify: the critic-active marker sweep (it deletes a
   marker on the theory that its writer's process is gone) and the previous-session gate check (it
   reads `.session-reflected`/`.gates-waived`/the change baseline and reports them as a completed
   session's record). Both are boundary-only. However read-only such a statement looks, it is not
   orientation — and sorting purely on "does it destroy evidence" puts it in the wrong column, which
   is exactly what the first cut of this split did.
3. **Orientation** — everything else: safe on every source, because it neither destroys session
   evidence nor assumes a boundary just happened.

The split is carried by the hooks.json matcher rather than by parsing the event payload, because the
matcher already carries the one fact needed. `--brief-only` selects the continuation path; it is
orthogonal to `--session-start`, which keeps meaning "a genuine hook invocation" (as opposed to a
reviewer subagent's bare `clear`, which the CRT-3X9D guard refuses). Note the ceiling on that
mechanism: `--brief-only` distinguishes continuation from boundary and **nothing finer**, so `resume`,
`compact` and `fork` are indistinguishable to the hook. Anything needing to tell them apart must split
the matcher further or read `source` from the event payload.

Two properties are easy to get backwards. First, a continuation must never re-capture an anchor **even
when one is missing**: stamping a resume-time clock onto a session that began earlier narrows the
Critic gate's jurisdiction, which is the defect the split exists to remove. An absent anchor already
fails closed, and failing closed is the safe direction. A third consequence follows from the same rule and is easy to miss: `.gates-waived` is deleted only at a boundary, so a declared waiver **outlives a continuation**. That is correct — a waiver is session-scoped and the session is continuing — but it means a waiver survives an unbounded number of resumes, which is a longer life than the pre-split behaviour gave it. Second, the marker sweep is **boundary-only**,
which is the opposite of the intuitive call: sweeping looks like a repair, and a crashed Critic's
marker does wedge an operator. But the premise that licenses deleting someone else's marker — an
in-flight review dies with the process that dispatched it — holds only for a session that *ended*.
`compact` fires mid-session in-process, and `fork`'s parent is frequently still running, so a marker
seen there is likely **live**; sweeping it would disarm both this norm's enforcement and the Stop
hook's abandoned-review backstop, which keys on the marker's presence. Sweeping a live marker is a
silent governance failure; leaving a dead one costs the 30-minute TTL, with `--force` and `rm` as loud
overrides. A crashed Critic is rescued by the next real boundary.

`fork` is the source most easily overlooked (it postdates the other four and was missing from this
plan's first draft). It restores the transcript *and* allocates a new session id, so the parent
session is frequently still running — making it the source where a boundary reset would destroy a
**live** session's evidence rather than a finished one's.

### The two model-owned session files

Session/gate state is machine-written by default — the model reads it, code writes it. Models do
write into `.prawduct/` elsewhere (reviewer subagents emit their own review partials), but those are
inputs to a machine consolidation step. Two files are different: they are narrative, and the machine
cannot synthesize them — `.session-reflected` (backward — what happened) and `.handoff-notes.md`
(forward — what the next session needs to know). The handoff pair's contract, which is the lock-in
that matters more than either file's format:

| | `.handoff-notes.md` | `.session-handoff.md` |
|---|---|---|
| Writer | the model, any time | the machine, at a session **boundary** only (`startup` / `clear` — never on a continuation) |
| Reader | the handoff generator, and nothing else | the next session (via the briefing pointer) |
| Lifetime | until *delivered*, then cleared (see below) | until the next boundary regenerates it |
| Scope | per-worktree, like every session file | per-worktree |

Consumption is transactional and keys on **delivery, not on the handoff having been written**: a
note is cleared only once its text is in the handoff, so one that was unreadable — or lost to a
failed write — survives for the next `/clear`. (Gating on "a handoff was written" is the near-miss:
it is true whenever any *other* section had content, so an unreadable note would be deleted
undelivered.) Notes get no archive of their own — their text is carried verbatim into the handoff,
which is where it is read. A generated handoff carries a machine marker; a `.session-handoff.md`
lacking it was hand-authored, and is folded into the new handoff rather than overwritten. Advice
fails soft applies throughout: none of this can block `/clear` — but every failure names its
consequence, because silent degradation is the bug this pair exists to fix. Failures split by
audience: housekeeping goes to stderr (the operator's), while "a note was left for you and did not
arrive" goes to stdout, which is the channel the incoming agent reads.

**What "survives" actually means, stated honestly** — the three survival paths differ, and only one
of them self-clears:

- *Delivered but not unlinked* — the text IS in the handoff; the stale copy is consumed on the next
  `/clear`. One hop, bounded.
- *Undelivered* (the handoff write failed) — the note is kept and persists until some later `/clear`
  writes successfully. Its text is in no handoff meanwhile.
- *Unreadable* — kept, and **unbounded**: nothing clears it until a human fixes or removes the file,
  and its text never reaches any handoff.

The last two are announced on stdout every session, which is what keeps them from being silent, but
neither is bounded by the mechanism and neither is visible *in the handoff*. Preferring an
unbounded, announced failure over an automatic deletion is the deliberate trade — this channel
exists because deleting an agent's note is the loss that matters — but the bound is the operator's
to close, not the code's.

**Both sides of the boundary can see the channel's state.** The failure this pair exists to fix was
silent in both directions, so two surfaces make it visible, and neither is a gate. *Forward:* when a
session did work and left no note — and left no hand-authored handoff to rescue either — the
generated handoff says so, in the position the note would have occupied, because a file listing a
session's commits and nothing else reads as a complete account of it. It is deliberately not raised
when a note exists but could not be *read*: that is the machine's failure, has its own notice at the
consumption site, and blaming the agent for it would contradict that notice. *Backward:* `handoff
preview` renders through the same function `/clear` does and stops there, so checking what the next
session would receive is no longer the same act as replacing what is there. The asymmetry is real
and worth stating: the absence signal reaches the incoming agent, who cannot act on it. What reaches
the agent who still could — the chunk-close step, the digest line, the preview — is all advisory
too, by the same norm.

**Known gap in the marker scheme:** it recognises a handoff that was *replaced* (no marker), not one
that was *appended to* (marker still present) — that text is still overwritten. Closing it needs a
retained copy or hash to diff against, judged disproportionate against a marker that already
redirects the writer. Tracked as SCN-2M6P; revisit if the net is observed firing at all, since that
is evidence agents still reach for the wrong file.

## Communication Channels

Four are local, and they are the only channels governance uses. A fifth exists only when a product
opts into the backlog service:

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
5. **`gh` subprocess → GitHub Issues REST** — *opt-in only*, present when `backlog_service_repo` is
   set. Sole egress lives in `lib/backlog/transport.py`; the counts cache under
   `<git-common-dir>/prawduct/` is a disposable, network-independent read-through of channel 2, never
   an authority. Absent this opt-in, prawduct makes no network call.

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
