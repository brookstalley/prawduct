---
artifact: collapse-map
version: 2
scope: learnings-firing
status: APPLIED 2026-08-01 — approved, amended in shape, and executed
last_validated: 2026-08-01
---

# Collapse Map — `learnings-firing` Chunk 03(b)

**Applied 2026-08-01.** The owner approved this map, then amended its *shape* the same day
(below) before `audit-learnings --apply` ran. Seventeen members retired by supersession;
the corpus went **159 → 149**.

Rosters are derived, never transcribed: `python3 tests/spikes/learning_families.py`.

## The test applied to every member

**Not** *"is this covered by the general rule?"* — everything is, and that is exactly what
makes collapse feel like progress while it removes the discriminating power a reader needs.

**The test is:** *does this member contribute an instance the general statement cannot
generate?* If yes → it retires, **and its instance moves into the successor's heading**.
Only a member whose instance is genuinely redundant retires leaving nothing behind.

Relocating an instance to `learnings-detail.md` does **not** count as keeping it: that file
is read on demand when debugging a known area, not at the moment a rule has to fire.

## Shape amendment — owner decision, 2026-08-01

Version 1 of this map collapsed each family into **one** destination heading and justified it
as *"within house style — the corpus already runs 188 median / 396 p90 / 907 max characters."*

**That premise was false, and the measurement is what falsified it.** Drafted for real, the two
destinations came in at **1,484 and 1,798 characters** — 1.7× and 2.0× the largest heading in the
corpus, not within it. They also collided head-on with `record_lint`'s `learnings-entry-shape`
check (`_LEARNINGS_RULE_MAX = 400`, shipped 2026-07-30 in `c8a24ed`), whose remedy text is *"move
the evidence to learnings-detail.md"* — the exact instruction the owner overruled on 2026-07-31.
Two ratified decisions one day apart, in direct contradiction, meeting here.

**Decision:** split each family **thematically** into destinations that fit under the 400-char
cap, grouped by the *kind* of failure rather than listed. No lint change; no rule dropped.

Two things this bought and one it cost, all measured:

- **It costs almost nothing in tokens.** One-heading-per-family would have been −21% across the
  touched set; the split is −18%. Character count is dominated by the *instances*, which both
  shapes preserve by construction. The shape choice buys **rule count**, not tokens.
