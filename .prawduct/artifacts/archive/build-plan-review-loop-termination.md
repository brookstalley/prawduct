---
artifact: build-plan
version: 2
scope: review-loop-termination
depends_on: []
last_validated: 2026-07-28
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High. Parent requirement is **CRT-8N5V**, filed 2026-07-28 from an owner escalation with a
live reproduction in the same session. The mechanism was read out of the code (`coverage_algebra`,
`gates`, the two review protocols) rather than inferred, and the fix was scoped by an explicit owner
ruling ("instructions first, code after").

**Open assumption:** that the instruction-half alone changes agent behaviour. It is **not** assumed to
be sufficient — `CRT-4J8W` (shipped 2026-06-10) fixed the same symptom structurally and it recurred,
so the structural half is tracked as remaining scope rather than treated as optional polish.

## Status

- [ ] Chunk 01: The terminating rule, the severity contract, and the budget raise

Context: One chunk, built 2026-07-28. Retrospective plan — the work shipped first and this artifact
was written when `regen-views --check` failed closed on a change-log entry whose `scope=` had no plan
file (the fail-closed behaviour working as designed, VWS-6R4T).

## Build Chunks

### Chunk 01: The terminating rule, the severity contract, and the budget raise

**Goal:** Give the Critic review loop an exit condition, on both sides of it.

**Covers:** CRT-8N5V (instruction half). **Type:** code (governance prose + test budgets).

**The defect.** WARNING and NOTE gate nothing — both the PR gate and the Stop gate require only
*coverage* plus *zero unresolved BLOCKING*. But `building.md` said warnings "should be addressed,"
which reads as must-fix. So: agent fixes a warning → the fix is a commit → the commit outruns
coverage → a new review runs → it reviews the records just written → prose always has a truer
phrasing. Measured live: **four rounds, ~40 minutes, on a ~40-line code change**, every finding
correct, none blocking, the last round required by no gate at all.

**Done when:**
1. `methodology/building.md` — once zero blocking remain, **file the rest rather than fixing them**;
   re-run the gate rather than infer another round from stale output. ✅
   **SUPERSEDED 2026-07-29** — the filing-as-default half was reversed within the week. The shipped
   text is now "fix, accept, or file; never file by default", with ACCEPT the default and FILE
   requiring a named trigger (`skills/critic/review-cycle.md`). Filing-as-default took open items
   from 50 → 180 in 26 days. The re-run-the-gate half of this line still stands. Recorded rather
   than rewritten: this plan is the history of what shipped, and the reversal is part of it.
2. `skills/critic/review-protocol.md` — WARNING means true **and** worth the builder's time; name the
   consequence or rate NOTE. Record-only prose defaults to NOTE unless it ships as a false claim or
   misleads someone into a wrong action. ✅
3. `skills/critic/review-cycle.md` — the full rule under "The review loop terminates": exit
   condition, the re-run-the-gate instruction, the `is_judgeable_path` trap, both severity bars with
   examples, the diminishing-returns signal. ✅
4. Token budgets raised by **owner ruling** — `review-protocol.md` 3530 → 3620, `building.md`
   4600 → 4660 — with the departure recorded at both assertions. ✅

**Why the budgets moved rather than the prose being trimmed to fit.** Both files sat at **4 tokens of
headroom**, pinned there by MET-3Q8V's prose diet, whose success line reads "stay green without
raising budgets" and whose test comments say "the next addition trims or relocates first." Three
compression passes ran first and landed +43 over. Trimming to fit would have deleted a real check to
make room for a rule that removes far more work than it costs. **The trim-or-relocate rule still
stands — it was overridden once, on the record, for this.**

**Verification:** suite green (2683 on the isolated branch off `develop`; 2733 on the release branch
carrying it). No new tests — the change is prose plus two raised assertions, and the assertions are
themselves the guard.

## Remaining scope — tracked by CRT-8N5V, deliberately NOT in this plan

1. **COV-3M8Q** — comment/docstring-only `.py` should be non-judgeable. `stage: research`; needs an
   owner ruling on whether an AST-equivalence proof is the banned content inspection, and it moves in
   the **unsafe direction** (removes review coverage).
2. **Structural enforcement** — nothing detects an agent starting round N+1 against an already-passing
   gate. A `critic-begin` refusal would bind regardless of whether the prose was read. This is the
   half `CRT-4J8W`'s recurrence says is load-bearing.
3. **Narrowing `verify-resolutions`** — it runs Goals 1-3 over the whole delta, which is why
   record-writing enters its scope at all. The deeper fix; needs design.
