# Norms — Normative Authority Across Governing Artifacts

A **norm** is a statement in a governing artifact that **binds future work**: a declared
substrate, pattern, convention, or constraint that new and changed code must honor. Norms are
how a product's architectural direction survives contact with a hundred future diffs.

The failure this spec exists to prevent: prawduct's coherence machinery keeps artifacts
**fresh** — when code and artifact disagree, the artifact gets updated to describe reality
(Principle 3, Living Documentation). Applied to a norm, that reflex runs backwards: work that
diverges from a declared direction gets *documented as the new reality*, and the divergence is
laundered into legitimacy through the documentation-upkeep pipeline itself. Every reviewer
correctly executes their instructions and the wrong outcome still ships, because the framework
had no concept that some statements **lead** the code rather than follow it.

## The Authority Rule

> **Norms bind; descriptions track.** When work departs from a normative statement, that
> departure is an architectural decision. Exactly four resolutions exist, and three of them are
> recorded decisions: **conform**, **amend** the norm, record a **ruling** at its edge, or take
> a **bounded exception**. What is never available is silent departure. When code diverges from
> a *descriptive* statement, update the artifact — that is ordinary documentation upkeep.

**Severity, stated once and generally:** any departure from a governing norm without a recorded
decision — and any change to normative content without one, and any norm birth without capture —
is an **undocumented architectural decision**: the Critic routes it to Goal 3, **BLOCKING**.
This applies to every form in this spec (amendments, rulings, exceptions, stopgaps,
retroactivity, characteristic flips), so no individual rule below needs its own severity.
**Scoped to adoption:** BLOCKING presumes the product has adopted norms to depart *from* —
any `## Direction` section in `.prawduct/artifacts/*.md`, or norm rows in the preferences
Enforcement table. **Recorded classification fields count as adopted too:** recording a
structural characteristic is how an ambient norm is adopted, so silently flipping a
*recorded* characteristic is BLOCKING even where no Direction section exists (a
never-recorded characteristic has no norm to depart from). In a product with **no** adopted
norms on any of these surfaces, the same detections surface as **NOTE** (name the would-be
norm and its capture path — a Direction entry or preferences row);
a repo is never blocked into a lifecycle it has not adopted. The PR reviewer's norm-amendment
check emits **WARNING** at its layer regardless (the cumulative Critic is the blocking organ —
`skills/pr/review-protocol.md` explains the layering).

Two corollaries:

- **A reviewer's judgment that a departure looks correct never substitutes for the decision.**
  It shapes the recommendation ("record the ruling" vs. "conform"), not whether a decision is
  required — a reviewer waiving a norm unilaterally is the same decision-by-default, relocated.
- **The structural tell:** a changeset that edits a governing artifact's normative content to
  match its own code is the *aggravated* form of unrecorded amendment — but an amendment needs
  the recorded decision whether or not code rides along (a doc-only norm edit followed later by
  conforming code is the same laundering, split in two).

### What counts as a recorded decision

One standard, used by amendments, rulings, exceptions, stopgaps, retroactivity decisions, and
characteristic flips alike:

