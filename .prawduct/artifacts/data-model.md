---
artifact: data-model
version: 1
depends_on:
  - artifact: product-brief   # prawduct has no product-brief.md; the vision lives in README.md + CLAUDE.md
last_validated: null
---

# Data Model

<!-- Prawduct persists development-process metadata only — no product data, no end-user data,
     no PII. The "entities" here are the governance stores the framework reads and writes across
     a session's lifecycle. This model describes what those stores are FOR and the invariants they
     must hold, not an exhaustive field dump (the code is the field-level source of truth). Where
     the intended design and the current code differ, the text says so. -->

## Design Intent

The data model exists to make one thing true: **governance verdicts are computed from an
append-only ledger of facts, never from mutable model-written state.** Five invariants carry that
intent. They are what we are building toward; a few are already fully realized, and the notes call
out where reality still lags.

1. **One source of truth: the evidence store.** Every gate verdict (Critic coverage, resolution
   status) is derived from facts in `evidence.jsonl`. Nothing else is trusted for a verdict.
   *Realized* for the Critic data plane (kernel v3); test-run and PR-review evidence are **intended**
   to migrate onto the same store (reserved fact kinds `test-run`, `pr-review`, `promotion`) and
   today still live in their own files.

2. **Facts are immutable and append-only.** A fact is never edited or deleted in place. State
   changes are expressed as *new* facts (a resolution fact supersedes a finding; it does not mutate
   it). This is what lets any worktree reconstruct the same verdict from the same log.

3. **Derived views are disposable and never authoritative.** `.critic-findings.json` and similar
   caches are regenerated from facts by code and may be deleted at any time without loss. No gate
   reads a derived view to reach a verdict — it reads facts. A view exists for human/agent reading
   speed, not for correctness.

4. **No model in the write path of a fact.** Facts are written by deterministic code
   (`critic-begin` writes the dispatch manifest; `critic-consolidate` writes the review/resolution
   facts). Model judgment enters only as *content inside* a reviewer's partial, which code then
   validates against the manifest before it becomes a fact. The boundary between "what a reviewer
   claimed" and "what the ledger attests" is code.

5. **Two stores, two lifetimes, deliberately split.** Shared, committed *answers* (what a team
   decided — `project-state.yaml`) are distinct from per-clone, gitignored *nags and caches*
   (`.advisories.json`, the evidence store, session state). A teammate's committed decision resolves
   an advisory for everyone; local nag state never pollutes the shared record.

## Direction

<!-- Ratified norms (2026-07-17). The descriptive Design Intent above motivates these; the entries
     below are their binding form. See docs/norms.md. -->

- **Governance verdicts on the Critic data plane are computed from the append-only fact ledger, never from mutable model-written state — no model sits in a fact's write path.** Facts are written by deterministic code; a reviewer's judgment enters only as validated content inside a partial that code checks against a code-written manifest before it becomes a fact.
  Why: the governed party must never be able to certify itself — deriving every verdict from code-written facts is what keeps model judgment out of the authority path and lets any worktree reconstruct the same verdict from the same log.
  Status: steady-state — scoped to the Critic data plane (kernel v3). Test-run and PR-review evidence still live in their own files; extending the store to subsume them (reserved kinds `test-run`/`pr-review`/`promotion`) is design direction, not yet a ratified norm.
- **Facts are immutable and append-only; a state change is expressed as a new fact, never an edit or delete in place.**
  Why: append-only history is what lets any checkout replay the same verdict from the same log — an in-place edit or delete would make the ledger unreproducible and a verdict unauditable.
  Status: steady-state.
- **Derived views are disposable and never authoritative — no gate reads a view to reach a verdict.**
  Why: a view (`.critic-findings.json` and kin) exists for human/agent read-speed and may be regenerated or deleted at will; letting a gate trust one would smuggle mutable, model-adjacent state back into the authority path.
  Status: steady-state.
- **A fact written by a newer schema than the reader is surfaced as a loud block, never silently dropped.**
  Why: forward-incompatibility must be visible — silently skipping an ahead-of-schema fact would let a gate render a verdict on incomplete evidence.
  Status: steady-state. Mechanism: `evidence status` exit 2 (schema-ahead).
- **Two stores, two lifetimes: shared committed *answers* are kept distinct from per-clone, gitignored *nags and caches*.**
  Why: a teammate's committed decision must resolve state for everyone, while local nag/cache/session state must never pollute the shared record; collapsing the two would either leak local state into the repo or block a shared decision from propagating.
  Status: steady-state.

