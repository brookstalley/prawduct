# Issue #622 — Migration runbook omits post-cutover repair and handoff steps: Requirements

`status: draft · stage: requirements · area: backlog · added: 2026-08-08 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/622`

> **Provenance note (2026-08-16).** This analysis was written 2026-08-08 by an earlier scheduled
> session but committed only to a branch (`claude/youthful-galileo-3ygn67`) that was never merged
> into `develop`, leaving the work stranded and the issue's `stage:requirements` label stale. A
> later session found the branch, re-verified every "Grounding facts" claim below against current
> `develop` (`plugin/skills/backlog/migration-scrub.md` has changed only in minor rewording since
> this branch's base commit — no drift found), and landed it here unchanged. Ironic, given the
> subject: this is itself an instance of the "work completes, the handoff step is missing" failure
> class #622 exists to close in the runbook it amends.

Related: `plugin/skills/backlog/migration-scrub.md` (the runbook this item amends),
`documentation/backlog-service-issue-standard.md` (the standard 6b lints against), #621 (W1
read-through cache — the sequencing blocker this item was filed behind; **closed 2026-08-07**, so
this item is now unblocked), #623 (a separate item that gives `doctor` an automated `gh` auth
preflight check — this item's 6d is a documentation statement only, not that tooling).

## Problem

The runbook (`migration-scrub.md`) is thorough on the dangerous, hard-to-reverse parts — target
binding, id validity, the preflight title refusal, the completeness gate (`verify-migration`),
disposition ordering after the gate. It says nothing about the repo *around* the backlog: items
the importer silently skipped restructuring, issues already on the target that were never checked
against the issue standard, documentation elsewhere in the repo left pointing at a now-frozen
file, a second archive file left unbannered, and what a downstream contributor needs to keep
working after cutover.

A live 415-item migration (discodon, prawduct v3.2.7, 2026-08-07) hit all seven gaps below. The
migration itself completed clean — every gap is a **process** hole, not an outcome defect — but
each one recurs on every future migration: the owner's 2026-08-07 ruling puts 20–50 repos still to
migrate.

## Grounding facts

Verified against this repo's current `plugin/skills/backlog/migration-scrub.md` and
`plugin/lib/backlog/`, not carried over unread from the discodon writeup:

- **Gap 1 (adopted items keep their pre-restructure title/body) still applies.** `--restructure`
  is consumed only by `backlog import` (`migration-scrub.md` Step 4), which applies it at create.
  An item the importer adopts by its `id:PFX` alias — already on the target from an earlier
  partial run — is looked up, not re-created, so the plan never touches it. No later step
  re-applies a restructure plan to an already-existing issue.
- **Gap 2 (nothing inspects what's already on the target against the standard) still applies, and
  no bulk-lint command exists to close it without new adapter code.** `issuefmt.lint()` is called
  in exactly two places: `core.py`'s `file`/`update` write paths (lint findings ride alongside a
  write) and `restructure.py`'s `restructure-preview` (which lints entries in an operator-supplied
  **plan**, built from the **source markdown** — never from a live `list`/`get` read of the
  target). There is no "lint this already-created issue" command. Because #622 is scoped as a
  runbook (process) change, not adapter/importer code (see Scope-out below), 6b's "lint" is a
  **manual step against the standard document**, not a new command — see Decision 2.
- **Gap 3 (no documentation-sweep step) still applies.** Step 6 ("Cut over") banners
  `.prawduct/backlog.md` and flips `backlog_service_repo`; nothing in the runbook greps the rest of
  the repo for stale instructions or an anchor-doc pointer. (The concrete instances discodon found
  — `DEVELOPMENT.md`, `TOKEN_COST_TRACKING.md` — live in the discodon repo, not this one; they are
  evidence for the shape of the gap, not something this repo itself needs to fix.)
- **Gap 4 (a separate `--archive` file gets no banner) still applies.** Step 6's "mark the source
  file itself" instruction only describes bannering `.prawduct/backlog.md`. `import`,
  `verify-migration`, and Step 3c's archive-scope explanation all accept a **separate**
  `--archive <file>` (confirmed: `[--archive <archive>]` appears on the `import` and
  `verify-migration` command lines), and that file is never mentioned as something to banner.
