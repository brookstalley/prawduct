---
schema: 1
type: fix
scope: plan-archive-scope-name
date: 2026-10-25
title: an archived plan's filename names its scope, so plans from one directory no longer collide
---
`archive-plan` kept a plan's own filename in `archive/`. A plan living at the generic
`build-plan.md` therefore archived as a bare `archive/build-plan.md`, which says nothing about
which plan it holds. The next plan archived from the same directory was refused, because that
path was already taken. The PR #1047 reviewer caught this on the refusal-reasons plan.

`plan_archive.archived_name` now appends `-<scope>` from the plan's frontmatter `scope:`, unless
the filename already carries the scope as a hyphen-delimited segment. The established
`build-plan-<scope>.md` names archive unchanged. The scope is appended rather than prefixed,
so the release gate's `release-plan-<version>*.md` glob still finds an archived release plan
(BP8). A scope that is absent, null or not filename-safe (a separator, `..` or a leading dot)
keeps the plan's own name, so frontmatter cannot steer the write outside `archive/`. The
`--dry-run` preview reports the same destination, because both paths call
`archive_destination`.

## Consumer note
- `prawduct-hook archive-plan` (and `plan-backfill`, which archives through it) now writes
  `archive/<name>-<scope>.md` for a plan whose filename does not carry its scope, for example
  `build-plan.md` with scope `demo` becomes `archive/build-plan-demo.md`. Plans already named
  `build-plan-<scope>.md` archive under their own name, as before.
