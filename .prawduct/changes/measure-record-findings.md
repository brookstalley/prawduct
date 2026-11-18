---
schema: 1
type: chore
scope: measure-record-findings
date: 2026-11-18
title: tools/measure-record-findings.py measures whether findings about governance records still buy review rounds
---
#771 asks whether record findings (those naming only files under `.prawduct/` or
`.claude/rules/learnings/`) still buy review rounds now that records are oracle rather than review
subject. No tool could answer it. `tools/measure-record-findings.py` (a sibling of
`measure-review-loop-economy.py`, with `--root`, `--since` and `--json`) reads review facts from
each clone's evidence store, classifies each finding as record-only, subject-only, mixed or
no-files using the plugin's own record prefixes, splits by stage, severity and plugin era (before
and after commit `429ac2df`), and reports the record-only share of round-buying (`fixed`) findings
beside the no-files share, with #771's fixed decision rule applied. Refs #771: the issue stays
open until the fleet run is posted there and the rule's outcome is acted on.

## Consumer note
none: a maintainer tool under `tools/`, not shipped in the plugin
