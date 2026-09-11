# Issue #183 — operator-verification.md is a write-only queue: Design

`status: draft · stage: design · area: governance · added: 2026-08-18 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/183`

Builds on `documentation/issues/183-requirements.md` (D1–D3, OV1–OV6). That document settled what
question `operator_verification_required` actually poses, formalized the split-the-deferral rule,
and produced a per-entry disposition table for the six entries pending as of 2026-08-06. It
deliberately left the exact wording/placement of OV1's comment fix and OV2/OV3's template addition
to design (its own Scope-out section, and the 197-requirements.md precedent it cites for the
split). This document resolves that wording, and additionally validates D3's disposition table
against the queue's current state before reusing it (Principle 15 — Validate Before Propagating).

## Queue drift since the requirements doc — validated, not assumed

D3's table was built against a 2026-08-06 count (14 entries, 6 pending: VRF-002, 003, 005, 007,
008, 013). Re-read at the source for this design pass (2026-08-18), the live queue has moved:

- **VRF-008 is no longer pending.** Its own `**Status:**` line now reads `superseded`, with a
  `**Superseded:** 2026-08-07 by ... VRF-015` note already in the file explaining why draining it
  as written would report a failure against correct behavior (the backlog read-through cache
  restored the readers VRF-008 verified as dormant). It needs no groom note from this item — it
  already carries its own disposition, self-authored at the point the fact changed.
- **VRF-015 was added 2026-08-07** (`backlog-cache` Chunk 06), one day after the requirements doc,
  explicitly "supersedes VRF-008." It is currently `pending` and was never covered by D3.

Net: the queue still has **six pending entries**, but the set is VRF-002, 003, 005, 007, 013,
**015** (008 → 015), not the set D3 enumerated. OV4 said to record a disposition for "the six
entries pending as of this item's filing" — treated literally that phrase would mean VRF-008, but
recording a disposition for an entry the file itself already correctly marks non-pending would
misdescribe the queue. This design applies OV4's intent (every currently-pending entry gets a
recorded disposition, nothing sits unexamined) to the current six, and gives VRF-015 the same D1
reclassification treatment D3 gave VRF-013, reasoned below.

### VRF-015's disposition (new — not in D3)

Its seven verify steps (findings appear instead of an "unavailable" NOTE, a finding's id resolves,
the janitor's Backlog Health block lists real groupings, no permission prompt on a cache query, an
unreadable-store fallback names the right remediation, no stale dormancy advisory, the human-mode
`cache:` freshness line) are each a stated PASS/FAIL comparison against a live cut-over sibling
repo — no owner judgment call, the same shape VRF-013 was reclassified under D1. **Disposition:
stays pending, reclassified as live/networked-session-only, not person-only** — any `gh`-
authenticated agent session pointed at a cut-over sibling repo via `--plugin-dir` can run all
seven steps and report the printed/observed values. No static half to extract: every step depends
on the actual restored-reader behavior at runtime, which is exactly what VRF-008's stale steps got
wrong by assuming the dormant contract instead of re-observing it.

## Summary of what ships

1. **OV1** — `.prawduct/project-state.yaml:600-604`'s comment gets replaced wording (below), same
   line count, no behavior change.