- **Gap 5 (archive wording presumes one shape) still applies, but not as a literal misstatement in
  Step 6 today** — Step 6 currently says nothing about archive shape at all (see Gap 4). Step 3c
  *does* already carry a detailed, correct explanation of what `open`/`all` do to a **separate**
  archive file. The fix is Step 6 telling the operator to check which shape they have (a `##
  Archive` section inside `backlog.md`, a separate `--archive` file, or no archive) and banner
  accordingly — not a wording correction to an existing false claim.
- **Gap 6 (`refresh-counts` unmentioned) still applies, and the op already exists** —
  `prawduct-hook backlog refresh-counts --repo <target>` is a real, documented op
  (`lib/backlog/cli.py`, `_ALWAYS_ALLOWED` set — "never withheld" per its own comment) that derives
  and persists the GV2 briefing snapshot. The runbook never calls it out; this is a doc-only fix,
  no new tooling needed.
- **Gap 7 (contributor `gh` auth prerequisite unstated) still applies.** `transport.py` confirms
  the adapter drives `gh` as a subprocess and "never manages a token" — it relies on
  `~/.config/gh`. The runbook covers the operator running the scrub and says nothing about what a
  teammate needs once the cutover key is committed and pulled. This item's fix is a **stated
  prerequisite in the runbook**, not new tooling — #623 (separate, stage:requirements) is where an
  automated `doctor` check for this is tracked; 6d does not duplicate or block on it.

## Decisions

**1. Where the four fixes land.** All four are edits to the single existing file
`plugin/skills/backlog/migration-scrub.md` — three new lettered sub-steps after Step 6
(6b/6c/6d, following the file's existing `3b`/`3c` lettering convention for steps that
insert without renumbering the whole sequence) plus one addition to Step 6's own "mark the source
file itself" guidance. No new file, no new skill, no new adapter command — the issue's own
scope-out already rules those out, and nothing found while grounding this item creates a reason to
revisit that.

**2. 6b's "lint" is a manual checklist step, not a new command.** Building a bulk
"lint every issue on the target" command would be adapter/importer code, explicitly out of scope
for this item. 6b instead instructs the operator to: (a) list every issue carrying an `id:PFX`
alias label (`backlog list --repo <target> --json`, filtered on the alias-label namespace), (b)
for each, compare its live title/body against `documentation/backlog-service-issue-standard.md`
§1–§2 by hand, and (c) where the item was also named in the confirmed restructure plan
(Step 3b), re-apply that plan's entry with `backlog update <id> --repo <target> --title ...
--body ...` — the existing per-item write path, unchanged. This keeps 6b entirely inside
"process," consistent with the issue's scope-out, at the cost of being manual rather than
automated; a future item can propose a bulk-lint command against the standard if this proves too
slow in practice, but that is new scope, not this item's.

**3. 6c is a grep-and-fix instruction, not a new tool.** "Sweep inbound references" is written as:
grep the repo for the source backlog path (`.prawduct/backlog.md` and any configured archive
path), read each hit in context (not just the filename), fix any hit that gives an *instruction*
(tell contributors to file into the frozen file) rather than merely linking to it, and explicitly
check the product's own anchor doc (`CLAUDE.md` or equivalent) for whether it names where the
backlog lives — adding a pointer if it does not already have one. This mirrors the existing
Step 1b "grep, don't auto-fix" pattern already used elsewhere in the runbook, rather than
introducing a new mechanism.

**4. Step 6's archive-banner gap is closed by extending the existing "mark the source file itself"
guidance**, not by rewriting Step 3c (which already correctly explains archive-scope semantics).
Step 6 gains an explicit instruction: determine which archive shape applies (a `## Archive`
section inside `backlog.md`, a separate file named at `--archive`, or none), and banner whichever
file(s) actually hold un-migrated history — never assert a shape without checking.

## Requirements

MUST unless marked SHOULD.

- **MSR1** `migration-scrub.md` gains a new Step **6b — repair adopted items**: for every issue the
  import adopted by its `id:PFX` alias (i.e., already existed on the target before this run),
  re-apply the confirmed restructure plan's entry for that item via `backlog update`, then compare
  every aliased issue on the target against the issue standard by hand (Decision 2) and record any
  divergence found for owner disposition.