## Entities

Prawduct's stores fall into three tiers: **ledger** (source of truth), **committed curated state**
(human/tool-authored, shared), and **ephemeral/derived** (per-session or regenerable).

### Tier 1 — Ledger (source of truth)

#### Evidence Store — `<git-common-dir>/prawduct/evidence.jsonl`

The append-only fact log. One JSON envelope per line. Lives *inside* `.git` (the common dir shared
by every worktree of a clone), so it is uncommitted by construction and shared across all worktrees.
An absent file is the empty store.

| Field | Type | Purpose |
|-------|------|---------|
| `schema` | int | Envelope schema version (guards forward-compat; a record from a newer plugin is surfaced, never silently dropped) |
| `kind` | string | Fact namespace — `review`, `resolution` today; `test-run`, `pr-review`, `promotion` reserved (intended) |
| `id` | string | Idempotency key, fixed at dispatch — re-running consolidation never double-appends |
| `ts` | string | ISO-8601 UTC |
| `actor` | object | `{session, worktree, plugin}` — provenance: which session, which worktree, which plugin version wrote it |
| `body` | object | Kind-specific payload (see below) |

- **Review fact `body`** — the tree interval reviewed (`base_tree`/`head_tree` and their commits),
  `mode`, `roster` (roles + models), `files_reviewed`/`files_changed`, `findings[]` (each with a
  stable `fid`, `goal`, `severity`, `title`, `recommendation`), and `counts`.
- **Resolution fact `body`** — points at the finding it resolves (`{review_id, fid}`), the
  `disposition` (`fixed` | `waived`), the `verified_by` review that attests it, the `at_tree` it was
  verified against, and a `rationale` (required for `waived`). A resolution may only originate from a
  `verify-resolutions` review and must reference a finding already in the store (fail-closed).

**Tree-keying (the load-bearing idea).** Facts reference git *tree SHAs*, captured via a temporary
index that never touches the session's working tree or real index. Because a verbatim commit
preserves its tree, a fact recorded before commit still vouches for that tree from any checkout — so
the verdict is reproducible across worktrees and across time, not tied to a mutable branch pointer.

#### Governance Ledger — `.prawduct/.governance-ledger.jsonl` (gitignored)

Append-only telemetry of governance events (a consolidated review anchors a `review.critic` event
here). Distinct from the evidence store: the ledger is *observability* (what happened, for
audit/telemetry), the evidence store is *authority* (what the gate trusts). Intended to stay a
thin event trail, not a second source of truth.

### Tier 2 — Committed curated state (shared, source of truth for its domain)

#### Project State — `.prawduct/project-state.yaml`

The shared "answer store." Long-lived, hand- and tool-edited, committed. Holds product identity,
`classification.structural` (the six structural characteristics that drive artifact coverage),
`dependency_graph` (recorded design decisions and what they affect), `active_build_plan`, the
governance flags (`coverage_required`, `operator_verification_required`, `base_branch`), and
resolution-condition state that advisory probes read (so a committed answer clears a nag for the
whole team).

#### Backlog — `.prawduct/backlog.md`

Committed, structured Markdown (format v2). Each item: an ID line (`**[GOV-4M7K]** <title>`), a
backticked metadata bar (`effort · impact · area · source · added · status · stage · refs`), and an
optional body. Sections model lifecycle placement: `## Open` (pickable) → `## Promoted` (in an
active plan) → `## Archive` (shipped/dropped, append-only, bodies preserved). Items move only via
the backlog skill, never hand-edited across sections.

#### Learnings — `.prawduct/learnings.md` + `learnings-detail.md`

Committed. `learnings.md` holds one "When X, do Y because Z" rule per `##` heading plus a dense
summary; `learnings-detail.md` mirrors the headings 1:1 with the full narrative. Intent: the rule
is the durable, index-surfaced artifact; the narrative is a deep-read reference, kept out of the
hot path. Cross-linked to principles and backlog ids.

#### Operator Verification Queue — `.prawduct/operator-verification.md`

Committed, append-only queue of human-verifiable checks (`## VRF-<id>` entries with a `**Status:**`
of `pending` | `verified` | `accepted`). Gates the PR when `operator_verification_required: true`.

#### Change Log — `.prawduct/change-log.md`

Committed narrative log, kept separate from `project-state.yaml` for merge-friendliness (state holds
only a compact `change_log_history`).

### Tier 3 — Ephemeral / derived (per-session or regenerable)