- **It uplevels further than the mega-heading did.** Naming three kinds of green-but-empty test
  (*the fixture never reaches the subject* / *the assertion passes for a reason that is not the
  property* / *the fixture's world is narrower than the requirement*) is an abstraction layer
  that a single 1,798-character list does not have.
- **It costs rule count.** One-per-family would have been 19 → 6; the split is 19 → 10.

Token reduction was never this chunk's goal and the union rule forecloses it deliberately
(Success criterion 3: *"shrinks in rule count, not in discriminating detail"*). That work already
shipped separately as **LRN-4K8T** (2026-07-30, 121KB → 34KB) — which is where the 400 cap came
from.

---

## Family 1 — "a durable statement is a CLAIM" → 4 destinations

| Destination | Carries |
|---|---|
| **C1** `Anything in a durable artifact that one command could check is a CLAIM…` (amended in place, was `:292`) | the general statement + `:286` + `:324` |
| **C2** `A completeness claim asserts the falsifying COMMAND now returns nothing…` (new) | `:27` + `:298` |
| **C3** `Reads as evidence, is not: …` (new) | `:31` + `:21` + `:51` + `:217` |
| **C4** `Verify a review artifact's cited gaps against HEAD first…` (amended in place + widened, was `:91`) | `:91`, widened |
| **`:89`** *(untouched)* | **KEEP** — the trigger, not the definition |

| Retired | → | Instance that survived, and where |
|---|---|---|
| `:21` disposition vs diff | C3 | *a disposition recorded from intent, not the diff, which the next reader trusts INSTEAD of the findings* |
| `:27` completeness claim | C2 | all three: *never a count of sites fixed, true of any prefix of the real set*; *normalize the text before searching*; *query the CONCEPT, not the phrasings you already found wrong* |
| `:31` absence-claim path resolves | C3 | *a missing directory returns the same empty result as the claim being true* |
| `:51` commit closes a backlog item | C3 | *crediting a backlog item by TITLE while its filed reproduction still reproduces* |
| `:217` subagent count/list | C3 | *a subagent's COUNT or LIST, a lead* |
| `:286` rationale you reached for | C1 | *the rationale you REACHED FOR to defend a decision already made is the one to verify* |
| `:298` the falsifying query carries the defect | C2 | *the query is itself a mechanism and can carry the defect it hunts… line structure is not semantic structure* |
| `:324` a correction is a completeness claim | C1 | *a CORRECTION is itself a completeness claim: quoting the parent rule demonstrably does not prevent this* — kept verbatim, as required |

**`:91`'s widening, as approved.** It scoped to an *inherited* citation. Three anchors went stale
in one session from appends to files cited twenty minutes earlier — same file, same session, no
branch switch — and one stayed **arithmetically valid** while its content was rewritten, because
markdown held it as one long line. C4 drops "inherited" and adds *anchor on symbols and headings,
not digits — one that visibly breaks gets fixed; one still arithmetically valid under a rewrite
never does*.

## Family 2 — "green is evidence only about what could have made it red" → 5 destinations

| Destination | Carries |
|---|---|
| **D1** `Green is evidence ONLY about what could have made it red…` (**new — Chunk 03(a) rule 1**) | the general statement + `:15` + `:23` + discodon mechanism 1 |
| **D2** `A passing assertion may be satisfied by something other than the property…` (new) | `:123` + `:284` + `:302` |
| **D3** `A fixture's world is narrower than the requirement it certifies…` (new) | `:252` + `:256` + `:19` + `:141`(a) |
| **D4** `A test inherits inputs nobody declared and properties nothing observes…` (new) | discodon mechanisms 2, 4, 5, 6 |
| **D5** `A self-authored adversarial pass inherits the author's blind spots…` (new) | `:141`(b) |
| **`:318`**, **`:320`** *(untouched)* | **KEEP** — per v1: the only rule saying how to check a guard is not a spelling, and instructions-as-deliverable |

| Retired | → | Instance that survived, and where |
|---|---|---|
| `:15` pinning the constant | D1 | *a constant-equality assertion survives an inverted comparison while its NAME convinces the reader it is covered* |
| `:19` gate across state transitions | D3 | *one moment stands in for the procedure's transitions* |
| `:23` probe with no describable failure | D1 | *say what a FAILING run would have looked like before recording one* — the reclassification from family 1, as approved |
| `:123` arg guard rejected the flag | D2 | *an unimplemented flag passes because the arg guard REJECTED it (assert success BEFORE absence)* |
| `:141` fan-out collision | D3 + D5 | split, both kept: *the collision case is unwritten when the fan-out key is not unique* (D3) and the whole of D5 |
| `:252` the common instance narrows the requirement | D3 | *the COMMON instance narrows the requirement to itself, so check coverage against its stated BREADTH* |
| `:256` framework's own state vs propagated contract | D3 | *the framework's OWN state stands in for the propagated contract, so assert what reaches consumer repos* |
| `:284` substring of prose | D2 | both: *a prose SUBSTRING stays green under any longer sentence containing it*; *grep tests asserting FRAGMENTS, not just failing ones* |
| `:302` gate on THAT event | D2 | *a proxy passes every test you thought to write — gate on the named event* |

**The forwarding pointer for `:141` names D3**, its primary instance. D5 exists because of its
second, and is cross-referenced from D1's narrative — a supersession record carries one target,
which is a real limit of the mechanism and worth knowing before splitting a member again.

## What else `--apply` swept, deliberately recorded

`--apply` is a whole-corpus operation and cannot be scoped to this map. It additionally retired
**one unrelated entry** whose `sentinel=` route was already `ready`: *"A plugin skill with
unparseable YAML frontmatter loads with ALL metadata silently dropped"*
(`tests/test_plugin_manifest.py::TestAllPluginSkillFrontmatter` passes, so the failure mode is
structurally enforced). That is the mechanism working as designed, not a scope leak — but it is
recorded here rather than left to be discovered in the diff.

**One entry stayed, correctly.** *"Framework ownership follows the write strategy, not just
registry membership"* is blocked on a sentinel naming
`tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip`
— **a file that no longer exists**, since the file-sync engine was retired in v2.0.3. The audit
fails closed and retains the entry, which is the right posture. Filed for repair; not fixed here
(out of this chunk's scope).

## Verification

- `python3 tests/spikes/learning_families.py` — family 'assertion' 11 → 4 candidates,
  'discriminating' 10 → 4. Both destinations now exist, so `FAMILY_GENERALS` names both and the
  `None` case in that script is retired with them.
- All **17** forwarding pointers in `learnings-detail.md` resolve against the active corpus
  (0 unresolvable).
- No lifecycle metadata drifted into the detail file —
  `test_no_lifecycle_metadata_has_drifted_to_the_detail_file` and its four siblings pass.
- Every heading written by this chunk is ≤ 400 chars; the 15 headings still over the cap are
  pre-existing and grandfathered (the check reads added lines only).

## Sequencing constraint — still live

`LRN-9K2P` is open at `stage: ready` to reword ~28 `learnings.md` headings. A `superseded-by=`
forwarding pointer is written as *literal resolved heading text* and nothing ever re-resolves it.
**This collapse has now run, so the rewording is the "after" side** — and it must re-check every
`superseded by **X**` in `learnings-detail.md` against `learnings.md` before it lands. There are
now 17 more such pointers than when that item was filed.
