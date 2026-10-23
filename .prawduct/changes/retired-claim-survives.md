---
schema: 1
type: feature
scope: retired-claim-survives
date: 2026-10-22
title: Record-lint reports a retired claim's wording wherever it still survives
closes: [brookstalley/prawduct#136]
---
When a governing record retires a claim, the old wording keeps surviving in places the author's
sweep never reached. One governed product recorded thirteen such recurrences in four sessions, and
the author's own sweep caught none. A new record-lint check, `retired-claim-survives`, makes the
literal part mechanical.

A `Retires:` field on a `## Direction` norm entry lists the retired phrasings in double quotes.
So does a `retires:` list on a `technical_decisions` / `design_decisions` record in
`project-state.yaml`. The check searches every tracked file and every open backlog issue for
those phrases and reports each survivor as a WARNING at its line. The search ignores case and
follows a phrase across a line wrap. It skips history (archives, change-logs, fragments, a frozen
`backlog.md`), the declarations themselves, and lines acknowledged with
`prawduct:allow prawduct/retired-claim-survives -- <reason>`. Files the change edits are searched
like any other. An unreadable backlog reports `unchecked`, never clean.

It catches literal survivors, including those in files being edited and in the backlog. It does
not catch paraphrase (Critic Goal 4) or a finding's sites consumed only in part
(`verify-resolutions`). The tests replay all thirteen recorded recurrences and pin both halves of
that statement.

This repo's first run made the stage-keyed norm's existing `Retires:` line live. It found nine
survivors in tracked files. Three of them are invisible to a case-sensitive, per-line grep: two
are wrapped across lines and one is lowercased. All nine were
quotations: absence tests, budget-ledger comments and the assessment that argued for the
retirement. Each carries a waiver with its reason.

### Added
- #136: `retired-claim-survives` record-lint check (`lib/retired_claims.py`), WARNING; the `Retires` field in `docs/norms.md` § Anatomy and § Amendment; its waiver id in `docs/waivers.md`

## Consumer note
- A new record-lint check, `retired-claim-survives`, reads `Retires:` phrases (`docs/norms.md`
  § Anatomy). A repo that declares none sees only a new zero in the review fact's `record_lint`
  counts. A repo whose norms already carry a `Retires:` line with quoted phrases gets a WARNING
  for each surviving copy at its next boundary review. Rewrite each one, or waive a quotation
  with `prawduct:allow prawduct/retired-claim-survives -- <reason>`.
- When `backlog_service_repo` is set, the check also reads every open issue from the local cache.
  A cache that was never synced, or cannot be read, reports `retired-claim-survives unchecked`
  until `prawduct-hook backlog sync` runs.
