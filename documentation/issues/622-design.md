# Issue #622 — Migration Runbook Omits Post-Cutover Repair and Handoff Steps: Design

`status: draft · stage: design · area: backlog · added: 2026-08-20 · source: scheduled backlog
session · issue: https://github.com/brookstalley/prawduct/issues/622`

Builds on `documentation/issues/622-requirements.md` (MSR1–MSR5, Decisions 1–4). Requirements
scoped the exact wording/placement of the new steps as "design-stage detail" (its own Scope-out).
This document resolves that: the literal text for Steps 6b, 6c, 6d, and the extension to Step 6's
archive-banner guidance, each ready to paste into `plugin/skills/backlog/migration-scrub.md`
unchanged.

## Summary of what ships

One file, no code — MSR5 already rules out any change to `plugin/lib/backlog/`:

1. **MSR1** — new Step **6b** ("Repair adopted items"), inserted after Step 6's existing content,
   before Step 7.
2. **MSR2** — new Step **6c** ("Sweep inbound references"), immediately after 6b.
3. **MSR3** — new Step **6d** ("Hand off"), immediately after 6c.
4. **MSR4** — the existing "Then mark the source file itself" paragraph inside Step 6 (banner
   guidance) is extended in place to cover both archive shapes.

`plugin/skills/backlog/migration-scrub.md` is the only file touched. Test plan: none — see
"Verification" below.

## Decision — insertion point for 6b/6c/6d

**Directly after the paragraph ending "Everything else in this runbook is unaffected by that
gate." (the last sentence of Step 6's `incoming-bugs/` note) and before the `**7. Apply the
confirmed dispositions...**` header.** This is the one point in the file where Step 6 has fully
finished (gate passed, key recorded, banner written, retirement caveats stated) and Step 7 has
not yet started — matching the requirements doc's Decision 1 ("three new lettered sub-steps after
Step 6") and the file's own `3b`/`3c` precedent for inserting without renumbering the surrounding
sequence.

**Why not fold 6b/6c/6d's content into Step 6 itself, or make them part of Step 7?** Step 6 is
already the runbook's longest step and its own opening sentence calls it "the one step that must
not be taken on trust" — appending three more concerns to it would bury the gate under
housekeeping. Step 7 is scoped narrowly to the owner-confirmed dispositions (folds and drops) and
explicitly says re-running `import`/`verify-migration` after it is destructive; 6b/6c/6d have no
such constraint (6b's `backlog update` calls and 6c/6d's read-only checks are all safe to re-run
or run out of order), so they belong in their own lettered slot, not inside either neighbor's
invariants.

## Section 1 — Step 6b (MSR1)

**Where:** new step, right after Step 6, before Step 7.

```markdown
**6b. Repair adopted items — a restructure plan cannot reach an issue it did not create.**
`--restructure` (Step 3b) applies **at create only**. An issue the import *adopted* by an
existing `id:PFX` alias — already on the target from an earlier partial run — is looked up,
not re-created, so the confirmed plan never touches it, and nothing later repairs that on its
own. Two actions, both manual (Decision 2, requirements doc — this stays a runbook step, not
new adapter code):

- **Re-apply the plan to adopted items.** For every id in the confirmed restructure plan
  (Step 3b) that the import summary reports as *adopted* rather than *created*, re-apply that
  plan entry directly:
  `prawduct-hook backlog update <id> --repo <target> --title "<plan title>" --body "<plan body>"`
  — the same per-item write path Step 7 uses for dispositions, no new command.
- **Lint every aliased issue against the standard.** List everything on the target carrying an
  `id:` alias label — `prawduct-hook backlog list --repo <target> --json --state all`, paging
  with `--page` until a page comes back short of `--per-page` — and filter the returned labels
  for the `id:` namespace yourself: `list` has no facet for it (`stage`/`kind`/`area`/`effort`/
  `impact`/`source`/`tag` are the only label filters `list` accepts). For each, compare its live
  title and body against `documentation/backlog-service-issue-standard.md` §1–§2 by hand.
  **Record any divergence found — do not edit it yourself.** Present it to the owner the same
  way Step 3's disposition table does; this lint surfaces candidates, it does not apply them.