2. **OV2, OV3** — `plugin/templates/operator-verification.md` gains two additions: the
   split-the-deferral paragraph in the top guidance block (after the existing "Drain entries
   via…" sentence), and a `**Why a human/live check:**` line added to the "Suggested format" entry
   stub, carrying the person-vs-session prompt inline where a new entry is actually drafted.
3. **D2's building.md cross-reference** — `plugin/methodology/building.md:106`'s F10 line gains a
   four-word pointer to the template's rule, not a restatement.
4. **OV4** — six dated groom-note blockquotes, one per currently-pending entry (VRF-002, 003, 005,
   007, 013, 015), inserted between each entry's `**Status:**` and `**Added:**` lines — the same
   position VRF-002's own 2026-07-27 note already occupies, so the convention has one shape, not
   two.
5. **OV5/OV6** — no code or flag change. `operator_verification_required` stays `false`; this item
   ships no flip and no flip precondition-check tooling (OV5 already recorded the precondition in
   prose; nothing here reads it mechanically).

## Decisions resolved

### OV1 — exact comment wording

Current (`project-state.yaml:597-604`):

```yaml
# =============================================================================
# OPERATOR VERIFICATION (opt-in, v1.4+)
# =============================================================================
# When true, `/pr create` BLOCKS if `.prawduct/operator-verification.md`
# has any entry with `**Status:** pending`. The framework itself ships
# this gate disabled — Prawduct has no human-facing UI surface to
# verify pre-merge; product repos that ship visual changes opt in by
# setting `operator_verification_required: true`.

operator_verification_required: false
```

Replacement:

```yaml
# =============================================================================
# OPERATOR VERIFICATION (opt-in, v1.4+)
# =============================================================================
# When true, `/pr create` BLOCKS if `.prawduct/operator-verification.md`
# has any entry with `**Status:** pending`. The real criterion is whether
# this product's next PR needs a live/networked verification pass before
# merge — a hook actually firing, a CLI round-tripping against a real
# external service, a reviewer's prose behaving correctly end to end — not
# whether the product has a human-facing UI. Most such checks only need a
# live session (an agent can drive them, given the right environment and
# auth); a minority need a person (owner judgment, eyeballing that content
# reads right). The framework itself ships this gate disabled — draining
# Prawduct's own queue would need a drain plan first (issue #183); product
# repos with live-integration surface opt in by setting
# `operator_verification_required: true`.

operator_verification_required: false
```

This is a documentation-only change (D1/OV1 constraint) — the flag, its default, and
`is_operator_verification_required`'s read path are untouched. The new wording states the
criterion the queue's 15/15 entries have always actually tested — none of them is a visual check
— and keeps the framework's own reason for staying opted out (an undrained queue, tracked by this
issue) rather than the retired "no UI" framing, which was true but answered a different question.

### OV2/OV3 — template addition, exact text and placement

`plugin/templates/operator-verification.md`'s top guidance block currently ends:

```
     override for the current PR with `/pr create
     --accept-pending-verification "rationale"` (the rationale is recorded
     into each entry as an `**Accepted:**` line — this file is the work-log).

     This file is append-only history. Entries stay forever after they're
```

New paragraph inserted between those two (i.e. after the `--accept-pending-verification`
sentence, before "This file is append-only history"):

```
     When filing a new entry, split the "why a human/live check" reasoning
     into two questions: "can this be true in principle" (a claim decidable
     by reading code today — resolve it now, statically, before filing) and
     "does the harness actually do it" (only observable by running
     something — defer this half). Only the second half may be entered as
     `pending`. Bundling a statically-decidable claim into the same entry
     as a genuinely-live one lets a wrong claim sit unverified for as long
     as the live half stays undrained (issue #183 / VRF-002's 2026-07-27
     groom note is the case that established this).

     Also state whether draining the entry needs a **person** (owner
     judgment — a scope tradeoff, eyeballing that content reads right) or
     only a **live/networked session** (an agent can drive it, given the
     right environment and auth — a mechanical PASS/FAIL check against a
     real system). This is a second, independent axis from static-vs-live,
     and it determines who can drain the entry.
```

The "Suggested format" stub (currently lines 22–34) gains the `Why a human/live check` field it
was missing — every real entry in the live queue carries one, but the stub never did, so a new
entry authored strictly from the stub would omit the field OV2/OV3 now require:

```
<!-- New entries go below this line. Suggested format:

## VRF-001 — Chunk N — Short title

**Status:** pending
**Added:** YYYY-MM-DD (Chunk N, F-id)
**Where to verify:** <screen, CLI invocation, dashboard URL, etc.>

**Why a human/live check:** <the live-only half, per the split above — and
whether it needs a person or just a live/networked session>

**Verify:**
- <observable behavior 1>
- <observable behavior 2>

-->
```

