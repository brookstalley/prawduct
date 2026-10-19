# Issue #986 — Make a late requirement cheap to absorb: Requirements

`status: draft · stage: requirements · area: governance · added: 2026-10-11 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/986`

Related: #136 (an amended decision must acknowledge dependent artifacts — shares the impact-walk
substrate), #989 (governance tax measurement — the cost ceiling this must respect), #951
(escape attribution — the measurement this must feed). Evidence:
`.prawduct/artifacts/governance-roi-study-2026-10.md` (on `develop`) result 4 and "What it means"
point 4; `documentation/purpose.md` § "Why the gap never closes".

## Problem

The governance ROI study labelled the cause of 127 non-fix rework edges. A late requirement was
the largest single cause in every governance mode (none 45%, 1–2.x 32%, 3.x 46%). Governed repos
were no better: 0.84 late-requirement rework edges per kLOC at 3.x against 1.02 with no
governance, within noise. The classifier judged most late requirements unknowable in advance
("learned from operating it", "a new consumer arrived later"), so asking earlier does not pay.

Prawduct today has one answer to a requirement that surfaces mid-build: the tripwire in
`plugin/methodology/building.md` § "A Requirement Surfaced Mid-Build" says *stop, name it, write
or locate the parent requirement, then resume*. That is a **prompt to the author**, with three
gaps that match the issue's three asks:

| Gap | Today | Consequence |
|---|---|---|
| **Capture** | "Write or locate the parent requirement" names no home, id or required fields. | The requirement lives in chat or a commit message and is gone by the next session. |
| **Impact walk** | Nothing enumerates what a new requirement touches. | Absorption is a recall task; the sites missed come back as the next rework edge. |
| **Binding** | The Critic checks "requirement implemented or descoped" against whatever the plan lists. A requirement that never reached the plan is invisible to it. | Later plans, chunks and reviews do not check against it. |

The goal is not fewer late requirements. It is a lower cost per late requirement, measured as
fewer rework edges that rewrite the same area a second time.

## Scope

**In:** a defined capture act with a home and a minimal record; an impact walk from that record;
a binding of later plans, chunks and reviews to it; a way to attribute late-requirement rework
afterwards, so `escape.py` can compare with the 2026-10 baseline.

