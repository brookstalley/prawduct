---
schema: 1
type: fix
scope: change-log-fragments-advisory
date: 2026-11-01
title: The session briefing tells a product still on the single-file change log that it can move onto fragments
---
Products onboarded before change fragments shipped were not moving onto them. The migration
(`migrate-change-log`) only ever ran when the owner ran it, and the only thing that offered it was
`/prawduct:doctor` check #22. Doctor runs only when someone runs it, so a repo that never ran it
was never told. A scan of the owner's sibling repos on 2026-11-01 found 28 still on the legacy log
and two that had migrated.

A new advisory probe, `change-record:change-log-fragments-available`
(`plugin/lib/change_record_probes.py`), fires when `.prawduct/change-log.md` is committed and
`.prawduct/changes/` does not exist. It routes to `/prawduct:doctor`, where check #22 keeps the
procedure, and doctor's routing table now sends the advisory there. The apply still needs the
owner's go-ahead. Once the migration has written `.prawduct/changes/`, the advisory resolves itself.
When the committed install reference pins a release that cannot read fragments, the owner text
leads with moving the pin. The advisory is ordered before `change-log-union-merge`, because
migrating makes the union line unnecessary.

## Consumer note
If your product still records changes in `.prawduct/change-log.md`, the session briefing now says
so and offers to move it onto per-change files under `.prawduct/changes/`, so branches stop
conflicting on one shared file. You see a dry run first, nothing is written until you approve it,
and the move is one commit you can revert.
