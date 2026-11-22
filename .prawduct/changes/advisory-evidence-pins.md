---
schema: 1
type: fix
scope: advisory-evidence-pins
date: 2026-11-18
title: changing an advisory's literal evidence now fails a test until its probe version moves
closes: [brookstalley/prawduct#1192]
---
An advisory's id hashes its probe version with its evidence. New evidence under an old version
therefore mints a new id that reads as an accident: the open advisory is resolved as if its
condition had cleared, instead of being superseded by the refined one. The advisory spec says to bump
the version, and that was a rule to remember at the edit. `tests/test_advisory_evidence_pins.py` now
pins every probe candidate whose evidence is spelled as literals or module constants: a changed
digest under an unchanged version fails, and the failure names the remedy. Candidates whose evidence
is built from live data are counted rather than pinned, so a literal moved behind a helper shows up
as a changed count. `advisory_store.registered_versions()` reads the version each type is stamped
with, without running a probe.

The case that prompted this, the gitignore probe's `contract-ignored-by-rule` evidence reworded under
version 1, needs no bump: that advisory type has not shipped in a release, so no released id can go
stale.

## Consumer note
none: a test-only guard; no advisory id changes
