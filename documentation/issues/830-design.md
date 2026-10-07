# Issue #830 — Governance: Severity Should Select the Channel, Not Just the Label: Design

`status: draft · stage: design · area: governance · added: 2026-10-07 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/830 · requirements:
documentation/issues/830-requirements.md`

Resolves the requirements' CHN1–CHN9. Where the requirements left a question to design, it is
answered here; where an answer needs the owner, it is a numbered **Decision** at the end.

## What changed since the requirements

Re-reading the code for this design found one thing that reshapes the answer to CHN2 (the
norm-collision question).

**The ratified norm is silent on disposition.** `nonfunctional-requirements.md:115-116` says the
boundary stage "runs the full severity table" and that everything below the inner BLOCKING set is
"an observation at the inner stage and **a finding at the boundary**." Both clauses are about
*classification and assessment*: what the reviewer rates, and which array it lands in. Nothing in
the norm says a boundary NOTE must be individually dispositioned. That obligation lives elsewhere:

- `plugin/skills/critic/review-cycle.md:291-294` — prose ("Severity does not exempt").
- `next_action_line` (`critic_consolidate.py:795-908`) — tells the builder to decide warnings and
  notes "in that SAME pass."
- `dispositions._summarize` / `STATE_OPEN` (`dispositions.py:105-110, 819-843`) — counts an
  unanswered finding as `undispositioned`, a debt.

So the requirements' reading (a)/(b) dichotomy is a false one. There is a third reading, and it
needs neither a norm amendment nor a change to the boundary `observations` refusal
(`critic_consolidate.py:5227-5238`):

> At the boundary a NOTE **stays a finding**. It stays in the `findings` array, in the severity
> counts, in the fact body and in the ledger, exactly as today. What changes is that it stops being
> **owed** — the census reports it as `noted` rather than `undispositioned`, and the next-action
> text stops telling the builder to decide it.

This is the same split the inner stage already makes between a finding and an observation, applied
along the *obligation* axis instead of the *classification* axis. It is the smaller change and it
leaves the severity-laundering defence intact: a `cumulative` reviewer still cannot move a warning
somewhere that reads as 0/0/0, because nothing moves. Only an item the reviewer itself rated NOTE
changes how it is *reported to the builder*.

## Scope and target size (CHN3, CHN9)

- Boundary stage only (`cumulative`, PR review). Inner stage, WARNING delivery, remedy text and
  severity assignment are out, per the requirements' scope-out.
- **Target size is the boundary NOTE remainder, not the pooled 53%.** #832's closing comment gave
  992 of 1,141 post-2026-08-04 round-buying notes at `cumulative` (87%).
- **Re-measurement is not done in this document.** The session that wrote it had no
  `.governance-ledger.jsonl` (`prawduct-hook review-stats` reports "no review history"), so the
  992/1,141 figure is carried forward from #832's comment, not re-derived. CHN9's re-run is
  therefore the **first task of the build**, before chunk 1 merges, with this command and a
  recorded output in the build plan:
  `prawduct-hook review-stats --since 2026-08-04` split by stage (boundary vs inner) and by severity.
  Kill criterion: if boundary NOTEs are under ~25% of dispositions owed post-2026-08-04, close the
  item as not worth its code — the inner-stage demotion already took the volume.

## Design

### D1 — A third disposition state for a boundary NOTE: `noted`, reused

`dispositions.STATE_NOTED` already exists for unanswered observations and already means "work the
record explicitly does not demand" (`dispositions.py:105-111`). Reuse it; add no new state.

- A finding whose `severity == "note"` **and** whose review's stage is `boundary` is a *noted
  finding*: with no disposition it resolves to `STATE_NOTED`, not `STATE_OPEN`.
- A NOTE that *has* a disposition (FIX / ACCEPT / FILE) keeps that state. The builder may still
  answer one; it is simply not owed.
- `_summarize` already keeps `undispositioned` and `noted` apart, so the census's debt number drops
  by exactly the boundary NOTE count and no consumer of it needs a change. (Verify by the
  falsifying query in Test 3 — a count of sites edited is not that proof.)