Record which ids were repaired and which were flagged, where the other scrub decisions live
(this repo's own run records it in `.prawduct/artifacts/migration-scrub-decisions.md`).
```

## Section 2 — Step 6c (MSR2)

**Where:** immediately after 6b.

```markdown
**6c. Sweep inbound references — a migration that repoints the tooling and leaves the prose
unchanged is half a migration.** Grep the repo for the pre-migration backlog path(s) — the
source file (`.prawduct/backlog.md` or wherever it lives) and any `--archive` file bound in
Step 0 — and read every hit **in context**, not just the filename:

- Fix any hit that states an *instruction* pointing contributors at the file (for example,
  "file new items here"), not only a stale link. An instruction left unfixed actively
  misdirects the next contributor; a stale link merely under-informs — both get fixed, but the
  instruction is the one that costs someone real work if missed.
- Explicitly check the product's own anchor doc — `CLAUDE.md` or equivalent, the file every
  session and every new contributor reads first — for whether it names where the backlog now
  lives. Add a pointer if it does not already have one. This is the one file the sweep cannot
  afford to skip even when nothing else in the repo mentions the backlog.

This mirrors Step 1b's existing "grep, don't auto-fix" pattern: surface every hit, judge each
one, fix it by hand. No bulk-rewrite tool exists or is being proposed here.

Record what you found and fixed where the other scrub decisions live.
```

## Section 3 — Step 6d (MSR3)

**Where:** immediately after 6c.

```markdown
**6d. Hand off — the operator finishing the scrub is not the only person who needs to know it
happened.**

- Run `prawduct-hook backlog refresh-counts --repo <target>` — an existing, always-allowed op
  that derives and persists the GV2 briefing snapshot. Skip it and the next session's briefing
  has no counts to show, with nothing telling anyone why.
- State plainly, to the team: **every contributor needs the `gh` CLI installed and
  authenticated with `repo` scope** for the migrated backlog to work for them. The adapter
  drives `gh` as a subprocess and never manages a token itself — it relies on `~/.config/gh` —
  so a teammate who pulls the cutover key without that in place sees the backlog simply stop
  working, with no hint that credentials are the cause. (An automated preflight check for this
  is tracked separately, #623; this step is the stated prerequisite, nothing more.)
```

## Section 4 — Step 6 banner guidance extended (MSR4)

**Where:** the existing "Then mark the source file itself" paragraph inside Step 6 (the one
directly after the `backlog_service_repo:` YAML block and before "Unwinding the cutover takes
all three halves"). Replace it in place.

**Before:**

```markdown
**Then mark the source file itself — the key alone leaves it declaring that it is
live.** Setting the scalar changes what the *tooling* reads; it changes nothing a
human sees when they open `.prawduct/backlog.md`, which still carries a "managed via
the backlog skill" header and a `## Open (pickable)` section under it. Write a
frozen-history banner at the head of the source naming the cutover date, the live
tracker URL, and the read commands. Two constraints, both learned the hard way:

- **It must be visible when RENDERED.** An HTML comment is invisible in GitHub's
  rendered view — a reader browsing the file sees a heading and a list of open items
  with no signal at all that it is dead. Use a blockquote.
- **Say that divergence is expected.** The dispositions applied at *Apply the confirmed
  dispositions* land on the tracker and are *not* backported here, so the frozen file
  will show items as open that the tracker has closed. A banner that omits this reads as
  a bug the first time someone reconciles the two.
```

**After:**

```markdown
**Then mark the source file(s) — the key alone leaves them declaring that they are
live.** Setting the scalar changes what the *tooling* reads; it changes nothing a
human sees when they open `.prawduct/backlog.md`, which still carries a "managed via
the backlog skill" header and a `## Open (pickable)` section under it. **First determine
which archive shape is in play** — a `## Archive` section inside `backlog.md`, a separate
file named at `--archive` (Step 0/3c), or none — never assert a shape without checking;
the shapes take different banners. Write a frozen-history banner at the head of **every**
file that still holds un-migrated history (the source file always; the separate archive
file too, if that is the shape you have) naming the cutover date, the live tracker URL,
and the read commands. Three constraints, all learned the hard way:

- **It must be visible when RENDERED.** An HTML comment is invisible in GitHub's
  rendered view — a reader browsing the file sees a heading and a list of open items
  with no signal at all that it is dead. Use a blockquote.
- **Say that divergence is expected.** The dispositions applied at *Apply the confirmed
  dispositions* land on the tracker and are *not* backported here, so the frozen file
  will show items as open that the tracker has closed. A banner that omits this reads as
  a bug the first time someone reconciles the two.
- **A separate archive file needs its own banner, not a mention inside the source
  file's.** A reader who opens the archive directly — without passing through the
  now-bannered source file first — sees only whatever header the archive already
  carried (often something asserting it holds live history moved from `backlog.md`),
  with nothing telling them it too is now frozen, unless this banner corrects it.
```

This resolves Gap 4 (a separate archive file gets no banner) and Gap 5 (the old wording presumed
one shape) from the requirements doc's Grounding facts, without touching Step 3c's already-correct
archive-scope explanation (Decision 4, requirements doc).

## Files touched

| File | Change |
|---|---|
| `plugin/skills/backlog/migration-scrub.md` | New Steps 6b, 6c, 6d (Sections 1–3); Step 6's archive-banner paragraph replaced in place (Section 4) |

No other file changes — MSR5 (requirements doc) rules out any `plugin/lib/backlog/` change, and
nothing here introduces a new `prawduct-hook backlog` op, flag, or code path. Every command named
above (`update`, `list`, `refresh-counts`) already exists and is unchanged by this item.

## Verification

Docs-only change — no test file is added or touched (consistent with `building.md`'s `doc-only`
chunk type). Verification is a direct re-read of the amended `migration-scrub.md` against the
requirements doc's Acceptance list:

- [ ] Steps 6b, 6c, 6d each appear, each naming a concrete action and, where applicable, an
      existing `prawduct-hook backlog` command (`update`, `list`, `refresh-counts`).
- [ ] The archive-banner paragraph (Section 4) handles both shapes and tells the operator to
      check which they have before writing a banner.
- [ ] 6c names the anchor doc (`CLAUDE.md` or equivalent) explicitly and covers wrong
      *instructions*, not only stale links.
- [ ] 6d names `refresh-counts` and states the contributor-side `gh` auth prerequisite in plain
      language.
- [ ] No `plugin/lib/backlog/` file is touched.
- [ ] Every command named in the new text (`update`, `list --state all`, `refresh-counts`)
      matches an existing, currently-working CLI flag — checked directly against
      `plugin/lib/backlog/cli.py`'s `_run_update`/`_run_list`/`_run_refresh_counts` argument sets,
      not assumed from the requirements doc.

## Acceptance (carried from requirements, now with an implementation path)

- [ ] `migration-scrub.md` carries new Steps 6b, 6c, and 6d, each naming a concrete action and
      (where applicable) an existing `prawduct-hook backlog` command — Sections 1–3.
- [ ] Step 6's archive-banner guidance handles both shapes (in-file section vs. separate
      `--archive` file) and tells the operator to check which they have before writing a banner —
      Section 4.
- [ ] 6c names the anchor doc (`CLAUDE.md` or equivalent) explicitly and covers wrong
      *instructions*, not only stale links — Section 2.
- [ ] 6d names `refresh-counts` and states the contributor-side `gh` auth prerequisite in plain
      language — Section 3.
- [ ] No change to `plugin/lib/backlog/` or any other adapter/importer code is required to satisfy
      this item — confirmed above under Files touched.

## Evidence / references

- `documentation/issues/622-requirements.md` — MSR1–MSR5, Decisions 1–4, Grounding facts (all
  seven gaps re-verified against current `develop`).
- `plugin/skills/backlog/migration-scrub.md` — Steps 3b, 3c (the lettered-sub-step precedent
  Section insertion follows), Step 6 in full (the exact paragraph Section 4 replaces), Step 7's
  opening (the boundary 6b/6c/6d sit before).
- `plugin/lib/backlog/query.py:49` (`_LABEL_FACETS`) — confirms `list` has no `id` facet, grounding
  6b's "filter the returned labels yourself" instruction.
- `plugin/lib/backlog/cli.py:320-359` (`_run_update`), `:383-` (`_run_list`, including `--state`)
  — confirms the exact flags 6b's commands use exist today.
- `plugin/lib/backlog/cli.py:28-49` (`_ALWAYS_ALLOWED`) — confirms `refresh-counts` is
  always-allowed, grounding 6d.
- `plugin/lib/backlog/transport.py` — confirms the adapter drives `gh` as a subprocess and never
  manages a token, grounding 6d's stated prerequisite.
- `documentation/backlog-service-issue-standard.md` §1–§2 — the standard 6b's manual lint step
  checks against.
- `plugin/methodology/building.md` — `doc-only` chunk classification, grounding the Verification
  section's "no test file" posture.