- **MSR2** `migration-scrub.md` gains a new Step **6c — sweep inbound references**: grep the repo
  for the pre-migration backlog path(s) (source file and any `--archive` file), fix any hit that
  states an actively wrong *instruction* (not only stale links), and explicitly name the anchor
  doc (`CLAUDE.md` or equivalent) as a location to check for a backlog-location pointer.
- **MSR3** `migration-scrub.md` gains a new Step **6d — hand off**: run
  `prawduct-hook backlog refresh-counts --repo <target>` (naming the existing op), and state
  plainly that every contributor needs the `gh` CLI installed and authenticated with `repo` scope
  for the migrated backlog to work for them (naming `~/.config/gh` as the credential source the
  adapter relies on) — a documentation statement, not new tooling; #623 is where automated
  detection of this is tracked, separately.
- **MSR4** Step 6's "mark the source file itself" guidance is extended to instruct the operator to
  determine which archive shape is in play (in-file `## Archive` section, separate `--archive`
  file, or none) before writing any banner, and to banner **every** file that still holds
  un-migrated history — not only `.prawduct/backlog.md`.
- **MSR5** None of MSR1–MSR4 introduce a new `prawduct-hook backlog` op, flag, or code change to
  `plugin/lib/backlog/`. Every instruction resolves to an existing op (`list`, `get`, `update`,
  `refresh-counts`) or a manual review step.

## Acceptance

- [ ] `migration-scrub.md` carries new Steps 6b, 6c, and 6d, each naming a concrete action and
      (where applicable) an existing `prawduct-hook backlog` command.
- [ ] Step 6's archive-banner guidance handles both shapes (in-file section vs. separate
      `--archive` file) and tells the operator to check which they have before writing a banner.
- [ ] 6c names the anchor doc (`CLAUDE.md` or equivalent) explicitly and covers wrong
      *instructions*, not only stale links.
- [ ] 6d names `refresh-counts` and states the contributor-side `gh` auth prerequisite in plain
      language.
- [ ] No change to `plugin/lib/backlog/` or any other adapter/importer code is required to satisfy
      this item.

## Scope-out (this item)

- Any new `prawduct-hook backlog` command or flag (e.g. a bulk lint-against-standard command,
  automated reference-sweep tooling) — MSR5 rules these out; a future item may propose one if the
  manual steps here prove too slow at scale, but that is new scope.
- The automated `gh` auth preflight check itself — tracked separately by #623; MSR3 only states
  the prerequisite in prose.
- Any change to this repo's own `CLAUDE.md`, `DEVELOPMENT.md`, or similar — the gaps that
  motivated MSR2 were found in a different product's repo; this item only changes the *runbook
  instruction* that future migrators follow in their own repos.
- Exact wording/placement of the new steps within the file (heading level, precise phrasing) —
  design-stage detail.

## Evidence / references

- `plugin/skills/backlog/migration-scrub.md` — the runbook amended by this item; Steps 1b, 3b, 3c,
  4, 5, 6 read in full to confirm which of the seven gaps are still open against the current file
  (all seven; see Grounding facts).
- `plugin/lib/backlog/core.py` (`file`, `update_item`) and `plugin/lib/backlog/restructure.py`
  (`restructure-preview`) — confirmed `issuefmt.lint()`'s only two call sites, grounding Decision 2
  (no existing bulk-lint-the-target command).
- `plugin/lib/backlog/cli.py` — confirmed `refresh-counts` is an existing, always-allowed op
  (`_ALWAYS_ALLOWED`), grounding MSR3 as a documentation-only fix.
- `plugin/lib/backlog/transport.py` — confirms the adapter drives `gh` as a subprocess and relies
  on `~/.config/gh`, never managing a token itself, grounding MSR3's stated prerequisite.
- `documentation/backlog-service-issue-standard.md` §1–§2 — the standard 6b's manual lint step
  checks against.
- Issue #622 body — reproduces discodon's `migration-process-gaps.md` (2026-08-07) verbatim as the
  evidentiary source for all seven gaps.
- Issue #621 (closed 2026-08-07) — the W1 sequencing blocker this item was filed behind; its
  closure is why this item is picked up now.
