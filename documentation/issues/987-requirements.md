# Issue #987 — Telemetry: Re-run the Escape Metric Near 2026-11-10: Requirements

`status: draft · stage: requirements · area: telemetry · added: 2026-10-21 · source: scheduled backlog session · issue: https://github.com/brookstalley/prawduct/issues/987`

Related: #984 and #989 (items the result may change), `.prawduct/artifacts/governance-roi-study-2026-10.md`
(the study; "Recommendations" and "Reproducing" sections), `.prawduct/research/escape-2026-10/escape.py`
and `stats.py` (the instrument).

## Problem

The governance ROI study could not score 30-day escapes for repo F (the fast ungoverned repo)
for its October work: the batch was too recent for the 30-day window (`escape.WINDOW_DAYS`) to
close. That score is the definitive check on whether fast work escapes more than governed work.
The study says "re-run after 2026-11-10" and nothing makes anyone run it.

Success: after the window closes, one owner-run produces repo F's escape rate, it is compared with the
governed repos' rate over the same window, the result is written into the study, and #984/#989 are
corrected or explicitly confirmed unchanged.

## Grounding facts (verified 2026-10-21)

- The instrument is public and in this repo: `.prawduct/research/escape-2026-10/` (`escape.py`,
  `stats.py`, `branch_landings.py`, `test_escape.sh`). The study's "Reproducing" section gives the
  steps; step 2 already names this re-run (`--branch owner/repo=BRANCH`, "#987").
- The inputs (repo list, branch list, prior `landings.jsonl`) are private and live on the owner's
  machine. They cannot be run from a cloud or scheduled session, so the run is owner-executed.
- `escape.py` defines a landing's escape as a later landing rewriting its lines within
  `WINDOW_DAYS = 30`. A landing whose window has not closed is not scoreable.
- The revisit metadata (`revisit: 2026-11-10` on the issue) already raises the `revisit-due`
  advisory once the date passes. It says that a date arrived, not what to run.
- `--branch` emits only landings the main branch lacks, tagged with `branch`. Written to the same
  file as the default run, or also present in `fast_landings.jsonl`, the same landing is counted twice in
  the study's section 5 throughput. The issue's acceptance flags this (PR review round 3, note 2).

## Requirements

### R1 — Run scope and timing

- R1.1 The run covers every repo-F landing made in October 2026, on `develop`/default branch **and**
  its integration branches, using the same `escape.py` version the study used.
- R1.2 A landing is scored only when its full 30-day window has closed at run time. The earliest valid
  run date is landing-date + 30 days of the **last** October landing in scope, not a fixed date. If that
  is later than 2026-11-10, the run waits; the 2026-11-10 date is a lower bound.
- R1.3 Landings with an open window are reported as `window-open`, listed by count, and excluded
  from the rate. The write-up states both denominators (all landings, scoreable landings).
- R1.4 The governed repos are re-scored over the same calendar window so the comparison is like for like.

### R2 — No double counting

- R2.1 Output of a `--branch` run goes to a file separate from the default-branch run.
- R2.2 Either `stats.py` skips rows carrying a `branch` field when it also reads the branch-landings file,
  or the run fails on a landing id that appears twice across inputs. Silent double counting is the failure
  to prevent; the choice between skip and fail is a design decision.
- R2.3 `test_escape.sh` (or a sibling check) covers the duplicate case with a known answer, and has been
  seen to fail when the duplicate is present.

### R3 — Recording the result

- R3.1 The study artifact gains a dated "Escape re-run" section: repo-F rate, governed rate, window,
  both denominators, the `escape.py` version, and whether the study's conclusion holds.
- R3.2 If the result changes the conclusion, #984 and #989 are updated; if not, each gets a one-line
  "checked, unchanged" note. Neither is silently left stale.
- R3.3 Private data (repo names, branch names, landing ids) does not enter the artifact; it reports
  rates and counts only, as the study does.

### R4 — Prompting

- R4.1 The `revisit-due` advisory for this item is acceptable as the prompt, provided the item body names
  the command and where inputs live (it does: the proposed-change section plus the study's Reproducing steps).
  No new mechanism is built for a one-time re-run.

## Scope-out

- Changing the instrument (except R2.2). A different `escape.py` version makes the two runs incomparable.
- Automating the run: its inputs name private repos, so it stays on the owner's machine.
- Any new telemetry; ongoing escape measurement is #951.

## Acceptance (maps to the issue)

- [ ] R1: October landings incl. integration branches, full 30-day window, `window-open` reported
- [ ] R3.1: repo-F vs governed escape rate recorded in the study
- [ ] R3.2: #984/#989 updated or marked unchanged
- [ ] R2: duplicate-landing guard in place and exercised

## Open questions for the owner

1. Date of repo F's last October landing in scope. It sets the earliest valid run (R1.2).
2. R2.2: skip `branch`-tagged rows, or fail on duplicate ids? Recommendation: fail, since a duplicate
   means an input was wired wrong, and a skip hides that.
3. Is the `revisit-due` advisory the intended prompt (R4.1)?
