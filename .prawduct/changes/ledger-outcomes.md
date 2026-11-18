---
schema: 1
type: fix
scope: ledger-outcomes
date: 2026-11-18
title: The governance ledger says it holds reviews, never their outcomes, and names the command that shows a finding's outcome
closes: [brookstalley/prawduct#606]
---
#606 read `.prawduct/.governance-ledger.jsonl` as the shared audit trail. It saw every finding
raised and none discharged. The issue allowed two fixes: mirror `resolution` and `disposition`
facts into the ledger, or say where the ledger is described that it holds reviews only. This
change says so. It mirrors nothing.

**Why not mirror.** The issue's premise was that the ledger is committed and shared. It is not. It
has been in the managed gitignore (`core.GITIGNORE_ENTRIES`) since the commit that created it,
and it is per worktree. (#606 measured it committed in the reporting repo, which the managed gitignore does not intend.) So a
mirrored outcome would reach only readers in one worktree, and each of them can already read the
clone-wide store. The record that does travel was built after #606 was filed: the evidence
notes on `refs/notes/prawduct` (#1052). Consolidation attaches each `review` and `resolution` fact
to a note (`critic_consolidate._attach_note`). `/prawduct:pr` runs `prawduct-hook evidence sync`
after each push, and session start ingests the notes. A mirror would give one fact a second home
and grow a file no reader needs. The one ledger consumer that reports outcomes, `review-stats`,
already gets them by joining each review event to the store's facts by review id
(`telemetry._read_dispositions`).

**What changed.** A new paragraph in `lib/ledger.py`'s docstring, "Reviews, not their outcomes",
says the ledger is telemetry and not an audit trail. It says where an outcome lives and which
outcomes travel: `resolution` facts on the notes, `disposition` facts never
(`evidence.TRANSPORTED_KINDS`). It names `prawduct-hook render-dispositions` as the command that
shows each finding's outcome. The same statement, shorter, is now in `docs/governance-telemetry.md`,
in `documentation/project-structure.md`'s tree line, and in `data-model.md`'s Governance Ledger
section. That section used to say the ledger was "for audit/telemetry". It now says telemetry.

`tests/test_ledger_holds_no_outcomes.py` pins each of these claims to the code it depends on:

- no ledger kind records an outcome, with a control that adds `finding.resolution`;
- the ledger stays gitignored and outside the committed paths;
- the docstring's transport sentence matches `TRANSPORTED_KINDS`;
- `render-dispositions` is a dispatched subcommand;
- each description names that command.

The docstring and description tests failed before the prose was written.

## Consumer note
`.prawduct/.governance-ledger.jsonl` is review telemetry for this worktree. It is not your audit
trail, and it never records whether a finding was fixed, accepted or filed. To see a finding's
outcome, run `prawduct-hook render-dispositions` (`--review <id>` or `--scope <scope>`). Fixes
verified by `verify-resolutions` reach your other clones with the reviews when `/prawduct:pr`
pushes. ACCEPT and FILE dispositions stay in the clone that recorded them.