OV3 is satisfied by prose guidance and the stub field, not a schema change — matching the
requirements doc's explicit scope-out of a `VerificationEntry`/`_STATUS_LINE_RE` parser change.

### Building.md cross-reference (D2)

Current (`plugin/methodology/building.md:106`):

```
**Operator verification (F10).** Visual / live-integration chunks: enqueue in `.prawduct/operator-verification.md` and mark `Visual change: yes`. `/prawduct:pr create` blocks on pending entries when `operator_verification_required: true`.
```

Replacement (one clause added, nothing removed):

```
**Operator verification (F10).** Visual / live-integration chunks: enqueue in `.prawduct/operator-verification.md` (split static from live per the template's filing guidance) and mark `Visual change: yes`. `/prawduct:pr create` blocks on pending entries when `operator_verification_required: true`.
```

This is the pointer, not a restatement — building.md is where a builder decides *whether* to
enqueue at all (D2), so it needs to know the rule exists and where, not carry a second copy of it.

### OV4 — the six groom notes

Each note is a blockquote in VRF-002's established `=== <date> — <TITLE> ===` convention,
inserted directly after the entry's `**Status:**` line. Text below is what design specifies;
applying it to the live file is a build action, not this document (Scope-out).

**VRF-002** (after line 48, before the existing 2026-07-27 note — this groom note is *about* the
disposition-recording pass, not a new technical finding, so it is dated separately and stacked
above the existing one, oldest-first per the file's history convention):

```
> === 2026-08-18 — DISPOSITION RECORDED (issue #183, D3) ===
>
> Stays pending — genuinely live-only, correctly scoped. The static half (fact 2,
> matcher-can-match) is already resolved and pinned by
> `tests/test_critic_reviewer_agent.py::TestSubagentStopMatcherMatchesRuntimeAgentType`.
> Remaining: delivery (does the hook actually fire) and attribution (which trigger
> consolidated) — both need a real session with the fixed matcher, an isolated
> `CLAUDE_CONFIG_DIR`, and consolidation-attribution recorded on the `review.critic`
> event. No action taken here; recorded so this entry is not silently unexamined.
```

**VRF-003** (after line 134):

```
> === 2026-08-18 — DISPOSITION RECORDED (issue #183, D3) ===
>
> Stays pending. Half already discharged (CLI `coverage-status` before/after,
> recorded in-entry). The untested half is specifically the rendered
> SessionStart *briefing text* a person reads — only a fresh `clear`-hook session
> start exercises it. No static residual to extract.
```

**VRF-005** (after line 208):

```
> === 2026-08-18 — DISPOSITION RECORDED (issue #183, D3) ===
>
> Stays pending, correctly scoped as pure-live — all three facts (label-remove URL
> encoding, `state_reason` clearing on reopen, additive `add_labels`) are
> real-GitHub-behavior facts with no static half to split out. Checked against every
> live run since filing (VRF-006, 009, 010, 011, 012): none exercised a `status --to
> in-progress` transition or a reopen, so none discharges this by coincidence.
```

**VRF-007** (after line 363):

```
> === 2026-08-18 — DISPOSITION RECORDED (issue #183, D3) ===
>
> Stays pending. Open question flagged, not assumed: VRF-014 Item 1 (2026-08-02)
> attests a general sibling-repo exercise covering drift-burndown and Health Check
> #13 by name, but its record does not enumerate this entry's backlog-skill repoint.
> Not read as covering it by inference (Principle 5) — ask the owner or re-run.
```

**VRF-013** (after line 709):

```
> === 2026-08-18 — DISPOSITION RECORDED (issue #183, D1/D3) ===
>
> Stays pending, reclassified under D1: this needs a live/networked *session*, not a
> *person* — three read-only Python snippets against the real repo, each with a
> stated PASS/FAIL criterion and no judgment call. Any `gh`-authenticated agent
> session can run it. Flagged as a same-day-drainable candidate for the next such
> session (not this design pass — Scope-out).
```

**VRF-015** (after its `**Status:** pending` line):

```
> === 2026-08-18 — DISPOSITION RECORDED (issue #183 design pass — supersedes D3's
> VRF-008 row) ===
>
> New since the requirements doc (added 2026-08-07, one day after D3 was written);
> D3 never covered it. Reclassified under D1 the same way VRF-013 was: all seven
> verify steps are stated PASS/FAIL comparisons against a live cut-over sibling
> repo with no owner judgment call, so this needs a live/networked *session*, not a
> *person*. No static half — every step depends on the restored-reader behavior at
> runtime, which is exactly what VRF-008's stale steps got wrong by assuming
> instead of re-observing.
```

## Files touched

| File | Change |
|---|---|
| `.prawduct/project-state.yaml` | `operator_verification_required` comment replaced (OV1) — no key, default, or read-path change |
| `plugin/templates/operator-verification.md` | Split-the-deferral paragraph in the guidance block (OV2); `Why a human/live check` field added to the suggested-format stub (OV3) |
| `plugin/methodology/building.md` | F10 line gains a four-word cross-reference to the template's filing rule (D2) |
| `.prawduct/operator-verification.md` | Six dated groom-note blockquotes recording dispositions for the currently-pending entries (OV4, updated for the VRF-008→VRF-015 drift found in this pass) |

No code file changes and no test plan — every OV item here is comment/prose/markdown, matching
requirements' OV1 constraint ("documentation correction, not a behavior change") and OV2/OV3's
"prose, not a schema change" scope-out.

## Open items for the build chunk (not resolved here)

- Applying the six OV4 blockquotes and the OV1/OV2/OV3/D2 text edits to the live files — this
  design pass specifies exact text and insertion points; a build chunk (or a follow-up docs-only
  pass, consistent with how this item itself has been handled) applies them.
- Whether VRF-007/VRF-008's open coverage question (does VRF-014 Item 1's attested exercise cover
  the backlog-skill repoint) gets resolved — explicitly left open by D3 and unchanged here; it
  needs the owner or a live re-run, not a documentation decision.
