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
  Rulings: none live. **[[regen-views-is-advice]] retired 2026-08-08 — subject removed, recorded here rather than deleted (GD4).** It extended this norm from who may **read** a view to what posture a view *writer* holds, for the one writer that existed. `regen-views` and the three views it wrote are gone; the build-plan `## Status` block that was the contested one is now hand-authored state, not a view at all. **This norm is strengthened rather than weakened by the retirement** — it now has no subsystem in which a governance-relevant derived view exists to be trusted. Its live subject is `.critic-findings.json` and kin, and the read-side rule below is unchanged. The writer-posture question returns only if a view writer does, and the sentence that answers it now sits on `architecture.md`'s side of the old collision.
- **A governance document reaches a terminal state; it is never deleted. Archival records what became of it and moves it out of the live directory — and a live document always outranks an archived namesake.** Three rules, one norm, because they are only correct together: (1) a build plan ends in one of exactly two terminal states — *completed* (shipped) or *superseded* (stopped, descoped, absorbed elsewhere) — stamped into its own frontmatter AND moved under `archive/`; (2) every reader that scans `artifacts/` treats `archive/` as history, never as a live assertion, and prunes it at directory level rather than walking and filtering; (3) a reader resolving a document by *name or scope* searches live first, then archive, and a live file wins.
  Why: the framework had assigned these documents the wrong lifetime, and both halves of the mistake cost real work. Deleting a completed plan stranded the requirements, hazards and findings that lived only in it — every reference into it dangled *by design*, and an authoring discipline (the ephemeral-ref firewall) existed solely to cope. Keeping every plan forever in the live directory is the mirror failure: `artifacts/` stops answering "what is in flight" and becomes a pile that has to be read to be sorted, and the scan that walks it runs at every session start and every session end. Two terminal states rather than one is load-bearing: a plan whose work was descoped can never satisfy "all boxes ticked", so a lifecycle with only *completed* leaves exactly those plans sitting live and reading as active — which is the confusion the norm exists to remove, and it is the common case, not a corner.
  Scope: documents under `.prawduct/artifacts/`. It does NOT reach the append-only evidence store, which is governed by the immutability norm above — archival moves a *document*, it never rewrites a fact.
  Status: steady-state as of v3.2.8. Mechanism: `plan_archive.archive_plan` (stamp-then-move, refusing rather than half-completing), `plan_index.iter_scoped_plan_candidates` (directory-level prune, live-walked-first when the archive is included), `release_readiness._find_release_plan` (live, then archive).
  Retroactivity: **migrate**, not contain — and this is the departure from the backlog-title norm above, so the reason is recorded rather than assumed. Accumulated live plans reading as active IS the confusion, so a rule that only bound new plans would leave every existing repo in the state the norm exists to fix. `plan-backfill` performs the sweep mechanically off the change log's `release=` tags; **checkbox state is explicitly not a precondition and is not corrected on the way in**, which is what keeps the migration free of the judgment that would otherwise put a model in the write path of state the Stop hook's gates read.
  Ruled 2026-08-08 (owner, requirements v0.4): backfilling existing shipped plans is required for this repo and for consumers, not deferred to "from now on".
  Ruled 2026-08-11 (owner, in-session, v3.3.1 / #634), amending the Retroactivity clause above: **checkbox state IS a precondition of the mechanical sweep. It remains no precondition at all of an explicit `archive-plan <path>`.** The sentence it amends said "explicitly not a precondition" without qualification, and read against the sweep that is now false; the half about not correcting boxes on the way in is untouched and still holds on both routes. Engaging the stated why, which is what makes this an amendment rather than a reversal: the concern was **keeping a model out of the write path** of state the Stop hook's gates read, and that is preserved exactly — the new precondition is a deterministic count of unticked `## Status` items (`buildplan_refs.incompleteness_reason`), with no model anywhere in it. What the sweep now does with a plan it cannot evidence as finished is *decline and name the chunk*, which moves the judgment to a human and OUT of the write path rather than into it. The norm's own two-terminal-state reasoning supplies the escape hatch and is why this does not resurrect the failure that reasoning names: a plan that can never satisfy "all boxes ticked" was never meant to be archived *completed*, it was meant to be archived **superseded**, which only a human can name a reason for — so a plan the sweep declines is one command from its correct terminal state, not stranded live forever. Occasioned by a consumer repo (hallucinote) archiving a plan as `completed`/`released_in: v1.8.0` with two chunks unbuilt and still live: selection by change-log `release=` answers "did the scope ship", never "did the plan finish", and those come apart whenever a scope ships partially. That product had declined the identical proposal at two consecutive cuts and recorded the decline both times before the third went through — the cost of a judgement the tooling re-asks every release.
- **Every issue written to the backlog store conforms to the issue standard's §1 title rules — on every write path, `file` / `update` / `import` alike. Where a source title does not conform, the agent rewrites it; a non-conforming title is not written.**
  Why: the title is the handle every later reader triages by, and a non-conforming one fails silently — it reads badly forever and nothing complains. The failure is proven at scale: a 396-item migration reached GitHub with parsed titles up to 2319 characters against a 72-character budget, and only the handful breaching GitHub's own 256 cap announced themselves. Enforcing at the write path is what makes the standard binding rather than aspirational, and the standard (`documentation/backlog-service-issue-standard.md` §1) stays the one home for the rules themselves — this norm binds *that* they are enforced, never restates them.
  Scope: the backlog adapter's write paths. NOT the markdown backend's hand-authored bullets, which are the *source* a migration scrub rewrites.
  Status: **steady-state** as of #614. All three write paths refuse a non-conforming title: `file` and `update` through `core._title_refusal`, `import` through `migrate.preflight_titles`, which validates the whole corpus before its first write. The interim hand-conformance rule is retired — conformance now rests on a refusal rather than on the agent having read the standard.
  Retroactivity: **contain** — existing corpora are NOT migrated to conformance by this norm, and the containment boundary is the write path (everything written from here conforms; what is already stored does not change). Ref **#614**, whose scrub half is where retro-conformance would happen if it ever does. The reason it is contain rather than migrate is the standard's §1 altitude rule: a scrub rewriting titles item-by-item cannot see that three issues are one defect, so a bulk retro-conformance pass run before the dedup sweep's shared-root-cause question exists would entrench an over-split backlog — worse than the run-on titles it fixes.
  Mechanism: `issuefmt.lint_title` (`title-too-long` / `-too-short` / `-placeholder` / `-non-atomic`), blocking on all three write paths. Body lints stay WARN-only by the same ruling — a body budget blocking an edit to an unrelated field is the confirmation-fatigue shape `security-model.md`'s approval norm rejects.
  Ruled 2026-08-06 (owner): *"They must be EXCELLENT issue titles, always, whether migrated or created new or modified."* Superseded the standard's prior "WARN only, never blocks" posture, amended in §4 of that document.
  Ruled 2026-08-06 (owner), scope of the `update` path: **the refusal gates the title BEING WRITTEN, not the issue's resulting title.** `update <id> title=…` is refused when the new value fails §1; `update <id> status=shipped` on an issue whose *stored* title fails §1 **succeeds**, emitting a named non-blocking lint finding that says the title was not changed. Why, engaging this norm's own `Retroactivity: contain`: an **agent**, not a human, sits at this write — nothing automated calls `file`/`update` — so gating every field on the stored title would not block the ~11% of live issues predating the rule (20 of 180 measured 2026-08-06), it would make an agent silently **retitle** them to get past the gate, one at a time, as a side effect of archiving them, with none of the aggregate owner approval the import scrub preserves. That is retro-conformance by the back door, which this norm's Retroactivity line forbids, and §1's altitude rule says item-by-item rewriting is precisely how an over-split backlog gets entrenched.
- **A fact written by a newer schema than the reader is surfaced as a loud block, never silently dropped.**
  Why: forward-incompatibility must be visible — silently skipping an ahead-of-schema fact would let a gate render a verdict on incomplete evidence.
  Status: steady-state. Mechanism: `evidence status` exit 2 (schema-ahead).
- **Two stores, two lifetimes: shared committed *answers* are kept distinct from per-clone, gitignored *nags and caches*.**
  Why: a teammate's committed decision must resolve state for everyone, while local nag/cache/session state must never pollute the shared record; collapsing the two would either leak local state into the repo or block a shared decision from propagating.
  Status: steady-state.
- **`backlog_service_repo` selects which backlog store is authoritative; once it is set, `.prawduct/backlog.md` is frozen history and no reader treats it as live state.** Readers reach the backlog through `/prawduct:backlog`, which routes on both sides of a cutover. A direct read of the markdown file is permitted only after checking the scalar and finding it **unset**, and only for detail the skill's views don't carry (full item bodies, for instance); writes never bypass the skill on either backend.
  Why: the markdown file survives the cutover intact, so every item archived at cutover still parses as open — a direct read answers with identical confidence whether it is right or months stale, and a confident wrong answer is indistinguishable from a clean bill of health. The gate, not a blanket ban, is the rule: banning direct reads outright would retire the janitor's full-body overlap read with no live replacement, which is the bespoke per-reader projection the read-through cache exists to avoid.
  Status: **ratified but unenforced on `main` as of v3.1.1** — the norm binds, its enforcement does not exist in the shipped tree. `backlog_service_repo` is read by no code and appears nowhere in `project-state.yaml` at v3.1.1: the release deliberately withheld the whole backlog-service surface, and the scalar went with it. The norm is therefore vacuously satisfied (there is one backend, so nothing can read the wrong one) and returns to steady-state when v3.2.0 lands the adapter. Do not "fix" this by deleting the norm — it was legitimately ratified 2026-07-20 and the code is on `feature/backlog-service`.
  Retroactivity: migrate — the reader inventory was swept across `skills/` and `lib/` at birth and every reader is gated (`lib/` probes and the briefing guard on the scalar; the Critic, PR reviewer, and janitor state dormancy). `skills/pr/SKILL.md` had overstated the rule as an unconditional ban and was corrected in the birthing changeset. No residual sites, so no tracking item.

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
| `kind` | string | Fact namespace — `review`, `resolution`, `disposition`, `guard-refusal` today; `test-run`, `pr-review`, `promotion` reserved (intended) |
| `id` | string | Idempotency key, fixed at dispatch — re-running consolidation never double-appends |
| `ts` | string | ISO-8601 UTC |
| `actor` | object | `{session, worktree, plugin}` plus optional `branch` — provenance: which session, which worktree, which plugin version wrote it. `branch` is omitted (never null) on a detached/unreadable HEAD; it exists because the worktree path alone cannot say whether a tree was disposable (#648), and a reader cannot probe a tree that is usually already deleted |
| `body` | object | Kind-specific payload (see below) |

- **Review fact `body`** — the tree interval reviewed (`base_tree`/`head_tree` and their commits),
  `mode`, `roster` (roles + models), `files_reviewed`/`files_changed`, `findings[]` (each with a
  stable `fid`, `goal`, `severity`, `title`, `recommendation`), and `counts`.
- **Resolution fact `body`** — points at the finding it resolves (`{review_id, fid}`), the
  `disposition` (`fixed` | `waived`), the `verified_by` review that attests it, the `at_tree` it was
  verified against, and a `rationale` (required for `waived`). A resolution may only originate from a
  `verify-resolutions` review and must reference a finding already in the store (fail-closed).
- **Disposition fact `body`** — the builder's answer to a finding that was *not* fixed: the target
  (`{review_id, fid}`), an `action` (`accept` | `file`), a `reason` (accept) or `backlog_id` (file),
  and an `owner_ruling` (required to accept a BLOCKING finding). Field named `action`, not
  `disposition`, because that word already carries two other vocabularies here — release scope
  (`ships`/`withheld`) and resolution (`fixed`/`waived`). **A disposition never resolves anything:**
  gate composition filters on `kind` before reading a body, so a BLOCKING finding stays blocking until
  a real resolution lands. Written by the builder via `prawduct-hook disposition` (validated join, no
  reviewer in the loop); a changed answer is a newer fact under a sequenced id, and last-recorded
  wins. **Droppability:** a disposition sits on no coverage path, so the store's reachability rule
  cannot speak to it — a disposition fact is droppable exactly when the review fact it targets is,
  and never on its own. Compaction that violated this would silently un-answer a finding; the
  sequenced id defends against it by stepping past ids already present rather than counting
  surviving history.
- **Guard-refusal fact `body`** — that a **pre-dispatch guard** fired: a control that declined to
  spend something (a reviewer, a build) *before* spending it. Carries the `guard` name (the grouping
  key every yield query groups on, and the authority even if a caller's body offers its own), the
  `interval` it judged, and whatever that guard needs to answer its own yield question later — for
  `critic-dispatch-free-interval`, the `free_files` it waved through plus `mode`/`scope`/`chunk`/
  `branch`. **The interval is nested under `interval`, never spread to the body's top level**, which
  is where a coverage edge carries `base_tree`/`head_tree`: one level down, no reader walking bodies
  for edges can mistake a refusal for one. **This kind is purely observational and CANNOT become
  authoritative** — composition derives edges from `kind == "review"` alone, so a refusal contributes
  neither node nor edge and can only ever coexist with a verdict, never produce one. It exists
  because `nonfunctional-requirements.md` requires a control to emit its expected yield observably;
  a guard whose only output is stderr can never be measured, and therefore never retired.
  **Droppability:** a refusal sits on no coverage path and targets no other fact, so it is droppable
  at any time — dropping one loses a data point about the guard's yield, never a governance answer.
  Written by `evidence.append_guard_refusal`, the one sink for the whole class (#596).

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
  (briefing, builders), never for a verdict. Between a `critic-begin` and the consolidation that
  replaces it the record holds the *previous* review, so `critic-begin` stamps it
  `superseded_by` / `superseded_at` / `superseded_notice` (first keys in the file) and leaves every
  other field untouched — the view says which review it is and which one displaced it, rather than
  leaving a reader to compare timestamps. It is stamped rather than deleted because `fact_id` is the
  anchor a `verify-resolutions` dispatch reads, and a review abandoned before consolidating must
  still leave the last completed review anchorable. Consolidation rewrites the whole record, so the
  keys clear themselves.
- **Dispatch manifest + partials** — `.prawduct/.critic-partials/manifest.json` (code-written at
  `critic-begin`: the tree interval, the roster a review will attest, and `rendezvous`, the resolved
  per-role write paths) and one partial per reviewer at those paths (model-written, schema-validated
  before consolidation, each declaring the `dispatch_id` that binds it to its review). Partial paths
  are keyed by review id, so two reviews in one worktree never share a name; the shape lives in
  `critic_consolidate.partial_path` and nothing else spells it. The whole directory is removed on
  successful consolidation.
- **Review archive** — `.prawduct/.critic-partials-archive/<review-id>/` (gitignored) — where a
  review's manifest + partials go instead of being deleted, whenever a dispatch sweeps leftovers or
  `critic-discard` clears a stranded roster. **Not debris**: it is the last trace an unconsolidated
  review ever ran, and it is operator-addressable — `critic-restore <review-id>` copies a set back
  so it consolidates under its *own* id, which is sound only because partials carry review identity.
  Bounded: the newest three sets are kept, pruned best-effort at dispatch. A set archived before
  review-id keying carries no `rendezvous` and therefore restores as readable evidence that cannot
  be recorded as a fact; the restore says so rather than promising a consolidation.
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
`abandoned` (`critic-end` clears the marker with no fact), `expired` (active-marker TTL elapses),
and `archived` — a sweep at dispatch or a `critic-discard` moves the manifest + partials to the
review archive rather than deleting them. `archived` is the one off-ramp that is not terminal:
`critic-restore <review-id>` returns a set to `partials-collecting` **as the same review**, so it
can consolidate to a fact carrying its own id. Consolidation is fail-closed: it persists only when
*every* roster role has a schema-valid partial at the dispatch commit.

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