- **Owner-visible and vetoable** — the plan/changeset carries it in the vetoable block form
  `[DECISION: <what was decided> | <why, engaging the norm's why> | user can veto/override]`
  (the decision sibling of `methodology/planning.md`'s `[ASSUMPTION: …]` form), or the owner
  made the call directly. The builder may *draft* the decision; the owner's veto window is what
  legitimizes it. A builder-authored rationale sentence, alone, is not a recorded decision.
- **Reasoned** — it engages the norm's why, not just the local convenience.
- **Timely** — it lands with or before the departing change, never as post-hoc paperwork
  discovered by a later review.
- **Durably homed** — rulings in `learnings.md` linked from the norm; amendments in the norm's
  own entry; exceptions and stopgaps on backlog items (below); flips in
  `project-state.yaml` classification.

## Normative vs. Descriptive — the test

A statement is **normative** when a *decision stands behind it*: it was written to record a
chosen constraint — something the team decided ought to stay true, for reasons that outlive any
single implementation. A statement is **descriptive** when it *reports* current behavior and
changing the code should change the sentence, unmaking nothing.

The working test: **"If the code changed and this sentence were updated to match, would a
decision have been silently unmade?"** Yes → normative. No → descriptive.

Sentence form does not decide this — "All API timestamps are UTC ISO-8601" and "the exporter
batches every 5s" are grammatically alike, and the second is normative in a context where the
5s cadence was chosen to meet a freshness commitment. What decides is whether a why stands
behind the sentence. That is exactly why markers exist: Direction sections and preferences rows
make the classification cheap and prior. For unmarked prose the test is applied with judgment —
and **when classification is genuinely ambiguous, the ambiguity is resolved by ruling or by
marking the statement, not silently in either direction.** The test applies equally to
sentences a changeset *introduces*: adding normative content in a diff is **norm birth** and
routes to Birth below — it does not become binding-by-stealth or descriptive-by-default.

## Where Norms Live

Norms live where they already live — **no new file class, no norm IDs, no schemas**:

- **`project-preferences.md` rows** — code-level conventions. The Enforcement table is the
  product's norm **index**: each norm has a row assigning its enforcement mechanism
  (linter / test / Critic) and its audit home (janitor / advisory). A row may be a **pointer**
  ("norm lives in `observability-strategy.md` § Direction") instead of a restatement. The
  assigned mechanism must exist; if it doesn't yet, its creation is filed as backlog work at
  birth — a mechanism that is named but never built is the aspirational failure with extra
  steps.
- **`## Direction` sections in strategy-class artifacts** (observability strategy, security
  model, architecture, API contract, NFRs, operational spec, data model) — architectural norms,
  kept next to the descriptive content they govern. Within an entry, the Statement / Why /
  Status / Retroactivity / Rulings fields are normative; attached examples and current-state
  notes are descriptive surroundings, updatable as ordinary upkeep.
- **`project-state.yaml` classification fields** — the *ambient* norms: structural
  characteristics (`has_multiple_party_types`, `handles_sensitive_data`, `runs_unattended`, …). These are
  their own index and take no Enforcement-table row; their machinery is the characteristic-flip
  protocol below plus the doctor's classification-currency check.

Rulings live in `learnings.md`, cross-linked — norms are statute, learnings are case law, and
each reads better for pointing at the other.

## Anatomy of a Norm

A Direction entry (or preferences row) carries these parts:

```markdown
## Direction

- **All telemetry rides OpenTelemetry.** New instrumentation emits OTel spans/metrics; payload
  records may live in domain stores keyed by span/trace ids — never as a parallel correlation
  system.
  Why: one substrate for causality across turns, tools, and eval; a second system makes every
  consumer integrate twice and every future async surface reinvent it.
  Status: in-transition — collector export tracked in OBS-4C1K; interim: new work emits spans
  even where export is pending; work the substrate cannot yet serve escalates, never improvises.
  Rulings: [[otel-payload-store-ruling]]
```

- **Statement** — one sentence stating the constraint, scoped. Bold.
- **Why** — **required.** The why does triple duty: it is the input to boundary rulings (does
  the rationale bind this new scenario?), the arbiter in collisions (which why is at stake?),
  and the norm's expiry metadata (a why that references a condition or tracked work item
  becomes checkable — when the condition dies, the norm goes up for review). Where the
  rationale rests on tracked work, **cite the backlog id literally** — that is what makes decay
  mechanically detectable. A norm captured without its why is unenforceable at the edges and
  immortal at the center.
- **Status** — `steady-state` (default, may be omitted) or `in-transition`. An in-transition
  norm **must** name its tracking backlog item — the item covering the *remaining* work, not a
  mostly-done umbrella — and an **interim rule** (what new work does while the transition is
  incomplete).
- **Retroactivity** — present when the norm was adopted over existing code (see Birth): names
  the outcome and its record (`migrate: <item>` | `contain: <boundary artifact>` |
  `grandfather: <inventory ref>`).
- **Rulings** — links to learnings entries recording boundary and precedence decisions. Norms
  accrete case law; the statement stays short.

## Lifecycle Rules

### Birth — capture and retroactivity

