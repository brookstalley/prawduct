# Issue #1098 — gates: the Critic Stop verdict judges history a sync brought in: Requirements

`status: draft · stage: requirements · area: gates · added: 2026-10-30 · source: reflection (boundary review R-9 of fix/1071-session-authored-span) · issue: https://github.com/brookstalley/prawduct/issues/1098`

Related: #1071 (the authored-span fix this follows from), #304, #654 (base-advance transfer), #895 (transfer denies a stacked branch after parent merge), #937 (base-advance diagnosis cost).

## Problem

Two Stop-gate questions are asked of different spans:

- **Firing** ("did this session change anything judgeable?") uses the session-authored span. `_session_authored_paths` drops paths that differ only because a pull, merge, branch switch or reset brought in history the session did not write (`plugin/lib/gates.py`, "What this session CHANGED").
- **Verdict** ("is the change reviewed?") is `session_review_verdict`, which composes review coverage over `.session-base-tree` → working tree via `coverage_algebra.coverage_verdict`. That interval contains the imported history. It is only relaxed when the primary span is not covered: then the merge-base span is asked, and a covered (or transferred) merge-base span stands in.

So a session that both authored code and synced is *fired* on its own work but *judged* on its own work plus whatever it imported. The imported part has no review in the store on this session's behalf (it was reviewed, if at all, on another branch or clone, against other trees), so the verdict reads `uncovered` and the session is told to run a review whose subject is not its own.

## Goals

- G1. For a session that authored code and then synced, the verdict's required coverage is the session's own change, not the imported history.
- G2. A session that authored nothing keeps today's behaviour (firing already returns no-fire; nothing to judge).
- G3. Never weaker than the PR gate on the final state: whatever the Stop verdict stops requiring must still be required, once, by the PR gate's merge-base span. The Stop gate may be narrower than the PR gate; it may not be the only gate that is narrower in a way that lets unreviewed *authored* code through.
- G4. The change is explainable in one sentence in the block message (what span was judged and why).

## Non-goals

- Changing the firing span (done in #1071).
- Changing the PR gate or base-advance transfer rules (#654, #895).
- Reviewing imported history. Its review obligation belongs to the branch that authored it.

## Requirements

- R1. Decide which span the session verdict composes over. Candidates:
  - **A. Status quo.** Base tree → working tree, merge-base fallback only when uncovered. Imported history can block.
  - **B. Authored span.** Restrict required coverage to the paths `_session_authored_paths` returns. Needs the coverage algebra to accept a path filter; today it composes by tree, so a filter must be applied to the *diff* (`diff_fn`) the verdict asks about, not to the stored facts.
  - **C. Merge-base span only.** Same bar as the PR gate. Simple, but a session that only wrote a one-line fix on a long-lived branch would be required to cover the whole branch. This is what the existing fallback already permits when it composes, so C changes only the case where it does not.
  Recommendation to confirm: **B**, because it is the only candidate matching the firing span (G1) and the Stop gate's job (session's own work). The PR gate remains the backstop for the rest (G3).
- R2. Under B, a path both authored and imported (the session edited a file a sync also changed) stays *required*. Authorship is per path; a mixed path is the session's.
- R3. Under B, if `_session_authored_paths` cannot establish authorship (it returns `None` when the reflog is unrecognised or unreadable), the verdict falls back to today's full base→working-tree span. Authorship uncertainty fails toward more review, never less.
- R4. The verdict dict reports which span was judged (`span: "authored" | "full"`) and, when authored, the count of imported paths excluded, so the block message and telemetry can say what was ignored.
- R5. The excluded imported paths are not silent: the message states "N paths imported by a sync were not judged here; the PR gate covers them".
- R6. A test per branch: (a) authored + imported, authored reviewed → covered; (b) authored + imported, authored unreviewed → uncovered naming only authored paths; (c) mixed path stays required; (d) authorship unreadable → full span; (e) no authored paths → not fired. Each is red-verified against the current code.

## Acceptance

- A session that merges `main` into its branch and edits two files, then runs a review whose scope is those two files, stops clean.
- The same session without the review is blocked, and the block names only the two files.
- `/prawduct:pr` on that branch still requires merge-base coverage unchanged.

## Open questions for the owner

- Q1. Confirm B over C. C is smaller (no algebra change) but over-requires on long-lived branches.
- Q2. Is an imported-history exemption at Stop acceptable at all given G3, i.e. is "the PR gate is the backstop" enough, or should Stop emit an advisory when imported paths are unreviewed?
- Q3. Reflog authorship is wording-dependent (`_classify_reflog_subject`: "git's wording is not a contract"). Accept the R3 fallback as the only safeguard, or derive authorship from commit authorship/session id instead?

## Next step

On confirmation of Q1–Q3, write the design: where the path filter enters `coverage_verdict`, and how `_merge_base_verdict`'s fallback interacts with a filtered primary span.