- `record()` needs **no** change: it already accepts a disposition against any finding id and has
  no WARNING/NOTE refusal (`dispositions.py:349-554`; BLOCKING-only refusals at `:482-505`).

The stage is read from the review fact's recorded stage via `stage_of_manifest`'s recorded field
(`critic_consolidate.py:5236`), not re-derived from the mode name, so a manifest written before the
field existed still resolves.

**Why this is not "file it by another name" (Acceptance, CHN5).** A noted finding mints no backlog
item, no id the builder owes and no per-note obligation. It is the observations pattern's
*obligation* semantics on the findings array. The failure `review-cycle.md:268-276` records (open
items 50 → 180 in 26 days) came from FILE being the only outlet for a finding; nothing here adds a
route into the backlog, so it cannot reproduce that.

### D2 — Next-action text stops asking for NOTE decisions at the boundary

`next_action_line` decides the builder's instruction from `(blocking, warning, note, observations)`.
At the boundary, count a NOTE into a new `noted` argument, not `note`:

- 0 blocking, 0 warning, N notes → "the review is over; N note(s) gate nothing and are not owed a
  disposition" (the observations arm's wording at `:914-927` is the template).
- Warnings present → unchanged; notes are listed after, as "not owed."

The existing "decide the WARNING/NOTE findings in that SAME pass" sentence keeps its meaning for
WARNING. `review-cycle.md:291-294` is amended in the same change: "Severity does not exempt
BLOCKING or WARNING; a boundary NOTE is `noted`, not owed," and the "moves the pump" sentence is
rewritten to say *why it doesn't here* (nothing is filed). Per the learnings rule on mechanism
changes, the sweep covers every artifact **describing** the obligation — grep the phrases
`every finding takes an ACCEPT, FIX or FILE regardless of severity` (`dispositions.py:915-919`),
`Severity does not exempt`, and `all take a disposition` across `plugin/`, `tests/`, `documentation/`
and `.prawduct/`, and delete the superseded sentences rather than adding beside them.

### D3 — "Read at release" is a live query, not a file (CHN6, CHN7)

- Add `prawduct-hook review-notes [--since DATE] [--stage boundary]`, a read-only query over the
  evidence store that lists noted findings grouped by `scope`/file and by recurrence (same
  normalised `name`+`goal` across reviews). It writes nothing and holds no state.
- It is named **notes ledger view**, never "digest," to avoid the collision with
  `plugin/hooks/digest.py`'s SessionStart session digest (CHN7). The CLI verb is `review-notes`.
- It is wired into **one** consumer in the same change: a line in
  `documentation/release-process.md` Step 0, next to `check-releasability`, reading "run
  `review-notes --since <last release>`; skim recurrences." A producer with no named consumer is a
  defect (core learnings), so if the owner declines the release-step line (Decision 3) the command
  is not built.
- Recurrence is the signal worth surfacing: a NOTE that appears in three reviews is the evidence
  that a rule or norm is missing. That is how the notes channel earns its keep without anyone
  dispositioning individual notes.
- No persisted artifact, so nothing repeats the retired `.prawduct/release-notes.md` derived-view
  failure.

### D4 — Did a note ever matter? Descoped to a proxy, explicitly (CHN8)

A causal join ("this NOTE prevented that later BLOCKING") needs a per-finding pointer that does not
exist, and a definition of "prevented" that is a judgement call by someone. Building it first
means building an instrument whose key field is unreliable. **Decision: out of scope for this item.**
The stated proxy is *recurrence-then-escalation*, computable from the same store with no new field:
a normalised NOTE that later appears at WARNING or BLOCKING in a later review of the same files.
`review-notes --escalated` reports it. This is correlational and says so in its own output header;
it does not answer the literal question. #951 (`found_by`, escapes) is the item that builds
attribution infrastructure; if it ships, the causal join can reuse its attribution field and should
be filed then, not now. File that follow-up as a backlog item when this design is accepted (per
the learnings rule: file the moment you decide).

