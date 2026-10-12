# Issue #987 — telemetry: re-run the escape metric near 2026-11-10: Requirements

`status: draft · stage: requirements · area: telemetry · added: 2026-10-12 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/987`

Related: #984 and #989 (the items a changed result would update), #951 (`found_by` / B5 escapes — a
different, in-product escape measure; not the same instrument, see Decision 4).

## Problem

The governance ROI study (2026-10) could not score 30-day escapes for the fast ungoverned repo's
October work: the batch was younger than its 30-day window. That score is the check on whether the
fast work escapes more than governed work. The issue says nothing prompts anyone to run it.

This is a one-shot, dated measurement run by the owner, not a feature. The requirements are about
making the run **repeatable, comparable and recorded**, not about building a tool (the instrument is
out of scope).

## Grounding facts

Checked against this tree on 2026-10-12.

- **Neither the instrument nor the study is in this repository.** `git ls-files` shows no
  `escape.py`, no `.prawduct/research/escape-2026-10/`, and no `governance-roi-study-2026-10.md`
  (`.prawduct/artifacts/` holds other artifacts, not this one). The issue's paths are therefore
  unresolvable from a clone; the study artifact the acceptance criteria say to update must be located
  (owner's machine or an unmerged branch) before the run. Other sessions have also reported the
  ROI artifacts missing from `develop` (see #951's and #989's comments).
- **Inputs are deliberately outside the repo.** Repo list, branch list and prior landings name private
  repos and live on the owner's machine. A scheduled session cannot run this; it needs the owner.
- **The "nothing prompts anyone" premise is partly stale.** The issue's block carries
  `revisit: 2026-11-10`. `plugin/skills/backlog/SKILL.md:75` documents a dated `revisit:` as
  machine-fired: a past date raises a `revisit-due` advisory while the item is open. So a prompt
  exists once the date passes, provided the item stays open and the advisory is read. What it cannot
  do is say *what to run* — that lives only in the issue body.
- **The 30-day window is the binding constraint.** A landing on day D is scoreable from D+30. The
  newest October landing in scope sets the earliest valid run date; 2026-11-10 is correct only if the
  last October landing was on or before 2026-10-11. Landings on 2026-10-31 close on 2026-11-30.
- **The double-count hazard is real and already raised.** `escape.py --branch` output merged with the
  branch-landings file counts the branch's landings twice in section 5's throughput (PR review round 3,
  note 2, per the issue).

## Decisions

1. **Scope is the run and its record, not the instrument.** Same `escape.py` version as the study;
   no changes (issue scope-out, restated).
2. **The run is owner-executed.** The routine's only role is the reminder and the checklist; it does
   not touch private repos.
3. **Scoreability is checked per landing, not per batch.** A landing whose 30-day window is still
   open is reported as `window-open` and excluded from the rate, never scored early. The
   denominator is stated.
4. **This measure stays separate from #951's B5.** `escape.py` is a retrospective, git-derived,
   cross-repo score over bare clones. #951 is an in-product field on bug intake. Results are not
   merged or compared as one series.

## Requirements

MUST unless marked SHOULD.

- **ESC1** Before running, record the instrument identity: the `escape.py` version (commit or hash)
  the study used, and confirm the re-run uses the same one. A mismatch stops the run.
- **ESC2** Inputs are fresh bare clones taken on the run date, with the run date recorded in the
  output. The fast ungoverned repo's integration branches are included alongside `develop`.
- **ESC3** The run covers all of that repo's October landings. Any landing with an open 30-day
  window is listed as `window-open`; if any exist, the run is deferred or reported partial with the
  count, per Decision 3.
- **ESC4** The same-window governed comparison uses the governed repos' landings over the identical
  dates, so rates are comparable. The comparison states both denominators.
- **ESC5** If `--branch` is used, its output goes to a separate file, or `stats.py` skips rows that
  carry a `branch` field. Either way, section 5's throughput must not count a landing twice. After
  the run, check this by counting landings by id in the combined input; a duplicate id fails the run.
- **ESC6** The result is recorded in the study artifact: both rates, both denominators, the run date,
  the instrument version, and the `window-open` count.
- **ESC7** If the result changes the study's conclusions, #984 and #989 are updated in the same
  sitting, naming the changed conclusion. "No change" is also recorded, so the item can close.
- **ESC8 (SHOULD)** The issue body (or a comment) carries the exact command lines and the location of
  the private inputs file, with paths redacted as the owner prefers, so the run does not depend on
  recall. The `revisit-due` advisory then points at something actionable.
- **ESC9 (SHOULD)** If the last October landing falls after 2026-10-11, the `revisit:` date is moved to
  that landing's date + 30 days rather than running early.

## Acceptance

- [ ] The run covers the fast ungoverned repo's October landings, integration branches included, with
      a full 30-day window (ESC2, ESC3)
- [ ] The instrument version matches the study's and is recorded (ESC1)
- [ ] Its escape rate is compared with the governed repos' over the same window and the result is
      recorded in the study artifact with denominators (ESC4, ESC6)
- [ ] #984 and #989 are updated if the conclusions change, or "no change" is recorded (ESC7)
- [ ] No landing is counted twice in section 5 (ESC5)

## Open for the owner

1. Where is `governance-roi-study-2026-10.md` and the `escape-2026-10/` directory today? They are not
   in this repo, and the acceptance criteria write to them.
2. When was the fast repo's last October landing? That fixes the earliest valid run date (ESC9).
3. Is `revisit-due` the intended prompt, or is a separate calendar reminder wanted? If the former,
   ESC8 is what makes it useful.

## Scope-out

- Changing or extending `escape.py`.
- Owner-attention measurement and throughput in kLOC (the study's own scope-outs).
- Wiring the escape score into `prawduct-hook stats` (that is #951 / #989 territory).

## Evidence / references

- GitHub issue #987 — problem, proposed change, acceptance.
- `plugin/skills/backlog/SKILL.md:75` — `revisit:` date semantics (`revisit-due` advisory).
- Comments on #951 and #989 — the ROI audit and study artifacts are absent from `develop`.