- **`.critic-findings.json`** (gitignored) — derived *view* of the latest review fact, carrying a
  `fact_id` back-pointer. Regenerated by code on every consolidation; read only for content
  (briefing, builders), never for a verdict.
- **Dispatch manifest + partials** — `.prawduct/.critic-partials/manifest.json` (code-written at
  `critic-begin`: the tree interval + roster a review will attest) and `<role>.json` partials (one
  per reviewer, model-written, schema-validated before consolidation). The whole directory is removed
  on successful consolidation.
- **Critic-active marker** — `.prawduct/.critic-active` — presence signals a review is in flight;
  guards against a reviewer mutating the session under review, and carries a TTL so a crashed review
  self-clears.
- **Advisory store** — `.prawduct/.advisories.json` (gitignored) — the per-clone "nag log":
  `{schema_version, advisories[]}`, each advisory carrying its trigger evidence, `state`
  (`active` | `resolved` | `dismissed`), and dismissal/resolution metadata. Reconciled against the
  committed answer store on each sync; dismissals are sticky per-clone.
- **Session/gate state** — `.session-start`, `.session-base-tree`, `.session-git-baseline`,
  `.session-reflected`, `.gates-waived`, `.session-handoff.md`, `.test-evidence.json` — all
  gitignored, all reset at session `clear`. They hold the current session's identity, its diff
  baseline, its reflection, its gate waivers, and its most recent test-run evidence.

## Relationships

- A **dispatch manifest** defines the interval and roster for exactly one review; the reviewer
  **partials** it names are merged by consolidation into exactly one **review fact** (manifest → fact
  is 1:1, enforced by idempotency id).
- A **review fact** has many **findings** (each with a stable `fid`).
- A **resolution fact** references exactly one finding (`{review_id, fid}`) and is attested by
  exactly one later **review fact** (`verified_by`). Findings ← resolutions is one-to-many over time
  (a finding may be re-addressed), but a gate reads the latest attesting resolution.
- **`.critic-findings.json`** is derived from the single latest **review fact** (view → fact, via
  `fact_id`).
- **Advisory records** (per-clone nag log) reconcile against **resolution-condition state** in
  `project-state.yaml` (shared answer store): the committed answer is the input, the advisory state
  is the output.
- **Backlog items** are referenced by `refs`/`closes` from build plans and by `[[id]]` from
  learnings and norms; a shipped item moves to `## Archive` and is never deleted.

## State Machines

### Evidence fact (any kind)
`dispatched (manifest exists) → attested (fact appended, idempotent) → superseded (a later fact
references or overrides it)`. No transition ever mutates a prior fact; supersession is additive.

### Critic review (data-plane lifecycle)
`begin (manifest + active-marker written) → partials-collecting → consolidated (all roster partials
valid → review fact appended, view regenerated, partials + marker removed)`. Off-ramps:
`abandoned` (`critic-end` clears the marker with no fact) and `expired` (active-marker TTL elapses).
Consolidation is fail-closed: it persists only when *every* roster role has a schema-valid partial
at the dispatch commit.

### Backlog item
`idea → requirements → design → ready` (stage) and `open → shipped | dropped` (status). Shipped/
dropped items move to `## Archive`; the transition is explicit (via the skill), never a silent edit.

### Advisory
`active → resolved` (committed answer satisfies the resolution condition) or
`active → dismissed` (owner dismisses; sticky per-clone) → optionally `→ active` (undismiss). A
probe-version bump supersedes the old advisory id with a fresh one.

## Constraints

- **Facts are append-only.** No tool edits or deletes an existing fact line. (Read repair may skip a
  torn tail line, but never rewrites content.)
- **A verdict never reads a derived view.** Gates read facts; views are for display only.
- **A resolution fact requires a `verify-resolutions` origin and a pre-existing target finding** —
  fail-closed. A `waived` disposition requires a non-empty rationale.
- **The evidence store is shared per-clone via the git common dir**; every worktree appends to and
  reads the same log. Single-syscall append writes keep concurrent whole-line writes safe.
- **Committed vs. gitignored is a deliberate boundary, not incidental**: shared decisions are
  committed (`project-state.yaml`, `backlog.md`, `learnings*.md`, `operator-verification.md`,
  `change-log.md`); per-clone nags, caches, and session state are gitignored; the evidence store is
  uncommitted-by-construction (inside `.git`).
- **A newer-schema fact is surfaced, never dropped.** A record written by a plugin ahead of the
  reader's schema causes a loud block, not a silent skip — forward-incompatibility must be visible.
