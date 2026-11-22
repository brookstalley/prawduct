# Issue #1207 — evidence: disposition facts never travel to other clones: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-11-19 · source: builder,
found while building #606 on 2026-11-18 · issue:
https://github.com/brookstalley/prawduct/issues/1207`

Related: #606 (the ledger holds reviews, never outcomes; it documented this asymmetry and left the
choice alone), #1052 (evidence transport on `refs/notes/prawduct`), #1063 (a product can opt out of
the transport), #1058 (stats double-count ingested reviews), #1060 (a blocking finding a spanning
review cleared has no record).

## Problem

A finding ends in one of two kinds of fact. A `resolution` (a verify pass judged it fixed or
waived) travels to other clones with the review it answers. A `disposition` (ACCEPT, FILE, or a
free fix recorded with `--fixed`) does not: `evidence.TRANSPORTED_KINDS` leaves it out, and the
comment beside it says a builder's disposition is "about the clone that wrote it".

That reason does not match what a disposition is. It is keyed on `(review_id, fid)`, and the
review it answers does travel. So a second clone receives the finding and never the answer. Read
from the code on develop `e0e0051d`, four readers in that clone then get it wrong:

| Reader | What it shows in the clone that did not write the disposition |
|---|---|
| `render-dispositions`, and the census in a PR payload or change entry | The finding as `undispositioned`, with the text that every finding needs an answer. |
| The session briefing (`briefing.py`, "N undispositioned warning") | A debt count for findings someone already answered. |
| `dispositions.prior_dispositions`, the block a reviewer reads before the diff | Nothing. The reviewer has no memory of the ACCEPT and can raise the finding again, which is the re-litigation the block was built to stop. |
| `stats` and `review-stats` acted-on rates | The finding as unanswered, so the rate reads lower than it is. |

No gate is wrong because of this. `coverage_algebra` reads `review` and `resolution` facts only, and
`plan_status._blocking_clear` passes a blocking finding only on a resolution. The cost is wrong
debt, a repeated decision, and a reviewer round spent on a finding already answered.

Who meets it: two people on one product, one person on two machines, and a CI job or cloud
session that clones fresh and renders a census.

## Recommendation

Dispositions travel, all three actions, on the same footing as resolutions. Each alternative
below was weighed and is not recommended.

| Option | Why not |
|---|---|
| Keep all dispositions local and label the census "this clone's count" | Fixes the wording and none of the four readers. The reviewer in the other clone still re-raises an accepted finding. |
| ACCEPT and FILE travel, `fixed` stays local | A free fix is a claim about the shared tree, not about the writer's machine. Leaving it behind keeps the finding `undispositioned` everywhere else, which is the state `--fixed` was added to end. |
| Mirror outcomes somewhere else (the ledger, a committed file) | #606 already ruled against a second home for one fact. |

The one case with a real argument for staying local is the budget sweep (`auto_accept`), taken up
in Q2.

## Goals

- G1. A finding's answer is the same in every clone that holds the finding and has synced.
- G2. A reviewer dispatched in one clone is told about answers given in another, under the limits
  `prior_dispositions` already applies.
- G3. Two clones that hold the same facts render the same census, whatever order the facts
  arrived in.
- G4. Nothing that travels can lift a gate. The transport widens what is displayed, never what
  passes.
- G5. What the transport now publishes to the remote is stated where the owner ruled on the rest
  of it, before the first disposition is sent.

## Non-goals

- Making any gate read dispositions. A blocking finding still clears only on a resolution.
- Transporting `guard-refusal`, `test-run` or `session-start`. Each is about the machine or
  session that wrote it; R8 records that reason in place of the current sentence.
- Signing or verifying inbound facts. The security model's ruling stands: the product's own
  remote is trusted for facts at the level it is trusted for code.
- A freshness indicator on the census ("last synced"). Resolutions have the same staleness
  between syncs and nothing reports it; if that is wanted it is its own item, for both kinds.
- Changing the `disposition` CLI or what `record` accepts.

## Requirements

**Transport**

- R1. `disposition` joins `TRANSPORTED_KINDS`. A disposition is attached to the notes ref when it
  is recorded, sent by `evidence sync`, and taken in by `evidence ingest` and session start, by
  the same code paths the other transported kinds use. No second transport.
- R2. A disposition's note hangs on the anchor of the review it answers (`evidence.review_anchor`),
  as a resolution's does. A bounded ingest that reads a review therefore reads its answers. A
  disposition whose review this clone's store does not hold has no anchor and stays local, with
  the skip reported the way `attach` reports any other.
- R3. Observations are covered the same way as findings. An answered `O-` id travels with the
  review that carries the observation.
- R4. `reconcile` repairs a disposition whose attach failed or never ran, as it does for the other
  kinds. What it does with dispositions recorded before this change is Q1.
- R5. The outbound line passes through `sent_envelope` like every other. The body travels whole:
  `action`, `reason`, `backlog_id`, `owner_ruling`, `paths`.

**Convergence**

- R6. "Newest answer wins" is decided by something every clone computes the same way. Today it is
  store order (`disposition_index`), which is append order in one clone and arrival order in
  another, so two clones holding the same facts can disagree. Design picks the ordering key (the
  envelope `ts` with the fact id as tie-break is the obvious candidate); the requirement is the
  property, and a test that ingests the same facts in two orders and compares the census.
