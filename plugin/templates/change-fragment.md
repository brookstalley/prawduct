---
schema: 1
type: feature
scope: pantry-v1
date: 2026-07-03
title: The shared grocery list replaces the paper one
closes: [PAN-7K2Q]
---
Copy this file to `.prawduct/changes/<scope>.md`, one file per scope, where `<scope>` is the
`scope:` of the build plan the work belongs to. Two branches never edit the same file, so the
change record merges without conflicts. Every file in that directory is release-pending: the
release cut moves a shipped fragment into the change-log archive and removes the file.

Frontmatter keys, all validated at the PR:
- `schema` is always 1.
- `type` is one of: feature, fix, chore, docs, refactor, perf, governance.
- `scope` equals the filename stem.
- `date` is YYYY-MM-DD.
- `title` is a one-line headline.
- `closes` (optional) lists the backlog items this change closes: `owner/repo#N` for an issue, or
  `PFX-XXXX` for the markdown backlog. The PR body's `Closes` lines and the close at merge are
  generated from it.
- `reopens` (optional) names an already-released scope this change reopens; give the fragment
  its own scope, such as `<scope>-reopen-1`.

Replace this text with what changed and why, naming every chunk this scope shipped. Use `###`
for subheadings, because `##` starts a new entry once the fragment is archived.

## Consumer note
What someone using this product needs to know about this change. Where the repo publishes release
notes, the release cut copies this text into them. When there is nothing to tell them (release
mechanics, test-only or repo-internal work), write exactly one line instead: `none: <reason>`.