### D5 — Norm record

No amendment is needed, but the interpretation is now load-bearing, so land a one-line
clarification under the norm's `Status: steady-state` entry in `nonfunctional-requirements.md`:
"Stage keys classification and assessment. It does not key disposition: a boundary NOTE is a
finding that is `noted`, not owed." Carry it with a `[DECISION: …]` stub citing owner confirmation
(Decision 1). Per the learnings rule that a governance change cannot supply its own authority, the
build agent must not write the ratification itself; it lands the owner's confirmation in the issue
thread, outside the change.

## Build plan sketch (not a plan file)

1. **Re-measure** (CHN9) and record in the plan; stop if the kill criterion trips.
2. `dispositions.py`: stage-aware `noted` resolution for boundary NOTEs (D1) + tests.
3. `critic_consolidate.next_action_line` + the `review-cycle.md` / `dispositions` rendering text, and
   the sweep of every describing artifact (D2).
4. `review-notes` query + release-process line (D3).
5. Norm clarification (D5) after owner confirmation.

Chunks 2–3 are one reviewable unit (behaviour plus the text that describes it); 4 stands alone.

## Tests (each must be red-verified before trust)

1. **Boundary NOTE is `noted`:** a `cumulative` fact with one undispositioned NOTE → census row
   `state == "noted"`, `summary.undispositioned == 0`, `summary.noted == 1`.
2. **Inner and WARNING unchanged:** an undispositioned WARNING at `cumulative` stays
   `undispositioned`; a NOTE in an inner-stage fact's `findings` (legacy facts) stays
   `undispositioned`. This is the CHN4 regression pin.
3. **Falsifying query for the sweep:** a test that greps `plugin/` and `documentation/` for the
   superseded obligation sentences and fails if any remains. Seed it red by reverting one site.
4. **Laundering still refused:** the existing boundary-observations refusal test passes untouched
   (this design touches neither the refusal nor `_validate_observations`).
5. **A disposed boundary NOTE keeps its state:** `--accept` on a NOTE → `accepted`, not `noted`.
6. **`review-notes` is read-only:** run it over a fixture store; assert the store bytes are
   unchanged, and that recurrence grouping merges two reviews' NOTEs with the same normalised name.
7. **Old facts:** a fact written before the stage field existed resolves via the derive-from-mode
   path in `stage_of_manifest`.

## Risks

- **Wrong stage read.** If the stage resolves wrong for a mode, a WARNING-bearing inner review could
  lose an obligation. Mitigation: D1 keys on `severity == "note"` **and** boundary; test 2 pins it.
- **Notes stop being read at all.** The pre-change forcing function was the disposition obligation;
  with it gone the only reader is the release-step query. Mitigation is D3's recurrence view and the
  kill criterion — if `review-notes` output is never acted on for two releases, remove the command
  (ratchet norm: a control that never fires is removed).
- **Reviewer downgrades WARNING to NOTE to dodge the obligation.** The failure that sank #832.
  Here the incentive points the right way for the builder, but a reviewer-side drift would show as
  a falling WARNING share at `cumulative`; `review-stats` already reports B/W/N, so add the
  boundary W:N ratio to the pre/post comparison in step 1 and watch it after.

## Decisions for the owner

1. **Confirm the third reading (D5).** Stage keys classification, not disposition; a boundary NOTE
   stays a finding and becomes `noted`. *Recommendation: yes — it avoids a norm amendment and
   leaves the laundering refusal intact.* If no, the fallback is the requirements' reading (b), a
   formal amendment plus a changed refusal, which is materially larger and should be re-estimated.
2. **Kill criterion (~25%).** Acceptable threshold for stopping after re-measurement?
3. **Release-step consumer.** Approve adding the `review-notes` line to
   `documentation/release-process.md` Step 0? If not, drop D3.
4. **Causal join stays out (D4).** Confirm descoping, with a follow-up filed against #951's
   attribution field.

Stage after answers: `ready`. Effort stays M.