- OV5's flip precondition (zero pending, or every remaining entry classified live-session-only
  with a routine owner) is not yet met — five of six current entries (all but 013/015's
  reclassification) still need genuinely live work, so no flip is proposed by this or any future
  docs-only pass until that changes.

## Acceptance (carried from requirements, now with exact wording)

- [ ] Each of the six *currently*-pending entries (VRF-002, 003, 005, 007, 013, 015 — not the
      2026-08-06 set, per the validated drift above) has a recorded disposition.
- [ ] The split-the-deferral rule and the person-vs-session distinction are both written into the
      template's filing guidance, in the location a new entry is actually authored from.
- [ ] `operator_verification_required`'s comment states the queue's real criterion.
- [ ] No flip is attempted (OV5 precondition still unmet).

## Evidence / references

- `documentation/issues/183-requirements.md` — D1–D3, OV1–OV6, the Scope-out section this design
  resolves.
- `.prawduct/operator-verification.md` — re-read at the source 2026-08-18: 15 entries now (VRF-001
  through VRF-015), 6 pending (002, 003, 005, 007, 013, 015); VRF-008 `**Status:** superseded`,
  `**Superseded:** 2026-08-07 by ... VRF-015`.
- `.prawduct/project-state.yaml:597-606` — the comment OV1 replaces.
- `plugin/templates/operator-verification.md:1-34` — the template OV2/OV3 extend.
- `plugin/methodology/building.md:106` — the F10 line D2's cross-reference extends.
- `documentation/issues/197-design.md` — the sibling design doc whose format (Summary of what
  ships → Decisions resolved → Files touched → Open items → Acceptance → Evidence) this document
  follows.
