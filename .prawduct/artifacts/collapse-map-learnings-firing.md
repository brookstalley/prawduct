---
artifact: collapse-map
version: 1
scope: learnings-firing
status: AWAITING OWNER APPROVAL — no retirement has been applied
last_validated: 2026-07-31
---

# Collapse Map — `learnings-firing` Chunk 03(b)

**Nothing here has been applied.** `audit-learnings --apply` has not run against the
corpus and will not until this map is approved (the plan's hard stop).

Rosters are derived, never transcribed: `python3 tests/spikes/learning_families.py`.
Re-run it rather than trusting any count below — one already changed while this map was
being written (family 2 was reported as 9 until the script stopped excluding line 320
from its own roster).

## The test applied to every member

**Not** *"is this covered by the general rule?"* — everything is, and that is exactly what
makes collapse feel like progress while it removes the discriminating power a reader needs.

**The test is:** *does this member contribute an instance the general statement cannot
generate?* If yes → it retires, **and its instance moves into the successor's heading**.
Only a member whose instance is genuinely redundant retires leaving nothing behind.

Relocating an instance to `learnings-detail.md` does **not** count as keeping it: that file
is read on demand when debugging a known area, not at the moment a rule has to fire.

---

## Family 1 — "a durable statement is a CLAIM"

**Destination:** line 292 — *Anything in a durable artifact that one command could check is a
CLAIM — including an identifier, a count, or a facet value, not just a rationale.*

| Rule | Call | Instance that survives into 292 |
|---|---|---|
| `:21` disposition vs diff | **merge** | a disposition record is what the next reader trusts *instead of* re-reading the findings. Also now code-delivered (`RESOLUTION_IS_A_CLAIM_DIRECTIVE`) — the stored copy is the redundant one |
| `:23` probe with no describable failure | **reclassify → family 2** | not this family. Its own text says *"same discipline as a discriminating regression test, applied to live measurement"*. The keyword net misfiled it |
| `:27` completeness claim | **merge** | three, all kept: a count of sites is true of any prefix of the real set; run the query whitespace-normalized; query the **concept**, not the phrasings you already found wrong |
| `:31` absence-claim path resolves | **merge** | a missing directory produces the same evidence as the claim being true |
| `:51` commit closes a backlog item | **merge** | a fix aimed at the item's *title* lands the adjacent sub-case and passes every guard |
| `:89` "X now covers Y" | **KEEP** | this is the **trigger**, not the definition. 292 says what a claim is; `:89` says how to notice you are making one — *treat the SENTENCE as the trigger, not your confidence in it*. The delivery half, and the half that actually fires |
| `:91` inherited `file:line` | **merge** | *a `file:line` you did not personally resolve is a claim, not a citation — its precision reads as evidence of having been read*. **Widen it on merge** (see below) |
| `:217` subagent count/list | **merge** | a subagent's reported count or list is a lead, not ground truth |
| `:286` rationale you reached for | **merge** | the *reach* is the tell — this is about **which** claim to check, which 292 cannot generate |
| `:298` the falsifying query carries the defect | **merge** | normalize the text before searching; line structure is not semantic structure |
| `:324` a correction is a completeness claim | **merge** | *quoting the parent rule demonstrably does not prevent this* — keep that clause verbatim; it is evidence the rule does not self-enforce |

**12 rules → 2.** One merge carries a required amendment:

> **`:91` must widen.** It currently scopes to an *inherited* citation. Three anchors went
> stale in one session today from appends to files cited twenty minutes earlier — same file,
> same session, no branch switch. And one stayed **arithmetically valid** while its content
> was rewritten underneath, because markdown held it as one long line. An anchor that visibly
> breaks gets fixed; one that silently stays valid never does. The merged text should say
> *anchor on symbols and section headings, not digits* and drop "inherited".

---

## Family 2 — "green is evidence only about what could have made it red"

**Destination: a NEW rule, added by Chunk 03(a).** It does not exist yet, which is why the
script excludes nothing from this roster.

| Rule | Call | Instance that survives into the new rule |
|---|---|---|
| `:15` pinning the constant | **merge** | a constant-equality assertion survives an inverted comparison while its *name* convinces the next reader the path is covered |
| `:19` gate across state transitions | **merge** | a fixture encoding a single moment misses the step where the procedure changes the data the gate reads |
| `:123` arg guard rejected the flag | **merge** | assert success **before** asserting absence |
| `:141` fan-out collision | **merge** | two: test the collision case when the key is not unique; a self-authored adversarial pass inherits the author's blind spots |
| `:252` the common instance narrows the requirement | **merge** | check coverage against the requirement's stated **breadth**, not the available example |
| `:256` framework's own state vs propagated contract | **merge** | assert the contract that reaches consumer repos |
| `:284` substring of prose | **merge** | a longer sentence containing the fragment keeps the test green — and when prose changes meaning, grep the tests asserting *fragments*, not just the ones that fail |
| `:302` gate on THAT event | **merge** | a proxy signal passes every test you think to write, *because you wrote them believing the proxy* |
| `:318` assert the PROPERTY, not one spelling | **KEEP** | distinct and actionable, with its own verification step — *verify it red against a DIFFERENT phrasing than the one that prompted it*. Merging it would delete the only rule in the corpus that says how to check a guard is not a spelling. **Violated twice in this session's own work** |
| `:320` model the READER | **KEEP** | different subject: instructions as a *deliverable*, not test discipline. Its instance (size/budget/right-words guards all pass while the instruction is inert) does not follow from the general statement |
| `:23` (reclassified in) | **merge** | a measurement with no describable failing observation measured nothing — the rule applied to live measurement rather than to a test |

**11 rules → 3** (the new rule, plus `:318` and `:320`).

---

## What the owner is being asked to approve

1. **Two KEEPs in family 1** — only `:89`. Everything else merges.
2. **Two KEEPs in family 2** — `:318` and `:320`.
3. **The `:91` widening**, which changes a rule's meaning rather than merely relocating it.
4. **The `:23` reclassification** across families.
5. That every other member's instance moves **into** its successor's heading, making those
   two headings substantially longer. The corpus already runs 188 median / 396 p90 / 907 max
   characters, so this is within house style — but it is the deliberate trade: fewer rules,
   each carrying more.

**Not yet done, and not to be done without this approval:** writing the two new rules,
running `audit-learnings --apply`, and the part (c) read-instruction.

## Sequencing constraint — read before applying

`LRN-9K2P` is open at `stage: ready` to reword ~28 `learnings.md` headings. A `superseded-by=`
forwarding pointer is written as *literal resolved heading text* and nothing ever re-resolves
it. Run this collapse **before** that rewording or **after** it — never interleaved, and never
the rewording after without re-checking every `superseded by **X**` in `learnings-detail.md`
against `learnings.md`.
