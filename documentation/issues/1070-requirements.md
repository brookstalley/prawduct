# Issue #1070 — reflection: routing lines replace the episode narrative: Requirements

`status: draft · stage: requirements · area: learnings · added: 2026-10-26 · source: owner
conversation 2026-10-25 · issue: https://github.com/brookstalley/prawduct/issues/1070`

Related: #908 (spike: does the reflection gate earn its cost; this item is a redesign alternative to
its keep / narrow / retire outcomes), #1071 (the gate's work span counts another session's commits;
fixed separately, a precondition for trusting any reflection-gate measurement).

## Problem

The episode in `.prawduct/.session-reflected` has one reader, the next session's generated handoff
(`plugin/lib/briefing.py`, "Session reflection" block), and is then unlinked; nothing archives it.
`gates.reflection_shape` grades it by keyword (`expected`, `actual`, and `root cause` / `no defect`),
so the gate checks that prose exists, not that anything happened as a result. The valuable part of a
reflection is its *outcome* (a rule written, an issue filed, an existing rule that did or did not
fire), and that outcome is neither checkable nor consumed. core.md names this class: "A channel that
is produced and never consumed is a DEFECT."

## Goals

- G1. A reflection's outcome is recorded as machine-checkable lines, each verifiable against a
  queryable fact (a file, an issue, a test or review id).
- G2. Every produced line has a named consumer in the same change (core.md rule on producers).
- G3. The mechanisable lesson is surfaced: a rule that repeatedly *existed but did not fire* is
  proposed as a test or lint candidate (core.md: a rule you must recall is its weakest form).
- G4. The thinking that reflection exists to cause is not lost (see Q2; this goal is the one most at
  risk and is the go/no-go criterion).

## Non-goals

- Grading the "because…" root-cause clause (authoring.md: mechanise only a queryable claim).
- Rebuilding a reflection archive or a scheduled consolidation pass (decided away in learnings-v2).
- The concurrent-session span bug (#1071) and the keep/retire decision for the gate itself (#908).

## Requirements

**Format**

- R1. One routing line per *outcome*, several allowed. Vocabulary: `rule: <file> "<opening words>"`,
  `filed: #N`, `covered: <rule>`, `covered, missed: <rule>`, `caught: <test or review id>`,
  `no defect`. An optional `— because …` clause may follow any line.
- R2. `reflection_shape` accepts a file iff it holds at least one well-formed line. The narrative
  keywords (`expected`, `actual`) stop being required. Free prose around the lines is permitted and
  ignored by the gate.
- R3. Parsing is tolerant of encoding variants (case, dash, quotes) and hard-fails only on an
  ambiguous line (hook-surface rule on model-output seams).

**Checks** (each by the line's own queryable fact; none grades the reasoning)

- R4. `rule:` passes iff the quoted opening words appear in a line of the named learnings file.
- R5. `filed:` passes iff the issue exists in the resolved tracker AND is open and not
  dropped/closed-as-not-planned. Measured counter-example: the 2026-10-25 handoff cited #282 as
  "already filed", but #282 is closed (dropped); an existence check would pass a dead reference.
- R6. `covered:` and `covered, missed:` pass iff the rule exists.
- R7. `caught:` passes iff the named test exists or the review id is in the evidence store. A
  mechanism the reflector cannot name does not qualify ("noticed by luck" is not `caught`).
- R8. `no defect` is unchecked, as today. It is the one line with no cited fact and so stays the
  easy exit; Q1 asks whether to bound it.
- R9. The checks run offline except `filed:`; if the tracker is unreachable, `filed:` degrades to a
  format check with a named warning rather than blocking (probes and gates must not make network
  egress a stop condition).

**Reader**

- R10. At the session boundary (`/clear` or fresh start, where `.session-reflected` is removed
  today), each verified line is appended to the governance ledger as an event beside
  `learning.fired`, before the file is unlinked. New kinds are machine-emitted only
  (`ledger._MACHINE_ONLY_PREFIX` posture) and carry role `builder`.
- R11. `covered, missed` events are counted per rule. A rule reaching a threshold (initial: 2 in a
  rolling 60 days, tunable) is listed as a mechanisation candidate in the next briefing or a
  telemetry report, naming the rule and its events. This is the named consumer for G2/G3.
- R12. The generated handoff renders the routing lines in place of the narrative episode, so the
  forward-relevant content (filed ids, rules written) reaches the next session at lower cost.

**Cascade** (surfaces to update in the same change; verify by grep for the *claim*, not the tokens)

- R13. `plugin/methodology/reflection.md` Step 4 ("An episode") and Step 1 to 3 wording;
  `session-digest.md` (hard 10,000-character wall, currently 9,623 bytes: any growth needs an
  offsetting cut); `gates.reflection_shape`; the Stop-hook blocker text; `briefing.py` handoff
  rendering and its session-start "reflection not captured" advisory (they share the predicate);
  the ledger schema and role map; token-budget and digest tests.
- R14. Product repos: `rule:` and `covered:` resolve against the product's own
  `.claude/rules/learnings/`; `filed:` resolves against the tracker the product's friction routing
  uses (framework friction goes upstream via `/prawduct:report-bug`), so the line must be able to
  carry a repo qualifier (`filed: owner/repo#N`).

## Open questions (discovery; each needs an answer before design)

1. **Easy-exit drift.** `no defect`, `caught:` and `covered:` can become the new rubber stamp.
   Measure: sample the historical `reflections.md` (1,203 entries, gitignored, no reader) and
   classify how many would route to each line type; if more than a majority would be `no defect`,
   consider requiring one cited artifact (commit or file) for it. Derivation to be committed as a
   script, not transcribed digits (authoring rule on unfalsifiable spikes).
2. **Does dropping the narrative lose the thinking?** Untested, medium confidence per the issue.
   Proposed test: a bounded A/B over a few sessions, comparing root-cause quality and rule yield
   between narrative and routing-line sessions. This is the go/no-go evidence.
3. **Stable rule reference.** Rules are one line, capped and often merged
   (`learnings_compact.py`). Candidate: reuse the unit hash that `learning.written` /
   `learning.fired` already key on (`learnings_files.py`, with `learning.compacted` carrying
   `from_hash` to `unit_hash`), keeping the opening-words form as the human-facing spelling.
4. **Interaction with #908.** If #908 retires the gate, R2 to R9 are moot but R10 to R12 (a reader
   for outcomes) still stand. Sequence #908 first, or fold this into its decision.
5. **Ledger measurement bias.** All 123 October `learning.fired` events are role `critic`, so the
   ledger measures review citation, not builder behaviour; `covered` / `covered, missed` is the
   first builder-side signal and is self-reported. Decide how much weight R11 may carry.

## Acceptance (for this stage)

- [ ] Requirements reviewed by the owner; Q1 to Q5 each answered or explicitly deferred with an owner.
- [ ] Go / no-go recorded on the issue, with the Q2 evidence.
- [ ] On go: `documentation/issues/1070-design.md` written and the issue advanced to `stage:design`.

## Grounding

Read at `plugin/lib/gates.py` (`reflection_shape`), `plugin/lib/briefing.py` (handoff and
session-start advisory), `plugin/lib/ledger.py` (`_EVENT_ROLES`), `plugin/methodology/reflection.md`
Step 4, and the issue body. Counts quoted from the issue (measured 2026-10-25) were not re-derived
here; re-derive them in discovery. No prior art for routing lines on any unmerged branch (only
`origin/claude/*` and `origin/main` exist).