- R7. Two clones answering the same finding independently lose neither answer. Today both mint
  `disp:<review>:<fid>:1`, and `(kind, id)` dedupe keeps whichever each clone saw first, so the
  clones diverge and never converge. After the change both answers are in both stores, the census
  shows the winner under R6, and `disposition_history` shows both. Design picks how (a
  writer-distinct id, or dedupe that compares bodies); existing ids stay readable.

**Safety and honesty**

- R8. The comment at `TRANSPORTED_KINDS` records the decision and, for each kind still local, the
  reason it is local. The sentence calling a disposition "about the clone that wrote it" is
  removed, not amended beside.
- R9. An ingested disposition changes no gate verdict. The existing regression test that pins
  "a disposition can never weaken a gate" gains a case where the disposition arrived by ingest,
  including an ACCEPT that carries an `owner_ruling` on a blocking finding.
- R10. A `fixed` disposition is checked against the judgeable-path predicate in the clone that
  records it and is not re-checked at ingest. Its census state stays `fixed-unreviewed` in every
  clone, so no clone reads another's free fix as a reviewed one.
- R11. The security model's outbound entry for `evidence sync` names dispositions and what they
  add to the published content: free-text accept reasons, owner-ruling text, backlog ids and the
  path lists of free fixes. The inbound entry needs no new decision. It gets one sentence saying
  an ingested disposition reaches the census, the briefing and the reviewer's prior-dispositions
  block, and no gate.
- R12. A clone with the transport switched off (#1063, when it lands) or with no notes ref behaves
  as today: dispositions are recorded and read locally and nothing errors.
- R13. A plugin from before this change, reading a note that carries dispositions, skips them
  (`ingest` takes only its own `TRANSPORTED_KINDS`) and keeps working. No schema bump. Stated
  here so design verifies it and does not assume it.

**Every description agrees** (core.md: a mechanism change is done when every artifact describing
it agrees)

- R14. These say dispositions stay local today and each is rewritten, with the superseded sentence
  deleted: the `ledger.py` module docstring paragraph "Reviews, not their outcomes"; the test that
  pins it, `tests/test_ledger_holds_no_outcomes.py::test_its_transport_claim_matches_the_transported_kinds`;
  the `evidence_notes.py` module docstring's anchor paragraph; `plugin/docs/governance-telemetry.md`
  ("dispositions stay in their clone"); `plugin/skills/critic/review-cycle.md` ("Review and resolution facts reach other
  clones"); `.prawduct/artifacts/security-model.md` (R11). Design finds the rest by searching
  for the claim in other words ("stays in that clone", "per clone", "local to"), not for the
  token `TRANSPORTED_KINDS`.
- R15. `stats` and `review-stats` count an ingested disposition once. #1058 is the known
  double-count on ingested reviews; this change must not add a second one, and its test says so.

## Acceptance

- A1. Two-clone test: an ACCEPT, a FILE and a `--fixed` recorded in clone A reach clone B's census
  after `evidence sync` in A and ingest in B, each with the state A shows. Seen to fail before the
  change (core.md: a check never seen to return non-zero proves nothing).
- A2. Clone B's `prior_dispositions` for a dispatch over the cited file and scope lists A's ACCEPT.
- A3. Order test for R6: the same fact set ingested in two orders gives one census.
- A4. Conflict test for R7: A and B each answer one finding differently, both sync, both end
  with the same winner and a two-entry history.
- A5. Gate test for R9.
- A6. The pinned docstring test is updated with the sentence it pins, and
  `tests/test_evidence_notes.py::test_every_kind_outside_the_transported_set_is_skipped` still has
  a non-empty local set.
- A7. A falsifying search for the old claim over `plugin/`, `tests/`, `documentation/` and
  `.prawduct/artifacts/` returns only historical records (changelog, archived plans).

## Risks

- **Published text written as private.** Accept reasons and owner rulings recorded so far were
  written into a store that never left the machine. Sending them makes them readable by anyone
  who can fetch the product's remote. This repo's store held 652 dispositions at one measurement.
  Q1 decides whether old ones are sent.
- **Note growth.** Dispositions outnumber resolutions. Each adds a line to an existing note, and
  the bounded ingest reads only the branch's own commits, so session-start cost should move
  little. Design measures it on this repo's store before and after.
- **A wrong answer now spreads.** A mistaken ACCEPT used to mislead one clone. It will now hide a
  finding from reviewers everywhere until someone re-dispositions it. The remedy is the existing
  one (record a new answer; R6 makes it win everywhere). No new mechanism is proposed.

## Open questions for the owner

- Q1. **Backfill.** When this ships, `reconcile` would by default attach every not-yet-sent
  disposition for reviews on the current branch at the next sync. Three choices: send them (the
  census is right at once, and old free text is published); send only dispositions recorded
  after the change (nothing written as private leaves, and open branches stay wrong until
  re-answered); send old ones only on an explicit command. Recommended: the first, because the
  text is the same kind the transport already publishes in findings and waiver rationales, and
  it goes only to the remote the branch already goes to. This is the decision R11 needs your
  word on.
- Q2. **Budget sweeps.** `auto_accept` answers every open non-blocking finding with "round budget
  exhausted" when a dispatch is refused. The budget is counted per worktree, so another clone
  would see findings accepted for a reason that is not true of it. Recommended: they travel like
  any ACCEPT, since the reason says whose budget it was and the finding was in fact left
  unfixed; hiding them rebuilds the divergence this item removes. The alternative is to mark
  sweep facts and keep them local.
- Q3. **Stage.** With Q1 and Q2 answered this is small enough to go straight to `ready`: the
  design choices left (R6's ordering key, R7's id shape) fit in the build plan. Say if you want
  a design document first.