A norm is born when the owner declares one, or when one surfaces mid-build ("we should always
X") — the mirror of the requirements tripwire: **a norm surfacing mid-build routes to capture
before code proceeds.** Capture = statement + why + scope + status, an Enforcement-table row
(mechanism assigned and existing-or-filed; audit home per the rule below), and — when existing
code predates the norm — a **retroactivity decision** with exactly three honest outcomes,
recorded on the norm's Retroactivity line:

1. **Migrate** — existing violations become sized backlog work, **and the norm is born
   `Status: in-transition` with the migration item as its tracking ref** — that is what makes a
   stalled migration observable. *Completed at birth:* when the sweep finds every violation
   inside the birthing changeset and fixes it there, the norm is born `steady-state` with no
   tracking item — record the outcome as `migrate` with the inventory and "no residual sites,"
   never as Grandfather. The distinction is load-bearing: Grandfather means *never intending to
   converge*, so using it here would exempt sites that are already compliant and invite the next
   editor to add more.
2. **Contain** — old and new regimes coexist behind an explicit, modeled boundary (adapters at
   the seams). Two regimes without a modeled boundary are an unmodeled-state defect.
3. **Grandfather** — existing sites are exempt, with the exemption inventory recorded at the
   Retroactivity line's ref. Grandfather differs from Contain only in never intending to
   converge: **where exempt and compliant sites interact, the same modeled-boundary requirement
   applies** — a value flowing between regimes doesn't care which word you chose.

An owner's "from now on" phrasing scopes the *statement*, not the retroactivity decision — the
three-way choice (and its recorded ref) is still required, because the seams between old and
new code are exactly where the unstated mixture breeds. The forbidden outcome is that mixture:
new code complies, old code doesn't, and every seam is a bug factory nobody decided to build.

**Audit-home rule:** a norm whose violations carry no machine-readable hook is **janitor-homed**
(only the deep sweep can see it); advisory-homed norms must name the mechanical hook the probe
fires on.

### Boundaries and collisions — rulings

Work at a norm's edge — a scenario the norm's author never contemplated, or two norms whose
demands conflict — resolves by **ruling**, never by silent interpretation in either direction.
Silently exempting erodes the norm; mechanically applying it blocks legitimate work and teaches
builders to resent the registry. A ruling is a recorded decision (per the standard above),
derived from the norms' *whys*, recorded as a learnings entry linked from the norm's Rulings
list. Rule at the **category** level ("externally-ingested runtime content is exempt, provided
it is never persisted into the asset store"), not the instance, so the next case at the same
edge is pre-decided. A collision ruling records precedence on **both** norms. **A collision
involving a whyless norm blocks on backfilling that why first** — the arbiter cannot run on one
input, and backfilling is cheap (the owner states it).

**Applicability is recorded, not assumed.** "This norm doesn't apply here" is itself an
interpretation. At planning, the `governed_by:` reconciliation records a one-line disposition
per governing norm — *conforms* | *ruling needed* | *exception* | *amendment proposed* |
*inapplicable because X* — so
the determination exists on paper where a reviewer can disagree with it, instead of in the
builder's head where no one can.

### Amendment

Changing a norm's normative content — its statement, scope, status, retroactivity, or the
effective force of its why — is an amendment, **whether or not any code accompanies it**, and
whether the change edits, adds, or removes sentences. It requires the recorded decision. The
amend-to-match-own-code tell (Authority Rule) is the aggravated form; the doc-only form is the
same decision split from its code. Updating a norm's *descriptive surroundings* (examples,
current-state notes) is ordinary documentation upkeep.

### Exceptions expire

An exception is a scoped, deliberate non-application of a live norm. **The clock always lives
on a backlog item**: every *temporary* exception files one carrying
`revisit: <YYYY-MM-DD or event trigger>`, linked from the norm. A code-site waiver pragma
(`prawduct:allow <scope>/<rule-id> -- reason`, `docs/waivers.md`) marks the site — its rule-id
names the waived *check*, not the norm — and is the right rail alone only for **permanent**
boundary-legitimate waivers; a pragma whose reason says "temporary" without a revisit-bearing
backlog item is an unrecorded exception.

Expiries fire on two paths, honestly distinguished: **dated** `revisit:` values fire
mechanically (advisory probe); **event-bound** triggers are walked by the janitor's Norm Health
sweep, which asks of each open trigger "has this fired?". An expired or fired exception is a
decision point — renew with a fresh reason, or schedule the removal. The default flips from
"persists silently" to "expires visibly."

An incident hotfix may violate a norm deliberately and correctly — speed wins during incidents,
and building.md's emergency path already says artifacts can follow. What follows **must include
the exception item**: a deliberate bypass whose follow-up records no rail is an unrecorded
exception (BLOCKING per the Authority Rule), caught when the hotfix or its follow-up is
reviewed.

### Transitions — interim rules

A norm `in-transition` ("we are converging on Y") is a different object from a steady-state
norm: between old and new, *something* must say what new work does. The interim rule says it
("new work targets Y even where incomplete"), and the tracking ref makes the transition's
health observable. **A stalled transition is a forcing event, not a license to improvise**:
when the declared substrate cannot serve new work, the choices are (a) accelerate the tracked
migration or (b) record a **stopgap** — a bounded exception per the standard above, its expiry
tied to the tracking item — never (c) build a third system silently. Stall detection is
mechanical: the tracking item's backlog entry unedited (no status, stage, or content change)
for the 30-day stall window raises an advisory (a fixed window today; a config surface is
deferred until any probe needs one).

### Trajectory — erosion and decay

Diff-scoped review sees instantaneous compliance; two failure modes are visible only over
time, and they are owned by the **time-domain organs**, not the Critic:

- **Erosion** — each individual exception is defensible; cumulatively the norm is dead, and
  match-the-surrounding-code pressure makes every new violation look more idiomatic than the
  last. The janitor's Norm Health theme measures global distance-from-norm — point-in-time
  distance suffices on a first run; measurements are recorded in committed project state so
  later runs see the **trend**.
- **Decay** — the norm outlives its why (the planned migration shipped; the scale assumption
  broke), while compliance continues and compounds cost. A why citing a backlog id whose item
  is shipped/archived is mechanically detectable (advisory); prose whys are the janitor's
  judgment.

Either finding forces the same explicit fork: **re-affirm and schedule cleanup, or retire the
norm** — and the chosen arm is itself recorded (re-affirm ⇒ a cleanup backlog item; retire ⇒ an
amendment), so an erosion finding cannot evaporate by nobody deciding. Norms are standing
decisions subject to challenge (Principle 19 extended to products) — enforced, not worshipped.

### Ambient norms — structural characteristics

The most load-bearing norms are never written as sentences, because they were universal at
birth: single-user, single-tenant, one-region, trusted-input. Their written home is
`project-state.yaml`'s classification. **Flipping a structural characteristic is a norm
amendment** ("add sign-in and per-profile config" is not a feature — it flips
`has_multiple_party_types`), and it triggers, in order:

1. **Record the flip** as a recorded decision — writing the classification field if it was
   never captured (the flip is often the field's first recording).
2. **Re-derive the structurally-triggered artifact set** under the new characteristics
   (security model, data model, observability, test spec — the same machinery discovery uses
   at inception).
3. **Run an assumption audit** — a deliberate sweep for code assuming the old value (unkeyed
   caches, global config, unauthenticated surfaces). Audit findings are **requirements**
   (Principle 2 applies: implement or explicitly descope — an "explicitly descoped until after
   launch" isolation gap is an owner's call made visibly, not a default).

The flip changeset's review verifies all three happened — a recorded flip whose re-derivation
or audit is missing is an incomplete decision (Goal 2's silently-dropped-requirement rule, at
its usual severity). The diff of such a feature touches none of the dangerous places; only the
audit sees them.

## Enforcement — who checks what, when

| Moment | Organ | What it catches |
|---|---|---|
| Prompt time | work-model tripwires | a norm-shaped requirement entering undocumented |
| Planning | `governed_by:` reconciliation, seeded by `prawduct-hook jurisdiction` | jurisdiction + the per-norm disposition lines (incl. *inapplicable because X*); departures surfaced as decisions before code |
| Review (event-domain) | Critic Goals 3/4 + Learnings Cross-Check; PR reviewer | departure without a recorded decision (Critic: BLOCKING, all forms, where ratified norms exist; NOTE in a norm-less product — see Severity above; PR reviewer: WARNING at its layer); the amend tell incl. doc-only; flip follow-ups present; norm-staleness signals (→ NOTE recommending `/prawduct:doctor`). The Critic considers jurisdiction independently — `governed_by:` is an input, not a boundary. |
| Session sync (time-domain, cheap) | advisory probes | the mechanical hooks, canonically: **dated `revisit:` expiries; backlog-id literals in Status/Why lines whose items are shipped/archived (dead why); in-transition tracking items unedited past the window (stall); structural presence** (strategy artifacts with no Direction *entry* anywhere — a bare heading is not one — or missing Enforcement columns → unratified; Norm Health sweep overdue while norms exist under *either* homing) |
| Periodic (time-domain, deep) | janitor Norm Health theme | erosion distance + trend, decay in prose whys, event-bound triggers walked, registry hygiene — the re-affirm-or-retire fork |
| Repair | `/prawduct:doctor` | ratification flow (below) + registry integrity: whys present, mechanisms exist, in-transition entries carry tracking ids, classification currency |

Probes fire **only** on the mechanical hooks named in the Session-sync row — dates, id
literals, structural presence — never on prose interpretation. Rare and high-signal is a hard
bar. Anything subtler belongs to the janitor's judgment or the Critic's.

**Structural-coverage staging — staged nudges, not a pile-on.** The structural-presence hooks form a
three-layer chain that stages a product from "we don't yet know what this is" to "its norms are
ratified," so a fresh product never gets three simultaneous nags. The layers key off one shared
boundary — whether `classification.structural` records at least one characteristic
(`lib/coverage_probes.structural_characteristics_recorded`) — plus layer 2's *independent*
artifact-existence gate. The 0↔1 boundary is mutually exclusive **and possibly neither** — each layer
adds a second condition beyond the boundary predicate, so a repo can sit outside both; 1→2 is
sequential but not mutually exclusive (see below):

| Layer | Fires when | Nudge |
|---|---|---|
| 0 — discovery not captured | product work exists but **no** structural characteristic is recorded | run discovery / reconcile — record what this product *is* |
| 1 — strategy-artifact-missing | characteristics **recorded**, but an expected strategy-class artifact is absent | author the artifact (a `(not relevant — …)` stub counts) |
| 2 — norm-registry-unratified | a strategy-class artifact **exists**, but the norm registry is unratified | ratify the direction, or record there is none |

Layer 0 speaks only on the negation of the boundary predicate; layer 1 only on its truth — so 0
and 1 never double-fire. Each adds a second condition of its own (the table above: layer 0 also
needs product work, layer 1 a missing artifact), so both are silent on a freshly-onboarded empty
repo — that is the chain not yet engaged, not the chain satisfied, and `coverage-status` renders
the two differently. Layer 1 stays silent until characteristics are
recorded *even for the universal artifacts* — "every product needs a data model" means every
product that has told the framework it is one. Layer 2 keeps its OWN artifact-existence gate: it
fires once *any* strategy-class artifact exists and the registry is unratified — you can ratify the
direction of what you have already written — so it does **not** wait for layer 1 to clear. During
*partial* authoring (some strategy artifacts written, others still owed) layer 1 (author the rest)
and layer 2 (ratify what exists) therefore both speak — two distinct asks, not a double-nag on one.
So the guarantee is proportionality (a fresh product never gets three simultaneous nags), not a hard
one-at-a-time invariant. The common trajectory still reads as staged: an all-`(not relevant)` stub
set creates every file in one act (layer 1 clears), then layer 2 nudges ratification. The chain
advances as each layer's condition clears.

**Honest limitations.** Work landed entirely outside governed sessions (an out-of-band hotfix
pushed directly) meets no event-domain organ; the probes and the janitor sweep are the
backstop, and they see only what left a hook or a global footprint. And the event-domain catch
is per-review: a departure that leaves no artifact (an unrecorded "inapplicable" call that
never touches a hook) survives a missed review until a human, a later reviewer, or the sweep
trips over its consequences. The lifecycle narrows these windows; it does not pretend to close
them.

## Scenario Index

The nine failure modes this spec was tested against, and which rule catches each:

| Scenario | Caught by |
|---|---|
| Divergence documented into the strategy artifact by its own changeset ("laundering") | Authority Rule — the tell (incl. split/doc-only form) + general BLOCKING |
| Work at a norm's uncontemplated edge, departure looks correct | Boundaries — ruling required; recorded disposition; correctness shapes the recommendation only |
| Two norms collide on one scenario | Boundaries — precedence ruling on both; whyless norm blocks on backfill |
| Norm adopted mid-life over existing violations | Birth — retroactivity decision with recorded ref; Migrate ⇒ in-transition |
| "Temporary" incident bypass persists | Exceptions — clock on a backlog item; follow-up review demands the rail; dated expiries fire |
| Declared migration stalls; new work improvises a third system | Transitions — interim rule; stall advisory (30-day default); stopgap = bounded exception |
| Norm eroded by many small defensible exceptions | Trajectory — janitor distance + recorded trend; sweep-overdue advisory; fork outcomes recorded |
| Norm outlives its rationale, compliance continues | Trajectory — decay; id-citing whys fire mechanically, prose whys by sweep |
| Unwritten ambient assumption invalidated (e.g. single→multi-user) | Ambient — flip is a recorded decision; review verifies re-derivation + audit; audit output = requirements |

## Adoption — existing products

A prawduct upgrade ships the enforcement engine instantly (protocols, probes, commands), but
the norm *registry* is product-owned. The distinction that keeps this coherent: **binding force
comes from the owner having declared a direction; ratification records it, never creates it.**
An upgraded product's existing normative statements — marked or not — already bind, because the
product's owner already declared them. What the framework must never do is *decide which*
unmarked statements are norms on the owner's behalf: that classification is what ratification
puts in the owner's hands.

- **Day one, automatically:** reviewers apply the normative/descriptive test to unmarked prose
  (conservatively — ambiguity resolves by ruling or marking, not silently), and the amend tell
  needs no markers at all. A one-shot `norm-registry-unratified` advisory fires when
  strategy-class artifacts exist with no Direction **entry** — a heading with nothing normative
  under it does not clear it, since the `Why:` is what separates a norm from a roadmap bullet
  (§ Anatomy) — or the Enforcement table lacks norm columns, pointing at the fix.
- **On demand, owner-ratified:** the `/prawduct:doctor` ratification flow reads the product's
  strategy artifacts, preferences, and learnings; proposes candidate norms (statement + why +
  status, citing backlog ids in whys where the rationale rests on tracked work); **triages**
  them — decision-worthy candidates (aspirational, practice-not-written, wording fork, collision,
  whyless) surfaced individually with their fork, the obvious rest bulk-confirmed in one line,
  never a flat wall that buries the few real decisions and invites rubber-stamping — and writes
  ratified norms into Direction sections and Enforcement rows, additively and non-destructively.
  "No norms to ratify" is a valid outcome (proportionality) and clears the advisory; the answer
  is shared-state, so one teammate's ratification clears it for everyone.

**Worked example.** A product's observability strategy declared, in narrative prose, that
OpenTelemetry was "the unified trace substrate" — while the collector export sat deferred in
the backlog. New async-tool work needed telemetry the substrate couldn't yet serve, built a
bespoke parallel trace system, and amended the strategy to call it "the preferred surface";
every review certified the amendment as documentation freshness. Ratification turns that
narrative into the Direction entry shown in *Anatomy* above: statement, why, `Status:
in-transition` with the export's tracking item, and the interim rule — so the same situation
becomes a forcing event ("accelerate the export, or record a stopgap with an expiry") instead
of a silent third system.

## Deliberate Non-Design

What this spec intentionally does **not** introduce, and why:

- **No norm IDs, registries-as-files, or schemas.** Norms are prose read by capable models;
  the Enforcement table indexes them. Structure would trade away the judgment this depends on.
  (Waiver pragmas' `<rule-id>` names a *check*, per `docs/waivers.md` — not a norm.)
- **No mechanical divergence gates.** Every scenario above defeats a checker built for the
  previous one; all of them yield to the same questions asked by a capable reviewer with the
  right context. Mechanical hooks are confined to the canonical Session-sync list.
- **No prose-parsing probes.** The orphan-term hook's noise history is the cautionary tale: a
  probe that misfires trains its reader to ignore the one real catch.
- **No auto-ratification.** Visibility is automatic; ratification is the owner's — binding
  force is the owner's declaration, recorded or not.
