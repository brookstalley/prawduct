# Issue #240 — Governance: Treat Strategy-Artifact Backfill as Retroactive Discovery: Design

`status: draft · stage: design · area: governance · added: 2026-08-22 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/240`

Builds on `documentation/issues/240-requirements.md` (BKF1–BKF9, Decisions 1–8). The requirements
doc left three things open for design: the exact Critic check (name, severity, judgment
mechanism), the `/prawduct:doctor`-vs-discovery UX for the mode fork and Type 2 handling, and the
code path confirming a strategy-class `(not relevant — X)` stub is subject to the
structural-characteristic re-open (BKF9). This document resolves all three, plus the concrete
opt-out mechanics (BKF7) requirements left as "one new preference" without saying where it lives.

## Summary of what ships

Six methodology/doc files, no code — this item's own Decision 1 already ruled out new detection
code, and every remaining mechanism (the coverage nudge's recurrence, the `(not relevant — X)`
stub, the norm lifecycle, the Critic's prose-based judgment) already exists and is reused as-is:

1. **`plugin/methodology/discovery.md`** — new `## Backfilling a Strategy-Class Artifact` section:
   the mode fork (BKF1), the Direction-population rule (BKF2/BKF3), and the three opt-out layers
   (BKF7), each pointing at its canonical mechanism rather than restating it. One added clause in
   the existing `A structural characteristic flipped` section, making stub re-open explicit
   (BKF9).
2. **`plugin/docs/norms.md`** — one added clause in `### Ambient norms — structural
   characteristics`, step 2, naming stub re-open as part of re-derivation (BKF9's canonical home).
3. **`plugin/skills/doctor/SKILL.md`** — one new `needs-a-ruling` fork kind in the Norm
   Ratification Flow, `sub-optimal-by-choice` (BKF5, Type 2's canonical procedure).
4. **`plugin/methodology/planning.md`** — new `### Backfill: Direction Elicitation` subsection,
   defining the `**Backfill:** <artifact>` chunk annotation (mirrors `Foreign API`/`Exposed API`).
5. **`plugin/skills/critic/goals-1-3.md`** — one new Goal 2 bullet, scoped exclusively to
   `**Backfill:**`-annotated chunks (BKF6).
6. **`plugin/templates/project-preferences.md`** — one new `## Workflow` row, "Backfill nudges"
   (decline-everything, BKF7's third layer).

No new probe, no new hook, no new `project-state.yaml` field. Test plan: none — see
"Verification" below (the same reasoning as sibling design #622: methodology text has no
executable surface of its own; the Critic bullet is exercised the first time a real `**Backfill:**`
chunk is reviewed, same as `Foreign API`'s bullet was).

## Decision 1 — the mode fork lives in `discovery.md`, keyed off the existing coverage signal, not a new one

Requirements' Decision 1 already ruled out a new mid-conversation detector; the fork is offered
the moment `/prawduct:methodology planning` is invoked to author a `strategy-artifact-missing`
advisory's target **and** the product already shows code (`coverage_probes.discovery_expected` /
`gitstate._has_product_definition_work` — the same signal `probe_discovery_not_captured` already
reads to decide a repo has product-definition work). Placement: right after `## Reconciling an
Existing or Docs-First Product` (`discovery.md:71-80`) — that section is the product-level version
of exactly this problem (material precedes `project-state.yaml`); this section is the per-artifact
version (code precedes one strategy-class doc). Keeping them adjacent means a reader who already
knows one recognizes the shape of the other instead of two unrelated conventions.

**Why the interview does the ratifying itself, not a deferred `/prawduct:doctor` step.** The
requirements doc's grounding note (quoting the issue's own design refinement) is explicit that
solo-authored artifacts have no Direction sections because ratification needs the owner present —
"the interview produces Layer 1 + Layer 2 together." Deferring Type 1/Type 2 resolution to a later
`/prawduct:doctor` run would reintroduce the exact gap this item exists to close: an agent drafting
alone, again, with the owner's ratification bolted on afterward instead of woven through the
session that drafted the words. So the full Type 1/Type 2 procedure is exercised **live**, inside
the backfill interview — `doctor`'s Norm Ratification Flow gains the same fork kind (Decision 3
below) only so a norm proposed *outside* a backfill session — an ordinary `/prawduct:doctor
ratify-norms` pass over an existing artifact — gets the identical handling, not a lesser one.

## Text — `plugin/methodology/discovery.md`

Insert after line 80 (`## Reconciling an Existing or Docs-First Product`'s closing paragraph), a
new section, verbatim:

```markdown
## Backfilling a Strategy-Class Artifact

Authoring a strategy-class artifact (data model, security model, NFR, operational spec,
observability strategy, plus the characteristic-triggered API contract and architecture) for a
product whose code already exists is a **different task from writing one at inception**, and
treating it as an ordinary solo draft reliably produces the wrong document: an agent working alone
tends to describe what the code already does, which is coverage but not direction — the file
exists, but no decision stands behind a word in it (`/prawduct:methodology norms` § Anatomy). This
section is the interview that closes that gap, offered by `/prawduct:methodology planning` the
moment it is invoked against a `strategy-artifact-missing` advisory target on a product where code
already exists.

**Fork the mode before drafting a line.** Two questions, both cheap and both vetoable
(`[ASSUMPTION: …]`):

1. **Draft-from-what's-built, or first-principles?** The former reads the code and states what it
   does as the starting draft; the latter starts from what the artifact *should* say and treats the
   code as one input among several. Either is legitimate — the fork exists so the choice is made,
   not defaulted.
2. **Capture current state, or set direction?** The defining choice this section exists for.
   "Capture current state" is an honest, permitted outcome (BKF3 below) — not every artifact needs
   to lead the code, and Principle 3 (Living Documentation) governs a descriptive artifact exactly
   as it governs any other document. "Set direction" commits to stating intended design — the
   target you would defend to a skeptic, flagging any place current code falls short as an
   explicit decision rather than silently enshrining it.

**A "set direction" backfill closes with a populated `## Direction` section — never bare, never
absent.** At least one entry (Statement + Why + Status, per the existing Anatomy of a Norm) before
the artifact is considered authored. A "capture current state" backfill is explicitly permitted to
leave `## Direction` absent; this section does not force intent-stating on an owner who has
declared the doc is descriptive by choice.

**Two kinds of divergence surface once you elicit intent, and they take opposite handling** — reuse
`/prawduct:methodology norms`'s lifecycle wholesale, invent nothing new:

- **Type 1 — the elicited direction is genuinely better than what the code does.** This is an
  ordinary norm birth over existing violations: born `Status: in-transition`, the gap recorded as
  sized backlog work wired as the tracking ref (`norms.md` § Birth, the Migrate disposition). The
  code is what's wrong here, not the words.
- **Type 2 — the owner wants to ratify a practice you would not recommend.** Never withhold
  ratification — every best practice is a defeasible heuristic, and the owner may hold context you
  don't. But elicit the *why* before recording anything, and label the outcome honestly rather than
  laundering a known-suboptimal choice as recommended practice. This is the `sub-optimal-by-choice`
  fork of the Norm Ratification Flow (`plugin/skills/doctor/SKILL.md`) — read it there; the
  procedure is the same whether it's reached from a backfill interview or an ordinary
  `/prawduct:doctor ratify-norms` pass, and it has exactly one home.

**Declining costs you nothing you didn't already have — three layers, two of them mechanisms
you already know:**

- **Decline once** ("later") — say nothing gets written, and the nudge simply returns the next
  session the same coverage trigger fires (`coverage_probes.py`'s existing per-session recurrence
  — no new state, no stub, no calendar).
- **Decline this doc** ("not needed because X") — write the artifact as a one-line
  `(not relevant — X)` stub. The **same** stub `strategy-artifact-missing` already treats as valid
  coverage (`coverage_probes.py`) — this is not a second mechanism, it is that one, reached through
  this fork. A stub written this way is subject to the same structural-characteristic re-open every
  stub is (see "A structural characteristic flipped" below).
- **Decline everything** ("stop proactively asking") — a reversible project-scoped preference,
  `project-preferences.md`'s `## Workflow` → `Backfill nudges: suppressed`. Suppresses the
  *proactive* offer only; `/prawduct:doctor`'s coverage-status check and on-demand authoring are
  unaffected — an opt-out from being asked is not an opt-out from the answer existing.
```

Extend the existing `A structural characteristic flipped` paragraph (`discovery.md:55-64`) — append
one sentence after "…a sensitive-data flip re-opens the security model)":

```markdown
 — including re-opening any `(not relevant — X)` stub standing in for a now-triggered artifact:
re-deriving the artifact set means treating that stub as unresolved, not leaving it standing
because a file already exists at that path (`/prawduct:methodology norms` § Ambient norms).
```

## Decision 2 — BKF9's canonical mechanism lives in `norms.md`, not a new probe

Requirements left "confirming/wiring the exact code path" open. Grounding this pass: no code path
exists today, and none needs to. The flip's own enforcement is already a review-time check —
`norms.md`'s Ambient norms section states "The flip changeset's review verifies all three
happened," where "three" is record-the-flip / re-derive-the-artifact-set / run-an-assumption-audit.
A `(not relevant — X)` stub for the now-triggered artifact is exactly what "re-derive the artifact
set" already covers *in scope* but not *in words* — the fix is to say so explicitly, so a reviewer
checking re-derivation has the stub case named rather than inferring it. This is a documentation
precision fix, not new machinery: no mechanical hook is added (norms.md's own Deliberate
Non-Design already forecloses "no mechanical divergence gates" for anything short of the canonical
Session-sync list, and a stub going stale on a characteristic flip is exactly the kind of judgment
call that list explicitly excludes).

## Text — `plugin/docs/norms.md`

In `### Ambient norms — structural characteristics`, extend step 2 (currently: `**Re-derive the
structurally-triggered artifact set** under the new characteristics (security model, data model,
observability, test spec — the same machinery discovery uses at inception).`) by appending:

```markdown
 Re-derivation includes any existing `(not relevant — <reason>)` stub for a now-triggered
artifact: the stub answered a question under the *old* characteristics, and a flip re-opens it for
authoring exactly as if the artifact had never existed — a stub is not grandfathered by the file
already being present at that path.
```

## Decision 3 — Type 2 is one new fork kind in the existing Ratification Flow taxonomy, not a new flow

`doctor/SKILL.md`'s Norm Ratification Flow already enumerates `needs-a-ruling` fork kinds
(aspirational, practice-not-written, wording/scope fork, collision/ambiguous, whyless) — each with
its own resolution shape, surfaced individually, never bulk-confirmed. Type 2 (the owner wants to
ratify a practice below best practice) is a sixth kind of the same taxonomy, not a parallel
mechanism: it belongs in the same enumeration, gets the same "surfaced individually with its fork"
treatment the other five already get, and inherits the flow's existing write rule (only what the
owner confirmed, additive, into Direction sections and Enforcement rows).

## Text — `plugin/skills/doctor/SKILL.md`

In step 2's `needs-a-ruling` bullet, after `**whyless** (the rationale can't be stated without the
owner — backfill first).`, insert:

```markdown
 **sub-optimal-by-choice** (the owner wants to ratify a practice you would not recommend — e.g.
"never use comments," "plaintext credentials to this offline device"): never withhold
ratification — every best practice is a defeasible heuristic, and the owner may hold context you
don't (Principle 23). Elicit the *why* first rather than pre-judging the practice bad; the why
often reveals the practice is right in this context. Then ratify — always — but label the outcome
by how the why held up, not by whether you agree: a why that resolves your concern records as an
ordinary, context-specific decision (not "against advice" — you were working from partial
context); a why that doesn't still ratifies, with your unresolved concern noted alongside the
norm rather than omitted. The only outcome this fork forbids is **laundering** — recording a
knowingly sub-optimal choice as if it were recommended practice.
```

## Decision 4 — the Critic check is a chunk annotation, mirroring `Foreign API`/`Exposed API`, not a new detection mechanism

Requirements' BKF6 needs the Critic to catch "purely restates current behavior, no elicited
rationale" **only** on backfill-authored Direction content, never as a general documentation rule
(Decision 6, requirements doc). The Critic (`goals-1-3.md`) has no way to know a given `##
Direction` section was populated through a backfill interview unless the plan says so — and
`methodology/planning.md` already has exactly this shape twice over: `**Foreign API:** <name>`
triggers a `verify-api` Done-when check, `**Exposed API:** <name>` triggers the
versioning/error-model decision check. Both are chunk-frontmatter-adjacent annotations the planner
writes and the Critic's Goal 2 keys off with a single WARNING bullet — no new module, no new
`prawduct-hook` subcommand. A `**Backfill:**` annotation is the same shape: narrow by
construction (only chunks that carry it are in scope), so it cannot leak into Principle 3's
governance of every other document.

**Severity: WARNING**, matching the Foreign-API/Exposed-API precedent exactly (a missing required
decision on an annotated chunk) rather than BLOCKING (reserved for undocumented architectural
decisions and norm departures, per the Normative-authority paragraph two lines above where this
bullet lands — a thin or restated Direction entry is a *quality* defect in newly-authored content,
not a departure from an already-ratified norm).

## Text — `plugin/methodology/planning.md`

New subsection after `### Exposed API: Versioning, Deprecation & Error Model` (`planning.md:198`),
same heading level and shape:

```markdown
### Backfill: Direction Elicitation

**The rule.** A chunk that authors or backfills a strategy-class artifact through
`/prawduct:methodology discovery`'s "Backfilling a Strategy-Class Artifact" fork declares
`**Backfill:** <artifact-filename>`. The Critic's Goal 2 emits a **WARNING** when a
`**Backfill:**`-annotated chunk's resulting `## Direction` section is either absent (in "set
direction" mode — see discovery.md) or present but restates current code behavior with no
distinguishable elicited rationale beyond "this is what exists." The annotation is what triggers
the check — a Direction section authored outside this flow is Principle 3's ordinary territory,
untouched.
```

## Text — `plugin/skills/critic/goals-1-3.md`

New bullet under `## 2. Nothing Is Missing`, immediately after the `**Foreign API**` bullet
(placed with its two siblings, same list):

```markdown
- **Backfill**: chunks with `**Backfill:** <artifact>` must leave `## Direction` populated with
  elicited rationale, not bare/absent (`set direction` mode) and not a restatement of current
  behavior with no distinguishable "why" beyond describing the code → **WARNING** if either.
  Scoped exclusively to `**Backfill:**`-annotated chunks — never a general documentation check.
```

## Decision 5 — "decline everything" is a `project-preferences.md` row, not a new state file

BKF7's third layer needs one durable, reversible, project-scoped bit. `project-preferences.md`
already hosts exactly this shape of decision (`Delegation`, `PR creation` — "ship a safe default,
make it configurable," `discovery.md` § Surface Behavioral Choices) and its `## Workflow` section
is where behavioral toggles like this live; no new heading, no new file, no `project-state.yaml`
field (that file is product classification, not developer/workflow preference — the two are kept
separate everywhere else in the framework).

## Text — `plugin/templates/project-preferences.md`

New row in `## Workflow` (`project-preferences.md:40-50`), after the `Delegation approval` row:

```markdown
- **Backfill nudges**: enabled (default: enabled — proactively offer the backfill-interview mode
  fork, per `/prawduct:methodology discovery` § Backfilling a Strategy-Class Artifact, when a
  strategy-class artifact's coverage trigger fires on a product with existing code; set to
  "suppressed" to stop the proactive offer only — `/prawduct:doctor`'s coverage-status check and
  on-demand authoring are unaffected.)
```

## Verification

No automated test — every touched file is prose read by a capable model (methodology guidance, a
Critic judgment bullet, a template row default), matching sibling design #622's reasoning exactly:
this class of change has no executable surface to pin with a test, and inventing one (a greppy
heuristic for "restates current behavior") would be the false-confidence trap
`project-preferences.md` § Enforcement itself warns against. The Critic bullet is exercised the
first time a real `**Backfill:**` chunk reaches review — same as `Foreign API`'s bullet was, per
`planning.md:196`'s own history.

## Acceptance cross-check (against requirements' Acceptance list)

- BKF1/mode fork — `discovery.md` new section, offered before authoring: done via Decision 1's
  text.
- BKF2/BKF3 — "set direction" cannot close bare; "capture current state" may: stated in the same
  section, enforced by the Decision 4 Critic bullet for the case that reaches a chunk review.
- BKF4 — Type 1 = Migrate, no new mechanism: stated, no new text needed beyond the pointer already
  in Decision 1's section (norms.md's Birth section is unchanged).
- BKF5 — Type 2 always ratifies, elicits why, labels honestly: Decision 3's new fork kind, full
  text.
- BKF6 — Critic check scoped to backfill-populated Direction content only: Decision 4, the
  `**Backfill:**` annotation confines it by construction.
- BKF7 — three opt-out layers, two reused: Decision 1's section (decline-once, decline-this-doc)
  plus Decision 5 (decline-everything).
- BKF8 — no new mid-conversation detector: nothing in this design adds one; Decision 1 keys off the
  existing coverage signal only.
- BKF9 — stub re-open on characteristic flip: Decision 2, extending the existing flip-review
  language in both `discovery.md` and `norms.md`.

Next: build plan / implementation chunk. All six edits are additive text insertions into existing
files — a single `Type: doc-only` chunk covers the whole item, with `**Backfill:**` itself not
applicable (this chunk documents the mechanism; it does not exercise it).