**Out:** expanding up-front discovery (the study gives no evidence it pays); general
prose-consistency checking; re-verifying already-amended decisions (#136's remediation scope); a
new tracker or database for requirements.

## Definitions

- **Late requirement:** a requirement that is not in the product's governing artifacts at the
  time the work that discovers it begins, and that changes what must be built or already built.
  A clarification of an existing requirement is not one.
- **Captured requirement:** a late requirement recorded in the product's record under this
  document's capture rules.
- **Absorbed:** every site in the impact set has an explicit disposition (changed, or checked and
  unaffected) and every later chunk that touches the area cites it.

## Requirements

### Capture (LR-C)

- **LR-C1 — One home.** A captured requirement is written into the governing requirements
  artifact the product already has (product brief, nonfunctional requirements, or the equivalent
  that `prawduct-hook jurisdiction` ranks first). It is not written to a new file type. A product
  with no such artifact gets one section in the active build plan, named `## Late requirements`,
  until a governing artifact exists.
- **LR-C2 — Minimal record.** Each captured requirement carries: a stable id (`LR-<n>`, unique
  per product); the requirement in one sentence; **why it is late** (what surfaced it, in the
  study's terms: learned from operating it, new consumer, owner change, discovered constraint);
  the date; and the work cycle or commit where it surfaced. Nothing else is mandatory. The "why
  late" field is the one the study could only get by asking a model after the fact.
- **LR-C3 — Trigger.** Capture fires on the existing tripwires in `building.md` and on two
  more that the study's "unknowable" reasons suggest: an owner statement in conversation that
  changes behavior ("it also has to…"), and a defect fix whose root cause is a missing
  requirement (the fix is a bugfix; the requirement is the finding). The trigger stays a
  methodology step. **Decision:** the surfacing itself is not mechanised, because it is a
  semantic judgment and a detector would be the false-positive generator #989 warns about.
- **LR-C4 — Capture precedes code.** The record is committed before the code that implements it
  or in the same commit; a commit message is not a capture. This is checkable after the fact
  (LR-M1), which is the only enforcement this document asks for.
- **LR-C5 — Cheap.** Capturing takes one edit to one file. A requirement that needs a design
  discussion is captured as stated and the design follows; capture never waits for design.

### Impact walk (LR-W)

- **LR-W1 — Output is a list with dispositions.** The walk produces an **impact set**: every
  artifact section, plan chunk and code area the requirement touches, each with a disposition of
  *change* or *checked, unaffected*, stated per site and never inferred. It is written next to
  the captured record (LR-C1's home) or in the plan, not in chat.
- **LR-W2 — Sources of candidates.** The walk draws candidates from, at least: the artifact
  manifest's `depends_on` edges from the artifact that received the requirement; plan chunks
  whose file refs or acceptance criteria name the affected area (`buildplan_refs`); open backlog
  items that cite the area; and a literal and vocabulary search of the repo for the requirement's
  nouns. No single source is trusted to be complete, and the doc says so.
- **LR-W3 — Shared substrate with #136.** The decision→artifact edge data, the graph
  completeness check and the acknowledgement record that #136 specifies are the same machinery.
  This issue must not build a second one. If #136's design is not ready, the walk ships as a
  methodology step with the sources above, and adopts #136's mechanism when it lands.
- **LR-W4 — Self-edited files are not exempt.** The artifact that received the requirement is in
  the impact set and is re-read in full (#136 class 3).
- **LR-W5 — Honest about its limit.** The walk finds sites that can be found by structure and
  vocabulary. It does not find a paraphrased restatement (#136 class 2). The record states that
  limit, and the binding step (LR-B) is the backstop.

### Binding (LR-B)

- **LR-B1 — Plans cite requirements.** A chunk whose area intersects a captured requirement
  lists the id in a plan field. The field follows the build-plan Title Case convention
  (`**Requirements:**`), and its parser is specified in the design before the name is used
  (learnings: naming a field writes a machine-read value).
- **LR-B2 — No orphan.** A captured requirement that is neither cited by a chunk of the active
  plan nor marked descoped (with a reason) is reported. Severity is advisory at session start and
  a Critic finding at the plan's boundary review. The Critic already treats a silently dropped
  requirement as BLOCKING; this makes "dropped" detectable for requirements that never reached
  the plan.
- **LR-B3 — Reviews see them.** The Critic's review manifest lists the captured requirements
  whose impact set intersects the diff, so the reviewer grades the diff against them without
  needing the plan to have carried them.
- **LR-B4 — Superseding is explicit.** A later change that contradicts a captured requirement
  amends the record (marker plus reason). It does not edit the requirement to match the code. The
  same rule already governs norms.

### Measurement (LR-M)

- **LR-M1 — Attribution.** `escape.py` can label a rework edge as late-requirement rework
  attributed to a captured requirement when the landing or the edge's later landing cites its id.
  Edges with no id remain in the baseline category. The comparison to report is the 2026-10
  baseline (3.x: 0.84 late-requirement edges per kLOC) against the same measure after this ships,
  plus the share of such edges that cite a captured id.
- **LR-M2 — Capture rate.** `prawduct-hook stats` (or the equivalent in #989's output) reports
  captured requirements per work cycle and the share with a complete impact set. A capture rate
  of zero over a long window is a finding about the trigger, not a success.
- **LR-M3 — Cost ceiling.** The mechanism must be near-free when no requirement is late: no new
  gate runs, no review round, no session-start output (#989). It earns its cost only on the
  work cycles that capture one.

## Mechanism decisions (the issue's second acceptance item)

| Part | Decision | Why |
|---|---|---|
| Surfacing a late requirement | **Not mechanised.** Methodology step on the existing tripwires. | A semantic judgment; a detector adds false positives and tax. |
| Capture record | **Mechanised lightly.** A fixed record shape and id, with a lint that ids are unique and fields present. | A persisted format is a lock-in decision; its consumers' queries are LR-M1, LR-B2 and LR-B3. |
| Impact walk | **Partly mechanised.** The candidate lists (manifest edges, chunk refs, backlog citations) are computed; the dispositions are written by the author. | Structure is computable, relevance is not. Shares #136's substrate. |
| Binding | **Mechanised.** Orphan detection and the Critic manifest line. | This is the part that decays: it is cheap to forget and cheap to check. |

## Acceptance (for this document)

- [x] Capture, impact walk and binding are defined (LR-C, LR-W, LR-B) with triggers.
- [x] Each has a named mechanism or an explicit decision not to mechanise (table above).
- [x] Attribution for comparison with the 2026-10 baseline is specified (LR-M1).

## Open for design

1. **Record shape and home.** Whether `LR-<n>` entries live as a table row in the governing
   artifact or as a small block that a parser reads, and how the id survives a squash merge.
   The consumers' queries are listed above; the shape follows them.
2. **Ledger vs artifact.** Whether the captured records should also be indexed somewhere
   queryable (the work-model index) so LR-B2 and LR-M1 do not parse prose.
3. **Walk ordering with #136.** Whether #136's design lands first, or this ships a thin walk
   and converges later.
4. **The trigger for "owner statement changes behavior".** Where in the conversation-to-code path
   a methodology step can fire without a hook; the study suggests the weak point is the unprompted
   fluent chat design, which is already the building.md tripwire's target.
5. **Baseline validity.** The 0.84 and 1.02 figures were labelled by a model from commit diffs.
   LR-M1 compares them with a measure that uses authored ids. The design should say how the two
   are made comparable, or report them as separate series.

## Risks

- **Governance tax.** Every added record is a cost; the study found no throughput penalty yet,
  but #989 exists because the owner feels one. LR-M3 is the guard, and the design must show the
  no-late-requirement path costs nothing.
- **Rubber-stamp dispositions.** "Checked, unaffected" can be written without checking. Mitigation
  is the same as #136's: the walk's candidate list is computed, so a skipped candidate is visible.
- **Captured but wrong.** A recorded requirement can be mis-stated and then bind later work to
  the mistake. LR-B4 keeps amendment explicit; the record carries its "why late" so a reader can
  judge it.
